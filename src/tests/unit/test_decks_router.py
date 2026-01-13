"""Unit tests for decks router endpoints."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from src.modules.decks.service import (
    DeckAccessDeniedError,
    DeckCircularReferenceError,
    DeckNotFoundError,
    DeckService,
)


@pytest.fixture
def mock_user_id():
    """Create a mock user ID."""
    return uuid4()


@pytest.fixture
def mock_deck(mock_user_id):
    """Create a mock deck object."""
    deck = MagicMock()
    deck.id = uuid4()
    deck.name = "Test Deck"
    deck.description = "Test Description"
    deck.owner_id = mock_user_id
    deck.parent_id = None
    deck.anki_deck_id = None
    deck.created_at = datetime.utcnow()
    deck.updated_at = datetime.utcnow()
    deck.deleted_at = None
    deck.children = []
    deck.cards = []
    return deck


@pytest.fixture
def mock_deck_with_children(mock_user_id):
    """Create a mock deck with children for tree tests."""
    parent_deck = MagicMock()
    parent_deck.id = uuid4()
    parent_deck.name = "Parent Deck"
    parent_deck.description = "Parent Description"
    parent_deck.owner_id = mock_user_id
    parent_deck.parent_id = None
    parent_deck.anki_deck_id = None
    parent_deck.created_at = datetime.utcnow()
    parent_deck.updated_at = datetime.utcnow()
    parent_deck.deleted_at = None

    child_deck = MagicMock()
    child_deck.id = uuid4()
    child_deck.name = "Child Deck"
    child_deck.description = "Child Description"
    child_deck.owner_id = mock_user_id
    child_deck.parent_id = parent_deck.id
    child_deck.anki_deck_id = None
    child_deck.created_at = datetime.utcnow()
    child_deck.updated_at = datetime.utcnow()
    child_deck.deleted_at = None
    child_deck.children = []

    parent_deck.children = [child_deck]

    return parent_deck


@pytest.fixture
def app_with_mocked_db():
    """Create app with mocked database dependency."""
    from src.main import create_app
    from src.core.database import get_db

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_get_db

    yield app

    app.dependency_overrides.clear()


class TestCreateDeckEndpoint:
    """Tests for POST /api/decks/ endpoint."""

    def test_create_deck_success(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test successful deck creation."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.create.return_value = mock_deck

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/decks/",
            json={
                "name": "Test Deck",
                "description": "Test Description",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Deck"
        assert "id" in data

    def test_create_deck_with_parent(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test creating a deck with a parent."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        parent_id = uuid4()
        mock_deck.parent_id = parent_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.create.return_value = mock_deck

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/decks/",
            json={
                "name": "Child Deck",
                "parent_id": str(parent_id),
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_deck_parent_not_found(self, app_with_mocked_db, mock_user_id):
        """Test creating deck with non-existent parent returns 404."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        parent_id = uuid4()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.create.side_effect = DeckNotFoundError(parent_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/decks/",
            json={
                "name": "Child Deck",
                "parent_id": str(parent_id),
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_deck_parent_access_denied(self, app_with_mocked_db, mock_user_id):
        """Test creating deck with inaccessible parent returns 403."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        parent_id = uuid4()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.create.side_effect = DeckAccessDeniedError(parent_id, mock_user_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/decks/",
            json={
                "name": "Child Deck",
                "parent_id": str(parent_id),
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_deck_invalid_name(self, app_with_mocked_db, mock_user_id):
        """Test creating deck with empty name returns 422."""
        from src.modules.decks.router import get_current_user_id

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/decks/",
            json={
                "name": "",
                "description": "Test Description",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_deck_unauthorized(self, app_with_mocked_db):
        """Test creating deck without auth returns 501 (auth not implemented)."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/decks/",
            json={
                "name": "Test Deck",
            },
        )

        # Router has placeholder that returns 501
        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED


