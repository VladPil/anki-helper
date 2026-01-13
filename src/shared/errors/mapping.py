"""Mapping of infrastructure errors to domain errors.

Centralized exception mapping for SQLAlchemy, HTTP clients, and other infrastructure.
"""

import logging
from collections.abc import Callable
from typing import Any

# Infrastructure imports with optional handling
from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

try:
    from httpx import ConnectError, HTTPError, TimeoutException
except ImportError:
    HTTPError = ConnectError = TimeoutException = Exception  # type: ignore[misc, assignment]

try:
    from aiohttp import ClientError
except ImportError:
    ClientError = Exception  # type: ignore[misc, assignment]

from .base import AppError
from .domain import ConflictError, ServiceUnavailableError, ValidationError

logger = logging.getLogger(__name__)


class ExceptionMapper:
    """Centralized mapping of technical exceptions to domain exceptions."""

    _handlers: dict[type[Exception], Callable[[Exception, str], AppError]] = {}

    @classmethod
    def register(
        cls, *exception_types: type[Exception]
    ) -> Callable[[Callable[[Any, str], AppError]], Callable[[Any, str], AppError]]:
        """Register a handler for exception types.

        Usage:
            @ExceptionMapper.register(IntegrityError)
            def _handle_integrity_error(exc: IntegrityError, func_name: str) -> AppError:
                return ConflictError(message="Record already exists")
        """

        def decorator(
            handler: Callable[[Any, str], AppError]
        ) -> Callable[[Any, str], AppError]:
            for exc_type in exception_types:
                cls._handlers[exc_type] = handler
            return handler

        return decorator

    @classmethod
    def map(cls, exc: Exception, func_name: str = "") -> AppError:
        """Map a technical exception to a domain exception.

        Args:
            exc: The technical exception to map
            func_name: Name of the function where exception occurred (for logging)

        Returns:
            Mapped domain exception (AppError subclass)
        """
        # Direct type match
        handler = cls._handlers.get(type(exc))

        # Try inheritance match if no direct match
        if handler is None:
            for exc_type, exc_handler in cls._handlers.items():
                if isinstance(exc, exc_type):
                    handler = exc_handler
                    break

        if handler:
            return handler(exc, func_name)

        # Fallback for unhandled exceptions
        logger.exception(f"CRITICAL: Unhandled exception in {func_name}: {type(exc).__name__}")
        return AppError(
            message="Internal server error",
            details={"function": func_name} if func_name else {},
        )

    @classmethod
    def handle(cls, exc: Exception, func_name: str = "") -> AppError:
        """Alias for map() for backwards compatibility."""
        return cls.map(exc, func_name)


# --- Register default handlers ---


@ExceptionMapper.register(IntegrityError)
def _handle_integrity_error(exc: IntegrityError, func_name: str) -> AppError:
    """Database: integrity constraint violation."""
    err_msg = str(exc).lower()
    if "unique" in err_msg or "duplicate" in err_msg:
        return ConflictError(
            message="Record already exists",
            details={"constraint": "unique"},
        )
    if "foreign key" in err_msg:
        return ValidationError(
            message="Related record not found",
            details={"constraint": "foreign_key"},
        )
    return ValidationError(message="Database constraint violation")


@ExceptionMapper.register(OperationalError, DatabaseError)
def _handle_database_error(exc: Exception, func_name: str) -> AppError:
    """Database: connection or operational error."""
    logger.error(f"Database error in {func_name}: {exc}")
    return ServiceUnavailableError(
        message="Database temporarily unavailable",
        details={"service": "database"},
    )


@ExceptionMapper.register(TimeoutException, ConnectError, HTTPError)
def _handle_httpx_error(exc: Exception, func_name: str) -> AppError:
    """HTTPX: external service error."""
    status = getattr(getattr(exc, "response", None), "status_code", None)

    if isinstance(status, int) and status >= 500:
        logger.error(f"External HTTP 5xx in {func_name}")
    else:
        logger.warning(f"External HTTP error in {func_name}: {exc}")

    details: dict[str, Any] = {"service": "http_client"}
    if status:
        details["status"] = status

    return ServiceUnavailableError(
        message="External service temporarily unavailable",
        details=details,
    )


@ExceptionMapper.register(ClientError)
def _handle_aiohttp_error(exc: Exception, func_name: str) -> AppError:
    """Aiohttp: client error."""
    logger.warning(f"Aiohttp client error in {func_name}: {exc}")
    return ServiceUnavailableError(
        message="External service temporarily unavailable",
        details={"service": "http_client"},
    )
