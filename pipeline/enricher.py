"""
D2S Pipeline — LLMEnricher: enrich IMAGE/TABLE/MIXED chunks via Groq LLM.
TEXT chunks are cleaned directly without LLM.
"""
import asyncio
from io import BytesIO

from PIL import Image

from logger import logger
from llm.groq_client import describe_image, narrate_table
from pipeline.chunker import Chunk
from pipeline.classifier import ChunkType
from pipeline.parser import ElementType
from utils.cache import cache_get, cache_set
from utils.text_cleaner import clean_for_tts, table_to_markdown


def _resize_image(image_bytes: bytes, max_size: int = 1024) -> bytes:
    """Resize image to max dimension, keeping aspect ratio. Returns PNG bytes."""
    img = Image.open(BytesIO(image_bytes))
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def enrich_chunk(chunk: Chunk, llm_semaphore: asyncio.Semaphore) -> str:
    """
    Enrich a single chunk and return the final text for TTS.
    - TEXT chunks: clean directly (no LLM, no semaphore needed).
    - IMAGE/TABLE/MIXED: use LLM with semaphore for rate limiting.
    """
    if chunk.chunk_type == ChunkType.TEXT:
        # No LLM needed — just clean and concatenate text
        parts = []
        for el in chunk.elements:
            if el.content:
                parts.append(el.content)
        return clean_for_tts("\n".join(parts))

    # Non-text chunks need LLM enrichment
    enriched_parts = []

    for el in chunk.elements:
        if el.type == ElementType.HEADING or el.type == ElementType.PARAGRAPH:
            if el.content:
                enriched_parts.append(clean_for_tts(el.content))

        elif el.type == ElementType.IMAGE and el.image_bytes:
            async with llm_semaphore:
                # Check cache
                import hashlib
                img_hash = hashlib.sha256(el.image_bytes).hexdigest()
                cached = cache_get("llm", "image", img_hash)
                if cached:
                    enriched_parts.append(cached)
                else:
                    resized = _resize_image(el.image_bytes)
                    description = await describe_image(resized)
                    cache_set("llm", description, "image", img_hash)
                    enriched_parts.append(description)

        elif el.type == ElementType.TABLE and el.table_data:
            async with llm_semaphore:
                table_md = table_to_markdown(el.table_data)
                cached = cache_get("llm", "table", table_md)
                if cached:
                    enriched_parts.append(cached)
                else:
                    narration = await narrate_table(table_md)
                    cache_set("llm", narration, "table", table_md)
                    enriched_parts.append(narration)

    result = "\n".join(enriched_parts)
    logger.debug("Enriched chunk %s (%s): %d chars", chunk.chunk_id, chunk.chunk_type, len(result))
    return result
