"""
Structured logging with Loguru.

This module provides backwards compatibility by re-exporting
from the shared logging module. New code should import directly
from src.shared.logging.

Migration guide:
    # Old import (still works)
    from src.core.logging import get_logger, setup_logging

    # New import (preferred)
    from src.shared.logging import get_logger, setup_logger
"""

from contextvars import ContextVar
from typing import Any

from loguru import logger

# Re-export from shared module
from src.shared.logging import (
    InterceptHandler,
    get_logger,
    log_embedding_request,
    log_fact_check_result,
    log_generation_completed,
    log_generation_failed,
    log_generation_progress,
    log_generation_started,
    log_llm_request,
    log_llm_response,
    setup_logger,
)

# ==================== Context Variables ====================
# Kept for backwards compatibility with existing code

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
_trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id_ctx: ContextVar[str | None] = ContextVar("span_id", default=None)


def set_request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> None:
    """Set request context for logging."""
    if request_id is not None:
        _request_id_ctx.set(request_id)
    if user_id is not None:
        _user_id_ctx.set(user_id)
    if trace_id is not None:
        _trace_id_ctx.set(trace_id)
    if span_id is not None:
        _span_id_ctx.set(span_id)


def clear_request_context() -> None:
    """Clear request context."""
    _request_id_ctx.set(None)
    _user_id_ctx.set(None)
    _trace_id_ctx.set(None)
    _span_id_ctx.set(None)


def get_request_context() -> dict[str, str | None]:
    """Get current request context."""
    return {
        "request_id": _request_id_ctx.get(),
        "user_id": _user_id_ctx.get(),
        "trace_id": _trace_id_ctx.get(),
        "span_id": _span_id_ctx.get(),
    }


# Backwards compatibility alias
def setup_logging() -> None:
    """Configure application logging.

    Deprecated: Use setup_logger() instead.
    """
    setup_logger()


# ==================== StructuredLogger wrapper ====================


class StructuredLogger:
    """Wrapper for structured logging with additional fields.

    This class provides a familiar interface for code migrating
    from standard logging. For new code, use loguru directly:

        from loguru import logger
        logger.info("message", field=value)
    """

    def __init__(self, name: str) -> None:
        self._logger = logger.bind(name=name)
        self._extra: dict[str, Any] = {}

    def bind(self, **kwargs: Any) -> "StructuredLogger":
        """Create a new logger with additional fields."""
        new_logger = StructuredLogger(self._logger._core.extra.get("name", ""))
        new_logger._extra = {**self._extra, **kwargs}
        new_logger._logger = self._logger.bind(**kwargs)
        return new_logger

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log DEBUG message."""
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log INFO message."""
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log WARNING message."""
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args: Any, exc_info: bool = False, **kwargs: Any) -> None:
        """Log ERROR message."""
        if exc_info:
            self._logger.opt(exception=True).error(message, *args, **kwargs)
        else:
            self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args: Any, exc_info: bool = False, **kwargs: Any) -> None:
        """Log CRITICAL message."""
        if exc_info:
            self._logger.opt(exception=True).critical(message, *args, **kwargs)
        else:
            self._logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._logger.opt(exception=True).error(message, *args, **kwargs)


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger.

    Deprecated: Use get_logger() from src.shared.logging instead.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Structured logger wrapper.
    """
    return StructuredLogger(name)


# ==================== Exports ====================

__all__ = [
    # Core logging (new API)
    "logger",
    "setup_logger",
    "get_logger",
    "InterceptHandler",
    # Event logging
    "log_generation_started",
    "log_generation_completed",
    "log_generation_failed",
    "log_generation_progress",
    "log_llm_request",
    "log_llm_response",
    "log_embedding_request",
    "log_fact_check_result",
    # Backwards compatibility
    "setup_logging",
    "get_structured_logger",
    "StructuredLogger",
    "set_request_context",
    "clear_request_context",
    "get_request_context",
]
