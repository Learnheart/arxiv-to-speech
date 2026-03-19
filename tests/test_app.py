"""
Tests for app.py
Covers: _format_stats(), get_history(), process_upload(), process_url()
"""
import os
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

from app import _format_stats, get_history


# ══════════════════════════════════════════════════════════
# TC-STAT: _format_stats()
# ══════════════════════════════════════════════════════════

class TestFormatStats:

    def test_none_input(self):
        result = _format_stats(None)
        assert "Khong co thong tin" in result

    def test_completed_job(self):
        job = {
            "status": "completed",
            "chunks_total": 10,
            "chunks_failed": 0,
            "audio_duration": 125.5,
            "audio_size": 5 * 1024 * 1024,
            "estimated_cost": 0,
            "tts_voice": "vi-VN-HoaiMyNeural",
        }
        result = _format_stats(job)
        assert "OK" in result
        assert "10/10" in result
        assert "2:05" in result
        assert "5.0MB" in result

    def test_partial_failure_job(self):
        job = {
            "status": "partial_failure",
            "chunks_total": 10,
            "chunks_failed": 2,
            "audio_duration": 90.0,
            "audio_size": 3 * 1024 * 1024,
            "estimated_cost": 0,
            "tts_voice": "vi-VN-HoaiMyNeural",
        }
        result = _format_stats(job)
        assert "WARN" in result
        assert "8/10" in result

    def test_failed_job(self):
        job = {
            "status": "failed",
            "chunks_total": 0,
            "chunks_failed": 0,
            "audio_duration": None,
            "audio_size": None,
            "estimated_cost": None,
            "tts_voice": "vi-VN-HoaiMyNeural",
        }
        result = _format_stats(job)
        assert "FAIL" in result

    def test_zero_duration(self):
        job = {
            "status": "completed",
            "chunks_total": 1,
            "chunks_failed": 0,
            "audio_duration": 0,
            "audio_size": 0,
            "estimated_cost": 0,
            "tts_voice": "vi-VN-HoaiMyNeural",
        }
        result = _format_stats(job)
        assert "0:00" in result


# ══════════════════════════════════════════════════════════
# TC-HIST: get_history()
# ══════════════════════════════════════════════════════════

class TestGetHistory:

    @patch("app.get_recent_jobs")
    def test_no_jobs(self, mock_get_jobs):
        mock_get_jobs.return_value = []
        result = get_history()
        assert "Chua co lich su" in result

    @patch("app.get_recent_jobs")
    def test_with_jobs(self, mock_get_jobs):
        mock_get_jobs.return_value = [
            {
                "status": "completed",
                "audio_duration": 60.0,
                "audio_size": 1024 * 1024,
                "created_at": "2026-03-19T10:00:00",
                "file_type": "pdf",
            },
            {
                "status": "failed",
                "audio_duration": 0,
                "audio_size": 0,
                "created_at": "2026-03-19T09:00:00",
                "file_type": "docx",
            },
        ]
        result = get_history()
        assert "[OK]" in result
        assert "[FAIL]" in result
        assert "pdf" in result
        assert "docx" in result


# ══════════════════════════════════════════════════════════
# TC-UPLOAD: process_upload() — happy path (mocked)
# ══════════════════════════════════════════════════════════

class TestProcessUpload:

    @patch("app.get_job")
    @patch("app._run_pipeline_in_thread")
    @patch("app.create_job")
    @patch("app.validate_file")
    def test_none_file_returns_error(self, mock_validate, mock_create, mock_run, mock_get):
        from app import process_upload
        result_audio, result_stats = process_upload(None, "vi-VN-HoaiMyNeural", progress=MagicMock())
        assert result_audio is None
        assert "Chua chon file" in result_stats

    @patch("app.get_job")
    @patch("app._run_pipeline_in_thread")
    @patch("app.create_job")
    @patch("app.validate_file")
    def test_invalid_file_returns_error(self, mock_validate, mock_create, mock_run, mock_get):
        from app import process_upload
        from utils.validator import ValidationResult
        mock_validate.return_value = ValidationResult(valid=False, error="File khong hop le")

        mock_file = MagicMock()
        mock_file.name = "/tmp/test.txt"

        with patch("builtins.open", MagicMock()):
            result_audio, result_stats = process_upload(mock_file, "vi-VN-HoaiMyNeural", progress=MagicMock())

        assert result_audio is None
        assert "khong hop le" in result_stats


class TestProcessUrl:

    def test_empty_url_returns_error(self):
        from app import process_url
        result_audio, result_stats = process_url("", "vi-VN-HoaiMyNeural", progress=MagicMock())
        assert result_audio is None
        assert "Chua nhap URL" in result_stats

    def test_none_url_returns_error(self):
        from app import process_url
        result_audio, result_stats = process_url(None, "vi-VN-HoaiMyNeural", progress=MagicMock())
        assert result_audio is None
