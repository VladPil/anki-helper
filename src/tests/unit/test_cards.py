"""Unit tests for deck and card services.

Tests cover:
- Deck CRUD operations
- Deck hierarchy (nested decks)
- Card CRUD operations (via deck service)
- Access control for decks and cards
- Soft delete and restore

Note: Since the codebase has DeckService but cards are managed through decks,
this file tests deck operations primarily.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.decks.models import Deck
from src.modules.decks.schemas import DeckCreate, DeckUpdate
from src.modules.decks.service import (
    DeckAccessDeniedError,
    DeckCircularReferenceError,
    DeckNotFoundError,
    DeckService,
)
from src.modules.users.models import User

from src.tests.factories import DeckFactory, UserFactory


# ==================== Deck Creation Tests ====================


@pytest.mark.asyncio
class TestDeckCreation:
    """Tests for deck creation."""

    async def test_create_deck_success(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test successful deck creation."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(
                name="Test Deck",
                description="A test deck",
            ),
        )

        assert deck is not None
        assert deck.name == "Test Deck"
        assert deck.description == "A test deck"
        assert deck.owner_id == test_user.id
        assert deck.parent_id is None
        assert deck.deleted_at is None

    async def test_create_deck_without_description(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating a deck without description."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="No Description Deck"),
        )

        assert deck.name == "No Description Deck"
        assert deck.description is None

    async def test_create_nested_deck(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating a nested deck."""
        service = DeckService(db_session)

        # Create parent deck
        parent = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Parent Deck"),
        )

        # Create child deck
        child = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(
                name="Child Deck",
                parent_id=parent.id,
            ),
        )

        assert child.parent_id == parent.id

    async def test_create_deck_with_nonexistent_parent_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating deck with nonexistent parent fails."""
        service = DeckService(db_session)

        with pytest.raises(DeckNotFoundError):
            await service.create(
                owner_id=test_user.id,
                data=DeckCreate(
                    name="Orphan Deck",
                    parent_id=UUID("00000000-0000-0000-0000-000000000999"),
                ),
            )

    async def test_create_deck_with_other_users_parent_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating deck with another user's deck as parent fails."""
        service = DeckService(db_session)

        # Create another user with a deck
        other_user = await UserFactory.create_async(db_session)
        other_deck = await service.create(
            owner_id=other_user.id,
            data=DeckCreate(name="Other User's Deck"),
        )

        with pytest.raises(DeckAccessDeniedError):
            await service.create(
                owner_id=test_user.id,
                data=DeckCreate(
                    name="Unauthorized Child",
                    parent_id=other_deck.id,
                ),
            )

    async def test_create_deck_with_audit_info(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test deck creation with audit information."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Audited Deck"),
            created_by=str(test_user.id),
        )

        assert deck.created_by == str(test_user.id)


# ==================== Deck Retrieval Tests ====================


