"""Unit tests for RAG CardIndexer.

Tests cover:
- index_card method
- index_cards (batch) method
- delete_card_index (remove_card) method
- update_card_index (index_card with force=True)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.rag.indexer import CardIndexer


# ==================== Fixtures ====================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_embedding_service():
    """Create a mock EmbeddingService for testing."""
    service = AsyncMock()
    service.embed = AsyncMock(return_value=[[0.1] * 1024])
    service.embed_single = AsyncMock(return_value=[0.1] * 1024)
    service.model_name = "test-embedding-model"
    service.provider_name = "test-provider"
    service.dimension = 1024
    return service


@pytest.fixture
def indexer(mock_session, mock_embedding_service):
    """Create a CardIndexer instance with mocked dependencies."""
    with patch("src.rag.indexer.settings") as mock_settings:
        mock_settings.embedding.batch_size = 10
        indexer = CardIndexer(db=mock_session, embeddings=mock_embedding_service)
        return indexer


# ==================== _card_to_text Tests ====================


class TestCardToText:
    """Tests for _card_to_text internal method."""

    def test_card_to_text_basic(self, indexer):
        """Test converting basic card fields to text."""
        card = {
            "fields": {
                "front": "What is Python?",
                "back": "A programming language",
            },
            "tags": [],
        }

        result = indexer._card_to_text(card)

        assert "Question: What is Python?" in result
        assert "Answer: A programming language" in result

    def test_card_to_text_with_tags(self, indexer):
        """Test card with tags."""
        card = {
            "fields": {
                "front": "Question",
                "back": "Answer",
            },
            "tags": ["python", "programming"],
        }

        result = indexer._card_to_text(card)

        assert "Tags: python, programming" in result

    def test_card_to_text_with_extra_fields(self, indexer):
        """Test card with extra fields beyond front/back."""
        card = {
            "fields": {
                "front": "Question",
                "back": "Answer",
                "hint": "Some hint",
                "source": "Book XYZ",
            },
            "tags": [],
        }

        result = indexer._card_to_text(card)

        assert "Hint: Some hint" in result
        assert "Source: Book XYZ" in result

    def test_card_to_text_empty_fields(self, indexer):
        """Test card with empty fields."""
        card = {
            "fields": {},
            "tags": [],
        }

        result = indexer._card_to_text(card)

        assert result == ""

    def test_card_to_text_missing_tags(self, indexer):
        """Test card without tags key."""
        card = {
            "fields": {
                "front": "Question",
                "back": "Answer",
            },
        }

        result = indexer._card_to_text(card)

        assert "Question: Question" in result
        assert "Tags:" not in result


# ==================== index_card Tests ====================


@pytest.mark.asyncio
class TestIndexCard:
    """Tests for index_card method."""

    async def test_index_card_new_card(self, indexer, mock_session, mock_embedding_service):
        """Test indexing a new card that doesn't exist in the index."""
        card_id = uuid4()

        # Mock: no existing embedding
        mock_result_existing = MagicMock()
        mock_result_existing.fetchone.return_value = None

        # Mock: card data
        card_row = MagicMock()
        card_row.id = card_id
        card_row.fields = {"front": "Question", "back": "Answer"}
        card_row.tags = ["test"]
        mock_result_card = MagicMock()
        mock_result_card.fetchone.return_value = card_row

        # Mock: embedder ID
        embedder_row = MagicMock()
        embedder_row.id = uuid4()
        mock_result_embedder = MagicMock()
        mock_result_embedder.fetchone.return_value = embedder_row

        mock_session.execute.side_effect = [
            mock_result_existing,  # Check existing
            mock_result_card,  # Fetch card
            mock_result_embedder,  # Get embedder
            MagicMock(),  # Insert embedding
        ]

        result = await indexer.index_card(card_id)

        assert result is True
        mock_embedding_service.embed_single.assert_called_once()
        assert mock_session.execute.call_count == 4

    async def test_index_card_already_indexed(self, indexer, mock_session, mock_embedding_service):
        """Test that already indexed card is skipped when force=False."""
        card_id = uuid4()

        # Mock: embedding exists
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock()  # Existing row

        mock_session.execute.return_value = mock_result

        result = await indexer.index_card(card_id, force=False)

        assert result is False
        mock_embedding_service.embed_single.assert_not_called()

    async def test_index_card_force_reindex(self, indexer, mock_session, mock_embedding_service):
        """Test force reindexing an existing card."""
        card_id = uuid4()

        # Mock: card data (skip existence check with force=True)
        card_row = MagicMock()
        card_row.id = card_id
        card_row.fields = {"front": "Updated Question", "back": "Updated Answer"}
        card_row.tags = []
        mock_result_card = MagicMock()
        mock_result_card.fetchone.return_value = card_row

        # Mock: embedder ID
        embedder_row = MagicMock()
        embedder_row.id = uuid4()
        mock_result_embedder = MagicMock()
        mock_result_embedder.fetchone.return_value = embedder_row

        mock_session.execute.side_effect = [
            mock_result_card,  # Fetch card
            mock_result_embedder,  # Get embedder
            MagicMock(),  # Insert/update embedding
        ]

        result = await indexer.index_card(card_id, force=True)

        assert result is True
        mock_embedding_service.embed_single.assert_called_once()

    async def test_index_card_not_found(self, indexer, mock_session, mock_embedding_service):
        """Test indexing a card that doesn't exist."""
        card_id = uuid4()

        # Mock: no existing embedding
        mock_result_existing = MagicMock()
        mock_result_existing.fetchone.return_value = None

        # Mock: card not found
        mock_result_card = MagicMock()
        mock_result_card.fetchone.return_value = None

        mock_session.execute.side_effect = [
            mock_result_existing,  # Check existing
            mock_result_card,  # Fetch card (not found)
        ]

        result = await indexer.index_card(card_id)

        assert result is False
        mock_embedding_service.embed_single.assert_not_called()


