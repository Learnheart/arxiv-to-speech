"""
D2S Pipeline — TTSSynthesizer: convert text to speech using Edge TTS.
"""
import asyncio
import os
import tempfile

import edge_tts

from config import TTS_CONFIG, TTS_CACHE_DIR
from logger import logger
from utils.cache import cache_get, cache_set


async def synthesize_text(
    text: str,
    output_path: str,
    voice: str | None = None,
    tts_semaphore: asyncio.Semaphore | None = None,
) -> bool:
    """
    Synthesize text to MP3 file.
    Returns True on success, False on failure.
    """
    if not text or not text.strip():
        logger.warning("Empty text for TTS, skipping")
        return False

    voice = voice or TTS_CONFIG["voice"]

    async def _do_tts():
        # Check cache
        cached_path = cache_get("tts", text, voice)
        if cached_path and os.path.exists(cached_path):
            # Copy cached file to output
            import shutil
            shutil.copy2(cached_path, output_path)
            logger.debug("TTS cache hit, copied %s → %s", cached_path, output_path)
            return True

        # Split long text at sentence boundaries if needed
        if len(text) > 5000:
            segments = _split_sentences(text, max_chars=4500)
        else:
            segments = [text]

        all_audio = b""
        for seg in segments:
            communicate = edge_tts.Communicate(
                text=seg,
                voice=voice,
                rate=TTS_CONFIG["rate"],
                volume=TTS_CONFIG["volume"],
            )
            audio_bytes = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]
            all_audio += audio_bytes

        if not all_audio:
            logger.error("Edge TTS returned empty audio for text: %s...", text[:50])
            return False

        # Write to output
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(all_audio)

        # Save to cache
        os.makedirs(TTS_CACHE_DIR, exist_ok=True)
        import hashlib
        cache_hash = hashlib.sha256(f"{text}|{voice}".encode()).hexdigest()
        cache_path = os.path.join(TTS_CACHE_DIR, f"{cache_hash}.mp3")
        with open(cache_path, "wb") as f:
            f.write(all_audio)
        cache_set("tts", cache_path, text, voice)

        logger.debug("TTS synthesized %d chars → %s (%d bytes)", len(text), output_path, len(all_audio))
        return True

    # Use semaphore if provided
    if tts_semaphore:
        async with tts_semaphore:
            return await _do_tts()
    else:
        return await _do_tts()


def _split_sentences(text: str, max_chars: int = 4500) -> list[str]:
    """Split text into segments at sentence boundaries."""
    import re
    sentences = re.split(r'(?<=[.!?。])\s+', text)
    segments = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars and current:
            segments.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence

    if current.strip():
        segments.append(current.strip())

    return segments if segments else [text]
