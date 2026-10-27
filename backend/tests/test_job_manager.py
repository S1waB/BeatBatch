"""
Unit and integration tests for Job Manager (mocking yt-dlp).
"""

import asyncio
import time
from unittest.mock import patch

import pytest
from app.services.downloader import DownloadResult
from app.services.job_manager import (
    cancel_job,
    create_job,
    get_job,
    retry_item,
    start_job,
    subscribe,
    unsubscribe,
)
from app.services.link_parser import ValidLink


@pytest.fixture
def sample_links():
    return [
        ValidLink("dQw4w9WgXcY", "https://www.youtube.com/watch?v=dQw4w9WgXcY"),
        ValidLink("jfKfPfyJRdk", "https://www.youtube.com/watch?v=jfKfPfyJRdk"),
    ]


def test_create_job(sample_links):
    job = create_job(sample_links, quality="320")
    assert job.id is not None
    assert job.quality == "320"
    assert job.status == "queued"
    assert len(job.items) == 2
    assert job.items[0].video_id == "dQw4w9WgXcY"
    assert job.items[1].video_id == "jfKfPfyJRdk"


def test_get_job(sample_links):
    created = create_job(sample_links, quality="192")
    fetched = get_job(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.to_dict()["quality"] == "192"


def test_get_job_not_found():
    assert get_job("non-existent-uuid-12345") is None


def test_cancel_job(sample_links):
    job = create_job(sample_links, quality="192")
    assert cancel_job(job.id) is True
    assert job._cancel_flag.is_set()


def test_cancel_non_existent_job():
    assert cancel_job("non-existent-id") is False


def test_sse_subscribe_and_unsubscribe():
    queue = subscribe("test-job-id")
    assert queue is not None
    unsubscribe("test-job-id", queue)


def test_job_execution_mocked_success(sample_links, tmp_path):
    async def _run():
        job = create_job(sample_links, quality="192")
        loop = asyncio.get_running_loop()

        dummy_file = tmp_path / "song.mp3"
        dummy_file.write_bytes(b"dummy mp3 content")

        mock_result = DownloadResult(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcY",
            video_id="dQw4w9WgXcY",
            status="done",
            title="Test Song",
            file_path=str(dummy_file),
            duration=180,
            filesize=3500000,
        )

        with patch("app.services.job_manager.download_one", return_value=mock_result):
            start_job(job.id, loop)
            for _ in range(50):
                if job.status == "done":
                    break
                await asyncio.sleep(0.05)

        assert job.status == "done"
        assert job.done_count == 2
        assert job.error_count == 0

    asyncio.run(_run())


def test_retry_item_mocked(sample_links):
    async def _run():
        job = create_job(sample_links, quality="192")
        loop = asyncio.get_running_loop()

        job.items[0].status = "error"
        job.items[0].error = "Test failure"
        job.status = "partial"

        mock_result = DownloadResult(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcY",
            video_id="dQw4w9WgXcY",
            status="done",
            title="Recovered Song",
            file_path="downloads/song.mp3",
        )

        with patch("app.services.job_manager.download_one", return_value=mock_result):
            success = retry_item(job.id, 0, loop)
            assert success is True
            for _ in range(50):
                if job.items[0].status == "done":
                    break
                await asyncio.sleep(0.05)

        assert job.items[0].status == "done"
        assert job.items[0].error is None

    asyncio.run(_run())
