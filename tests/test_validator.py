"""
Unit tests for utils/validator.py
Covers: validate_file()
"""
import pytest

from utils.validator import validate_file, ValidationResult, MAGIC_PDF, MAGIC_DOCX
from config import MAX_FILE_SIZE


class TestValidateFile:
    """Test suite for file validation."""

    # ── TC-VAL-001: Valid PDF ──
    def test_valid_pdf(self):
        content = b"%PDF-1.4 some pdf content here" + b"\x00" * 100
        result = validate_file(content, "document.pdf")
        assert result.valid is True
        assert result.file_type == "pdf"
        assert result.file_size == len(content)
        assert result.error is None

    # ── TC-VAL-002: Valid DOCX ──
    def test_valid_docx(self):
        content = b"PK\x03\x04" + b"\x00" * 100
        result = validate_file(content, "document.docx")
        assert result.valid is True
        assert result.file_type == "docx"

    # ── TC-VAL-003: Empty file ──
    def test_empty_file(self):
        result = validate_file(b"", "empty.pdf")
        assert result.valid is False
        assert "rong" in result.error.lower() or "rong" in result.error

    # ── TC-VAL-004: File too large ──
    def test_file_exceeds_max_size(self):
        content = b"%PDF" + b"\x00" * (MAX_FILE_SIZE + 1)
        result = validate_file(content, "huge.pdf")
        assert result.valid is False
        assert "qua lon" in result.error.lower() or "lon" in result.error

    # ── TC-VAL-005: File exactly at max size ──
    def test_file_at_max_size(self):
        content = b"%PDF" + b"\x00" * (MAX_FILE_SIZE - 4)
        result = validate_file(content, "maxsize.pdf")
        assert result.valid is True

    # ── TC-VAL-006: Invalid magic bytes ──
    def test_invalid_magic_bytes(self):
        content = b"INVALID_HEADER" + b"\x00" * 100
        result = validate_file(content, "bad.pdf")
        assert result.valid is False
        assert "khong hop le" in result.error.lower() or "hop le" in result.error

    # ── TC-VAL-007: ZIP file but not .docx extension ──
    def test_zip_without_docx_extension(self):
        content = b"PK\x03\x04" + b"\x00" * 100
        result = validate_file(content, "archive.zip")
        assert result.valid is False

    # ── TC-VAL-008: PK header with .docx extension ──
    def test_pk_header_docx_extension(self):
        content = b"PK\x03\x04" + b"\x00" * 100
        result = validate_file(content, "file.DOCX")
        assert result.valid is True
        assert result.file_type == "docx"

    # ── TC-VAL-009: TXT file ──
    def test_txt_file_rejected(self):
        content = b"Hello World plain text"
        result = validate_file(content, "readme.txt")
        assert result.valid is False

    # ── TC-VAL-010: EXE file ──
    def test_exe_file_rejected(self):
        content = b"MZ\x90\x00" + b"\x00" * 100
        result = validate_file(content, "malware.exe")
        assert result.valid is False

    # ── TC-VAL-011: Very small valid PDF ──
    def test_minimal_pdf(self):
        content = b"%PDF-1.0"
        result = validate_file(content, "tiny.pdf")
        assert result.valid is True
        assert result.file_size == 8

    # ── TC-VAL-012: File size field populated ──
    def test_file_size_populated(self):
        content = b"%PDF" + b"x" * 1000
        result = validate_file(content, "test.pdf")
        assert result.file_size == 1004
