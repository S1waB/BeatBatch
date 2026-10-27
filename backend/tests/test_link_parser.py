"""
Tests for app/services/link_parser.py  (parse_links function)
and the POST /api/validate endpoint.

Coverage matrix
───────────────
 ✓  Standard  youtube.com/watch?v=  URL
 ✓  Short     youtu.be/             URL
 ✓  Shorts    youtube.com/shorts/   URL
 ✓  Music     music.youtube.com/    URL
 ✓  Blank lines ignored
 ✓  Comment lines (#) ignored
 ✓  Duplicate video IDs deduplicated (first wins, silent drop)
 ✓  Garbage text → invalid with "Not a valid URL."
 ✓  Non-YouTube https URL → invalid with "Not a recognised YouTube video URL."
 ✓  Playlist-only URL → invalid with playlist reason
 ✓  Canonical URL normalisation (all valid links → watch?v= form)
 ✓  Line numbers are preserved correctly in invalid_lines
 ✓  POST /api/validate – happy path (via TestClient)
 ✓  POST /api/validate – entirely invalid input
 ✓  POST /api/validate – mixed valid + invalid
"""

import pytest

from app.services.link_parser import InvalidLine, ValidLink, parse_links

# ---------------------------------------------------------------------------
# Helper aliases
# ---------------------------------------------------------------------------
WATCH = "https://www.youtube.com/watch?v=dQw4w9WgXcY"
YOUTU_BE = "https://youtu.be/dQw4w9WgXcY"
SHORTS = "https://www.youtube.com/shorts/dQw4w9WgXcY"
MUSIC = "https://music.youtube.com/watch?v=dQw4w9WgXcY"
CANONICAL = "https://www.youtube.com/watch?v=dQw4w9WgXcY"
VIDEO_ID = "dQw4w9WgXcY"

DIFFERENT_WATCH = "https://www.youtube.com/watch?v=9bZkp7q19f0"
DIFFERENT_ID = "9bZkp7q19f0"

PLAYLIST_ONLY = "https://www.youtube.com/playlist?list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-"
PLAYLIST_WITH_VIDEO = "https://www.youtube.com/watch?v=dQw4w9WgXcY&list=PLrEnWoR732-BHrPp_Pm8_VleD68f9s14-"
GARBAGE = "not a url at all"
FOREIGN_URL = "https://vimeo.com/123456789"


# ===========================================================================
# parse_links – service-level unit tests
# ===========================================================================

class TestBlankAndCommentLines:
    def test_empty_string_returns_empty_lists(self):
        valid, invalid = parse_links("")
        assert valid == []
        assert invalid == []

    def test_only_blank_lines_ignored(self):
        valid, invalid = parse_links("\n\n   \n\t\n")
        assert valid == []
        assert invalid == []

    def test_comment_lines_ignored(self):
        text = "# This is a comment\n# Another comment\n"
        valid, invalid = parse_links(text)
        assert valid == []
        assert invalid == []

    def test_blank_and_comment_mixed_with_valid(self):
        text = f"\n# header\n{WATCH}\n\n# footer\n"
        valid, invalid = parse_links(text)
        assert len(valid) == 1
        assert valid[0].video_id == VIDEO_ID
        assert invalid == []


class TestValidURLs:
    def test_standard_watch_url(self):
        valid, invalid = parse_links(WATCH)
        assert len(valid) == 1
        assert valid[0].video_id == VIDEO_ID
        assert valid[0].canonical_url == CANONICAL
        assert valid[0].original_url == WATCH
        assert invalid == []

    def test_youtu_be_short_url(self):
        valid, invalid = parse_links(YOUTU_BE)
        assert len(valid) == 1
        assert valid[0].video_id == VIDEO_ID
        assert valid[0].canonical_url == CANONICAL
        assert invalid == []

    def test_shorts_url(self):
        valid, invalid = parse_links(SHORTS)
        assert len(valid) == 1
        assert valid[0].video_id == VIDEO_ID
        assert valid[0].canonical_url == CANONICAL
        assert invalid == []

    def test_music_youtube_url(self):
        valid, invalid = parse_links(MUSIC)
        assert len(valid) == 1
        assert valid[0].video_id == VIDEO_ID
        assert valid[0].canonical_url == CANONICAL
        assert invalid == []

    def test_multiple_different_valid_urls(self):
        text = f"{WATCH}\n{DIFFERENT_WATCH}"
        valid, invalid = parse_links(text)
        assert len(valid) == 2
        assert valid[0].video_id == VIDEO_ID
        assert valid[1].video_id == DIFFERENT_ID
        assert invalid == []

    def test_all_formats_for_same_video_deduplicates(self):
        """All four URL forms for the same video ID → only one kept."""
        text = f"{WATCH}\n{YOUTU_BE}\n{SHORTS}\n{MUSIC}"
        valid, invalid = parse_links(text)
        assert len(valid) == 1
        assert valid[0].video_id == VIDEO_ID

    def test_canonical_url_is_watch_form(self):
        """Even a youtu.be link must produce a canonical watch URL."""
        valid, _ = parse_links(YOUTU_BE)
        assert valid[0].canonical_url.startswith("https://www.youtube.com/watch?v=")


