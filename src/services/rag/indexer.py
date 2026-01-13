"""
Card indexer for storing embeddings in pgvector.

Handles:
    - Batch embedding generation and storage
    - Incremental indexing (only new cards)
    - Full reindexing
    - Embedding updates when cards change
"""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.services.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class CardIndexer:
    """
    Indexes cards into pgvector for similarity search.

    The indexer creates embeddings from card content and stores them
    in the card_embeddings table with pgvector support.
    """

    def __init__(
        self,
        db: AsyncSession,
        embeddings: EmbeddingService,
    ) -> None:
        """
        Initialize the card indexer.

        Args:
            db: Database session.
            embeddings: Embedding service for generating vectors.
        """
        self.db = db
        self.embeddings = embeddings
        self._batch_size = settings.embedding.batch_size

    def _card_to_text(self, card: dict) -> str:
        """
        Convert card fields to indexable text.

        Combines relevant card fields into a single text for embedding.

        Args:
            card: Card data dictionary with 'fields' and optionally 'tags'.

        Returns:
            Combined text suitable for embedding.
        """
        fields = card.get("fields", {})
        parts = []

        # Add front/question
        if front := fields.get("front"):
            parts.append(f"Question: {front}")

        # Add back/answer
        if back := fields.get("back"):
            parts.append(f"Answer: {back}")

        # Add any extra fields
        for key, value in fields.items():
            if key not in ("front", "back") and value:
                parts.append(f"{key.title()}: {value}")

        # Add tags for context
        if tags := card.get("tags"):
            parts.append(f"Tags: {', '.join(tags)}")

        return "\n".join(parts)

    async def index_card(
        self,
        card_id: UUID,
        force: bool = False,
    ) -> bool:
        """
        Index a single card.

        Args:
            card_id: UUID of the card to index.
            force: If True, reindex even if embedding exists.

        Returns:
            True if the card was indexed, False if skipped.
        """
        # Check if embedding already exists
        if not force:
            existing = await self.db.execute(
                text("SELECT 1 FROM card_embeddings WHERE card_id = :card_id").bindparams(
                    card_id=card_id
                )
            )
            if existing.fetchone():
                logger.debug(f"Card {card_id} already indexed, skipping")
                return False

        # Fetch card data
        result = await self.db.execute(
            text(
                """
                SELECT c.id, c.fields, c.tags, c.deck_id, c.status
                FROM cards c
                WHERE c.id = :card_id AND c.deleted_at IS NULL
                """
            ).bindparams(card_id=card_id)
        )
        card_row = result.fetchone()

        if not card_row:
            logger.warning(f"Card {card_id} not found or deleted")
            return False

        card = {
            "id": card_row.id,
            "fields": card_row.fields,
            "tags": card_row.tags or [],
        }

        # Generate text for embedding
        content_text = self._card_to_text(card)

        # Generate embedding
        embedding = await self.embeddings.embed_single(content_text)

        # Get embedder model ID (or create one if not exists)
        embedder_id = await self._get_or_create_embedder_id()

        # Upsert embedding
        await self.db.execute(
            text(
                """
                INSERT INTO card_embeddings (
                    id, card_id, embedder_id, content_text, embedding, created_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), :card_id, :embedder_id, :content_text,
                    :embedding, NOW(), NOW()
                )
                ON CONFLICT (card_id)
                DO UPDATE SET
                    content_text = EXCLUDED.content_text,
                    embedding = EXCLUDED.embedding,
                    embedder_id = EXCLUDED.embedder_id,
                    updated_at = NOW()
                """
            ).bindparams(
                card_id=card_id,
                embedder_id=embedder_id,
                content_text=content_text,
                embedding=str(embedding),
            )
        )

        logger.debug(f"Indexed card {card_id}")
        return True

    async def index_cards(
        self,
        card_ids: list[UUID],
        force: bool = False,
    ) -> tuple[int, int, list[UUID]]:
        """
        Index multiple cards in batches.

        Args:
            card_ids: List of card UUIDs to index.
            force: If True, reindex even if embeddings exist.

        Returns:
            Tuple of (indexed_count, skipped_count, failed_ids).
        """
        if not card_ids:
            return 0, 0, []

        indexed_count = 0
        skipped_count = 0
        failed_ids: list[UUID] = []

        # Process in batches
        for i in range(0, len(card_ids), self._batch_size):
            batch_ids = card_ids[i : i + self._batch_size]

            try:
                batch_indexed, batch_skipped, batch_failed = await self._index_batch(
                    batch_ids, force
                )
                indexed_count += batch_indexed
                skipped_count += batch_skipped
                failed_ids.extend(batch_failed)

            except Exception as e:
                logger.error(f"Failed to index batch: {e}")
                failed_ids.extend(batch_ids)

        return indexed_count, skipped_count, failed_ids

    async def _index_batch(
        self,
        card_ids: list[UUID],
        force: bool,
    ) -> tuple[int, int, list[UUID]]:
        """
        Index a batch of cards.

        Args:
            card_ids: Card IDs in this batch.
            force: Whether to force reindexing.

        Returns:
            Tuple of (indexed_count, skipped_count, failed_ids).
        """
        # Get cards that need indexing
        if force:
            cards_to_index = card_ids
        else:
            # Check which cards already have embeddings
            result = await self.db.execute(
                text(
                    """
                    SELECT card_id FROM card_embeddings
                    WHERE card_id = ANY(:card_ids)
                    """
                ).bindparams(card_ids=card_ids)
            )
            existing_ids = {row.card_id for row in result.fetchall()}
            cards_to_index = [cid for cid in card_ids if cid not in existing_ids]

        skipped_count = len(card_ids) - len(cards_to_index)

        if not cards_to_index:
            return 0, skipped_count, []

        # Fetch card data
        result = await self.db.execute(
            text(
                """
                SELECT c.id, c.fields, c.tags
                FROM cards c
                WHERE c.id = ANY(:card_ids) AND c.deleted_at IS NULL
                """
            ).bindparams(card_ids=cards_to_index)
        )
        cards = [
            {"id": row.id, "fields": row.fields, "tags": row.tags or []}
            for row in result.fetchall()
        ]

        if not cards:
            return 0, skipped_count, cards_to_index

        # Generate texts
        texts = [self._card_to_text(card) for card in cards]

        # Generate embeddings in batch
        try:
            embeddings = await self.embeddings.embed(texts)
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return 0, skipped_count, [card["id"] for card in cards]

        # Get embedder ID
        embedder_id = await self._get_or_create_embedder_id()

        # Insert/update embeddings
        indexed_count = 0
        failed_ids: list[UUID] = []

        for card, content_text, embedding in zip(cards, texts, embeddings):
            try:
                await self.db.execute(
                    text(
                        """
                        INSERT INTO card_embeddings (
                            id, card_id, embedder_id, content_text,
                            embedding, created_at, updated_at
                        )
                        VALUES (
                            gen_random_uuid(), :card_id, :embedder_id, :content_text,
                            :embedding, NOW(), NOW()
                        )
                        ON CONFLICT (card_id)
                        DO UPDATE SET
                            content_text = EXCLUDED.content_text,
                            embedding = EXCLUDED.embedding,
                            embedder_id = EXCLUDED.embedder_id,
                            updated_at = NOW()
                        """
                    ).bindparams(
                        card_id=card["id"],
                        embedder_id=embedder_id,
                        content_text=content_text,
                        embedding=str(embedding),
                    )
                )
                indexed_count += 1

            except Exception as e:
                logger.error(f"Failed to index card {card['id']}: {e}")
                failed_ids.append(card["id"])

        return indexed_count, skipped_count, failed_ids

    async def index_user_cards(
        self,
        user_id: UUID,
        force: bool = False,
    ) -> tuple[int, int, list[UUID]]:
        """
        Index all cards for a user.

        Args:
            user_id: User UUID.
            force: If True, reindex all cards.

        Returns:
            Tuple of (indexed_count, skipped_count, failed_ids).
        """
        # Get all card IDs for user
        result = await self.db.execute(
            text(
                """
                SELECT c.id
                FROM cards c
                JOIN decks d ON c.deck_id = d.id
                WHERE d.owner_id = :user_id
                  AND c.deleted_at IS NULL
                  AND d.deleted_at IS NULL
                """
            ).bindparams(user_id=user_id)
        )
        card_ids = [row.id for row in result.fetchall()]

        logger.info(f"Indexing {len(card_ids)} cards for user {user_id}")

        return await self.index_cards(card_ids, force=force)

    async def remove_card(self, card_id: UUID) -> bool:
        """
        Remove a card from the index.

        Args:
            card_id: Card UUID to remove.

        Returns:
            True if the card was removed, False if not found.
        """
        result = await self.db.execute(
            text(
                """
                DELETE FROM card_embeddings
                WHERE card_id = :card_id
                RETURNING card_id
                """
            ).bindparams(card_id=card_id)
        )
        deleted = result.fetchone()

        if deleted:
            logger.debug(f"Removed card {card_id} from index")
            return True

        logger.debug(f"Card {card_id} not found in index")
        return False

    async def remove_user_cards(self, user_id: UUID) -> int:
        """
        Remove all cards for a user from the index.

        Args:
            user_id: User UUID.

        Returns:
            Number of embeddings removed.
        """
        result = await self.db.execute(
            text(
                """
                DELETE FROM card_embeddings ce
                USING cards c, decks d
                WHERE ce.card_id = c.id
                  AND c.deck_id = d.id
                  AND d.owner_id = :user_id
                """
            ).bindparams(user_id=user_id)
        )
        count = result.rowcount
        logger.info(f"Removed {count} embeddings for user {user_id}")
        return count

    async def reindex_user_cards(
        self,
        user_id: UUID,
        delete_existing: bool = True,
    ) -> tuple[int, int, int]:
        """
        Reindex all cards for a user.

        Args:
            user_id: User UUID.
            delete_existing: If True, delete existing embeddings first.

        Returns:
            Tuple of (deleted_count, indexed_count, failed_count).
        """
        deleted_count = 0

        if delete_existing:
            deleted_count = await self.remove_user_cards(user_id)

        indexed_count, _, failed_ids = await self.index_user_cards(user_id, force=True)

        return deleted_count, indexed_count, len(failed_ids)

    async def _get_or_create_embedder_id(self) -> UUID:
        """
        Get or create the embedder model ID.

        Returns:
            UUID of the embedding model.
        """
        model_name = self.embeddings.model_name
        provider = self.embeddings.provider_name
        dimension = self.embeddings.dimension

        # Try to find existing model
        result = await self.db.execute(
            text(
                """
                SELECT id FROM embedding_models
                WHERE name = :name
                """
            ).bindparams(name=model_name)
        )
        row = result.fetchone()

        if row:
            return row.id

        # Create new model entry
        result = await self.db.execute(
            text(
                """
                INSERT INTO embedding_models (
                    id, name, display_name, provider, model_id, dimension,
                    is_active, created_at, updated_at
                )
                VALUES (
                    gen_random_uuid(), :name, :display_name, :provider, :model_id,
                    :dimension, true, NOW(), NOW()
                )
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING id
                """
            ).bindparams(
                name=model_name,
                display_name=model_name,
                provider=provider,
                model_id=model_name,
                dimension=dimension,
            )
        )
        row = result.fetchone()
        return row.id

    async def get_index_stats(self, user_id: UUID) -> dict:
        """
        Get indexing statistics for a user.

        Args:
            user_id: User UUID.

        Returns:
            Dictionary with index statistics.
        """
        # Total cards
        result = await self.db.execute(
            text(
                """
                SELECT COUNT(*) as total
                FROM cards c
                JOIN decks d ON c.deck_id = d.id
                WHERE d.owner_id = :user_id
                  AND c.deleted_at IS NULL
                  AND d.deleted_at IS NULL
                """
            ).bindparams(user_id=user_id)
        )
        total_cards = result.fetchone().total

        # Indexed cards
        result = await self.db.execute(
            text(
                """
                SELECT COUNT(*) as indexed
                FROM card_embeddings ce
                JOIN cards c ON ce.card_id = c.id
                JOIN decks d ON c.deck_id = d.id
                WHERE d.owner_id = :user_id
                  AND c.deleted_at IS NULL
                  AND d.deleted_at IS NULL
                """
            ).bindparams(user_id=user_id)
        )
        indexed_cards = result.fetchone().indexed

        return {
            "total_cards": total_cards,
            "indexed_cards": indexed_cards,
            "unindexed_cards": total_cards - indexed_cards,
            "coverage_percent": (indexed_cards / total_cards * 100) if total_cards > 0 else 0,
        }
