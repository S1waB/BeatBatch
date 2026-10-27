"""
Link parser and validator for YouTube URLs.

Accepts raw text (one link per line), extracts valid YouTube video IDs,
normalises URLs, removes duplicates (preserving order), and reports
invalid lines with reasons.

Supported URL patterns:
  • https://www.youtube.com/watch?v=VIDEO_ID
  • https://youtu.be/VIDEO_ID
  • https://youtube.com/shorts/VIDEO_ID
  • https://music.youtube.com/watch?v=VIDEO_ID
"""

import re
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Regex for extracting a YouTube video ID (11 alphanumeric / - / _ chars)
# ---------------------------------------------------------------------------
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

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
    """A validated YouTube link with its extracted video ID."""

    __slots__ = ("video_id", "canonical_url", "original_url")

    def __init__(self, video_id: str, original_url: str) -> None:
        self.video_id = video_id
        self.canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        self.original_url = original_url

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "canonical_url": self.canonical_url,
            "original_url": self.original_url,
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
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_video_id(url: str) -> str | None:
    """
    Try to extract an 11-char YouTube video ID from *url*.

    Returns the ID string on success, or ``None`` if the URL
    does not match any known YouTube pattern.
    """
    try:
        parsed = urlparse(url)
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

    # Pattern 3: /watch  → video ID is in the "v" query parameter
    if path == "/watch":
        qs = parse_qs(parsed.query)
        candidates = qs.get("v", [])
        if not candidates:
            return None
        candidate = candidates[0]
        return candidate if VIDEO_ID_RE.match(candidate) else None

    return None


def _looks_like_playlist(url: str) -> bool:
    """Return True if the URL contains a ``list`` query parameter.

    This covers both playlist-only URLs (no ``v`` param) and combined
    URLs that embed a video ID *within* a playlist context
    (``?v=VIDEO_ID&list=PL...``).  Both are rejected so users are
    encouraged to paste clean, individual video links.
    """
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        return "list" in qs
    except Exception:
        return False


def _looks_like_url(text: str) -> bool:
    """Return True if *text* looks like it was intended to be a URL."""
    return text.startswith("http://") or text.startswith("https://")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_links(raw_text: str) -> tuple[list[ValidLink], list[InvalidLine]]:
    """
    Parse raw text containing one YouTube URL per line.

    Rules:
      1. Split by newlines, trim whitespace.
      2. Skip blank lines and comment lines (starting with ``#``).
      3. Validate each line as a YouTube URL.
      4. Remove duplicate video IDs (keep first occurrence).

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

        # --- Playlist guard (checked before extraction) ---
        # Reject any URL that carries a playlist context, even if it also
        # contains a valid video ID (e.g. ?v=XXX&list=PL...).
        if _looks_like_playlist(line):
            invalid.append(
                InvalidLine(
                    line_number,
                    line,
                    "Playlist URLs are not supported. Paste individual video links instead.",
                )
            )
            continue

        # --- Attempt extraction ---
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
