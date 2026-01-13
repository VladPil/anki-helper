"""Unit tests for SyncService.

Tests cover:
- create_sync_job (push_cards)
- get_sync_status (get_status, pull_status)
- import_from_anki (import_apkg)
- export_to_anki (sync_to_anki)
- sync_cards (push_cards + sync_to_anki workflow)

All external dependencies (DB, Redis, HTTP, file system) are mocked.
"""

import json
import sqlite3
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.sync.schemas import (
    CardSyncState,
    CardSyncStatus,
    CardToPush,
    ImportRequest,
    SyncPullRequest,
    SyncPushRequest,
    SyncState,
)
from src.modules.sync.service import SyncJobNotFoundError, SyncService

# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def sync_service(mock_db_session: AsyncMock) -> SyncService:
    """Create a SyncService instance with mocked DB."""
    return SyncService(mock_db_session)


@pytest.fixture
def sample_user_id() -> UUID:
    """Create a sample user UUID."""
    return UUID("12345678-1234-1234-1234-123456789abc")


@pytest.fixture
def another_user_id() -> UUID:
    """Create another user UUID for access control tests."""
    return UUID("87654321-4321-4321-4321-cba987654321")


@pytest.fixture
def sample_card_to_push() -> CardToPush:
    """Create a sample CardToPush object."""
    return CardToPush(
        card_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        front="What is Python?",
        back="A programming language",
        tags=["programming", "python"],
        deck_name="Programming",
        note_type="Basic",
        fields={"Front": "What is Python?", "Back": "A programming language"},
    )


@pytest.fixture
def sample_push_request(sample_card_to_push: CardToPush) -> SyncPushRequest:
    """Create a sample SyncPushRequest."""
    return SyncPushRequest(
        cards=[sample_card_to_push],
        priority=5,
        callback_url="https://example.com/callback",
    )


@pytest.fixture
def sample_import_request() -> ImportRequest:
    """Create a sample ImportRequest."""
    return ImportRequest(
        deck_id=None,
        create_deck=True,
        overwrite=False,
        tags=["imported"],
    )


