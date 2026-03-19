"""
Unit tests for utils/cache.py
Covers: _hash_key(), cache_get(), cache_set(), cache_cleanup()
"""
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from utils.cache import _hash_key, cache_get, cache_set, cache_cleanup


# ══════════════════════════════════════════════════════════
# TC-HASH: _hash_key()
# ══════════════════════════════════════════════════════════

class TestHashKey:

    def test_deterministic(self):
        assert _hash_key("a", "b") == _hash_key("a", "b")

    def test_different_inputs_different_hashes(self):
        assert _hash_key("a", "b") != _hash_key("a", "c")

    def test_order_matters(self):
        assert _hash_key("a", "b") != _hash_key("b", "a")

    def test_single_part(self):
        h = _hash_key("hello")
        assert len(h) == 64  # SHA256 hex length

    def test_empty_parts(self):
        h = _hash_key("", "")
        assert len(h) == 64

    def test_unicode_parts(self):
        h = _hash_key("Thành phố", "Hồ Chí Minh")
        assert len(h) == 64


# ══════════════════════════════════════════════════════════
# TC-CACHE: cache_get / cache_set / cache_cleanup
# ══════════════════════════════════════════════════════════

class TestCacheOperations:

    @pytest.fixture(autouse=True)
    def setup_mock_db(self, tmp_db):
        """Patch get_connection to use temp database."""
        def _get_conn():
            conn = sqlite3.connect(tmp_db)
            conn.row_factory = sqlite3.Row
            return conn
        self._patcher = patch("utils.cache.get_connection", side_effect=_get_conn)
        self._patcher.start()
        yield
        self._patcher.stop()

    # ── TC-CACHE-001: Set then get ──
    def test_set_and_get(self):
        cache_set("llm", "result_text", "key1", "key2")
        result = cache_get("llm", "key1", "key2")
        assert result == "result_text"

    # ── TC-CACHE-002: Cache miss ──
    def test_cache_miss(self):
        result = cache_get("llm", "nonexistent", "key")
        assert result is None

    # ── TC-CACHE-003: Different cache types with different keys ──
    def test_different_types_different_keys(self):
        cache_set("llm", "llm_result", "llm_key_unique")
        cache_set("tts", "tts_result", "tts_key_unique")
        assert cache_get("llm", "llm_key_unique") == "llm_result"
        assert cache_get("tts", "tts_key_unique") == "tts_result"

    # ── TC-CACHE-004: Overwrite existing entry ──
    def test_overwrite_entry(self):
        cache_set("llm", "old_value", "key1")
        cache_set("llm", "new_value", "key1")
        assert cache_get("llm", "key1") == "new_value"

    # ── TC-CACHE-005: Expired entry returns None ──
    def test_expired_entry(self, tmp_db):
        # Manually insert expired entry
        h = _hash_key("expired_key")
        conn = sqlite3.connect(tmp_db)
        expired = (datetime.utcnow() - timedelta(days=1)).isoformat()
        conn.execute(
            "INSERT INTO cache (hash, type, result, expires_at) VALUES (?, ?, ?, ?)",
            (h, "llm", "old_data", expired),
        )
        conn.commit()
        conn.close()

        result = cache_get("llm", "expired_key")
        assert result is None

    # ── TC-CACHE-006: Cleanup removes expired entries ──
    def test_cleanup_removes_expired(self, tmp_db):
        # Insert one valid and one expired
        conn = sqlite3.connect(tmp_db)
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        past = (datetime.utcnow() - timedelta(days=1)).isoformat()
        conn.execute(
            "INSERT INTO cache (hash, type, result, expires_at) VALUES (?, ?, ?, ?)",
            ("valid_hash", "llm", "valid", future),
        )
        conn.execute(
            "INSERT INTO cache (hash, type, result, expires_at) VALUES (?, ?, ?, ?)",
            ("expired_hash", "llm", "expired", past),
        )
        conn.commit()
        conn.close()

        cache_cleanup()

        conn = sqlite3.connect(tmp_db)
        rows = conn.execute("SELECT * FROM cache").fetchall()
        conn.close()
        assert len(rows) == 1

    # ── TC-CACHE-007: Unicode content cached correctly ──
    def test_unicode_content(self):
        text = "Thành phố Hồ Chí Minh có 10 triệu dân"
        cache_set("llm", text, "vn_key")
        result = cache_get("llm", "vn_key")
        assert result == text

    # ── TC-CACHE-008: LLM TTL = 30 days, TTS TTL = 7 days ──
    def test_llm_ttl_longer_than_tts(self, tmp_db):
        cache_set("llm", "llm_data", "ttl_test_llm")
        cache_set("tts", "tts_data", "ttl_test_tts")

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        llm_row = conn.execute(
            "SELECT expires_at FROM cache WHERE type = 'llm'"
        ).fetchone()
        tts_row = conn.execute(
            "SELECT expires_at FROM cache WHERE type = 'tts'"
        ).fetchone()
        conn.close()

        llm_exp = datetime.fromisoformat(llm_row["expires_at"])
        tts_exp = datetime.fromisoformat(tts_row["expires_at"])
        # LLM should expire much later than TTS
        assert llm_exp > tts_exp
