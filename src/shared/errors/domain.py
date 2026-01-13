"""Standard domain error types.

Catalog of standard error types for use across the application.
"""

from .base import AppError


class NotFoundError(AppError):
    """Resource not found."""

    status_code = 404


class ConflictError(AppError):
    """Resource conflict or duplicate."""

    status_code = 409


class ValidationError(AppError):
    """Input validation error."""

    status_code = 422


class AuthenticationError(AppError):
    """Authentication required or failed."""

    status_code = 401


class AuthorizationError(AppError):
    """Access denied - insufficient permissions."""

    status_code = 403


class ServiceUnavailableError(AppError):
    """External service is unavailable."""

    status_code = 503


class RateLimitError(AppError):
    """Rate limit exceeded."""

    status_code = 429


class BadRequestError(AppError):
    """Bad request - malformed or invalid."""

    status_code = 400
