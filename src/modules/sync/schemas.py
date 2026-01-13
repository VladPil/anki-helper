"""Pydantic schemas for sync module."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from src.shared.schemas import BaseSchema


class SyncState(StrEnum):
    """Enumeration of sync states."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CardSyncState(StrEnum):
    """Enumeration of individual card sync states."""

    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


# ==================== Sync Push Schemas ====================


class CardToPush(BaseSchema):
    """Schema for a card to be pushed to sync queue.

    Attributes:
        card_id: UUID of the card to sync.
        front: Card front content.
        back: Card back content.
        tags: List of card tags.
        deck_name: Target deck name in Anki.
        note_type: Note type name in Anki.
        fields: Additional note fields.
    """

    card_id: UUID = Field(description="UUID of the card to sync")
    front: str = Field(description="Card front content")
    back: str = Field(description="Card back content")
    tags: list[str] = Field(
        default_factory=list,
        description="List of card tags",
    )
    deck_name: str = Field(description="Target deck name in Anki")
    note_type: str = Field(
        default="Basic",
        description="Note type name in Anki",
    )
    fields: dict[str, str] = Field(
        default_factory=dict,
        description="Additional note fields",
    )


class SyncPushRequest(BaseSchema):
    """Schema for pushing cards to sync queue.

    Attributes:
        cards: List of cards to push.
        priority: Sync priority (higher = faster).
        callback_url: Optional URL to call when sync completes.
    """

    cards: list[CardToPush] = Field(
        min_length=1,
        max_length=1000,
        description="List of cards to push",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Sync priority (higher = faster)",
    )
    callback_url: str | None = Field(
        default=None,
        description="Optional URL to call when sync completes",
    )


class SyncPushResponse(BaseSchema):
    """Response schema for sync push operation.

    Attributes:
        sync_id: UUID of the created sync job.
        queued_count: Number of cards queued.
        estimated_time: Estimated time to completion in seconds.
    """

    sync_id: UUID = Field(description="UUID of the created sync job")
    queued_count: int = Field(description="Number of cards queued")
    estimated_time: int | None = Field(
        default=None,
        description="Estimated time to completion in seconds",
    )


# ==================== Sync Pull Schemas ====================


class SyncPullRequest(BaseSchema):
    """Schema for pulling synced card statuses.

    Attributes:
        sync_id: UUID of the sync job to query.
        card_ids: Optional list of specific card IDs to query.
        include_failed: Whether to include failed cards.
    """

    sync_id: UUID | None = Field(
        default=None,
        description="UUID of the sync job to query",
    )
    card_ids: list[UUID] | None = Field(
        default=None,
        description="Optional list of specific card IDs to query",
    )
    include_failed: bool = Field(
        default=True,
        description="Whether to include failed cards",
    )


class CardSyncStatus(BaseSchema):
    """Schema for individual card sync status.

    Attributes:
        card_id: UUID of the card.
        state: Current sync state.
        anki_note_id: Anki note ID if synced.
        error_message: Error message if failed.
        synced_at: Timestamp when synced.
    """

    card_id: UUID = Field(description="UUID of the card")
    state: CardSyncState = Field(description="Current sync state")
    anki_note_id: int | None = Field(
        default=None,
        description="Anki note ID if synced",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if failed",
    )
    synced_at: datetime | None = Field(
        default=None,
        description="Timestamp when synced",
    )


class SyncPullResponse(BaseSchema):
    """Response schema for sync pull operation.

    Attributes:
        sync_id: UUID of the sync job.
        cards: List of card sync statuses.
        total: Total number of cards.
        synced: Number of successfully synced cards.
        pending: Number of pending cards.
        failed: Number of failed cards.
    """

    sync_id: UUID | None = Field(description="UUID of the sync job")
    cards: list[CardSyncStatus] = Field(description="List of card sync statuses")
    total: int = Field(description="Total number of cards")
    synced: int = Field(description="Number of successfully synced cards")
    pending: int = Field(description="Number of pending cards")
    failed: int = Field(description="Number of failed cards")


# ==================== Sync Status Schemas ====================


