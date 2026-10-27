"""
Jobs router – batch download job lifecycle endpoints.

Endpoints
---------
POST   /api/jobs                           Create a job and start it
GET    /api/jobs/{job_id}                  Fetch full job state (polling)
GET    /api/jobs/{job_id}/events           SSE stream of live progress
POST   /api/jobs/{job_id}/cancel          Cancel a running job
GET    /api/jobs/{job_id}/files/{index}   Download a single MP3
GET    /api/jobs/{job_id}/zip             Download all MP3s as a ZIP
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import zipfile
from datetime import date
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.services.downloader import VALID_QUALITIES, DEFAULT_QUALITY
from app.services.rate_limiter import get_client_ip, job_rate_limiter
from app.services.job_manager import (
    cancel_job,
    create_job,
    get_job,
    retry_item,
    start_job,
    subscribe,
    unsubscribe,
)
from app.services.link_parser import parse_links

logger = logging.getLogger("beatbatch.router.jobs")

router = APIRouter(prefix="/api", tags=["jobs"])


# ---------------------------------------------------------------------------
# Security helper
# ---------------------------------------------------------------------------

def _safe_path(base: Path, *parts: str) -> Path:
    """
    Resolve a path built from *parts* relative to *base* and raise 400
    if the result escapes the base directory (path-traversal protection).
    """
    try:
        candidate = (base / Path(*parts)).resolve()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid path.") from exc

    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Path traversal detected.")

    return candidate


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CreateJobRequest(BaseModel):
    text: str = Field(..., max_length=150_000, description="Raw text of YouTube URLs")
    quality: str = DEFAULT_QUALITY

    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: str) -> str:
        if v not in VALID_QUALITIES:
            raise ValueError(
                f"quality must be one of {sorted(VALID_QUALITIES)}, got {v!r}"
            )
        return v


class InvalidLineOut(BaseModel):
    line_number: int
    text: str
    reason: str


class CreateJobResponse(BaseModel):
    job_id: str
    quality: str
    total_valid: int
    total_invalid: int
    invalid_lines: list[InvalidLineOut]


# ---------------------------------------------------------------------------
# POST /api/jobs  – create + start a job
# ---------------------------------------------------------------------------

@router.post("/jobs", response_model=CreateJobResponse, status_code=202)
async def create_job_endpoint(body: CreateJobRequest, request: Request):
    """
    Parse the submitted text, validate URLs, create a job, and start it.

    Returns immediately (202 Accepted) with the job_id so the client can
    connect to the SSE stream and poll for state.

    Invalid lines are reported but do not prevent the job from starting.
    A job with zero valid links returns 422.
    """
    # ── Rate limiting guard ────────────────────────────────────────────────
    client_ip = get_client_ip(request)
    job_rate_limiter.check(client_ip)

    valid_links, invalid_lines = parse_links(body.text)

    if not valid_links:
        raise HTTPException(
            status_code=422,
            detail="No valid YouTube URLs found in the submitted text.",
        )

    if len(valid_links) > settings.max_links_per_job:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Too many links: {len(valid_links)} submitted, "
                f"maximum is {settings.max_links_per_job} per job."
            ),
        )

    job = create_job(valid_links, body.quality)

    # Grab the running event loop and start the job without blocking it
    loop = asyncio.get_event_loop()
    start_job(job.id, loop)

    logger.info(
        "Job %s created: %d valid, %d invalid, quality=%s",
        job.id, len(valid_links), len(invalid_lines), body.quality,
    )

    return CreateJobResponse(
        job_id=job.id,
        quality=job.quality,
        total_valid=len(valid_links),
        total_invalid=len(invalid_lines),
        invalid_lines=[InvalidLineOut(**il.to_dict()) for il in invalid_lines],
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}  – fetch current state (for polling)
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}")
async def get_job_endpoint(job_id: str):
    """Return the full current state of a job (all items + statuses)."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")
    return job.to_dict()


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/events  – SSE live progress stream
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/events")
async def job_events_endpoint(job_id: str, request: Request):
    """
    Server-Sent Events stream for live job progress.

    Event types emitted
    -------------------
    connected       – sent immediately on connect with current snapshot
    item_started    – a video started downloading
    item_progress   – chunk progress (percent, speed, eta)
    item_finished   – an item completed (done or error)
    item_cancelled  – an item was cancelled
    job_finished    – the whole job completed (done/partial/failed/cancelled)
    keepalive       – empty comment every 15 s to prevent proxy timeouts
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    queue = subscribe(job_id)

    async def event_stream() -> AsyncIterator[str]:
        # Send the current snapshot immediately so the client is in sync
        snapshot = json.dumps({"event": "connected", "job": job.to_dict()})
        yield f"data: {snapshot}\n\n"

        # If job already finished before the client connected, close stream
        if job.status in ("done", "partial", "failed", "cancelled"):
            unsubscribe(job_id, queue)
            return

        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                try:
                    # Wait up to 15 s for the next event, then send keepalive
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"

                    # Stop streaming once the job is finished
                    try:
                        event_data = json.loads(payload)
                        if event_data.get("event") == "job_finished":
                            break
                    except (json.JSONDecodeError, AttributeError):
                        pass

                except asyncio.TimeoutError:
                    # Send SSE comment as keepalive (not parsed by the client)
                    yield ": keepalive\n\n"

        finally:
            unsubscribe(job_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/cancel  – cancel a running job
# ---------------------------------------------------------------------------

@router.post("/jobs/{job_id}/cancel")
async def cancel_job_endpoint(job_id: str):
    """
    Signal a running job to cancel.

    Items that are already downloading are allowed to finish their current
    yt-dlp call; queued items that haven't started yet are skipped.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    if job.status in ("done", "partial", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Job is already in terminal state: {job.status!r}.",
        )

    success = cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=409, detail="Job could not be cancelled.")

    logger.info("Job %s cancel accepted", job_id)
    return {"job_id": job_id, "status": "cancelling"}


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/items/{item_index}/retry – retry downloading single item
# ---------------------------------------------------------------------------

