"""Unit tests for RAGService.

Tests cover:
- index_card method
- search method
- get_similar_cards (find_similar_cards) method
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.rag.schemas import CardStatus, SearchType

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
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_indexer():
    """Create a mock CardIndexer for testing."""
    indexer = AsyncMock()
    indexer.index_card = AsyncMock(return_value=True)
    indexer.index_cards = AsyncMock(return_value=(5, 0, []))
    indexer.index_user_cards = AsyncMock(return_value=(10, 2, []))
    indexer.remove_card = AsyncMock(return_value=True)
    indexer.reindex_user_cards = AsyncMock(return_value=(5, 10, 0))
    indexer.get_index_stats = AsyncMock(return_value={
        "total_cards": 100,
        "indexed_cards": 75,
        "unindexed_cards": 25,
        "coverage_percent": 75.0,
    })
    return indexer


@pytest.fixture
def mock_retriever():
    """Create a mock CardRetriever for testing."""
    retriever = AsyncMock()
    retriever.search = AsyncMock(return_value=[])
    retriever.find_duplicates = AsyncMock(return_value=[])
    retriever.find_similar_to_card = AsyncMock(return_value=[])
    return retriever


@pytest.fixture
def mock_search_result():
    """Create a mock SearchResult object."""
    return MagicMock(
        card_id=uuid4(),
        deck_id=uuid4(),
        deck_name="Test Deck",
        fields={"front": "Question", "back": "Answer"},
        tags=["test"],
        status=CardStatus.DRAFT,
        similarity=0.95,
        content_text="Question: Question\nAnswer: Answer",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def rag_service(mock_session, mock_embedding_service, mock_indexer, mock_retriever):
    """Create a RAGService instance with mocked dependencies."""
    with patch("src.rag.service.EmbeddingService", return_value=mock_embedding_service):
        with patch("src.rag.service.CardIndexer", return_value=mock_indexer):
            with patch("src.rag.service.CardRetriever", return_value=mock_retriever):
                from src.services.rag.service import RAGService
                service = RAGService(db=mock_session, redis=None)
                # Manually set mocks for direct access
                service.embeddings = mock_embedding_service
                service.indexer = mock_indexer
                service.retriever = mock_retriever
                return service


# ==================== index_card Tests ====================


@pytest.mark.asyncio
class TestIndexCard:
    """Tests for RAGService.index_card method."""

    async def test_index_card_success(self, rag_service, mock_indexer):
        """Test successful card indexing."""
        card_id = uuid4()
        mock_indexer.index_card.return_value = True

        await rag_service.index_card(card_id)

        mock_indexer.index_card.assert_called_once_with(card_id, force=False)

    async def test_index_card_already_indexed(self, rag_service, mock_indexer):
        """Test indexing card that's already indexed."""
        card_id = uuid4()
        mock_indexer.index_card.return_value = False

        # Should not raise
        await rag_service.index_card(card_id)

        mock_indexer.index_card.assert_called_once()

    async def test_index_card_failure(self, rag_service, mock_indexer):
        """Test card indexing failure."""
        card_id = uuid4()
        mock_indexer.index_card.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await rag_service.index_card(card_id)


# ==================== search Tests ====================


