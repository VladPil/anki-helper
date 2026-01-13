"""SQLAlchemy models for LLM and embedding models."""

from typing import Any

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.shared.mixins import TimestampMixin, UUIDMixin


class LLMModel(UUIDMixin, TimestampMixin, Base):
    """LLM model configuration.

    Stores information about available LLM models for card generation
    and other text generation tasks.

    Attributes:
        name: Unique identifier name for the model.
        display_name: Human-readable name shown in UI.
        provider: Provider name (e.g., 'openai', 'anthropic', 'sop').
        model_id: Model identifier used by the provider API.
        max_tokens: Maximum context window size in tokens.
        supports_vision: Whether model supports image inputs.
        supports_functions: Whether model supports function calling.
        input_price_per_million: Input token price per million tokens (USD).
        output_price_per_million: Output token price per million tokens (USD).
        is_active: Whether the model is available for use.
        extra_config: Additional model-specific configuration.
    """

    __tablename__ = "llm_models"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_functions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    input_price_per_million: Mapped[float | None] = mapped_column(Float, nullable=True)
    output_price_per_million: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    extra_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class EmbeddingModel(UUIDMixin, TimestampMixin, Base):
    """Embedding model configuration.

    Stores information about available embedding models for
    semantic search and RAG functionality.

    Attributes:
        name: Unique identifier name for the model.
        display_name: Human-readable name shown in UI.
        provider: Provider name (e.g., 'openai', 'huggingface', 'local').
        model_id: Model identifier used by the provider API.
        dimension: Vector dimension size.
        supported_languages: List of supported language codes.
        is_active: Whether the model is available for use.
    """

    __tablename__ = "embedding_models"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    supported_languages: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=["en"], nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
