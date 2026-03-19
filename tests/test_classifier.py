"""
Unit tests for pipeline/classifier.py
Covers: classify_chunks(), ChunkType
"""
import pytest

from pipeline.classifier import classify_chunks, ChunkType
from pipeline.chunker import Chunk
from pipeline.parser import DocumentElement, ElementType


class TestClassifyChunks:

    def _make_chunk(self, elements, chunk_id="c000"):
        return Chunk(
            chunk_id=chunk_id,
            order=0,
            section_id="s0",
            word_count=10,
            elements=elements,
        )

    # ── TC-CLS-001: Text-only chunk ──
    def test_text_only(self):
        elements = [
            DocumentElement(type=ElementType.HEADING, content="Title", heading_level=1),
            DocumentElement(type=ElementType.PARAGRAPH, content="Body text"),
        ]
        chunks = classify_chunks([self._make_chunk(elements)])
        assert chunks[0].chunk_type == ChunkType.TEXT

    # ── TC-CLS-002: Table chunk ──
    def test_table_chunk(self):
        elements = [
            DocumentElement(type=ElementType.PARAGRAPH, content="Intro"),
            DocumentElement(type=ElementType.TABLE, table_data=[["a", "b"]]),
        ]
        chunks = classify_chunks([self._make_chunk(elements)])
        assert chunks[0].chunk_type == ChunkType.TABLE

    # ── TC-CLS-003: Image chunk ──
    def test_image_chunk(self):
        elements = [
            DocumentElement(type=ElementType.IMAGE, image_bytes=b"\x89PNG"),
        ]
        chunks = classify_chunks([self._make_chunk(elements)])
        assert chunks[0].chunk_type == ChunkType.IMAGE

    # ── TC-CLS-004: Mixed chunk (table + image) ──
    def test_mixed_chunk(self):
        elements = [
            DocumentElement(type=ElementType.TABLE, table_data=[["x"]]),
            DocumentElement(type=ElementType.IMAGE, image_bytes=b"\x89PNG"),
        ]
        chunks = classify_chunks([self._make_chunk(elements)])
        assert chunks[0].chunk_type == ChunkType.MIXED

    # ── TC-CLS-005: Empty chunk → TEXT ──
    def test_empty_elements_classified_as_text(self):
        chunks = classify_chunks([self._make_chunk([])])
        assert chunks[0].chunk_type == ChunkType.TEXT

    # ── TC-CLS-006: Multiple chunks classified independently ──
    def test_multiple_chunks(self):
        text_chunk = self._make_chunk(
            [DocumentElement(type=ElementType.PARAGRAPH, content="text")],
            chunk_id="c000",
        )
        table_chunk = self._make_chunk(
            [DocumentElement(type=ElementType.TABLE, table_data=[["a"]])],
            chunk_id="c001",
        )
        image_chunk = self._make_chunk(
            [DocumentElement(type=ElementType.IMAGE, image_bytes=b"img")],
            chunk_id="c002",
        )

        results = classify_chunks([text_chunk, table_chunk, image_chunk])
        assert results[0].chunk_type == ChunkType.TEXT
        assert results[1].chunk_type == ChunkType.TABLE
        assert results[2].chunk_type == ChunkType.IMAGE

    # ── TC-CLS-007: Heading-only chunk = TEXT ──
    def test_heading_only_is_text(self):
        elements = [
            DocumentElement(type=ElementType.HEADING, content="Title", heading_level=1),
        ]
        chunks = classify_chunks([self._make_chunk(elements)])
        assert chunks[0].chunk_type == ChunkType.TEXT

    # ── TC-CLS-008: Table without image = TABLE not MIXED ──
    def test_table_with_paragraph_not_mixed(self):
        elements = [
            DocumentElement(type=ElementType.PARAGRAPH, content="context"),
            DocumentElement(type=ElementType.TABLE, table_data=[["a"]]),
            DocumentElement(type=ElementType.PARAGRAPH, content="after table"),
        ]
        chunks = classify_chunks([self._make_chunk(elements)])
        assert chunks[0].chunk_type == ChunkType.TABLE

    # ── TC-CLS-009: Image without table = IMAGE not MIXED ──
    def test_image_with_paragraph_not_mixed(self):
        elements = [
            DocumentElement(type=ElementType.PARAGRAPH, content="context"),
            DocumentElement(type=ElementType.IMAGE, image_bytes=b"img"),
        ]
        chunks = classify_chunks([self._make_chunk(elements)])
        assert chunks[0].chunk_type == ChunkType.IMAGE

    # ── TC-CLS-010: Return same list (mutated in place) ──
    def test_returns_same_list(self):
        original = [self._make_chunk([DocumentElement(type=ElementType.PARAGRAPH, content="x")])]
        result = classify_chunks(original)
        assert result is original
