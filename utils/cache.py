"""
D2S Pipeline — SQLite-based cache for LLM and TTS results.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from config import LLM_CACHE_TTL_DAYS, TTS_CACHE_TTL_DAYS
from db.models import get_connection
from logger import logger


def _hash_key(*parts: str) -> str:
    """SHA256 hash of concatenated parts."""
    combined = "|".join(str(p) for p in parts)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def cache_get(cache_type: str, *key_parts: str) -> Optional[str]:
    """Look up cache. Returns result string or None if miss/expired."""
    h = _hash_key(*key_parts)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT result FROM cache WHERE hash = ? AND type = ? AND expires_at > datetime('now')",
            (h, cache_type),
        ).fetchone()
        if row:
            logger.debug("Cache HIT [%s] %s", cache_type, h[:12])
            return row["result"]
        return None
    finally:
        conn.close()


def cache_set(cache_type: str, result: str, *key_parts: str):
    """Insert or replace a cache entry."""
    h = _hash_key(*key_parts)
    ttl_days = LLM_CACHE_TTL_DAYS if cache_type == "llm" else TTS_CACHE_TTL_DAYS
    expires = (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cache (hash, type, result, expires_at) VALUES (?, ?, ?, ?)",
            (h, cache_type, result, expires),
        )
        conn.commit()
        logger.debug("Cache SET [%s] %s (TTL=%dd)", cache_type, h[:12], ttl_days)
    finally:
        conn.close()


def cache_cleanup():
    """Delete expired entries."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM cache WHERE expires_at < datetime('now')")
        conn.commit()
        if cursor.rowcount > 0:
            logger.info("Cache cleanup: removed %d expired entries", cursor.rowcount)
    finally:
        conn.close()
