"""
Link parser and validator for YouTube URLs and Playlists.

Accepts raw text (one link per line), extracts valid YouTube video IDs
and playlist items, normalises URLs, removes duplicates (preserving order),
and reports invalid lines with reasons.

Supported URL patterns:
  • https://www.youtube.com/watch?v=VIDEO_ID
  • https://youtu.be/VIDEO_ID
  • https://youtube.com/shorts/VIDEO_ID
  • https://music.youtube.com/watch?v=VIDEO_ID
  • https://www.youtube.com/playlist?list=PLAYLIST_ID
  • https://music.youtube.com/playlist?list=PLAYLIST_ID
  • URLs with playlist parameters (e.g. watch?v=ID&list=...)
"""

from __future__ import annotations

import functools
import logging
import re
from urllib.parse import parse_qs, urlparse

import yt_dlp

logger = logging.getLogger("beatbatch.link_parser")

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")

# Hosts we accept as YouTube domains
_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------
class ValidLink:
    """A validated YouTube link with its extracted video ID and optional title."""

    __slots__ = ("video_id", "canonical_url", "original_url", "title")

    def __init__(
        self,
        video_id: str,
        original_url: str,
        title: str | None = None,
    ) -> None:
        self.video_id = video_id
        self.canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        self.original_url = original_url
        self.title = title

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "canonical_url": self.canonical_url,
            "original_url": self.original_url,
            "title": self.title,
        }


class InvalidLine:
    """A line that could not be parsed, together with a human-readable reason."""

    __slots__ = ("line_number", "text", "reason")

    def __init__(self, line_number: int, text: str, reason: str) -> None:
        self.line_number = line_number
        self.text = text
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "line_number": self.line_number,
            "text": self.text,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Playlist extraction helper (cached)
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=128)
def extract_playlist_items(
    playlist_url: str,
    max_items: int = 100,
) -> tuple[tuple[str, str, str | None], ...]:
    """
    Extract video entries from a YouTube playlist URL using yt-dlp flat extraction.
    Returns a tuple of (video_id, canonical_url, title) entries.
    """
    ydl_opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "skip_download": True,
        "playlist_items": f"1-{max_items}",
        "retries": 1,
        "socket_timeout": 15,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        if not info:
            return ()
        entries = info.get("entries") or []
        results: list[tuple[str, str, str | None]] = []
        for e in entries:
            if not e:
                continue
            vid = e.get("id")
            title = e.get("title")
            if (
                vid
                and VIDEO_ID_RE.match(vid)
                and title not in ("[Private video]", "[Deleted video]")
            ):
                results.append((vid, f"https://www.youtube.com/watch?v={vid}", title))
        return tuple(results)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _extract_playlist_id(url: str) -> str | None:
    """
    Extract a YouTube playlist ID from *url*.
    Returns the playlist ID if the URL matches a dedicated playlist pattern, else None.
    """
    try:
        norm_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
        parsed = urlparse(norm_url)
    except Exception:
        return None

    host = (parsed.hostname or "").lower()
    if host not in _YOUTUBE_HOSTS:
        return None

    path = parsed.path.rstrip("/")
    qs = parse_qs(parsed.query)
    lists = qs.get("list", [])
    if not lists:
        return None

    candidate = lists[0]
    if not PLAYLIST_ID_RE.match(candidate):
        return None

    # Matches /playlist?list=...
    if path == "/playlist":
        return candidate

    return None


def _extract_video_id(url: str) -> str | None:
    """
    Try to extract an 11-char YouTube video ID from *url*.

    Returns the ID string on success, or ``None`` if the URL
    does not match any known YouTube pattern.
    """
    try:
        norm_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
        parsed = urlparse(norm_url)
    except Exception:
        return None

    host = (parsed.hostname or "").lower()

    # Reject non-YouTube hosts
    if host not in _YOUTUBE_HOSTS:
        return None

    path = parsed.path.rstrip("/")

    # Pattern 1: youtu.be/<VIDEO_ID>
    if host in ("youtu.be", "www.youtu.be"):
        candidate = path.lstrip("/")
        # The path should be just the video ID (no further segments)
        if "/" in candidate:
            return None
        return candidate if VIDEO_ID_RE.match(candidate) else None

    # Pattern 2: /shorts/<VIDEO_ID>
    if path.startswith("/shorts/"):
        candidate = path.split("/shorts/", 1)[1].split("/")[0]
        return candidate if VIDEO_ID_RE.match(candidate) else None

    # Pattern 3: /watch  → video ID is in the "v" query parameter (even if list is present)
    if path == "/watch":
        qs = parse_qs(parsed.query)
        candidates = qs.get("v", [])
        if not candidates:
            return None
        candidate = candidates[0]
        return candidate if VIDEO_ID_RE.match(candidate) else None

    return None


def _looks_like_url(text: str) -> bool:
    """Return True if *text* looks like it was intended to be a URL."""
    return (
        text.startswith("http://")
        or text.startswith("https://")
        or text.startswith("www.")
        or text.startswith("youtube.com")
        or text.startswith("youtu.be")
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_links(
    raw_text: str,
    expand_playlists: bool = True,
    max_playlist_items: int = 100,
) -> tuple[list[ValidLink], list[InvalidLine]]:
    """
    Parse raw text containing YouTube URLs or playlist URLs (one per line).

    Rules:
      1. Split by newlines, trim whitespace.
      2. Skip blank lines and comment lines (starting with ``#``).
      3. For dedicated playlist URLs (e.g. /playlist?list=...), extract and expand
         all individual video tracks into the batch.
      4. For video URLs (watch, shorts, youtu.be), extract video ID (even if
         embedded in a playlist context).
      5. Remove duplicate video IDs (keep first occurrence).

    Returns:
        ``(valid_links, invalid_lines)``
    """
    valid: list[ValidLink] = []
    invalid: list[InvalidLine] = []
    seen_ids: set[str] = set()

    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        line = raw_line.strip()

        # Skip blank lines and comments
        if not line or line.startswith("#"):
            continue

        # --- 1. Check for dedicated playlist URL ---
        playlist_id = _extract_playlist_id(line)
        if playlist_id:
            if not expand_playlists:
                canon = f"https://www.youtube.com/playlist?list={playlist_id}"
                valid.append(ValidLink(video_id=playlist_id, original_url=canon))
                continue

            try:
                items = extract_playlist_items(line, max_items=max_playlist_items)
                if not items:
                    invalid.append(
                        InvalidLine(
                            line_number,
                            line,
                            "Playlist is empty or contains no available videos.",
                        )
                    )
                else:
                    for vid, canon_url, title in items:
                        if vid not in seen_ids:
                            seen_ids.add(vid)
                            valid.append(
                                ValidLink(video_id=vid, original_url=canon_url, title=title)
                            )
            except Exception as exc:
                logger.warning("Failed to extract playlist from %s: %s", line, exc)
                invalid.append(
                    InvalidLine(
                        line_number,
                        line,
                        "Playlist could not be loaded (it may be private, unavailable, or rate-limited).",
                    )
                )
            continue

        # --- 2. Attempt video extraction ---
        video_id = _extract_video_id(line)

        if video_id is None:
            # Determine a helpful reason
            if _looks_like_url(line):
                reason = "Not a recognised YouTube video URL."
            else:
                reason = "Not a valid URL."
            invalid.append(InvalidLine(line_number, line, reason))
            continue

        # Duplicate check (by video ID)
        if video_id in seen_ids:
            continue  # silently skip duplicates
        seen_ids.add(video_id)

        valid.append(ValidLink(video_id=video_id, original_url=line))

    return valid, invalid
