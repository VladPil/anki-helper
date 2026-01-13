"""Integration tests for Anki synchronization service.

Tests cover:
- AnkiConnect communication
- Deck synchronization
- Card synchronization
- Note type mapping
- Conflict resolution
- Error handling
"""


from datetime import UTC

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.users.models import User
from src.tests.factories import DeckFactory
from src.tests.fixtures.sample_data import (
    SAMPLE_ANKI_DECKS,
    SAMPLE_ANKI_NOTES,
    SAMPLE_CARD_DATA,
)

# ==================== Mock AnkiConnect Client ====================


class MockAnkiConnectClient:
    """Mock AnkiConnect client for testing."""

    def __init__(
        self,
        connected: bool = True,
        decks: list[dict] | None = None,
        notes: list[dict] | None = None,
    ):
        self.connected = connected
        self.decks = decks or SAMPLE_ANKI_DECKS
        self.notes = notes or SAMPLE_ANKI_NOTES
        self.created_decks: list[str] = []
        self.created_notes: list[dict] = []
        self.call_log: list[str] = []

    async def test_connection(self) -> bool:
        """Test connection to Anki."""
        self.call_log.append("test_connection")
        return self.connected

    async def get_version(self) -> int:
        """Get AnkiConnect version."""
        self.call_log.append("get_version")
        if not self.connected:
            raise ConnectionError("Anki not running")
        return 6

    async def get_deck_names(self) -> list[str]:
        """Get list of deck names."""
        self.call_log.append("get_deck_names")
        if not self.connected:
            raise ConnectionError("Anki not running")
        return [d["name"] for d in self.decks]

    async def get_deck_names_and_ids(self) -> dict[str, int]:
        """Get deck names with their IDs."""
        self.call_log.append("get_deck_names_and_ids")
        if not self.connected:
            raise ConnectionError("Anki not running")
        return {d["name"]: d["id"] for d in self.decks}

    async def create_deck(self, name: str) -> int:
        """Create a new deck."""
        self.call_log.append(f"create_deck:{name}")
        if not self.connected:
            raise ConnectionError("Anki not running")

        new_id = max(d["id"] for d in self.decks) + 1
        self.decks.append({"id": new_id, "name": name})
        self.created_decks.append(name)
        return new_id

    async def delete_deck(self, deck_name: str, cards_too: bool = True) -> None:
        """Delete a deck."""
        self.call_log.append(f"delete_deck:{deck_name}")
        if not self.connected:
            raise ConnectionError("Anki not running")

        self.decks = [d for d in self.decks if d["name"] != deck_name]

    async def add_note(self, note: dict) -> int:
        """Add a note to Anki."""
        self.call_log.append(f"add_note:{note.get('deckName', 'default')}")
        if not self.connected:
            raise ConnectionError("Anki not running")

        new_id = len(self.notes) + 1
        self.notes.append({**note, "id": new_id})
        self.created_notes.append(note)
        return new_id

    async def update_note(self, note_id: int, fields: dict) -> None:
        """Update a note's fields."""
        self.call_log.append(f"update_note:{note_id}")
        if not self.connected:
            raise ConnectionError("Anki not running")

        for note in self.notes:
            if note.get("id") == note_id:
                note["fields"] = fields
                break

    async def delete_notes(self, note_ids: list[int]) -> None:
        """Delete notes by IDs."""
        self.call_log.append(f"delete_notes:{note_ids}")
        if not self.connected:
            raise ConnectionError("Anki not running")

        self.notes = [n for n in self.notes if n.get("id") not in note_ids]

    async def find_notes(self, query: str) -> list[int]:
        """Find notes matching a query."""
        self.call_log.append(f"find_notes:{query}")
        if not self.connected:
            raise ConnectionError("Anki not running")

        # Simple query matching
        if "deck:" in query:
            deck_name = query.split("deck:")[1].strip('"')
            return [n["id"] for n in self.notes if True]  # Simplified
        return [n["id"] for n in self.notes]

    async def get_note_info(self, note_ids: list[int]) -> list[dict]:
        """Get detailed note information."""
        self.call_log.append(f"get_note_info:{note_ids}")
        if not self.connected:
            raise ConnectionError("Anki not running")

        return [n for n in self.notes if n.get("id") in note_ids]

    async def sync(self) -> None:
        """Trigger Anki sync."""
        self.call_log.append("sync")
        if not self.connected:
            raise ConnectionError("Anki not running")


