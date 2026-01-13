"""Сервис для работы с эмбеддингами карточек.

Использует SOP LLM Executor для генерации векторных представлений
карточек для семантического поиска.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.llm_client import LLMClient, LLMClientError, get_llm_client
from src.modules.cards.models import Card, CardEmbedding

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingService:
    """Сервис для генерации и поиска по эмбеддингам карточек.

    Attributes:
        session: Async SQLAlchemy session.
        llm_client: Client for sop_llm embeddings.
    """

    session: AsyncSession
    llm_client: LLMClient | None = None

    def __post_init__(self) -> None:
        if self.llm_client is None:
            self.llm_client = get_llm_client()

    def _card_to_text(self, card: Card) -> str:
        """Convert card to text for embedding.

        Args:
            card: Card model instance.

        Returns:
            Combined text from card fields.
        """
        fields = card.fields or {}
        parts = []

        # Front field
        front = fields.get("Front", "")
        if front:
            parts.append(f"Question: {front}")

        # Back field
        back = fields.get("Back", "")
        if back:
            parts.append(f"Answer: {back}")

        # Tags
        if card.tags:
            parts.append(f"Tags: {', '.join(card.tags)}")

        return "\n".join(parts)

    async def generate_embedding(
        self,
        card: Card,
        embedder_id: UUID | None = None,
    ) -> CardEmbedding | None:
        """Generate and save embedding for a card.

        Args:
            card: Card to generate embedding for.
            embedder_id: UUID of the embedding model (optional).

        Returns:
            CardEmbedding instance or None if failed.
        """
        if not self.llm_client:
            logger.error("LLM client not available")
            return None

        content_text = self._card_to_text(card)
        if not content_text.strip():
            logger.warning("Empty card content, skipping embedding: %s", card.id)
            return None

        try:
            # Generate embedding via sop_llm
            embeddings = await self.llm_client.generate_embeddings([content_text])

            if not embeddings:
                logger.warning("No embeddings returned for card: %s", card.id)
                return None

            embedding_vector = embeddings[0]

            # Check if embedding already exists
            existing = await self.session.execute(
                select(CardEmbedding).where(CardEmbedding.card_id == card.id)
            )
            card_embedding = existing.scalar_one_or_none()

            if card_embedding:
                # Update existing
                card_embedding.content_text = content_text
                # Update vector via raw SQL (pgvector)
                await self.session.execute(
                    text(
                        "UPDATE card_embeddings SET embedding = :vector WHERE card_id = :card_id"
                    ),
                    {"vector": embedding_vector, "card_id": str(card.id)},
                )
            else:
                # Create new embedding record
                # Note: We need to use raw SQL for pgvector column
                # First create the record without the vector
                card_embedding = CardEmbedding(
                    card_id=card.id,
                    embedder_id=embedder_id or UUID("00000000-0000-0000-0000-000000000001"),
                    content_text=content_text,
                )
                self.session.add(card_embedding)
                await self.session.flush()

                # Then update the vector
                await self.session.execute(
                    text(
                        "UPDATE card_embeddings SET embedding = :vector WHERE card_id = :card_id"
                    ),
                    {"vector": embedding_vector, "card_id": str(card.id)},
                )

            await self.session.commit()
            await self.session.refresh(card_embedding)

            logger.info(
                "Generated embedding for card %s (dims=%d)",
                card.id,
                len(embedding_vector),
            )
            return card_embedding

        except LLMClientError as e:
            logger.error("LLM error generating embedding for card %s: %s", card.id, e)
            return None

        except Exception:
            logger.exception("Error generating embedding for card %s", card.id)
            await self.session.rollback()
            return None

    async def generate_embeddings_batch(
        self,
        cards: list[Card],
        batch_size: int = 32,
        embedder_id: UUID | None = None,
    ) -> int:
        """Generate embeddings for multiple cards.

        Args:
            cards: List of cards to process.
            batch_size: Number of cards per batch.
            embedder_id: UUID of the embedding model.

        Returns:
            Number of successfully processed cards.
        """
        if not self.llm_client:
            logger.error("LLM client not available")
            return 0

        success_count = 0
        total = len(cards)

        for i in range(0, total, batch_size):
            batch = cards[i : i + batch_size]
            batch_texts = []
            batch_cards = []

            for card in batch:
                card_text = self._card_to_text(card)
                if card_text.strip():
                    batch_texts.append(card_text)
                    batch_cards.append(card)

            if not batch_texts:
                continue

            try:
                # Generate embeddings for batch
                embeddings = await self.llm_client.generate_embeddings(batch_texts)

                for card, embedding_vector, content_text in zip(
                    batch_cards, embeddings, batch_texts, strict=False
                ):
                    try:
                        # Check existing
                        existing = await self.session.execute(
                            select(CardEmbedding).where(CardEmbedding.card_id == card.id)
                        )
                        card_embedding = existing.scalar_one_or_none()

                        if card_embedding:
                            card_embedding.content_text = content_text
                            await self.session.execute(
                                text(
                                    "UPDATE card_embeddings SET embedding = :vector WHERE card_id = :card_id"
                                ),
                                {"vector": embedding_vector, "card_id": str(card.id)},
                            )
                        else:
                            card_embedding = CardEmbedding(
                                card_id=card.id,
                                embedder_id=embedder_id or UUID("00000000-0000-0000-0000-000000000001"),
                                content_text=content_text,
                            )
                            self.session.add(card_embedding)
                            await self.session.flush()
                            await self.session.execute(
                                text(
                                    "UPDATE card_embeddings SET embedding = :vector WHERE card_id = :card_id"
                                ),
                                {"vector": embedding_vector, "card_id": str(card.id)},
                            )

                        success_count += 1

                    except Exception as e:
                        logger.error("Error saving embedding for card %s: %s", card.id, e)

                await self.session.commit()
                logger.info(
                    "Processed batch %d-%d of %d cards",
                    i + 1,
                    min(i + batch_size, total),
                    total,
                )

            except LLMClientError as e:
                logger.error("LLM error processing batch: %s", e)

        return success_count

    async def search_similar(
        self,
        query: str,
        deck_id: UUID | None = None,
        limit: int = 5,
        threshold: float = 0.7,
    ) -> list[tuple[Card, float]]:
        """Search for similar cards using semantic search.

        Args:
            query: Search query text.
            deck_id: Optional deck ID to filter by.
            limit: Maximum number of results.
            threshold: Minimum similarity threshold.

        Returns:
            List of (card, similarity_score) tuples.
        """
        if not self.llm_client:
            logger.error("LLM client not available")
            return []

        try:
            # Generate query embedding
            embeddings = await self.llm_client.generate_embeddings([query])
            if not embeddings:
                return []

            query_vector = embeddings[0]

            # Build SQL query with pgvector cosine similarity
            sql = """
                SELECT c.*, 1 - (ce.embedding <=> :query_vector::vector) as similarity
                FROM cards c
                JOIN card_embeddings ce ON ce.card_id = c.id
                WHERE c.deleted_at IS NULL
            """
            params: dict = {"query_vector": query_vector}

            if deck_id:
                sql += " AND c.deck_id = :deck_id"
                params["deck_id"] = str(deck_id)

            sql += """
                AND 1 - (ce.embedding <=> :query_vector::vector) >= :threshold
                ORDER BY ce.embedding <=> :query_vector::vector
                LIMIT :limit
            """
            params["threshold"] = threshold
            params["limit"] = limit

            result = await self.session.execute(text(sql), params)
            rows = result.fetchall()

            cards_with_scores = []
            for row in rows:
                # Get card by ID
                card_result = await self.session.execute(
                    select(Card).where(Card.id == row.id)
                )
                card = card_result.scalar_one_or_none()
                if card:
                    cards_with_scores.append((card, row.similarity))

            return cards_with_scores

        except LLMClientError as e:
            logger.error("LLM error in semantic search: %s", e)
            return []

        except Exception:
            logger.exception("Error in semantic search")
            return []

    async def get_similar_cards(
        self,
        card: Card,
        limit: int = 5,
        threshold: float = 0.8,
    ) -> list[tuple[Card, float]]:
        """Find cards similar to a given card.

        Args:
            card: Reference card.
            limit: Maximum number of results.
            threshold: Minimum similarity threshold.

        Returns:
            List of (card, similarity_score) tuples.
        """
        content_text = self._card_to_text(card)
        results = await self.search_similar(
            query=content_text,
            deck_id=card.deck_id,
            limit=limit + 1,  # +1 to exclude the card itself
            threshold=threshold,
        )

        # Filter out the card itself
        return [(c, score) for c, score in results if c.id != card.id][:limit]
