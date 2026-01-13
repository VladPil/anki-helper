"""SQLAlchemy models for prompts and prompt executions."""

from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.mixins import AuditMixin, TimestampMixin, UUIDMixin


class PromptCategory(str, Enum):
    """Categories for organizing prompts by use case."""

    GENERATION = "generation"
    FACT_CHECK = "fact_check"
    CHAT = "chat"
    IMPROVEMENT = "improvement"


class Prompt(UUIDMixin, TimestampMixin, AuditMixin, Base):
    """Prompt model for storing LLM prompt templates.

    Attributes:
        name: Unique identifier name for the prompt.
        description: Human-readable description of the prompt's purpose.
        category: Category for organizing prompts.
        system_prompt: The system message for the LLM.
        user_prompt_template: Jinja2 template for the user message.
        variables_schema: JSON schema defining required template variables.
        preferred_model_id: Reference to preferred LLM model.
        temperature: LLM temperature setting.
        max_tokens: Maximum tokens for LLM response.
        is_active: Whether the prompt is active and available for use.
        version: Version number for tracking changes.
        parent_id: Reference to parent prompt for version history.
    """

    __tablename__ = "prompts"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[PromptCategory] = mapped_column(
        SQLEnum(PromptCategory, name="prompt_category"),
        nullable=False,
        index=True,
    )
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    variables_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preferred_model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("llm_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("prompts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    parent: Mapped["Prompt | None"] = relationship(
        "Prompt",
        remote_side="Prompt.id",
        backref="children",
    )
    executions: Mapped[list["PromptExecution"]] = relationship(
        "PromptExecution",
        back_populates="prompt",
        cascade="all, delete-orphan",
    )


class PromptExecution(UUIDMixin, TimestampMixin, Base):
    """Model for tracking prompt execution history.

    Attributes:
        prompt_id: Reference to the prompt that was executed.
        user_id: Reference to the user who executed the prompt.
        model_id: Reference to the LLM model used.
        rendered_system_prompt: The rendered system prompt.
        rendered_user_prompt: The rendered user prompt with variables.
        variables: Variables used for rendering.
        response_text: The LLM response text.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        latency_ms: Response latency in milliseconds.
        trace_id: Trace ID for distributed tracing.
    """

    __tablename__ = "prompt_executions"

    prompt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("prompts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("llm_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    rendered_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Relationships
    prompt: Mapped["Prompt | None"] = relationship(
        "Prompt",
        back_populates="executions",
    )
