"""Base exception class for application errors.

Core exception logic with auto-generation of error codes and messages.
"""

import logging
import re
from typing import Any

from pydantic import ValidationError

from .context import trace_id_var
from .schemas import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for all application errors.

    Features:
    - Auto-generates error_code from class name (e.g., NotFoundError -> NOT_FOUND)
    - Auto-generates default_message from docstring
    - Validates details via Pydantic
    - Includes trace_id from context for request correlation
    """

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | ErrorDetail | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.default_message

        if details is not None:
            if isinstance(details, ErrorDetail):
                self.details = details.model_dump(exclude_none=True)
            else:
                try:
                    validated = ErrorDetail(**details)
                    self.details = validated.model_dump(exclude_none=True)
                except ValidationError as e:
                    logger.exception(f"Invalid details in {self.__class__.__name__}: {e}")
                    # Allow arbitrary details if validation fails
                    self.details = details
        else:
            self.details = {}

        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code

        super().__init__(self.message)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-generate code and default_message for subclasses."""
        super().__init_subclass__(**kwargs)

        if cls.__name__ == "AppError":
            return

        # Auto-generate error code from class name
        if "code" not in cls.__dict__:
            name = cls.__name__
            for suffix in ("Exception", "Error"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            cls.code = re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()

        # Auto-generate default message from docstring
        if "default_message" not in cls.__dict__ and cls.__doc__:
            cls.default_message = cls.__doc__.strip().split("\n")[0]

    @property
    def trace_id(self) -> str:
        """Get current trace_id from context."""
        return trace_id_var.get()

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception to dictionary for JSON response."""
        result: dict[str, Any] = {
            "error": self.code,
            "message": self.message,
            "details": self.details,
            "trace_id": self.trace_id,
        }
        return result

    def to_response(self) -> ErrorResponse:
        """Serialize to Pydantic model."""
        return ErrorResponse(
            error=self.code,
            message=self.message,
            details=self.details,
            trace_id=self.trace_id,
        )

    @classmethod
    def openapi_response(cls) -> dict[str, Any]:
        """Generate OpenAPI schema for this exception type."""
        return {
            "model": ErrorResponse,
            "description": cls.default_message,
            "content": {
                "application/json": {
                    "example": {
                        "error": cls.code,
                        "message": cls.default_message,
                        "details": {},
                        "trace_id": "example-trace-id",
                    }
                }
            },
        }
