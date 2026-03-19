"""
Shared fixtures for D2S Pipeline tests.
"""
import asyncio
import os
import sqlite3
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.parser import DocumentElement, ElementType
from pipeline.chunker import Chunk


# ── Async support ──

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Temp directories ──

@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a clean temp directory."""
    return tmp_path


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temp SQLite database with schema initialized."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              TEXT PRIMARY KEY,
            status          TEXT NOT NULL DEFAULT 'processing',
            source_type     TEXT NOT NULL DEFAULT 'upload',
            source_url      TEXT,
            file_path       TEXT NOT NULL,
            file_type       TEXT NOT NULL,
            file_size_bytes INTEGER,
            chunks_total    INTEGER DEFAULT 0,
            chunks_failed   INTEGER DEFAULT 0,
            audio_path      TEXT,
            audio_duration  REAL,
            audio_size      INTEGER,
            tts_voice       TEXT DEFAULT 'vi-VN-HoaiMyNeural',
            estimated_cost  REAL DEFAULT 0,
            error_message   TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            completed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS cache (
            hash        TEXT PRIMARY KEY,
            type        TEXT NOT NULL,
            result      TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            expires_at  TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    return db_path


# ── Sample DocumentElements ──

@pytest.fixture
def heading_element():
    return DocumentElement(
        type=ElementType.HEADING,
        content="Chapter 1: Introduction",
        heading_level=1,
        order=0,
    )


@pytest.fixture
def paragraph_element():
    return DocumentElement(
        type=ElementType.PARAGRAPH,
        content="This is a sample paragraph with enough words to be meaningful.",
        order=1,
    )


@pytest.fixture
def table_element():
    return DocumentElement(
        type=ElementType.TABLE,
        table_data=[
            ["Name", "Age", "City"],
            ["Alice", "30", "Hanoi"],
            ["Bob", "25", "HCMC"],
        ],
        order=2,
    )


@pytest.fixture
def image_element():
    # Minimal valid PNG: 1x1 pixel
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00"
        b"\x00\x00\x00IEND\xaeB`\x82"
    )
    return DocumentElement(
        type=ElementType.IMAGE,
        image_bytes=png_bytes,
        order=3,
    )


@pytest.fixture
def sample_elements(heading_element, paragraph_element, table_element, image_element):
    """A mixed list of all element types."""
    return [heading_element, paragraph_element, table_element, image_element]


@pytest.fixture
def text_only_elements():
    """Elements with only headings and paragraphs."""
    return [
        DocumentElement(type=ElementType.HEADING, content="Title", heading_level=1, order=0),
        DocumentElement(type=ElementType.PARAGRAPH, content="Paragraph one.", order=1),
        DocumentElement(type=ElementType.PARAGRAPH, content="Paragraph two.", order=2),
    ]


@pytest.fixture
def text_chunk(text_only_elements):
    return Chunk(
        chunk_id="c000",
        order=0,
        section_id="s0",
        word_count=5,
        elements=text_only_elements,
        chunk_type="TEXT",
    )


@pytest.fixture
def table_chunk(table_element):
    return Chunk(
        chunk_id="c001",
        order=1,
        section_id="s1",
        word_count=10,
        elements=[table_element],
        chunk_type="TABLE",
    )


@pytest.fixture
def image_chunk(image_element):
    return Chunk(
        chunk_id="c002",
        order=2,
        section_id="s2",
        word_count=0,
        elements=[image_element],
        chunk_type="IMAGE",
    )


@pytest.fixture
def mixed_chunk(table_element, image_element):
    return Chunk(
        chunk_id="c003",
        order=3,
        section_id="s3",
        word_count=10,
        elements=[table_element, image_element],
        chunk_type="MIXED",
    )


# ── Sample files ──

@pytest.fixture
def sample_pdf_bytes():
    """Minimal valid PDF bytes (won't parse real content but passes magic bytes check)."""
    return b"%PDF-1.4 minimal test content"


@pytest.fixture
def sample_docx_bytes():
    """DOCX magic bytes (PK = ZIP header)."""
    return b"PK\x03\x04 minimal test content for docx"
