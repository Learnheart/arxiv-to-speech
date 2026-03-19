"""
Unit tests for pipeline/enricher.py
Covers: enrich_chunk(), _resize_image()
"""
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from pipeline.enricher import enrich_chunk, _resize_image
from pipeline.chunker import Chunk
from pipeline.classifier import ChunkType
from pipeline.parser import DocumentElement, ElementType


# ══════════════════════════════════════════════════════════
# TC-IMG: _resize_image()
# ══════════════════════════════════════════════════════════

class TestResizeImage:

    def test_small_image_unchanged(self):
        """Image smaller than max_size should not be resized."""
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (100, 100), color="red")
        buf = BytesIO()
        img.save(buf, format="PNG")
        original_bytes = buf.getvalue()

        result = _resize_image(original_bytes, max_size=1024)
        # Result should still be valid PNG
        result_img = Image.open(BytesIO(result))
        assert result_img.size == (100, 100)

    def test_large_image_resized(self):
        """Image larger than max_size should be resized."""
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (2048, 2048), color="blue")
        buf = BytesIO()
        img.save(buf, format="PNG")

        result = _resize_image(buf.getvalue(), max_size=512)
        result_img = Image.open(BytesIO(result))
        assert max(result_img.size) <= 512

    def test_output_is_png(self):
        """Output should always be PNG format."""
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (50, 50))
        buf = BytesIO()
        img.save(buf, format="JPEG")

        result = _resize_image(buf.getvalue())
        # PNG magic bytes
        assert result[:4] == b"\x89PNG"


# ══════════════════════════════════════════════════════════
# TC-ENR: enrich_chunk()
# ══════════════════════════════════════════════════════════

class TestEnrichChunk:

    @pytest.fixture
    def llm_semaphore(self):
        return asyncio.Semaphore(5)

    # ── TC-ENR-001: TEXT chunk → clean text, no LLM call ──
    @pytest.mark.asyncio
    async def test_text_chunk_no_llm(self, llm_semaphore):
        chunk = Chunk(
            chunk_id="c000", order=0, section_id="s0", word_count=5,
            elements=[
                DocumentElement(type=ElementType.HEADING, content="Title", heading_level=1),
                DocumentElement(type=ElementType.PARAGRAPH, content="Body text here."),
            ],
            chunk_type=ChunkType.TEXT,
        )
        with patch("pipeline.enricher.describe_image") as mock_img, \
             patch("pipeline.enricher.narrate_table") as mock_tbl:
            result = await enrich_chunk(chunk, llm_semaphore)
            mock_img.assert_not_called()
            mock_tbl.assert_not_called()
        assert "Title" in result
        assert "Body text here" in result

    # ── TC-ENR-002: TABLE chunk → calls narrate_table ──
    @pytest.mark.asyncio
    async def test_table_chunk_calls_llm(self, llm_semaphore):
        chunk = Chunk(
            chunk_id="c001", order=1, section_id="s1", word_count=10,
            elements=[
                DocumentElement(
                    type=ElementType.TABLE,
                    table_data=[["Name", "Score"], ["Alice", "95"]],
                ),
            ],
            chunk_type=ChunkType.TABLE,
        )
        with patch("pipeline.enricher.narrate_table", new_callable=AsyncMock, return_value="Alice dat 95 diem") as mock_narrate, \
             patch("pipeline.enricher.cache_get", return_value=None), \
             patch("pipeline.enricher.cache_set"):
            result = await enrich_chunk(chunk, llm_semaphore)
            mock_narrate.assert_called_once()
        assert "Alice dat 95 diem" in result

    # ── TC-ENR-003: IMAGE chunk → calls describe_image ──
    @pytest.mark.asyncio
    async def test_image_chunk_calls_llm(self, llm_semaphore, image_element):
        chunk = Chunk(
            chunk_id="c002", order=2, section_id="s2", word_count=0,
            elements=[image_element],
            chunk_type=ChunkType.IMAGE,
        )
        with patch("pipeline.enricher.describe_image", new_callable=AsyncMock, return_value="Mo ta hinh anh") as mock_desc, \
             patch("pipeline.enricher._resize_image", return_value=b"resized_png") as mock_resize, \
             patch("pipeline.enricher.cache_get", return_value=None), \
             patch("pipeline.enricher.cache_set"):
            result = await enrich_chunk(chunk, llm_semaphore)
            mock_desc.assert_called_once()
        assert "Mo ta hinh anh" in result

    # ── TC-ENR-004: Cache hit skips LLM ──
    @pytest.mark.asyncio
    async def test_table_cache_hit_skips_llm(self, llm_semaphore):
        chunk = Chunk(
            chunk_id="c001", order=1, section_id="s1", word_count=10,
            elements=[
                DocumentElement(type=ElementType.TABLE, table_data=[["a", "b"]]),
            ],
            chunk_type=ChunkType.TABLE,
        )
        with patch("pipeline.enricher.narrate_table", new_callable=AsyncMock) as mock_narrate, \
             patch("pipeline.enricher.cache_get", return_value="cached narration"), \
             patch("pipeline.enricher.cache_set"):
            result = await enrich_chunk(chunk, llm_semaphore)
            mock_narrate.assert_not_called()
        assert "cached narration" in result

    # ── TC-ENR-005: MIXED chunk processes both table and image ──
    @pytest.mark.asyncio
    async def test_mixed_chunk(self, llm_semaphore, image_element):
        chunk = Chunk(
            chunk_id="c003", order=3, section_id="s3", word_count=10,
            elements=[
                DocumentElement(type=ElementType.TABLE, table_data=[["x"]]),
                image_element,
            ],
            chunk_type=ChunkType.MIXED,
        )
        with patch("pipeline.enricher.narrate_table", new_callable=AsyncMock, return_value="table narration"), \
             patch("pipeline.enricher.describe_image", new_callable=AsyncMock, return_value="image description"), \
             patch("pipeline.enricher._resize_image", return_value=b"resized_png"), \
             patch("pipeline.enricher.cache_get", return_value=None), \
             patch("pipeline.enricher.cache_set"):
            result = await enrich_chunk(chunk, llm_semaphore)
        assert "table narration" in result
        assert "image description" in result

    # ── TC-ENR-006: TEXT chunk with empty content ──
    @pytest.mark.asyncio
    async def test_text_chunk_empty_content(self, llm_semaphore):
        chunk = Chunk(
            chunk_id="c000", order=0, section_id="s0", word_count=0,
            elements=[
                DocumentElement(type=ElementType.PARAGRAPH, content=""),
            ],
            chunk_type=ChunkType.TEXT,
        )
        result = await enrich_chunk(chunk, llm_semaphore)
        assert result == ""

    # ── TC-ENR-007: Semaphore limits concurrency ──
    @pytest.mark.asyncio
    async def test_semaphore_acquired_for_llm_calls(self):
        """LLM calls should be rate-limited by semaphore."""
        sem = asyncio.Semaphore(1)

        chunk = Chunk(
            chunk_id="c001", order=1, section_id="s1", word_count=10,
            elements=[
                DocumentElement(type=ElementType.TABLE, table_data=[["a"]]),
            ],
            chunk_type=ChunkType.TABLE,
        )

        async def slow_narrate(md):
            await asyncio.sleep(0.1)
            return "narrated"

        with patch("pipeline.enricher.narrate_table", side_effect=slow_narrate), \
             patch("pipeline.enricher.cache_get", return_value=None), \
             patch("pipeline.enricher.cache_set"):
            result = await enrich_chunk(chunk, sem)
        assert "narrated" in result
