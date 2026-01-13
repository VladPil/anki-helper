"""Unit tests for CardService with mocked AsyncSession.

Tests cover:
- Card CRUD operations (create, get, list, update, delete)
- Bulk card operations
- Status transitions
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.cards.models import Card, CardGenerationInfo, CardStatus
from src.modules.cards.schemas import CardBulkItem, CardCreate, CardUpdate
from src.modules.cards.service import (
    CardNotFoundError,
    CardService,
    DeckNotFoundError,
    InvalidCardStatusTransitionError,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def card_service(mock_session):
    """Create CardService instance with mocked session."""
    return CardService(mock_session)


@pytest.fixture
def sample_user_id():
    """Generate a sample user UUID."""
    return uuid4()


@pytest.fixture
def sample_deck_id():
    """Generate a sample deck UUID."""
    return uuid4()


@pytest.fixture
def sample_template_id():
    """Generate a sample template UUID."""
    return uuid4()


@pytest.fixture
def sample_card_id():
    """Generate a sample card UUID."""
    return uuid4()


@pytest.fixture
def sample_card(sample_card_id, sample_deck_id, sample_template_id):
    """Create a sample Card mock object."""
    card = MagicMock(spec=Card)
    card.id = sample_card_id
    card.deck_id = sample_deck_id
    card.template_id = sample_template_id
    card.fields = {"Front": "Question", "Back": "Answer"}
    card.tags = ["test"]
    card.status = CardStatus.DRAFT
    card.deleted_at = None
    card.anki_card_id = None
    card.anki_note_id = None
    card.created_at = datetime.now(timezone.utc)
    card.updated_at = datetime.now(timezone.utc)
    return card


@pytest.fixture
def sample_deck(sample_deck_id, sample_user_id):
    """Create a sample Deck mock object."""
    deck = MagicMock()
    deck.id = sample_deck_id
    deck.owner_id = sample_user_id
    deck.name = "Test Deck"
    deck.deleted_at = None
    return deck


# ==================== Create Tests ====================


@pytest.mark.asyncio
class TestCardServiceCreate:
    """Tests for card creation."""

    async def test_create_card_success(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_deck_id,
        sample_template_id,
        sample_deck,
    ):
        """Test successful card creation."""
        # Setup mock to return deck
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_deck
        mock_session.execute.return_value = mock_result

        card_data = CardCreate(
            deck_id=sample_deck_id,
            template_id=sample_template_id,
            fields={"Front": "Test Question", "Back": "Test Answer"},
            tags=["test", "unit"],
        )

        # Execute
        card = await card_service.create(sample_user_id, card_data)

        # Assert session methods were called
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    async def test_create_card_deck_not_found(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_deck_id,
        sample_template_id,
    ):
        """Test card creation fails when deck not found."""
        # Setup mock to return None (deck not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        card_data = CardCreate(
            deck_id=sample_deck_id,
            template_id=sample_template_id,
            fields={"Front": "Test Question", "Back": "Test Answer"},
        )

        # Execute & Assert
        with pytest.raises(DeckNotFoundError) as exc_info:
            await card_service.create(sample_user_id, card_data)

        assert exc_info.value.deck_id == sample_deck_id

    async def test_create_card_with_created_by(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_deck_id,
        sample_template_id,
        sample_deck,
    ):
        """Test card creation with created_by audit info."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_deck
        mock_session.execute.return_value = mock_result

        card_data = CardCreate(
            deck_id=sample_deck_id,
            template_id=sample_template_id,
            fields={"Front": "Question", "Back": "Answer"},
        )

        await card_service.create(
            sample_user_id,
            card_data,
            created_by="test_user",
        )

        # Verify card was added
        mock_session.add.assert_called_once()
        added_card = mock_session.add.call_args[0][0]
        assert added_card.deck_id == sample_deck_id


# ==================== Bulk Create Tests ====================


