"""
Unit tests for llm/groq_client.py
Covers: describe_image(), narrate_table(), _call_groq(), _fallback_table_readout()
"""
import base64
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from llm.groq_client import (
    describe_image,
    narrate_table,
    _fallback_table_readout,
    PROMPT_DESCRIBE_IMAGE,
    PROMPT_NARRATE_TABLE,
)


# ══════════════════════════════════════════════════════════
# TC-GROQ: _call_groq() / describe_image() / narrate_table()
# ══════════════════════════════════════════════════════════

class TestDescribeImage:

    # ── TC-GROQ-001: Successful image description ──
    @pytest.mark.asyncio
    async def test_successful_description(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hình ảnh mô tả biểu đồ doanh thu"

        with patch("llm.groq_client._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await describe_image(b"\x89PNG test image bytes")

        assert "biểu đồ doanh thu" in result

    # ── TC-GROQ-002: Primary model fails, fallback succeeds ──
    @pytest.mark.asyncio
    async def test_fallback_model_on_primary_failure(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Fallback description"

        call_count = 0

        async def mock_create(**kwargs):
            nonlocal call_count
            call_count += 1
            if "maverick" in kwargs.get("model", ""):
                raise Exception("Rate limit")
            return mock_response

        with patch("llm.groq_client._client") as mock_client:
            mock_client.chat.completions.create = mock_create
            result = await describe_image(b"\x89PNG")

        assert result == "Fallback description"

    # ── TC-GROQ-003: Both models fail → placeholder ──
    @pytest.mark.asyncio
    async def test_both_models_fail_returns_placeholder(self):
        async def always_fail(**kwargs):
            raise Exception("Service down")

        with patch("llm.groq_client._client") as mock_client:
            mock_client.chat.completions.create = always_fail
            result = await describe_image(b"\x89PNG")

        assert "khong the mo ta" in result.lower() or "Hinh anh" in result

    # ── TC-GROQ-004: Image encoded as base64 ──
    @pytest.mark.asyncio
    async def test_image_base64_encoding(self):
        test_bytes = b"test image data"
        expected_b64 = base64.b64encode(test_bytes).decode("utf-8")

        captured_messages = []

        async def capture_create(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "ok"
            return mock_resp

        with patch("llm.groq_client._client") as mock_client:
            mock_client.chat.completions.create = capture_create
            await describe_image(test_bytes)

        # Verify base64 is in the message
        msg_str = str(captured_messages)
        assert expected_b64 in msg_str


class TestNarrateTable:

    # ── TC-GROQ-005: Successful table narration ──
    @pytest.mark.asyncio
    async def test_successful_narration(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Bảng cho thấy doanh thu tăng 20%"

        with patch("llm.groq_client._client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            result = await narrate_table("| Year | Revenue |\n| --- | --- |\n| 2024 | 100M |")

        assert "doanh thu" in result

    # ── TC-GROQ-006: Both models fail → fallback readout ──
    @pytest.mark.asyncio
    async def test_fallback_readout_on_total_failure(self):
        async def always_fail(**kwargs):
            raise Exception("All models down")

        with patch("llm.groq_client._client") as mock_client:
            mock_client.chat.completions.create = always_fail
            result = await narrate_table("| A | B |\n| --- | --- |\n| 1 | 2 |")

        assert "Bang gom" in result


# ══════════════════════════════════════════════════════════
# TC-FBACK: _fallback_table_readout()
# ══════════════════════════════════════════════════════════

class TestFallbackTableReadout:

    def test_basic_table(self):
        md = "| Name | Score |\n| --- | --- |\n| Alice | 95 |"
        result = _fallback_table_readout(md)
        assert "Bang gom" in result
        assert "2" in result  # 2 data rows (header + 1 data)
        assert "Alice" in result

    def test_empty_table(self):
        result = _fallback_table_readout("")
        assert "Bang gom 0 dong" in result

    def test_separator_lines_removed(self):
        md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
        result = _fallback_table_readout(md)
        assert "---" not in result

    def test_multirow_table(self):
        md = "| H1 | H2 |\n| --- | --- |\n| a | b |\n| c | d |\n| e | f |"
        result = _fallback_table_readout(md)
        assert "4" in result  # 4 data rows
