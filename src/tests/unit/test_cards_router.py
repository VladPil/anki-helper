"""Unit tests for cards router endpoints."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from src.modules.cards.models import CardStatus
from src.modules.cards.service import (
    CardNotFoundError,
    CardService,
    DeckNotFoundError,
    InvalidCardStatusTransitionError,
    TemplateNotFoundError,
)


@pytest.fixture
def mock_user_id():
    """Create a mock user ID."""
    return uuid4()


@pytest.fixture
def mock_deck_id():
    """Create a mock deck ID."""
    return uuid4()


@pytest.fixture
def mock_template_id():
    """Create a mock template ID."""
    return uuid4()


@pytest.fixture
def mock_card(mock_deck_id, mock_template_id):
    """Create a mock card object."""
    card = MagicMock()
    card.id = uuid4()
    card.deck_id = mock_deck_id
    card.template_id = mock_template_id
    card.fields = {"front": "Question", "back": "Answer"}
    card.status = CardStatus.DRAFT
    card.tags = ["test", "mock"]
    card.anki_card_id = None
    card.anki_note_id = None
    card.created_at = datetime.utcnow()
    card.updated_at = datetime.utcnow()
    card.deleted_at = None
    card.generation_info = None
    return card


@pytest.fixture
def mock_approved_card(mock_deck_id, mock_template_id):
    """Create a mock approved card."""
    card = MagicMock()
    card.id = uuid4()
    card.deck_id = mock_deck_id
    card.template_id = mock_template_id
    card.fields = {"front": "Question", "back": "Answer"}
    card.status = CardStatus.APPROVED
    card.tags = ["approved"]
    card.anki_card_id = None
    card.anki_note_id = None
    card.created_at = datetime.utcnow()
    card.updated_at = datetime.utcnow()
    card.deleted_at = None
    card.generation_info = None
    return card


@pytest.fixture
def mock_generation_info():
    """Create mock generation info."""
    info = MagicMock()
    info.id = uuid4()
    info.prompt_id = uuid4()
    info.model_id = uuid4()
    info.user_request = "Generate a card about Python"
    info.fact_check_result = {"verified": True}
    info.fact_check_confidence = 0.95
    info.created_at = datetime.utcnow()
    return info


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


class TestCreateCardEndpoint:
    """Tests for POST /api/cards/ endpoint."""

    def test_create_card_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test successful card creation."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.create.return_value = mock_card

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/cards/",
            json={
                "deck_id": str(mock_card.deck_id),
                "template_id": str(mock_card.template_id),
                "fields": {"front": "Question", "back": "Answer"},
                "tags": ["test"],
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["status"] == CardStatus.DRAFT.value

    def test_create_card_deck_not_found(self, app_with_mocked_db, mock_user_id):
        """Test creating card with non-existent deck returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        deck_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.create.side_effect = DeckNotFoundError(deck_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/cards/",
            json={
                "deck_id": str(deck_id),
                "template_id": str(uuid4()),
                "fields": {"front": "Question", "back": "Answer"},
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_card_template_not_found(self, app_with_mocked_db, mock_user_id):
        """Test creating card with non-existent template returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        template_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.create.side_effect = TemplateNotFoundError(template_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/cards/",
            json={
                "deck_id": str(uuid4()),
                "template_id": str(template_id),
                "fields": {"front": "Question", "back": "Answer"},
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_card_empty_fields(self, app_with_mocked_db, mock_user_id):
        """Test creating card with empty fields returns 422."""
        from src.modules.cards.router import get_current_user_id

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/cards/",
            json={
                "deck_id": str(uuid4()),
                "template_id": str(uuid4()),
                "fields": {},
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_card_unauthorized(self, app_with_mocked_db):
        """Test creating card without auth returns 501."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/cards/",
            json={
                "deck_id": str(uuid4()),
                "template_id": str(uuid4()),
                "fields": {"front": "Q", "back": "A"},
            },
        )

        assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED


class TestListCardsEndpoint:
    """Tests for GET /api/cards/ endpoint."""

    def test_list_cards_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test listing user's cards."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.list_by_status.return_value = ([mock_card], 1)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/cards/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_list_cards_by_deck(self, app_with_mocked_db, mock_user_id, mock_card, mock_deck_id):
        """Test listing cards filtered by deck."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.list_by_deck.return_value = ([mock_card], 1)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get(f"/api/cards/?deck_id={mock_deck_id}")

        assert response.status_code == status.HTTP_200_OK
        mock_service.list_by_deck.assert_called_once()

    def test_list_cards_by_status(self, app_with_mocked_db, mock_user_id, mock_approved_card):
        """Test listing cards filtered by status."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.list_by_status.return_value = ([mock_approved_card], 1)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/cards/?status=approved")

        assert response.status_code == status.HTTP_200_OK
        mock_service.list_by_status.assert_called_once()

    def test_list_cards_empty(self, app_with_mocked_db, mock_user_id):
        """Test listing cards when user has none."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.list_by_status.return_value = ([], 0)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/cards/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestGetCardEndpoint:
    """Tests for GET /api/cards/{card_id} endpoint."""

    def test_get_card_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test getting a specific card."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.get_by_id_for_user.return_value = mock_card

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get(f"/api/cards/{mock_card.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "fields" in data

    def test_get_card_with_generation_info(
        self, app_with_mocked_db, mock_user_id, mock_card, mock_generation_info
    ):
        """Test getting a card with generation info."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_card.generation_info = mock_generation_info

        mock_service = AsyncMock(spec=CardService)
        mock_service.get_by_id_for_user.return_value = mock_card

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get(f"/api/cards/{mock_card.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "generation_info" in data

    def test_get_card_not_found(self, app_with_mocked_db, mock_user_id):
        """Test getting non-existent card returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.get_by_id_for_user.return_value = None

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get(f"/api/cards/{card_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateCardEndpoint:
    """Tests for PATCH /api/cards/{card_id} endpoint."""

    def test_update_card_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test successful card update."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        updated_card = MagicMock()
        updated_card.id = mock_card.id
        updated_card.deck_id = mock_card.deck_id
        updated_card.template_id = mock_card.template_id
        updated_card.fields = {"front": "Updated Question", "back": "Updated Answer"}
        updated_card.status = CardStatus.DRAFT
        updated_card.tags = ["updated"]
        updated_card.anki_card_id = None
        updated_card.anki_note_id = None
        updated_card.created_at = mock_card.created_at
        updated_card.updated_at = datetime.utcnow()

        mock_service = AsyncMock(spec=CardService)
        mock_service.update.return_value = updated_card

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            f"/api/cards/{mock_card.id}",
            json={"fields": {"front": "Updated Question", "back": "Updated Answer"}},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_update_card_not_found(self, app_with_mocked_db, mock_user_id):
        """Test updating non-existent card returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.update.side_effect = CardNotFoundError(card_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            f"/api/cards/{card_id}",
            json={"fields": {"front": "Q", "back": "A"}},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_card_invalid_status_transition(self, app_with_mocked_db, mock_user_id):
        """Test updating card with invalid status transition returns 400."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.update.side_effect = InvalidCardStatusTransitionError(
            card_id, CardStatus.SYNCED, CardStatus.DRAFT
        )

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            f"/api/cards/{card_id}",
            json={"status": "draft"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestDeleteCardEndpoint:
    """Tests for DELETE /api/cards/{card_id} endpoint."""

    def test_delete_card_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test successful soft delete."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.delete.return_value = True

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.delete(f"/api/cards/{mock_card.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    def test_delete_card_hard_delete(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test hard delete."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.delete.return_value = True

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.delete(f"/api/cards/{mock_card.id}?hard=true")

        assert response.status_code == status.HTTP_200_OK
        mock_service.delete.assert_called_once()
        call_kwargs = mock_service.delete.call_args[1]
        assert call_kwargs["hard_delete"] is True

    def test_delete_card_not_found(self, app_with_mocked_db, mock_user_id):
        """Test deleting non-existent card returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.delete.side_effect = CardNotFoundError(card_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.delete(f"/api/cards/{card_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestApproveCardEndpoint:
    """Tests for POST /api/cards/{card_id}/approve endpoint."""

    def test_approve_card_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test successful card approval."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        approved_card = MagicMock()
        approved_card.id = mock_card.id
        approved_card.deck_id = mock_card.deck_id
        approved_card.template_id = mock_card.template_id
        approved_card.fields = mock_card.fields
        approved_card.status = CardStatus.APPROVED
        approved_card.tags = mock_card.tags
        approved_card.anki_card_id = None
        approved_card.anki_note_id = None
        approved_card.created_at = mock_card.created_at
        approved_card.updated_at = datetime.utcnow()

        mock_service = AsyncMock(spec=CardService)
        mock_service.approve.return_value = approved_card

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(f"/api/cards/{mock_card.id}/approve")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == CardStatus.APPROVED.value

    def test_approve_card_not_found(self, app_with_mocked_db, mock_user_id):
        """Test approving non-existent card returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.approve.side_effect = CardNotFoundError(card_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(f"/api/cards/{card_id}/approve")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_approve_card_invalid_status(self, app_with_mocked_db, mock_user_id):
        """Test approving already synced card returns 400."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.approve.side_effect = InvalidCardStatusTransitionError(
            card_id, CardStatus.SYNCED, CardStatus.APPROVED
        )

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(f"/api/cards/{card_id}/approve")

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestRejectCardEndpoint:
    """Tests for POST /api/cards/{card_id}/reject endpoint."""

    def test_reject_card_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test successful card rejection."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        rejected_card = MagicMock()
        rejected_card.id = mock_card.id
        rejected_card.deck_id = mock_card.deck_id
        rejected_card.template_id = mock_card.template_id
        rejected_card.fields = mock_card.fields
        rejected_card.status = CardStatus.REJECTED
        rejected_card.tags = mock_card.tags
        rejected_card.anki_card_id = None
        rejected_card.anki_note_id = None
        rejected_card.created_at = mock_card.created_at
        rejected_card.updated_at = datetime.utcnow()

        mock_service = AsyncMock(spec=CardService)
        mock_service.reject.return_value = rejected_card

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            f"/api/cards/{mock_card.id}/reject",
            json={"reason": "Incorrect answer"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == CardStatus.REJECTED.value

    def test_reject_card_without_reason(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test rejecting card without reason returns 422."""
        from src.modules.cards.router import get_current_user_id

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            f"/api/cards/{mock_card.id}/reject",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_reject_card_not_found(self, app_with_mocked_db, mock_user_id):
        """Test rejecting non-existent card returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.reject.side_effect = CardNotFoundError(card_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            f"/api/cards/{card_id}/reject",
            json={"reason": "Incorrect"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestRestoreCardEndpoint:
    """Tests for POST /api/cards/{card_id}/restore endpoint."""

    def test_restore_card_success(self, app_with_mocked_db, mock_user_id, mock_card):
        """Test successful card restoration."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.restore.return_value = mock_card

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(f"/api/cards/{mock_card.id}/restore")

        assert response.status_code == status.HTTP_200_OK

    def test_restore_card_not_found(self, app_with_mocked_db, mock_user_id):
        """Test restoring non-existent card returns 404."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        card_id = uuid4()

        mock_service = AsyncMock(spec=CardService)
        mock_service.restore.side_effect = CardNotFoundError(card_id)

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(f"/api/cards/{card_id}/restore")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestBulkCreateCardsEndpoint:
    """Tests for POST /api/cards/bulk endpoint."""

    def test_bulk_create_success(self, app_with_mocked_db, mock_user_id, mock_card, mock_deck_id, mock_template_id):
        """Test successful bulk card creation."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.create_bulk.return_value = ([mock_card], [])

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/cards/bulk",
            json={
                "deck_id": str(mock_deck_id),
                "template_id": str(mock_template_id),
                "cards": [
                    {"fields": {"front": "Q1", "back": "A1"}, "tags": ["tag1"]},
                    {"fields": {"front": "Q2", "back": "A2"}, "tags": ["tag2"]},
                ],
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "created" in data
        assert "failed" in data
        assert "total_created" in data

    def test_bulk_create_partial_failure(
        self, app_with_mocked_db, mock_user_id, mock_card, mock_deck_id, mock_template_id
    ):
        """Test bulk creation with partial failure."""
        from src.modules.cards.router import get_card_service, get_current_user_id

        mock_service = AsyncMock(spec=CardService)
        mock_service.create_bulk.return_value = (
            [mock_card],
            [(1, "Validation error")],
        )

        app_with_mocked_db.dependency_overrides[get_current_user_id] = lambda: mock_user_id
        app_with_mocked_db.dependency_overrides[get_card_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/cards/bulk",
            json={
                "deck_id": str(mock_deck_id),
                "template_id": str(mock_template_id),
                "cards": [
                    {"fields": {"front": "Q1", "back": "A1"}, "tags": []},
                    {"fields": {"front": "", "back": ""}, "tags": []},
                ],
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["total_created"] == 1
        assert data["total_failed"] == 1
