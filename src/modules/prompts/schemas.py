"""Pydantic schemas for prompts."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import PromptCategory


class PromptCreate(BaseModel):
    """Schema for creating a new prompt."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique identifier name for the prompt",
    )
    description: str | None = Field(
        None,
        description="Human-readable description of the prompt's purpose",
    )
    category: PromptCategory = Field(
        ...,
        description="Category for organizing prompts",
    )
    system_prompt: str = Field(
        ...,
        min_length=1,
        description="The system message for the LLM",
    )
    user_prompt_template: str = Field(
        ...,
        min_length=1,
        description="Jinja2 template for the user message",
    )
    variables_schema: dict[str, Any] = Field(
        ...,
        description="JSON schema defining required template variables",
    )
    preferred_model_id: UUID | None = Field(
        None,
        description="Reference to preferred LLM model",
    )
    temperature: float = Field(
        0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature setting",
    )
    max_tokens: int = Field(
        2000,
        ge=1,
        le=100000,
        description="Maximum tokens for LLM response",
    )

    @field_validator("variables_schema")
    @classmethod
    def validate_variables_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that variables_schema is a valid JSON Schema structure."""
        if not isinstance(v, dict):
            raise ValueError("variables_schema must be a dictionary")
        # Ensure it has basic JSON Schema structure
        if "type" not in v and "properties" not in v:
            # Allow empty schema
            if v:
                raise ValueError("variables_schema must have 'type' or 'properties' key")
        return v


class PromptUpdate(BaseModel):
    """Schema for updating an existing prompt."""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
    )
    description: str | None = None
    category: PromptCategory | None = None
    system_prompt: str | None = Field(
        None,
        min_length=1,
    )
    user_prompt_template: str | None = Field(
        None,
        min_length=1,
    )
    variables_schema: dict[str, Any] | None = None
    preferred_model_id: UUID | None = None
    temperature: float | None = Field(
        None,
        ge=0.0,
        le=2.0,
    )
    max_tokens: int | None = Field(
        None,
        ge=1,
        le=100000,
    )
    is_active: bool | None = None

    @field_validator("variables_schema")
    @classmethod
    def validate_variables_schema(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate that variables_schema is a valid JSON Schema structure."""
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("variables_schema must be a dictionary")
        if "type" not in v and "properties" not in v:
            if v:
                raise ValueError("variables_schema must have 'type' or 'properties' key")
        return v


class PromptResponse(BaseModel):
    """Schema for prompt response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    category: PromptCategory
    system_prompt: str
    user_prompt_template: str
    variables_schema: dict[str, Any]
    preferred_model_id: UUID | None
    temperature: float
    max_tokens: int
    is_active: bool
    version: int
    parent_id: UUID | None
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    updated_by: str | None


class PromptListResponse(BaseModel):
    """Schema for paginated prompt list response."""

    items: list[PromptResponse]
    total: int
    page: int
    size: int
    pages: int


class RenderRequest(BaseModel):
    """Schema for prompt rendering request."""

    variables: dict[str, Any] = Field(
        ...,
        description="Variables to render into the prompt template",
    )


class RenderResponse(BaseModel):
    """Schema for rendered prompt response."""

    system_prompt: str = Field(
        ...,
        description="The rendered system prompt",
    )
    user_prompt: str = Field(
        ...,
        description="The rendered user prompt with variables",
    )
    prompt_id: UUID = Field(
        ...,
        description="The ID of the prompt that was rendered",
    )
    prompt_version: int = Field(
        ...,
        description="The version of the prompt that was rendered",
    )


class PromptExecutionCreate(BaseModel):
    """Schema for creating a prompt execution record."""

    prompt_id: UUID | None = None
    user_id: UUID | None = None
    model_id: UUID | None = None
    rendered_system_prompt: str
    rendered_user_prompt: str
    variables: dict[str, Any]
    response_text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None
    trace_id: str | None = None


class PromptExecutionResponse(BaseModel):
    """Schema for prompt execution response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prompt_id: UUID | None
    user_id: UUID | None
    model_id: UUID | None
    rendered_system_prompt: str
    rendered_user_prompt: str
    variables: dict[str, Any]
    response_text: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    trace_id: str | None
    created_at: datetime


class PromptExecutionListResponse(BaseModel):
    """Schema for paginated prompt execution list response."""

    items: list[PromptExecutionResponse]
    total: int
    page: int
    size: int
    pages: int