class SyncStatus(BaseSchema):
    """Schema for overall sync status.

    Attributes:
        state: Current sync state.
        total_cards: Total number of cards in queue.
        synced_cards: Number of synced cards.
        pending_cards: Number of pending cards.
        failed_cards: Number of failed cards.
        started_at: Timestamp when sync started.
        completed_at: Timestamp when sync completed.
        last_sync: Timestamp of last successful sync.
        anki_connected: Whether Anki is connected.
    """

    state: SyncState = Field(description="Current sync state")
    total_cards: int = Field(default=0, description="Total number of cards in queue")
    synced_cards: int = Field(default=0, description="Number of synced cards")
    pending_cards: int = Field(default=0, description="Number of pending cards")
    failed_cards: int = Field(default=0, description="Number of failed cards")
    started_at: datetime | None = Field(
        default=None,
        description="Timestamp when sync started",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Timestamp when sync completed",
    )
    last_sync: datetime | None = Field(
        default=None,
        description="Timestamp of last successful sync",
    )
    anki_connected: bool = Field(
        default=False,
        description="Whether Anki is connected",
    )


class SyncResult(BaseSchema):
    """Schema for sync result.

    Attributes:
        sync_id: UUID of the sync job.
        state: Final sync state.
        total_cards: Total number of cards processed.
        synced_cards: Number of successfully synced cards.
        failed_cards: Number of failed cards.
        errors: List of error messages.
        duration_seconds: Sync duration in seconds.
    """

    sync_id: UUID = Field(description="UUID of the sync job")
    state: SyncState = Field(description="Final sync state")
    total_cards: int = Field(description="Total number of cards processed")
    synced_cards: int = Field(description="Number of successfully synced cards")
    failed_cards: int = Field(description="Number of failed cards")
    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages",
    )
    duration_seconds: float = Field(description="Sync duration in seconds")


# ==================== Import Schemas ====================


class ImportRequest(BaseSchema):
    """Schema for importing an .apkg file.

    Attributes:
        deck_id: Optional UUID of target deck.
        create_deck: Whether to create deck if not exists.
        overwrite: Whether to overwrite existing cards.
        tags: Additional tags to add to imported cards.
    """

    deck_id: UUID | None = Field(
        default=None,
        description="Optional UUID of target deck",
    )
    create_deck: bool = Field(
        default=True,
        description="Whether to create deck if not exists",
    )
    overwrite: bool = Field(
        default=False,
        description="Whether to overwrite existing cards",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Additional tags to add to imported cards",
    )


class ImportedCard(BaseSchema):
    """Schema for an imported card.

    Attributes:
        card_id: UUID of the created card.
        front: Card front content.
        back: Card back content.
        tags: Card tags.
        note_type: Note type name.
    """

    card_id: UUID = Field(description="UUID of the created card")
    front: str = Field(description="Card front content")
    back: str = Field(description="Card back content")
    tags: list[str] = Field(default_factory=list, description="Card tags")
    note_type: str = Field(description="Note type name")


class ImportResult(BaseSchema):
    """Schema for import result.

    Attributes:
        deck_id: UUID of the deck.
        deck_name: Name of the deck.
        total_cards: Total number of cards in file.
        imported_cards: Number of successfully imported cards.
        skipped_cards: Number of skipped cards.
        failed_cards: Number of failed cards.
        cards: List of imported cards.
        note_types: List of note types found.
        errors: List of error messages.
    """

    deck_id: UUID = Field(description="UUID of the deck")
    deck_name: str = Field(description="Name of the deck")
    total_cards: int = Field(description="Total number of cards in file")
    imported_cards: int = Field(description="Number of successfully imported cards")
    skipped_cards: int = Field(description="Number of skipped cards")
    failed_cards: int = Field(description="Number of failed cards")
    cards: list[ImportedCard] = Field(
        default_factory=list,
        description="List of imported cards",
    )
    note_types: list[str] = Field(
        default_factory=list,
        description="List of note types found",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="List of error messages",
    )


class ImportProgress(BaseSchema):
    """Schema for import progress.

    Attributes:
        stage: Current import stage.
        progress: Progress percentage (0-100).
        current: Current item being processed.
        total: Total items to process.
        message: Progress message.
    """

    stage: str = Field(description="Current import stage")
    progress: float = Field(ge=0, le=100, description="Progress percentage")
    current: int = Field(description="Current item being processed")
    total: int = Field(description="Total items to process")
    message: str = Field(description="Progress message")
