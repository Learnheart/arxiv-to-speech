"""
Unit tests for pipeline/chunker.py
Covers: chunk_elements(), _word_count(), Chunk dataclass
"""
import pytest

from pipeline.chunker import chunk_elements, _word_count, Chunk
from pipeline.parser import DocumentElement, ElementType


# ══════════════════════════════════════════════════════════
# TC-WC: _word_count()
# ══════════════════════════════════════════════════════════

class TestWordCount:

    def test_empty_list(self):
        assert _word_count([]) == 0

    def test_paragraph_words(self):
        el = DocumentElement(type=ElementType.PARAGRAPH, content="one two three")
        assert _word_count([el]) == 3

    def test_table_words_counted(self):
        el = DocumentElement(
            type=ElementType.TABLE,
            table_data=[["hello world", "foo bar baz"]],
        )
        assert _word_count([el]) == 5

    def test_mixed_content_and_table(self):
        p = DocumentElement(type=ElementType.PARAGRAPH, content="a b c")
        t = DocumentElement(type=ElementType.TABLE, table_data=[["x y"]])
        assert _word_count([p, t]) == 5

    def test_empty_content(self):
        el = DocumentElement(type=ElementType.PARAGRAPH, content="")
        assert _word_count([el]) == 0

    def test_image_no_words(self):
        el = DocumentElement(type=ElementType.IMAGE, image_bytes=b"\x89PNG")
        assert _word_count([el]) == 0


# ══════════════════════════════════════════════════════════
# TC-CHK: chunk_elements()
# ══════════════════════════════════════════════════════════

class TestChunkElements:

    # ── TC-CHK-001: Empty input ──
    def test_empty_elements(self):
        assert chunk_elements([]) == []

    # ── TC-CHK-002: Single paragraph → single chunk ──
    def test_single_paragraph(self):
        elements = [
            DocumentElement(type=ElementType.PARAGRAPH, content="Hello world test.", order=0),
        ]
        chunks = chunk_elements(elements, max_words=100)
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "c000"
        assert chunks[0].order == 0

    # ── TC-CHK-003: Heading splits create sections ──
    def test_heading_creates_new_section(self):
        elements = [
            DocumentElement(type=ElementType.HEADING, content="Section 1", heading_level=1, order=0),
            DocumentElement(type=ElementType.PARAGRAPH, content="Content one.", order=1),
            DocumentElement(type=ElementType.HEADING, content="Section 2", heading_level=1, order=2),
            DocumentElement(type=ElementType.PARAGRAPH, content="Content two.", order=3),
        ]
        chunks = chunk_elements(elements, max_words=100)
        assert len(chunks) >= 1
        # All chunks should have section_ids
        section_ids = [c.section_id for c in chunks]
        assert all(s.startswith("s") for s in section_ids)

    # ── TC-CHK-004: Small sections merged (greedy packing) ──
    def test_small_sections_merged(self):
        elements = [
            DocumentElement(type=ElementType.HEADING, content="A", heading_level=1, order=0),
            DocumentElement(type=ElementType.PARAGRAPH, content="short", order=1),
            DocumentElement(type=ElementType.HEADING, content="B", heading_level=1, order=2),
            DocumentElement(type=ElementType.PARAGRAPH, content="also short", order=3),
        ]
        chunks = chunk_elements(elements, max_words=100)
        # Both sections fit in one chunk
        assert len(chunks) == 1

    # ── TC-CHK-005: Oversized section sub-chunked ──
    def test_oversized_section_split(self):
        # Create section with many paragraphs exceeding max_words
        elements = [
            DocumentElement(type=ElementType.HEADING, content="Big Section", heading_level=1, order=0),
        ]
        for i in range(50):
            elements.append(
                DocumentElement(
                    type=ElementType.PARAGRAPH,
                    content=" ".join([f"word{j}" for j in range(100)]),
                    order=i + 1,
                )
            )
        chunks = chunk_elements(elements, max_words=500)
        # Should be split into multiple chunks
        assert len(chunks) > 1
        # All chunks should respect max_words (approximately)
        for chunk in chunks:
            assert chunk.word_count <= 600  # some tolerance

    # ── TC-CHK-006: Chunk IDs are sequential ──
    def test_chunk_ids_sequential(self):
        elements = [
            DocumentElement(type=ElementType.HEADING, content="S1", heading_level=1, order=0),
            DocumentElement(type=ElementType.PARAGRAPH, content=" ".join(["w"] * 1000), order=1),
            DocumentElement(type=ElementType.HEADING, content="S2", heading_level=1, order=2),
            DocumentElement(type=ElementType.PARAGRAPH, content=" ".join(["w"] * 1000), order=3),
        ]
        chunks = chunk_elements(elements, max_words=500)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_id == f"c{i:03d}"
            assert chunk.order == i

    # ── TC-CHK-007: H4+ headings do NOT split sections ──
    def test_h4_does_not_split(self):
        elements = [
            DocumentElement(type=ElementType.HEADING, content="Main", heading_level=1, order=0),
            DocumentElement(type=ElementType.PARAGRAPH, content="Content", order=1),
            DocumentElement(type=ElementType.HEADING, content="Sub-detail", heading_level=4, order=2),
            DocumentElement(type=ElementType.PARAGRAPH, content="More content", order=3),
        ]
        chunks = chunk_elements(elements, max_words=100)
        # H4 should not trigger a section split, so only 1 chunk expected
        assert len(chunks) == 1

    # ── TC-CHK-008: Word count calculated correctly ──
    def test_word_count_in_chunk(self):
        elements = [
            DocumentElement(type=ElementType.PARAGRAPH, content="one two three four five", order=0),
        ]
        chunks = chunk_elements(elements, max_words=100)
        assert chunks[0].word_count == 5

    # ── TC-CHK-009: Empty content sections skipped ──
    def test_empty_content_sections_skipped(self):
        elements = [
            DocumentElement(type=ElementType.HEADING, content="Empty", heading_level=1, order=0),
            # No content elements after heading
            DocumentElement(type=ElementType.HEADING, content="Has Content", heading_level=1, order=1),
            DocumentElement(type=ElementType.PARAGRAPH, content="Real text here", order=2),
        ]
        chunks = chunk_elements(elements, max_words=100)
        # The empty section might be merged or skipped
        assert len(chunks) >= 1
        # At least one chunk should have real content
        assert any(c.word_count > 0 for c in chunks)

    # ── TC-CHK-010: Max words boundary ──
    def test_max_words_boundary_exact(self):
        """Section with exactly max_words should fit in one chunk."""
        content = " ".join(["word"] * 100)
        elements = [
            DocumentElement(type=ElementType.PARAGRAPH, content=content, order=0),
        ]
        chunks = chunk_elements(elements, max_words=100)
        assert len(chunks) == 1

    # ── TC-CHK-011: Elements preserved in chunks ──
    def test_elements_preserved(self):
        elements = [
            DocumentElement(type=ElementType.PARAGRAPH, content="Text A", order=0),
            DocumentElement(type=ElementType.TABLE, table_data=[["x"]], order=1),
        ]
        chunks = chunk_elements(elements, max_words=100)
        all_elements = []
        for c in chunks:
            all_elements.extend(c.elements)
        assert len(all_elements) == 2
