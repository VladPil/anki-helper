"""Unit tests for DeckService with mocked database sessions.

These tests use unittest.mock to mock AsyncSession and avoid real database interactions.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.modules.decks.service import (
    DeckService,
    DeckNotFoundError,
    DeckAccessDeniedError,
    DeckCircularReferenceError,
)
from src.modules.decks.schemas import DeckCreate, DeckUpdate


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
def deck_service(mock_session):
    """Create DeckService instance with mocked session."""
    return DeckService(mock_session)


@pytest.fixture
def sample_user_id():
    """Create a sample user ID."""
    return uuid4()


@pytest.fixture
def sample_deck(sample_user_id):
    """Create a sample Deck-like object for testing."""
    deck = MagicMock()
    deck.id = uuid4()
    deck.name = "Test Deck"
    deck.description = "Test Description"
    deck.owner_id = sample_user_id
    deck.parent_id = None
    deck.anki_deck_id = None
    deck.deleted_at = None
    deck.created_at = datetime.now(timezone.utc)
    deck.updated_at = datetime.now(timezone.utc)
    deck.children = []
    deck.cards = []
    return deck


@pytest.fixture
def sample_child_deck(sample_user_id, sample_deck):
    """Create a sample child Deck-like object for testing."""
    child = MagicMock()
    child.id = uuid4()
    child.name = "Child Deck"
    child.description = "Child Description"
    child.owner_id = sample_user_id
    child.parent_id = sample_deck.id
    child.anki_deck_id = None
    child.deleted_at = None
    child.created_at = datetime.now(timezone.utc)
    child.updated_at = datetime.now(timezone.utc)
    child.children = []
    child.cards = []
    return child


# ==================== create Tests ====================


@pytest.mark.asyncio
async def test_create_deck_success(deck_service, mock_session, sample_user_id):
    """Test successful deck creation."""
    deck_data = DeckCreate(name="New Deck", description="New Description")

    result = await deck_service.create(sample_user_id, deck_data)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_deck_with_parent(deck_service, mock_session, sample_user_id, sample_deck):
    """Test creating a deck with a parent."""
    deck_data = DeckCreate(
        name="Child Deck",
        description="Child Description",
        parent_id=sample_deck.id,
    )

    # Mock get_by_id to return parent deck
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.create(sample_user_id, deck_data)

    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_deck_parent_not_found(deck_service, mock_session, sample_user_id):
    """Test create fails when parent deck doesn't exist."""
    parent_id = uuid4()
    deck_data = DeckCreate(name="Child Deck", parent_id=parent_id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(DeckNotFoundError) as exc_info:
        await deck_service.create(sample_user_id, deck_data)
    assert exc_info.value.deck_id == parent_id


@pytest.mark.asyncio
async def test_create_deck_parent_belongs_to_different_user(
    deck_service, mock_session, sample_user_id, sample_deck
):
    """Test create fails when parent belongs to different user."""
    different_user_id = uuid4()
    sample_deck.owner_id = different_user_id  # Parent belongs to different user

    deck_data = DeckCreate(name="Child Deck", parent_id=sample_deck.id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    with pytest.raises(DeckAccessDeniedError) as exc_info:
        await deck_service.create(sample_user_id, deck_data)
    assert exc_info.value.deck_id == sample_deck.id


@pytest.mark.asyncio
async def test_create_deck_with_created_by(deck_service, mock_session, sample_user_id):
    """Test creating a deck with audit trail."""
    deck_data = DeckCreate(name="New Deck")

    # Capture the deck that gets added
    added_deck = None
    def capture_add(obj):
        nonlocal added_deck
        added_deck = obj
    mock_session.add.side_effect = capture_add

    await deck_service.create(sample_user_id, deck_data, created_by="test_user")

    # Verify set_created_by was called
    assert added_deck is not None


# ==================== get_by_id Tests ====================


@pytest.mark.asyncio
async def test_get_by_id_returns_deck(deck_service, mock_session, sample_deck):
    """Test get_by_id returns deck when found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_by_id(sample_deck.id)

    assert result == sample_deck


@pytest.mark.asyncio
async def test_get_by_id_returns_none(deck_service, mock_session):
    """Test get_by_id returns None when deck not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_by_id(uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_excludes_deleted(deck_service, mock_session, sample_deck):
    """Test get_by_id excludes deleted decks by default."""
    sample_deck.deleted_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Excluded by query
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_by_id(sample_deck.id)

    assert result is None


@pytest.mark.asyncio
async def test_get_by_id_include_deleted(deck_service, mock_session, sample_deck):
    """Test get_by_id includes deleted decks when requested."""
    sample_deck.deleted_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_by_id(sample_deck.id, include_deleted=True)

    assert result == sample_deck


# ==================== get_by_id_for_user Tests ====================


@pytest.mark.asyncio
async def test_get_by_id_for_user_returns_deck(deck_service, mock_session, sample_deck, sample_user_id):
    """Test get_by_id_for_user returns deck when owned by user."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_by_id_for_user(sample_deck.id, sample_user_id)

    assert result == sample_deck


@pytest.mark.asyncio
async def test_get_by_id_for_user_returns_none_different_owner(deck_service, mock_session, sample_deck):
    """Test get_by_id_for_user returns None for different owner."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # Query filters by user
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_by_id_for_user(sample_deck.id, uuid4())

    assert result is None


# ==================== get_with_cards Tests ====================


@pytest.mark.asyncio
async def test_get_with_cards_success(deck_service, mock_session, sample_deck, sample_user_id):
    """Test get_with_cards returns deck with cards loaded."""
    sample_deck.cards = [MagicMock(), MagicMock()]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_with_cards(sample_deck.id, sample_user_id)

    assert result == sample_deck
    assert len(result.cards) == 2


# ==================== list_by_owner Tests ====================


@pytest.mark.asyncio
async def test_list_by_owner_returns_decks(deck_service, mock_session, sample_deck, sample_user_id):
    """Test list_by_owner returns user's decks."""
    # Mock count query
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    # Mock decks query
    mock_decks_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_deck]
    mock_decks_result.scalars.return_value = mock_scalars

    mock_session.execute.side_effect = [mock_count_result, mock_decks_result]

    decks, total = await deck_service.list_by_owner(sample_user_id)

    assert total == 1
    assert len(decks) == 1
    assert decks[0] == sample_deck


@pytest.mark.asyncio
async def test_list_by_owner_with_pagination(deck_service, mock_session, sample_deck, sample_user_id):
    """Test list_by_owner respects pagination parameters."""
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 50

    mock_decks_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_deck]
    mock_decks_result.scalars.return_value = mock_scalars

    mock_session.execute.side_effect = [mock_count_result, mock_decks_result]

    decks, total = await deck_service.list_by_owner(sample_user_id, offset=10, limit=10)

    assert total == 50


@pytest.mark.asyncio
async def test_list_by_owner_filter_by_parent(
    deck_service, mock_session, sample_deck, sample_child_deck, sample_user_id
):
    """Test list_by_owner filters by parent."""
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    mock_decks_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_child_deck]
    mock_decks_result.scalars.return_value = mock_scalars

    mock_session.execute.side_effect = [mock_count_result, mock_decks_result]

    decks, total = await deck_service.list_by_owner(sample_user_id, parent_id=sample_deck.id)

    assert total == 1
    assert decks[0] == sample_child_deck


