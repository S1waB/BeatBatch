"""
Job manager for BeatBatch.

Responsibilities
----------------
- Define the Job and JobItem data models (in-memory, dict-backed store).
- Run downloads concurrently via a ThreadPoolExecutor (yt-dlp is blocking).
- Forward per-chunk progress to SSE subscribers via asyncio.Queue.
- Support job cancellation.

Public interface
----------------
    job = create_job(links, quality)          -> Job
    job = get_job(job_id)                     -> Job | None
    start_job(job_id, loop)                   -> None   (fire-and-forget)
    cancel_job(job_id)                        -> bool
    subscribe(job_id)                         -> asyncio.Queue
    unsubscribe(job_id, queue)                -> None

Design notes
------------
- The store is a plain dict[str, Job] protected by a threading.Lock.
  Swap it for a database-backed store later without changing the interface.
- Concurrency is controlled by MAX_CONCURRENT_DOWNLOADS (default 3).
- Each download runs in a thread; progress updates are posted to an
  asyncio.Queue per subscriber using loop.call_soon_threadsafe.
- SSE events are JSON strings matching the schema expected by the frontend.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from app.config import settings
from app.services.downloader import download_one
from app.services.link_parser import ValidLink

logger = logging.getLogger("beatbatch.job_manager")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_CONCURRENT_DOWNLOADS: int = 3   # max parallel yt-dlp threads per server

# Single shared executor – reused across all jobs so the pool size is bounded.
_executor = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_DOWNLOADS,
    thread_name_prefix="beatbatch-dl",
)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

JobStatus   = Literal["queued", "running", "done", "partial", "failed", "cancelled"]
ItemStatus  = Literal["queued", "downloading", "done", "error", "cancelled"]


@dataclass
class JobItem:
    """State of a single download inside a Job."""

    url:        str
    video_id:   str
    title:      str | None = None
    status:     ItemStatus = "queued"
    percent:    float = 0.0      # 0-100
    speed:      float | None = None   # bytes/sec
    eta:        int   | None = None   # seconds remaining
    error:      str   | None = None
    file_path:  str   | None = None
    duration:   int   | None = None   # seconds
    filesize:   int   | None = None   # bytes

    def to_dict(self) -> dict:
        return {
            "url":       self.url,
            "video_id":  self.video_id,
            "title":     self.title,
            "status":    self.status,
            "percent":   round(self.percent, 1),
            "speed":     self.speed,
            "eta":       self.eta,
            "error":     self.error,
            "file_path": self.file_path,
            "duration":  self.duration,
            "filesize":  self.filesize,
        }


@dataclass
class Job:
    """A batch download job containing one or more items."""

    id:         str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    quality:    str = "192"
    status:     JobStatus = "queued"
    items:      list[JobItem] = field(default_factory=list)

    # Internal – not serialised
    _cancel_flag: threading.Event = field(
        default_factory=threading.Event, repr=False, compare=False
    )
    _lock: threading.Lock = field(
        default_factory=threading.Lock, repr=False, compare=False
    )

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "created_at": self.created_at,
            "quality":    self.quality,
            "status":     self.status,
            "items":      [item.to_dict() for item in self.items],
        }

    # Convenience counters (thread-safe reads are fine – Python GIL)
    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.status == "done")

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.items if i.status == "error")

    @property
    def cancelled_count(self) -> int:
        return sum(1 for i in self.items if i.status == "cancelled")


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

class _JobStore:
    """Thread-safe dict-backed job store. Replace with a DB store later."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


_store = _JobStore()

# ---------------------------------------------------------------------------
# SSE subscriber registry
# ---------------------------------------------------------------------------
# Maps job_id -> list of asyncio.Queue objects (one per connected SSE client).

_subscribers: dict[str, list[asyncio.Queue]] = {}
_sub_lock = threading.Lock()


