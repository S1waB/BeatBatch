"""
Download engine for BeatBatch.

Uses yt-dlp as a library (not subprocess) to download a single YouTube
video as an MP3 file with embedded metadata and thumbnail.

Public API
──────────
    result = download_one(url, job_id, quality, on_progress)

Result fields
─────────────
    url           – original URL that was requested
    video_id      – YouTube video ID
    title         – video title (as reported by yt-dlp)
    status        – "done" | "error"
    file_path     – absolute path to the .mp3 file (or None on error)
    error_message – human-friendly message (or None on success)
    duration      – video duration in seconds (or None)
    filesize      – file size in bytes of the final MP3 (or None)
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import yt_dlp
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    GeoRestrictedError,
    PostProcessingError,
    UnavailableVideoError,
)

from app.config import settings

logger = logging.getLogger("beatbatch.downloader")

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Quality = Literal["128", "192", "256", "320"]
ProgressHook = Callable[[dict], None]

# Qualities we accept (validated at the API layer, but also checked here)
VALID_QUALITIES: frozenset[str] = frozenset({"128", "192", "256", "320"})
DEFAULT_QUALITY: Quality = "192"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DownloadResult:
    """Outcome of a single download attempt."""

    url: str
    video_id: str | None = None
    title: str | None = None
    status: Literal["done", "error"] = "error"
    file_path: str | None = None
    error_message: str | None = None
    duration: int | None = None       # seconds
    filesize: int | None = None       # bytes of the final MP3

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "video_id": self.video_id,
            "title": self.title,
            "status": self.status,
            "file_path": self.file_path,
            "error_message": self.error_message,
            "duration": self.duration,
            "filesize": self.filesize,
        }


# ---------------------------------------------------------------------------
# Error-message classifier
# ---------------------------------------------------------------------------

# Ordered list of (compiled-regex, friendly message) pairs.
# Checked against DownloadError.msg (lowercased).
_ERROR_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"private video"),
        "This video is private and cannot be downloaded.",
    ),
    (
        re.compile(r"sign in|please sign in|confirm your age|age.restrict|age-gated"),
        "This video requires sign-in or is age-restricted. Cookies are not supported yet.",
    ),
    (
        re.compile(r"not available in your country|geo.restrict|blocked it"),
        "This video is region-blocked and is not available in this location.",
    ),
    (
        re.compile(r"video has been removed|no longer available|been deleted|unavailable"),
        "This video has been removed or is no longer available.",
    ),
    (
        re.compile(r"copyright"),
        "This video has been blocked due to a copyright claim.",
    ),
    (
        re.compile(r"members.only|membership required|join this channel"),
        "This video is for channel members only.",
    ),
    (
        re.compile(r"live event|is live|premieres in"),
        "Live streams and premieres cannot be downloaded.",
    ),
    (
        re.compile(r"unable to extract|no video formats found|requested format"),
        "Could not extract a downloadable format from this video.",
    ),
    (
        re.compile(r"http error 429|too many requests"),
        "YouTube is rate-limiting requests. Please wait a few minutes and try again.",
    ),
    (
        re.compile(r"network|connection|timed? ?out|socket|ssl"),
        "A network error occurred. Check your connection and try again.",
    ),
    (
        re.compile(r"could not copy.*cookie|cookie database|unable to read cookie"),
        "Could not read browser cookies (the browser may be open and locking the database).",
    ),
]


def _friendly_error(exc: Exception) -> str:
    """Convert a yt-dlp exception to a human-readable error message."""
    raw = str(exc).lower()

    for pattern, message in _ERROR_PATTERNS:
        if pattern.search(raw):
            return message

    if isinstance(exc, GeoRestrictedError):
        return "This video is region-blocked and is not available in this location."
    if isinstance(exc, UnavailableVideoError):
        return "This video is unavailable."
    if isinstance(exc, PostProcessingError):
        return f"Post-processing failed (FFmpeg error): {exc}"

    # Fallback – include truncated raw message for debugging
    brief = str(exc)[:200]
    return f"Download failed: {brief}"


_COOKIE_ERROR_RE = re.compile(
    r"could not copy.*cookie|cookie database|unable to read cookie"
    r"|could not find.*cookies|failed to.*cookie",
    re.IGNORECASE,
)


def _is_cookie_error(msg: str) -> bool:
    """Return True if *msg* indicates a browser cookie access failure.

    These errors are transient (browser has DB locked) and are worth
    retrying with a different cookie source.
    """
    return bool(_COOKIE_ERROR_RE.search(msg))



# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

# Browsers tried in order when cookies_from_browser = "auto".
# We prefer browsers most commonly used for YouTube.
_AUTO_BROWSER_ORDER = ("chrome", "edge", "firefox", "brave", "chromium", "opera", "vivaldi")

# Executables that indicate a browser is available on this machine.
_BROWSER_EXECUTABLES: dict[str, list[str]] = {
    "chrome":   ["chrome", "google-chrome", "google-chrome-stable"],
    "edge":     ["msedge", "microsoft-edge"],
    "firefox":  ["firefox"],
    "brave":    ["brave", "brave-browser"],
    "chromium": ["chromium", "chromium-browser"],
    "opera":    ["opera"],
    "vivaldi":  ["vivaldi"],
    "safari":   ["safari"],
}

# Windows-specific install paths (fallback when not on PATH)
_BROWSER_WIN_PATHS: dict[str, list[str]] = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ],
}


def _is_browser_installed(browser: str) -> bool:
    """Return True if *browser* appears to be installed on this machine."""
    # 1. Check PATH
    for exe in _BROWSER_EXECUTABLES.get(browser, [browser]):
        if shutil.which(exe):
            return True
    # 2. Check known Windows install paths
    for path in _BROWSER_WIN_PATHS.get(browser, []):
        if os.path.isfile(path):
            return True
    return False


def _cookie_candidates() -> list[dict]:
    """
    Return an ordered list of cookie-source option dicts to try.

    Each entry is a partial yt-dlp params dict containing either
    ``cookiefile`` or ``cookiesfrombrowser``.  An empty list means
    no cookies are configured.

    ``download_one`` tries each candidate in order, falling back when
    yt-dlp raises (e.g. because the browser's SQLite DB is locked while
    the browser is open).
    """
    candidates: list[dict] = []

    # ── Option B: explicit cookie file (highest priority) ───────────────
    cookie_file = settings.cookie_file.strip()
    if cookie_file:
        if os.path.isfile(cookie_file):
            candidates.append({"cookiefile": cookie_file})
        else:
            logger.warning(
                "COOKIE_FILE '%s' does not exist – skipping file cookies.",
                cookie_file,
            )

    # ── Option A: browser cookie extraction ─────────────────────────────
    browser_setting = settings.cookies_from_browser.strip().lower()

    if not browser_setting:
        logger.info("Cookie extraction disabled (COOKIES_FROM_BROWSER is empty).")
        return candidates

    if browser_setting == "auto":
        for browser in _AUTO_BROWSER_ORDER:
            if _is_browser_installed(browser):
                candidates.append({"cookiesfrombrowser": (browser,)})
    elif _is_browser_installed(browser_setting):
        candidates.append({"cookiesfrombrowser": (browser_setting,)})
    else:
        logger.warning("Browser '%s' not found. Cookie extraction skipped.", browser_setting)

    return candidates


# ---------------------------------------------------------------------------
# yt-dlp options builder
# ---------------------------------------------------------------------------

def _build_ydl_opts(
    job_id: str,
    quality: str,
    on_progress: ProgressHook | None,
) -> dict:
    """
    Build the yt-dlp options dict for a single download job.

    Parameters
    ----------
    job_id:      Unique identifier for this job; used in the output path.
    quality:     MP3 bitrate – one of "128", "192", "256", "320".
    on_progress: Optional callback receiving a yt-dlp progress dict on
                 each chunk; forwarded directly as a progress hook.
    """
    if quality not in VALID_QUALITIES:
        logger.warning("Invalid quality %r, falling back to %s", quality, DEFAULT_QUALITY)
        quality = DEFAULT_QUALITY

    # Output directory:  downloads/<job_id>/
    out_dir = Path(settings.download_dir) / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Template:  downloads/<job_id>/<title (≤150 bytes)> [<video_id>].<ext>
    outtmpl = str(out_dir / "%(title).150B [%(id)s].%(ext)s")

    hooks = []
    if on_progress is not None:
        hooks.append(on_progress)

    return {
        # ── Format selection ────────────────────────────────────────────
        "format": "bestaudio/best",
        # ── Post-processors ─────────────────────────────────────────────
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": quality,
            },
            {
                # Write ID3 tags (artist, album, etc.) from video metadata
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
            {
                # Embed the video thumbnail as album art
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            },
        ],
        # ── Output ──────────────────────────────────────────────────────
        "outtmpl": outtmpl,
        "writethumbnail": True,          # needed for EmbedThumbnail
        # ── Playlist safety ─────────────────────────────────────────────
        "noplaylist": True,
        # ── Filename sanitation ─────────────────────────────────────────
        # restrictfilenames=False keeps Unicode; yt-dlp still strips
        # characters that are illegal on the current OS automatically.
        "restrictfilenames": False,
        "windowsfilenames": True,        # coerce illegal Win32 chars
        # ── Network / retry ─────────────────────────────────────────────
        "retries": 3,
        "fragment_retries": 3,
        "extractor_retries": 3,
        "socket_timeout": 30,
        # ── JavaScript runtime (required by yt-dlp 2026+) ───────────────
        # Node.js is used to decipher YouTube's signature functions.
        # Supported keys: "node", "deno", "bun", "quickjs".
        # An empty dict value means "use system default path".
        "js_runtimes": {"node": {}},
        # ── Verbosity ───────────────────────────────────────────────────
        "quiet": True,
        "no_warnings": False,            # still surface warnings to stderr
        # ── Progress ────────────────────────────────────────────────────
        "progress_hooks": hooks,
        # ── Misc ────────────────────────────────────────────────────────
        "noprogress": on_progress is None,  # suppress console bar when no hook
        # Note: cookies are injected per-attempt in download_one()
    }


# ---------------------------------------------------------------------------
# Public download function
# ---------------------------------------------------------------------------

def download_one(
    url: str,
    job_id: str,
    quality: str = DEFAULT_QUALITY,
    on_progress: ProgressHook | None = None,
) -> DownloadResult:
    """
    Download a single YouTube video as an MP3 file.

    Parameters
    ----------
    url:         YouTube video URL (already validated by link_parser).
    job_id:      Unique job identifier; files land in downloads/<job_id>/.
    quality:     MP3 bitrate string – "128" | "192" | "256" | "320".
    on_progress: Optional callable receiving yt-dlp progress dicts.
                 Signature: ``on_progress(d: dict) -> None``
                 Key fields in *d*:
                   ``status``          – "downloading" | "finished" | "error"
                   ``downloaded_bytes``– bytes fetched so far
                   ``total_bytes``     – total expected bytes (may be None)
                   ``speed``           – bytes/second (may be None)
                   ``eta``             – seconds remaining (may be None)

    Returns
    -------
    DownloadResult
        Always returns a result object; never raises. Check ``result.status``.
    """
    result = DownloadResult(url=url)
    base_opts = _build_ydl_opts(job_id, quality, on_progress)

    # Try each cookie source in order, with a final no-cookie fallback.
    # This handles the common case where Chrome is open and locks its DB:
    # we fall through to Edge, then Firefox, then unauthenticated.
    candidates = _cookie_candidates()
    attempts: list[dict | None] = [*candidates, None]  # None = no cookies
    last_exc: Exception | None = None

    for cookie_source in attempts:
        opts = {**base_opts}
        if cookie_source is not None:
            opts.update(cookie_source)
            label = (
                f"cookie file: {cookie_source['cookiefile']}"
                if "cookiefile" in cookie_source
                else f"browser: {cookie_source['cookiesfrombrowser'][0]}"
            )
        else:
            label = "no cookies"

        logger.debug("Attempting download via %s: %s", label, url)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

            if info is None:
                result.error_message = "yt-dlp returned no info for this URL."
                return result

            result.video_id = info.get("id")
            result.title    = info.get("title")
            result.duration = info.get("duration")

            mp3_path = _resolve_output_path(info, opts["outtmpl"])
            result.file_path = mp3_path

            if mp3_path and os.path.isfile(mp3_path):
                result.filesize = os.path.getsize(mp3_path)
                result.status = "done"
                logger.info(
                    "Downloaded '%s' via %s -> %s (%.1f MB)",
                    result.title, label, mp3_path,
                    result.filesize / 1_048_576,
                )
            else:
                result.error_message = (
                    "Post-processing completed but the MP3 file could not be located."
                )
                logger.error("MP3 not found after download: %s", mp3_path)

            return result  # success (or post-proc issue) – stop retrying

        except (DownloadError, ExtractorError) as exc:
            # If a cookie source caused the failure, try the next one
            if cookie_source is not None and _is_cookie_error(str(exc)):
                logger.warning(
                    "Cookie source '%s' failed, trying next. Reason: %s", label, exc
                )
                last_exc = exc
                continue
            # Any other error – no point retrying with different cookies
            result.error_message = _friendly_error(exc)
            logger.warning("%s for %s: %s", type(exc).__name__, url, exc)
            return result

        except PostProcessingError as exc:
            result.error_message = _friendly_error(exc)
            logger.warning("PostProcessingError for %s: %s", url, exc)
            return result

        except Exception as exc:  # noqa: BLE001
            result.error_message = f"Unexpected error: {exc!r}"
            logger.exception("Unexpected error downloading %s", url)
            return result

    # All sources exhausted
    if last_exc is not None:
        result.error_message = _friendly_error(last_exc)
        logger.error("All cookie sources failed for %s. Last: %s", url, last_exc)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_output_path(info: dict, outtmpl: str) -> str | None:
    """
    Determine the final MP3 path after yt-dlp post-processing.

    Strategy (in order):
    1. Check ``info["requested_downloads"][0]["filepath"]`` – this is the
       post-processed path set by FFmpegExtractAudio.
    2. Fall back to the template rendered by yt-dlp's prepare_filename,
       with the extension forced to ".mp3".
    """
    # Strategy 1: requested_downloads (most reliable post-PP path)
    try:
        requested = info.get("requested_downloads") or []
        if requested:
            fp = requested[0].get("filepath") or requested[0].get("_filename")
            if fp:
                # FFmpegExtractAudio changes the extension to .mp3
                base = os.path.splitext(fp)[0]
                candidate = base + ".mp3"
                if os.path.isfile(candidate):
                    return candidate
                # The path itself might already end in .mp3
                if os.path.isfile(fp):
                    return fp
    except Exception:
        pass

    # Strategy 2: reconstruct from the outtmpl directory + video ID glob
    try:
        out_dir = os.path.dirname(outtmpl)
        video_id = info.get("id", "")
        if video_id and out_dir:
            for fname in os.listdir(out_dir):
                if video_id in fname and fname.endswith(".mp3"):
                    return os.path.join(out_dir, fname)
    except Exception:
        pass

    return None
