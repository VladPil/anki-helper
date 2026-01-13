"""
Custom exceptions and error handlers.

This module provides backwards compatibility by re-exporting from the new
shared.errors module while maintaining the original API.
"""

from collections.abc import Callable
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Import from new shared.errors module
from src.shared.errors import (
    AppError as BaseAppError,
)
from src.shared.errors import (
    AuthenticationError as BaseAuthenticationError,
)
from src.shared.errors import (
    AuthorizationError as BaseAuthorizationError,
)
from src.shared.errors import (
    ConflictError as BaseConflictError,
)
from src.shared.errors import (
    ExceptionMapper,
    safe,
    setup_exception_handlers,
    trace_id_var,
)
from src.shared.errors import (
    NotFoundError as BaseNotFoundError,
)
from src.shared.errors import (
    ValidationError as BaseValidationError,
)

# Re-export for backwards compatibility
__all__ = [
    # Base class
    "AppError",
    "AppError",
    # Authentication
    "AuthenticationError",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "TokenInvalidError",
    "TokenRevokedError",
    # Authorization
    "AuthorizationError",
    "PermissionDeniedError",
    "ResourceOwnershipError",
    # Resources
    "NotFoundError",
    "UserNotFoundError",
    "DeckNotFoundError",
    "CardNotFoundError",
    "DocumentNotFoundError",
    # Validation
    "ValidationError",
    "InvalidInputError",
    # Conflicts
    "ConflictError",
    "DuplicateError",
    "EmailAlreadyExistsError",
    "DeckNameExistsError",
    # External services
    "ExternalServiceError",
    "LLMServiceError",
    "AnkiConnectError",
    "PerplexityError",
    # Limits
    "RateLimitError",
    "QuotaExceededError",
    # Database
    "DatabaseError",
    "TransactionError",
    # Handlers
    "app_error_handler",
    "unhandled_exception_handler",
    "register_exception_handlers",
    "setup_exception_handlers",
    "error_handler",
    # New exports
    "safe",
    "ExceptionMapper",
    "trace_id_var",
]


# ==================== Backwards compatibility alias ====================


class AppError(BaseAppError):
    """Backwards compatibility alias for AppError."""

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(
            message=message,
            details=details,
            status_code=status_code,
            code=error_code,
        )

    @property
    def error_code(self) -> str:
        """Legacy property for backwards compatibility."""
        return self.code

    def to_dict(self) -> dict[str, Any]:
        """Legacy format for backwards compatibility."""
        result: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        if self.trace_id:
            result["error"]["trace_id"] = self.trace_id
        return result


# ==================== Authentication exceptions ====================


class AuthenticationError(BaseAuthenticationError):
    """Authentication error."""

    status_code = HTTPStatus.UNAUTHORIZED
    code = "AUTHENTICATION_ERROR"
    default_message = "Authentication failed"


class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials."""

    code = "INVALID_CREDENTIALS"
    default_message = "Invalid email or password"


class TokenExpiredError(AuthenticationError):
    """Token expired."""

    code = "TOKEN_EXPIRED"
    default_message = "Token has expired"


class TokenInvalidError(AuthenticationError):
    """Invalid token."""

    code = "TOKEN_INVALID"
    default_message = "Invalid token"


class TokenRevokedError(AuthenticationError):
    """Token revoked."""

    code = "TOKEN_REVOKED"
    default_message = "Token has been revoked"


# ==================== Authorization exceptions ====================


class AuthorizationError(BaseAuthorizationError):
    """Authorization error."""

    status_code = HTTPStatus.FORBIDDEN
    code = "AUTHORIZATION_ERROR"
    default_message = "Access denied"


class PermissionDeniedError(AuthorizationError):
    """Insufficient permissions."""

    code = "PERMISSION_DENIED"
    default_message = "You don't have permission to perform this action"


class ResourceOwnershipError(AuthorizationError):
    """Resource belongs to another user."""

    code = "RESOURCE_OWNERSHIP_ERROR"
    default_message = "You don't have access to this resource"


# ==================== Resource exceptions ====================


class NotFoundError(BaseNotFoundError):
    """Resource not found."""

    status_code = HTTPStatus.NOT_FOUND
    code = "NOT_FOUND"
    default_message = "Resource not found"


class UserNotFoundError(NotFoundError):
    """User not found."""

    code = "USER_NOT_FOUND"
    default_message = "User not found"


class DeckNotFoundError(NotFoundError):
    """Deck not found."""

    code = "DECK_NOT_FOUND"
    default_message = "Deck not found"


class CardNotFoundError(NotFoundError):
    """Card not found."""

    code = "CARD_NOT_FOUND"
    default_message = "Card not found"


class DocumentNotFoundError(NotFoundError):
    """Document not found."""

    code = "DOCUMENT_NOT_FOUND"
    default_message = "Document not found"


# ==================== Validation exceptions ====================


class ValidationError(BaseValidationError):
    """Validation error."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"
    default_message = "Validation failed"