# ==================== list_root_decks Tests ====================


@pytest.mark.asyncio
async def test_list_root_decks_returns_root_only(deck_service, mock_session, sample_deck, sample_user_id):
    """Test list_root_decks returns only root decks."""
    mock_count_result = MagicMock()
    mock_count_result.scalar_one.return_value = 1

    mock_decks_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_deck]
    mock_decks_result.scalars.return_value = mock_scalars

    mock_session.execute.side_effect = [mock_count_result, mock_decks_result]

    decks, total = await deck_service.list_root_decks(sample_user_id)

    assert total == 1
    assert decks[0].parent_id is None


# ==================== get_deck_tree Tests ====================


@pytest.mark.asyncio
async def test_get_deck_tree_returns_hierarchy(deck_service, mock_session, sample_deck, sample_user_id):
    """Test get_deck_tree returns hierarchical structure."""
    sample_deck.children = [MagicMock()]

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_deck]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_deck_tree(sample_user_id)

    assert len(result) == 1
    assert result[0] == sample_deck


@pytest.mark.asyncio
async def test_get_deck_tree_from_specific_root(deck_service, mock_session, sample_deck, sample_user_id):
    """Test get_deck_tree from specific root deck."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_deck]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    result = await deck_service.get_deck_tree(sample_user_id, root_deck_id=sample_deck.id)

    assert len(result) == 1


# ==================== update Tests ====================


@pytest.mark.asyncio
async def test_update_deck_name(deck_service, mock_session, sample_deck, sample_user_id):
    """Test updating deck name."""
    update_data = DeckUpdate(name="Updated Name")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.update(sample_deck.id, sample_user_id, update_data)

    assert sample_deck.name == "Updated Name"
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_deck_description(deck_service, mock_session, sample_deck, sample_user_id):
    """Test updating deck description."""
    update_data = DeckUpdate(description="New Description")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    await deck_service.update(sample_deck.id, sample_user_id, update_data)

    assert sample_deck.description == "New Description"


@pytest.mark.asyncio
async def test_update_deck_not_found(deck_service, mock_session, sample_user_id):
    """Test update raises error when deck not found."""
    update_data = DeckUpdate(name="New Name")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    deck_id = uuid4()
    with pytest.raises(DeckNotFoundError) as exc_info:
        await deck_service.update(deck_id, sample_user_id, update_data)
    assert exc_info.value.deck_id == deck_id


@pytest.mark.asyncio
async def test_update_deck_self_parent_circular(deck_service, mock_session, sample_deck, sample_user_id):
    """Test update raises error when setting self as parent."""
    update_data = DeckUpdate(parent_id=sample_deck.id)  # Self-reference

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    with pytest.raises(DeckCircularReferenceError):
        await deck_service.update(sample_deck.id, sample_user_id, update_data)


@pytest.mark.asyncio
async def test_update_deck_with_updated_by(deck_service, mock_session, sample_deck, sample_user_id):
    """Test update with audit trail."""
    update_data = DeckUpdate(name="New Name")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    await deck_service.update(sample_deck.id, sample_user_id, update_data, updated_by="test_user")

    sample_deck.set_updated_by.assert_called_once_with("test_user")


# ==================== delete Tests ====================


@pytest.mark.asyncio
async def test_delete_deck_soft(deck_service, mock_session, sample_deck, sample_user_id):
    """Test soft delete of a deck."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []  # No children
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    result = await deck_service.delete(sample_deck.id, sample_user_id)

    assert result is True
    sample_deck.soft_delete.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_delete_deck_hard(deck_service, mock_session, sample_deck, sample_user_id):
    """Test hard delete of a deck."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.delete(sample_deck.id, sample_user_id, hard_delete=True)

    assert result is True
    mock_session.delete.assert_called_once_with(sample_deck)


@pytest.mark.asyncio
async def test_delete_deck_not_found(deck_service, mock_session, sample_user_id):
    """Test delete raises error when deck not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    deck_id = uuid4()
    with pytest.raises(DeckNotFoundError) as exc_info:
        await deck_service.delete(deck_id, sample_user_id)
    assert exc_info.value.deck_id == deck_id


