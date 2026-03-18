"""
D2S Pipeline — Groq API client for image description and table narration.
Uses python-dotenv to load GROQ_API_KEY from .env.
"""
import base64
from groq import AsyncGroq

from config import GROQ_API_KEY, LLM_CONFIG
from logger import logger
from utils.retry import retry_async

# Initialize async Groq client
_client = AsyncGroq(api_key=GROQ_API_KEY)


PROMPT_DESCRIBE_IMAGE = """Bạn là trợ lý chuyển đổi tài liệu sang audio.
Hãy mô tả hình ảnh này bằng tiếng Việt một cách tự nhiên, dễ nghe, phù hợp để đọc trong audiobook.
Tập trung vào nội dung chính, số liệu quan trọng (nếu có), và ý nghĩa của hình ảnh.
Không sử dụng markdown, bullet point, hay ký tự đặc biệt. Viết thành đoạn văn liền mạch."""

PROMPT_NARRATE_TABLE = """Bạn là trợ lý chuyển đổi tài liệu sang audio.
Hãy diễn giải bảng dữ liệu sau bằng tiếng Việt, tự nhiên và dễ nghe, phù hợp để đọc trong audiobook.
Nêu các số liệu quan trọng, xu hướng, so sánh nổi bật.
Không sử dụng markdown, bullet point, hay ký tự đặc biệt. Viết thành đoạn văn liền mạch.

Bảng dữ liệu:
{table_md}"""


async def _call_groq(
    messages: list[dict],
    model: str | None = None,
) -> str:
    """Make a Groq API call. Returns the response text."""
    model = model or LLM_CONFIG["model"]
    response = await _client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=LLM_CONFIG["max_tokens"],
        temperature=LLM_CONFIG["temperature"],
    )
    return response.choices[0].message.content.strip()


async def describe_image(image_bytes: bytes) -> str:
    """Describe an image for audiobook narration using Groq vision model."""
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT_DESCRIBE_IMAGE},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64_image}",
                    },
                },
            ],
        }
    ]

    try:
        result = await retry_async(
            _call_groq,
            messages,
            LLM_CONFIG["model"],
            max_retries=3,
        )
        logger.info("Image described successfully (%d chars)", len(result))
        return result
    except Exception as e:
        logger.warning("Primary model failed for image, trying fallback: %s", e)
        try:
            result = await retry_async(
                _call_groq,
                messages,
                LLM_CONFIG["fallback_model"],
                max_retries=2,
            )
            logger.info("Image described via fallback (%d chars)", len(result))
            return result
        except Exception as e2:
            logger.error("All models failed for image description: %s", e2)
            return "[Hinh anh khong the mo ta]"


async def narrate_table(table_md: str) -> str:
    """Narrate a table for audiobook using Groq."""
    messages = [
        {
            "role": "user",
            "content": PROMPT_NARRATE_TABLE.format(table_md=table_md),
        }
    ]

    try:
        result = await retry_async(
            _call_groq,
            messages,
            LLM_CONFIG["model"],
            max_retries=3,
        )
        logger.info("Table narrated successfully (%d chars)", len(result))
        return result
    except Exception as e:
        logger.warning("Primary model failed for table, trying fallback: %s", e)
        try:
            result = await retry_async(
                _call_groq,
                messages,
                LLM_CONFIG["fallback_model"],
                max_retries=2,
            )
            logger.info("Table narrated via fallback (%d chars)", len(result))
            return result
        except Exception as e2:
            logger.error("All models failed for table narration: %s", e2)
            return _fallback_table_readout(table_md)


def _fallback_table_readout(table_md: str) -> str:
    """Simple raw readout when LLM fails."""
    lines = table_md.strip().split("\n")
    # Remove markdown separator lines
    data_lines = [l for l in lines if not all(c in "|-: " for c in l)]
    rows = []
    for line in data_lines:
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(", ".join(cells))
    return f"Bang gom {len(rows)} dong. " + ". ".join(rows)
