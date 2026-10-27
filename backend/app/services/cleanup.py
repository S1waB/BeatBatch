"""
services/cleanup.py
-------------------
Background task that periodically deletes job download folders older than
``FILE_RETENTION_HOURS`` hours.

Design
------
- Runs immediately on server startup, then every ``CLEANUP_INTERVAL_HOURS``
  hours (both configurable via .env).
- Only deletes subdirectories directly inside the configured download_dir;
  it never touches the root directory itself.
- Uses asyncio.create_task (non-blocking) so it never delays startup.
- Gracefully handles permission errors and missing directories.
- Logs what it deletes and why it skips.

Public API
----------
    start_cleanup_scheduler(app: FastAPI) -> None   # call from lifespan
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path

from app.config import settings

logger = logging.getLogger("beatbatch.cleanup")

# How often to run cleanup (seconds between sweeps)
_CLEANUP_INTERVAL_SECS: int = int(
    getattr(settings, "cleanup_interval_hours", 1) * 3600
)


def _sweep_once() -> tuple[int, int]:
    """
    Delete job-download subfolders that are older than the configured
    retention period.

    Returns
    -------
    (deleted_count, skipped_count)
    """
    root = Path(settings.download_dir).resolve()

    if not root.is_dir():
        logger.debug("Cleanup: download_dir %s does not exist – skipping", root)
        return 0, 0

    cutoff_secs = settings.file_retention_hours * 3600
    now = time.time()
    deleted = skipped = 0

    for entry in root.iterdir():
        if not entry.is_dir():
            continue  # only touch subdirectories (= job folders)

        try:
            age = now - entry.stat().st_mtime
        except OSError:
            skipped += 1
            continue

        if age >= cutoff_secs:
            try:
                shutil.rmtree(entry)
                logger.info(
                    "Cleanup: deleted %s (age %.1f h)", entry.name, age / 3600
                )
                deleted += 1
            except OSError as exc:
                logger.warning("Cleanup: could not delete %s: %s", entry, exc)
                skipped += 1
        else:
            skipped += 1

    return deleted, skipped


async def _cleanup_loop() -> None:
    """Asyncio task: sweep immediately, then every _CLEANUP_INTERVAL_SECS."""
    logger.info(
        "Cleanup scheduler started (retention=%dh, interval=%dh)",
        settings.file_retention_hours,
        _CLEANUP_INTERVAL_SECS // 3600,
    )

    while True:
        try:
            deleted, skipped = await asyncio.to_thread(_sweep_once)
            logger.info(
                "Cleanup sweep: deleted=%d skipped=%d", deleted, skipped
            )
        except Exception as exc:
            logger.exception("Cleanup sweep raised an unexpected error: %s", exc)

        await asyncio.sleep(_CLEANUP_INTERVAL_SECS)


def start_cleanup_scheduler() -> asyncio.Task:
    """
    Schedule the cleanup loop as a background asyncio Task.

    Call this inside the FastAPI lifespan context (after the event loop is
    running) and store the returned Task so it can be cancelled on shutdown.
    """
    return asyncio.create_task(_cleanup_loop(), name="cleanup-scheduler")