@pytest.mark.asyncio
class TestCardServiceBulkCreate:
    """Tests for bulk card creation."""

    async def test_bulk_create_success(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_deck_id,
        sample_template_id,
        sample_deck,
    ):
        """Test successful bulk card creation."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_deck
        mock_session.execute.return_value = mock_result

        items = [
            CardBulkItem(fields={"Front": "Q1", "Back": "A1"}, tags=["tag1"]),
            CardBulkItem(fields={"Front": "Q2", "Back": "A2"}, tags=["tag2"]),
            CardBulkItem(fields={"Front": "Q3", "Back": "A3"}, tags=["tag3"]),
        ]

        cards, errors = await card_service.create_bulk(
            sample_user_id,
            sample_deck_id,
            sample_template_id,
            items,
        )

        # All cards should be added
        assert mock_session.add.call_count == 3
        assert len(errors) == 0

    async def test_bulk_create_deck_not_found(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_deck_id,
        sample_template_id,
    ):
        """Test bulk creation fails when deck not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        items = [
            CardBulkItem(fields={"Front": "Q1", "Back": "A1"}),
        ]

        with pytest.raises(DeckNotFoundError):
            await card_service.create_bulk(
                sample_user_id,
                sample_deck_id,
                sample_template_id,
                items,
            )

    async def test_bulk_create_partial_failure(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_deck_id,
        sample_template_id,
        sample_deck,
    ):
        """Test bulk creation with some items failing."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_deck
        mock_session.execute.return_value = mock_result

        # Make flush fail on second call
        call_count = 0

        async def failing_flush():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Database error")

        mock_session.flush = failing_flush

        items = [
            CardBulkItem(fields={"Front": "Q1", "Back": "A1"}),
            CardBulkItem(fields={"Front": "Q2", "Back": "A2"}),  # Will fail
            CardBulkItem(fields={"Front": "Q3", "Back": "A3"}),
        ]

        cards, errors = await card_service.create_bulk(
            sample_user_id,
            sample_deck_id,
            sample_template_id,
            items,
        )

        assert len(errors) == 1
        assert errors[0][0] == 1  # Index of failed item


# ==================== Get Tests ====================


@pytest.mark.asyncio
class TestCardServiceGet:
    """Tests for card retrieval."""

    async def test_get_by_id_success(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_card,
    ):
        """Test successful card retrieval by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_card
        mock_session.execute.return_value = mock_result

        card = await card_service.get_by_id(sample_card_id)

        assert card is not None
        assert card.id == sample_card_id
        mock_session.execute.assert_called_once()

    async def test_get_by_id_not_found(
        self,
        card_service,
        mock_session,
        sample_card_id,
    ):
        """Test card retrieval when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        card = await card_service.get_by_id(sample_card_id)

        assert card is None

    async def test_get_by_id_include_deleted(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_card,
    ):
        """Test card retrieval including deleted cards."""
        sample_card.deleted_at = datetime.now(timezone.utc)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_card
        mock_session.execute.return_value = mock_result

        card = await card_service.get_by_id(sample_card_id, include_deleted=True)

        assert card is not None
        mock_session.execute.assert_called_once()

    async def test_get_by_id_for_user_success(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test card retrieval for specific user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_card
        mock_session.execute.return_value = mock_result

        card = await card_service.get_by_id_for_user(sample_card_id, sample_user_id)

        assert card is not None
        mock_session.execute.assert_called_once()

    async def test_get_by_id_for_user_not_found(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
    ):
        """Test card retrieval for user when not found or not owned."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        card = await card_service.get_by_id_for_user(sample_card_id, sample_user_id)

        assert card is None


# ==================== List Tests ====================


@pytest.mark.asyncio
class TestCardServiceList:
    """Tests for card listing."""

    async def test_list_by_deck_success(
        self,
        card_service,
        mock_session,
        sample_deck_id,
        sample_user_id,
        sample_card,
    ):
        """Test listing cards by deck."""
        # Mock count query
        count_result = MagicMock()
        count_result.scalar_one.return_value = 5

        # Mock data query
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_card] * 5
        data_result.scalars.return_value = scalars_mock

        mock_session.execute.side_effect = [count_result, data_result]

        cards, total = await card_service.list_by_deck(sample_deck_id, sample_user_id)

        assert len(cards) == 5
        assert total == 5
        assert mock_session.execute.call_count == 2

    async def test_list_by_deck_with_status_filter(
        self,
        card_service,
        mock_session,
        sample_deck_id,
        sample_user_id,
        sample_card,
    ):
        """Test listing cards with status filter."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3

        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_card] * 3
        data_result.scalars.return_value = scalars_mock

        mock_session.execute.side_effect = [count_result, data_result]

        cards, total = await card_service.list_by_deck(
            sample_deck_id,
            sample_user_id,
            status=CardStatus.DRAFT,
        )

        assert len(cards) == 3
        assert total == 3

    async def test_list_by_deck_with_pagination(
        self,
        card_service,
        mock_session,
        sample_deck_id,
        sample_user_id,
        sample_card,
    ):
        """Test listing cards with pagination."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = 20

        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_card] * 10
        data_result.scalars.return_value = scalars_mock

        mock_session.execute.side_effect = [count_result, data_result]

        cards, total = await card_service.list_by_deck(
            sample_deck_id,
            sample_user_id,
            offset=0,
            limit=10,
        )

        assert len(cards) == 10
        assert total == 20

    async def test_list_by_status_success(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_card,
    ):
        """Test listing cards by status across all decks."""
        count_result = MagicMock()
        count_result.scalar_one.return_value = 7

        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_card] * 7
        data_result.scalars.return_value = scalars_mock

        mock_session.execute.side_effect = [count_result, data_result]

        cards, total = await card_service.list_by_status(
            sample_user_id,
            CardStatus.APPROVED,
        )

        assert len(cards) == 7
        assert total == 7