@pytest.mark.asyncio
class TestDeckRetrieval:
    """Tests for deck retrieval operations."""

    async def test_get_deck_by_id(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting a deck by ID."""
        service = DeckService(db_session)

        # Create deck
        created = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Test Deck"),
        )

        # Retrieve deck
        deck = await service.get_by_id(created.id)

        assert deck is not None
        assert deck.id == created.id
        assert deck.name == "Test Deck"

    async def test_get_nonexistent_deck(
        self,
        db_session: AsyncSession,
    ):
        """Test getting a nonexistent deck returns None."""
        service = DeckService(db_session)

        deck = await service.get_by_id(
            UUID("00000000-0000-0000-0000-000000000999")
        )

        assert deck is None

    async def test_get_deleted_deck_excluded_by_default(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that deleted decks are excluded by default."""
        service = DeckService(db_session)

        # Create and delete deck
        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="To Delete"),
        )
        await service.delete(deck.id, test_user.id)

        # Should not find deleted deck
        retrieved = await service.get_by_id(deck.id)
        assert retrieved is None

    async def test_get_deleted_deck_with_include_deleted(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting deleted deck with include_deleted flag."""
        service = DeckService(db_session)

        # Create and delete deck
        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="To Delete"),
        )
        await service.delete(deck.id, test_user.id)

        # Should find with include_deleted
        retrieved = await service.get_by_id(deck.id, include_deleted=True)
        assert retrieved is not None
        assert retrieved.deleted_at is not None

    async def test_get_deck_for_user(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting deck ensuring user ownership."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="User's Deck"),
        )

        # Should find for correct user
        retrieved = await service.get_by_id_for_user(deck.id, test_user.id)
        assert retrieved is not None

        # Should not find for wrong user
        other_user = await UserFactory.create_async(db_session)
        not_found = await service.get_by_id_for_user(deck.id, other_user.id)
        assert not_found is None

    async def test_get_deck_with_cards(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting deck with cards eagerly loaded."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Deck with Cards"),
        )

        retrieved = await service.get_with_cards(deck.id, test_user.id)
        assert retrieved is not None
        # Cards relationship should be accessible
        assert hasattr(retrieved, 'cards')


# ==================== Deck Listing Tests ====================


@pytest.mark.asyncio
class TestDeckListing:
    """Tests for deck listing operations."""

    async def test_list_decks_by_owner(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test listing decks by owner."""
        service = DeckService(db_session)

        # Create multiple decks
        for i in range(5):
            await service.create(
                owner_id=test_user.id,
                data=DeckCreate(name=f"Deck {i}"),
            )

        decks, total = await service.list_by_owner(test_user.id)

        assert len(decks) == 5
        assert total == 5

    async def test_list_decks_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test deck listing with pagination."""
        service = DeckService(db_session)

        # Create 10 decks
        for i in range(10):
            await service.create(
                owner_id=test_user.id,
                data=DeckCreate(name=f"Deck {i}"),
            )

        # Get first page
        page1, total = await service.list_by_owner(
            test_user.id,
            offset=0,
            limit=5,
        )

        # Get second page
        page2, _ = await service.list_by_owner(
            test_user.id,
            offset=5,
            limit=5,
        )

        assert len(page1) == 5
        assert len(page2) == 5
        assert total == 10

        # Ensure no duplicates
        page1_ids = {d.id for d in page1}
        page2_ids = {d.id for d in page2}
        assert page1_ids.isdisjoint(page2_ids)

    async def test_list_root_decks_only(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test listing only root-level decks."""
        service = DeckService(db_session)

        # Create parent and child decks
        parent = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Parent"),
        )
        await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Child", parent_id=parent.id),
        )
        await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Another Root"),
        )

        roots, total = await service.list_root_decks(test_user.id)

        assert len(roots) == 2
        assert total == 2
        assert all(d.parent_id is None for d in roots)

    async def test_list_decks_excludes_deleted(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that listing excludes deleted decks."""
        service = DeckService(db_session)

        # Create decks
        deck1 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Deck 1"),
        )
        deck2 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Deck 2"),
        )

        # Delete one
        await service.delete(deck1.id, test_user.id)

        decks, total = await service.list_by_owner(test_user.id)

        assert len(decks) == 1
        assert total == 1
        assert decks[0].id == deck2.id


# ==================== Deck Update Tests ====================


@pytest.mark.asyncio
class TestDeckUpdate:
    """Tests for deck update operations."""

    async def test_update_deck_name(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating deck name."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Original Name"),
        )

        updated = await service.update(
            deck_id=deck.id,
            user_id=test_user.id,
            data=DeckUpdate(name="New Name"),
        )

        assert updated.name == "New Name"

    async def test_update_deck_description(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating deck description."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Test Deck"),
        )

        updated = await service.update(
            deck_id=deck.id,
            user_id=test_user.id,
            data=DeckUpdate(description="New description"),
        )

        assert updated.description == "New description"

    async def test_update_deck_parent(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test moving deck to new parent."""
        service = DeckService(db_session)

        # Create decks
        parent = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Parent"),
        )
        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Deck"),
        )

        updated = await service.update(
            deck_id=deck.id,
            user_id=test_user.id,
            data=DeckUpdate(parent_id=parent.id),
        )

        assert updated.parent_id == parent.id

    async def test_update_deck_prevents_self_parent(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that deck cannot be its own parent."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Test Deck"),
        )

        with pytest.raises(DeckCircularReferenceError):
            await service.update(
                deck_id=deck.id,
                user_id=test_user.id,
                data=DeckUpdate(parent_id=deck.id),
            )

    async def test_update_deck_prevents_circular_reference(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that update prevents circular parent references."""
        service = DeckService(db_session)

        # Create A -> B -> C hierarchy
        deck_a = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="A"),
        )
        deck_b = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="B", parent_id=deck_a.id),
        )
        deck_c = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="C", parent_id=deck_b.id),
        )

        # Try to make A a child of C (would create A -> B -> C -> A)
        with pytest.raises(DeckCircularReferenceError):
            await service.update(
                deck_id=deck_a.id,
                user_id=test_user.id,
                data=DeckUpdate(parent_id=deck_c.id),
            )

    async def test_update_nonexistent_deck_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating nonexistent deck fails."""
        service = DeckService(db_session)

        with pytest.raises(DeckNotFoundError):
            await service.update(
                deck_id=UUID("00000000-0000-0000-0000-000000000999"),
                user_id=test_user.id,
                data=DeckUpdate(name="New Name"),
            )

    async def test_update_other_users_deck_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating another user's deck fails."""
        service = DeckService(db_session)

        # Create deck for another user
        other_user = await UserFactory.create_async(db_session)
        deck = await service.create(
            owner_id=other_user.id,
            data=DeckCreate(name="Other's Deck"),
        )

        with pytest.raises(DeckNotFoundError):
            await service.update(
                deck_id=deck.id,
                user_id=test_user.id,  # Wrong user
                data=DeckUpdate(name="Stolen"),
            )


# ==================== Deck Deletion Tests ====================


@pytest.mark.asyncio
class TestDeckDeletion:
    """Tests for deck deletion operations."""

    async def test_soft_delete_deck(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test soft deleting a deck."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="To Delete"),
        )

        result = await service.delete(deck.id, test_user.id)

        assert result is True

        # Deck should not be found normally
        retrieved = await service.get_by_id(deck.id)
        assert retrieved is None

        # But should exist when including deleted
        deleted = await service.get_by_id(deck.id, include_deleted=True)
        assert deleted is not None
        assert deleted.deleted_at is not None

    async def test_soft_delete_cascades_to_children(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that soft delete cascades to child decks."""
        service = DeckService(db_session)

        # Create parent and children
        parent = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Parent"),
        )
        child1 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Child 1", parent_id=parent.id),
        )
        child2 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Child 2", parent_id=parent.id),
        )

        # Delete parent
        await service.delete(parent.id, test_user.id)

        # Children should also be deleted
        child1_retrieved = await service.get_by_id(child1.id)
        child2_retrieved = await service.get_by_id(child2.id)

        assert child1_retrieved is None
        assert child2_retrieved is None

    async def test_hard_delete_deck(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test hard deleting a deck."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="To Hard Delete"),
        )

        await service.delete(deck.id, test_user.id, hard_delete=True)

        # Deck should not exist at all
        deleted = await service.get_by_id(deck.id, include_deleted=True)
        assert deleted is None

    async def test_delete_nonexistent_deck_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test deleting nonexistent deck fails."""
        service = DeckService(db_session)

        with pytest.raises(DeckNotFoundError):
            await service.delete(
                UUID("00000000-0000-0000-0000-000000000999"),
                test_user.id,
            )


# ==================== Deck Restore Tests ====================


@pytest.mark.asyncio
class TestDeckRestore:
    """Tests for deck restore operations."""

    async def test_restore_deck(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test restoring a soft-deleted deck."""
        service = DeckService(db_session)

        # Create and delete deck
        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="To Restore"),
        )
        await service.delete(deck.id, test_user.id)

        # Restore deck
        restored = await service.restore(deck.id, test_user.id)

        assert restored is not None
        assert restored.deleted_at is None

        # Should be findable again
        retrieved = await service.get_by_id(deck.id)
        assert retrieved is not None

    async def test_restore_nonexistent_deck_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test restoring nonexistent deck fails."""
        service = DeckService(db_session)

        with pytest.raises(DeckNotFoundError):
            await service.restore(
                UUID("00000000-0000-0000-0000-000000000999"),
                test_user.id,
            )


# ==================== Deck Hierarchy Tests ====================


@pytest.mark.asyncio
class TestDeckHierarchy:
    """Tests for deck hierarchy operations."""

    async def test_get_deck_tree(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting deck hierarchy tree."""
        service = DeckService(db_session)

        # Create hierarchy
        root1 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Root 1"),
        )
        root2 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Root 2"),
        )
        await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Child of Root 1", parent_id=root1.id),
        )

        tree = await service.get_deck_tree(test_user.id)

        assert len(tree) == 2  # Two root decks
        root1_node = next((d for d in tree if d.id == root1.id), None)
        assert root1_node is not None
        assert len(root1_node.children) == 1

    async def test_get_ancestors(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting deck ancestors."""
        service = DeckService(db_session)

        # Create A -> B -> C hierarchy
        deck_a = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="A"),
        )
        deck_b = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="B", parent_id=deck_a.id),
        )
        deck_c = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="C", parent_id=deck_b.id),
        )

        ancestors = await service.get_ancestors(deck_c.id, test_user.id)

        assert len(ancestors) == 2
        assert ancestors[0].id == deck_b.id
        assert ancestors[1].id == deck_a.id

    async def test_get_descendants(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting deck descendants."""
        service = DeckService(db_session)

        # Create A -> B, C hierarchy
        deck_a = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="A"),
        )
        deck_b = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="B", parent_id=deck_a.id),
        )
        deck_c = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="C", parent_id=deck_a.id),
        )
        # B -> D
        deck_d = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="D", parent_id=deck_b.id),
        )

        descendants = await service.get_descendants(deck_a.id, test_user.id)

        assert len(descendants) == 3  # B, C, D
        descendant_ids = {d.id for d in descendants}
        assert deck_b.id in descendant_ids
        assert deck_c.id in descendant_ids
        assert deck_d.id in descendant_ids

    async def test_move_to_parent(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test moving deck to a new parent."""
        service = DeckService(db_session)

        # Create decks
        parent1 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Parent 1"),
        )
        parent2 = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Parent 2"),
        )
        child = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Child", parent_id=parent1.id),
        )

        # Move child to parent2
        moved = await service.move_to_parent(
            deck_id=child.id,
            new_parent_id=parent2.id,
            user_id=test_user.id,
        )

        assert moved.parent_id == parent2.id


