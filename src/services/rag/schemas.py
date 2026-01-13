"""
Pydantic schemas for RAG module.

Defines request/response models for search, indexing, and duplicate detection.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.shared.schemas import BaseSchema


class SearchType(str, Enum):
    """Type of search to perform."""

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class CardStatus(str, Enum):
    """Card status filter."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SYNCED = "synced"


# --- Search Schemas ---


class SearchRequest(BaseSchema):
    """Request schema for similarity search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Search query text",
    )
    user_id: UUID = Field(
        ...,
        description="User ID to scope the search",
    )
    k: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of results to return",
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold (0-1)",
    )
    search_type: SearchType = Field(
        default=SearchType.VECTOR,
        description="Type of search to perform",
    )
    deck_ids: list[UUID] | None = Field(
        default=None,
        description="Filter by specific deck IDs",
    )
    statuses: list[CardStatus] | None = Field(
        default=None,
        description="Filter by card statuses",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Filter by tags",
    )


class SearchResult(BaseSchema):
    """Single search result with card data and similarity score."""

    card_id: UUID = Field(description="Card UUID")
    deck_id: UUID = Field(description="Deck UUID")
    deck_name: str = Field(description="Deck name")
    fields: dict[str, str] = Field(description="Card fields (front, back, etc.)")
    tags: list[str] = Field(default_factory=list, description="Card tags")
    status: CardStatus = Field(description="Card status")
    similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Similarity score (0-1)",
    )
    content_text: str = Field(description="Indexed content text")
    created_at: datetime = Field(description="Card creation timestamp")


class SearchResponse(BaseSchema):
    """Response schema for similarity search."""

    results: list[SearchResult] = Field(
        default_factory=list,
        description="Search results sorted by similarity",
    )
    total: int = Field(
        ge=0,
        description="Total number of results found",
    )
    query: str = Field(description="Original search query")
    search_type: SearchType = Field(description="Search type used")
    threshold: float = Field(description="Similarity threshold applied")
    latency_ms: int = Field(
        ge=0,
        description="Search latency in milliseconds",
    )


# --- Index Schemas ---


class IndexRequest(BaseSchema):
    """Request schema for indexing cards."""

    user_id: UUID = Field(
        ...,
        description="User ID whose cards to index",
    )
    card_ids: list[UUID] | None = Field(
        default=None,
        description="Specific card IDs to index. If None, index all user's cards.",
    )
    force_reindex: bool = Field(
        default=False,
        description="Force reindexing even if embeddings exist",
    )


class IndexResponse(BaseSchema):
    """Response schema for indexing operation."""

    indexed_count: int = Field(
        ge=0,
        description="Number of cards indexed",
    )
    skipped_count: int = Field(
        ge=0,
        description="Number of cards skipped (already indexed)",
    )
    failed_count: int = Field(
        ge=0,
        description="Number of cards that failed to index",
    )
    failed_card_ids: list[UUID] = Field(
        default_factory=list,
        description="IDs of cards that failed to index",
    )
    latency_ms: int = Field(
        ge=0,
        description="Total indexing latency in milliseconds",
    )


class ReindexRequest(BaseSchema):
    """Request schema for reindexing all cards."""

    user_id: UUID = Field(
        ...,
        description="User ID whose cards to reindex",
    )
    delete_existing: bool = Field(
        default=True,
        description="Delete existing embeddings before reindexing",
    )


class ReindexResponse(BaseSchema):
    """Response schema for reindex operation."""

    deleted_count: int = Field(
        ge=0,
        description="Number of old embeddings deleted",
    )
    indexed_count: int = Field(
        ge=0,
        description="Number of cards reindexed",
    )
    failed_count: int = Field(
        ge=0,
        description="Number of cards that failed to reindex",
    )
    latency_ms: int = Field(
        ge=0,
        description="Total reindex latency in milliseconds",
    )


class RemoveFromIndexRequest(BaseSchema):
    """Request schema for removing a card from the index."""

    card_id: UUID = Field(
        ...,
        description="Card ID to remove from index",
    )


class RemoveFromIndexResponse(BaseSchema):
    """Response schema for remove from index operation."""

    success: bool = Field(description="Whether the removal was successful")
    card_id: UUID = Field(description="Card ID that was removed")
    message: str = Field(description="Status message")


# --- Duplicate Detection Schemas ---


class DuplicateCheckRequest(BaseSchema):
    """Request schema for checking duplicate cards."""

    user_id: UUID = Field(
        ...,
        description="User ID to check against",
    )
    cards: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Cards to check for duplicates. Each dict should have 'temp_id' and 'fields'.",
    )
    threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for duplicate detection",
    )


class DuplicateMatch(BaseSchema):
    """A potential duplicate match."""

    existing_card_id: UUID = Field(description="ID of the existing card")
    existing_card_fields: dict[str, str] = Field(description="Fields of the existing card")
    similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Similarity score",
    )


class DuplicateResult(BaseSchema):
    """Duplicate check result for a single card."""

    temp_id: str = Field(description="Temporary ID of the new card")
    is_duplicate: bool = Field(description="Whether duplicates were found")
    matches: list[DuplicateMatch] = Field(
        default_factory=list,
        description="List of potential duplicate matches",
    )
    highest_similarity: float = Field(
        ge=0.0,
        le=1.0,
        description="Highest similarity score found",
    )


class DuplicateCheckResponse(BaseSchema):
    """Response schema for duplicate check."""

    results: list[DuplicateResult] = Field(
        default_factory=list,
        description="Duplicate check results for each card",
    )
    duplicates_found: int = Field(
        ge=0,
        description="Total number of cards with duplicates",
    )
    latency_ms: int = Field(
        ge=0,
        description="Duplicate check latency in milliseconds",
    )


# --- Embedding Schemas ---


class EmbeddingRequest(BaseSchema):
    """Request schema for generating embeddings."""

    texts: list[str] = Field(
        ...,
        min_length=1,
        description="Texts to generate embeddings for",
    )


class EmbeddingResult(BaseSchema):
    """Single embedding result."""

    text: str = Field(description="Original text")
    embedding: list[float] = Field(description="Embedding vector")
    dimension: int = Field(description="Vector dimension")


class EmbeddingResponse(BaseSchema):
    """Response schema for embedding generation."""

    results: list[EmbeddingResult] = Field(
        default_factory=list,
        description="Generated embeddings",
    )
    model: str = Field(description="Model used for generation")
    provider: str = Field(description="Provider used (openai, huggingface, local)")
    total_tokens: int | None = Field(
        default=None,
        description="Total tokens processed (if available)",
    )


# --- Stats Schemas ---


class IndexStatsResponse(BaseSchema):
    """Response schema for index statistics."""

    total_cards: int = Field(
        ge=0,
        description="Total number of cards",
    )
    indexed_cards: int = Field(
        ge=0,
        description="Number of indexed cards",
    )
    unindexed_cards: int = Field(
        ge=0,
        description="Number of unindexed cards",
    )
    coverage_percent: float = Field(
        ge=0.0,
        le=100.0,
        description="Indexing coverage percentage",
    )


# --- Similar Cards Schemas ---


class SimilarCardsResponse(BaseSchema):
    """Response schema for similar cards search."""

    card_id: UUID = Field(description="Source card ID")
    similar_cards: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of similar cards",
    )
    count: int = Field(
        ge=0,
        description="Number of similar cards found",
    )