def subscribe(job_id: str) -> asyncio.Queue:
    """Register a new SSE subscriber for *job_id* and return its queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=512)
    with _sub_lock:
        _subscribers.setdefault(job_id, []).append(q)
    return q


def unsubscribe(job_id: str, queue: asyncio.Queue) -> None:
    """Remove *queue* from the subscriber list for *job_id*."""
    with _sub_lock:
        subs = _subscribers.get(job_id, [])
        try:
            subs.remove(queue)
        except ValueError:
            pass


def _publish(job_id: str, event: dict, loop: asyncio.AbstractEventLoop) -> None:
    """Post *event* to all SSE queues for *job_id* from any thread."""
    payload = json.dumps(event)
    with _sub_lock:
        queues = list(_subscribers.get(job_id, []))
    for q in queues:
        try:
            loop.call_soon_threadsafe(q.put_nowait, payload)
        except Exception:
            pass   # queue full or closed – drop the frame


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def create_job(links: list[ValidLink], quality: str) -> Job:
    """
    Create a new Job from a list of validated links and store it.

    Parameters
    ----------
    links:   Output of parse_links() – already-validated YouTube URLs.
    quality: MP3 bitrate string – "128" | "192" | "256" | "320".

    Returns
    -------
    The newly created Job (status="queued").
    """
    job = Job(quality=quality)
    job.items = [
        JobItem(url=link.canonical_url, video_id=link.video_id)
        for link in links
    ]
    _store.add(job)
    logger.info("Created job %s with %d items at quality %s kbps", job.id, len(job.items), quality)
    return job


def get_job(job_id: str) -> Job | None:
    """Return the Job for *job_id*, or None if it doesn't exist."""
    return _store.get(job_id)


def cancel_job(job_id: str) -> bool:
    """
    Signal the job to cancel.  Items that have already started will be
    allowed to finish their current yt-dlp call; future queued items are
    skipped.

    Returns True if the job was found and cancellable, False otherwise.
    """
    job = _store.get(job_id)
    if job is None:
        return False
    if job.status in ("done", "partial", "failed", "cancelled"):
        return False
    job._cancel_flag.set()
    logger.info("Cancel requested for job %s", job_id)
    return True


def retry_item(job_id: str, item_index: int, loop: asyncio.AbstractEventLoop) -> bool:
    """Retry downloading a specific item inside a job."""
    job = _store.get(job_id)
    if job is None or item_index < 0 or item_index >= len(job.items):
        return False
    item = job.items[item_index]

    with job._lock:
        item.status = "queued"
        item.percent = 0.0
        item.error = None
        item.speed = None
        item.eta = None
        job._cancel_flag.clear()
        if job.status in ("done", "partial", "failed", "cancelled"):
            job.status = "running"

    _publish(
        job.id,
        {
            "event": "item_progress",
            "job_id": job.id,
            "video_id": item.video_id,
            "percent": 0.0,
            "speed": None,
            "eta": None,
        },
        loop,
    )

    def _worker():
        _download_item(job, item, loop)
        with job._lock:
            done = job.done_count
            errors = job.error_count
            total = job.total
            running = sum(1 for i in job.items if i.status in ("queued", "downloading"))
            if running == 0:
                if errors == 0:
                    job.status = "done"
                elif done == 0:
                    job.status = "failed"
                else:
                    job.status = "partial"
                _publish(
                    job.id,
                    {"event": "job_finished", "job_id": job.id, "status": job.status},
                    loop,
                )

    _executor.submit(_worker)
    return True


def start_job(job_id: str, loop: asyncio.AbstractEventLoop) -> None:
    """
    Launch the job in background threads (non-blocking from the caller).

    Must be called from the asyncio event loop thread.
    Uses the shared ThreadPoolExecutor to bound server-wide concurrency.
    """
    job = _store.get(job_id)
    if job is None:
        logger.error("start_job: job %s not found", job_id)
        return

    # Kick off in a separate thread so we never block the event loop
    threading.Thread(
        target=_run_job,
        args=(job, loop),
        daemon=True,
        name=f"job-{job_id[:8]}",
    ).start()


# ---------------------------------------------------------------------------
# Internal job execution
# ---------------------------------------------------------------------------

