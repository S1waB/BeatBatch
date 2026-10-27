#!/usr/bin/env python
"""
scripts/test_download.py
------------------------
Quick smoke-test for the BeatBatch download engine.

Usage (from the backend/ directory, with the venv active):

    python scripts/test_download.py [URL] [--quality KBPS] [--cookies FILE]

Defaults
    URL     - a short public YouTube video
    quality - 192

Cookie setup (required for most YouTube downloads)
--------------------------------------------------
YouTube blocks unauthenticated downloads from server IPs.
Use ONE of these methods:

  Method A - cookies.txt file (RECOMMENDED, works while browser is open)
    1. Install "Get cookies.txt LOCALLY" from Chrome Web Store
    2. Visit youtube.com and make sure you are logged in
    3. Click the extension -> export "cookies.txt"
    4. Pass it to this script:
         python scripts/test_download.py --cookies cookies.txt
       OR set permanently in backend/.env:
         COOKIE_FILE=C:/path/to/cookies.txt

  Method B - close ALL Chrome/Edge processes first
    Chrome/Edge lock their SQLite cookie database while any process runs.
    Kill all chrome.exe and msedge.exe in Task Manager, then run normally.
    The auto-detect (COOKIES_FROM_BROWSER=auto) will then read them.

Examples
    python scripts/test_download.py
    python scripts/test_download.py https://youtu.be/9bZkp7q19f0 --quality 320
    python scripts/test_download.py --cookies cookies.txt
    python scripts/test_download.py "https://www.youtube.com/shorts/VIDEO_ID" --quality 128
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Make sure the backend package is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Temporarily override COOKIES_FROM_BROWSER if --cookies is passed
# (done before importing downloader so settings are already set)
_COOKIES_ARG = None
for i, arg in enumerate(sys.argv):
    if arg == "--cookies" and i + 1 < len(sys.argv):
        _COOKIES_ARG = sys.argv[i + 1]
        os.environ["COOKIE_FILE"] = _COOKIES_ARG
        os.environ["COOKIES_FROM_BROWSER"] = ""  # disable browser extraction
        break

from app.services.downloader import DEFAULT_QUALITY, VALID_QUALITIES, download_one

# -----------------------------------------------------------------------------
# CLI argument parsing
# -----------------------------------------------------------------------------

DEFAULT_TEST_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcY"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BeatBatch download engine smoke-test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_TEST_URL,
        help=f"YouTube URL to download (default: {DEFAULT_TEST_URL})",
    )
    parser.add_argument(
        "--quality",
        choices=sorted(VALID_QUALITIES),
        default=DEFAULT_QUALITY,
        metavar="KBPS",
        help=f"MP3 bitrate: {', '.join(sorted(VALID_QUALITIES))} (default: {DEFAULT_QUALITY})",
    )
    parser.add_argument(
        "--job-id",
        default="test_job",
        help="Job identifier / download subdirectory name (default: test_job)",
    )
    parser.add_argument(
        "--cookies",
        metavar="FILE",
        default=None,
        help="Path to Netscape-format cookies.txt exported from your browser",
    )
    return parser.parse_args()


# -----------------------------------------------------------------------------
# Progress display
# -----------------------------------------------------------------------------

_last_print_time: float = 0.0


def progress_hook(d: dict) -> None:
    """Print a throttled one-line progress update."""
    global _last_print_time

    status = d.get("status", "")

    if status == "downloading":
        now = time.monotonic()
        if now - _last_print_time < 0.5:
            return
        _last_print_time = now

        downloaded = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        speed = d.get("speed") or 0
        eta = d.get("eta")

        pct = f"{downloaded / total * 100:.1f}%" if total else "??%"
        dl_mb = downloaded / 1_048_576
        spd_kb = speed / 1024 if speed else 0
        eta_str = f"ETA {eta}s" if eta is not None else ""

        print(
            f"  v {pct}  {dl_mb:.2f} MB  {spd_kb:.0f} KB/s  {eta_str}",
            end="\r",
            flush=True,
        )

    elif status == "finished":
        print(" " * 70, end="\r")
        print("  >> Download finished, running post-processors ...", flush=True)

    elif status == "error":
        print("\n  !! yt-dlp reported a download error.", flush=True)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> int:
    args = parse_args()

    # Apply --cookies if given (env var already set above for settings)
    if args.cookies:
        if not os.path.isfile(args.cookies):
            print(f"ERROR: cookies file not found: {args.cookies}")
            return 1
        os.environ["COOKIE_FILE"] = str(Path(args.cookies).resolve())
        os.environ["COOKIES_FROM_BROWSER"] = ""

    sep = "-" * 60
    print(sep)
    print("BeatBatch - Download Engine Smoke-Test")
    print(sep)
    print(f"  URL     : {args.url}")
    print(f"  Quality : {args.quality} kbps")
    print(f"  Job ID  : {args.job_id}")
    if args.cookies:
        print(f"  Cookies : {args.cookies}")
    print(sep)

    start = time.perf_counter()

    result = download_one(
        url=args.url,
        job_id=args.job_id,
        quality=args.quality,
        on_progress=progress_hook,
    )

    elapsed = time.perf_counter() - start

    print(sep)
    if result.status == "done":
        size_mb = (result.filesize or 0) / 1_048_576
        duration_s = result.duration or 0
        print("  STATUS  : [OK]  done")
        print(f"  Title   : {result.title}")
        print(f"  Video ID: {result.video_id}")
        print(f"  Duration: {duration_s // 60}m {duration_s % 60}s")
        print(f"  File    : {result.file_path}")
        print(f"  Size    : {size_mb:.2f} MB")
        print(f"  Time    : {elapsed:.1f}s")
        print(sep)
        return 0
    else:
        print("  STATUS  : [FAIL]  error")
        print(f"  Reason  : {result.error_message}")
        print(f"  Time    : {elapsed:.1f}s")
        print(sep)
        print()
        print("  TIP: If you see 'unavailable' or 'sign in' errors,")
        print("       export cookies.txt from your browser and run:")
        print("       python scripts/test_download.py --cookies cookies.txt URL")
        print(sep)
        return 1


if __name__ == "__main__":
    sys.exit(main())