# ==================== Update Tests ====================


@pytest.mark.asyncio
class TestCardServiceUpdate:
    """Tests for card updates."""

    async def test_update_card_fields(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test updating card fields."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_card
        mock_session.execute.return_value = mock_result

        update_data = CardUpdate(
            fields={"Front": "Updated Question", "Back": "Updated Answer"},
        )

        # Patch get_by_id_for_user to return sample_card
        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            card = await card_service.update(
                sample_card_id,
                sample_user_id,
                update_data,
            )

        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    async def test_update_card_tags(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test updating card tags."""
        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            update_data = CardUpdate(tags=["new_tag1", "new_tag2"])

            card = await card_service.update(
                sample_card_id,
                sample_user_id,
                update_data,
            )

        mock_session.flush.assert_called()

    async def test_update_card_not_found(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
    ):
        """Test updating nonexistent card."""
        with patch.object(card_service, "get_by_id_for_user", return_value=None):
            update_data = CardUpdate(fields={"Front": "Test"})

            with pytest.raises(CardNotFoundError):
                await card_service.update(
                    sample_card_id,
                    sample_user_id,
                    update_data,
                )

    async def test_update_card_invalid_status_transition(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test invalid status transition."""
        # Card is DRAFT, cannot go directly to SYNCED
        sample_card.status = CardStatus.DRAFT

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            update_data = CardUpdate(status=CardStatus.SYNCED)

            with pytest.raises(InvalidCardStatusTransitionError):
                await card_service.update(
                    sample_card_id,
                    sample_user_id,
                    update_data,
                )

    async def test_update_card_valid_status_transition(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test valid status transition."""
        sample_card.status = CardStatus.DRAFT

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            update_data = CardUpdate(status=CardStatus.APPROVED)

            card = await card_service.update(
                sample_card_id,
                sample_user_id,
                update_data,
            )

        mock_session.flush.assert_called()

    async def test_update_card_move_to_new_deck(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
        sample_deck,
    ):
        """Test moving card to a different deck."""
        new_deck_id = uuid4()
        new_deck = MagicMock()
        new_deck.id = new_deck_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = new_deck
        mock_session.execute.return_value = mock_result

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            update_data = CardUpdate(deck_id=new_deck_id)

            card = await card_service.update(
                sample_card_id,
                sample_user_id,
                update_data,
            )

        mock_session.flush.assert_called()


# ==================== Delete Tests ====================


@pytest.mark.asyncio
class TestCardServiceDelete:
    """Tests for card deletion."""

    async def test_soft_delete_card(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test soft deleting a card."""
        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            result = await card_service.delete(sample_card_id, sample_user_id)

        assert result is True
        sample_card.soft_delete.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_hard_delete_card(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test hard deleting a card."""
        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            result = await card_service.delete(
                sample_card_id,
                sample_user_id,
                hard_delete=True,
            )

        assert result is True
        mock_session.delete.assert_called_once_with(sample_card)
        mock_session.flush.assert_called_once()

    async def test_delete_card_not_found(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
    ):
        """Test deleting nonexistent card."""
        with patch.object(card_service, "get_by_id_for_user", return_value=None):
            with pytest.raises(CardNotFoundError):
                await card_service.delete(sample_card_id, sample_user_id)


# ==================== Status Transition Tests ====================


@pytest.mark.asyncio
class TestCardServiceStatusTransitions:
    """Tests for card status transitions."""

    async def test_approve_card(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test approving a card."""
        sample_card.status = CardStatus.DRAFT

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            card = await card_service.approve(sample_card_id, sample_user_id)

        assert sample_card.status == CardStatus.APPROVED
        mock_session.flush.assert_called()
        mock_session.refresh.assert_called()

    async def test_approve_card_not_found(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
    ):
        """Test approving nonexistent card."""
        with patch.object(card_service, "get_by_id_for_user", return_value=None):
            with pytest.raises(CardNotFoundError):
                await card_service.approve(sample_card_id, sample_user_id)

    async def test_approve_card_invalid_transition(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test approving card with invalid status."""
        sample_card.status = CardStatus.SYNCED

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            with pytest.raises(InvalidCardStatusTransitionError):
                await card_service.approve(sample_card_id, sample_user_id)

    async def test_reject_card(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test rejecting a card."""
        sample_card.status = CardStatus.DRAFT

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            card = await card_service.reject(
                sample_card_id,
                sample_user_id,
                reason="Poor quality",
            )

        assert sample_card.status == CardStatus.REJECTED
        mock_session.flush.assert_called()

    async def test_reject_card_invalid_transition(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test rejecting card with invalid status."""
        sample_card.status = CardStatus.SYNCED

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            with pytest.raises(InvalidCardStatusTransitionError):
                await card_service.reject(
                    sample_card_id,
                    sample_user_id,
                    reason="test",
                )

    async def test_mark_synced(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_card,
    ):
        """Test marking card as synced."""
        sample_card.status = CardStatus.APPROVED

        with patch.object(card_service, "get_by_id", return_value=sample_card):
            card = await card_service.mark_synced(
                sample_card_id,
                anki_card_id=12345,
                anki_note_id=67890,
            )

        assert sample_card.status == CardStatus.SYNCED
        assert sample_card.anki_card_id == 12345
        assert sample_card.anki_note_id == 67890
        mock_session.flush.assert_called()

    async def test_mark_synced_invalid_transition(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_card,
    ):
        """Test marking draft card as synced (invalid)."""
        sample_card.status = CardStatus.DRAFT

        with patch.object(card_service, "get_by_id", return_value=sample_card):
            with pytest.raises(InvalidCardStatusTransitionError):
                await card_service.mark_synced(
                    sample_card_id,
                    anki_card_id=12345,
                    anki_note_id=67890,
                )


# ==================== Bulk Status Tests ====================


@pytest.mark.asyncio
class TestCardServiceBulkStatus:
    """Tests for bulk status operations."""

    async def test_bulk_approve(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_card,
    ):
        """Test bulk approving cards."""
        card_ids = [uuid4() for _ in range(3)]
        sample_card.status = CardStatus.DRAFT

        with patch.object(
            card_service, "approve", return_value=sample_card
        ) as mock_approve:
            approved, errors = await card_service.bulk_approve(
                card_ids,
                sample_user_id,
            )

        assert mock_approve.call_count == 3
        assert len(errors) == 0

    async def test_bulk_approve_partial_failure(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_card,
    ):
        """Test bulk approve with some failures."""
        card_ids = [uuid4() for _ in range(3)]

        async def mock_approve(card_id, user_id, **kwargs):
            if card_id == card_ids[1]:
                raise CardNotFoundError(card_id)
            return sample_card

        with patch.object(card_service, "approve", side_effect=mock_approve):
            approved, errors = await card_service.bulk_approve(
                card_ids,
                sample_user_id,
            )

        assert len(errors) == 1
        assert errors[0][0] == card_ids[1]

    async def test_bulk_reject(
        self,
        card_service,
        mock_session,
        sample_user_id,
        sample_card,
    ):
        """Test bulk rejecting cards."""
        card_ids = [uuid4() for _ in range(3)]
        sample_card.status = CardStatus.DRAFT

        with patch.object(
            card_service, "reject", return_value=sample_card
        ) as mock_reject:
            rejected, errors = await card_service.bulk_reject(
                card_ids,
                sample_user_id,
                reason="Quality issue",
            )

        assert mock_reject.call_count == 3
        assert len(errors) == 0


# ==================== Restore Tests ====================


@pytest.mark.asyncio
class TestCardServiceRestore:
    """Tests for card restoration."""

    async def test_restore_card(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
        sample_card,
    ):
        """Test restoring a soft-deleted card."""
        sample_card.deleted_at = datetime.now(timezone.utc)

        with patch.object(
            card_service, "get_by_id_for_user", return_value=sample_card
        ):
            card = await card_service.restore(sample_card_id, sample_user_id)

        sample_card.restore.assert_called_once()
        mock_session.flush.assert_called()

    async def test_restore_card_not_found(
        self,
        card_service,
        mock_session,
        sample_card_id,
        sample_user_id,
    ):
        """Test restoring nonexistent card."""
        with patch.object(card_service, "get_by_id_for_user", return_value=None):
            with pytest.raises(CardNotFoundError):
                await card_service.restore(sample_card_id, sample_user_id)


# ==================== Generation Info Tests ====================


@pytest.mark.asyncio
class TestCardServiceGenerationInfo:
    """Tests for card generation info."""

    async def test_add_generation_info(
        self,
        card_service,
        mock_session,
        sample_card_id,
    ):
        """Test adding generation info to a card."""
        prompt_id = uuid4()
        model_id = uuid4()

        info = await card_service.add_generation_info(
            card_id=sample_card_id,
            prompt_id=prompt_id,
            model_id=model_id,
            user_request="Generate cards about Python",
            fact_check_result={"verified": True},
            fact_check_confidence=0.95,
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

        # Verify the added object has correct attributes
        added_info = mock_session.add.call_args[0][0]
        assert added_info.card_id == sample_card_id
        assert added_info.prompt_id == prompt_id
        assert added_info.model_id == model_id
        assert added_info.user_request == "Generate cards about Python"