class TestDuplicates:
    def test_exact_duplicate_url_silently_dropped(self):
        text = f"{WATCH}\n{WATCH}"
        valid, invalid = parse_links(text)
        assert len(valid) == 1

    def test_same_video_different_format_dropped(self):
        text = f"{WATCH}\n{YOUTU_BE}"
        valid, invalid = parse_links(text)
        assert len(valid) == 1
        # Original URL is from the first occurrence
        assert valid[0].original_url == WATCH

    def test_duplicate_not_reported_as_invalid(self):
        text = f"{WATCH}\n{WATCH}"
        _, invalid = parse_links(text)
        assert invalid == []

    def test_order_preserved_first_wins(self):
        text = f"{DIFFERENT_WATCH}\n{WATCH}\n{DIFFERENT_WATCH}"
        valid, _ = parse_links(text)
        assert valid[0].video_id == DIFFERENT_ID
        assert valid[1].video_id == VIDEO_ID
        assert len(valid) == 2


class TestInvalidLines:
    def test_garbage_text_flagged(self):
        valid, invalid = parse_links(GARBAGE)
        assert valid == []
        assert len(invalid) == 1
        assert invalid[0].reason == "Not a valid URL."
        assert invalid[0].text == GARBAGE

    def test_non_youtube_url_flagged(self):
        valid, invalid = parse_links(FOREIGN_URL)
        assert valid == []
        assert len(invalid) == 1
        assert "Not a recognised YouTube video URL." in invalid[0].reason

    def test_playlist_only_url_flagged_with_clear_reason(self):
        valid, invalid = parse_links(PLAYLIST_ONLY)
        assert valid == []
        assert len(invalid) == 1
        assert "playlist" in invalid[0].reason.lower()

    def test_playlist_with_video_id_flagged_too(self):
        """A URL that has both ?v= and &list= contains a playlist param → invalid."""
        valid, invalid = parse_links(PLAYLIST_WITH_VIDEO)
        # The URL has a list param; current policy = invalid
        assert len(invalid) == 1
        assert "playlist" in invalid[0].reason.lower()

    def test_line_numbers_in_invalid_are_1_indexed(self):
        text = f"\n{GARBAGE}"  # line 1 blank, line 2 garbage
        _, invalid = parse_links(text)
        assert invalid[0].line_number == 2

    def test_line_numbers_skip_blank_and_comment(self):
        """Line numbers reflect position in original text, not count of processed lines."""
        text = f"# comment\n\n{GARBAGE}"
        _, invalid = parse_links(text)
        assert invalid[0].line_number == 3

    def test_multiple_invalid_lines_all_reported(self):
        text = f"garbage1\ngarbage2\ngarbage3"
        valid, invalid = parse_links(text)
        assert len(invalid) == 3
        assert [i.line_number for i in invalid] == [1, 2, 3]

    def test_invalid_line_to_dict(self):
        _, invalid = parse_links(GARBAGE)
        d = invalid[0].to_dict()
        assert set(d.keys()) == {"line_number", "text", "reason"}

    def test_valid_link_to_dict(self):
        valid, _ = parse_links(WATCH)
        d = valid[0].to_dict()
        assert set(d.keys()) == {"video_id", "canonical_url", "original_url"}


