"""Decorators for error handling.

Function wrappers for protection against technical errors.
"""

import logging
from collections.abc import Callable
from functools import wraps
from inspect import iscoroutinefunction
from typing import Never, ParamSpec, TypeVar

from .base import AppError
from .mapping import ExceptionMapper

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


def safe(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator for protection against technical errors (Repository/Service layer).

    Usage:
        @safe
        async def get_user(user_id: int) -> User:
            # Business errors (AppError) pass through
            # Technical errors (IntegrityError, etc.) -> domain errors
            ...

    The decorator:
    - Lets AppError subclasses pass through unchanged
    - Maps technical exceptions to domain exceptions via ExceptionMapper
    - Works with both sync and async functions
    """

    def _handle_exception(e: Exception, func_name: str) -> Never:
        if isinstance(e, AppError):
            raise
        raise ExceptionMapper.map(e, func_name) from e

    if iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                _handle_exception(e, func.__name__)

        return async_wrapper  # type: ignore[return-value]

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _handle_exception(e, func.__name__)

    return sync_wrapper  # type: ignore[return-value]


def safe_with_fallback(
    fallback: T,
    log_level: int = logging.WARNING,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator that returns a fallback value on error instead of raising.

    Usage:
        @safe_with_fallback(fallback=[])
        async def get_recommendations() -> list[str]:
            # On any error, returns [] instead of raising
            ...

    Args:
        fallback: Value to return when an exception occurs
        log_level: Logging level for caught exceptions
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        if iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.log(
                        log_level,
                        f"Exception in {func.__name__}, returning fallback: {e}",
                    )
                    return fallback

            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level,
                    f"Exception in {func.__name__}, returning fallback: {e}",
                )
                return fallback

        return sync_wrapper  # type: ignore[return-value]

    return decorator
