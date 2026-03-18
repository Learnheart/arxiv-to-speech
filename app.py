"""
D2S Pipeline — Entry point: Gradio UI.
python app.py → http://localhost:7860
"""
import asyncio
import os
import shutil
import threading

import gradio as gr

from config import (
    DATA_DIR, UPLOADS_DIR, PROCESSING_DIR, OUTPUTS_DIR,
    CACHE_DIR, TTS_CACHE_DIR, VOICE_OPTIONS,
)
from db.models import (
    init_db, create_job, get_job, get_recent_jobs, fail_job,
)
from logger import logger
from pipeline.orchestrator import run_pipeline
from utils.cache import cache_cleanup
from utils.downloader import download_file, DownloadError
from utils.validator import validate_file


# Ensure directories exist
for d in [DATA_DIR, UPLOADS_DIR, PROCESSING_DIR, OUTPUTS_DIR, CACHE_DIR, TTS_CACHE_DIR]:
    os.makedirs(d, exist_ok=True)

# Initialize database
init_db()


def _run_pipeline_in_thread(job_id, file_path, file_type, voice, progress):
    """Run the async pipeline in a new event loop inside a thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def progress_callback(frac, msg):
        try:
            progress(frac, desc=msg)
        except Exception:
            pass

    try:
        result = loop.run_until_complete(
            run_pipeline(job_id, file_path, file_type, voice, progress_callback)
        )
        return result
    finally:
        loop.close()


def process_upload(file, voice, progress=gr.Progress()):
    """Handle file upload and run pipeline."""
    if file is None:
        gr.Warning("Vui long chon file.")
        return None, "Chua chon file."

    progress(0.02, desc="Dang validate file...")

    # Read file bytes
    with open(file.name, "rb") as f:
        file_bytes = f.read()

    filename = os.path.basename(file.name)
    validation = validate_file(file_bytes, filename)

    if not validation.valid:
        gr.Warning(validation.error)
        return None, validation.error

    # Save to uploads directory
    import uuid
    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOADS_DIR, job_id)
    os.makedirs(upload_dir, exist_ok=True)
    saved_path = os.path.join(upload_dir, f"original.{validation.file_type}")
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # Create job in DB
    job_id_db = create_job(
        file_path=saved_path,
        file_type=validation.file_type,
        file_size_bytes=validation.file_size,
        tts_voice=voice,
        source_type="upload",
    )
    # Overwrite job_id if DB generated a different one
    if job_id_db != job_id:
        new_dir = os.path.join(UPLOADS_DIR, job_id_db)
        os.rename(upload_dir, new_dir)
        saved_path = os.path.join(new_dir, f"original.{validation.file_type}")
        # Update DB path
        from db.models import update_job
        update_job(job_id_db, file_path=saved_path)
        job_id = job_id_db

    progress(0.05, desc="Khoi tao pipeline...")
    logger.info("Starting pipeline for job %s (file: %s)", job_id, filename)

    # Run pipeline
    result = _run_pipeline_in_thread(job_id, saved_path, validation.file_type, voice, progress)

    if result and os.path.exists(result):
        job = get_job(job_id)
        stats = _format_stats(job)
        return result, stats
    else:
        job = get_job(job_id)
        error = job.get("error_message", "Loi khong xac dinh") if job else "Loi khong xac dinh"
        return None, f"That bai: {error}"


def process_url(url, voice, progress=gr.Progress()):
    """Handle URL input: download → validate → pipeline."""
    if not url or not url.strip():
        gr.Warning("Vui long nhap URL.")
        return None, "Chua nhap URL."

    url = url.strip()
    progress(0.02, desc="Dang tai file tu URL...")

    # Download
    loop = asyncio.new_event_loop()
    try:
        file_bytes, filename = loop.run_until_complete(download_file(url))
    except DownloadError as e:
        gr.Warning(str(e))
        return None, str(e)
    except Exception as e:
        gr.Warning(f"Loi tai file: {e}")
        return None, f"Loi tai file: {e}"
    finally:
        loop.close()

    progress(0.04, desc="Dang validate file...")

    validation = validate_file(file_bytes, filename)
    if not validation.valid:
        gr.Warning(validation.error)
        return None, validation.error

    # Save to uploads
    import uuid
    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(UPLOADS_DIR, job_id)
    os.makedirs(upload_dir, exist_ok=True)
    saved_path = os.path.join(upload_dir, f"original.{validation.file_type}")
    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    # Create job
    job_id_db = create_job(
        file_path=saved_path,
        file_type=validation.file_type,
        file_size_bytes=validation.file_size,
        tts_voice=voice,
        source_type="url",
        source_url=url,
    )
    if job_id_db != job_id:
        new_dir = os.path.join(UPLOADS_DIR, job_id_db)
        os.rename(upload_dir, new_dir)
        saved_path = os.path.join(new_dir, f"original.{validation.file_type}")
        from db.models import update_job
        update_job(job_id_db, file_path=saved_path)
        job_id = job_id_db

    progress(0.05, desc="Khoi tao pipeline...")
    logger.info("Starting pipeline for job %s (url: %s)", job_id, url)

    result = _run_pipeline_in_thread(job_id, saved_path, validation.file_type, voice, progress)

    if result and os.path.exists(result):
        job = get_job(job_id)
        stats = _format_stats(job)
        return result, stats
    else:
        job = get_job(job_id)
        error = job.get("error_message", "Loi khong xac dinh") if job else "Loi khong xac dinh"
        return None, f"That bai: {error}"


def _format_stats(job: dict | None) -> str:
    """Format job stats for display."""
    if not job:
        return "Khong co thong tin."

    status = job.get("status", "unknown")
    chunks_total = job.get("chunks_total", 0)
    chunks_failed = job.get("chunks_failed", 0)
    duration = job.get("audio_duration", 0) or 0
    size = job.get("audio_size", 0) or 0
    cost = job.get("estimated_cost", 0) or 0

    minutes = int(duration // 60)
    seconds = int(duration % 60)
    size_mb = size / 1024 / 1024

    status_emoji = {"completed": "OK", "partial_failure": "WARN", "failed": "FAIL"}.get(status, "?")

    return (
        f"Trang thai: {status_emoji} {status}\n"
        f"Chunks: {chunks_total - chunks_failed}/{chunks_total} thanh cong\n"
        f"Thoi luong: {minutes}:{seconds:02d}\n"
        f"Dung luong: {size_mb:.1f}MB\n"
        f"Engine: edge-tts | Voice: {job.get('tts_voice', 'N/A')}"
    )


def get_history():
    """Get recent jobs for history display."""
    jobs = get_recent_jobs(20)
    if not jobs:
        return "Chua co lich su."

    lines = []
    for j in jobs:
        status = j.get("status", "?")
        emoji = {"completed": "[OK]", "partial_failure": "[WARN]", "processing": "[...]", "failed": "[FAIL]"}.get(status, "[?]")
        duration = j.get("audio_duration", 0) or 0
        size = (j.get("audio_size", 0) or 0) / 1024 / 1024
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        created = j.get("created_at", "")[:16]
        lines.append(f"{emoji} {created} | {minutes}:{seconds:02d} | {size:.1f}MB | {j.get('file_type', '?')}")

    return "\n".join(lines)


# ── Build Gradio UI ──

def build_ui():
    voice_choices = list(VOICE_OPTIONS.keys())
    voice_labels = list(VOICE_OPTIONS.values())

    with gr.Blocks(
        title="Document-to-Speech Pipeline",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown("# Document-to-Speech Pipeline\nChuyen doi tai lieu DOCX/PDF thanh audio MP3.")

        with gr.Row():
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.Tab("Upload File"):
                        file_input = gr.File(
                            label="Upload DOCX/PDF",
                            file_types=[".docx", ".pdf"],
                            type="filepath",
                        )
                        btn_upload = gr.Button("Bat dau xu ly", variant="primary")

                    with gr.Tab("Dan URL"):
                        url_input = gr.Textbox(
                            label="URL toi file DOCX/PDF",
                            placeholder="https://drive.google.com/file/d/.../view",
                        )
                        btn_url = gr.Button("Tai va xu ly", variant="primary")

                voice_dropdown = gr.Dropdown(
                    choices=voice_choices,
                    value=voice_choices[0],
                    label="Giong doc",
                )

            with gr.Column(scale=3):
                audio_output = gr.Audio(label="Audio output", type="filepath")
                stats_output = gr.Textbox(label="Thong tin", lines=5, interactive=False)

        with gr.Accordion("Lich su", open=False):
            history_output = gr.Textbox(label="Cac job gan day", lines=10, interactive=False)
            btn_refresh = gr.Button("Lam moi", size="sm")

        # Event handlers
        btn_upload.click(
            fn=process_upload,
            inputs=[file_input, voice_dropdown],
            outputs=[audio_output, stats_output],
        )

        btn_url.click(
            fn=process_url,
            inputs=[url_input, voice_dropdown],
            outputs=[audio_output, stats_output],
        )

        btn_refresh.click(fn=get_history, outputs=[history_output])

        # Load history on start
        app.load(fn=get_history, outputs=[history_output])

    return app


if __name__ == "__main__":
    # Cleanup expired cache on startup
    cache_cleanup()

    logger.info("Starting D2S Pipeline UI...")
    app = build_ui()
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
    )
