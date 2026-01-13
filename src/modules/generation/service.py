"""
Сервис генерации карточек.

Этот модуль оркестрирует рабочие процессы генерации карточек с помощью ИИ.

Основные компоненты:
    - GenerationService: управление заданиями генерации и их статусами
    - get_generation_service: получение синглтона сервиса генерации
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import RedisManager
from src.core.logging import get_structured_logger
from src.core.metrics import CARD_GENERATION_COUNT, CARD_GENERATION_LATENCY

from .schemas import (
    GeneratedCard,
    GenerationJob,
    GenerationJobStatus,
    GenerationRequest,
    GenerationStatus,
    GenerationStreamEvent,
)
from .workflows.card_generator import CardGeneratorWorkflow

logger = get_structured_logger(__name__)


class GenerationService:
    """
    Сервис оркестрации генерации карточек.

    Управляет заданиями генерации, делегирует работу рабочим процессам
    и обрабатывает сохранение заданий и обновление статусов.

    Attributes:
        JOB_PREFIX: Префикс ключей заданий в Redis
        JOB_STATUS_PREFIX: Префикс ключей статусов в Redis
        JOB_CANCEL_PREFIX: Префикс ключей отмены в Redis
        USER_JOBS_PREFIX: Префикс ключей заданий пользователя
        JOB_TTL: Время жизни задания в секундах (24 часа)
    """

    # Redis key prefixes
    JOB_PREFIX = "generation:job:"
    JOB_STATUS_PREFIX = "generation:status:"
    JOB_CANCEL_PREFIX = "generation:cancel:"
    USER_JOBS_PREFIX = "generation:user_jobs:"

    # Job expiration time (24 hours)
    JOB_TTL = 60 * 60 * 24

    def __init__(self, redis: Redis) -> None:
        """
        Инициализировать сервис генерации.

        Args:
            redis: Клиент Redis для хранения заданий
        """
        self._redis = redis
        self._workflow = CardGeneratorWorkflow()

    async def create_job(
        self,
        user_id: UUID,
        request: GenerationRequest,
        db: AsyncSession,
    ) -> GenerationJob:
        """
        Создать новое задание генерации.

        Args:
            user_id: UUID пользователя, создающего задание
            request: Параметры запроса генерации
            db: Сессия базы данных

        Returns:
            Созданный объект GenerationJob
        """
        import uuid

        job_id = uuid.uuid4()
        now = datetime.now(UTC)

        job = GenerationJob(
            id=job_id,
            user_id=user_id,
            deck_id=request.deck_id,
            status=GenerationStatus.PENDING,
            topic=request.topic,
            card_type=request.card_type,
            num_cards_requested=request.num_cards,
            num_cards_generated=0,
            cards=[],
            created_at=now,
            updated_at=now,
            metadata={
                "language": request.language,
                "difficulty": request.difficulty,
                "include_sources": request.include_sources,
                "fact_check": request.fact_check,
                "model_id": request.model_id,
                "tags": request.tags,
            },
        )

        # Store job in Redis
        job_key = f"{self.JOB_PREFIX}{job_id}"
        await self._redis.setex(
            job_key,
            self.JOB_TTL,
            job.model_dump_json(),
        )

        # Add to user's job list
        user_jobs_key = f"{self.USER_JOBS_PREFIX}{user_id}"
        await self._redis.lpush(user_jobs_key, str(job_id))
        await self._redis.ltrim(user_jobs_key, 0, 99)  # Keep last 100 jobs

        logger.info(
            "Created generation job",
            job_id=str(job_id),
            user_id=str(user_id),
            topic=request.topic,
        )

        return job

    async def get_job(
        self,
        job_id: UUID,
        db: AsyncSession | None = None,
    ) -> GenerationJob | None:
        """
        Получить задание генерации по ID.

        Args:
            job_id: UUID задания для получения
            db: Сессия базы данных (опционально, не используется для Redis)

        Returns:
            GenerationJob или None если не найдено
        """
        job_key = f"{self.JOB_PREFIX}{job_id}"
        job_data = await self._redis.get(job_key)

        if job_data is None:
            return None

        return GenerationJob.model_validate_json(job_data)

    async def get_job_status(
        self,
        job_id: UUID,
        db: AsyncSession,
    ) -> GenerationJobStatus | None:
        """
        Получить статус задания для легковесного опроса.

        Args:
            job_id: UUID задания для проверки
            db: Сессия базы данных

        Returns:
            GenerationJobStatus или None если не найдено
        """
        job = await self.get_job(job_id, db)

        if job is None:
            return None

        # Calculate progress
        if job.num_cards_requested > 0:
            progress = (job.num_cards_generated / job.num_cards_requested) * 100
        else:
            progress = 0.0

        # Determine current step based on status
        current_step = None
        if job.status == GenerationStatus.RUNNING:
            current_step = job.metadata.get("current_step", "generating")

        return GenerationJobStatus(
            job_id=job.id,
            status=job.status,
            progress=progress,
            num_cards_generated=job.num_cards_generated,
            num_cards_requested=job.num_cards_requested,
            current_step=current_step,
            error_message=job.error_message,
        )

    async def update_job(
        self,
        job_id: UUID,
        updates: dict[str, Any],
    ) -> GenerationJob | None:
        """
        Обновить задание генерации.

        Args:
            job_id: UUID задания для обновления
            updates: Словарь полей для обновления

        Returns:
            Обновленный GenerationJob или None если не найдено
        """
        job_key = f"{self.JOB_PREFIX}{job_id}"
        job_data = await self._redis.get(job_key)

        if job_data is None:
            return None

        job = GenerationJob.model_validate_json(job_data)

        # Apply updates
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)

        job.updated_at = datetime.now(UTC)

        # Save back to Redis
        await self._redis.setex(
            job_key,
            self.JOB_TTL,
            job.model_dump_json(),
        )

        return job

    async def cancel_job(
        self,
        job_id: UUID,
        db: AsyncSession,
    ) -> bool:
        """
        Отменить задание генерации.

        Args:
            job_id: UUID задания для отмены
            db: Сессия базы данных

        Returns:
            True если успешно отменено
        """
        # Set cancellation flag
        cancel_key = f"{self.JOB_CANCEL_PREFIX}{job_id}"
        await self._redis.setex(cancel_key, 3600, "1")

        # Update job status
        await self.update_job(job_id, {"status": GenerationStatus.CANCELLED})

        logger.info("Cancelled generation job", job_id=str(job_id))
        return True

    async def is_cancelled(self, job_id: UUID) -> bool:
        """
        Проверить, было ли задание отменено.

        Args:
            job_id: UUID задания для проверки

        Returns:
            True если отменено
        """
        cancel_key = f"{self.JOB_CANCEL_PREFIX}{job_id}"
        return await self._redis.exists(cancel_key) > 0

    async def process_job(
        self,
        job_id: UUID,
        request: GenerationRequest,
    ) -> None:
        """
        Обработать задание генерации.

        Запускает рабочий процесс генерации карточек и обновляет статус задания.

        Args:
            job_id: UUID задания для обработки
            request: Параметры запроса генерации
        """
        import time

        start_time = time.perf_counter()

        try:
            # Update status to running
            await self.update_job(
                job_id,
                {
                    "status": GenerationStatus.RUNNING,
                    "started_at": datetime.now(UTC),
                },
            )

            CARD_GENERATION_COUNT.labels(
                status="started",
                workflow="card_generator",
            ).inc()

            # Run the workflow
            result = await self._workflow.run(
                topic=request.topic,
                num_cards=request.num_cards,
                card_type=request.card_type.value,
                language=request.language,
                difficulty=request.difficulty,
                context=request.context,
                model_id=request.model_id,
                fact_check=request.fact_check,
                include_sources=request.include_sources,
                tags=request.tags,
                job_id=str(job_id),
                on_progress=lambda step: self._update_progress(job_id, step),
                is_cancelled=lambda: self.is_cancelled(job_id),
            )

            # Check for cancellation
            if await self.is_cancelled(job_id):
                logger.info("Job was cancelled during processing", job_id=str(job_id))
                return

            # Convert workflow result to generated cards
            cards = [
                GeneratedCard(
                    front=card["front"],
                    back=card["back"],
                    card_type=request.card_type,
                    tags=card.get("tags", request.tags),
                    source=card.get("source"),
                    confidence=card.get("confidence"),
                    is_duplicate=card.get("is_duplicate", False),
                    duplicate_card_id=card.get("duplicate_card_id"),
                    similarity_score=card.get("similarity_score"),
                )
                for card in result.get("cards", [])
            ]

            # Update job with results
            await self.update_job(
                job_id,
                {
                    "status": GenerationStatus.COMPLETED,
                    "cards": cards,
                    "num_cards_generated": len(cards),
                    "completed_at": datetime.now(UTC),
                },
            )

            CARD_GENERATION_COUNT.labels(
                status="completed",
                workflow="card_generator",
            ).inc()

            latency = time.perf_counter() - start_time
            CARD_GENERATION_LATENCY.labels(workflow="card_generator").observe(latency)

            logger.info(
                "Generation job completed",
                job_id=str(job_id),
                num_cards=len(cards),
                latency=latency,
            )

        except Exception as e:
            logger.error(
                "Generation job failed",
                job_id=str(job_id),
                error=str(e),
                exc_info=True,
            )

            await self.update_job(
                job_id,
                {
                    "status": GenerationStatus.FAILED,
                    "error_message": str(e),
                    "completed_at": datetime.now(UTC),
                },
            )

            CARD_GENERATION_COUNT.labels(
                status="failed",
                workflow="card_generator",
            ).inc()

    async def _update_progress(self, job_id: UUID, step: str) -> None:
        """
        Обновить шаг прогресса задания.

        Args:
            job_id: UUID задания
            step: Текущий шаг обработки
        """
        job = await self.get_job(job_id, None)
        if job:
            metadata = job.metadata.copy()
            metadata["current_step"] = step
            await self.update_job(job_id, {"metadata": metadata})

    async def generate_stream(
        self,
        user_id: UUID,
        request: GenerationRequest,
        db: AsyncSession,
    ) -> AsyncGenerator[GenerationStreamEvent, None]:
        """
        Стримить события генерации карточек.

        Генерирует карточки и возвращает события в реальном времени.

        Args:
            user_id: UUID пользователя
            request: Параметры запроса генерации
            db: Сессия базы данных

        Yields:
            GenerationStreamEvent для каждой карточки и обновления прогресса
        """
        import time

        start_time = time.perf_counter()

        try:
            # Yield initial progress
            yield GenerationStreamEvent(
                type="progress",
                progress=0.0,
                step="initializing",
                message="Starting card generation...",
            )

            # Run the workflow with streaming
            async for event in self._workflow.run_stream(
                topic=request.topic,
                num_cards=request.num_cards,
                card_type=request.card_type.value,
                language=request.language,
                difficulty=request.difficulty,
                context=request.context,
                model_id=request.model_id,
                fact_check=request.fact_check,
                include_sources=request.include_sources,
                tags=request.tags,
            ):
                if event["type"] == "card":
                    card = GeneratedCard(
                        front=event["card"]["front"],
                        back=event["card"]["back"],
                        card_type=request.card_type,
                        tags=event["card"].get("tags", request.tags),
                        source=event["card"].get("source"),
                        confidence=event["card"].get("confidence"),
                        is_duplicate=event["card"].get("is_duplicate", False),
                    )
                    yield GenerationStreamEvent(
                        type="card",
                        card=card,
                        progress=event.get("progress", 0.0),
                    )

                elif event["type"] == "progress":
                    yield GenerationStreamEvent(
                        type="progress",
                        progress=event.get("progress", 0.0),
                        step=event.get("step"),
                        message=event.get("message"),
                    )

                # Allow other tasks to run
                await asyncio.sleep(0)

            # Yield completion
            latency = time.perf_counter() - start_time
            yield GenerationStreamEvent(
                type="complete",
                progress=100.0,
                message=f"Generation completed in {latency:.1f}s",
            )

            CARD_GENERATION_COUNT.labels(
                status="completed",
                workflow="card_generator_stream",
            ).inc()

        except Exception as e:
            logger.error("Stream generation failed", error=str(e))
            yield GenerationStreamEvent(
                type="error",
                error=str(e),
            )

            CARD_GENERATION_COUNT.labels(
                status="failed",
                workflow="card_generator_stream",
            ).inc()

    async def list_jobs(
        self,
        user_id: UUID,
        db: AsyncSession,
        status_filter: GenerationStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[GenerationJob]:
        """
        Получить список заданий генерации пользователя.

        Args:
            user_id: UUID пользователя
            db: Сессия базы данных
            status_filter: Опциональный фильтр по статусу
            limit: Максимальное количество заданий
            offset: Количество заданий для пропуска

        Returns:
            Список объектов GenerationJob
        """
        user_jobs_key = f"{self.USER_JOBS_PREFIX}{user_id}"
        job_ids = await self._redis.lrange(user_jobs_key, offset, offset + limit - 1)

        jobs = []
        for job_id_str in job_ids:
            job = await self.get_job(UUID(job_id_str), db)
            if job is not None:
                if status_filter is None or job.status == status_filter:
                    jobs.append(job)

        return jobs


# Singleton instance
_generation_service: GenerationService | None = None


async def get_generation_service() -> GenerationService:
    """
    Получить или создать синглтон сервиса генерации.

    Returns:
        Экземпляр GenerationService
    """
    global _generation_service
    if _generation_service is None:
        redis = await RedisManager.get_client()
        _generation_service = GenerationService(redis)
    return _generation_service
