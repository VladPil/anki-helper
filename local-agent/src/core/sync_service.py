"""Sync service for synchronizing cards between AnkiRAG and Anki."""

import logging
from datetime import datetime
from typing import Callable, Optional

from src.clients.anki_client import AnkiConnectClient
from src.clients.api_client import BackendAPIClient
from src.core.exceptions import AnkiConnectError, APIError
from src.core.models import CardData, SyncResult, SyncStatus

logger = logging.getLogger(__name__)


class SyncService:
    """Service for synchronizing cards between AnkiRAG backend and Anki.

    Handles the complete sync workflow:
    1. Fetch approved cards from backend
    2. Create/update notes in Anki
    3. Report sync status back to backend

    Example:
        >>> sync_service = SyncService(anki_client, api_client)
        >>> result = sync_service.sync(progress_callback=print)
        >>> print(f"Synced {result.cards_synced} cards")
    """

    # Tag to mark cards synced by AnkiRAG
    ANKIRAG_TAG = "AnkiRAG"

    def __init__(
        self,
        anki_client: AnkiConnectClient,
        api_client: BackendAPIClient,
        default_deck: str = "AnkiRAG",
        default_model: str = "Basic",
    ) -> None:
        """Initialize the sync service.

        Args:
            anki_client: AnkiConnect client instance.
            api_client: Backend API client instance.
            default_deck: Default deck name for new cards.
            default_model: Default note model for new cards.
        """
        self.anki = anki_client
        self.api = api_client
        self.default_deck = default_deck
        self.default_model = default_model

    def sync(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> SyncResult:
        """Perform full sync operation.

        Args:
            progress_callback: Optional callback for progress updates.

        Returns:
            SyncResult with sync statistics.

        Raises:
            AnkiConnectError: If Anki communication fails.
            APIError: If backend communication fails.
        """
        result = SyncResult(started_at=datetime.utcnow())

        def report(message: str) -> None:
            logger.info(message)
            if progress_callback:
                progress_callback(message)

        try:
            # Step 1: Verify connections
            report("Verifying connections...")
            self._verify_connections()

            # Step 2: Ensure deck exists
            report(f"Ensuring deck '{self.default_deck}' exists...")
            self._ensure_deck_exists()

            # Step 3: Get approved cards from backend
            report("Fetching approved cards from backend...")
            cards = self.api.get_approved_cards(limit=500)
            report(f"Found {len(cards)} approved cards")

            if not cards:
                report("No cards to sync")
                result.completed_at = datetime.utcnow()
                return result

            # Step 4: Process each card
            sync_statuses: list[SyncStatus] = []

            for i, card in enumerate(cards, 1):
                report(f"Processing card {i}/{len(cards)}: {card.id[:8]}...")

                try:
                    note_id = self._sync_card(card)

                    if note_id:
                        result.cards_synced += 1
                        sync_statuses.append(SyncStatus(
                            card_id=card.id,
                            anki_note_id=note_id,
                            synced_at=datetime.utcnow(),
                            status="synced",
                        ))
                    else:
                        result.cards_skipped += 1

                except AnkiConnectError as e:
                    error_msg = f"Anki error for card {card.id}: {e}"
                    logger.error(error_msg)
                    result.cards_failed += 1
                    result.errors.append(error_msg)
                    sync_statuses.append(SyncStatus(
                        card_id=card.id,
                        anki_note_id=0,
                        synced_at=datetime.utcnow(),
                        status="error",
                        error_message=str(e),
                    ))

                except Exception as e:
                    error_msg = f"Error syncing card {card.id}: {e}"
                    logger.exception(error_msg)
                    result.cards_failed += 1
                    result.errors.append(error_msg)

            # Step 5: Report sync statuses to backend
            if sync_statuses:
                report("Updating sync statuses in backend...")
                try:
                    self.api.bulk_update_sync_status(sync_statuses)
                except APIError as e:
                    logger.error(f"Failed to update sync statuses: {e}")
                    result.errors.append(f"Failed to update backend: {e}")

            # Step 6: Report completion
            report("Reporting sync completion...")
            try:
                self.api.report_sync_complete(
                    cards_synced=result.cards_synced,
                    cards_failed=result.cards_failed,
                    errors=result.errors[:10],  # Limit errors sent
                )
            except APIError as e:
                logger.error(f"Failed to report sync completion: {e}")

            result.completed_at = datetime.utcnow()
            report(
                f"Sync complete: {result.cards_synced} synced, "
                f"{result.cards_failed} failed, {result.cards_skipped} skipped"
            )

        except Exception as e:
            error_msg = f"Sync failed: {e}"
            logger.exception(error_msg)
            result.errors.append(error_msg)
            result.completed_at = datetime.utcnow()
            raise

        return result

    def _verify_connections(self) -> None:
        """Verify both Anki and API connections are working."""
        # Check Anki
        try:
            self.anki.get_version()
        except AnkiConnectError as e:
            raise AnkiConnectError(
                f"Cannot connect to Anki: {e}. "
                "Make sure Anki is running with AnkiConnect installed."
            )

        # Check API
        if not self.api.verify_token():
            raise APIError(
                "API authentication failed. Please login again.",
                status_code=401,
            )

    def _ensure_deck_exists(self) -> None:
        """Ensure the target deck exists in Anki."""
        decks = self.anki.get_deck_names()
        if self.default_deck not in decks:
            self.anki.create_deck(self.default_deck)
            logger.info(f"Created deck: {self.default_deck}")

    def _sync_card(self, card: CardData) -> Optional[int]:
        """Sync a single card to Anki.

        Args:
            card: Card data from backend.

        Returns:
            Anki note ID if created/updated, None if skipped.
        """
        # Check if card already exists in Anki
        if card.anki_note_id:
            existing = self._check_existing_note(card.anki_note_id)
            if existing:
                # Card already synced, check for updates
                return self._update_existing_card(card, existing)

        # Check for duplicate by content
        duplicate_id = self._find_duplicate(card)
        if duplicate_id:
            logger.info(f"Card {card.id} appears to be duplicate of note {duplicate_id}")
            return duplicate_id

        # Create new note
        return self._create_note(card)

    def _check_existing_note(self, note_id: int) -> Optional[dict]:
        """Check if a note exists in Anki and return its info."""
        try:
            notes = self.anki.get_notes_info([note_id])
            if notes and notes[0].get("noteId"):
                return notes[0]
        except AnkiConnectError:
            pass
        return None

    def _find_duplicate(self, card: CardData) -> Optional[int]:
        """Find if a card already exists in Anki by content.

        Returns:
            Note ID if duplicate found, None otherwise.
        """
        # Search for cards with same front content
        # Escape special characters in search
        front_escaped = card.front.replace('"', '\\"')[:50]  # Limit search length
        query = f'deck:"{self.default_deck}" "front:{front_escaped}"'

        try:
            note_ids = self.anki.find_notes(query)
            if note_ids:
                return note_ids[0]
        except AnkiConnectError:
            pass

        return None

    def _create_note(self, card: CardData) -> int:
        """Create a new note in Anki.

        Args:
            card: Card data.

        Returns:
            Created note ID.
        """
        deck = card.deck or self.default_deck
        model = card.model or self.default_model

        # Ensure deck exists
        if deck != self.default_deck:
            decks = self.anki.get_deck_names()
            if deck not in decks:
                self.anki.create_deck(deck)

        # Build tags
        tags = list(card.tags) if card.tags else []
        if self.ANKIRAG_TAG not in tags:
            tags.append(self.ANKIRAG_TAG)

        # Add source document tag if available
        if card.source_document:
            source_tag = f"source::{card.source_document.replace(' ', '_')}"
            tags.append(source_tag)

        # Build fields based on model
        fields = self._build_fields(card, model)

        note_id = self.anki.add_note(
            deck_name=deck,
            model_name=model,
            fields=fields,
            tags=tags,
            allow_duplicate=False,
        )

        logger.info(f"Created note {note_id} for card {card.id}")
        return note_id

    def _update_existing_card(
        self,
        card: CardData,
        existing: dict,
    ) -> Optional[int]:
        """Update an existing note if content has changed.

        Args:
            card: Card data from backend.
            existing: Existing note info from Anki.

        Returns:
            Note ID if updated, None if no changes needed.
        """
        note_id = existing["noteId"]
        existing_fields = existing.get("fields", {})

        # Check if update needed
        front_changed = existing_fields.get("Front", {}).get("value") != card.front
        back_changed = existing_fields.get("Back", {}).get("value") != card.back

        if not (front_changed or back_changed):
            logger.debug(f"Note {note_id} unchanged, skipping")
            return None

        # Update fields
        model = card.model or self.default_model
        fields = self._build_fields(card, model)

        self.anki.update_note_fields(note_id, fields)
        logger.info(f"Updated note {note_id} for card {card.id}")

        return note_id

    def _build_fields(self, card: CardData, model: str) -> dict[str, str]:
        """Build field dictionary based on note model.

        Args:
            card: Card data.
            model: Note model name.

        Returns:
            Field name to value mapping.
        """
        if model == "Cloze":
            return {
                "Text": card.front,
                "Extra": card.back,
            }
        else:
            # Basic and most other models
            return {
                "Front": card.front,
                "Back": card.back,
            }

    def trigger_anki_sync(self) -> None:
        """Trigger Anki to sync with AnkiWeb."""
        try:
            self.anki.sync()
            logger.info("Triggered Anki sync with AnkiWeb")
        except AnkiConnectError as e:
            logger.warning(f"Could not trigger Anki sync: {e}")

    def get_local_card_count(self) -> int:
        """Get count of AnkiRAG cards in Anki."""
        try:
            cards = self.anki.find_cards(f"tag:{self.ANKIRAG_TAG}")
            return len(cards)
        except AnkiConnectError:
            return 0

    def cleanup_orphaned_cards(self, dry_run: bool = True) -> list[int]:
        """Find cards in Anki that no longer exist in backend.

        Args:
            dry_run: If True, only report orphaned cards without deleting.

        Returns:
            List of orphaned note IDs.
        """
        # Get all AnkiRAG notes from Anki
        try:
            note_ids = self.anki.find_notes(f"tag:{self.ANKIRAG_TAG}")
        except AnkiConnectError:
            return []

        if not note_ids:
            return []

        # TODO: Implement backend endpoint to check which cards still exist
        logger.info(f"Found {len(note_ids)} AnkiRAG notes in Anki")
        return []
