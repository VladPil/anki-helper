"""
RAG Service - Main orchestrator for RAG operations.

Provides a unified interface for:
    - Searching similar cards
    - Finding duplicate cards
    - Indexing and reindexing cards
    - Managing card embeddings
"""

import logging
import time
from uuid import UUID

from prometheus_client import Counter, Histogram
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.rag.embeddings import EmbeddingService
from src.services.rag.indexer import CardIndexer
from src.services.rag.retriever import CardRetriever
from src.services.rag.schemas import (
    CardStatus,
    SearchType,
)

logger = logging.getLogger(__name__)


# Prometheus metrics
RAG_SEARCH_COUNT = Counter(
    "rag_searches_total",
    "Total RAG searches",
    ["search_type"],
)

RAG_SEARCH_LATENCY = Histogram(
    "rag_search_duration_seconds",
    "RAG search latency",
    ["search_type"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

RAG_INDEX_COUNT = Counter(
    "rag_index_operations_total",
    "Total RAG index operations",
    ["operation"],
)

RAG_INDEX_LATENCY = Histogram(
    "rag_index_duration_seconds",
    "RAG index latency",
    ["operation"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
)


class RAGService:
    """
    Main RAG service orchestrating indexing and retrieval operations.

    This service provides the primary interface for RAG functionality,
    delegating to specialized components (indexer, retriever, embeddings).
    """

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis | None = None,
    ) -> None:
        """
        Initialize the RAG service.

        Args:
            db: Database session.
            redis: Optional Redis client for embedding caching.
        """
        self.db = db
        self.embeddings = EmbeddingService(redis=redis)
        self.indexer = CardIndexer(db, self.embeddings)
        self.retriever = CardRetriever(db, self.embeddings)

    async def search(
        self,
        query: str,
        user_id: UUID,
        k: int = 5,
        threshold: float = 0.7,
        search_type: SearchType = SearchType.VECTOR,
        deck_ids: list[UUID] | None = None,
        statuses: list[CardStatus] | None = None,
        tags: list[str] | None = None,
    ) -> list[dict]:
        """
        Search for similar cards using vector similarity.

        Args:
            query: Search query text.
            user_id: User ID to scope the search.
            k: Number of results to return.
            threshold: Minimum similarity threshold (0-1).
            search_type: Type of search (vector, keyword, hybrid).
            deck_ids: Optional list of deck IDs to filter by.
            statuses: Optional list of card statuses to filter by.
            tags: Optional list of tags to filter by.

        Returns:
            List of search results as dictionaries.
        """
        start_time = time.perf_counter()

        try:
            results = await self.retriever.search(
                query=query,
                user_id=user_id,
                k=k,
                threshold=threshold,
                search_type=search_type,
                deck_ids=deck_ids,
                statuses=statuses,
                tags=tags,
            )

            # Record metrics
            latency = time.perf_counter() - start_time
            RAG_SEARCH_COUNT.labels(search_type=search_type.value).inc()
            RAG_SEARCH_LATENCY.labels(search_type=search_type.value).observe(latency)

            logger.info(
                f"Search completed: query='{query[:50]}...', "
                f"results={len(results)}, latency={latency:.3f}s"
            )

            # Convert to dict for easier serialization
            return [
                {
                    "card_id": str(r.card_id),
                    "deck_id": str(r.deck_id),
                    "deck_name": r.deck_name,
                    "fields": r.fields,
                    "tags": r.tags,
                    "status": r.status.value,
                    "similarity": r.similarity,
                    "content_text": r.content_text,
                    "created_at": r.created_at.isoformat(),
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def find_duplicates(
        self,
        user_id: UUID,
        cards: list[dict],
        threshold: float = 0.85,
    ) -> list[dict]:
        """
        Find potential duplicate cards.

        Args:
            user_id: User ID to check against existing cards.
            cards: List of cards to check. Each dict should have 'temp_id' and 'fields'.
            threshold: Similarity threshold for duplicate detection (default: 0.85).

        Returns:
            List of duplicate check results.
        """
        start_time = time.perf_counter()

        try:
            results = await self.retriever.find_duplicates(
                cards=cards,
                user_id=user_id,
                threshold=threshold,
            )

            latency = time.perf_counter() - start_time
            duplicates_found = sum(1 for r in results if r.get("is_duplicate", False))

            logger.info(
                f"Duplicate check completed: cards={len(cards)}, "
                f"duplicates_found={duplicates_found}, latency={latency:.3f}s"
            )

            return results

        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            raise

    async def index_card(self, card_id: UUID) -> None:
        """
        Index a single card.

        Args:
            card_id: UUID of the card to index.
        """
        start_time = time.perf_counter()

        try:
            indexed = await self.indexer.index_card(card_id, force=False)

            latency = time.perf_counter() - start_time
            RAG_INDEX_COUNT.labels(operation="index_single").inc()
            RAG_INDEX_LATENCY.labels(operation="index_single").observe(latency)

            if indexed:
                logger.info(f"Card {card_id} indexed in {latency:.3f}s")
            else:
                logger.debug(f"Card {card_id} already indexed, skipped")

        except Exception as e:
            logger.error(f"Failed to index card {card_id}: {e}")
            raise

    async def index_user_cards(self, user_id: UUID) -> int:
        """
        Index all cards for a user.

        Args:
            user_id: User UUID.

        Returns:
            Number of cards indexed.
        """
        start_time = time.perf_counter()

        try:
            indexed_count, skipped_count, failed_ids = await self.indexer.index_user_cards(
                user_id, force=False
            )

            latency = time.perf_counter() - start_time
            RAG_INDEX_COUNT.labels(operation="index_user").inc()
            RAG_INDEX_LATENCY.labels(operation="index_user").observe(latency)

            logger.info(
                f"Indexed {indexed_count} cards for user {user_id} "
                f"(skipped={skipped_count}, failed={len(failed_ids)}) "
                f"in {latency:.3f}s"
            )

            return indexed_count

        except Exception as e:
            logger.error(f"Failed to index cards for user {user_id}: {e}")
            raise

    async def remove_from_index(self, card_id: UUID) -> None:
        """
        Remove a card from the index.

        Args:
            card_id: UUID of the card to remove.
        """
        start_time = time.perf_counter()

        try:
            removed = await self.indexer.remove_card(card_id)

            latency = time.perf_counter() - start_time
            RAG_INDEX_COUNT.labels(operation="remove").inc()
            RAG_INDEX_LATENCY.labels(operation="remove").observe(latency)

            if removed:
                logger.info(f"Card {card_id} removed from index in {latency:.3f}s")
            else:
                logger.debug(f"Card {card_id} not found in index")

        except Exception as e:
            logger.error(f"Failed to remove card {card_id} from index: {e}")
            raise

    async def reindex_user_cards(
        self,
        user_id: UUID,
        delete_existing: bool = True,
    ) -> dict:
        """
        Reindex all cards for a user.

        Args:
            user_id: User UUID.
            delete_existing: Whether to delete existing embeddings first.

        Returns:
            Dictionary with reindex statistics.
        """
        start_time = time.perf_counter()

        try:
            deleted_count, indexed_count, failed_count = await self.indexer.reindex_user_cards(
                user_id, delete_existing
            )

            latency = time.perf_counter() - start_time
            RAG_INDEX_COUNT.labels(operation="reindex").inc()
            RAG_INDEX_LATENCY.labels(operation="reindex").observe(latency)

            logger.info(
                f"Reindexed cards for user {user_id}: "
                f"deleted={deleted_count}, indexed={indexed_count}, "
                f"failed={failed_count}, latency={latency:.3f}s"
            )

            return {
                "deleted_count": deleted_count,
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "latency_ms": int(latency * 1000),
            }

        except Exception as e:
            logger.error(f"Failed to reindex cards for user {user_id}: {e}")
            raise

    async def get_index_stats(self, user_id: UUID) -> dict:
        """
        Get indexing statistics for a user.

        Args:
            user_id: User UUID.

        Returns:
            Dictionary with index statistics.
        """
        return await self.indexer.get_index_stats(user_id)

    async def find_similar_cards(
        self,
        card_id: UUID,
        user_id: UUID,
        k: int = 5,
        threshold: float = 0.7,
    ) -> list[dict]:
        """
        Find cards similar to a given card.

        Args:
            card_id: Card ID to find similar cards for.
            user_id: User ID to scope the search.
            k: Number of results to return.
            threshold: Minimum similarity threshold.

        Returns:
            List of similar cards.
        """
        results = await self.retriever.find_similar_to_card(
            card_id=card_id,
            user_id=user_id,
            k=k,
            threshold=threshold,
            exclude_self=True,
        )

        return [
            {
                "card_id": str(r.card_id),
                "deck_id": str(r.deck_id),
                "deck_name": r.deck_name,
                "fields": r.fields,
                "tags": r.tags,
                "status": r.status.value,
                "similarity": r.similarity,
                "content_text": r.content_text,
                "created_at": r.created_at.isoformat(),
            }
            for r in results
        ]

    async def close(self) -> None:
        """Clean up resources."""
        await self.embeddings.close()


# Factory function for dependency injection
async def get_rag_service(
    db: AsyncSession,
    redis: Redis | None = None,
) -> RAGService:
    """
    Create a RAGService instance.

    This function is intended to be used with FastAPI's dependency injection.

    Args:
        db: Database session.
        redis: Optional Redis client.

    Returns:
        RAGService instance.
    """
    return RAGService(db=db, redis=redis)
