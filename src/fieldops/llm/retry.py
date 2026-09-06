"""Retry with exponential backoff and jitter for transient LLM errors."""

import logging
import random
import time
from typing import Callable, TypeVar

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

from fieldops.core.exceptions import LLMServiceError, LLMTimeoutError

logger = logging.getLogger(__name__)
T = TypeVar("T")

RETRYABLE_EXCEPTIONS = (
    APITimeoutError,
    RateLimitError,
    InternalServerError,
    APIConnectionError,
    LLMTimeoutError,
    TimeoutError,
    ConnectionError,
)


def retry_with_backoff(
    fn: Callable[[], T],
    max_attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    jitter: float = 0.2,
    operation_name: str = "llm_call",
) -> T:
    """Execute a callable with exponential backoff and jitter for transient failures.

    Transient errors retried:
    - APITimeoutError / TimeoutError
    - RateLimitError (429)
    - InternalServerError (5xx)
    - APIConnectionError

    Non-retryable errors (e.g. 400 Bad Request, Authentication, Schema violations)
    fail immediately.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except RETRYABLE_EXCEPTIONS as e:
            if attempt >= max_attempts:
                logger.error(
                    "Operation [%s] exhausted %d attempts. Final error: %s",
                    operation_name,
                    max_attempts,
                    e,
                )
                if isinstance(e, (APITimeoutError, TimeoutError, LLMTimeoutError)):
                    raise LLMTimeoutError(
                        f"LLM request timed out after {max_attempts} attempts: {e}"
                    ) from e
                raise LLMServiceError(
                    f"LLM transient error after {max_attempts} attempts: {e}",
                    retryable=True,
                ) from e

            delay = min(max_delay, base_delay * (2 ** (attempt - 1))) + random.uniform(
                0, jitter
            )
            logger.warning(
                "Transient error during [%s] (attempt %d/%d): %s. Backoff %.2fs...",
                operation_name,
                attempt,
                max_attempts,
                e,
                delay,
            )
            time.sleep(delay)
        except Exception as e:
            logger.error("Non-retryable error during [%s]: %s", operation_name, e)
            raise