@pytest.mark.asyncio
class TestSearch:
    """Tests for RAGService.search method."""

    async def test_search_vector_success(self, rag_service, mock_retriever, mock_search_result):
        """Test successful vector search."""
        user_id = uuid4()
        mock_retriever.search.return_value = [mock_search_result]

        results = await rag_service.search(
            query="What is Python?",
            user_id=user_id,
            k=5,
            threshold=0.7,
            search_type=SearchType.VECTOR,
        )

        assert len(results) == 1
        assert results[0]["similarity"] == 0.95
        assert results[0]["fields"] == {"front": "Question", "back": "Answer"}
        mock_retriever.search.assert_called_once()

    async def test_search_keyword_success(self, rag_service, mock_retriever, mock_search_result):
        """Test successful keyword search."""
        user_id = uuid4()
        mock_retriever.search.return_value = [mock_search_result]

        results = await rag_service.search(
            query="Python programming",
            user_id=user_id,
            search_type=SearchType.KEYWORD,
        )

        assert len(results) == 1
        mock_retriever.search.assert_called_once_with(
            query="Python programming",
            user_id=user_id,
            k=5,
            threshold=0.7,
            search_type=SearchType.KEYWORD,
            deck_ids=None,
            statuses=None,
            tags=None,
        )

    async def test_search_hybrid_success(self, rag_service, mock_retriever, mock_search_result):
        """Test successful hybrid search."""
        user_id = uuid4()
        mock_retriever.search.return_value = [mock_search_result]

        results = await rag_service.search(
            query="test query",
            user_id=user_id,
            search_type=SearchType.HYBRID,
        )

        assert len(results) == 1
        mock_retriever.search.assert_called_once_with(
            query="test query",
            user_id=user_id,
            k=5,
            threshold=0.7,
            search_type=SearchType.HYBRID,
            deck_ids=None,
            statuses=None,
            tags=None,
        )

    async def test_search_with_filters(self, rag_service, mock_retriever, mock_search_result):
        """Test search with deck, status, and tag filters."""
        user_id = uuid4()
        deck_ids = [uuid4(), uuid4()]
        statuses = [CardStatus.DRAFT, CardStatus.APPROVED]
        tags = ["python", "programming"]

        mock_retriever.search.return_value = [mock_search_result]

        results = await rag_service.search(
            query="test",
            user_id=user_id,
            deck_ids=deck_ids,
            statuses=statuses,
            tags=tags,
        )

        assert len(results) == 1
        mock_retriever.search.assert_called_once_with(
            query="test",
            user_id=user_id,
            k=5,
            threshold=0.7,
            search_type=SearchType.VECTOR,
            deck_ids=deck_ids,
            statuses=statuses,
            tags=tags,
        )

    async def test_search_no_results(self, rag_service, mock_retriever):
        """Test search with no matching results."""
        user_id = uuid4()
        mock_retriever.search.return_value = []

        results = await rag_service.search(
            query="nonexistent query",
            user_id=user_id,
        )

        assert len(results) == 0

    async def test_search_failure(self, rag_service, mock_retriever):
        """Test search failure."""
        user_id = uuid4()
        mock_retriever.search.side_effect = Exception("Search failed")

        with pytest.raises(Exception, match="Search failed"):
            await rag_service.search(
                query="test",
                user_id=user_id,
            )

    async def test_search_result_serialization(self, rag_service, mock_retriever, mock_search_result):
        """Test that search results are properly serialized."""
        user_id = uuid4()
        mock_retriever.search.return_value = [mock_search_result]

        results = await rag_service.search(
            query="test",
            user_id=user_id,
        )

        assert len(results) == 1
        result = results[0]

        # Verify serialization
        assert isinstance(result["card_id"], str)
        assert isinstance(result["deck_id"], str)
        assert isinstance(result["deck_name"], str)
        assert isinstance(result["fields"], dict)
        assert isinstance(result["tags"], list)
        assert isinstance(result["status"], str)
        assert isinstance(result["similarity"], float)
        assert isinstance(result["content_text"], str)
        assert isinstance(result["created_at"], str)


# ==================== get_similar_cards (find_similar_cards) Tests ====================