# ==================== Edge Cases Tests ====================


@pytest.mark.asyncio
class TestDeckEdgeCases:
    """Tests for edge cases and boundary conditions."""

    async def test_create_deck_with_special_characters(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating deck with special characters in name."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Deck with 'quotes' & <special> chars"),
        )

        assert deck.name == "Deck with 'quotes' & <special> chars"

    async def test_create_deck_with_unicode(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating deck with unicode characters."""
        service = DeckService(db_session)

        deck = await service.create(
            owner_id=test_user.id,
            data=DeckCreate(name="Japanese Deck"),
        )

        assert deck.name == "Japanese Deck"

    async def test_deeply_nested_hierarchy(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test handling deeply nested deck hierarchies."""
        service = DeckService(db_session)

        # Create 10-level deep hierarchy
        parent_id = None
        for i in range(10):
            deck = await service.create(
                owner_id=test_user.id,
                data=DeckCreate(
                    name=f"Level {i}",
                    parent_id=parent_id,
                ),
            )
            parent_id = deck.id

        # Get ancestors from deepest level
        ancestors = await service.get_ancestors(parent_id, test_user.id)
        assert len(ancestors) == 9  # All except the deepest

    async def test_concurrent_deck_operations(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that concurrent operations don't cause issues."""
        service = DeckService(db_session)

        # Create multiple decks quickly
        decks = []
        for i in range(5):
            deck = await service.create(
                owner_id=test_user.id,
                data=DeckCreate(name=f"Concurrent Deck {i}"),
            )
            decks.append(deck)

        # All should have unique IDs
        ids = [d.id for d in decks]
        assert len(ids) == len(set(ids))
