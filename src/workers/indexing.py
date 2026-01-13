"""Embedding indexing worker tasks.

Handles indexing of card embeddings for semantic search.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from src.workers.broker import broker


class IndexingTask(BaseModel):
    """Task payload for embedding indexing.

    Attributes:
        task_id: Unique identifier for the indexing task.
        user_id: ID of the user whose cards to index.
        card_ids: Optional list of specific card IDs to index.
        reindex: Whether to reindex all cards (delete existing first).
    """

    task_id: UUID
    user_id: UUID
    card_ids: list[UUID] | None = None
    reindex: bool = False


@broker.subscriber("indexing:tasks")
async def process_indexing_task(task: IndexingTask) -> None:
    """Process embedding indexing task from queue.

    Args:
        task: Indexing task payload.
    """
    from src.core.database import db_manager
    from src.services.rag.service import RAGService

    async for db in db_manager.get_session():
        service = RAGService(db=db)

        if task.reindex:
            await service.reindex_user_cards(task.user_id)
        elif task.card_ids:
            for card_id in task.card_ids:
                await service.index_card(card_id)
        else:
            await service.index_user_cards(task.user_id)
        break


__all__ = ["IndexingTask", "process_indexing_task"]
