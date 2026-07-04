import asyncio
import functools
import logging
import time
from typing import Callable, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Semantic Scholar rate limit: 1 request per second
MIN_REQUEST_INTERVAL = 1.0  # seconds
_last_request_time = 0.0


async def ensure_rate_limit():
    """确保遵守 Semantic Scholar 的速率限制（1 request per second）"""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        wait_time = MIN_REQUEST_INTERVAL - elapsed
        await asyncio.sleep(wait_time)
    _last_request_time = time.time()


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    # 确保遵守速率限制
                    await ensure_rate_limit()
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
                        raise
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    # 确保遵守速率限制
                    global _last_request_time
                    now = time.time()
                    elapsed = now - _last_request_time
                    if elapsed < MIN_REQUEST_INTERVAL:
                        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
                    _last_request_time = time.time()
                    
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(f"All {max_retries} attempts failed. Last error: {str(e)}")
                        raise
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator