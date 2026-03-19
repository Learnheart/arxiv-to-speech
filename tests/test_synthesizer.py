"""
Unit tests for pipeline/synthesizer.py
Covers: synthesize_text(), _split_sentences()
"""
import asyncio
import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from pipeline.synthesizer import synthesize_text, _split_sentences


# ══════════════════════════════════════════════════════════
# TC-SPLIT: _split_sentences()
# ══════════════════════════════════════════════════════════

class TestSplitSentences:

    def test_short_text_no_split(self):
        result = _split_sentences("Hello world.", max_chars=100)
        assert len(result) == 1
        assert result[0] == "Hello world."

    def test_split_at_sentence_boundaries(self):
        text = "Sentence one. Sentence two. Sentence three."
        result = _split_sentences(text, max_chars=30)
        assert len(result) >= 2

    def test_long_single_sentence(self):
        text = "A" * 5000  # One long "sentence"
        result = _split_sentences(text, max_chars=4500)
        # Should return as-is since there's no sentence boundary
        assert len(result) == 1

    def test_vietnamese_sentences(self):
        text = "Câu một. Câu hai. Câu ba."
        result = _split_sentences(text, max_chars=20)
        assert len(result) >= 2

    def test_empty_text(self):
        result = _split_sentences("", max_chars=100)
        assert result == [""]

    def test_preserves_all_content(self):
        text = "First sentence. Second sentence. Third sentence."
        segments = _split_sentences(text, max_chars=30)
        reassembled = " ".join(segments)
        for word in ["First", "Second", "Third"]:
            assert word in reassembled


# ══════════════════════════════════════════════════════════
# TC-TTS: synthesize_text()
# ══════════════════════════════════════════════════════════

class TestSynthesizeText:

    # ── TC-TTS-001: Empty text returns False ──
    @pytest.mark.asyncio
    async def test_empty_text(self, tmp_path):
        result = await synthesize_text("", str(tmp_path / "out.mp3"))
        assert result is False

    @pytest.mark.asyncio
    async def test_whitespace_only(self, tmp_path):
        result = await synthesize_text("   \n  ", str(tmp_path / "out.mp3"))
        assert result is False

    # ── TC-TTS-002: Successful synthesis (mocked edge-tts) ──
    @pytest.mark.asyncio
    async def test_successful_synthesis(self, tmp_path):
        output_path = str(tmp_path / "output.mp3")

        mock_communicate = MagicMock()

        async def mock_stream():
            yield {"type": "audio", "data": b"\xff\xfb\x90\x00" * 100}
            yield {"type": "WordBoundary", "data": {}}

        mock_communicate.stream = mock_stream

        with patch("pipeline.synthesizer.edge_tts.Communicate", return_value=mock_communicate), \
             patch("pipeline.synthesizer.cache_get", return_value=None), \
             patch("pipeline.synthesizer.cache_set"):
            result = await synthesize_text("Hello world", output_path)

        assert result is True
        assert os.path.exists(output_path)

    # ── TC-TTS-003: Cache hit copies cached file ──
    @pytest.mark.asyncio
    async def test_cache_hit(self, tmp_path):
        # Create a "cached" file
        cached_file = str(tmp_path / "cached.mp3")
        with open(cached_file, "wb") as f:
            f.write(b"cached audio data")

        output_path = str(tmp_path / "output.mp3")

        with patch("pipeline.synthesizer.cache_get", return_value=cached_file):
            result = await synthesize_text("Some text", output_path)

        assert result is True
        assert os.path.exists(output_path)
        with open(output_path, "rb") as f:
            assert f.read() == b"cached audio data"

    # ── TC-TTS-004: Semaphore used when provided ──
    @pytest.mark.asyncio
    async def test_uses_semaphore(self, tmp_path):
        sem = asyncio.Semaphore(1)
        output_path = str(tmp_path / "output.mp3")

        mock_communicate = MagicMock()

        async def mock_stream():
            yield {"type": "audio", "data": b"\xff\xfb\x90\x00" * 10}

        mock_communicate.stream = mock_stream

        with patch("pipeline.synthesizer.edge_tts.Communicate", return_value=mock_communicate), \
             patch("pipeline.synthesizer.cache_get", return_value=None), \
             patch("pipeline.synthesizer.cache_set"):
            result = await synthesize_text("Test", output_path, tts_semaphore=sem)

        assert result is True

    # ── TC-TTS-005: Empty audio from TTS engine returns False ──
    @pytest.mark.asyncio
    async def test_empty_audio_returns_false(self, tmp_path):
        output_path = str(tmp_path / "output.mp3")

        mock_communicate = MagicMock()

        async def mock_stream():
            # No audio chunks, only metadata
            yield {"type": "WordBoundary", "data": {}}

        mock_communicate.stream = mock_stream

        with patch("pipeline.synthesizer.edge_tts.Communicate", return_value=mock_communicate), \
             patch("pipeline.synthesizer.cache_get", return_value=None):
            result = await synthesize_text("Test", output_path)

        assert result is False

    # ── TC-TTS-006: Long text triggers sentence splitting ──
    @pytest.mark.asyncio
    async def test_long_text_split(self, tmp_path):
        output_path = str(tmp_path / "output.mp3")
        long_text = "Sentence. " * 1000  # >5000 chars

        mock_communicate = MagicMock()

        async def mock_stream():
            yield {"type": "audio", "data": b"\xff\xfb\x90\x00" * 10}

        mock_communicate.stream = mock_stream

        with patch("pipeline.synthesizer.edge_tts.Communicate", return_value=mock_communicate) as mock_cls, \
             patch("pipeline.synthesizer.cache_get", return_value=None), \
             patch("pipeline.synthesizer.cache_set"):
            result = await synthesize_text(long_text, output_path)

        assert result is True
        # Communicate should be called multiple times (one per segment)
        assert mock_cls.call_count >= 2

    # ── TC-TTS-007: Custom voice parameter ──
    @pytest.mark.asyncio
    async def test_custom_voice(self, tmp_path):
        output_path = str(tmp_path / "output.mp3")

        mock_communicate = MagicMock()

        async def mock_stream():
            yield {"type": "audio", "data": b"\xff\xfb\x90\x00" * 10}

        mock_communicate.stream = mock_stream

        with patch("pipeline.synthesizer.edge_tts.Communicate", return_value=mock_communicate) as mock_cls, \
             patch("pipeline.synthesizer.cache_get", return_value=None), \
             patch("pipeline.synthesizer.cache_set"):
            await synthesize_text("Test", output_path, voice="vi-VN-NamMinhNeural")

        # Verify custom voice was used
        call_args = mock_cls.call_args
        # Check both positional and keyword arguments
        all_args = str(call_args)
        assert "vi-VN-NamMinhNeural" in all_args
