"""Domain models for AnkiRAG Agent."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CardData(BaseModel):
    """Flashcard data from the backend.

    Represents a card that has been approved for syncing to Anki.

    Attributes:
        id: Unique identifier in the backend.
        front: Question/front side content.
        back: Answer/back side content.
        tags: List of tags to apply to the card.
        deck: Target deck name (uses default if None).
        model: Anki note model name (uses default if None).
        created_at: When the card was created.
        updated_at: When the card was last modified.
        source_document: Name of the source document.
        anki_note_id: Anki note ID if already synced.
    """
    id: str
    front: str
    back: str
    tags: list[str] = []
    deck: Optional[str] = None
    model: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source_document: Optional[str] = None
    anki_note_id: Optional[int] = None


class SyncStatus(BaseModel):
    """Sync status for a single card.

    Used to report sync results back to the backend.

    Attributes:
        card_id: Backend card ID.
        anki_note_id: Anki note ID after sync.
        synced_at: Timestamp of sync attempt.
        status: Result status ("synced", "error", "conflict").
        error_message: Error details if sync failed.
    """
    card_id: str
    anki_note_id: int
    synced_at: datetime
    status: str  # "synced", "error", "conflict"
    error_message: Optional[str] = None


@dataclass
class SyncResult:
    """Result of a sync operation.

    Aggregates statistics and errors from a complete sync run.

    Attributes:
        cards_synced: Number of successfully synced cards.
        cards_failed: Number of cards that failed to sync.
        cards_skipped: Number of cards skipped (already up-to-date).
        errors: List of error messages encountered.
        started_at: When sync started.
        completed_at: When sync finished.
    """
    cards_synced: int = 0
    cards_failed: int = 0
    cards_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def total_processed(self) -> int:
        """Total number of cards processed."""
        return self.cards_synced + self.cards_failed + self.cards_skipped

    @property
    def success_rate(self) -> float:
        """Ratio of successfully synced cards to total processed."""
        if self.total_processed == 0:
            return 0.0
        return self.cards_synced / self.total_processed
