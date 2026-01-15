"""Retry utilities for resilient operations."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fabric_hydrate.exceptions import FabricAPIError, RateLimitError
from fabric_hydrate.logging import get_logger

logger = get_logger("retry")

P = ParamSpec("P")
T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type[Exception], ...] = (
            FabricAPIError,
            ConnectionError,
            TimeoutError,
        ),
        retryable_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
    ) -> None:
        """Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts.
            base_delay: Initial delay between retries in seconds.
            max_delay: Maximum delay between retries in seconds.
            exponential_base: Base for exponential backoff calculation.
            jitter: Whether to add random jitter to delays.
            retryable_exceptions: Exception types that should trigger retry.
            retryable_status_codes: HTTP status codes that should trigger retry.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self.retryable_status_codes = retryable_status_codes

    def calculate_delay(self, attempt: int, retry_after: int | None = None) -> float:
        """Calculate delay for a given retry attempt.

        Args:
            attempt: Current attempt number (0-indexed).
            retry_after: Optional server-specified retry delay.

        Returns:
            Delay in seconds.
        """
        if retry_after:
            return float(retry_after)

        delay = min(
            self.base_delay * (self.exponential_base**attempt),
            self.max_delay,
        )

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if an operation should be retried.

        Args:
            exception: The exception that occurred.
            attempt: Current attempt number.

        Returns:
            True if should retry, False otherwise.
        """
        if attempt >= self.max_retries:
            return False

        if isinstance(exception, self.retryable_exceptions):
            if isinstance(exception, FabricAPIError):
                return exception.status_code in self.retryable_status_codes
            return True

        return False


DEFAULT_RETRY_CONFIG = RetryConfig()


def retry(
    config: RetryConfig | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for adding retry logic to synchronous functions.

    Args:
        config: Retry configuration. Uses default if not provided.

    Returns:
        Decorated function with retry logic.
    """
    _config = config or DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(_config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not _config.should_retry(e, attempt):
                        raise

                    retry_after = None
                    if isinstance(e, RateLimitError):
                        retry_after = e.retry_after

                    delay = _config.calculate_delay(attempt, retry_after)
                    logger.warning(
                        f"Attempt {attempt + 1}/{_config.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")  # pragma: no cover

        return wrapper

    return decorator


def async_retry(
    config: RetryConfig | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration. Uses default if not provided.

    Returns:
        Decorated async function with retry logic.
    """
    _config = config or DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            last_exception: Exception | None = None

            for attempt in range(_config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not _config.should_retry(e, attempt):
                        raise

                    retry_after = None
                    if isinstance(e, RateLimitError):
                        retry_after = e.retry_after

                    delay = _config.calculate_delay(attempt, retry_after)
                    logger.warning(
                        f"Attempt {attempt + 1}/{_config.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")  # pragma: no cover

        return wrapper

    return decorator
