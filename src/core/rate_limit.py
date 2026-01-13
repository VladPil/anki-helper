"""Redis-based rate limiting for API endpoints.

This module provides rate limiting using Redis sliding window algorithm.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from fastapi import HTTPException, Request, status

from src.core.dependencies import RedisManager

P = ParamSpec("P")
R = TypeVar("R")


class RedisRateLimiter:
    """Redis-based sliding window rate limiter.

    Uses sorted sets to implement a sliding window rate limiting algorithm.

    Attributes:
        key_prefix: Prefix for Redis keys.
        limit: Maximum number of requests allowed in the window.
        window_seconds: Size of the sliding window in seconds.
    """

    PREFIX = "rate_limit:"

    def __init__(
        self,
        key_prefix: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        """Initialize rate limiter.

        Args:
            key_prefix: Prefix for this limiter's Redis keys.
            limit: Maximum requests per window.
            window_seconds: Window size in seconds.
        """
        self.key_prefix = key_prefix
        self.limit = limit
        self.window_seconds = window_seconds

    async def is_allowed(self, identifier: str) -> tuple[bool, int]:
        """Check if request is allowed.

        Args:
            identifier: Unique identifier for the client (user_id or IP).

        Returns:
            Tuple of (is_allowed, retry_after_seconds).
        """
        redis = await RedisManager.get_client()
        key = f"{self.PREFIX}{self.key_prefix}:{identifier}"

        now = int(time.time())
        window_start = now - self.window_seconds

        pipe = redis.pipeline()
        # Remove old entries outside the window
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries in window
        pipe.zcard(key)
        # Add new entry with current timestamp
        pipe.zadd(key, {str(now): now})
        # Set expiry on the key
        pipe.expire(key, self.window_seconds)

        results = await pipe.execute()
        count = results[1]  # zcard result

        if count >= self.limit:
            # Get oldest entry time to calculate retry_after
            oldest = await redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = int(oldest[0][1])
                retry_after = oldest_time + self.window_seconds - now
                return False, max(retry_after, 1)
            return False, self.window_seconds

        return True, 0


# Pre-configured limiters based on SPECIFICATION.md
GENERATION_LIMITER = RedisRateLimiter(
    key_prefix="generation",
    limit=10,
    window_seconds=3600,  # 10 per hour
)

CHAT_LIMITER = RedisRateLimiter(
    key_prefix="chat",
    limit=60,
    window_seconds=3600,  # 60 per hour
)


def rate_limit(
    limiter: RedisRateLimiter,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for rate-limited endpoints.

    Args:
        limiter: The rate limiter instance to use.

    Returns:
        Decorator function.

    Raises:
        HTTPException: 429 Too Many Requests when rate limit exceeded.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Try to get user_id from kwargs (authenticated endpoints)
            user_id = kwargs.get("user_id")

            # Fallback to request IP
            request: Request | None = kwargs.get("request")
            if user_id:
                identifier = str(user_id)
            elif request and request.client:
                identifier = request.client.host
            else:
                identifier = "unknown"

            allowed, retry_after = await limiter.is_allowed(identifier)

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "RedisRateLimiter",
    "GENERATION_LIMITER",
    "CHAT_LIMITER",
    "rate_limit",
]
