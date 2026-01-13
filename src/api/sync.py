"""FastAPI роутер для эндпоинтов синхронизации с Anki."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.sync.schemas import (
    ImportRequest,
    ImportResult,
    SyncPullRequest,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncResult,
    SyncStatus,
)
from src.modules.sync.service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["Синхронизация"])


async def get_current_user_id() -> UUID:
    """Получить идентификатор текущего аутентифицированного пользователя.

    Это заглушка, которую следует заменить реальной зависимостью
    аутентификации.

    Returns:
        UUID: Идентификатор текущего пользователя.
    """
    # TODO: Replace with actual auth dependency
    from uuid import uuid4

    return uuid4()


CurrentUserID = Annotated[UUID, Depends(get_current_user_id)]
DBSession = Annotated[AsyncSession, Depends(get_db)]


def get_sync_service(db: DBSession) -> SyncService:
    """Получить экземпляр SyncService.

    Args:
        db: Сессия базы данных.

    Returns:
        SyncService: Экземпляр сервиса синхронизации.
    """
    return SyncService(db)


SyncServiceDep = Annotated[SyncService, Depends(get_sync_service)]


@router.post(
    "/push",
    response_model=SyncPushResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Отправить карточки в очередь синхронизации",
    description=(
        "Добавляет карточки в очередь синхронизации с Anki. "
        "Возвращает идентификатор задачи для отслеживания прогресса."
    ),
)
async def push_cards(
    request: SyncPushRequest,
    user_id: CurrentUserID,
    service: SyncServiceDep,
) -> SyncPushResponse:
    """Отправить карточки в очередь синхронизации.

    Args:
        request: Запрос на отправку с карточками.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса синхронизации.

    Returns:
        SyncPushResponse: Ответ с идентификатором задачи синхронизации.
    """
    return await service.push_cards(user_id, request)


@router.get(
    "/status",
    response_model=SyncStatus,
    status_code=status.HTTP_200_OK,
    summary="Получить статус синхронизации",
    description="Получает общий статус синхронизации для аутентифицированного пользователя.",
)
async def get_status(
    user_id: CurrentUserID,
    service: SyncServiceDep,
) -> SyncStatus:
    """Получить общий статус синхронизации.

    Args:
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса синхронизации.

    Returns:
        SyncStatus: Общий статус синхронизации.
    """
    return await service.get_status(user_id)


@router.post(
    "/pull",
    response_model=SyncPullResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить статус синхронизации карточек",
    description="Получает статус синхронизации для конкретной задачи или карточек.",
)
async def pull_status(
    request: SyncPullRequest,
    user_id: CurrentUserID,
    service: SyncServiceDep,
) -> SyncPullResponse:
    """Получить статус синхронизации карточек.

    Args:
        request: Запрос на получение статуса с идентификатором задачи или карточек.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса синхронизации.

    Returns:
        SyncPullResponse: Ответ со статусами карточек.
    """
    return await service.pull_status(user_id, request)


@router.post(
    "/execute/{sync_id}",
    response_model=SyncResult,
    status_code=status.HTTP_200_OK,
    summary="Выполнить задачу синхронизации",
    description=(
        "Выполняет ожидающую задачу синхронизации, отправляя карточки в Anki через AnkiConnect. "
        "Требуется запущенный Anki с установленным аддоном AnkiConnect."
    ),
)
async def execute_sync(
    sync_id: Annotated[UUID, Path(description="Идентификатор задачи синхронизации")],
    user_id: CurrentUserID,
    service: SyncServiceDep,
) -> SyncResult:
    """Выполнить задачу синхронизации.

    Args:
        sync_id: UUID задачи синхронизации.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса синхронизации.

    Returns:
        SyncResult: Результат синхронизации со статистикой.
    """
    return await service.sync_to_anki(sync_id, user_id)


@router.post(
    "/import",
    response_model=ImportResult,
    status_code=status.HTTP_201_CREATED,
    summary="Импортировать файл .apkg",
    description=(
        "Импортирует файл Anki .apkg и извлекает карточки. "
        "Поддерживает типы заметок Basic и Cloze."
    ),
)
async def import_apkg(
    file: Annotated[UploadFile, File(description="Файл Anki .apkg")],
    user_id: CurrentUserID,
    service: SyncServiceDep,
    deck_id: Annotated[
        UUID | None,
        Form(description="UUID целевой колоды"),
    ] = None,
    create_deck: Annotated[
        bool,
        Form(description="Создать колоду, если не существует"),
    ] = True,
    overwrite: Annotated[
        bool,
        Form(description="Перезаписать существующие карточки"),
    ] = False,
    tags: Annotated[
        str,
        Form(description="Теги через запятую для добавления к карточкам"),
    ] = "",
) -> ImportResult:
    """Импортировать файл .apkg.

    Args:
        file: Загруженный файл .apkg.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса синхронизации.
        deck_id: Опциональный UUID целевой колоды.
        create_deck: Создать колоду, если не существует.
        overwrite: Перезаписать существующие карточки.
        tags: Теги через запятую для добавления к импортированным карточкам.

    Returns:
        ImportResult: Результат импорта с импортированными карточками.

    Raises:
        HTTPException: 400 если файл не является .apkg.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith(".apkg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an .apkg file",
        )

    # Read file content
    content = await file.read()

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Create import request
    request = ImportRequest(
        deck_id=deck_id,
        create_deck=create_deck,
        overwrite=overwrite,
        tags=tag_list,
    )

    return await service.import_apkg(
        user_id=user_id,
        file_content=content,
        filename=file.filename,
        request=request,
    )


