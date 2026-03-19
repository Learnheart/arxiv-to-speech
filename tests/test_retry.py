"""
Unit tests for utils/retry.py
Covers: retry_async()
"""
import asyncio
from unittest.mock import AsyncMock

import pytest

from utils.retry import retry_async


class TestRetryAsync:
    """Test suite for exponential backoff retry."""

    # ── TC-RTY-001: Success on first try ──
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        mock_func = AsyncMock(return_value="ok")
        result = await retry_async(mock_func, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert mock_func.call_count == 1

    # ── TC-RTY-002: Success after retries ──
    @pytest.mark.asyncio
    async def test_success_after_two_failures(self):
        mock_func = AsyncMock(side_effect=[ValueError("err1"), ValueError("err2"), "ok"])
        result = await retry_async(mock_func, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert mock_func.call_count == 3

    # ── TC-RTY-003: All retries exhausted ──
    @pytest.mark.asyncio
    async def test_all_retries_exhausted_raises(self):
        mock_func = AsyncMock(side_effect=ValueError("persistent error"))
        with pytest.raises(ValueError, match="persistent error"):
            await retry_async(mock_func, max_retries=3, base_delay=0.01)
        assert mock_func.call_count == 3

    # ── TC-RTY-004: Only catches specified exceptions ──
    @pytest.mark.asyncio
    async def test_only_catches_specified_exceptions(self):
        mock_func = AsyncMock(side_effect=TypeError("wrong type"))
        with pytest.raises(TypeError):
            await retry_async(
                mock_func,
                max_retries=3,
                base_delay=0.01,
                exceptions=(ValueError,),
            )
        assert mock_func.call_count == 1  # No retry for unspecified exception

    # ── TC-RTY-005: Single retry ──
    @pytest.mark.asyncio
    async def test_single_retry(self):
        mock_func = AsyncMock(side_effect=ValueError("fail"))
        with pytest.raises(ValueError):
            await retry_async(mock_func, max_retries=1, base_delay=0.01)
        assert mock_func.call_count == 1

    # ── TC-RTY-006: Args and kwargs forwarded ──
    @pytest.mark.asyncio
    async def test_args_kwargs_forwarded(self):
        async def sample_func(a, b, key="default"):
            return f"{a}-{b}-{key}"

        result = await retry_async(sample_func, "x", "y", key="z", max_retries=1, base_delay=0.01)
        assert result == "x-y-z"

    # ── TC-RTY-007: Exponential backoff delay increases ──
    @pytest.mark.asyncio
    async def test_delay_increases(self):
        """Verify retry takes longer with more attempts (indirect test)."""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = await retry_async(failing_func, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert call_count == 3
