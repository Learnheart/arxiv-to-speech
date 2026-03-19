"""
Integration tests for pipeline/orchestrator.py
Covers: process_chunk_pipeline(), run_pipeline()
"""
import asyncio
import os
import sqlite3
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from pipeline.orchestrator import process_chunk_pipeline, run_pipeline
from pipeline.chunker import Chunk
from pipeline.parser import DocumentElement, ElementType
from pipeline.stitcher import AudioSegmentInfo


@pytest.fixture
def mock_db_for_orchestrator(tmp_db):
    """Mock all db.models functions to use temp DB."""
    def _get_conn():
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        return conn

    with patch("db.models.get_connection", side_effect=_get_conn), \
         patch("pipeline.orchestrator.complete_job") as mock_complete, \
         patch("pipeline.orchestrator.fail_job") as mock_fail, \
         patch("pipeline.orchestrator.update_job") as mock_update:
        yield {
            "complete_job": mock_complete,
            "fail_job": mock_fail,
            "update_job": mock_update,
        }


# ══════════════════════════════════════════════════════════
# TC-CHP: process_chunk_pipeline()
# ══════════════════════════════════════════════════════════

class TestProcessChunkPipeline:

    @pytest.fixture
    def semaphores(self):
        return asyncio.Semaphore(5), asyncio.Semaphore(10)

    # ── TC-CHP-001: Successful chunk processing ──
    @pytest.mark.asyncio
    async def test_success(self, semaphores, tmp_path):
        llm_sem, tts_sem = semaphores
        chunk = Chunk(
            chunk_id="c000", order=0, section_id="s0", word_count=5,
            elements=[DocumentElement(type=ElementType.PARAGRAPH, content="Hello world")],
            chunk_type="TEXT",
        )

        with patch("pipeline.orchestrator.enrich_chunk", new_callable=AsyncMock, return_value="Hello world"), \
             patch("pipeline.orchestrator.synthesize_text", new_callable=AsyncMock, return_value=True), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)):
            result = await process_chunk_pipeline(chunk, "job123", "vi-VN-HoaiMyNeural", llm_sem, tts_sem)

        assert isinstance(result, AudioSegmentInfo)
        assert result.success is True
        assert result.order == 0
        assert result.section_id == "s0"

    # ── TC-CHP-002: Empty enrichment → failure ──
    @pytest.mark.asyncio
    async def test_empty_enrichment(self, semaphores, tmp_path):
        llm_sem, tts_sem = semaphores
        chunk = Chunk(
            chunk_id="c000", order=0, section_id="s0", word_count=0,
            elements=[DocumentElement(type=ElementType.PARAGRAPH, content="")],
            chunk_type="TEXT",
        )

        with patch("pipeline.orchestrator.enrich_chunk", new_callable=AsyncMock, return_value=""), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)):
            result = await process_chunk_pipeline(chunk, "job123", "vi-VN-HoaiMyNeural", llm_sem, tts_sem)

        assert result.success is False

    # ── TC-CHP-003: TTS failure → success=False ──
    @pytest.mark.asyncio
    async def test_tts_failure(self, semaphores, tmp_path):
        llm_sem, tts_sem = semaphores
        chunk = Chunk(
            chunk_id="c000", order=0, section_id="s0", word_count=5,
            elements=[DocumentElement(type=ElementType.PARAGRAPH, content="Text")],
            chunk_type="TEXT",
        )

        with patch("pipeline.orchestrator.enrich_chunk", new_callable=AsyncMock, return_value="Text"), \
             patch("pipeline.orchestrator.synthesize_text", new_callable=AsyncMock, return_value=False), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)):
            result = await process_chunk_pipeline(chunk, "job123", "vi-VN-HoaiMyNeural", llm_sem, tts_sem)

        assert result.success is False

    # ── TC-CHP-004: Exception caught gracefully ──
    @pytest.mark.asyncio
    async def test_exception_caught(self, semaphores, tmp_path):
        llm_sem, tts_sem = semaphores
        chunk = Chunk(
            chunk_id="c000", order=0, section_id="s0", word_count=5,
            elements=[DocumentElement(type=ElementType.PARAGRAPH, content="Text")],
            chunk_type="TEXT",
        )

        with patch("pipeline.orchestrator.enrich_chunk", new_callable=AsyncMock, side_effect=RuntimeError("boom")), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)):
            result = await process_chunk_pipeline(chunk, "job123", "vi-VN-HoaiMyNeural", llm_sem, tts_sem)

        assert result.success is False


