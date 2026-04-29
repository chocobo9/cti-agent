from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

import httpx

from cti_agent.enrichment.config import get_settings

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


def retry_async(
    max_retries: int | None = None,
    base_delay: float | None = None,
    retryable_exceptions: tuple[type[BaseException], ...] = (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.HTTPStatusError,
    ),
) -> Callable[[Callable[P, Coroutine[Any, Any, T]]], Callable[P, Coroutine[Any, Any, T]]]:
    def decorator(func: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            settings = get_settings()
            retries = max_retries if max_retries is not None else settings.max_retries
            delay = base_delay if base_delay is not None else settings.retry_base_delay
            last_exc: BaseException | None = None
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt < retries:
                        await asyncio.sleep(delay * (2**attempt))
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


def create_http_client(timeout: float | None = None) -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout or settings.http_timeout),
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )
