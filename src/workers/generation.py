"""Card generation worker tasks.

Handles card generation tasks from the queue, processing them
through the LangGraph workflow.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from src.workers.broker import broker


class GenerationTask(BaseModel):
    """Task payload for card generation.

    Attributes:
        job_id: Unique identifier for the generation job.
        user_id: ID of the user who initiated the generation.
        topic: Topic for card generation.
        deck_id: Target deck for generated cards.
        num_cards: Number of cards to generate.
        card_type: Type of cards (basic, cloze, etc.).
        difficulty: Difficulty level.
        language: Language code.
        fact_check: Whether to perform fact checking.
        include_sources: Whether to include sources.
        context: Additional context for generation.
        model_id: Optional specific model to use.
        tags: Tags to apply to generated cards.
    """

    job_id: UUID
    user_id: UUID
    topic: str
    deck_id: UUID
    num_cards: int = 5
    card_type: str = "basic"
    difficulty: str = "medium"
    language: str = "en"
    fact_check: bool = True
    include_sources: bool = True
    context: str | None = None
    model_id: str | None = None
    tags: list[str] = []


@broker.subscriber("generation:tasks")
async def process_generation_task(task: GenerationTask) -> None:
    """Process card generation task from queue.

    Args:
        task: Generation task payload.
    """
    from src.core.database import db_manager
    from src.core.dependencies import RedisManager
    from src.modules.generation.schemas import GenerationRequest
    from src.modules.generation.service import GenerationService

    redis = await RedisManager.get_client()
    service = GenerationService(redis)

    # Convert task to GenerationRequest
    request = GenerationRequest(
        topic=task.topic,
        deck_id=task.deck_id,
        num_cards=task.num_cards,
        card_type=task.card_type,
        difficulty=task.difficulty,
        language=task.language,
        fact_check=task.fact_check,
        include_sources=task.include_sources,
        context=task.context,
        model_id=task.model_id,
        tags=task.tags,
    )

    async for db in db_manager.get_session():
        await service.process_job(
            job_id=task.job_id,
            request=request,
            db=db,
        )
        break


__all__ = ["GenerationTask", "process_generation_task"]
