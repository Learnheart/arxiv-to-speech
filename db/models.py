"""
D2S Pipeline — SQLite database: schema creation + CRUD operations.
"""
import sqlite3
import uuid
from datetime import datetime
from typing import Optional

from config import DB_PATH
from logger import logger


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id              TEXT PRIMARY KEY,
                status          TEXT NOT NULL DEFAULT 'processing',
                source_type     TEXT NOT NULL DEFAULT 'upload',
                source_url      TEXT,
                file_path       TEXT NOT NULL,
                file_type       TEXT NOT NULL,
                file_size_bytes INTEGER,
                chunks_total    INTEGER DEFAULT 0,
                chunks_failed   INTEGER DEFAULT 0,
                audio_path      TEXT,
                audio_duration  REAL,
                audio_size      INTEGER,
                tts_voice       TEXT DEFAULT 'vi-VN-HoaiMyNeural',
                estimated_cost  REAL DEFAULT 0,
                error_message   TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                completed_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS cache (
                hash        TEXT PRIMARY KEY,
                type        TEXT NOT NULL,
                result      TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                expires_at  TEXT NOT NULL
            );
        """)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    finally:
        conn.close()


# ── Job CRUD ──

def create_job(
    file_path: str,
    file_type: str,
    file_size_bytes: int,
    tts_voice: str = "vi-VN-HoaiMyNeural",
    source_type: str = "upload",
    source_url: Optional[str] = None,
) -> str:
    """Insert a new job record, return job_id."""
    job_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO jobs (id, status, source_type, source_url, file_path,
               file_type, file_size_bytes, tts_voice)
               VALUES (?, 'processing', ?, ?, ?, ?, ?, ?)""",
            (job_id, source_type, source_url, file_path, file_type,
             file_size_bytes, tts_voice),
        )
        conn.commit()
        logger.info("Job created: %s (type=%s, size=%d)", job_id, file_type, file_size_bytes)
    finally:
        conn.close()
    return job_id


def update_job(job_id: str, **kwargs):
    """Update job fields by keyword arguments."""
    if not kwargs:
        return
    columns = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    conn = get_connection()
    try:
        conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_recent_jobs(limit: int = 20) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def complete_job(
    job_id: str,
    audio_path: str,
    audio_duration: float,
    audio_size: int,
    chunks_total: int,
    chunks_failed: int,
    estimated_cost: float = 0.0,
):
    """Mark job as completed or partial_failure."""
    fail_ratio = chunks_failed / max(chunks_total, 1)
    if fail_ratio >= 0.2:
        status = "failed"
    elif chunks_failed > 0:
        status = "partial_failure"
    else:
        status = "completed"

    update_job(
        job_id,
        status=status,
        audio_path=audio_path,
        audio_duration=audio_duration,
        audio_size=audio_size,
        chunks_total=chunks_total,
        chunks_failed=chunks_failed,
        estimated_cost=estimated_cost,
        completed_at=datetime.utcnow().isoformat(),
    )
    logger.info("Job %s → %s (failed=%d/%d)", job_id, status, chunks_failed, chunks_total)


def fail_job(job_id: str, error_message: str):
    update_job(
        job_id,
        status="failed",
        error_message=error_message,
        completed_at=datetime.utcnow().isoformat(),
    )
    logger.error("Job %s FAILED: %s", job_id, error_message)
