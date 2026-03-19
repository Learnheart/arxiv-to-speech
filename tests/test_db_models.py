"""
Unit tests for db/models.py
Covers: init_db(), create_job(), get_job(), update_job(), complete_job(), fail_job(), get_recent_jobs()
"""
import sqlite3
from unittest.mock import patch

import pytest

from db.models import (
    init_db,
    create_job,
    get_job,
    update_job,
    complete_job,
    fail_job,
    get_recent_jobs,
)


@pytest.fixture(autouse=True)
def mock_db(tmp_db):
    """Redirect all DB operations to temp database."""
    def _get_conn():
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    patcher = patch("db.models.get_connection", side_effect=_get_conn)
    patcher.start()
    yield tmp_db
    patcher.stop()


# ══════════════════════════════════════════════════════════
# TC-DB: Database operations
# ══════════════════════════════════════════════════════════

class TestCreateJob:

    # ── TC-DB-001: Create job returns UUID ──
    def test_creates_job_returns_id(self):
        job_id = create_job(
            file_path="/tmp/test.pdf",
            file_type="pdf",
            file_size_bytes=1024,
        )
        assert isinstance(job_id, str)
        assert len(job_id) == 36  # UUID format

    # ── TC-DB-002: Job retrievable after creation ──
    def test_job_retrievable(self):
        job_id = create_job(
            file_path="/tmp/doc.docx",
            file_type="docx",
            file_size_bytes=2048,
            tts_voice="vi-VN-NamMinhNeural",
        )
        job = get_job(job_id)
        assert job is not None
        assert job["file_path"] == "/tmp/doc.docx"
        assert job["file_type"] == "docx"
        assert job["file_size_bytes"] == 2048
        assert job["tts_voice"] == "vi-VN-NamMinhNeural"
        assert job["status"] == "processing"

    # ── TC-DB-003: Job with URL source ──
    def test_url_source_job(self):
        job_id = create_job(
            file_path="/tmp/downloaded.pdf",
            file_type="pdf",
            file_size_bytes=5000,
            source_type="url",
            source_url="https://example.com/paper.pdf",
        )
        job = get_job(job_id)
        assert job["source_type"] == "url"
        assert job["source_url"] == "https://example.com/paper.pdf"


class TestGetJob:

    # ── TC-DB-004: Get nonexistent job returns None ──
    def test_nonexistent_job(self):
        result = get_job("nonexistent-uuid")
        assert result is None


class TestUpdateJob:

    # ── TC-DB-005: Update single field ──
    def test_update_single_field(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        update_job(job_id, chunks_total=10)
        job = get_job(job_id)
        assert job["chunks_total"] == 10

    # ── TC-DB-006: Update multiple fields ──
    def test_update_multiple_fields(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        update_job(job_id, chunks_total=10, chunks_failed=2, status="partial_failure")
        job = get_job(job_id)
        assert job["chunks_total"] == 10
        assert job["chunks_failed"] == 2
        assert job["status"] == "partial_failure"

    # ── TC-DB-007: Update with no kwargs does nothing ──
    def test_update_no_kwargs(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        update_job(job_id)  # Should not raise


class TestCompleteJob:

    # ── TC-DB-008: Complete with zero failures → "completed" ──
    def test_completed_status(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        complete_job(
            job_id=job_id,
            audio_path="/tmp/audio.mp3",
            audio_duration=120.5,
            audio_size=5000000,
            chunks_total=10,
            chunks_failed=0,
        )
        job = get_job(job_id)
        assert job["status"] == "completed"
        assert job["audio_duration"] == 120.5
        assert job["completed_at"] is not None

    # ── TC-DB-009: Some failures but <20% → "partial_failure" ──
    def test_partial_failure_status(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        complete_job(
            job_id=job_id,
            audio_path="/tmp/audio.mp3",
            audio_duration=100.0,
            audio_size=3000000,
            chunks_total=10,
            chunks_failed=1,  # 10% failure
        )
        job = get_job(job_id)
        assert job["status"] == "partial_failure"

    # ── TC-DB-010: >=20% failures → "failed" ──
    def test_failed_status_high_failure_ratio(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        complete_job(
            job_id=job_id,
            audio_path="/tmp/audio.mp3",
            audio_duration=50.0,
            audio_size=1000000,
            chunks_total=10,
            chunks_failed=3,  # 30% failure
        )
        job = get_job(job_id)
        assert job["status"] == "failed"


class TestFailJob:

    # ── TC-DB-011: Fail job sets status and error message ──
    def test_fail_job(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        fail_job(job_id, "Something went wrong")
        job = get_job(job_id)
        assert job["status"] == "failed"
        assert job["error_message"] == "Something went wrong"
        assert job["completed_at"] is not None


class TestGetRecentJobs:

    # ── TC-DB-012: Returns empty list when no jobs ──
    def test_empty_list(self):
        jobs = get_recent_jobs()
        assert jobs == []

    # ── TC-DB-013: Returns all created jobs ──
    def test_returns_all_jobs(self):
        id1 = create_job("/tmp/1.pdf", "pdf", 100)
        id2 = create_job("/tmp/2.pdf", "pdf", 200)
        id3 = create_job("/tmp/3.pdf", "pdf", 300)

        jobs = get_recent_jobs(limit=10)
        assert len(jobs) == 3
        # All jobs should be returned
        job_ids = {j["id"] for j in jobs}
        assert id1 in job_ids
        assert id2 in job_ids
        assert id3 in job_ids

    # ── TC-DB-014: Limit parameter respected ──
    def test_limit_respected(self):
        for i in range(5):
            create_job(f"/tmp/{i}.pdf", "pdf", 100)
        jobs = get_recent_jobs(limit=3)
        assert len(jobs) == 3

    # ── TC-DB-015: Default voice is correct ──
    def test_default_voice(self):
        job_id = create_job("/tmp/f.pdf", "pdf", 100)
        job = get_job(job_id)
        assert job["tts_voice"] == "vi-VN-HoaiMyNeural"
