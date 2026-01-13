"""FastAPI роутер для эндпоинтов генерации карточек."""

import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status
from sse_starlette.sse import EventSourceResponse

from src.core.dependencies import CurrentUserId, DatabaseSession
from src.core.logging import get_structured_logger
from src.modules.generation.schemas import (
    GenerationJob,
    GenerationJobStatus,
    GenerationRequest,
    GenerationResponse,
    GenerationStatus,
)
from src.modules.generation.service import GenerationService, get_generation_service

logger = get_structured_logger(__name__)

router = APIRouter(prefix="/generate", tags=["Генерация"])


@router.post(
    "",
    response_model=GenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить генерацию карточек",
    description="Запускает асинхронную задачу генерации карточек.",
)
async def generate_cards(
    request: GenerationRequest,
    background_tasks: BackgroundTasks,
    user_id: CurrentUserId,
    db: DatabaseSession,
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationResponse:
    """Запустить задачу генерации карточек.

    Создает новую задачу генерации и запускает обработку в фоновом режиме.
    Немедленно возвращает идентификатор задачи для отслеживания прогресса.

    Args:
        request: Параметры запроса на генерацию.
        background_tasks: Фоновые задачи FastAPI.
        user_id: Идентификатор текущего аутентифицированного пользователя.
        db: Сессия базы данных.
        service: Экземпляр сервиса генерации.

    Returns:
        GenerationResponse: Ответ с идентификатором задачи и начальным статусом.
    """
    logger.info(
        "Starting card generation",
        user_id=str(user_id),
        topic=request.topic,
        num_cards=request.num_cards,
    )

    # Create the generation job
    job = await service.create_job(
        user_id=user_id,
        request=request,
        db=db,
    )

    # Start processing in background
    background_tasks.add_task(
        service.process_job,
        job_id=job.id,
        request=request,
    )

    return GenerationResponse(
        job_id=job.id,
        status=GenerationStatus.PENDING,
        message="Card generation started. Use the job ID to track progress.",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=GenerationJob,
    status_code=status.HTTP_200_OK,
    summary="Получить информацию о задаче генерации",
    description="Получает детальную информацию о задаче, включая карточки.",
)
async def get_job(
    job_id: Annotated[UUID, Path(description="Уникальный идентификатор задачи генерации")],
    user_id: CurrentUserId,
    db: DatabaseSession,
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationJob:
    """Получить детали задачи генерации.

    Возвращает полную информацию о задаче, включая все сгенерированные карточки.
    Доступ к задаче имеет только её владелец.

    Args:
        job_id: Идентификатор задачи для получения.
        user_id: Идентификатор текущего аутентифицированного пользователя.
        db: Сессия базы данных.
        service: Экземпляр сервиса генерации.

    Returns:
        GenerationJob: Полная информация о задаче генерации.

    Raises:
        HTTPException: 404 если задача не найдена, 403 если доступ запрещен.
    """
    job = await service.get_job(job_id=job_id, db=db)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found",
        )

    if job.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this generation job",
        )

    return job


