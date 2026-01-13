"""Cashews caching configuration and utilities.

This module provides Redis-based caching using the Cashews library.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cashews import cache

if TYPE_CHECKING:
    from src.core.config import Settings


async def setup_cache(settings: Settings) -> None:
    """Initialize cache on application startup.

    Args:
        settings: Application settings with Redis configuration.
    """
    cache.setup(
        settings.redis.url,
        prefix="ankirag:",
        enable=True,
    )


async def close_cache() -> None:
    """Close cache connections on shutdown."""
    await cache.close()


# Re-export cache for use in decorators
__all__ = ["cache", "setup_cache", "close_cache"]
