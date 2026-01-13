"""Background worker for import operations."""

import logging
from dataclasses import dataclass, field
from typing import Callable

import httpx
from PyQt6.QtCore import QThread, pyqtSignal

from src.clients import AnkiConnectClient
from src.config import settings, token_manager
from src.core.import_cache import import_cache

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of import operation."""

    total_cards: int = 0
    imported_cards: int = 0
    skipped_cards: int = 0
    failed_cards: int = 0
    cached_skipped: int = 0  # Skipped due to local cache
    errors: list[str] = field(default_factory=list)


class ImportWorker(QThread):
    """Background worker for importing cards from Anki.

    Imports cards in batches to avoid timeouts and memory issues.
    Uses import cache to skip already imported cards.

    Signals:
        progress: Emitted with (message, current, total) tuple.
        deck_progress: Emitted when starting a new deck (deck_name, card_count).
        finished: Emitted with ImportResult when import completes.
        error: Emitted with error message string on failure.
    """

    progress = pyqtSignal(str, int, int)  # message, current, total
    deck_progress = pyqtSignal(str, int)  # deck_name, card_count
    finished = pyqtSignal(object)  # ImportResult
    error = pyqtSignal(str)

    def __init__(
        self,
        anki_url: str,
        api_url: str,
        token: str,
        batch_size: int = 50,
        timeout: int = 120,
    ) -> None:
        """Initialize the worker.

        Args:
            anki_url: AnkiConnect URL.
            api_url: Backend API URL.
            token: Authentication token.
            batch_size: Number of cards per API request.
            timeout: API request timeout in seconds.
        """
        super().__init__()
        self.anki_url = anki_url
        self.api_url = api_url
        self.token = token
        self.batch_size = batch_size
        self.timeout = timeout
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the import."""
        self._cancelled = True
        logger.info("Import cancellation requested")

    def run(self) -> None:
        """Execute the import operation."""
        result = ImportResult()

        try:
            logger.info("=" * 50)
            logger.info("Starting import from Anki")
            logger.info(f"AnkiConnect URL: {self.anki_url}")
            logger.info(f"API URL: {self.api_url}")
            logger.info(f"Batch size: {self.batch_size}")
            logger.info("=" * 50)

            self.progress.emit("Connecting to Anki...", 0, 100)

            anki_client = AnkiConnectClient(self.anki_url)

            # Get deck list
            decks = anki_client.get_deck_names()
            decks = [d for d in decks if d != "Default"]

            if not decks:
                logger.warning("No decks found in Anki")
                self.progress.emit("No decks found", 100, 100)
                self.finished.emit(result)
                return

            logger.info(f"Found {len(decks)} decks to process")
            self.progress.emit(f"Found {len(decks)} decks", 5, 100)

            # First pass - count total cards
            deck_note_counts = {}
            total_notes = 0

            for deck_name in decks:
                if self._cancelled:
                    logger.info("Import cancelled during counting")
                    self.finished.emit(result)
                    return

                note_ids = anki_client.get_deck_note_ids(deck_name)
                deck_note_counts[deck_name] = len(note_ids)
                total_notes += len(note_ids)
                logger.debug(f"Deck '{deck_name}': {len(note_ids)} notes")

            result.total_cards = total_notes
            logger.info(f"Total notes to process: {total_notes}")
            self.progress.emit(f"Total: {total_notes} cards in {len(decks)} decks", 10, 100)

            if total_notes == 0:
                logger.info("No cards to import")
                self.finished.emit(result)
                return

            # Second pass - import each deck
            processed_cards = 0
            http_client = httpx.Client(timeout=self.timeout)

            try:
                for deck_idx, deck_name in enumerate(decks):
                    if self._cancelled:
                        logger.info("Import cancelled")
                        break

                    note_count = deck_note_counts.get(deck_name, 0)
                    if note_count == 0:
                        continue

                    logger.info(f"Processing deck: {deck_name} ({note_count} notes)")
                    self.deck_progress.emit(deck_name, note_count)

                    # Import this deck in batches
                    deck_result = self._import_deck(
                        anki_client,
                        http_client,
                        deck_name,
                        processed_cards,
                        total_notes,
                    )

                    result.imported_cards += deck_result.imported_cards
                    result.skipped_cards += deck_result.skipped_cards
                    result.failed_cards += deck_result.failed_cards
                    result.cached_skipped += deck_result.cached_skipped
                    result.errors.extend(deck_result.errors)

                    processed_cards += note_count

                    # Update progress
                    progress_pct = int(10 + (processed_cards / total_notes) * 85)
                    self.progress.emit(
                        f"Processed {processed_cards}/{total_notes} cards",
                        progress_pct,
                        100,
                    )

            finally:
                http_client.close()

            # Done
            logger.info("=" * 50)
            logger.info("Import completed")
            logger.info(f"Total: {result.total_cards}")
            logger.info(f"Imported: {result.imported_cards}")
            logger.info(f"Skipped (duplicates): {result.skipped_cards}")
            logger.info(f"Skipped (cached): {result.cached_skipped}")
            logger.info(f"Failed: {result.failed_cards}")
            logger.info(f"Errors: {len(result.errors)}")
            logger.info("=" * 50)

            self.progress.emit("Import completed", 100, 100)
            self.finished.emit(result)

        except Exception as e:
            logger.exception(f"Import failed: {e}")
            self.error.emit(str(e))

    def _import_deck(
        self,
        anki_client: AnkiConnectClient,
        http_client: httpx.Client,
        deck_name: str,
        base_progress: int,
        total_notes: int,
    ) -> ImportResult:
        """Import a single deck in batches.

        Args:
            anki_client: Anki client instance.
            http_client: HTTP client for API calls.
            deck_name: Name of the deck to import.
            base_progress: Base progress count for UI updates.
            total_notes: Total notes across all decks.

        Returns:
            ImportResult for this deck.
        """
        result = ImportResult()

        for batch_idx, total_batches, cards in anki_client.iter_deck_cards(
            deck_name,
            batch_size=settings.import_batch_size,
        ):
            if self._cancelled:
                return result

            # Filter out already cached cards
            original_count = len(cards)
            cards = import_cache.filter_not_imported(cards)
            cached_count = original_count - len(cards)
            result.cached_skipped += cached_count

            if cached_count > 0:
                logger.debug(
                    f"Batch {batch_idx + 1}/{total_batches}: "
                    f"skipped {cached_count} cached cards"
                )

            if not cards:
                continue

            # Send to API in smaller batches
            for i in range(0, len(cards), self.batch_size):
                if self._cancelled:
                    return result

                batch = cards[i : i + self.batch_size]

                try:
                    api_result = self._send_batch_to_api(
                        http_client,
                        deck_name,
                        batch,
                    )

                    result.imported_cards += api_result.imported_cards
                    result.skipped_cards += api_result.skipped_cards
                    result.failed_cards += api_result.failed_cards

                    # Mark successfully imported cards in cache
                    if api_result.imported_cards > 0:
                        imported_ids = [
                            c["anki_note_id"]
                            for c in batch
                            if c.get("anki_note_id")
                        ]
                        import_cache.mark_imported(imported_ids)

                except Exception as e:
                    error_msg = f"API error for '{deck_name}' batch: {str(e)}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    result.failed_cards += len(batch)

        return result

    def _send_batch_to_api(
        self,
        client: httpx.Client,
        deck_name: str,
        cards: list[dict],
    ) -> ImportResult:
        """Send a batch of cards to the API.

        Args:
            client: HTTP client.
            deck_name: Deck name for import.
            cards: List of card data dicts.

        Returns:
            ImportResult for this batch.
        """
        result = ImportResult()

        logger.debug(f"Sending batch of {len(cards)} cards for deck '{deck_name}'")

        response = client.post(
            f"{self.api_url}/api/sync/import/cards",
            json={
                "deck_name": deck_name,
                "cards": [
                    {
                        "front": c["front"],
                        "back": c["back"],
                        "tags": c.get("tags", []),
                        "anki_note_id": c.get("anki_note_id"),
                    }
                    for c in cards
                ],
                "mark_as_synced": True,
            },
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )

        if response.status_code == 201:
            data = response.json()
            result.imported_cards = data.get("imported_cards", 0)
            result.skipped_cards = data.get("skipped_cards", 0)
            result.failed_cards = data.get("failed_cards", 0)

            # Log any errors from API response
            api_errors = data.get("errors", [])
            if api_errors:
                logger.warning(f"API returned errors: {api_errors}")
                result.errors.extend(api_errors)

            logger.info(
                f"Batch result for '{deck_name}': imported={result.imported_cards}, "
                f"skipped={result.skipped_cards}, failed={result.failed_cards}"
            )
        else:
            error_msg = f"API error {response.status_code}: {response.text[:500]}"
            logger.error(f"Failed to import cards to '{deck_name}': {error_msg}")
            result.errors.append(error_msg)
            result.failed_cards = len(cards)

        return result
