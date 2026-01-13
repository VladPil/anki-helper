"""Pydantic models for error handling.

Data structures for error responses and details.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Strict schema for error details."""

    model_config = ConfigDict(extra="allow")

    field: str | None = None
    value: Any | None = None
    expected: Any | None = None
    current: Any | None = None
    required: Any | None = None
    constraint: str | None = None
    resource_id: str | int | None = None
    resource_type: str | None = None
    errors: list[dict[str, Any]] | None = None
    service: str | None = None


class ErrorResponse(BaseModel):
    """Unified error response schema."""

    error: str = Field(..., description="Error code (SNAKE_CASE)")
    message: str = Field(..., description="Human-readable error description")
    details: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = Field(default="", description="Request correlation ID")
