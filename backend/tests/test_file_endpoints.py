"""
Tests for file delivery, ZIP streaming, rate limiting, and security guards.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from app.config import settings
from app.main import app
from app.services.downloader import DownloadResult
from app.services.job_manager import create_job
from app.services.link_parser import ValidLink
from app.services.rate_limiter import SlidingWindowRateLimiter
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def test_job(tmp_path):
    """Creates a job with one real on-disk MP3 and one missing file."""
    # Create fake MP3 in the downloads folder
    dl_dir = Path(settings.download_dir).resolve()
    dl_dir.mkdir(parents=True, exist_ok=True)
    fake_mp3 = dl_dir / "test_track.mp3"
    fake_mp3.write_bytes(b"ID3\x03\x00\x00\x00fake audio content")

    links = [
        ValidLink("dQw4w9WgXcY", "https://www.youtube.com/watch?v=dQw4w9WgXcY"),
        ValidLink("jfKfPfyJRdk", "https://www.youtube.com/watch?v=jfKfPfyJRdk"),
    ]
    job = create_job(links, quality="192")
    job.items[0].status = "done"
    job.items[0].title = "Never Gonna Give You Up"
    job.items[0].file_path = str(fake_mp3)

    job.items[1].status = "error"
    job.items[1].error = "Network timeout"
    job.status = "partial"

    return job, fake_mp3


def test_download_single_file_success(test_job):
    job, fake_mp3 = test_job
    response = client.get(f"/api/jobs/{job.id}/files/0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content == b"ID3\x03\x00\x00\x00fake audio content"


def test_download_single_file_not_ready(test_job):
    job, _ = test_job
    # Item 1 is in error state, not downloadable
    response = client.get(f"/api/jobs/{job.id}/files/1")
    assert response.status_code == 404
    assert "not finished" in response.json()["detail"].lower()


def test_download_single_file_out_of_bounds(test_job):
    job, _ = test_job
    response = client.get(f"/api/jobs/{job.id}/files/99")
    assert response.status_code == 404
    assert "out of range" in response.json()["detail"].lower()


def test_download_zip_archive_success(test_job):
    job, _ = test_job
    response = client.get(f"/api/jobs/{job.id}/zip")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "BeatBatch_" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.zip"')
    # ZIP files start with PK\x03\x04
    assert response.content.startswith(b"PK\x03\x04")


def test_download_zip_no_done_items():
    links = [ValidLink("dQw4w9WgXcY", "https://www.youtube.com/watch?v=dQw4w9WgXcY")]
    job = create_job(links, quality="192")
    # Job has no completed items
    response = client.get(f"/api/jobs/{job.id}/zip")
    assert response.status_code == 404


def test_path_traversal_prevention(test_job):
    job, _ = test_job
    # Attempt path traversal
    job.items[0].file_path = "../../Windows/System32/calc.exe"
    response = client.get(f"/api/jobs/{job.id}/files/0")
    assert response.status_code == 400
    assert "traversal" in response.json()["detail"].lower()


def test_rate_limiting_on_create_job():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=60.0)
    with patch("app.routers.jobs.job_rate_limiter", limiter), patch("app.routers.jobs.start_job"):
        # 1st request ok
        r1 = client.post("/api/jobs", json={"text": "https://youtu.be/dQw4w9WgXcY"})
        assert r1.status_code == 202

        # 2nd request ok
        r2 = client.post("/api/jobs", json={"text": "https://youtu.be/dQw4w9WgXcY"})
        assert r2.status_code == 202

        # 3rd request triggers 429
        r3 = client.post("/api/jobs", json={"text": "https://youtu.be/dQw4w9WgXcY"})
        assert r3.status_code == 429
        assert "rate limit exceeded" in r3.json()["detail"].lower()


def test_input_size_limit():
    huge_text = "https://www.youtube.com/watch?v=dQw4w9WgXcY\n" * 4000  # > 150KB
    response = client.post("/api/jobs", json={"text": huge_text})
    assert response.status_code == 422  # validation error from pydantic Field max_length
