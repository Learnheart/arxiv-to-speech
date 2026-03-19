"""
D2S Pipeline — Orchestrator: run the 6-stage pipeline.
1. Upload & Validate (handled by UI/caller)
2. Parse document
3. Chunk by headings
4. Classify chunks
5. Enrich (LLM) + Synthesize (TTS) — concurrent via asyncio.gather
6. Stitch audio segments
"""
import asyncio
import os
from typing import Callable, Optional

from config import CONCURRENCY_CONFIG, PROCESSING_DIR, OUTPUTS_DIR
from db.models import complete_job, fail_job, update_job
from logger import logger
from pipeline.chunker import Chunk, chunk_elements
from pipeline.classifier import ChunkType, classify_chunks
from pipeline.enricher import enrich_chunk
from pipeline.parser import parse_document
from pipeline.stitcher import AudioSegmentInfo, stitch_audio
from pipeline.synthesizer import synthesize_text


ProgressCallback = Optional[Callable[[float, str], None]]


async def process_chunk_pipeline(
    chunk: Chunk,
    job_id: str,
    voice: str,
    llm_semaphore: asyncio.Semaphore,
    tts_semaphore: asyncio.Semaphore,
) -> AudioSegmentInfo:
    """Process a single chunk: enrich → TTS. Returns AudioSegmentInfo."""
    seg_path = os.path.join(PROCESSING_DIR, job_id, f"seg_{chunk.order:03d}.mp3")

    try:
        # Phase 1: Enrich
        enriched_text = await enrich_chunk(chunk, llm_semaphore)

        if not enriched_text or not enriched_text.strip():
            logger.warning("Chunk %s produced empty text after enrichment", chunk.chunk_id)
            return AudioSegmentInfo(
                order=chunk.order,
                audio_path=seg_path,
                section_id=chunk.section_id,
                success=False,
            )

        # Phase 2: TTS
        success = await synthesize_text(
            text=enriched_text,
            output_path=seg_path,
            voice=voice,
            tts_semaphore=tts_semaphore,
        )

        return AudioSegmentInfo(
            order=chunk.order,
            audio_path=seg_path,
            section_id=chunk.section_id,
            success=success,
        )

    except Exception as e:
        logger.error("Failed to process chunk %s: %s", chunk.chunk_id, e)
        return AudioSegmentInfo(
            order=chunk.order,
            audio_path=seg_path,
            section_id=chunk.section_id,
            success=False,
        )


async def run_pipeline(
    job_id: str,
    file_path: str,
    file_type: str,
    voice: str = "vi-VN-HoaiMyNeural",
    progress_callback: ProgressCallback = None,
):
    """
    Run the full D2S pipeline for a job.
    progress_callback(fraction: float, message: str) is called at each stage.
    """
    def _progress(frac: float, msg: str):
        if progress_callback:
            progress_callback(frac, msg)
        logger.info("[Job %s] %.0f%% - %s", job_id, frac * 100, msg)

    try:
        # ── Stage 2: Parse ──
        _progress(0.1, "Dang parse document...")
        with open(file_path, "rb") as f:
            file_bytes = f.read()
        elements = parse_document(file_bytes, file_type)

        if not elements:
            fail_job(job_id, "Khong the parse noi dung tu document.")
            _progress(1.0, "That bai: khong co noi dung.")
            return None

        # ── Stage 3: Chunk ──
        _progress(0.2, "Dang tach chunks...")
        chunks = chunk_elements(elements)

        if not chunks:
            fail_job(job_id, "Khong tach duoc chunk nao.")
            _progress(1.0, "That bai: khong co chunk.")
            return None

        # ── Stage 4: Classify ──
        _progress(0.25, "Dang phan loai chunks...")
        chunks = classify_chunks(chunks)

        update_job(job_id, chunks_total=len(chunks))

        # ── Stage 5+6: Enrich + TTS (concurrent) ──
        _progress(0.3, f"Xu ly {len(chunks)} chunks song song...")

        # Create processing directory
        os.makedirs(os.path.join(PROCESSING_DIR, job_id), exist_ok=True)

        llm_sem = asyncio.Semaphore(CONCURRENCY_CONFIG["llm_semaphore"])
        tts_sem = asyncio.Semaphore(CONCURRENCY_CONFIG["tts_semaphore"])

        # Fan-out: process all chunks concurrently
        tasks = [
            process_chunk_pipeline(chunk, job_id, voice, llm_sem, tts_sem)
            for chunk in chunks
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions that escaped process_chunk_pipeline
        results: list[AudioSegmentInfo] = []
        for i, r in enumerate(raw_results):
            if isinstance(r, BaseException):
                logger.error("Chunk %s raised exception: %s", chunks[i].chunk_id, r)
                results.append(AudioSegmentInfo(
                    order=chunks[i].order,
                    audio_path=os.path.join(PROCESSING_DIR, job_id, f"seg_{chunks[i].order:03d}.mp3"),
                    section_id=chunks[i].section_id,
                    success=False,
                ))
            else:
                results.append(r)

        chunks_failed = sum(1 for r in results if not r.success)
        _progress(0.85, f"{len(chunks)}/{len(chunks)} chunks hoan tat ({chunks_failed} that bai)")

        # Check failure threshold
        if len(chunks) > 0 and chunks_failed / len(chunks) >= 0.2:
            fail_job(job_id, f"Qua nhieu chunks that bai: {chunks_failed}/{len(chunks)}")
            _progress(1.0, "That bai: qua nhieu loi.")
            return None

        # ── Stage 7: Stitch ──
        _progress(0.9, "Dang ghep audio cuoi cung...")
        output_dir = os.path.join(OUTPUTS_DIR, job_id)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "audio.mp3")

        final_path = stitch_audio(results, output_path)

        if not final_path:
            fail_job(job_id, "Khong the ghep audio.")
            _progress(1.0, "That bai: loi ghep audio.")
            return None

        # Update job as completed
        audio_size = os.path.getsize(final_path)
        from pydub import AudioSegment as PydubSegment
        audio = PydubSegment.from_file(final_path)
        audio_duration = len(audio) / 1000.0

        complete_job(
            job_id=job_id,
            audio_path=final_path,
            audio_duration=audio_duration,
            audio_size=audio_size,
            chunks_total=len(chunks),
            chunks_failed=chunks_failed,
        )

        _progress(1.0, "Hoan tat!")
        logger.info(
            "Pipeline completed for job %s: %d chunks, %.1fs audio, %.1fMB",
            job_id, len(chunks), audio_duration, audio_size / 1024 / 1024,
        )
        return final_path

    except Exception as e:
        logger.exception("Pipeline failed for job %s: %s", job_id, e)
        fail_job(job_id, str(e))
        _progress(1.0, f"That bai: {e}")
        return None