# ==================== index_cards (Batch) Tests ====================


@pytest.mark.asyncio
class TestIndexCardsBatch:
    """Tests for index_cards batch method."""

    async def test_index_cards_empty_list(self, indexer):
        """Test indexing empty list of cards."""
        result = await indexer.index_cards([])

        assert result == (0, 0, [])

    async def test_index_cards_batch_success(self, indexer, mock_session, mock_embedding_service):
        """Test successful batch indexing."""
        card_ids = [uuid4() for _ in range(3)]

        # Mock: no existing embeddings
        mock_result_existing = MagicMock()
        mock_result_existing.fetchall.return_value = []

        # Mock: card data
        cards_data = [
            MagicMock(id=card_ids[0], fields={"front": "Q1", "back": "A1"}, tags=[]),
            MagicMock(id=card_ids[1], fields={"front": "Q2", "back": "A2"}, tags=[]),
            MagicMock(id=card_ids[2], fields={"front": "Q3", "back": "A3"}, tags=[]),
        ]
        mock_result_cards = MagicMock()
        mock_result_cards.fetchall.return_value = cards_data

        # Mock: embedder ID
        embedder_row = MagicMock()
        embedder_row.id = uuid4()
        mock_result_embedder = MagicMock()
        mock_result_embedder.fetchone.return_value = embedder_row

        # Mock embeddings
        mock_embedding_service.embed.return_value = [[0.1] * 1024 for _ in range(3)]

        mock_session.execute.side_effect = [
            mock_result_existing,  # Check existing
            mock_result_cards,  # Fetch cards
            mock_result_embedder,  # Get embedder
            MagicMock(),  # Insert embedding 1
            MagicMock(),  # Insert embedding 2
            MagicMock(),  # Insert embedding 3
        ]

        indexed, skipped, failed = await indexer.index_cards(card_ids)

        assert indexed == 3
        assert skipped == 0
        assert len(failed) == 0

    async def test_index_cards_partial_existing(self, indexer, mock_session, mock_embedding_service):
        """Test batch indexing with some cards already indexed."""
        card_ids = [uuid4() for _ in range(3)]

        # Mock: one card already indexed
        mock_result_existing = MagicMock()
        mock_result_existing.fetchall.return_value = [MagicMock(card_id=card_ids[0])]

        # Mock: card data (only 2 cards to index)
        cards_data = [
            MagicMock(id=card_ids[1], fields={"front": "Q2", "back": "A2"}, tags=[]),
            MagicMock(id=card_ids[2], fields={"front": "Q3", "back": "A3"}, tags=[]),
        ]
        mock_result_cards = MagicMock()
        mock_result_cards.fetchall.return_value = cards_data

        # Mock: embedder ID
        embedder_row = MagicMock()
        embedder_row.id = uuid4()
        mock_result_embedder = MagicMock()
        mock_result_embedder.fetchone.return_value = embedder_row

        # Mock embeddings
        mock_embedding_service.embed.return_value = [[0.1] * 1024 for _ in range(2)]

        mock_session.execute.side_effect = [
            mock_result_existing,  # Check existing
            mock_result_cards,  # Fetch cards
            mock_result_embedder,  # Get embedder
            MagicMock(),  # Insert embedding 1
            MagicMock(),  # Insert embedding 2
        ]

        indexed, skipped, failed = await indexer.index_cards(card_ids, force=False)

        assert indexed == 2
        assert skipped == 1
        assert len(failed) == 0

    async def test_index_cards_embedding_failure(self, indexer, mock_session, mock_embedding_service):
        """Test batch indexing with embedding generation failure."""
        card_ids = [uuid4() for _ in range(2)]

        # Mock: no existing embeddings
        mock_result_existing = MagicMock()
        mock_result_existing.fetchall.return_value = []

        # Mock: card data
        cards_data = [
            MagicMock(id=card_ids[0], fields={"front": "Q1", "back": "A1"}, tags=[]),
            MagicMock(id=card_ids[1], fields={"front": "Q2", "back": "A2"}, tags=[]),
        ]
        mock_result_cards = MagicMock()
        mock_result_cards.fetchall.return_value = cards_data

        mock_session.execute.side_effect = [
            mock_result_existing,  # Check existing
            mock_result_cards,  # Fetch cards
        ]

        # Embedding service fails
        mock_embedding_service.embed.side_effect = Exception("Embedding service unavailable")

        indexed, skipped, failed = await indexer.index_cards(card_ids)

        assert indexed == 0
        assert skipped == 0
        assert len(failed) == 2

    async def test_index_cards_no_cards_found(self, indexer, mock_session, mock_embedding_service):
        """Test batch indexing when cards are not found in database."""
        card_ids = [uuid4() for _ in range(2)]

        # Mock: no existing embeddings
        mock_result_existing = MagicMock()
        mock_result_existing.fetchall.return_value = []

        # Mock: no cards found
        mock_result_cards = MagicMock()
        mock_result_cards.fetchall.return_value = []

        mock_session.execute.side_effect = [
            mock_result_existing,  # Check existing
            mock_result_cards,  # Fetch cards (empty)
        ]

        indexed, skipped, failed = await indexer.index_cards(card_ids)

        assert indexed == 0
        assert skipped == 0
        assert len(failed) == 2  # Both card_ids failed