@router.get(
    "/jobs/{job_id}/status",
    response_model=GenerationJobStatus,
    status_code=status.HTTP_200_OK,
    summary="Получить статус задачи генерации",
    description="Получает текущий статус и прогресс выполнения задачи генерации.",
)
async def get_job_status(
    job_id: Annotated[UUID, Path(description="Уникальный идентификатор задачи генерации")],
    user_id: CurrentUserId,
    db: DatabaseSession,
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationJobStatus:
    """Получить статус задачи генерации.

    Возвращает облегченный ответ со статусом для опроса.

    Args:
        job_id: Идентификатор задачи для проверки.
        user_id: Идентификатор текущего аутентифицированного пользователя.
        db: Сессия базы данных.
        service: Экземпляр сервиса генерации.

    Returns:
        GenerationJobStatus: Информация о прогрессе выполнения задачи.

    Raises:
        HTTPException: 404 если задача не найдена, 403 если доступ запрещен.
    """
    status_info = await service.get_job_status(job_id=job_id, db=db)

    if status_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found",
        )

    # Check ownership via the job
    job = await service.get_job(job_id=job_id, db=db)
    if job and job.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this generation job",
        )

    return status_info


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=GenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Отменить задачу генерации",
    description="Отменяет выполняющуюся задачу генерации карточек.",
)
async def cancel_job(
    job_id: Annotated[UUID, Path(description="Уникальный идентификатор задачи генерации")],
    user_id: CurrentUserId,
    db: DatabaseSession,
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> GenerationResponse:
    """Отменить задачу генерации.

    Пытается отменить выполняющуюся задачу. Уже завершенные или
    неуспешные задачи не могут быть отменены.

    Args:
        job_id: Идентификатор задачи для отмены.
        user_id: Идентификатор текущего аутентифицированного пользователя.
        db: Сессия базы данных.
        service: Экземпляр сервиса генерации.

    Returns:
        GenerationResponse: Ответ с обновленным статусом задачи.

    Raises:
        HTTPException: 404 если задача не найдена, 403 если доступ запрещен,
            400 если задачу нельзя отменить.
    """
    job = await service.get_job(job_id=job_id, db=db)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation job {job_id} not found",
        )

    if job.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this generation job",
        )

    if job.status in (GenerationStatus.COMPLETED, GenerationStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}",
        )

    await service.cancel_job(job_id=job_id, db=db)

    return GenerationResponse(
        job_id=job_id,
        status=GenerationStatus.CANCELLED,
        message="Generation job cancelled",
    )


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Потоковая генерация карточек",
    description="Потоковая генерация карточек с использованием Server-Sent Events (SSE).",
)
async def generate_cards_stream(
    request: GenerationRequest,
    user_id: CurrentUserId,
    db: DatabaseSession,
    service: Annotated[GenerationService, Depends(get_generation_service)],
) -> EventSourceResponse:
    """Потоковая генерация карточек с SSE.

    Предоставляет обновления в реальном времени по мере генерации карточек.
    Типы событий: card, progress, error, complete.

    Args:
        request: Параметры запроса на генерацию.
        user_id: Идентификатор текущего аутентифицированного пользователя.
        db: Сессия базы данных.
        service: Экземпляр сервиса генерации.

    Returns:
        EventSourceResponse: Поток событий генерации.
    """
    logger.info(
        "Starting streaming card generation",
        user_id=str(user_id),
        topic=request.topic,
        num_cards=request.num_cards,
    )

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        """Генерирует SSE события для генерации карточек."""
        try:
            async for event in service.generate_stream(
                user_id=user_id,
                request=request,
                db=db,
            ):
                yield {
                    "event": event.type,
                    "data": event.model_dump_json(),
                }

                # Allow other tasks to run
                await asyncio.sleep(0)

        except Exception as e:
            logger.error("Stream generation error", error=str(e))
            yield {
                "event": "error",
                "data": {"error": str(e)},
            }

    return EventSourceResponse(event_generator())


@router.get(
    "/jobs",
    response_model=list[GenerationJob],
    status_code=status.HTTP_200_OK,
    summary="Получить список задач генерации",
    description="Получает список всех задач генерации текущего пользователя.",
)
async def list_jobs(
    user_id: CurrentUserId,
    db: DatabaseSession,
    service: Annotated[GenerationService, Depends(get_generation_service)],
    status_filter: Annotated[
        GenerationStatus | None,
        Query(alias="status", description="Фильтр по статусу задачи"),
    ] = None,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Максимальное количество задач для возврата"),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0, description="Количество задач для пропуска"),
    ] = 0,
) -> list[GenerationJob]:
    """Получить список задач генерации пользователя.

    Возвращает пагинированный список задач генерации с возможностью
    фильтрации по статусу.

    Args:
        user_id: Идентификатор текущего аутентифицированного пользователя.
        db: Сессия базы данных.
        service: Экземпляр сервиса генерации.
        status_filter: Опциональный фильтр по статусу.
        limit: Максимальное количество задач для возврата.
        offset: Количество задач для пропуска.

    Returns:
        list[GenerationJob]: Список объектов GenerationJob.
    """
    jobs = await service.list_jobs(
        user_id=user_id,
        db=db,
        status_filter=status_filter,
        limit=min(limit, 100),
        offset=offset,
    )

    return jobs