# ══════════════════════════════════════════════════════════
# TC-PIPE: run_pipeline()
# ══════════════════════════════════════════════════════════

class TestRunPipeline:

    # ── TC-PIPE-001: Empty document → fail_job called ──
    @pytest.mark.asyncio
    async def test_empty_document_fails(self, tmp_path, mock_db_for_orchestrator):
        # Create a dummy file
        file_path = str(tmp_path / "empty.pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4")

        with patch("pipeline.orchestrator.parse_document", return_value=[]):
            result = await run_pipeline("job1", file_path, "pdf")

        assert result is None
        mock_db_for_orchestrator["fail_job"].assert_called_once()

    # ── TC-PIPE-002: No chunks → fail_job called ──
    @pytest.mark.asyncio
    async def test_no_chunks_fails(self, tmp_path, mock_db_for_orchestrator):
        file_path = str(tmp_path / "test.pdf")
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4")

        elements = [DocumentElement(type=ElementType.PARAGRAPH, content="", order=0)]

        with patch("pipeline.orchestrator.parse_document", return_value=elements), \
             patch("pipeline.orchestrator.chunk_elements", return_value=[]):
            result = await run_pipeline("job2", file_path, "pdf")

        assert result is None
        mock_db_for_orchestrator["fail_job"].assert_called_once()

    # ── TC-PIPE-003: Too many failures (>=20%) → fail_job ──
    @pytest.mark.asyncio
    async def test_high_failure_ratio_fails(self, tmp_path, mock_db_for_orchestrator):
        file_path = str(tmp_path / "test.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        elements = [DocumentElement(type=ElementType.PARAGRAPH, content="text", order=0)]
        chunks = [
            Chunk(chunk_id=f"c{i:03d}", order=i, section_id="s0", word_count=5,
                  elements=elements, chunk_type="TEXT")
            for i in range(5)
        ]

        # 2/5 = 40% failure
        async def mock_process(chunk, job_id, voice, llm_sem, tts_sem):
            return AudioSegmentInfo(
                order=chunk.order,
                audio_path=f"/tmp/seg_{chunk.order}.mp3",
                section_id=chunk.section_id,
                success=(chunk.order < 3),  # 3 success, 2 fail
            )

        with patch("pipeline.orchestrator.parse_document", return_value=elements), \
             patch("pipeline.orchestrator.chunk_elements", return_value=chunks), \
             patch("pipeline.orchestrator.classify_chunks", return_value=chunks), \
             patch("pipeline.orchestrator.process_chunk_pipeline", side_effect=mock_process), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)), \
             patch("pipeline.orchestrator.OUTPUTS_DIR", str(tmp_path)):
            result = await run_pipeline("job3", file_path, "pdf")

        assert result is None
        mock_db_for_orchestrator["fail_job"].assert_called()

    # ── TC-PIPE-004: Successful full pipeline ──
    @pytest.mark.asyncio
    async def test_successful_pipeline(self, tmp_path, mock_db_for_orchestrator):
        file_path = str(tmp_path / "test.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        elements = [DocumentElement(type=ElementType.PARAGRAPH, content="text", order=0)]
        chunks = [
            Chunk(chunk_id="c000", order=0, section_id="s0", word_count=5,
                  elements=elements, chunk_type="TEXT"),
        ]

        async def mock_process(chunk, job_id, voice, llm_sem, tts_sem):
            return AudioSegmentInfo(
                order=chunk.order,
                audio_path=str(tmp_path / f"seg_{chunk.order}.mp3"),
                section_id=chunk.section_id,
                success=True,
            )

        output_path = str(tmp_path / "job4" / "audio.mp3")

        with patch("pipeline.orchestrator.parse_document", return_value=elements), \
             patch("pipeline.orchestrator.chunk_elements", return_value=chunks), \
             patch("pipeline.orchestrator.classify_chunks", return_value=chunks), \
             patch("pipeline.orchestrator.process_chunk_pipeline", side_effect=mock_process), \
             patch("pipeline.orchestrator.stitch_audio", return_value=output_path), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)), \
             patch("pipeline.orchestrator.OUTPUTS_DIR", str(tmp_path)), \
             patch("os.path.getsize", return_value=5000000), \
             patch("pydub.AudioSegment.from_file") as mock_from_file:
            # Mock audio duration
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=120000)  # 120s
            mock_from_file.return_value = mock_audio

            result = await run_pipeline("job4", file_path, "pdf")

        assert result == output_path
        mock_db_for_orchestrator["complete_job"].assert_called_once()

    # ── TC-PIPE-005: Progress callback called at each stage ──
    @pytest.mark.asyncio
    async def test_progress_callback_called(self, tmp_path, mock_db_for_orchestrator):
        file_path = str(tmp_path / "test.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        progress_calls = []

        def track_progress(frac, msg):
            progress_calls.append((frac, msg))

        with patch("pipeline.orchestrator.parse_document", return_value=[]):
            await run_pipeline("job5", file_path, "pdf", progress_callback=track_progress)

        assert len(progress_calls) >= 2  # At least start and fail
        assert progress_calls[-1][0] == 1.0  # Final call should be 100%

    # ── TC-PIPE-006: asyncio.gather with return_exceptions=True ──
    @pytest.mark.asyncio
    async def test_gather_handles_exceptions(self, tmp_path, mock_db_for_orchestrator):
        """Exceptions from individual chunks should not crash the pipeline."""
        file_path = str(tmp_path / "test.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        elements = [DocumentElement(type=ElementType.PARAGRAPH, content="text", order=0)]
        chunks = [
            Chunk(chunk_id="c000", order=0, section_id="s0", word_count=5,
                  elements=elements, chunk_type="TEXT"),
            Chunk(chunk_id="c001", order=1, section_id="s0", word_count=5,
                  elements=elements, chunk_type="TEXT"),
        ]

        call_count = 0

        async def mock_process(chunk, job_id, voice, llm_sem, tts_sem):
            nonlocal call_count
            call_count += 1
            if chunk.order == 0:
                raise RuntimeError("Unexpected failure")
            return AudioSegmentInfo(
                order=chunk.order,
                audio_path=str(tmp_path / f"seg_{chunk.order}.mp3"),
                section_id=chunk.section_id,
                success=True,
            )

        with patch("pipeline.orchestrator.parse_document", return_value=elements), \
             patch("pipeline.orchestrator.chunk_elements", return_value=chunks), \
             patch("pipeline.orchestrator.classify_chunks", return_value=chunks), \
             patch("pipeline.orchestrator.process_chunk_pipeline", side_effect=mock_process), \
             patch("pipeline.orchestrator.stitch_audio", return_value=None), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)), \
             patch("pipeline.orchestrator.OUTPUTS_DIR", str(tmp_path)):
            # Should not raise despite exception in chunk 0
            result = await run_pipeline("job6", file_path, "pdf")

        assert call_count == 2  # Both chunks attempted

    # ── TC-PIPE-007: Stitch failure → fail_job ──
    @pytest.mark.asyncio
    async def test_stitch_failure(self, tmp_path, mock_db_for_orchestrator):
        file_path = str(tmp_path / "test.pdf")
        with open(file_path, "wb") as f:
            f.write(b"data")

        elements = [DocumentElement(type=ElementType.PARAGRAPH, content="text", order=0)]
        chunks = [
            Chunk(chunk_id="c000", order=0, section_id="s0", word_count=5,
                  elements=elements, chunk_type="TEXT"),
        ]

        async def mock_process(chunk, job_id, voice, llm_sem, tts_sem):
            return AudioSegmentInfo(order=0, audio_path="/tmp/seg.mp3", section_id="s0", success=True)

        with patch("pipeline.orchestrator.parse_document", return_value=elements), \
             patch("pipeline.orchestrator.chunk_elements", return_value=chunks), \
             patch("pipeline.orchestrator.classify_chunks", return_value=chunks), \
             patch("pipeline.orchestrator.process_chunk_pipeline", side_effect=mock_process), \
             patch("pipeline.orchestrator.stitch_audio", return_value=None), \
             patch("pipeline.orchestrator.PROCESSING_DIR", str(tmp_path)), \
             patch("pipeline.orchestrator.OUTPUTS_DIR", str(tmp_path)):
            result = await run_pipeline("job7", file_path, "pdf")

        assert result is None
        mock_db_for_orchestrator["fail_job"].assert_called()
