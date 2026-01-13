"""
Card retriever for searching similar cards using pgvector.

Supports multiple search modes:
    - Vector similarity search (cosine distance)
    - Keyword search (full-text search)
    - Hybrid search (combining vector and keyword)

Filtering capabilities:
    - By user
    - By deck(s)
    - By card status
    - By tags
"""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.rag.embeddings import EmbeddingService
from src.services.rag.schemas import CardStatus, SearchResult, SearchType

logger = logging.getLogger(__name__)


class CardRetriever:
    """
    Retrieves similar cards using vector similarity and/or keyword search.

    Uses pgvector for efficient similarity search with various distance metrics.
    """

    def __init__(
        self,
        db: AsyncSession,
        embeddings: EmbeddingService,
    ) -> None:
        """
        Initialize the card retriever.

        Args:
            db: Database session.
            embeddings: Embedding service for generating query vectors.
        """
        self.db = db
        self.embeddings = embeddings

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
    ) -> list[SearchResult]:
        """
        Search for similar cards.

        Args:
            query: Search query text.
            user_id: User ID to scope the search.
            k: Number of results to return.
            threshold: Minimum similarity threshold (0-1).
            search_type: Type of search to perform.
            deck_ids: Optional list of deck IDs to filter by.
            statuses: Optional list of card statuses to filter by.
            tags: Optional list of tags to filter by (ANY match).

        Returns:
            List of search results sorted by similarity.
        """
        if search_type == SearchType.VECTOR:
            return await self._vector_search(query, user_id, k, threshold, deck_ids, statuses, tags)
        elif search_type == SearchType.KEYWORD:
            return await self._keyword_search(query, user_id, k, deck_ids, statuses, tags)
        elif search_type == SearchType.HYBRID:
            return await self._hybrid_search(query, user_id, k, threshold, deck_ids, statuses, tags)
        else:
            raise ValueError(f"Unknown search type: {search_type}")

    async def _vector_search(
        self,
        query: str,
        user_id: UUID,
        k: int,
        threshold: float,
        deck_ids: list[UUID] | None,
        statuses: list[CardStatus] | None,
        tags: list[str] | None,
    ) -> list[SearchResult]:
        """
        Perform vector similarity search using pgvector.

        Uses cosine distance for similarity comparison.
        """
        # Generate query embedding
        query_embedding = await self.embeddings.embed_single(query)

        # Build the SQL query with filters
        filters = ["d.owner_id = :user_id", "c.deleted_at IS NULL", "d.deleted_at IS NULL"]
        params: dict = {"user_id": user_id, "embedding": str(query_embedding), "k": k}

        if deck_ids:
            filters.append("c.deck_id = ANY(:deck_ids)")
            params["deck_ids"] = deck_ids

        if statuses:
            status_values = [s.value for s in statuses]
            filters.append("c.status = ANY(:statuses)")
            params["statuses"] = status_values

        if tags:
            filters.append("c.tags && :tags")
            params["tags"] = tags

        where_clause = " AND ".join(filters)

        # Use cosine distance (<=>) for similarity
        # Convert distance to similarity: 1 - distance
        sql = f"""
            SELECT
                c.id as card_id,
                c.deck_id,
                d.name as deck_name,
                c.fields,
                c.tags,
                c.status,
                c.created_at,
                ce.content_text,
                1 - (ce.embedding <=> :embedding::vector) as similarity
            FROM card_embeddings ce
            JOIN cards c ON ce.card_id = c.id
            JOIN decks d ON c.deck_id = d.id
            WHERE {where_clause}
              AND 1 - (ce.embedding <=> :embedding::vector) >= :threshold
            ORDER BY ce.embedding <=> :embedding::vector
            LIMIT :k
        """

        params["threshold"] = threshold

        result = await self.db.execute(text(sql).bindparams(**params))
        rows = result.fetchall()

        return [
            SearchResult(
                card_id=row.card_id,
                deck_id=row.deck_id,
                deck_name=row.deck_name,
                fields=row.fields,
                tags=row.tags or [],
                status=CardStatus(row.status),
                similarity=float(row.similarity),
                content_text=row.content_text,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def _keyword_search(
        self,
        query: str,
        user_id: UUID,
        k: int,
        deck_ids: list[UUID] | None,
        statuses: list[CardStatus] | None,
        tags: list[str] | None,
    ) -> list[SearchResult]:
        """
        Perform keyword-based full-text search.

        Uses PostgreSQL full-text search with ts_rank for ranking.
        """
        # Build filters
        filters = ["d.owner_id = :user_id", "c.deleted_at IS NULL", "d.deleted_at IS NULL"]
        params: dict = {"user_id": user_id, "query": query, "k": k}

        if deck_ids:
            filters.append("c.deck_id = ANY(:deck_ids)")
            params["deck_ids"] = deck_ids

        if statuses:
            status_values = [s.value for s in statuses]
            filters.append("c.status = ANY(:statuses)")
            params["statuses"] = status_values

        if tags:
            filters.append("c.tags && :tags")
            params["tags"] = tags

        where_clause = " AND ".join(filters)

        # Full-text search on content_text
        sql = f"""
            SELECT
                c.id as card_id,
                c.deck_id,
                d.name as deck_name,
                c.fields,
                c.tags,
                c.status,
                c.created_at,
                ce.content_text,
                ts_rank(
                    to_tsvector('english', ce.content_text),
                    plainto_tsquery('english', :query)
                ) as similarity
            FROM card_embeddings ce
            JOIN cards c ON ce.card_id = c.id
            JOIN decks d ON c.deck_id = d.id
            WHERE {where_clause}
              AND to_tsvector('english', ce.content_text) @@ plainto_tsquery('english', :query)
            ORDER BY similarity DESC
            LIMIT :k
        """

        result = await self.db.execute(text(sql).bindparams(**params))
        rows = result.fetchall()

        # Normalize ts_rank scores to 0-1 range
        max_score = max((row.similarity for row in rows), default=1.0) or 1.0

        return [
            SearchResult(
                card_id=row.card_id,
                deck_id=row.deck_id,
                deck_name=row.deck_name,
                fields=row.fields,
                tags=row.tags or [],
                status=CardStatus(row.status),
                similarity=float(row.similarity) / max_score,
                content_text=row.content_text,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def _hybrid_search(
        self,
        query: str,
        user_id: UUID,
        k: int,
        threshold: float,
        deck_ids: list[UUID] | None,
        statuses: list[CardStatus] | None,
        tags: list[str] | None,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> list[SearchResult]:
        """
        Perform hybrid search combining vector and keyword search.

        Uses Reciprocal Rank Fusion (RRF) to combine results.
        """
        # Get results from both search types
        vector_results = await self._vector_search(
            query, user_id, k * 2, threshold, deck_ids, statuses, tags
        )
        keyword_results = await self._keyword_search(
            query, user_id, k * 2, deck_ids, statuses, tags
        )

        # Create score maps
        vector_scores: dict[UUID, float] = {r.card_id: r.similarity for r in vector_results}
        keyword_scores: dict[UUID, float] = {r.card_id: r.similarity for r in keyword_results}

        # Combine using RRF
        rrf_constant = 60  # Standard RRF constant
        combined_scores: dict[UUID, float] = {}

        # Get all unique card IDs
        all_card_ids = set(vector_scores.keys()) | set(keyword_scores.keys())

        for card_id in all_card_ids:
            # Get ranks (1-indexed)
            vector_rank = (
                list(vector_scores.keys()).index(card_id) + 1
                if card_id in vector_scores
                else len(vector_scores) + 1
            )
            keyword_rank = (
                list(keyword_scores.keys()).index(card_id) + 1
                if card_id in keyword_scores
                else len(keyword_scores) + 1
            )

            # Calculate RRF score
            vector_rrf = vector_weight / (rrf_constant + vector_rank)
            keyword_rrf = keyword_weight / (rrf_constant + keyword_rank)
            combined_scores[card_id] = vector_rrf + keyword_rrf

        # Sort by combined score
        sorted_card_ids = sorted(
            combined_scores.keys(),
            key=lambda x: combined_scores[x],
            reverse=True,
        )[:k]

        # Build results from vector results (they have all the data)
        results_map = {r.card_id: r for r in vector_results}
        results_map.update({r.card_id: r for r in keyword_results})

        final_results = []
        for card_id in sorted_card_ids:
            if card_id in results_map:
                result = results_map[card_id]
                # Update similarity to combined score (normalized)
                max_combined = max(combined_scores.values())
                result = SearchResult(
                    card_id=result.card_id,
                    deck_id=result.deck_id,
                    deck_name=result.deck_name,
                    fields=result.fields,
                    tags=result.tags,
                    status=result.status,
                    similarity=combined_scores[card_id] / max_combined if max_combined > 0 else 0,
                    content_text=result.content_text,
                    created_at=result.created_at,
                )
                final_results.append(result)

        return final_results

    async def find_similar_to_card(
        self,
        card_id: UUID,
        user_id: UUID,
        k: int = 5,
        threshold: float = 0.7,
        exclude_self: bool = True,
    ) -> list[SearchResult]:
        """
        Find cards similar to a given card.

        Args:
            card_id: Card ID to find similar cards for.
            user_id: User ID to scope the search.
            k: Number of results to return.
            threshold: Minimum similarity threshold.
            exclude_self: Whether to exclude the source card from results.

        Returns:
            List of similar cards.
        """
        # Get the card's embedding
        result = await self.db.execute(
            text(
                """
                SELECT embedding, content_text
                FROM card_embeddings
                WHERE card_id = :card_id
                """
            ).bindparams(card_id=card_id)
        )
        row = result.fetchone()

        if not row:
            logger.warning(f"Card {card_id} not found in index")
            return []

        # Search using the existing embedding
        filters = ["d.owner_id = :user_id", "c.deleted_at IS NULL", "d.deleted_at IS NULL"]
        params: dict = {"user_id": user_id, "card_id": card_id, "k": k + 1}

        if exclude_self:
            filters.append("c.id != :card_id")

        where_clause = " AND ".join(filters)

        sql = f"""
            SELECT
                c.id as card_id,
                c.deck_id,
                d.name as deck_name,
                c.fields,
                c.tags,
                c.status,
                c.created_at,
                ce.content_text,
                1 - (ce.embedding <=> (
                    SELECT embedding FROM card_embeddings WHERE card_id = :card_id
                )) as similarity
            FROM card_embeddings ce
            JOIN cards c ON ce.card_id = c.id
            JOIN decks d ON c.deck_id = d.id
            WHERE {where_clause}
              AND 1 - (ce.embedding <=> (
                  SELECT embedding FROM card_embeddings WHERE card_id = :card_id
              )) >= :threshold
            ORDER BY ce.embedding <=> (
                SELECT embedding FROM card_embeddings WHERE card_id = :card_id
            )
            LIMIT :k
        """

        params["threshold"] = threshold

        result = await self.db.execute(text(sql).bindparams(**params))
        rows = result.fetchall()

        return [
            SearchResult(
                card_id=row.card_id,
                deck_id=row.deck_id,
                deck_name=row.deck_name,
                fields=row.fields,
                tags=row.tags or [],
                status=CardStatus(row.status),
                similarity=float(row.similarity),
                content_text=row.content_text,
                created_at=row.created_at,
            )
            for row in rows
        ][:k]

    async def find_duplicates(
        self,
        cards: list[dict],
        user_id: UUID,
        threshold: float = 0.85,
    ) -> list[dict]:
        """
        Find potential duplicates for a list of new cards.

        Args:
            cards: List of cards to check. Each dict should have 'temp_id' and 'fields'.
            user_id: User ID to check against existing cards.
            threshold: Similarity threshold for duplicate detection.

        Returns:
            List of duplicate results with matches.
        """
        results = []

        for card in cards:
            temp_id = card.get("temp_id", "")
            fields = card.get("fields", {})

            # Build search text from fields
            search_text = self._fields_to_text(fields)

            if not search_text:
                results.append(
                    {
                        "temp_id": temp_id,
                        "is_duplicate": False,
                        "matches": [],
                        "highest_similarity": 0.0,
                    }
                )
                continue

            # Search for similar existing cards
            similar = await self.search(
                query=search_text,
                user_id=user_id,
                k=5,
                threshold=threshold,
                search_type=SearchType.VECTOR,
            )

            is_duplicate = len(similar) > 0
            highest_similarity = max((r.similarity for r in similar), default=0.0)

            matches = [
                {
                    "existing_card_id": r.card_id,
                    "existing_card_fields": r.fields,
                    "similarity": r.similarity,
                }
                for r in similar
            ]

            results.append(
                {
                    "temp_id": temp_id,
                    "is_duplicate": is_duplicate,
                    "matches": matches,
                    "highest_similarity": highest_similarity,
                }
            )

        return results

    def _fields_to_text(self, fields: dict) -> str:
        """Convert card fields to searchable text."""
        parts = []

        if front := fields.get("front"):
            parts.append(front)

        if back := fields.get("back"):
            parts.append(back)

        for key, value in fields.items():
            if key not in ("front", "back") and value:
                parts.append(str(value))

        return " ".join(parts)

    async def get_deck_coverage(
        self,
        deck_id: UUID,
    ) -> dict:
        """
        Get the embedding coverage for a deck.

        Args:
            deck_id: Deck UUID.

        Returns:
            Dictionary with coverage statistics.
        """
        result = await self.db.execute(
            text(
                """
                SELECT
                    COUNT(c.id) as total_cards,
                    COUNT(ce.card_id) as indexed_cards
                FROM cards c
                LEFT JOIN card_embeddings ce ON c.id = ce.card_id
                WHERE c.deck_id = :deck_id
                  AND c.deleted_at IS NULL
                """
            ).bindparams(deck_id=deck_id)
        )
        row = result.fetchone()

        total = row.total_cards
        indexed = row.indexed_cards

        return {
            "deck_id": deck_id,
            "total_cards": total,
            "indexed_cards": indexed,
            "unindexed_cards": total - indexed,
            "coverage_percent": (indexed / total * 100) if total > 0 else 0,
        }