class InvalidInputError(ValidationError):
    """Invalid input data."""

    code = "INVALID_INPUT"
    default_message = "Invalid input data"


# ==================== Conflict exceptions ====================


class ConflictError(BaseConflictError):
    """Data conflict."""

    status_code = HTTPStatus.CONFLICT
    code = "CONFLICT"
    default_message = "Resource conflict"


class DuplicateError(ConflictError):
    """Duplicate data."""

    code = "DUPLICATE"
    default_message = "Resource already exists"


class EmailAlreadyExistsError(DuplicateError):
    """Email already in use."""

    code = "EMAIL_ALREADY_EXISTS"
    default_message = "Email is already registered"


class DeckNameExistsError(DuplicateError):
    """Deck name already in use."""

    code = "DECK_NAME_EXISTS"
    default_message = "Deck with this name already exists"


# ==================== External service exceptions ====================


class ExternalServiceError(AppError):
    """External service error."""

    status_code = HTTPStatus.BAD_GATEWAY
    code = "EXTERNAL_SERVICE_ERROR"
    default_message = "External service error"


class LLMServiceError(ExternalServiceError):
    """LLM service error."""

    code = "LLM_SERVICE_ERROR"
    default_message = "LLM service is unavailable"


class AnkiConnectError(ExternalServiceError):
    """AnkiConnect error."""

    code = "ANKI_CONNECT_ERROR"
    default_message = "Failed to connect to Anki"


class PerplexityError(ExternalServiceError):
    """Perplexity API error."""

    code = "PERPLEXITY_ERROR"
    default_message = "Perplexity API error"


# ==================== Rate limit exceptions ====================


class RateLimitError(AppError):
    """Rate limit exceeded."""

    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"
    default_message = "Too many requests"


class QuotaExceededError(AppError):
    """Quota exceeded."""

    status_code = HTTPStatus.PAYMENT_REQUIRED
    code = "QUOTA_EXCEEDED"
    default_message = "Quota exceeded"


# ==================== Database exceptions ====================


class DatabaseError(AppError):
    """Database error."""

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    code = "DATABASE_ERROR"
    default_message = "Database operation failed"


class TransactionError(DatabaseError):
    """Transaction error."""

    code = "TRANSACTION_ERROR"
    default_message = "Transaction failed"


# ==================== Exception handlers ====================


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handler for application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict() if isinstance(exc, AppError) else exc.to_response().model_dump(),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handler for unhandled exceptions."""
    error = AppError()
    return JSONResponse(
        status_code=error.status_code,
        content=error.to_dict(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers in the application."""
    setup_exception_handlers(app)


def error_handler(
    error_class: type[AppError],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for transforming exceptions to AppError.

    Usage:
        @error_handler(DatabaseError)
        async def create_user(...):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except AppError:
                raise
            except Exception as e:
                raise error_class(str(e)) from e

        return wrapper

    return decorator
