import asyncio
import logging
from typing import Callable, Awaitable, Type, Tuple, Any, Optional

_LOGGER = logging.getLogger(__name__)


class RetryUtil:
    """Utility class for retry logic with constant delay backoff."""
    
    @staticmethod
    async def async_retry_with_backoff(
        coro: Callable[[], Awaitable[Any]],
        max_retries: int,
        delay: int,
        exceptions_to_catch: Tuple[Type[Exception], ...] = (Exception,),
        operation_name: Optional[str] = None
    ) -> Any:
        """Retry an async operation with constant delay between attempts.
        
        Args:
            coro: Async callable to retry (takes no arguments)
            max_retries: Maximum number of retry attempts (total attempts = max_retries + 1)
            delay: Delay in seconds between retries
            exceptions_to_catch: Tuple of exception types to catch and retry on
            operation_name: Optional name for logging purposes
            
        Returns:
            Result from the coroutine
            
        Raises:
            Last exception if all retries are exhausted, or any unexpected exception
        """
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if delay < 0:
            raise ValueError("delay must be non-negative")
        
        last_error: Optional[Exception] = None
        operation = operation_name or "operation"
        
        for attempt in range(max_retries + 1):
            try:
                return await coro()
            except exceptions_to_catch as err:
                last_error = err
                _LOGGER.warning(
                    "%s failed (attempt %d/%d): %s",
                    operation.capitalize(),
                    attempt + 1,
                    max_retries + 1,
                    err
                )
                if attempt < max_retries:
                    _LOGGER.debug("Retrying %s in %d seconds...", operation, delay)
                    await asyncio.sleep(delay)
                    continue
            except Exception as err:
                # Don't retry on unexpected exceptions - re-raise immediately
                _LOGGER.error(
                    "%s failed with unexpected exception (attempt %d/%d): %s",
                    operation.capitalize(),
                    attempt + 1,
                    max_retries + 1,
                    err
                )
                raise
        
        if last_error is None:
            raise RuntimeError(f"{operation.capitalize()} failed after {max_retries + 1} attempts (no error captured)")
        
        _LOGGER.error(
            "%s failed after %d attempts: %s",
            operation.capitalize(),
            max_retries + 1,
            last_error
        )
        raise last_error