def _run_job(job: Job, loop: asyncio.AbstractEventLoop) -> None:
    """
    Orchestrate the parallel download of all items in *job*.

    Runs in a dedicated daemon thread; spawns one thread per item
    (bounded by the shared executor's max_workers).
    """
    job.status = "running"
    _publish(job.id, {"event": "job_started", "job_id": job.id}, loop)
    logger.info("Job %s started (%d items)", job.id, job.total)

    futures: list[Future] = []

    for item in job.items:
        if job._cancel_flag.is_set():
            item.status = "cancelled"
            continue

        future = _executor.submit(_download_item, job, item, loop)
        futures.append(future)

    # Wait for all submitted futures (they may still be queued in the pool)
    for future in futures:
        try:
            future.result()        # propagates exceptions (shouldn't happen)
        except Exception as exc:
            logger.exception("Unhandled exception in download thread: %s", exc)

    # Mark any items that were cancelled before they started
    for item in job.items:
        if item.status == "queued":
            item.status = "cancelled"

    # Determine final job status
    done     = job.done_count
    errors   = job.error_count
    total    = job.total

    if job._cancel_flag.is_set() and done < total:
        job.status = "cancelled"
    elif errors == 0:
        job.status = "done"
    elif done == 0:
        job.status = "failed"
    else:
        job.status = "partial"

    _publish(
        job.id,
        {"event": "job_finished", "job_id": job.id, "status": job.status},
        loop,
    )
    logger.info(
        "Job %s finished: status=%s done=%d errors=%d total=%d",
        job.id, job.status, done, errors, total,
    )


def _download_item(
    job: Job,
    item: JobItem,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """
    Download a single item; called inside a ThreadPoolExecutor worker thread.

    Updates item fields in place and publishes SSE events.
    """
    if job._cancel_flag.is_set():
        item.status = "cancelled"
        _publish(
            job.id,
            {"event": "item_cancelled", "job_id": job.id, "video_id": item.video_id},
            loop,
        )
        return

    item.status = "downloading"
    item.percent = 0.0

    _publish(
        job.id,
        {
            "event":    "item_started",
            "job_id":   job.id,
            "video_id": item.video_id,
            "url":      item.url,
        },
        loop,
    )

    def on_progress(d: dict) -> None:
        """yt-dlp progress hook – runs in the same download thread."""
        if job._cancel_flag.is_set():
            return

        status = d.get("status")

        if status == "downloading":
            downloaded = d.get("downloaded_bytes") or 0
            total_b    = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            pct = (downloaded / total_b * 100) if total_b else 0.0

            with job._lock:
                item.percent = pct
                item.speed   = d.get("speed")
                item.eta     = d.get("eta")

            _publish(
                job.id,
                {
                    "event":    "item_progress",
                    "job_id":   job.id,
                    "video_id": item.video_id,
                    "percent":  round(pct, 1),
                    "speed":    item.speed,
                    "eta":      item.eta,
                },
                loop,
            )

        elif status == "finished":
            with job._lock:
                item.percent = 99.0  # post-processors still running

    result = download_one(
        url=item.url,
        job_id=job.id,
        quality=job.quality,
        on_progress=on_progress,
    )

    with job._lock:
        item.title     = result.title
        item.duration  = result.duration
        item.filesize  = result.filesize
        item.file_path = result.file_path

        if result.status == "done":
            item.status  = "done"
            item.percent = 100.0
            item.error   = None
        else:
            item.status  = "error"
            item.percent = 0.0
            item.error   = result.error_message

    _publish(
        job.id,
        {
            "event":      "item_finished",
            "job_id":     job.id,
            "video_id":   item.video_id,
            "status":     item.status,
            "title":      item.title,
            "percent":    item.percent,
            "error":      item.error,
            "file_path":  item.file_path,
            "duration":   item.duration,
            "filesize":   item.filesize,
        },
        loop,
    )

    logger.info(
        "Item %s in job %s: %s%s",
        item.video_id, job.id, item.status,
        f" – {item.error}" if item.error else "",
    )
