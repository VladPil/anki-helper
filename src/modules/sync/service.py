"""Sync service for managing Anki synchronization queue."""

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import NotFoundError
from src.shared.uuid7 import uuid7

from .apkg_parser import ApkgParser
from .schemas import (
    CardSyncState,
    CardSyncStatus,
    ImportedCard,
    ImportProgress,
    ImportRequest,
    ImportResult,
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncResult,
    SyncState,
    SyncStatus,
)

logger = logging.getLogger(__name__)


class SyncJobNotFoundError(NotFoundError):
    """Sync job not found error."""

    error_code = "SYNC_JOB_NOT_FOUND"
    message = "Sync job not found"


class SyncService:
    """Service for managing Anki synchronization.

    This service provides methods for:
    - Pushing cards to the sync queue
    - Pulling sync status
    - Checking overall sync status
    - Importing .apkg files

    Attributes:
        db: AsyncSession for database operations.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the sync service.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self._sync_jobs: dict[UUID, dict] = {}  # In-memory store for demo
        self._card_states: dict[UUID, CardSyncStatus] = {}  # In-memory store for demo

    async def push_cards(
        self,
        user_id: UUID,
        request: SyncPushRequest,
    ) -> SyncPushResponse:
        """Push cards to the sync queue.

        Args:
            user_id: UUID of the requesting user.
            request: Push request with cards.

        Returns:
            Push response with sync job ID.
        """
        sync_id = uuid7()
        now = datetime.now(UTC)

        # Create sync job
        self._sync_jobs[sync_id] = {
            "id": sync_id,
            "user_id": user_id,
            "state": SyncState.PENDING,
            "total_cards": len(request.cards),
            "synced_cards": 0,
            "failed_cards": 0,
            "pending_cards": len(request.cards),
            "priority": request.priority,
            "callback_url": request.callback_url,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "cards": [card.model_dump() for card in request.cards],
        }

        # Initialize card states
        for card in request.cards:
            self._card_states[card.card_id] = CardSyncStatus(
                card_id=card.card_id,
                state=CardSyncState.PENDING,
                anki_note_id=None,
                error_message=None,
                synced_at=None,
            )

        logger.info(
            "Created sync job %s with %d cards for user %s",
            sync_id,
            len(request.cards),
            user_id,
        )

        # Estimate time based on poll interval and card count
        estimated_time = (
            len(request.cards) * 0.5  # ~0.5 seconds per card
            + settings.app.sync_poll_interval_seconds
        )

        return SyncPushResponse(
            sync_id=sync_id,
            queued_count=len(request.cards),
            estimated_time=int(estimated_time),
        )

    async def pull_status(
        self,
        user_id: UUID,
        request: SyncPullRequest,
    ) -> SyncPullResponse:
        """Pull sync status for cards.

        Args:
            user_id: UUID of the requesting user.
            request: Pull request with sync job or card IDs.

        Returns:
            Pull response with card statuses.
        """
        cards: list[CardSyncStatus] = []

        if request.sync_id:
            # Get status for a specific sync job
            job = self._sync_jobs.get(request.sync_id)
            if job is None:
                raise SyncJobNotFoundError()

            if job["user_id"] != user_id:
                raise SyncJobNotFoundError()  # Don't reveal existence

            for card_data in job["cards"]:
                card_id = (
                    UUID(card_data["card_id"])
                    if isinstance(card_data["card_id"], str)
                    else card_data["card_id"]
                )
                status = self._card_states.get(card_id)
                if status:
                    if not request.include_failed and status.state == CardSyncState.FAILED:
                        continue
                    cards.append(status)

        elif request.card_ids:
            # Get status for specific cards
            for card_id in request.card_ids:
                status = self._card_states.get(card_id)
                if status:
                    if not request.include_failed and status.state == CardSyncState.FAILED:
                        continue
                    cards.append(status)

        # Calculate totals
        synced = sum(1 for c in cards if c.state == CardSyncState.SYNCED)
        pending = sum(1 for c in cards if c.state == CardSyncState.PENDING)
        failed = sum(1 for c in cards if c.state == CardSyncState.FAILED)

        return SyncPullResponse(
            sync_id=request.sync_id,
            cards=cards,
            total=len(cards),
            synced=synced,
            pending=pending,
            failed=failed,
        )

    async def get_status(
        self,
        user_id: UUID,
    ) -> SyncStatus:
        """Get overall sync status for a user.

        Args:
            user_id: UUID of the requesting user.

        Returns:
            Overall sync status.
        """
        # Aggregate status from all user's sync jobs
        total_cards = 0
        synced_cards = 0
        pending_cards = 0
        failed_cards = 0
        last_sync: datetime | None = None
        current_state = SyncState.COMPLETED

        for job in self._sync_jobs.values():
            if job["user_id"] != user_id:
                continue

            total_cards += job["total_cards"]
            synced_cards += job["synced_cards"]
            pending_cards += job["pending_cards"]
            failed_cards += job["failed_cards"]

            if job["state"] == SyncState.IN_PROGRESS:
                current_state = SyncState.IN_PROGRESS
            elif job["state"] == SyncState.PENDING and current_state != SyncState.IN_PROGRESS:
                current_state = SyncState.PENDING

            if job["completed_at"] and (last_sync is None or job["completed_at"] > last_sync):
                last_sync = job["completed_at"]

        # Check Anki connection
        anki_connected = await self._check_anki_connection()

        return SyncStatus(
            state=current_state if total_cards > 0 else SyncState.COMPLETED,
            total_cards=total_cards,
            synced_cards=synced_cards,
            pending_cards=pending_cards,
            failed_cards=failed_cards,
            last_sync=last_sync,
            anki_connected=anki_connected,
        )

    async def _check_anki_connection(self) -> bool:
        """Check if Anki is connected via AnkiConnect.

        Returns:
            True if Anki is connected, False otherwise.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    "http://localhost:8765",
                    json={"action": "version", "version": 6},
                )
                return response.status_code == 200
        except Exception:
            return False

    async def import_apkg(
        self,
        user_id: UUID,
        file_content: bytes,
        filename: str,
        request: ImportRequest,
    ) -> ImportResult:
        """Import an .apkg file.

        Args:
            user_id: UUID of the requesting user.
            file_content: Raw file content.
            filename: Original filename.
            request: Import request options.

        Returns:
            Import result with imported cards.
        """
        parser = ApkgParser()
        imported_cards: list[ImportedCard] = []
        errors: list[str] = []
        note_types: set[str] = set()

        try:
            # Parse the .apkg file
            with NamedTemporaryFile(suffix=".apkg", delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = Path(tmp_file.name)

            try:
                parsed_deck = await parser.parse(tmp_path)

                # Create or get deck ID
                deck_id = request.deck_id or uuid7()
                deck_name = parsed_deck.name

                # Process cards
                for card in parsed_deck.cards:
                    try:
                        card_id = uuid7()

                        # Add additional tags
                        tags = list(card.tags) + request.tags

                        imported_card = ImportedCard(
                            card_id=card_id,
                            front=card.front,
                            back=card.back,
                            tags=tags,
                            note_type=card.note_type,
                        )
                        imported_cards.append(imported_card)
                        note_types.add(card.note_type)

                    except Exception as e:
                        errors.append(f"Failed to import card: {str(e)}")

                logger.info(
                    "Imported %d cards from %s for user %s",
                    len(imported_cards),
                    filename,
                    user_id,
                )

            finally:
                # Clean up temp file
                tmp_path.unlink(missing_ok=True)

            return ImportResult(
                deck_id=deck_id,
                deck_name=deck_name,
                total_cards=len(parsed_deck.cards),
                imported_cards=len(imported_cards),
                skipped_cards=0,
                failed_cards=len(errors),
                cards=imported_cards,
                note_types=list(note_types),
                errors=errors,
            )

        except Exception:
            logger.exception("Failed to import .apkg file %s", filename)
            raise

    async def stream_import_progress(
        self,
        user_id: UUID,
        file_content: bytes,
        filename: str,
        request: ImportRequest,
    ) -> AsyncGenerator[ImportProgress, None]:
        """Stream import progress for large files.

        Args:
            user_id: UUID of the requesting user.
            file_content: Raw file content.
            filename: Original filename.
            request: Import request options.

        Yields:
            Import progress updates.
        """
        yield ImportProgress(
            stage="parsing",
            progress=0,
            current=0,
            total=0,
            message="Parsing .apkg file...",
        )

        parser = ApkgParser()

        try:
            # Parse the .apkg file
            with NamedTemporaryFile(suffix=".apkg", delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = Path(tmp_file.name)

            try:
                parsed_deck = await parser.parse(tmp_path)
                total_cards = len(parsed_deck.cards)

                yield ImportProgress(
                    stage="importing",
                    progress=10,
                    current=0,
                    total=total_cards,
                    message=f"Found {total_cards} cards to import",
                )

                # Process cards in batches
                batch_size = 50
                for i, card in enumerate(parsed_deck.cards):
                    if i % batch_size == 0:
                        progress = 10 + (i / total_cards * 80)
                        yield ImportProgress(
                            stage="importing",
                            progress=progress,
                            current=i,
                            total=total_cards,
                            message=f"Importing card {i + 1} of {total_cards}",
                        )

                yield ImportProgress(
                    stage="finalizing",
                    progress=95,
                    current=total_cards,
                    total=total_cards,
                    message="Finalizing import...",
                )

            finally:
                tmp_path.unlink(missing_ok=True)

            yield ImportProgress(
                stage="complete",
                progress=100,
                current=total_cards,
                total=total_cards,
                message=f"Successfully imported {total_cards} cards",
            )

        except Exception as e:
            yield ImportProgress(
                stage="error",
                progress=0,
                current=0,
                total=0,
                message=f"Import failed: {str(e)}",
            )

    async def sync_to_anki(
        self,
        sync_id: UUID,
        user_id: UUID,
    ) -> SyncResult:
        """Execute sync to Anki for a sync job.

        This method connects to AnkiConnect and syncs the cards.

        Args:
            sync_id: UUID of the sync job.
            user_id: UUID of the requesting user.

        Returns:
            Sync result with statistics.
        """
        from datetime import datetime

        import httpx

        job = self._sync_jobs.get(sync_id)
        if job is None:
            raise SyncJobNotFoundError()

        if job["user_id"] != user_id:
            raise SyncJobNotFoundError()

        start_time = datetime.now(UTC)
        job["state"] = SyncState.IN_PROGRESS
        job["started_at"] = start_time

        synced_count = 0
        failed_count = 0
        errors: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for card_data in job["cards"]:
                    card_id = (
                        UUID(card_data["card_id"])
                        if isinstance(card_data["card_id"], str)
                        else card_data["card_id"]
                    )

                    try:
                        # Create note in Anki via AnkiConnect
                        response = await client.post(
                            "http://localhost:8765",
                            json={
                                "action": "addNote",
                                "version": 6,
                                "params": {
                                    "note": {
                                        "deckName": card_data["deck_name"],
                                        "modelName": card_data["note_type"],
                                        "fields": {
                                            "Front": card_data["front"],
                                            "Back": card_data["back"],
                                            **card_data.get("fields", {}),
                                        },
                                        "tags": card_data.get("tags", []),
                                    }
                                },
                            },
                        )

                        result = response.json()
                        if result.get("error"):
                            raise Exception(result["error"])

                        note_id = result.get("result")

                        # Update card state
                        self._card_states[card_id] = CardSyncStatus(
                            card_id=card_id,
                            state=CardSyncState.SYNCED,
                            anki_note_id=note_id,
                            synced_at=datetime.now(UTC),
                        )
                        synced_count += 1

                    except Exception as e:
                        self._card_states[card_id] = CardSyncStatus(
                            card_id=card_id,
                            state=CardSyncState.FAILED,
                            error_message=str(e),
                        )
                        failed_count += 1
                        errors.append(f"Card {card_id}: {str(e)}")

        except Exception as e:
            logger.exception("Sync job %s failed", sync_id)
            errors.append(f"Sync failed: {str(e)}")

        end_time = datetime.now(UTC)
        duration = (end_time - start_time).total_seconds()

        # Update job state
        job["state"] = SyncState.COMPLETED if failed_count == 0 else SyncState.FAILED
        job["synced_cards"] = synced_count
        job["failed_cards"] = failed_count
        job["pending_cards"] = 0
        job["completed_at"] = end_time

        return SyncResult(
            sync_id=sync_id,
            state=SyncState(job["state"]),
            total_cards=job["total_cards"],
            synced_cards=synced_count,
            failed_cards=failed_count,
            errors=errors,
            duration_seconds=duration,
        )