@router.post("/jobs/{job_id}/items/{item_index}/retry")
async def retry_item_endpoint(job_id: str, item_index: int):
    """Retry a failed or cancelled item inside a job."""
    loop = asyncio.get_event_loop()
    success = retry_item(job_id, item_index, loop)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry item index {item_index} in job {job_id!r}.",
        )
    return {"job_id": job_id, "item_index": item_index, "status": "queued"}


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/files/{item_index}  – download a single MP3
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/files/{item_index}")
async def download_file_endpoint(job_id: str, item_index: int):
    """
    Stream a single MP3 file to the client.

    *item_index* is the 0-based index into job.items[].  Only items with
    status "done" and a valid file_path are downloadable.

    Path-traversal protection: the resolved file path must live inside the
    configured download_dir before the FileResponse is created.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    if item_index < 0 or item_index >= len(job.items):
        raise HTTPException(
            status_code=404,
            detail=f"Item index {item_index} is out of range (job has {len(job.items)} items).",
        )

    item = job.items[item_index]

    if item.status != "done" or not item.file_path:
        raise HTTPException(
            status_code=404,
            detail="This item has not finished downloading or failed.",
        )

    # ── Path-traversal guard ────────────────────────────────────────────────
    download_root = Path(settings.download_dir).resolve()
    safe = _safe_path(download_root, item.file_path)

    if not safe.is_file():
        raise HTTPException(
            status_code=404,
            detail="The MP3 file no longer exists on disk (it may have been cleaned up).",
        )

    filename = safe.name  # e.g. "Never Gonna Give You Up [dQw4w9WgXcY].mp3"

    return FileResponse(
        path=str(safe),
        media_type="audio/mpeg",
        filename=filename,
        headers={
            # Inline preview in browser; swap to "attachment" if preferred
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/zip  – stream a ZIP of all successful MP3s
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/zip")
async def download_zip_endpoint(job_id: str):
    """
    Build and stream a ZIP archive of all successfully downloaded MP3 files
    in this job.

    The archive is built entirely in memory using zipfile + BytesIO so no
    temporary file is written to disk.  For very large batches this means
    the archive lives in RAM; the trade-off is simplicity and no temp-file
    management.

    The filename is ``BeatBatch_YYYY-MM-DD.zip``.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found.")

    done_items = [item for item in job.items if item.status == "done" and item.file_path]

    if not done_items:
        raise HTTPException(
            status_code=404,
            detail="No successfully downloaded files are available for this job.",
        )

    download_root = Path(settings.download_dir).resolve()

    def _build_zip() -> bytes:
        """Build the ZIP in a worker thread (blocking I/O)."""
        buf = io.BytesIO()
        seen_names: dict[str, int] = {}  # deduplicate filenames inside the archive

        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for item in done_items:
                # Path-traversal check for every file
                try:
                    safe = _safe_path(download_root, item.file_path)
                except HTTPException:
                    continue  # skip files that fail the guard

                if not safe.is_file():
                    continue  # file was cleaned up between job completion and now

                # Deduplicate archive names (same title from different videos)
                arc_name = safe.name
                count = seen_names.get(arc_name, 0)
                if count:
                    stem = safe.stem
                    arc_name = f"{stem} ({count}){safe.suffix}"
                seen_names[safe.name] = count + 1

                zf.write(safe, arcname=arc_name)

        buf.seek(0)
        return buf.read()

    # Build the ZIP in a thread so the event loop is never blocked
    zip_bytes = await asyncio.to_thread(_build_zip)

    if not zip_bytes:
        raise HTTPException(
            status_code=404,
            detail="All files have been cleaned up from disk.",
        )

    zip_name = f"BeatBatch_{date.today().isoformat()}.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )
