import logging
import time
from collections import defaultdict
from typing import Callable
from fastapi import HTTPException, Request, status
import redis

from fieldops.core.config import settings

logger = logging.getLogger(__name__)

# In-memory sliding counter fallback (for testing or when Redis is absent)
_LOCAL_COUNTER: dict[str, list[float]] = defaultdict(list)


import os

def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    fail_open: bool = True,
) -> bool:
    """Check whether a request key exceeds rate limit within a time window."""
    if (
        not settings.RATE_LIMIT_ENABLED
        or os.environ.get("RATE_LIMIT_ENABLED", "").lower() in ("false", "0")
        or settings.LOAD_TEST_MODE
        or settings.APP_ENV == "testing"
    ):
        return True

    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=0.5)
        # Use simple fixed-window counter with atomic INCR + EXPIRE
        current_window = int(time.time() // window_seconds)
        redis_key = f"rate_limit:{key}:{current_window}"

        current_count = r.incr(redis_key)
        if current_count == 1:
            r.expire(redis_key, window_seconds)

        if current_count > max_requests:
            logger.warning("Rate limit exceeded for key=%s: count=%d > max=%d", key, current_count, max_requests)
            return False
        return True

    except Exception as e:
        logger.warning("Redis unavailable during rate limit check for key=%s: %s", key, e)
        if not fail_open:
            # Security-sensitive: Fail-Closed
            logger.error("Rate limiter failing closed for sensitive key=%s", key)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security rate limiter temporarily unavailable. Request blocked for safety.",
            )

        # In-memory sliding window fallback for local testing / fail-open
        now = time.time()
        window_start = now - window_seconds
        timestamps = _LOCAL_COUNTER[key]
        # Purge stale timestamps
        _LOCAL_COUNTER[key] = [t for t in timestamps if t > window_start]

        if len(_LOCAL_COUNTER[key]) >= max_requests:
            logger.warning("Local fallback rate limit exceeded for key=%s", key)
            return False

        _LOCAL_COUNTER[key].append(now)
        return True


def rate_limiter(
    max_requests: int,
    window_seconds: int,
    is_auth: bool = False,
) -> Callable[[Request], None]:
    """FastAPI dependency for endpoint rate limiting."""

    def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        key = f"{endpoint}:{client_ip}"

        fail_open = not is_auth  # Business routes fail-open, Auth routes fail-closed

        allowed = check_rate_limit(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
            fail_open=fail_open,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too Many Requests: Rate limit exceeded ({max_requests} requests per {window_seconds}s).",
            )

    return dependency


def reset_local_rate_limiter() -> None:
    """Clear local memory counter (for unit and performance testing)."""
    global _LOCAL_COUNTER
    _LOCAL_COUNTER.clear()
