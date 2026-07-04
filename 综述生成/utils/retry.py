"""
带指数退避的重试机制
"""
import asyncio
import httpx
from typing import TypeVar, Callable, Any
from functools import wraps

T = TypeVar('T')


async def exponential_backoff_retry(
    func: Callable[..., T],
    max_retries: int = 5,
    initial_delay: float = 1.0,
    *args,
    **kwargs
) -> T:
    """
    指数退避重试装饰器/函数

    Args:
        func: 异步函数
        max_retries: 最大重试次数
        initial_delay: 初始延迟秒数
        *args, **kwargs: 函数参数
    """
    last_exception = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            last_exception = e
            if e.response.status_code == 429:
                # 火山方舟API限流
                delay = initial_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise
        except Exception as e:
            # 其他错误直接抛出
            raise

    raise last_exception


def with_retry(max_retries: int = 5, initial_delay: float = 1.0):
    """
    重试装饰器

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟秒数
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await exponential_backoff_retry(
                func, max_retries, initial_delay, *args, **kwargs
            )
        return wrapper
    return decorator
