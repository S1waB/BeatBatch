"""
BeatBatch – FastAPI application entry point.

Responsibilities:
  • Mount CORS middleware (allows the Vite dev server origin).
  • Run a startup check that verifies FFmpeg is installed.
  • Ensure the downloads directory exists.
  • Include all API routers.
"""

import logging
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, validate, jobs

from app.logging_config import setup_structured_logging

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
setup_structured_logging(logging.INFO)
logger = logging.getLogger("beatbatch")


# ---------------------------------------------------------------------------
# Lifespan – runs once on startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks for the application."""

    # 1. Verify FFmpeg is available on PATH
    if shutil.which("ffmpeg") is None:
        logger.error(
            "\n"
            "╔══════════════════════════════════════════════════════════╗\n"
            "║  FFmpeg is NOT installed or not found on PATH!          ║\n"
            "║                                                        ║\n"
            "║  BeatBatch needs FFmpeg to convert audio to MP3.       ║\n"
            "║                                                        ║\n"
            "║  Install instructions:                                 ║\n"
            "║    Windows : winget install FFmpeg                      ║\n"
            "║    macOS   : brew install ffmpeg                        ║\n"
            "║    Ubuntu  : sudo apt install ffmpeg                    ║\n"
            "║                                                        ║\n"
            "║  After installing, restart this server.                 ║\n"
            "╚══════════════════════════════════════════════════════════╝"
        )
        sys.exit(1)
    else:
        logger.info("FFmpeg found: %s", shutil.which("ffmpeg"))

    # 2. Create the downloads directory if it doesn't exist
    downloads_path = Path(settings.download_dir)
    downloads_path.mkdir(parents=True, exist_ok=True)
    logger.info("Downloads directory: %s", downloads_path.resolve())

    # 3. Start background cleanup scheduler
    from app.services.cleanup import start_cleanup_scheduler
    cleanup_task = start_cleanup_scheduler()

    logger.info("🚀 BeatBatch backend is ready")

    yield  # ← application runs here

    cleanup_task.cancel()
    logger.info("BeatBatch backend shutting down")


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="BeatBatch",
    description="Batch-download YouTube videos as MP3 files.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS – allow the Vite dev server (and any extra origins from .env)
# ---------------------------------------------------------------------------
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Structured request logging middleware
# ---------------------------------------------------------------------------
import time
from fastapi import Request

@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )
    logger.info(
        "%s %s -> %d (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={
            "http_method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        },
    )
    return response

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router)
app.include_router(validate.router)
app.include_router(jobs.router)
