"""
D2S Pipeline — Exponential backoff retry helper.
"""
import asyncio
import random
from functools import wraps
from typing import Type

from logger import logger


async def retry_async(
    coro_func,
    *args,
    max_retries: int = 3,
    base_delay: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    **kwargs,
):
    """
    Retry an async function with exponential backoff + jitter.
    Returns result on success, raises last exception on exhaustion.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            return await coro_func(*args, **kwargs)
        except exceptions as e:
            last_exc = e
            if attempt < max_retries - 1:
                delay = (base_delay ** (attempt + 1)) + random.uniform(0, 1)
                logger.warning(
                    "Retry %d/%d for %s: %s (wait %.1fs)",
                    attempt + 1, max_retries, coro_func.__name__, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All %d retries exhausted for %s: %s",
                    max_retries, coro_func.__name__, e,
                )
    raise last_exc
