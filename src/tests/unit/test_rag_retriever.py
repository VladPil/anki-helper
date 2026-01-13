"""Unit tests for RAG CardRetriever.

Tests cover:
- search_similar (_vector_search) method
- search_by_text (_keyword_search) method
- hybrid_search (_hybrid_search) method
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.rag.retriever import CardRetriever
from src.services.rag.schemas import CardStatus, SearchResult, SearchType

# ==================== Fixtures ====================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_embedding_service():
    """Create a mock EmbeddingService for testing."""
    service = AsyncMock()
    service.embed = AsyncMock(return_value=[[0.1] * 1024])
    service.embed_single = AsyncMock(return_value=[0.1] * 1024)
    service.model_name = "test-embedding-model"
    service.dimension = 1024
    return service


@pytest.fixture
def retriever(mock_session, mock_embedding_service):
    """Create a CardRetriever instance with mocked dependencies."""
    return CardRetriever(db=mock_session, embeddings=mock_embedding_service)


def create_search_result(
    card_id=None,
    deck_id=None,
    similarity=0.9,
    status=CardStatus.DRAFT,
):
    """Helper to create SearchResult objects for testing."""
    return SearchResult(
        card_id=card_id or uuid4(),
        deck_id=deck_id or uuid4(),
        deck_name="Test Deck",
        fields={"front": "Question", "back": "Answer"},
        tags=["test"],
        status=status,
        similarity=similarity,
        content_text="Question: Question\nAnswer: Answer",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_search_results():
    """Create sample search result rows."""
    card_id_1 = uuid4()
    card_id_2 = uuid4()
    deck_id = uuid4()

    return [
        MagicMock(
            card_id=card_id_1,
            deck_id=deck_id,
            deck_name="Test Deck",
            fields={"front": "Question 1", "back": "Answer 1"},
            tags=["tag1"],
            status="draft",
            similarity=0.95,
            content_text="Question: Question 1\nAnswer: Answer 1",
            created_at=datetime.now(UTC),
        ),
        MagicMock(
            card_id=card_id_2,
            deck_id=deck_id,
            deck_name="Test Deck",
            fields={"front": "Question 2", "back": "Answer 2"},
            tags=["tag2"],
            status="approved",
            similarity=0.85,
            content_text="Question: Question 2\nAnswer: Answer 2",
            created_at=datetime.now(UTC),
        ),
    ]


# ==================== search_similar (Vector Search) Tests ====================


@pytest.mark.asyncio
class TestSearchSimilar:
    """Tests for search method with vector search type.

    Note: These tests mock _vector_search directly to avoid SQLAlchemy
    parameter binding issues with pgvector syntax (::vector cast).
    """

    async def test_vector_search_success(
        self, retriever, mock_embedding_service
    ):
        """Test successful vector similarity search."""
        user_id = uuid4()
        card_id_1 = uuid4()
        card_id_2 = uuid4()

        expected_results = [
            create_search_result(card_id=card_id_1, similarity=0.95),
            create_search_result(card_id=card_id_2, similarity=0.85),
        ]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            mock_vector.return_value = expected_results

            results = await retriever.search(
                query="What is Python?",
                user_id=user_id,
                k=5,
                threshold=0.7,
                search_type=SearchType.VECTOR,
            )

            assert len(results) == 2
            assert results[0].similarity == 0.95
            assert results[1].similarity == 0.85
            mock_vector.assert_called_once()

    async def test_vector_search_with_deck_filter(
        self, retriever, mock_embedding_service
    ):
        """Test vector search with deck ID filter."""
        user_id = uuid4()
        deck_id = uuid4()

        expected_results = [create_search_result(deck_id=deck_id, similarity=0.9)]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            mock_vector.return_value = expected_results

            results = await retriever.search(
                query="Test query",
                user_id=user_id,
                k=5,
                threshold=0.7,
                search_type=SearchType.VECTOR,
                deck_ids=[deck_id],
            )

            assert len(results) == 1
            # Verify _vector_search was called with correct arguments
            mock_vector.assert_called_once()
            # Check that deck_ids was passed (it's in positional args)
            call_args = mock_vector.call_args
            # Args: query, user_id, k, threshold, deck_ids, statuses, tags
            assert [deck_id] in call_args[0]

    async def test_vector_search_with_status_filter(
        self, retriever, mock_embedding_service
    ):
        """Test vector search with status filter."""
        user_id = uuid4()

        expected_results = [create_search_result(status=CardStatus.APPROVED)]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            mock_vector.return_value = expected_results

            results = await retriever.search(
                query="Test query",
                user_id=user_id,
                k=5,
                threshold=0.7,
                search_type=SearchType.VECTOR,
                statuses=[CardStatus.DRAFT, CardStatus.APPROVED],
            )

            assert len(results) == 1
            # Verify _vector_search was called
            mock_vector.assert_called_once()
            # Check that statuses was passed
            call_args = mock_vector.call_args
            assert [CardStatus.DRAFT, CardStatus.APPROVED] in call_args[0]

    async def test_vector_search_with_tags_filter(
        self, retriever, mock_embedding_service
    ):
        """Test vector search with tags filter."""
        user_id = uuid4()

        expected_results = [create_search_result()]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            mock_vector.return_value = expected_results

            results = await retriever.search(
                query="Test query",
                user_id=user_id,
                k=5,
                threshold=0.7,
                search_type=SearchType.VECTOR,
                tags=["python", "programming"],
            )

            assert len(results) == 1
            # Verify _vector_search was called
            mock_vector.assert_called_once()
            # Check that tags was passed
            call_args = mock_vector.call_args
            assert ["python", "programming"] in call_args[0]

    async def test_vector_search_no_results(
        self, retriever, mock_embedding_service
    ):
        """Test vector search with no matching results."""
        user_id = uuid4()

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            mock_vector.return_value = []

            results = await retriever.search(
                query="Very specific query with no matches",
                user_id=user_id,
                k=5,
                threshold=0.7,
                search_type=SearchType.VECTOR,
            )

            assert len(results) == 0

    async def test_vector_search_result_structure(
        self, retriever, mock_embedding_service
    ):
        """Test that search results have correct structure."""
        user_id = uuid4()

        expected_results = [
            create_search_result(similarity=0.95),
            create_search_result(similarity=0.85),
        ]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            mock_vector.return_value = expected_results

            results = await retriever.search(
                query="Test",
                user_id=user_id,
                search_type=SearchType.VECTOR,
            )

            assert len(results) == 2
            result = results[0]

            # Verify SearchResult structure
            assert hasattr(result, "card_id")
            assert hasattr(result, "deck_id")
            assert hasattr(result, "deck_name")
            assert hasattr(result, "fields")
            assert hasattr(result, "tags")
            assert hasattr(result, "status")
            assert hasattr(result, "similarity")
            assert hasattr(result, "content_text")
            assert hasattr(result, "created_at")


# ==================== search_by_text (Keyword Search) Tests ====================


@pytest.mark.asyncio
class TestSearchByText:
    """Tests for search method with keyword search type."""

    async def test_keyword_search_success(
        self, retriever, mock_session, sample_search_results
    ):
        """Test successful keyword search."""
        user_id = uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_search_results

        mock_session.execute.return_value = mock_result

        results = await retriever.search(
            query="Python programming",
            user_id=user_id,
            k=5,
            search_type=SearchType.KEYWORD,
        )

        assert len(results) == 2

    async def test_keyword_search_with_filters(
        self, retriever, mock_session, sample_search_results
    ):
        """Test keyword search with deck and status filters."""
        user_id = uuid4()
        deck_id = uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = sample_search_results[:1]

        mock_session.execute.return_value = mock_result

        results = await retriever.search(
            query="Python",
            user_id=user_id,
            k=5,
            search_type=SearchType.KEYWORD,
            deck_ids=[deck_id],
            statuses=[CardStatus.APPROVED],
        )

        assert len(results) == 1

    async def test_keyword_search_no_results(self, retriever, mock_session):
        """Test keyword search with no matching results."""
        user_id = uuid4()

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []

        mock_session.execute.return_value = mock_result

        results = await retriever.search(
            query="xyznonexistentterm",
            user_id=user_id,
            search_type=SearchType.KEYWORD,
        )

        assert len(results) == 0

    async def test_keyword_search_score_normalization(
        self, retriever, mock_session
    ):
        """Test that keyword search normalizes scores to 0-1."""
        user_id = uuid4()
        deck_id = uuid4()

        # Create results with different ts_rank scores
        search_results = [
            MagicMock(
                card_id=uuid4(),
                deck_id=deck_id,
                deck_name="Test Deck",
                fields={"front": "Q1", "back": "A1"},
                tags=[],
                status="draft",
                similarity=0.8,  # Will be normalized
                content_text="Q1 A1",
                created_at=datetime.now(UTC),
            ),
            MagicMock(
                card_id=uuid4(),
                deck_id=deck_id,
                deck_name="Test Deck",
                fields={"front": "Q2", "back": "A2"},
                tags=[],
                status="draft",
                similarity=0.4,  # Will be normalized
                content_text="Q2 A2",
                created_at=datetime.now(UTC),
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = search_results

        mock_session.execute.return_value = mock_result

        results = await retriever.search(
            query="test",
            user_id=user_id,
            search_type=SearchType.KEYWORD,
        )

        # First result should have similarity = 1.0 (max)
        assert results[0].similarity == 1.0
        # Second result should be normalized relative to max
        assert results[1].similarity == 0.5


# ==================== hybrid_search Tests ====================


@pytest.mark.asyncio
class TestHybridSearch:
    """Tests for search method with hybrid search type.

    Note: These tests mock _vector_search and _keyword_search directly
    to avoid SQLAlchemy parameter binding issues.
    """

    async def test_hybrid_search_success(
        self, retriever, mock_embedding_service
    ):
        """Test successful hybrid search combining vector and keyword."""
        user_id = uuid4()
        deck_id = uuid4()
        card_id_1 = uuid4()
        card_id_2 = uuid4()
        card_id_3 = uuid4()

        # Vector search results
        vector_results = [
            create_search_result(card_id=card_id_1, deck_id=deck_id, similarity=0.95),
            create_search_result(card_id=card_id_2, deck_id=deck_id, similarity=0.85),
        ]

        # Keyword search results (overlapping with vector)
        keyword_results = [
            create_search_result(card_id=card_id_1, deck_id=deck_id, similarity=0.9),
            create_search_result(card_id=card_id_3, deck_id=deck_id, similarity=0.7),
        ]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            with patch.object(retriever, "_keyword_search", new_callable=AsyncMock) as mock_keyword:
                mock_vector.return_value = vector_results
                mock_keyword.return_value = keyword_results

                results = await retriever.search(
                    query="test query",
                    user_id=user_id,
                    k=5,
                    threshold=0.7,
                    search_type=SearchType.HYBRID,
                )

                # Should combine results using RRF
                assert len(results) > 0
                # card_id_1 appears in both, should rank higher
                assert results[0].card_id == card_id_1

    async def test_hybrid_search_vector_only_results(
        self, retriever, mock_embedding_service
    ):
        """Test hybrid search when only vector search has results."""
        user_id = uuid4()
        card_id = uuid4()

        vector_results = [create_search_result(card_id=card_id, similarity=0.9)]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            with patch.object(retriever, "_keyword_search", new_callable=AsyncMock) as mock_keyword:
                mock_vector.return_value = vector_results
                mock_keyword.return_value = []

                results = await retriever.search(
                    query="test",
                    user_id=user_id,
                    k=5,
                    threshold=0.7,
                    search_type=SearchType.HYBRID,
                )

                assert len(results) == 1
                assert results[0].card_id == card_id

    async def test_hybrid_search_keyword_only_results(
        self, retriever, mock_embedding_service
    ):
        """Test hybrid search when only keyword search has results."""
        user_id = uuid4()
        card_id = uuid4()

        keyword_results = [create_search_result(card_id=card_id, similarity=0.8)]

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            with patch.object(retriever, "_keyword_search", new_callable=AsyncMock) as mock_keyword:
                mock_vector.return_value = []
                mock_keyword.return_value = keyword_results

                results = await retriever.search(
                    query="test",
                    user_id=user_id,
                    k=5,
                    threshold=0.7,
                    search_type=SearchType.HYBRID,
                )

                assert len(results) == 1
                assert results[0].card_id == card_id

    async def test_hybrid_search_no_results(
        self, retriever, mock_embedding_service
    ):
        """Test hybrid search with no results from either search type."""
        user_id = uuid4()

        with patch.object(retriever, "_vector_search", new_callable=AsyncMock) as mock_vector:
            with patch.object(retriever, "_keyword_search", new_callable=AsyncMock) as mock_keyword:
                mock_vector.return_value = []
                mock_keyword.return_value = []

                results = await retriever.search(
                    query="nonexistent",
                    user_id=user_id,
                    k=5,
                    threshold=0.7,
                    search_type=SearchType.HYBRID,
                )

                assert len(results) == 0


# ==================== search Method Dispatch Tests ====================


@pytest.mark.asyncio
class TestSearchDispatch:
    """Tests for search method dispatch to correct search type."""

    async def test_search_unknown_type(self, retriever, mock_session):
        """Test that unknown search type raises ValueError."""
        user_id = uuid4()

        with pytest.raises(ValueError, match="Unknown search type"):
            await retriever.search(
                query="test",
                user_id=user_id,
                search_type="invalid_type",
            )


# ==================== find_similar_to_card Tests ====================


@pytest.mark.asyncio
class TestFindSimilarToCard:
    """Tests for find_similar_to_card method."""

    async def test_find_similar_to_card_success(
        self, retriever, mock_session
    ):
        """Test finding cards similar to a given card."""
        user_id = uuid4()
        card_id = uuid4()
        similar_card_id = uuid4()
        deck_id = uuid4()

        # Mock: card embedding exists
        mock_result_embedding = MagicMock()
        mock_result_embedding.fetchone.return_value = MagicMock(
            embedding=[0.1] * 1024,
            content_text="Original card text",
        )

        # Mock: similar cards
        similar_results = [
            MagicMock(
                card_id=similar_card_id,
                deck_id=deck_id,
                deck_name="Test Deck",
                fields={"front": "Similar Q", "back": "Similar A"},
                tags=[],
                status="draft",
                similarity=0.9,
                content_text="Similar Q Similar A",
                created_at=datetime.now(UTC),
            ),
        ]
        mock_result_similar = MagicMock()
        mock_result_similar.fetchall.return_value = similar_results

        mock_session.execute.side_effect = [
            mock_result_embedding,
            mock_result_similar,
        ]

        results = await retriever.find_similar_to_card(
            card_id=card_id,
            user_id=user_id,
            k=5,
            threshold=0.7,
        )

        assert len(results) == 1
        assert results[0].card_id == similar_card_id

    async def test_find_similar_to_card_not_indexed(self, retriever, mock_session):
        """Test finding similar cards when source card is not indexed."""
        user_id = uuid4()
        card_id = uuid4()

        # Mock: card not found in index
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session.execute.return_value = mock_result

        results = await retriever.find_similar_to_card(
            card_id=card_id,
            user_id=user_id,
        )

        assert len(results) == 0

    async def test_find_similar_exclude_self(
        self, retriever, mock_session
    ):
        """Test that exclude_self parameter works correctly."""
        user_id = uuid4()
        card_id = uuid4()
        deck_id = uuid4()

        # Mock: card embedding exists
        mock_result_embedding = MagicMock()
        mock_result_embedding.fetchone.return_value = MagicMock(
            embedding=[0.1] * 1024,
            content_text="Original card text",
        )

        # Mock: empty results (card excluded itself)
        mock_result_similar = MagicMock()
        mock_result_similar.fetchall.return_value = []

        mock_session.execute.side_effect = [
            mock_result_embedding,
            mock_result_similar,
        ]

        results = await retriever.find_similar_to_card(
            card_id=card_id,
            user_id=user_id,
            exclude_self=True,
        )

        # Verify exclude_self is applied in query
        call_args = mock_session.execute.call_args_list[1]
        sql_text = str(call_args[0][0])
        assert "!=" in sql_text or "c.id != :card_id" in sql_text.replace(" ", "")


# ==================== find_duplicates Tests ====================


@pytest.mark.asyncio
class TestFindDuplicates:
    """Tests for find_duplicates method.

    Note: These tests mock the search method to avoid SQLAlchemy issues.
    """

    async def test_find_duplicates_with_matches(
        self, retriever, mock_embedding_service
    ):
        """Test duplicate detection with matching cards."""
        user_id = uuid4()
        existing_card_id = uuid4()

        cards_to_check = [
            {
                "temp_id": "temp_1",
                "fields": {"front": "Question 1", "back": "Answer 1"},
            },
        ]

        # Mock search to return a matching card
        matching_result = create_search_result(card_id=existing_card_id, similarity=0.95)

        with patch.object(retriever, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [matching_result]

            results = await retriever.find_duplicates(
                cards=cards_to_check,
                user_id=user_id,
                threshold=0.85,
            )

            assert len(results) == 1
            assert results[0]["temp_id"] == "temp_1"
            assert results[0]["is_duplicate"] is True
            assert results[0]["highest_similarity"] == 0.95
            assert len(results[0]["matches"]) == 1

    async def test_find_duplicates_no_matches(
        self, retriever, mock_embedding_service
    ):
        """Test duplicate detection with no matches."""
        user_id = uuid4()

        cards_to_check = [
            {
                "temp_id": "temp_1",
                "fields": {"front": "Unique Question", "back": "Unique Answer"},
            },
        ]

        with patch.object(retriever, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []

            results = await retriever.find_duplicates(
                cards=cards_to_check,
                user_id=user_id,
                threshold=0.85,
            )

            assert len(results) == 1
            assert results[0]["temp_id"] == "temp_1"
            assert results[0]["is_duplicate"] is False
            assert results[0]["highest_similarity"] == 0.0
            assert len(results[0]["matches"]) == 0

    async def test_find_duplicates_empty_fields(
        self, retriever, mock_session, mock_embedding_service
    ):
        """Test duplicate detection with empty fields."""
        user_id = uuid4()

        cards_to_check = [
            {
                "temp_id": "temp_1",
                "fields": {},
            },
        ]

        results = await retriever.find_duplicates(
            cards=cards_to_check,
            user_id=user_id,
            threshold=0.85,
        )

        assert len(results) == 1
        assert results[0]["temp_id"] == "temp_1"
        assert results[0]["is_duplicate"] is False

    async def test_find_duplicates_multiple_cards(
        self, retriever, mock_embedding_service
    ):
        """Test duplicate detection with multiple cards."""
        user_id = uuid4()
        existing_card_id = uuid4()

        cards_to_check = [
            {
                "temp_id": "temp_1",
                "fields": {"front": "Duplicate Q", "back": "Duplicate A"},
            },
            {
                "temp_id": "temp_2",
                "fields": {"front": "Unique Q", "back": "Unique A"},
            },
        ]

        # First card has duplicate, second doesn't
        matching_result = create_search_result(card_id=existing_card_id, similarity=0.90)

        with patch.object(retriever, "search", new_callable=AsyncMock) as mock_search:
            # First call returns match, second returns empty
            mock_search.side_effect = [
                [matching_result],
                [],
            ]

            results = await retriever.find_duplicates(
                cards=cards_to_check,
                user_id=user_id,
                threshold=0.85,
            )

            assert len(results) == 2
            assert results[0]["is_duplicate"] is True
            assert results[1]["is_duplicate"] is False


# ==================== get_deck_coverage Tests ====================


@pytest.mark.asyncio
class TestGetDeckCoverage:
    """Tests for get_deck_coverage method."""

    async def test_get_deck_coverage_full(self, retriever, mock_session):
        """Test getting coverage for fully indexed deck."""
        deck_id = uuid4()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(
            total_cards=100,
            indexed_cards=100,
        )

        mock_session.execute.return_value = mock_result

        coverage = await retriever.get_deck_coverage(deck_id)

        assert coverage["deck_id"] == deck_id
        assert coverage["total_cards"] == 100
        assert coverage["indexed_cards"] == 100
        assert coverage["unindexed_cards"] == 0
        assert coverage["coverage_percent"] == 100.0

    async def test_get_deck_coverage_partial(self, retriever, mock_session):
        """Test getting coverage for partially indexed deck."""
        deck_id = uuid4()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(
            total_cards=100,
            indexed_cards=75,
        )

        mock_session.execute.return_value = mock_result

        coverage = await retriever.get_deck_coverage(deck_id)

        assert coverage["total_cards"] == 100
        assert coverage["indexed_cards"] == 75
        assert coverage["unindexed_cards"] == 25
        assert coverage["coverage_percent"] == 75.0

    async def test_get_deck_coverage_empty(self, retriever, mock_session):
        """Test getting coverage for empty deck."""
        deck_id = uuid4()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(
            total_cards=0,
            indexed_cards=0,
        )

        mock_session.execute.return_value = mock_result

        coverage = await retriever.get_deck_coverage(deck_id)

        assert coverage["total_cards"] == 0
        assert coverage["indexed_cards"] == 0
        assert coverage["coverage_percent"] == 0


# ==================== _fields_to_text Tests ====================


class TestFieldsToText:
    """Tests for _fields_to_text helper method."""

    def test_fields_to_text_basic(self, retriever):
        """Test converting basic fields to text."""
        fields = {"front": "Question", "back": "Answer"}

        result = retriever._fields_to_text(fields)

        assert "Question" in result
        assert "Answer" in result

    def test_fields_to_text_with_extra_fields(self, retriever):
        """Test converting fields with additional fields."""
        fields = {
            "front": "Question",
            "back": "Answer",
            "hint": "Some hint",
        }

        result = retriever._fields_to_text(fields)

        assert "Question" in result
        assert "Answer" in result
        assert "Some hint" in result

    def test_fields_to_text_empty(self, retriever):
        """Test converting empty fields."""
        fields = {}

        result = retriever._fields_to_text(fields)

        assert result == ""

    def test_fields_to_text_only_front(self, retriever):
        """Test converting fields with only front."""
        fields = {"front": "Question Only"}

        result = retriever._fields_to_text(fields)

        assert result == "Question Only"