# ==================== remove_card (delete_card_index) Tests ====================


@pytest.mark.asyncio
class TestDeleteCardIndex:
    """Tests for remove_card method (delete_card_index)."""

    async def test_remove_card_success(self, indexer, mock_session):
        """Test successful removal of card from index."""
        card_id = uuid4()

        # Mock: card was deleted
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(card_id=card_id)

        mock_session.execute.return_value = mock_result

        result = await indexer.remove_card(card_id)

        assert result is True
        mock_session.execute.assert_called_once()

    async def test_remove_card_not_found(self, indexer, mock_session):
        """Test removing card that doesn't exist in index."""
        card_id = uuid4()

        # Mock: card not found
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session.execute.return_value = mock_result

        result = await indexer.remove_card(card_id)

        assert result is False


# ==================== update_card_index Tests ====================


@pytest.mark.asyncio
class TestUpdateCardIndex:
    """Tests for update_card_index (index_card with force=True)."""

    async def test_update_card_index(self, indexer, mock_session, mock_embedding_service):
        """Test updating an existing card's index."""
        card_id = uuid4()

        # Mock: card data
        card_row = MagicMock()
        card_row.id = card_id
        card_row.fields = {"front": "New Question", "back": "New Answer"}
        card_row.tags = ["updated"]
        mock_result_card = MagicMock()
        mock_result_card.fetchone.return_value = card_row

        # Mock: embedder ID
        embedder_row = MagicMock()
        embedder_row.id = uuid4()
        mock_result_embedder = MagicMock()
        mock_result_embedder.fetchone.return_value = embedder_row

        mock_session.execute.side_effect = [
            mock_result_card,  # Fetch card
            mock_result_embedder,  # Get embedder
            MagicMock(),  # Insert/update embedding
        ]

        # Using force=True is equivalent to update_card_index
        result = await indexer.index_card(card_id, force=True)

        assert result is True
        mock_embedding_service.embed_single.assert_called_once()

        # Verify the text includes updated content
        call_args = mock_embedding_service.embed_single.call_args
        embedded_text = call_args[0][0]
        assert "New Question" in embedded_text
        assert "New Answer" in embedded_text


# ==================== _get_or_create_embedder_id Tests ====================


