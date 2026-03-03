"""Tests for utils/retry_util.py."""
import asyncio

import pytest

from custom_components.mijnted.utils.retry_util import RetryUtil


class TestAsyncRetryWithBackoff:
    async def test_succeeds_first_try(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            return "ok"

        result = await RetryUtil.async_retry_with_backoff(op, max_retries=2, delay=0)
        assert result == "ok"
        assert calls == 1

    async def test_succeeds_after_retries(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ValueError("not yet")
            return "done"

        result = await RetryUtil.async_retry_with_backoff(
            op, max_retries=3, delay=0, exceptions_to_catch=(ValueError,)
        )
        assert result == "done"
        assert calls == 3

    async def test_raises_after_exhausted_retries(self):
        async def op():
            raise ValueError("always fails")

        with pytest.raises(ValueError, match="always fails"):
            await RetryUtil.async_retry_with_backoff(
                op, max_retries=2, delay=0, exceptions_to_catch=(ValueError,)
            )

    async def test_unexpected_exception_not_retried(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            raise RuntimeError("unexpected")

        with pytest.raises(RuntimeError, match="unexpected"):
            await RetryUtil.async_retry_with_backoff(
                op, max_retries=3, delay=0, exceptions_to_catch=(ValueError,)
            )
        assert calls == 1

    async def test_zero_retries_single_attempt(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await RetryUtil.async_retry_with_backoff(
                op, max_retries=0, delay=0, exceptions_to_catch=(ValueError,)
            )
        assert calls == 1

    async def test_negative_retries_raises_value_error(self):
        async def op():
            return "ok"

        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            await RetryUtil.async_retry_with_backoff(op, max_retries=-1, delay=0)

    async def test_negative_delay_raises_value_error(self):
        async def op():
            return "ok"

        with pytest.raises(ValueError, match="delay must be non-negative"):
            await RetryUtil.async_retry_with_backoff(op, max_retries=1, delay=-1)

    async def test_operation_name_in_logging(self):
        """Ensure operation_name parameter is accepted (logging tested implicitly)."""
        async def op():
            return 42

        result = await RetryUtil.async_retry_with_backoff(
            op, max_retries=0, delay=0, operation_name="test_op"
        )
        assert result == 42