@pytest.mark.asyncio
class TestGetSimilarCards:
    """Tests for RAGService.find_similar_cards method."""

    async def test_find_similar_cards_success(self, rag_service, mock_retriever, mock_search_result):
        """Test successful similar cards search."""
        card_id = uuid4()
        user_id = uuid4()
        mock_retriever.find_similar_to_card.return_value = [mock_search_result]

        results = await rag_service.find_similar_cards(
            card_id=card_id,
            user_id=user_id,
            k=5,
            threshold=0.7,
        )

        assert len(results) == 1
        assert results[0]["similarity"] == 0.95
        mock_retriever.find_similar_to_card.assert_called_once_with(
            card_id=card_id,
            user_id=user_id,
            k=5,
            threshold=0.7,
            exclude_self=True,
        )

    async def test_find_similar_cards_no_results(self, rag_service, mock_retriever):
        """Test finding similar cards with no matches."""
        card_id = uuid4()
        user_id = uuid4()
        mock_retriever.find_similar_to_card.return_value = []

        results = await rag_service.find_similar_cards(
            card_id=card_id,
            user_id=user_id,
        )

        assert len(results) == 0

    async def test_find_similar_cards_default_parameters(self, rag_service, mock_retriever):
        """Test finding similar cards with default parameters."""
        card_id = uuid4()
        user_id = uuid4()
        mock_retriever.find_similar_to_card.return_value = []

        await rag_service.find_similar_cards(
            card_id=card_id,
            user_id=user_id,
        )

        mock_retriever.find_similar_to_card.assert_called_once_with(
            card_id=card_id,
            user_id=user_id,
            k=5,
            threshold=0.7,
            exclude_self=True,
        )


# ==================== find_duplicates Tests ====================


@pytest.mark.asyncio
class TestFindDuplicates:
    """Tests for RAGService.find_duplicates method."""

    async def test_find_duplicates_success(self, rag_service, mock_retriever):
        """Test successful duplicate detection."""
        user_id = uuid4()
        cards = [
            {"temp_id": "temp_1", "fields": {"front": "Q1", "back": "A1"}},
        ]
        mock_retriever.find_duplicates.return_value = [
            {
                "temp_id": "temp_1",
                "is_duplicate": True,
                "matches": [{"existing_card_id": uuid4(), "similarity": 0.9}],
                "highest_similarity": 0.9,
            }
        ]

        results = await rag_service.find_duplicates(
            user_id=user_id,
            cards=cards,
            threshold=0.85,
        )

        assert len(results) == 1
        assert results[0]["is_duplicate"] is True
        mock_retriever.find_duplicates.assert_called_once()

    async def test_find_duplicates_no_duplicates(self, rag_service, mock_retriever):
        """Test duplicate detection with no duplicates found."""
        user_id = uuid4()
        cards = [
            {"temp_id": "temp_1", "fields": {"front": "Unique Q", "back": "Unique A"}},
        ]
        mock_retriever.find_duplicates.return_value = [
            {
                "temp_id": "temp_1",
                "is_duplicate": False,
                "matches": [],
                "highest_similarity": 0.0,
            }
        ]

        results = await rag_service.find_duplicates(
            user_id=user_id,
            cards=cards,
        )

        assert len(results) == 1
        assert results[0]["is_duplicate"] is False


# ==================== index_user_cards Tests ====================


@pytest.mark.asyncio
class TestIndexUserCards:
    """Tests for RAGService.index_user_cards method."""

    async def test_index_user_cards_success(self, rag_service, mock_indexer):
        """Test successful user cards indexing."""
        user_id = uuid4()
        mock_indexer.index_user_cards.return_value = (10, 5, [])

        count = await rag_service.index_user_cards(user_id)

        assert count == 10
        mock_indexer.index_user_cards.assert_called_once_with(user_id, force=False)

    async def test_index_user_cards_with_failures(self, rag_service, mock_indexer):
        """Test user cards indexing with some failures."""
        user_id = uuid4()
        failed_ids = [uuid4(), uuid4()]
        mock_indexer.index_user_cards.return_value = (8, 2, failed_ids)

        count = await rag_service.index_user_cards(user_id)

        assert count == 8

    async def test_index_user_cards_failure(self, rag_service, mock_indexer):
        """Test user cards indexing failure."""
        user_id = uuid4()
        mock_indexer.index_user_cards.side_effect = Exception("Indexing failed")

        with pytest.raises(Exception, match="Indexing failed"):
            await rag_service.index_user_cards(user_id)


# ==================== remove_from_index Tests ====================


