"""Tests for retry module."""

from unittest.mock import patch

import pytest

from fabric_hydrate.exceptions import FabricAPIError, RateLimitError
from fabric_hydrate.retry import RetryConfig, async_retry, retry


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            jitter=False,
        )

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.jitter is False

    def test_calculate_delay_no_jitter(self) -> None:
        """Test delay calculation without jitter."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_calculate_delay_respects_max(self) -> None:
        """Test delay respects max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter=False)

        assert config.calculate_delay(10) == 5.0

    def test_calculate_delay_with_retry_after(self) -> None:
        """Test delay uses retry-after when provided."""
        config = RetryConfig(base_delay=1.0, jitter=False)

        assert config.calculate_delay(0, retry_after=30) == 30.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test delay has jitter when enabled."""
        config = RetryConfig(base_delay=1.0, jitter=True)

        delays = [config.calculate_delay(1) for _ in range(10)]
        # With jitter, delays should vary
        assert len(set(delays)) > 1

    def test_should_retry_within_limit(self) -> None:
        """Test should_retry returns True within retry limit."""
        config = RetryConfig(max_retries=3)
        error = FabricAPIError("test", status_code=500)

        assert config.should_retry(error, 0) is True
        assert config.should_retry(error, 1) is True
        assert config.should_retry(error, 2) is True
        assert config.should_retry(error, 3) is False

    def test_should_retry_checks_status_code(self) -> None:
        """Test should_retry checks status code for API errors."""
        config = RetryConfig()

        # Retryable status codes
        assert config.should_retry(FabricAPIError("test", status_code=429), 0) is True
        assert config.should_retry(FabricAPIError("test", status_code=500), 0) is True
        assert config.should_retry(FabricAPIError("test", status_code=503), 0) is True

        # Non-retryable status codes
        assert config.should_retry(FabricAPIError("test", status_code=400), 0) is False
        assert config.should_retry(FabricAPIError("test", status_code=401), 0) is False
        assert config.should_retry(FabricAPIError("test", status_code=404), 0) is False

    def test_should_retry_connection_errors(self) -> None:
        """Test should_retry for connection errors."""
        config = RetryConfig()

        assert config.should_retry(ConnectionError("test"), 0) is True
        assert config.should_retry(TimeoutError("test"), 0) is True

    def test_should_retry_non_retryable_exceptions(self) -> None:
        """Test should_retry returns False for non-retryable exceptions."""
        config = RetryConfig()

        assert config.should_retry(ValueError("test"), 0) is False
        assert config.should_retry(KeyError("test"), 0) is False


class TestRetryDecorator:
    """Tests for retry decorator."""

    def test_retry_success_first_try(self) -> None:
        """Test function succeeds on first try."""
        call_count = 0

        @retry(RetryConfig(max_retries=3))
        def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()

        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failures(self) -> None:
        """Test function succeeds after retries."""
        call_count = 0

        @retry(RetryConfig(max_retries=3, base_delay=0.01, jitter=False))
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise FabricAPIError("test", status_code=500)
            return "success"

        result = flaky_func()

        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted(self) -> None:
        """Test function fails after retries exhausted."""
        call_count = 0

        @retry(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise FabricAPIError("test", status_code=500)

        with pytest.raises(FabricAPIError):
            always_fails()

        assert call_count == 3  # Initial + 2 retries

    def test_retry_non_retryable_exception(self) -> None:
        """Test non-retryable exceptions are raised immediately."""
        call_count = 0

        @retry(RetryConfig(max_retries=3, base_delay=0.01))
        def value_error_func() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            value_error_func()

        assert call_count == 1

    def test_retry_respects_rate_limit(self) -> None:
        """Test retry respects rate limit retry-after."""
        delays: list[float] = []

        def mock_sleep(seconds: float) -> None:
            delays.append(seconds)

        call_count = 0

        @retry(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        def rate_limited_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=5)
            return "success"

        with patch("time.sleep", mock_sleep):
            result = rate_limited_func()

        assert result == "success"
        assert len(delays) == 1
        assert delays[0] == 5.0  # Respects retry-after

    def test_retry_with_default_config(self) -> None:
        """Test retry decorator with default config."""
        call_count = 0

        @retry()
        def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = success_func()
        assert result == "success"
        assert call_count == 1


class TestAsyncRetryDecorator:
    """Tests for async_retry decorator."""

    @pytest.mark.asyncio
    async def test_async_retry_success_first_try(self) -> None:
        """Test async function succeeds on first try."""
        call_count = 0

        @async_retry(RetryConfig(max_retries=3))
        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_success_after_failures(self) -> None:
        """Test async function succeeds after retries."""
        call_count = 0

        @async_retry(RetryConfig(max_retries=3, base_delay=0.01, jitter=False))
        async def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise FabricAPIError("test", status_code=500)
            return "success"

        result = await flaky_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_exhausted(self) -> None:
        """Test async function fails after retries exhausted."""
        call_count = 0

        @async_retry(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        async def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise FabricAPIError("test", status_code=500)

        with pytest.raises(FabricAPIError):
            await always_fails()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_non_retryable(self) -> None:
        """Test async non-retryable exceptions are raised immediately."""
        call_count = 0

        @async_retry(RetryConfig(max_retries=3, base_delay=0.01))
        async def value_error_func() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await value_error_func()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_respects_rate_limit(self) -> None:
        """Test async retry respects rate limit retry-after."""
        delays: list[float] = []

        async def mock_sleep(seconds: float) -> None:
            delays.append(seconds)

        call_count = 0

        @async_retry(RetryConfig(max_retries=2, base_delay=0.01, jitter=False))
        async def rate_limited_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(retry_after=5)
            return "success"

        with patch("asyncio.sleep", mock_sleep):
            result = await rate_limited_func()

        assert result == "success"
        assert len(delays) == 1
        assert delays[0] == 5.0

    @pytest.mark.asyncio
    async def test_async_retry_with_default_config(self) -> None:
        """Test async_retry decorator with default config."""
        call_count = 0

        @async_retry()
        async def success_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1
