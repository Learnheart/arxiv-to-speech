"""
D2S Pipeline — AudioStitcher: concatenate audio segments, normalize, export final MP3.
"""
import os
from dataclasses import dataclass
from typing import Optional

from pydub import AudioSegment

from config import AUDIO_CONFIG
from logger import logger


@dataclass
class AudioSegmentInfo:
    order: int
    audio_path: str
    section_id: str
    success: bool = True


def stitch_audio(
    segments: list[AudioSegmentInfo],
    output_path: str,
) -> Optional[str]:
    """
    Concatenate audio segments into a single MP3 file.
    - Sort by order
    - Insert silence gaps (300ms same section, 800ms different section)
    - Normalize volume
    - Apply fade in/out
    - Export MP3 192kbps
    Returns output_path on success, None on failure.
    """
    if not segments:
        logger.error("No audio segments to stitch")
        return None

    # Sort by order
    segments.sort(key=lambda s: s.order)

    cfg = AUDIO_CONFIG
    gap_same = AudioSegment.silent(duration=cfg["gap_between_chunks_ms"])
    gap_section = AudioSegment.silent(duration=cfg["gap_between_sections_ms"])

    combined = AudioSegment.empty()
    prev_section_id = None
    loaded_count = 0

    for seg in segments:
        if not seg.success or not os.path.exists(seg.audio_path):
            # Failed chunk → insert 1 second silence as placeholder
            logger.warning("Segment %d missing/failed, inserting silence placeholder", seg.order)
            combined += AudioSegment.silent(duration=1000)
            prev_section_id = seg.section_id
            continue

        try:
            audio = AudioSegment.from_file(seg.audio_path)
        except Exception as e:
            logger.error("Failed to load segment %d (%s): %s", seg.order, seg.audio_path, e)
            combined += AudioSegment.silent(duration=1000)
            prev_section_id = seg.section_id
            continue

        # Insert gap
        if prev_section_id is not None:
            if seg.section_id != prev_section_id:
                combined += gap_section
            else:
                combined += gap_same

        combined += audio
        prev_section_id = seg.section_id
        loaded_count += 1

    if loaded_count == 0:
        logger.error("No segments loaded successfully")
        return None

    # Normalize to mono and target sample rate
    combined = combined.set_channels(cfg["channels"])
    combined = combined.set_frame_rate(cfg["sample_rate"])

    # Volume normalization (simplified LUFS approximation)
    target_dbfs = cfg["target_lufs"]  # -16 dBFS as proxy for -16 LUFS
    change_in_dbfs = target_dbfs - combined.dBFS
    combined = combined.apply_gain(change_in_dbfs)

    # Fade in/out
    combined = combined.fade_in(cfg["fade_in_ms"])
    combined = combined.fade_out(cfg["fade_out_ms"])

    # Export
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    combined.export(
        output_path,
        format=cfg["format"],
        bitrate=cfg["bitrate"],
    )

    duration_sec = len(combined) / 1000.0
    file_size = os.path.getsize(output_path)
    logger.info(
        "Audio stitched: %d segments → %s (%.1fs, %.1fMB)",
        loaded_count, output_path, duration_sec, file_size / 1024 / 1024,
    )
    return output_path
