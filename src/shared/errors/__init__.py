"""Shared errors package.

Centralized error handling and exception management.
"""

from .base import AppError
from .context import trace_id_var
from .decorators import safe, safe_with_fallback
from .domain import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
    ValidationError,
)
from .handlers import register_exception_handlers, setup_exception_handlers
from .mapping import ExceptionMapper
from .schemas import ErrorDetail, ErrorResponse

__all__ = [
    # Base
    "AppError",
    # Domain errors
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "ServiceUnavailableError",
    "RateLimitError",
    "BadRequestError",
    # Mapping
    "ExceptionMapper",
    # Decorators
    "safe",
    "safe_with_fallback",
    # Handlers
    "setup_exception_handlers",
    "register_exception_handlers",
    # Context
    "trace_id_var",
    # Schemas
    "ErrorDetail",
    "ErrorResponse",
]