@pytest.mark.asyncio
class TestRemoveFromIndex:
    """Tests for RAGService.remove_from_index method."""

    async def test_remove_from_index_success(self, rag_service, mock_indexer):
        """Test successful card removal from index."""
        card_id = uuid4()
        mock_indexer.remove_card.return_value = True

        await rag_service.remove_from_index(card_id)

        mock_indexer.remove_card.assert_called_once_with(card_id)

    async def test_remove_from_index_not_found(self, rag_service, mock_indexer):
        """Test removing card that's not in index."""
        card_id = uuid4()
        mock_indexer.remove_card.return_value = False

        # Should not raise
        await rag_service.remove_from_index(card_id)


# ==================== reindex_user_cards Tests ====================


@pytest.mark.asyncio
class TestReindexUserCards:
    """Tests for RAGService.reindex_user_cards method."""

    async def test_reindex_user_cards_success(self, rag_service, mock_indexer):
        """Test successful user cards reindexing."""
        user_id = uuid4()
        mock_indexer.reindex_user_cards.return_value = (50, 100, 5)

        result = await rag_service.reindex_user_cards(user_id)

        assert result["deleted_count"] == 50
        assert result["indexed_count"] == 100
        assert result["failed_count"] == 5
        assert "latency_ms" in result
        mock_indexer.reindex_user_cards.assert_called_once_with(user_id, True)

    async def test_reindex_user_cards_keep_existing(self, rag_service, mock_indexer):
        """Test reindexing without deleting existing."""
        user_id = uuid4()
        mock_indexer.reindex_user_cards.return_value = (0, 50, 0)

        result = await rag_service.reindex_user_cards(user_id, delete_existing=False)

        assert result["deleted_count"] == 0
        mock_indexer.reindex_user_cards.assert_called_once_with(user_id, False)


# ==================== get_index_stats Tests ====================


@pytest.mark.asyncio
class TestGetIndexStats:
    """Tests for RAGService.get_index_stats method."""

    async def test_get_index_stats_success(self, rag_service, mock_indexer):
        """Test getting index statistics."""
        user_id = uuid4()
        expected_stats = {
            "total_cards": 100,
            "indexed_cards": 75,
            "unindexed_cards": 25,
            "coverage_percent": 75.0,
        }
        mock_indexer.get_index_stats.return_value = expected_stats

        stats = await rag_service.get_index_stats(user_id)

        assert stats == expected_stats
        mock_indexer.get_index_stats.assert_called_once_with(user_id)


# ==================== close Tests ====================


@pytest.mark.asyncio
class TestClose:
    """Tests for RAGService.close method."""

    async def test_close_success(self, rag_service, mock_embedding_service):
        """Test successful service closure."""
        await rag_service.close()

        mock_embedding_service.close.assert_called_once()


# ==================== get_rag_service Factory Tests ====================


@pytest.mark.asyncio
class TestGetRagServiceFactory:
    """Tests for get_rag_service factory function."""

    async def test_get_rag_service(self, mock_session):
        """Test creating RAG service via factory."""
        with patch("src.rag.service.EmbeddingService"):
            with patch("src.rag.service.CardIndexer"):
                with patch("src.rag.service.CardRetriever"):
                    from src.services.rag.service import get_rag_service

                    service = await get_rag_service(db=mock_session, redis=None)

                    assert service is not None
                    assert hasattr(service, "search")
                    assert hasattr(service, "index_card")
                    assert hasattr(service, "find_similar_cards")


# ==================== Prometheus Metrics Tests ====================


@pytest.mark.asyncio
class TestPrometheusMetrics:
    """Tests for Prometheus metrics recording."""

    async def test_search_records_metrics(self, rag_service, mock_retriever, mock_search_result):
        """Test that search operations record Prometheus metrics."""
        user_id = uuid4()
        mock_retriever.search.return_value = [mock_search_result]

        # The search method should record metrics
        # We're mainly verifying it doesn't raise
        await rag_service.search(
            query="test",
            user_id=user_id,
            search_type=SearchType.VECTOR,
        )

        mock_retriever.search.assert_called_once()

    async def test_index_records_metrics(self, rag_service, mock_indexer):
        """Test that index operations record Prometheus metrics."""
        card_id = uuid4()
        mock_indexer.index_card.return_value = True

        # The index_card method should record metrics
        await rag_service.index_card(card_id)

        mock_indexer.index_card.assert_called_once()
