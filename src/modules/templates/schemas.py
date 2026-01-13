"""Pydantic schemas for card templates."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FieldSchema(BaseModel):
    """Schema for field definition within fields_schema."""

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern=r"^(text|html|image|audio|cloze)$")
    required: bool = True
    description: str | None = None
    default: str | None = None


class TemplateFieldCreate(BaseModel):
    """Schema for creating a template field."""

    name: str = Field(..., min_length=1, max_length=100)
    field_type: str = Field(..., pattern=r"^(text|html|image|audio|cloze)$")
    is_required: bool = True
    order: int = Field(..., ge=0)


class TemplateFieldResponse(BaseModel):
    """Schema for template field response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    name: str
    field_type: str
    is_required: bool
    order: int


class TemplateCreate(BaseModel):
    """Schema for creating a new card template."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier name for the template",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable name shown in UI",
    )
    fields_schema: dict[str, Any] = Field(
        ...,
        description="JSON schema defining the fields structure",
    )
    front_template: str = Field(
        ...,
        min_length=1,
        description="HTML/Jinja2 template for card front",
    )
    back_template: str = Field(
        ...,
        min_length=1,
        description="HTML/Jinja2 template for card back",
    )
    css: str | None = Field(
        None,
        description="Optional CSS styles for the card",
    )
    fields: list[TemplateFieldCreate] | None = Field(
        None,
        description="List of field definitions",
    )

    @field_validator("fields_schema")
    @classmethod
    def validate_fields_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that fields_schema has required structure."""
        if not isinstance(v, dict):
            raise ValueError("fields_schema must be a dictionary")
        if "fields" not in v:
            raise ValueError("fields_schema must contain 'fields' key")
        if not isinstance(v["fields"], list):
            raise ValueError("fields_schema['fields'] must be a list")
        return v


class TemplateUpdate(BaseModel):
    """Schema for updating an existing card template."""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
    )
    display_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
    )
    fields_schema: dict[str, Any] | None = None
    front_template: str | None = Field(
        None,
        min_length=1,
    )
    back_template: str | None = Field(
        None,
        min_length=1,
    )
    css: str | None = None
    fields: list[TemplateFieldCreate] | None = None

    @field_validator("fields_schema")
    @classmethod
    def validate_fields_schema(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate that fields_schema has required structure if provided."""
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("fields_schema must be a dictionary")
        if "fields" not in v:
            raise ValueError("fields_schema must contain 'fields' key")
        if not isinstance(v["fields"], list):
            raise ValueError("fields_schema['fields'] must be a list")
        return v


class TemplateResponse(BaseModel):
    """Schema for card template response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    fields_schema: dict[str, Any]
    front_template: str
    back_template: str
    css: str | None
    is_system: bool
    owner_id: UUID | None
    created_at: datetime
    updated_at: datetime
    fields: list[TemplateFieldResponse] = []


class TemplateListResponse(BaseModel):
    """Schema for paginated template list response."""

    items: list[TemplateResponse]
    total: int
    page: int
    size: int
    pages: int
