"""Pydantic schemas for LLM module."""

from typing import Any

from pydantic import Field

from src.shared.schemas import BaseSchema, UUIDTimestampSchema


class LLMModelBase(BaseSchema):
    """Base schema for LLM model data."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Internal model name",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable display name",
    )
    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Model provider (openai, anthropic, etc.)",
    )
    model_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Provider-specific model identifier",
    )
    max_tokens: int = Field(
        ...,
        gt=0,
        description="Maximum context window in tokens",
    )


class LLMModelCreate(LLMModelBase):
    """Schema for creating an LLM model."""

    supports_vision: bool = Field(
        False,
        description="Whether model supports image inputs",
    )
    supports_functions: bool = Field(
        True,
        description="Whether model supports function calling",
    )
    input_price_per_million: float | None = Field(
        None,
        ge=0,
        description="Input token price per million (USD)",
    )
    output_price_per_million: float | None = Field(
        None,
        ge=0,
        description="Output token price per million (USD)",
    )
    is_active: bool = Field(
        True,
        description="Whether model is available for use",
    )
    extra_config: dict[str, Any] | None = Field(
        None,
        description="Additional model-specific configuration",
    )


class LLMModelUpdate(BaseSchema):
    """Schema for updating an LLM model."""

    display_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
    )
    max_tokens: int | None = Field(None, gt=0)
    supports_vision: bool | None = None
    supports_functions: bool | None = None
    input_price_per_million: float | None = Field(None, ge=0)
    output_price_per_million: float | None = Field(None, ge=0)
    is_active: bool | None = None
    extra_config: dict[str, Any] | None = None


class LLMModelResponse(LLMModelBase, UUIDTimestampSchema):
    """Response schema for LLM model."""

    supports_vision: bool = Field(description="Whether model supports image inputs")
    supports_functions: bool = Field(description="Whether model supports function calling")
    input_price_per_million: float | None = Field(description="Input token price per million (USD)")
    output_price_per_million: float | None = Field(
        description="Output token price per million (USD)"
    )
    is_active: bool = Field(description="Whether model is available for use")
    extra_config: dict[str, Any] | None = Field(
        description="Additional model-specific configuration"
    )


class EmbeddingModelBase(BaseSchema):
    """Base schema for embedding model data."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Internal model name",
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable display name",
    )
    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Model provider (openai, voyage, etc.)",
    )
    model_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Provider-specific model identifier",
    )
    dimension: int = Field(
        ...,
        gt=0,
        description="Embedding vector dimension",
    )


class EmbeddingModelCreate(EmbeddingModelBase):
    """Schema for creating an embedding model."""

    supported_languages: list[str] = Field(
        default=["en"],
        min_length=1,
        description="List of supported language codes",
    )
    is_active: bool = Field(
        True,
        description="Whether model is available for use",
    )


class EmbeddingModelUpdate(BaseSchema):
    """Schema for updating an embedding model."""

    display_name: str | None = Field(None, min_length=1, max_length=255)
    dimension: int | None = Field(None, gt=0)
    supported_languages: list[str] | None = Field(None, min_length=1)
    is_active: bool | None = None


class EmbeddingModelResponse(EmbeddingModelBase, UUIDTimestampSchema):
    """Response schema for embedding model."""

    supported_languages: list[str] = Field(description="List of supported language codes")
    is_active: bool = Field(description="Whether model is available for use")


# Request/Response schemas for LLM operations


class GenerateRequest(BaseSchema):
    """Request schema for text generation."""

    model_id: str = Field(
        ...,
        description="Model identifier to use for generation",
    )
    system_prompt: str = Field(
        ...,
        min_length=1,
        description="System message for context",
    )
    user_prompt: str = Field(
        ...,
        min_length=1,
        description="User message/prompt",
    )
    temperature: float = Field(
        0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        2000,
        gt=0,
        le=100000,
        description="Maximum tokens to generate",
    )


class GenerateResponse(BaseSchema):
    """Response schema for text generation."""

    content: str = Field(description="Generated text content")
    model: str = Field(description="Model used for generation")
    input_tokens: int = Field(description="Number of input tokens")
    output_tokens: int = Field(description="Number of output tokens")
    finish_reason: str = Field(description="Reason generation stopped")


class FactCheckRequest(BaseSchema):
    """Request schema for fact checking."""

    claim: str = Field(
        ...,
        min_length=1,
        description="The claim to fact-check",
    )
    context: str | None = Field(
        None,
        description="Optional context for the claim",
    )


class FactCheckResponse(BaseSchema):
    """Response schema for fact checking."""

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0)",
    )
    sources: list[str] = Field(description="List of sources")
    reasoning: str = Field(description="Reasoning for the confidence score")


class EmbeddingRequest(BaseSchema):
    """Request schema for embeddings."""

    texts: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of texts to embed",
    )
    model_id: str | None = Field(
        None,
        description="Optional embedding model ID",
    )


class EmbeddingResponse(BaseSchema):
    """Response schema for embeddings."""

    embeddings: list[list[float]] = Field(description="List of embedding vectors")
    model: str = Field(description="Model used for embedding")
    dimension: int = Field(description="Embedding dimension")
