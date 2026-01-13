"""Chat workflows module."""

from sqlalchemy.ext.asyncio import AsyncSession

from .chat_workflow import ChatWorkflow


async def get_chat_workflow(db: AsyncSession) -> ChatWorkflow:
    """Get an initialized chat workflow instance.

    Args:
        db: Database session for RAG context retrieval.

    Returns:
        Configured ChatWorkflow instance.
    """
    return ChatWorkflow(db)


__all__ = [
    "ChatWorkflow",
    "get_chat_workflow",
]