@router.post(
    "/import/stream",
    status_code=status.HTTP_200_OK,
    summary="Импортировать файл .apkg с потоковой передачей прогресса",
    description=(
        "Импортирует файл Anki .apkg с Server-Sent Events (SSE) для обновлений прогресса. "
        "Полезно для больших файлов."
    ),
    responses={
        200: {
            "description": "Потоковый SSE ответ",
            "content": {
                "text/event-stream": {
                    "example": (
                        'data: {"stage":"importing","progress":50,"current":250,'
                        '"total":500,"message":"Importing card 250 of 500"}\n\n'
                    ),
                }
            },
        }
    },
)
async def import_apkg_stream(
    file: Annotated[UploadFile, File(description="Файл Anki .apkg")],
    user_id: CurrentUserID,
    service: SyncServiceDep,
    deck_id: Annotated[
        UUID | None,
        Form(description="UUID целевой колоды"),
    ] = None,
    create_deck: Annotated[
        bool,
        Form(description="Создать колоду, если не существует"),
    ] = True,
    overwrite: Annotated[
        bool,
        Form(description="Перезаписать существующие карточки"),
    ] = False,
    tags: Annotated[
        str,
        Form(description="Теги через запятую для добавления к карточкам"),
    ] = "",
) -> StreamingResponse:
    """Импортировать файл .apkg с потоковой передачей прогресса.

    Args:
        file: Загруженный файл .apkg.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса синхронизации.
        deck_id: Опциональный UUID целевой колоды.
        create_deck: Создать колоду, если не существует.
        overwrite: Перезаписать существующие карточки.
        tags: Теги через запятую для добавления к импортированным карточкам.

    Returns:
        StreamingResponse: Потоковый ответ с SSE событиями прогресса.

    Raises:
        HTTPException: 400 если файл не является .apkg.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith(".apkg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an .apkg file",
        )

    # Read file content
    content = await file.read()

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Create import request
    request = ImportRequest(
        deck_id=deck_id,
        create_deck=create_deck,
        overwrite=overwrite,
        tags=tag_list,
    )

    async def event_generator():
        """Генерирует SSE события для прогресса импорта."""
        try:
            async for progress in service.stream_import_progress(
                user_id=user_id,
                file_content=content,
                filename=file.filename,
                request=request,
            ):
                yield f"data: {progress.model_dump_json()}\n\n"
        except Exception as e:
            logger.exception("Error in import stream")
            error_data = {
                "stage": "error",
                "progress": 0,
                "current": 0,
                "total": 0,
                "message": f"Import failed: {str(e)}",
            }
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
