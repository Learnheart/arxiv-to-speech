"""
D2S Pipeline — File validation: magic bytes + size check.
"""
from dataclasses import dataclass
from typing import Optional

from config import MAX_FILE_SIZE
from logger import logger

# Magic bytes signatures
MAGIC_PDF = b"%PDF"
MAGIC_DOCX = b"PK"  # ZIP-based (DOCX is a ZIP archive)


@dataclass
class ValidationResult:
    valid: bool
    file_type: Optional[str] = None  # "pdf" or "docx"
    file_size: int = 0
    error: Optional[str] = None


def validate_file(file_bytes: bytes, filename: str) -> ValidationResult:
    """Validate uploaded file by magic bytes and size."""
    size = len(file_bytes)

    # Size check
    if size == 0:
        return ValidationResult(valid=False, error="File rong.")
    if size > MAX_FILE_SIZE:
        return ValidationResult(
            valid=False,
            error=f"File qua lon ({size / 1024 / 1024:.1f}MB). Gioi han {MAX_FILE_SIZE / 1024 / 1024:.0f}MB.",
        )

    # Magic bytes check
    file_type = None
    if file_bytes[:4] == MAGIC_PDF:
        file_type = "pdf"
    elif file_bytes[:2] == MAGIC_DOCX and filename.lower().endswith(".docx"):
        file_type = "docx"
    else:
        return ValidationResult(
            valid=False,
            error="File khong hop le. Chi ho tro DOCX va PDF.",
        )

    logger.info("File validated: %s (type=%s, size=%d bytes)", filename, file_type, size)
    return ValidationResult(valid=True, file_type=file_type, file_size=size)
