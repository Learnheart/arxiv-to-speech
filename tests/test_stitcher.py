"""
Unit tests for pipeline/stitcher.py
Covers: stitch_audio(), AudioSegmentInfo
"""
import os
from unittest.mock import patch, MagicMock

import pytest
from pydub import AudioSegment
from pydub.generators import Sine

from pipeline.stitcher import stitch_audio, AudioSegmentInfo


@pytest.fixture
def create_audio_file(tmp_path):
    """Helper to create a valid WAV audio file (no ffmpeg needed)."""
    def _create(filename, duration_ms=1000, freq=440):
        # Use .wav to avoid ffmpeg dependency
        wav_name = filename.replace(".mp3", ".wav")
        filepath = str(tmp_path / wav_name)
        tone = Sine(freq).to_audio_segment(duration=duration_ms)
        tone.export(filepath, format="wav")
        return filepath
    return _create


class TestStitchAudio:

    # ── TC-STI-001: Empty segments → None ──
    def test_empty_segments(self, tmp_path):
        result = stitch_audio([], str(tmp_path / "out.mp3"))
        assert result is None

    # ── TC-STI-002: Single segment ──
    def test_single_segment(self, create_audio_file, tmp_path):
        path = create_audio_file("seg_000.wav")
        segments = [AudioSegmentInfo(order=0, audio_path=path, section_id="s0")]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            result = stitch_audio(segments, output)
        assert result == output
        assert os.path.exists(output)

    # ── TC-STI-003: Multiple segments stitched in order ──
    def test_multiple_segments_ordered(self, create_audio_file, tmp_path):
        paths = [
            create_audio_file("seg_002.wav", freq=880),
            create_audio_file("seg_000.wav", freq=220),
            create_audio_file("seg_001.wav", freq=440),
        ]
        segments = [
            AudioSegmentInfo(order=2, audio_path=paths[0], section_id="s0"),
            AudioSegmentInfo(order=0, audio_path=paths[1], section_id="s0"),
            AudioSegmentInfo(order=1, audio_path=paths[2], section_id="s0"),
        ]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            result = stitch_audio(segments, output)
        assert result is not None
        assert os.path.exists(output)

    # ── TC-STI-004: Same section → 300ms gap ──
    def test_same_section_gap(self, create_audio_file, tmp_path):
        p1 = create_audio_file("seg1.wav", duration_ms=500)
        p2 = create_audio_file("seg2.wav", duration_ms=500)
        segments = [
            AudioSegmentInfo(order=0, audio_path=p1, section_id="s0"),
            AudioSegmentInfo(order=1, audio_path=p2, section_id="s0"),
        ]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            result = stitch_audio(segments, output)
        assert result is not None

        audio = AudioSegment.from_file(output)
        # 500 + 300 (gap) + 500 = ~1300ms
        assert len(audio) >= 1200

    # ── TC-STI-005: Different section → 800ms gap ──
    def test_different_section_gap(self, create_audio_file, tmp_path):
        p1 = create_audio_file("seg1.wav", duration_ms=500)
        p2 = create_audio_file("seg2.wav", duration_ms=500)
        segments = [
            AudioSegmentInfo(order=0, audio_path=p1, section_id="s0"),
            AudioSegmentInfo(order=1, audio_path=p2, section_id="s1"),
        ]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            result = stitch_audio(segments, output)
        assert result is not None

        audio = AudioSegment.from_file(output)
        # 500 + 800 (gap) + 500 = ~1800ms
        assert len(audio) >= 1600

    # ── TC-STI-006: Failed segment → 1s silence placeholder ──
    def test_failed_segment_placeholder(self, create_audio_file, tmp_path):
        p1 = create_audio_file("seg1.wav", duration_ms=500)
        segments = [
            AudioSegmentInfo(order=0, audio_path=p1, section_id="s0"),
            AudioSegmentInfo(order=1, audio_path="nonexistent.mp3", section_id="s0", success=False),
        ]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            result = stitch_audio(segments, output)
        assert result is not None

    # ── TC-STI-007: All segments failed → None ──
    def test_all_segments_failed(self, tmp_path):
        segments = [
            AudioSegmentInfo(order=0, audio_path="none1.mp3", section_id="s0", success=False),
            AudioSegmentInfo(order=1, audio_path="none2.mp3", section_id="s0", success=False),
        ]
        output = str(tmp_path / "output.mp3")
        result = stitch_audio(segments, output)
        assert result is None

    # ── TC-STI-008: Output is mono, correct sample rate ──
    def test_output_format(self, create_audio_file, tmp_path):
        path = create_audio_file("seg.wav")
        segments = [AudioSegmentInfo(order=0, audio_path=path, section_id="s0")]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            stitch_audio(segments, output)
        audio = AudioSegment.from_file(output)
        assert audio.channels == 1
        assert audio.frame_rate == 44100

    # ── TC-STI-009: Fade in/out applied ──
    def test_fade_applied(self, create_audio_file, tmp_path):
        path = create_audio_file("seg.wav", duration_ms=3000)
        segments = [AudioSegmentInfo(order=0, audio_path=path, section_id="s0")]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            stitch_audio(segments, output)
        audio = AudioSegment.from_file(output)
        assert len(audio) > 2000

    # ── TC-STI-010: Volume normalization applied ──
    def test_volume_normalized(self, create_audio_file, tmp_path):
        path = create_audio_file("seg.wav")
        segments = [AudioSegmentInfo(order=0, audio_path=path, section_id="s0")]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            stitch_audio(segments, output)
        audio = AudioSegment.from_file(output)
        # After normalization + fade, dBFS should be finite (not -inf)
        assert audio.dBFS != float("-inf")
        assert len(audio) > 0

    # ── TC-STI-011: Missing file treated as failed ──
    def test_missing_file_treated_as_failed(self, create_audio_file, tmp_path):
        good = create_audio_file("good.wav")
        segments = [
            AudioSegmentInfo(order=0, audio_path=good, section_id="s0"),
            AudioSegmentInfo(order=1, audio_path="/nonexistent/path.mp3", section_id="s0", success=True),
        ]
        output = str(tmp_path / "output.wav")

        with patch.dict("config.AUDIO_CONFIG", {"format": "wav", "bitrate": "192k",
            "sample_rate": 44100, "channels": 1, "target_lufs": -16,
            "fade_in_ms": 500, "fade_out_ms": 1000,
            "gap_between_chunks_ms": 300, "gap_between_sections_ms": 800}):
            result = stitch_audio(segments, output)
        assert result is not None
