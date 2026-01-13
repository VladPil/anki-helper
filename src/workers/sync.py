"""Anki synchronization worker tasks.

Handles synchronization of cards with Anki through AnkiConnect.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from src.workers.broker import broker


class SyncTask(BaseModel):
    """Task payload for Anki sync.

    Attributes:
        task_id: Unique identifier for the sync task.
        user_id: ID of the user who initiated the sync.
        card_ids: List of card IDs to synchronize.
    """

    task_id: UUID
    user_id: UUID
    card_ids: list[UUID]


@broker.subscriber("sync:tasks")
async def process_sync_task(task: SyncTask) -> None:
    """Process Anki sync task from queue.

    Args:
        task: Sync task payload.
    """
    from src.core.database import db_manager
    from src.modules.sync.service import SyncService

    async for db in db_manager.get_session():
        service = SyncService(db)
        await service.sync_to_anki(
            user_id=task.user_id,
            card_ids=task.card_ids,
        )
        break


__all__ = ["SyncTask", "process_sync_task"]