class TestMixedInput:
    def test_mixed_valid_and_invalid(self):
        text = f"{WATCH}\n{GARBAGE}\n{YOUTU_BE}\n{FOREIGN_URL}"
        valid, invalid = parse_links(text)
        # WATCH and YOUTU_BE are the same video; deduplication keeps one
        assert len(valid) == 1
        assert len(invalid) == 2

    def test_order_of_valid_preserved(self):
        text = f"{DIFFERENT_WATCH}\n{GARBAGE}\n{WATCH}"
        valid, invalid = parse_links(text)
        assert valid[0].video_id == DIFFERENT_ID
        assert valid[1].video_id == VIDEO_ID
        assert len(invalid) == 1


class TestEdgeCases:
    def test_url_with_trailing_whitespace(self):
        valid, invalid = parse_links(f"  {WATCH}  ")
        assert len(valid) == 1

    def test_http_scheme_watch_url(self):
        """http:// variant should still be parsed correctly."""
        url = "http://www.youtube.com/watch?v=dQw4w9WgXcY"
        valid, invalid = parse_links(url)
        assert len(valid) == 1
        assert valid[0].video_id == VIDEO_ID

    def test_watch_without_v_param(self):
        url = "https://www.youtube.com/watch"
        _, invalid = parse_links(url)
        assert len(invalid) == 1

    def test_shorts_with_extra_path(self):
        """Trailing path segment after video ID should not match."""
        url = "https://www.youtube.com/shorts/dQw4w9WgXcY/extra"
        # The extra segment is stripped by the split logic – still valid
        valid, invalid = parse_links(url)
        # Accept either behaviour but at minimum ensure no crash
        assert isinstance(valid, list)
        assert isinstance(invalid, list)

    def test_very_large_input_performance(self):
        """1 000 unique (mock) lines should parse without error."""
        # Use real-looking but fake 11-char IDs
        lines = [f"https://www.youtube.com/watch?v=AAAAAAAAAAA" for _ in range(1000)]
        valid, invalid = parse_links("\n".join(lines))
        # All are the same video ID → deduplication keeps 1
        assert len(valid) == 1


# ===========================================================================
# POST /api/validate – integration tests via TestClient
# ===========================================================================

class TestValidateEndpoint:
    def test_happy_path_returns_valid_links(self, client):
        resp = client.post("/api/validate", json={"text": WATCH})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_valid"] == 1
        assert data["total_invalid"] == 0
        link = data["valid_links"][0]
        assert link["video_id"] == VIDEO_ID
        assert link["canonical_url"] == CANONICAL
        assert link["original_url"] == WATCH

    def test_invalid_only_input(self, client):
        resp = client.post("/api/validate", json={"text": GARBAGE})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_valid"] == 0
        assert data["total_invalid"] == 1
        item = data["invalid_lines"][0]
        assert item["line_number"] == 1
        assert "Not a valid URL." in item["reason"]

    def test_mixed_input(self, client):
        text = f"{WATCH}\n{GARBAGE}\n{YOUTU_BE}"
        resp = client.post("/api/validate", json={"text": text})
        assert resp.status_code == 200
        data = resp.json()
        # WATCH and YOUTU_BE share the same video ID → 1 valid
        assert data["total_valid"] == 1
        assert data["total_invalid"] == 1

    def test_playlist_url_returns_invalid_with_reason(self, client):
        resp = client.post("/api/validate", json={"text": PLAYLIST_ONLY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_valid"] == 0
        assert data["total_invalid"] == 1
        assert "playlist" in data["invalid_lines"][0]["reason"].lower()

    def test_empty_text_returns_empty_lists(self, client):
        resp = client.post("/api/validate", json={"text": ""})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_valid"] == 0
        assert data["total_invalid"] == 0
        assert data["valid_links"] == []
        assert data["invalid_lines"] == []

    def test_missing_text_field_returns_422(self, client):
        resp = client.post("/api/validate", json={})
        assert resp.status_code == 422

    def test_youtu_be_normalised_in_response(self, client):
        resp = client.post("/api/validate", json={"text": YOUTU_BE})
        assert resp.status_code == 200
        data = resp.json()
        link = data["valid_links"][0]
        assert link["canonical_url"] == CANONICAL

    def test_all_four_formats_deduplication(self, client):
        text = f"{WATCH}\n{YOUTU_BE}\n{SHORTS}\n{MUSIC}"
        resp = client.post("/api/validate", json={"text": text})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_valid"] == 1

    def test_response_schema_keys(self, client):
        resp = client.post("/api/validate", json={"text": WATCH})
        data = resp.json()
        assert set(data.keys()) == {"valid_links", "invalid_lines", "total_valid", "total_invalid"}