class TestListDecksEndpoint:
    """Tests for GET /api/decks/ endpoint."""

    def test_list_decks_success(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test listing user's decks."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.list_by_owner.return_value = ([mock_deck], 1)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/decks/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 1

    def test_list_decks_with_pagination(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test listing decks with pagination."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.list_by_owner.return_value = ([mock_deck], 10)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/decks/?page=1&page_size=10")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_root_decks_only(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test listing only root decks."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.list_root_decks.return_value = ([mock_deck], 1)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/decks/?root_only=true")

        assert response.status_code == status.HTTP_200_OK
        mock_service.list_root_decks.assert_called_once()

    def test_list_decks_empty(self, app_with_mocked_db, mock_user_id):
        """Test listing decks when user has none."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.list_by_owner.return_value = ([], 0)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/decks/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestGetDeckEndpoint:
    """Tests for GET /api/decks/{deck_id} endpoint."""

    def test_get_deck_success(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test getting a specific deck."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.get_by_id_for_user.return_value = mock_deck

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get(f"/api/decks/{mock_deck.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == mock_deck.name

    def test_get_deck_not_found(self, app_with_mocked_db, mock_user_id):
        """Test getting non-existent deck returns 404."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        deck_id = uuid4()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.get_by_id_for_user.return_value = None

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get(f"/api/decks/{deck_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateDeckEndpoint:
    """Tests for PATCH /api/decks/{deck_id} endpoint."""

    def test_update_deck_success(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test successful deck update."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        updated_deck = MagicMock()
        updated_deck.id = mock_deck.id
        updated_deck.name = "Updated Deck"
        updated_deck.description = mock_deck.description
        updated_deck.owner_id = mock_user_id
        updated_deck.parent_id = None
        updated_deck.anki_deck_id = None
        updated_deck.created_at = mock_deck.created_at
        updated_deck.updated_at = datetime.utcnow()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.update.return_value = updated_deck

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            f"/api/decks/{mock_deck.id}",
            json={"name": "Updated Deck"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Deck"

    def test_update_deck_not_found(self, app_with_mocked_db, mock_user_id):
        """Test updating non-existent deck returns 404."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        deck_id = uuid4()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.update.side_effect = DeckNotFoundError(deck_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            f"/api/decks/{deck_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_deck_circular_reference(self, app_with_mocked_db, mock_user_id):
        """Test updating deck with circular reference returns 400."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        deck_id = uuid4()
        parent_id = uuid4()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.update.side_effect = DeckCircularReferenceError(deck_id, parent_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            f"/api/decks/{deck_id}",
            json={"parent_id": str(parent_id)},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestDeleteDeckEndpoint:
    """Tests for DELETE /api/decks/{deck_id} endpoint."""

    def test_delete_deck_success(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test successful soft delete."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.delete.return_value = True

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.delete(f"/api/decks/{mock_deck.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_delete_deck_hard_delete(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test hard delete."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.delete.return_value = True

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.delete(f"/api/decks/{mock_deck.id}?hard=true")

        assert response.status_code == status.HTTP_200_OK
        mock_service.delete.assert_called_once()
        call_kwargs = mock_service.delete.call_args[1]
        assert call_kwargs["hard_delete"] is True

    def test_delete_deck_not_found(self, app_with_mocked_db, mock_user_id):
        """Test deleting non-existent deck returns 404."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        deck_id = uuid4()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.delete.side_effect = DeckNotFoundError(deck_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.delete(f"/api/decks/{deck_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGetDeckTreeEndpoint:
    """Tests for GET /api/decks/tree endpoint."""

    def test_get_deck_tree_success(self, app_with_mocked_db, mock_user_id, mock_deck_with_children):
        """Test getting deck hierarchy tree."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.get_deck_tree.return_value = [mock_deck_with_children]

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/decks/tree")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert "children" in data[0]


class TestRestoreDeckEndpoint:
    """Tests for POST /api/decks/{deck_id}/restore endpoint."""

    def test_restore_deck_success(self, app_with_mocked_db, mock_user_id, mock_deck):
        """Test successful deck restoration."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        mock_service = AsyncMock(spec=DeckService)
        mock_service.restore.return_value = mock_deck

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(f"/api/decks/{mock_deck.id}/restore")

        assert response.status_code == status.HTTP_200_OK

    def test_restore_deck_not_found(self, app_with_mocked_db, mock_user_id):
        """Test restoring non-existent deck returns 404."""
        from src.modules.decks.router import get_deck_service, get_current_user_id

        deck_id = uuid4()

        mock_service = AsyncMock(spec=DeckService)
        mock_service.restore.side_effect = DeckNotFoundError(deck_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_deck_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(f"/api/decks/{deck_id}/restore")

        assert response.status_code == status.HTTP_404_NOT_FOUND