@pytest.mark.asyncio
class TestGetOrCreateEmbedderId:
    """Tests for _get_or_create_embedder_id internal method."""

    async def test_get_existing_embedder_id(self, indexer, mock_session):
        """Test getting existing embedder ID."""
        existing_id = uuid4()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(id=existing_id)

        mock_session.execute.return_value = mock_result

        result = await indexer._get_or_create_embedder_id()

        assert result == existing_id
        mock_session.execute.assert_called_once()

    async def test_create_new_embedder_id(self, indexer, mock_session):
        """Test creating new embedder ID when not found."""
        new_id = uuid4()

        # First call: not found
        mock_result_not_found = MagicMock()
        mock_result_not_found.fetchone.return_value = None

        # Second call: created
        mock_result_created = MagicMock()
        mock_result_created.fetchone.return_value = MagicMock(id=new_id)

        mock_session.execute.side_effect = [
            mock_result_not_found,
            mock_result_created,
        ]

        result = await indexer._get_or_create_embedder_id()

        assert result == new_id
        assert mock_session.execute.call_count == 2


# ==================== index_user_cards Tests ====================


@pytest.mark.asyncio
class TestIndexUserCards:
    """Tests for index_user_cards method."""

    async def test_index_user_cards_success(self, indexer, mock_session, mock_embedding_service):
        """Test indexing all cards for a user."""
        user_id = uuid4()
        card_ids = [uuid4() for _ in range(2)]

        # Mock: get user's card IDs
        card_rows = [MagicMock(id=cid) for cid in card_ids]
        mock_result_card_ids = MagicMock()
        mock_result_card_ids.fetchall.return_value = card_rows

        # Mock: no existing embeddings
        mock_result_existing = MagicMock()
        mock_result_existing.fetchall.return_value = []

        # Mock: card data
        cards_data = [
            MagicMock(id=card_ids[0], fields={"front": "Q1", "back": "A1"}, tags=[]),
            MagicMock(id=card_ids[1], fields={"front": "Q2", "back": "A2"}, tags=[]),
        ]
        mock_result_cards = MagicMock()
        mock_result_cards.fetchall.return_value = cards_data

        # Mock: embedder ID
        embedder_row = MagicMock()
        embedder_row.id = uuid4()
        mock_result_embedder = MagicMock()
        mock_result_embedder.fetchone.return_value = embedder_row

        mock_embedding_service.embed.return_value = [[0.1] * 1024 for _ in range(2)]

        mock_session.execute.side_effect = [
            mock_result_card_ids,  # Get user card IDs
            mock_result_existing,  # Check existing
            mock_result_cards,  # Fetch cards
            mock_result_embedder,  # Get embedder
            MagicMock(),  # Insert embedding 1
            MagicMock(),  # Insert embedding 2
        ]

        indexed, skipped, failed = await indexer.index_user_cards(user_id)

        assert indexed == 2
        assert skipped == 0
        assert len(failed) == 0


# ==================== get_index_stats Tests ====================


@pytest.mark.asyncio
class TestGetIndexStats:
    """Tests for get_index_stats method."""

    async def test_get_index_stats(self, indexer, mock_session):
        """Test getting index statistics."""
        user_id = uuid4()

        # Mock: total cards
        mock_result_total = MagicMock()
        mock_result_total.fetchone.return_value = MagicMock(total=100)

        # Mock: indexed cards
        mock_result_indexed = MagicMock()
        mock_result_indexed.fetchone.return_value = MagicMock(indexed=75)

        mock_session.execute.side_effect = [
            mock_result_total,
            mock_result_indexed,
        ]

        stats = await indexer.get_index_stats(user_id)

        assert stats["total_cards"] == 100
        assert stats["indexed_cards"] == 75
        assert stats["unindexed_cards"] == 25
        assert stats["coverage_percent"] == 75.0

    async def test_get_index_stats_empty(self, indexer, mock_session):
        """Test getting index stats with no cards."""
        user_id = uuid4()

        # Mock: no cards
        mock_result_total = MagicMock()
        mock_result_total.fetchone.return_value = MagicMock(total=0)

        mock_result_indexed = MagicMock()
        mock_result_indexed.fetchone.return_value = MagicMock(indexed=0)

        mock_session.execute.side_effect = [
            mock_result_total,
            mock_result_indexed,
        ]

        stats = await indexer.get_index_stats(user_id)

        assert stats["total_cards"] == 0
        assert stats["indexed_cards"] == 0
        assert stats["coverage_percent"] == 0