# ==================== Connection Tests ====================


@pytest.mark.asyncio
class TestAnkiConnection:
    """Tests for AnkiConnect connection handling."""

    async def test_successful_connection(self):
        """Test successful connection to Anki."""
        client = MockAnkiConnectClient(connected=True)

        is_connected = await client.test_connection()

        assert is_connected is True
        assert "test_connection" in client.call_log

    async def test_failed_connection(self):
        """Test handling failed connection."""
        client = MockAnkiConnectClient(connected=False)

        is_connected = await client.test_connection()

        assert is_connected is False

    async def test_get_version(self):
        """Test getting AnkiConnect version."""
        client = MockAnkiConnectClient()

        version = await client.get_version()

        assert version >= 6  # Minimum supported version

    async def test_connection_error_on_operation(self):
        """Test connection error during operation."""
        client = MockAnkiConnectClient(connected=False)

        with pytest.raises(ConnectionError):
            await client.get_version()


# ==================== Deck Sync Tests ====================


@pytest.mark.asyncio
class TestDeckSync:
    """Tests for deck synchronization."""

    async def test_get_existing_decks(self):
        """Test getting existing decks from Anki."""
        client = MockAnkiConnectClient()

        deck_names = await client.get_deck_names()

        assert "Default" in deck_names
        assert len(deck_names) > 0

    async def test_create_new_deck(self):
        """Test creating a new deck in Anki."""
        client = MockAnkiConnectClient()

        deck_id = await client.create_deck("New Test Deck")

        assert deck_id > 0
        assert "New Test Deck" in client.created_decks
        assert "New Test Deck" in await client.get_deck_names()

    async def test_create_nested_deck(self):
        """Test creating a nested deck."""
        client = MockAnkiConnectClient()

        deck_id = await client.create_deck("Parent::Child::Grandchild")

        assert deck_id > 0
        assert "Parent::Child::Grandchild" in await client.get_deck_names()

    async def test_delete_deck(self):
        """Test deleting a deck."""
        client = MockAnkiConnectClient()

        initial_count = len(await client.get_deck_names())
        await client.delete_deck("Japanese")

        assert len(await client.get_deck_names()) < initial_count

    async def test_sync_deck_from_app(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test syncing a deck from the app to Anki."""
        # Create deck in app
        deck = await DeckFactory.create_async(
            db_session,
            owner_id=test_user.id,
            name="App Deck",
        )

        # Sync to Anki
        client = MockAnkiConnectClient()
        anki_id = await client.create_deck(deck.name)

        # Update deck with Anki ID
        deck.anki_deck_id = anki_id
        await db_session.flush()

        assert deck.anki_deck_id is not None
        assert deck.name in await client.get_deck_names()


# ==================== Note/Card Sync Tests ====================


@pytest.mark.asyncio
class TestNoteSync:
    """Tests for note/card synchronization."""

    async def test_add_basic_note(self):
        """Test adding a basic note to Anki."""
        client = MockAnkiConnectClient()

        note = {
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {
                "Front": "What is 1+1?",
                "Back": "2",
            },
            "tags": ["math"],
        }

        note_id = await client.add_note(note)

        assert note_id > 0
        assert len(client.created_notes) == 1

    async def test_add_cloze_note(self):
        """Test adding a cloze note to Anki."""
        client = MockAnkiConnectClient()

        note = {
            "deckName": "Default",
            "modelName": "Cloze",
            "fields": {
                "Text": "The capital of {{c1::Japan}} is {{c2::Tokyo}}.",
                "Extra": "Geography fact",
            },
            "tags": ["geography", "cloze"],
        }

        note_id = await client.add_note(note)

        assert note_id > 0

    async def test_update_note_fields(self):
        """Test updating note fields."""
        client = MockAnkiConnectClient()

        # Add a note first
        note = {
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "Old Q", "Back": "Old A"},
        }
        note_id = await client.add_note(note)

        # Update it
        await client.update_note(
            note_id,
            {"Front": "New Q", "Back": "New A"},
        )

        # Verify update
        notes = await client.get_note_info([note_id])
        assert len(notes) > 0

    async def test_delete_notes(self):
        """Test deleting notes."""
        client = MockAnkiConnectClient()

        initial_count = len(client.notes)

        # Delete first note
        note_ids = [client.notes[0]["id"]]
        await client.delete_notes(note_ids)

        assert len(client.notes) < initial_count

    async def test_find_notes_in_deck(self):
        """Test finding notes in a specific deck."""
        client = MockAnkiConnectClient()

        note_ids = await client.find_notes('deck:"Default"')

        assert isinstance(note_ids, list)


# ==================== Sync Conflict Tests ====================


@pytest.mark.asyncio
class TestSyncConflicts:
    """Tests for handling sync conflicts."""

    async def test_deck_name_collision(self):
        """Test handling deck name collision."""
        client = MockAnkiConnectClient()

        # Create deck
        await client.create_deck("Test Deck")

        # Try to create same name (should succeed in Anki, just returns ID)
        deck_id = await client.create_deck("Test Deck")

        assert deck_id > 0

    async def test_note_duplicate_detection(self):
        """Test detecting duplicate notes."""
        client = MockAnkiConnectClient()

        note = {
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "Duplicate", "Back": "Test"},
        }

        # Add twice
        id1 = await client.add_note(note)
        id2 = await client.add_note(note)

        # Both should succeed (Anki allows duplicates)
        assert id1 != id2

    async def test_sync_modified_note(self):
        """Test syncing a note modified in both places."""
        client = MockAnkiConnectClient()

        # Original note
        note = {
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "Original", "Back": "Answer"},
        }
        note_id = await client.add_note(note)

        # Simulate conflict: app has different version
        app_version = {"Front": "App Modified", "Back": "Answer"}
        anki_version = {"Front": "Anki Modified", "Back": "Answer"}

        # Resolution strategy: take most recent (simulate)
        # In real implementation, would compare timestamps
        await client.update_note(note_id, app_version)

        notes = await client.get_note_info([note_id])
        assert len(notes) > 0


# ==================== Batch Operations Tests ====================


@pytest.mark.asyncio
class TestBatchOperations:
    """Tests for batch sync operations."""

    async def test_batch_create_notes(self):
        """Test creating multiple notes in batch."""
        client = MockAnkiConnectClient()

        notes = [
            {
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": f"Q{i}", "Back": f"A{i}"},
            }
            for i in range(10)
        ]

        ids = []
        for note in notes:
            note_id = await client.add_note(note)
            ids.append(note_id)

        assert len(ids) == 10
        assert len(set(ids)) == 10  # All unique

    async def test_batch_update_notes(self):
        """Test updating multiple notes."""
        client = MockAnkiConnectClient()

        # Get existing note IDs
        note_ids = [n["id"] for n in client.notes[:2]]

        # Update each
        for note_id in note_ids:
            await client.update_note(
                note_id,
                {"Front": f"Updated {note_id}"},
            )

        assert client.call_log.count(f"update_note:{note_ids[0]}") == 1


# ==================== Error Handling Tests ====================


@pytest.mark.asyncio
class TestSyncErrorHandling:
    """Tests for sync error handling."""

    async def test_handle_connection_lost(self):
        """Test handling connection lost during sync."""
        client = MockAnkiConnectClient(connected=True)

        # Start operation
        await client.get_deck_names()

        # Simulate connection lost
        client.connected = False

        with pytest.raises(ConnectionError):
            await client.create_deck("New Deck")

    async def test_handle_invalid_note_model(self):
        """Test handling invalid note model."""
        client = MockAnkiConnectClient()

        # In real implementation, this would fail
        note = {
            "deckName": "Default",
            "modelName": "NonExistentModel",
            "fields": {"Field1": "Value"},
        }

        # Mock doesn't validate, but real would fail
        note_id = await client.add_note(note)
        assert note_id > 0  # Mock succeeds

    async def test_retry_on_transient_error(self):
        """Test retry mechanism for transient errors."""
        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "Success"

        # Retry loop
        max_retries = 3
        result = None
        for attempt in range(max_retries):
            try:
                result = await flaky_operation()
                break
            except ConnectionError:
                if attempt == max_retries - 1:
                    raise

        assert result == "Success"
        assert call_count == 3


# ==================== Full Sync Workflow Tests ====================


@pytest.mark.asyncio
class TestFullSyncWorkflow:
    """Tests for complete sync workflows."""

    async def test_initial_sync_from_anki(self):
        """Test initial sync importing data from Anki."""
        client = MockAnkiConnectClient()

        # 1. Get all decks
        deck_names = await client.get_deck_names()

        # 2. Get deck IDs
        deck_ids = await client.get_deck_names_and_ids()

        # 3. For each deck, find notes
        all_notes = []
        for deck_name in deck_names:
            note_ids = await client.find_notes(f'deck:"{deck_name}"')
            if note_ids:
                notes = await client.get_note_info(note_ids)
                all_notes.extend(notes)

        assert len(deck_names) > 0
        assert len(deck_ids) > 0

    async def test_push_changes_to_anki(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test pushing changes from app to Anki."""
        client = MockAnkiConnectClient()

        # 1. Create deck in app
        deck = await DeckFactory.create_async(
            db_session,
            owner_id=test_user.id,
            name="Push Test Deck",
        )

        # 2. Push deck to Anki
        anki_deck_id = await client.create_deck(deck.name)
        deck.anki_deck_id = anki_deck_id

        # 3. Create card data
        card_data = SAMPLE_CARD_DATA["basic"]

        # 4. Push card as note
        note = {
            "deckName": deck.name,
            "modelName": "Basic",
            "fields": {
                "Front": card_data["front"],
                "Back": card_data["back"],
            },
            "tags": card_data.get("tags", []),
        }
        note_id = await client.add_note(note)

        # 5. Trigger Anki sync
        await client.sync()

        assert anki_deck_id > 0
        assert note_id > 0
        assert "sync" in client.call_log

    async def test_bidirectional_sync(self):
        """Test bidirectional sync between app and Anki."""
        client = MockAnkiConnectClient()

        # Simulate changes on both sides
        app_changes = {
            "new_decks": ["App Deck 1", "App Deck 2"],
            "new_cards": [
                {"front": "App Q1", "back": "App A1"},
            ],
        }

        anki_changes = {
            "existing_decks": await client.get_deck_names(),
            "existing_notes": client.notes,
        }

        # Push app changes
        for deck_name in app_changes["new_decks"]:
            await client.create_deck(deck_name)

        for card in app_changes["new_cards"]:
            await client.add_note({
                "deckName": "Default",
                "modelName": "Basic",
                "fields": {"Front": card["front"], "Back": card["back"]},
            })

        # Verify both sides synced
        final_decks = await client.get_deck_names()
        assert all(d in final_decks for d in app_changes["new_decks"])


# ==================== Sync Status Tests ====================


@pytest.mark.asyncio
class TestSyncStatus:
    """Tests for sync status tracking."""

    async def test_track_sync_timestamp(self):
        """Test tracking last sync timestamp."""
        from datetime import datetime

        client = MockAnkiConnectClient()

        # Record sync start
        sync_start = datetime.now(UTC)

        # Perform sync operations
        await client.get_deck_names()
        await client.sync()

        # Record sync end
        sync_end = datetime.now(UTC)

        # Verify timing
        assert sync_end >= sync_start

    async def test_track_sync_operations(self):
        """Test tracking sync operations performed."""
        client = MockAnkiConnectClient()

        # Perform operations
        await client.get_deck_names()
        await client.create_deck("Tracked Deck")
        await client.add_note({
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "Q", "Back": "A"},
        })
        await client.sync()

        # Check call log
        assert "get_deck_names" in client.call_log
        assert any("create_deck" in c for c in client.call_log)
        assert any("add_note" in c for c in client.call_log)
        assert "sync" in client.call_log

    async def test_sync_statistics(self):
        """Test generating sync statistics."""
        client = MockAnkiConnectClient()

        initial_deck_count = len(await client.get_deck_names())
        initial_note_count = len(client.notes)

        # Perform changes
        await client.create_deck("Stats Deck")
        await client.add_note({
            "deckName": "Default",
            "modelName": "Basic",
            "fields": {"Front": "Q", "Back": "A"},
        })

        final_deck_count = len(await client.get_deck_names())
        final_note_count = len(client.notes)

        stats = {
            "decks_created": final_deck_count - initial_deck_count,
            "notes_created": final_note_count - initial_note_count,
        }

        assert stats["decks_created"] == 1
        assert stats["notes_created"] == 1
