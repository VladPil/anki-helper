"""Exception handlers for FastAPI.

Centralized exception handling for the application.
Transforms various exception types into unified HTTP responses.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .base import AppError
from .context import trace_id_var
from .schemas import ErrorResponse

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers in FastAPI application.

    Registers handlers for:
    - Business errors (AppError)
    - Validation errors (RequestValidationError)
    - HTTP errors (StarletteHTTPException)
    - Unexpected exceptions (Exception)

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(AppError)
    async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
        """Handle application business errors.

        Transforms AppError into JSON response with appropriate HTTP status.

        Args:
            request: HTTP request
            exc: Business exception

        Returns:
            JSONResponse with error details
        """
        response_model = exc.to_response()
        return JSONResponse(
            status_code=exc.status_code,
            content=response_model.model_dump(),
            headers={"X-Error-Code": exc.code},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle Pydantic validation errors.

        Transforms input validation errors into a readable format.

        Args:
            request: HTTP request
            exc: Validation exception

        Returns:
            JSONResponse with validation error list
        """
        response = ErrorResponse(
            error="VALIDATION_ERROR",
            message="Input validation error",
            details={"errors": exc.errors()},
            trace_id=trace_id_var.get(),
        )
        return JSONResponse(
            status_code=422,
            content=response.model_dump(),
            headers={"X-Error-Code": "VALIDATION_ERROR"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Handle standard HTTP exceptions from FastAPI/Starlette.

        Args:
            request: HTTP request
            exc: HTTP exception

        Returns:
            JSONResponse with HTTP error details
        """
        error_code = f"HTTP_{exc.status_code}"
        response = ErrorResponse(
            error=error_code,
            message=str(exc.detail),
            details={},
            trace_id=trace_id_var.get(),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(),
            headers={"X-Error-Code": error_code},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions (last line of defense).

        Catches all unexpected errors and returns generic 500 response.
        Logs full traceback for investigation.

        Args:
            request: HTTP request
            exc: Any unhandled exception

        Returns:
            JSONResponse with generic error message
        """
        logger.exception("CRITICAL: Unhandled exception")

        response = ErrorResponse(
            error="INTERNAL_SERVER_ERROR",
            message="Internal server error",
            details={},
            trace_id=trace_id_var.get(),
        )
        return JSONResponse(
            status_code=500,
            content=response.model_dump(),
            headers={"X-Error-Code": "INTERNAL_SERVER_ERROR"},
        )


# Alias for backwards compatibility
register_exception_handlers = setup_exception_handlers