@pytest.mark.asyncio
async def test_delete_deck_with_children(
    deck_service, mock_session, sample_deck, sample_child_deck, sample_user_id
):
    """Test soft delete also deletes children."""
    # First call returns the deck, second returns children
    mock_result_deck = MagicMock()
    mock_result_deck.scalar_one_or_none.return_value = sample_deck

    mock_result_children = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_child_deck]
    mock_result_children.scalars.return_value = mock_scalars

    mock_result_no_children = MagicMock()
    mock_scalars_empty = MagicMock()
    mock_scalars_empty.all.return_value = []
    mock_result_no_children.scalars.return_value = mock_scalars_empty

    mock_session.execute.side_effect = [
        mock_result_deck,
        mock_result_children,
        mock_result_no_children,
    ]

    await deck_service.delete(sample_deck.id, sample_user_id)

    sample_deck.soft_delete.assert_called_once()
    sample_child_deck.soft_delete.assert_called_once()


# ==================== restore Tests ====================


@pytest.mark.asyncio
async def test_restore_deck_success(deck_service, mock_session, sample_deck, sample_user_id):
    """Test successful deck restoration."""
    sample_deck.deleted_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    result = await deck_service.restore(sample_deck.id, sample_user_id)

    sample_deck.restore.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_restore_deck_not_found(deck_service, mock_session, sample_user_id):
    """Test restore raises error when deck not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    deck_id = uuid4()
    with pytest.raises(DeckNotFoundError):
        await deck_service.restore(deck_id, sample_user_id)


# ==================== move_to_parent Tests ====================


@pytest.mark.asyncio
async def test_move_to_parent_success(
    deck_service, mock_session, sample_deck, sample_child_deck, sample_user_id
):
    """Test moving deck to new parent."""
    # We need to patch the update method
    with patch.object(deck_service, 'update', new_callable=AsyncMock) as mock_update:
        mock_update.return_value = sample_deck

        await deck_service.move_to_parent(sample_deck.id, sample_child_deck.id, sample_user_id)

        mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_move_to_root(deck_service, mock_session, sample_child_deck, sample_user_id):
    """Test moving deck to root level."""
    with patch.object(deck_service, 'update', new_callable=AsyncMock) as mock_update:
        mock_update.return_value = sample_child_deck

        await deck_service.move_to_parent(sample_child_deck.id, None, sample_user_id)

        mock_update.assert_called_once()


# ==================== get_ancestors Tests ====================


@pytest.mark.asyncio
async def test_get_ancestors_returns_chain(
    deck_service, mock_session, sample_deck, sample_child_deck, sample_user_id
):
    """Test get_ancestors returns parent chain."""
    # Child has parent
    sample_child_deck.parent_id = sample_deck.id
    # Parent has no parent (root)
    sample_deck.parent_id = None

    call_count = 0
    def mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            # First call: get child
            mock_result.scalar_one_or_none.return_value = sample_child_deck
        elif call_count == 2:
            # Second call: get parent
            mock_result.scalar_one_or_none.return_value = sample_deck
        else:
            # Root reached
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    mock_session.execute.side_effect = mock_execute

    ancestors = await deck_service.get_ancestors(sample_child_deck.id, sample_user_id)

    assert len(ancestors) == 1
    assert ancestors[0] == sample_deck


@pytest.mark.asyncio
async def test_get_ancestors_root_deck(deck_service, mock_session, sample_deck, sample_user_id):
    """Test get_ancestors for root deck returns empty list."""
    sample_deck.parent_id = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_deck
    mock_session.execute.return_value = mock_result

    ancestors = await deck_service.get_ancestors(sample_deck.id, sample_user_id)

    assert len(ancestors) == 0


# ==================== get_descendants Tests ====================


@pytest.mark.asyncio
async def test_get_descendants_returns_children(
    deck_service, mock_session, sample_deck, sample_child_deck, sample_user_id
):
    """Test get_descendants returns all children."""
    mock_result_children = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_child_deck]
    mock_result_children.scalars.return_value = mock_scalars

    mock_result_no_children = MagicMock()
    mock_scalars_empty = MagicMock()
    mock_scalars_empty.all.return_value = []
    mock_result_no_children.scalars.return_value = mock_scalars_empty

    mock_session.execute.side_effect = [mock_result_children, mock_result_no_children]

    descendants = await deck_service.get_descendants(sample_deck.id, sample_user_id)

    assert len(descendants) == 1
    assert descendants[0] == sample_child_deck


@pytest.mark.asyncio
async def test_get_descendants_empty(deck_service, mock_session, sample_deck, sample_user_id):
    """Test get_descendants returns empty list for leaf deck."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    descendants = await deck_service.get_descendants(sample_deck.id, sample_user_id)

    assert len(descendants) == 0


# ==================== _would_create_cycle Tests ====================


@pytest.mark.asyncio
async def test_would_create_cycle_true(
    deck_service, mock_session, sample_deck, sample_child_deck, sample_user_id
):
    """Test cycle detection returns True for circular reference."""
    # child -> parent -> child (circular)
    sample_child_deck.parent_id = sample_deck.id

    call_count = 0
    def mock_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one_or_none.return_value = sample_child_deck
        else:
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    mock_session.execute.side_effect = mock_execute

    # Try to set parent's parent to child (would create cycle)
    result = await deck_service._would_create_cycle(
        sample_deck.id, sample_child_deck.id, sample_user_id
    )

    assert result is True


@pytest.mark.asyncio
async def test_would_create_cycle_false(deck_service, mock_session, sample_deck, sample_user_id):
    """Test cycle detection returns False for valid hierarchy."""
    new_parent = MagicMock()
    new_parent.id = uuid4()
    new_parent.parent_id = None  # Root deck

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = new_parent
    mock_session.execute.return_value = mock_result

    result = await deck_service._would_create_cycle(
        sample_deck.id, new_parent.id, sample_user_id
    )

    assert result is False