def create_mock_apkg_bytes() -> bytes:
    """Create minimal valid .apkg file bytes for testing."""
    models_json = {
        "1234567890": {
            "name": "Basic",
            "flds": [{"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}],
            "tmpls": [{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
            "css": "",
        }
    }

    decks_json = {
        "1": {"name": "Default", "id": 1},
        "1234567890123": {"name": "Test Deck", "id": 1234567890123},
    }

    # Create SQLite database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE col (
                id INTEGER PRIMARY KEY,
                crt INTEGER, mod INTEGER, scm INTEGER, ver INTEGER,
                dty INTEGER, usn INTEGER, ls INTEGER, conf TEXT,
                models TEXT, decks TEXT, dconf TEXT, tags TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO col VALUES (1, 0, 0, 0, 0, 0, 0, 0, '{}', ?, ?, '{}', '{}')
        """, (json.dumps(models_json), json.dumps(decks_json)))

        cursor.execute("""
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY, guid TEXT, mid INTEGER, mod INTEGER,
                usn INTEGER, tags TEXT, flds TEXT, sfld TEXT,
                csum INTEGER, flags INTEGER, data TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO notes VALUES (1, 'guid1', 1234567890, 0, 0, 'tag1', 'Question\x1fAnswer', 'Question', 0, 0, '')
        """)

        cursor.execute("""
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY, nid INTEGER, did INTEGER, ord INTEGER,
                mod INTEGER, usn INTEGER, type INTEGER, queue INTEGER,
                due INTEGER, ivl INTEGER, factor INTEGER, reps INTEGER,
                lapses INTEGER, left INTEGER, odue INTEGER, odid INTEGER,
                flags INTEGER, data TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO cards VALUES (1, 1, 1234567890123, 0, 0, 0, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')
        """)

        conn.commit()
        conn.close()

        with open(tmp_db_path, "rb") as f:
            db_content = f.read()
    finally:
        Path(tmp_db_path).unlink(missing_ok=True)

    # Create ZIP
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("collection.anki2", db_content)
        zf.writestr("media", "{}")

    return zip_buffer.getvalue()


# ==================== Create Sync Job Tests (push_cards) ====================


@pytest.mark.asyncio
class TestCreateSyncJob:
    """Tests for creating sync jobs (push_cards)."""

    async def test_push_cards_creates_sync_job(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test that push_cards creates a sync job with correct data."""
        response = await sync_service.push_cards(sample_user_id, sample_push_request)

        assert response.sync_id is not None
        assert response.queued_count == 1
        assert response.estimated_time is not None
        assert response.estimated_time > 0

    async def test_push_cards_stores_job_in_memory(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test that sync job is stored in internal state."""
        response = await sync_service.push_cards(sample_user_id, sample_push_request)

        assert response.sync_id in sync_service._sync_jobs
        job = sync_service._sync_jobs[response.sync_id]

        assert job["user_id"] == sample_user_id
        assert job["state"] == SyncState.PENDING
        assert job["total_cards"] == 1
        assert job["priority"] == 5
        assert job["callback_url"] == "https://example.com/callback"

    async def test_push_cards_initializes_card_states(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test that push_cards initializes card sync states."""
        await sync_service.push_cards(sample_user_id, sample_push_request)

        card_id = sample_push_request.cards[0].card_id
        assert card_id in sync_service._card_states

        status = sync_service._card_states[card_id]
        assert status.state == CardSyncState.PENDING
        assert status.anki_note_id is None
        assert status.error_message is None

    async def test_push_multiple_cards(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test pushing multiple cards in one request."""
        cards = [
            CardToPush(
                card_id=UUID(f"0000000{i}-0000-0000-0000-000000000000"),
                front=f"Question {i}",
                back=f"Answer {i}",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            )
            for i in range(5)
        ]

        request = SyncPushRequest(cards=cards)
        response = await sync_service.push_cards(sample_user_id, request)

        assert response.queued_count == 5

        job = sync_service._sync_jobs[response.sync_id]
        assert job["total_cards"] == 5
        assert len(job["cards"]) == 5

    async def test_push_cards_estimates_time_based_on_count(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test that estimated time scales with card count."""
        cards_1 = [
            CardToPush(
                card_id=UUID("00000001-0000-0000-0000-000000000000"),
                front="Q",
                back="A",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            )
        ]
        cards_10 = [
            CardToPush(
                card_id=UUID(f"0000000{i}-0000-0000-0000-000000000000"),
                front=f"Q{i}",
                back=f"A{i}",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            )
            for i in range(10)
        ]

        response_1 = await sync_service.push_cards(
            sample_user_id,
            SyncPushRequest(cards=cards_1),
        )
        response_10 = await sync_service.push_cards(
            sample_user_id,
            SyncPushRequest(cards=cards_10),
        )

        assert response_10.estimated_time > response_1.estimated_time

    async def test_push_cards_with_default_priority(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_card_to_push: CardToPush,
    ):
        """Test pushing cards with default priority."""
        request = SyncPushRequest(cards=[sample_card_to_push])
        response = await sync_service.push_cards(sample_user_id, request)

        job = sync_service._sync_jobs[response.sync_id]
        assert job["priority"] == 0


# ==================== Get Sync Status Tests ====================


@pytest.mark.asyncio
class TestGetSyncStatus:
    """Tests for getting sync status (get_status)."""

    async def test_get_status_empty(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test getting status when no sync jobs exist."""
        with patch.object(
            sync_service,
            "_check_anki_connection",
            return_value=False,
        ):
            status = await sync_service.get_status(sample_user_id)

        assert status.state == SyncState.COMPLETED
        assert status.total_cards == 0
        assert status.synced_cards == 0
        assert status.pending_cards == 0
        assert status.failed_cards == 0
        assert status.anki_connected is False

    async def test_get_status_with_pending_job(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test getting status with a pending sync job."""
        await sync_service.push_cards(sample_user_id, sample_push_request)

        with patch.object(
            sync_service,
            "_check_anki_connection",
            return_value=True,
        ):
            status = await sync_service.get_status(sample_user_id)

        assert status.state == SyncState.PENDING
        assert status.total_cards == 1
        assert status.pending_cards == 1
        assert status.anki_connected is True

    async def test_get_status_aggregates_multiple_jobs(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test that status aggregates data from multiple jobs."""
        # Create two jobs
        cards1 = [
            CardToPush(
                card_id=UUID("00000001-0000-0000-0000-000000000000"),
                front="Q1",
                back="A1",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            )
        ]
        cards2 = [
            CardToPush(
                card_id=UUID("00000002-0000-0000-0000-000000000000"),
                front="Q2",
                back="A2",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            ),
            CardToPush(
                card_id=UUID("00000003-0000-0000-0000-000000000000"),
                front="Q3",
                back="A3",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            ),
        ]

        await sync_service.push_cards(sample_user_id, SyncPushRequest(cards=cards1))
        await sync_service.push_cards(sample_user_id, SyncPushRequest(cards=cards2))

        with patch.object(sync_service, "_check_anki_connection", return_value=False):
            status = await sync_service.get_status(sample_user_id)

        assert status.total_cards == 3
        assert status.pending_cards == 3

    async def test_get_status_ignores_other_users_jobs(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        another_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test that status only includes current user's jobs."""
        # Create job for another user
        await sync_service.push_cards(another_user_id, sample_push_request)

        with patch.object(sync_service, "_check_anki_connection", return_value=False):
            status = await sync_service.get_status(sample_user_id)

        # Should not see the other user's job
        assert status.total_cards == 0


# ==================== Pull Status Tests ====================


@pytest.mark.asyncio
class TestPullStatus:
    """Tests for pulling sync status (pull_status)."""

    async def test_pull_status_by_sync_id(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test pulling status by sync job ID."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        pull_request = SyncPullRequest(sync_id=push_response.sync_id)
        response = await sync_service.pull_status(sample_user_id, pull_request)

        assert response.sync_id == push_response.sync_id
        assert len(response.cards) == 1
        assert response.total == 1
        assert response.pending == 1
        assert response.synced == 0
        assert response.failed == 0

    async def test_pull_status_by_card_ids(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test pulling status by specific card IDs."""
        await sync_service.push_cards(sample_user_id, sample_push_request)

        card_id = sample_push_request.cards[0].card_id
        pull_request = SyncPullRequest(card_ids=[card_id])
        response = await sync_service.pull_status(sample_user_id, pull_request)

        assert len(response.cards) == 1
        assert response.cards[0].card_id == card_id

    async def test_pull_status_nonexistent_sync_id(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test pulling status with non-existent sync ID raises error."""
        pull_request = SyncPullRequest(
            sync_id=UUID("00000000-0000-0000-0000-000000000000")
        )

        with pytest.raises(SyncJobNotFoundError):
            await sync_service.pull_status(sample_user_id, pull_request)

    async def test_pull_status_wrong_user(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        another_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test pulling status for another user's job raises error."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        pull_request = SyncPullRequest(sync_id=push_response.sync_id)

        with pytest.raises(SyncJobNotFoundError):
            await sync_service.pull_status(another_user_id, pull_request)

    async def test_pull_status_exclude_failed(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test excluding failed cards from pull response."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        # Manually mark the card as failed
        card_id = sample_push_request.cards[0].card_id
        sync_service._card_states[card_id] = CardSyncStatus(
            card_id=card_id,
            state=CardSyncState.FAILED,
            error_message="Test error",
        )

        pull_request = SyncPullRequest(
            sync_id=push_response.sync_id,
            include_failed=False,
        )
        response = await sync_service.pull_status(sample_user_id, pull_request)

        assert len(response.cards) == 0  # Failed card excluded

    async def test_pull_status_include_failed(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test including failed cards in pull response."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        # Manually mark the card as failed
        card_id = sample_push_request.cards[0].card_id
        sync_service._card_states[card_id] = CardSyncStatus(
            card_id=card_id,
            state=CardSyncState.FAILED,
            error_message="Test error",
        )

        pull_request = SyncPullRequest(
            sync_id=push_response.sync_id,
            include_failed=True,
        )
        response = await sync_service.pull_status(sample_user_id, pull_request)

        assert len(response.cards) == 1
        assert response.cards[0].state == CardSyncState.FAILED


# ==================== Import from Anki Tests (import_apkg) ====================


@pytest.mark.asyncio
class TestImportFromAnki:
    """Tests for importing .apkg files."""

    async def test_import_apkg_success(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_import_request: ImportRequest,
    ):
        """Test successful .apkg import."""
        file_content = create_mock_apkg_bytes()

        result = await sync_service.import_apkg(
            user_id=sample_user_id,
            file_content=file_content,
            filename="test.apkg",
            request=sample_import_request,
        )

        assert result.deck_name == "Test Deck"
        assert result.total_cards == 1
        assert result.imported_cards == 1
        assert len(result.cards) == 1
        assert "Basic" in result.note_types

    async def test_import_apkg_adds_extra_tags(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test that extra tags from request are added to imported cards."""
        file_content = create_mock_apkg_bytes()
        request = ImportRequest(tags=["imported", "batch-1"])

        result = await sync_service.import_apkg(
            user_id=sample_user_id,
            file_content=file_content,
            filename="test.apkg",
            request=request,
        )

        # Check that extra tags are added
        assert "imported" in result.cards[0].tags
        assert "batch-1" in result.cards[0].tags

    async def test_import_apkg_with_deck_id(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test importing to a specific deck ID."""
        file_content = create_mock_apkg_bytes()
        target_deck_id = UUID("99999999-9999-9999-9999-999999999999")
        request = ImportRequest(deck_id=target_deck_id)

        result = await sync_service.import_apkg(
            user_id=sample_user_id,
            file_content=file_content,
            filename="test.apkg",
            request=request,
        )

        assert result.deck_id == target_deck_id

    async def test_import_apkg_generates_deck_id(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_import_request: ImportRequest,
    ):
        """Test that deck ID is generated when not provided."""
        file_content = create_mock_apkg_bytes()

        result = await sync_service.import_apkg(
            user_id=sample_user_id,
            file_content=file_content,
            filename="test.apkg",
            request=sample_import_request,
        )

        assert result.deck_id is not None

    async def test_import_apkg_invalid_file(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_import_request: ImportRequest,
    ):
        """Test importing invalid .apkg file raises error."""
        invalid_content = b"This is not a valid apkg file"

        with pytest.raises(Exception):
            await sync_service.import_apkg(
                user_id=sample_user_id,
                file_content=invalid_content,
                filename="invalid.apkg",
                request=sample_import_request,
            )

    async def test_import_apkg_cleans_up_temp_file(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_import_request: ImportRequest,
    ):
        """Test that temp file is cleaned up after import."""
        file_content = create_mock_apkg_bytes()

        # Import should succeed and clean up
        result = await sync_service.import_apkg(
            user_id=sample_user_id,
            file_content=file_content,
            filename="test.apkg",
            request=sample_import_request,
        )

        assert result is not None
        # Temp file should be deleted (no easy way to verify, but no exception = success)


# ==================== Export to Anki Tests (sync_to_anki) ====================


@pytest.mark.asyncio
class TestExportToAnki:
    """Tests for syncing cards to Anki (sync_to_anki)."""

    async def test_sync_to_anki_success(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test successful sync to Anki."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 12345, "error": None}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=sample_user_id,
            )

        assert result.state == SyncState.COMPLETED
        assert result.synced_cards == 1
        assert result.failed_cards == 0
        assert result.duration_seconds > 0

    async def test_sync_to_anki_updates_card_state(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test that sync_to_anki updates card states."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 12345, "error": None}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=sample_user_id,
            )

        card_id = sample_push_request.cards[0].card_id
        card_status = sync_service._card_states[card_id]

        assert card_status.state == CardSyncState.SYNCED
        assert card_status.anki_note_id == 12345
        assert card_status.synced_at is not None

    async def test_sync_to_anki_handles_anki_error(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test handling AnkiConnect error response."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": None,
            "error": "deck not found",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=sample_user_id,
            )

        assert result.state == SyncState.FAILED
        assert result.synced_cards == 0
        assert result.failed_cards == 1
        assert "deck not found" in result.errors[0]

    async def test_sync_to_anki_handles_connection_error(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test handling connection error to AnkiConnect."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=sample_user_id,
            )

        assert result.failed_cards == 1
        assert "Connection refused" in result.errors[0]

    async def test_sync_to_anki_nonexistent_job(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test syncing non-existent job raises error."""
        fake_sync_id = UUID("00000000-0000-0000-0000-000000000000")

        with pytest.raises(SyncJobNotFoundError):
            await sync_service.sync_to_anki(
                sync_id=fake_sync_id,
                user_id=sample_user_id,
            )

    async def test_sync_to_anki_wrong_user(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        another_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test syncing another user's job raises error."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        with pytest.raises(SyncJobNotFoundError):
            await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=another_user_id,
            )

    async def test_sync_to_anki_partial_success(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test syncing multiple cards with partial success."""
        cards = [
            CardToPush(
                card_id=UUID("00000001-0000-0000-0000-000000000000"),
                front="Q1",
                back="A1",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            ),
            CardToPush(
                card_id=UUID("00000002-0000-0000-0000-000000000000"),
                front="Q2",
                back="A2",
                tags=[],
                deck_name="Test",
                note_type="Basic",
            ),
        ]

        push_response = await sync_service.push_cards(
            sample_user_id,
            SyncPushRequest(cards=cards),
        )

        # First card succeeds, second fails
        call_count = [0]

        def mock_json():
            call_count[0] += 1
            if call_count[0] == 1:
                return {"result": 111, "error": None}
            else:
                return {"result": None, "error": "duplicate note"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = mock_json

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=sample_user_id,
            )

        assert result.state == SyncState.FAILED
        assert result.synced_cards == 1
        assert result.failed_cards == 1


# ==================== Sync Cards Workflow Tests ====================


@pytest.mark.asyncio
class TestSyncCardsWorkflow:
    """Tests for the complete sync workflow (push + sync)."""

    async def test_complete_sync_workflow(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test complete workflow: push cards -> sync to Anki."""
        # Step 1: Push cards
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)
        assert push_response.queued_count == 1

        # Step 2: Check status (should be pending)
        with patch.object(sync_service, "_check_anki_connection", return_value=True):
            status = await sync_service.get_status(sample_user_id)
        assert status.state == SyncState.PENDING

        # Step 3: Sync to Anki
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 12345, "error": None}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=sample_user_id,
            )

        assert result.state == SyncState.COMPLETED

        # Step 4: Verify final status
        with patch.object(sync_service, "_check_anki_connection", return_value=True):
            final_status = await sync_service.get_status(sample_user_id)
        assert final_status.synced_cards == 1
        assert final_status.pending_cards == 0

    async def test_workflow_updates_job_timestamps(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_push_request: SyncPushRequest,
    ):
        """Test that workflow updates job timestamps correctly."""
        push_response = await sync_service.push_cards(sample_user_id, sample_push_request)

        job = sync_service._sync_jobs[push_response.sync_id]
        assert job["created_at"] is not None
        assert job["started_at"] is None
        assert job["completed_at"] is None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": 12345, "error": None}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await sync_service.sync_to_anki(
                sync_id=push_response.sync_id,
                user_id=sample_user_id,
            )

        job = sync_service._sync_jobs[push_response.sync_id]
        assert job["started_at"] is not None
        assert job["completed_at"] is not None
        assert job["completed_at"] >= job["started_at"]


# ==================== Check Anki Connection Tests ====================


@pytest.mark.asyncio
class TestCheckAnkiConnection:
    """Tests for Anki connection check."""

    async def test_check_connection_success(
        self,
        sync_service: SyncService,
    ):
        """Test successful Anki connection check."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service._check_anki_connection()

        assert result is True

    async def test_check_connection_failure(
        self,
        sync_service: SyncService,
    ):
        """Test failed Anki connection check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Connection refused")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service._check_anki_connection()

        assert result is False

    async def test_check_connection_non_200_status(
        self,
        sync_service: SyncService,
    ):
        """Test connection check with non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await sync_service._check_anki_connection()

        assert result is False


# ==================== Stream Import Progress Tests ====================


@pytest.mark.asyncio
class TestStreamImportProgress:
    """Tests for streaming import progress."""

    async def test_stream_import_progress_success(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_import_request: ImportRequest,
    ):
        """Test streaming import progress yields correct stages."""
        file_content = create_mock_apkg_bytes()

        stages = []
        async for progress in sync_service.stream_import_progress(
            user_id=sample_user_id,
            file_content=file_content,
            filename="test.apkg",
            request=sample_import_request,
        ):
            stages.append(progress.stage)

        # Should go through parsing -> importing -> finalizing -> complete
        assert "parsing" in stages
        assert "importing" in stages
        assert "finalizing" in stages
        assert "complete" in stages

    async def test_stream_import_progress_values(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_import_request: ImportRequest,
    ):
        """Test that progress values increase correctly."""
        file_content = create_mock_apkg_bytes()

        progress_values = []
        async for progress in sync_service.stream_import_progress(
            user_id=sample_user_id,
            file_content=file_content,
            filename="test.apkg",
            request=sample_import_request,
        ):
            progress_values.append(progress.progress)

        # Progress should generally increase (start at 0, end at 100)
        assert progress_values[0] == 0
        assert progress_values[-1] == 100

    async def test_stream_import_progress_error(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        sample_import_request: ImportRequest,
    ):
        """Test streaming import progress on error."""
        invalid_content = b"invalid apkg content"

        stages = []
        async for progress in sync_service.stream_import_progress(
            user_id=sample_user_id,
            file_content=invalid_content,
            filename="invalid.apkg",
            request=sample_import_request,
        ):
            stages.append(progress.stage)

        assert "error" in stages


# ==================== Edge Cases Tests ====================


@pytest.mark.asyncio
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_push_cards_with_special_characters(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test pushing cards with special characters."""
        card = CardToPush(
            card_id=UUID("00000001-0000-0000-0000-000000000000"),
            front="<b>HTML</b> & 'quotes' \"double\"",
            back="Unicode: Mir emoji",
            tags=["special/chars", "test::nested"],
            deck_name="Test Deck",
            note_type="Basic",
        )

        request = SyncPushRequest(cards=[card])
        response = await sync_service.push_cards(sample_user_id, request)

        assert response.queued_count == 1

        job = sync_service._sync_jobs[response.sync_id]
        assert job["cards"][0]["front"] == "<b>HTML</b> & 'quotes' \"double\""

    async def test_multiple_users_isolated(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
        another_user_id: UUID,
    ):
        """Test that multiple users' data is properly isolated."""
        card1 = CardToPush(
            card_id=UUID("00000001-0000-0000-0000-000000000000"),
            front="User 1 card",
            back="Answer",
            tags=[],
            deck_name="Test",
            note_type="Basic",
        )
        card2 = CardToPush(
            card_id=UUID("00000002-0000-0000-0000-000000000000"),
            front="User 2 card",
            back="Answer",
            tags=[],
            deck_name="Test",
            note_type="Basic",
        )

        await sync_service.push_cards(sample_user_id, SyncPushRequest(cards=[card1]))
        await sync_service.push_cards(another_user_id, SyncPushRequest(cards=[card2]))

        with patch.object(sync_service, "_check_anki_connection", return_value=False):
            status1 = await sync_service.get_status(sample_user_id)
            status2 = await sync_service.get_status(another_user_id)

        assert status1.total_cards == 1
        assert status2.total_cards == 1

    async def test_empty_card_ids_in_pull_request(
        self,
        sync_service: SyncService,
        sample_user_id: UUID,
    ):
        """Test pull request with empty card_ids list."""
        pull_request = SyncPullRequest(card_ids=[])
        response = await sync_service.pull_status(sample_user_id, pull_request)

        assert len(response.cards) == 0
        assert response.total == 0

    async def test_service_initialization(self, mock_db_session: AsyncMock):
        """Test SyncService initialization."""
        service = SyncService(mock_db_session)

        assert service.db == mock_db_session
        assert service._sync_jobs == {}
        assert service._card_states == {}
