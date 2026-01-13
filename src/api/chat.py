"""FastAPI роутер для эндпоинтов чата."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.chat.schemas import (
    ChatMessageCreate,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatSessionWithMessages,
)
from src.modules.chat.service import ChatService
from src.modules.chat.workflows import get_chat_workflow
from src.shared.schemas import PaginatedResponse, SuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Чат"])


async def get_current_user_id() -> UUID:
    """Получить ID текущего аутентифицированного пользователя.

    Это заглушка, которая должна быть заменена на реальную
    зависимость аутентификации.

    Returns:
        UUID текущего пользователя.
    """
    # TODO: Заменить на реальную зависимость аутентификации
    from uuid import uuid4

    return uuid4()


CurrentUserID = Annotated[UUID, Depends(get_current_user_id)]
DBSession = Annotated[AsyncSession, Depends(get_db)]


def get_chat_service(db: DBSession) -> ChatService:
    """Получить экземпляр сервиса чата.

    Args:
        db: Асинхронная сессия базы данных.

    Returns:
        Экземпляр ChatService для работы с чат-сессиями.
    """
    return ChatService(db)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую чат-сессию",
)
async def create_session(
    data: ChatSessionCreate,
    user_id: CurrentUserID,
    service: ChatServiceDep,
) -> ChatSessionResponse:
    """Создать новую чат-сессию.

    Создает новую сессию чата для генерации карточек с помощью ИИ.
    Сессия сохраняет историю диалога и контекст.

    Args:
        data: Данные для создания сессии.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.

    Returns:
        Созданная сессия чата.
    """
    return await service.create_session(user_id, data)


@router.get(
    "/sessions",
    response_model=PaginatedResponse[ChatSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить список чат-сессий",
)
async def list_sessions(
    user_id: CurrentUserID,
    service: ChatServiceDep,
    page: Annotated[
        int,
        Query(ge=1, description="Номер страницы (начиная с 1)"),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=100, description="Количество элементов на странице"),
    ] = 20,
) -> PaginatedResponse[ChatSessionResponse]:
    """Получить список чат-сессий пользователя.

    Возвращает пагинированный список всех чат-сессий
    текущего аутентифицированного пользователя.

    Args:
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.
        page: Номер страницы (начиная с 1).
        page_size: Количество элементов на странице.

    Returns:
        Пагинированный список сессий.
    """
    offset = (page - 1) * page_size
    sessions, total = await service.list_sessions(
        user_id,
        limit=page_size,
        offset=offset,
    )

    return PaginatedResponse(
        items=sessions,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionWithMessages,
    status_code=status.HTTP_200_OK,
    summary="Получить чат-сессию по ID",
)
async def get_session(
    session_id: Annotated[UUID, Path(description="Уникальный идентификатор сессии")],
    user_id: CurrentUserID,
    service: ChatServiceDep,
) -> ChatSessionWithMessages:
    """Получить чат-сессию с сообщениями.

    Возвращает детальную информацию о сессии, включая
    полную историю сообщений.

    Args:
        session_id: UUID сессии.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.

    Returns:
        Сессия с полной историей сообщений.

    Raises:
        HTTPException: 404 если сессия не найдена.
    """
    return await service.get_session(session_id, user_id)


@router.patch(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить чат-сессию",
)
async def update_session(
    session_id: Annotated[UUID, Path(description="Уникальный идентификатор сессии")],
    data: ChatSessionUpdate,
    user_id: CurrentUserID,
    service: ChatServiceDep,
) -> ChatSessionResponse:
    """Обновить чат-сессию.

    Позволяет изменить название сессии или её контекст.

    Args:
        session_id: UUID сессии для обновления.
        data: Данные для обновления.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.

    Returns:
        Обновленная сессия.

    Raises:
        HTTPException: 404 если сессия не найдена.
    """
    return await service.update_session(session_id, user_id, data)


@router.delete(
    "/sessions/{session_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Удалить чат-сессию",
)
async def delete_session(
    session_id: Annotated[UUID, Path(description="Уникальный идентификатор сессии")],
    user_id: CurrentUserID,
    service: ChatServiceDep,
) -> SuccessResponse:
    """Удалить чат-сессию.

    Удаляет сессию чата вместе со всей историей сообщений.
    Это действие необратимо.

    Args:
        session_id: UUID сессии для удаления.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.

    Returns:
        Подтверждение успешного удаления.

    Raises:
        HTTPException: 404 если сессия не найдена.
    """
    await service.delete_session(session_id, user_id)
    return SuccessResponse(message="Чат-сессия успешно удалена")


@router.post(
    "/sessions/{session_id}/messages",
    status_code=status.HTTP_200_OK,
    summary="Отправить сообщение и получить потоковый ответ",
    responses={
        200: {
            "description": "Потоковый SSE-ответ",
            "content": {
                "text/event-stream": {
                    "example": (
                        'data: {"event":"content","data":"Привет",'
                        '"message_id":"...","done":false}\n\n'
                    ),
                }
            },
        }
    },
)
async def send_message(
    session_id: Annotated[UUID, Path(description="Уникальный идентификатор сессии")],
    message: ChatMessageCreate,
    user_id: CurrentUserID,
    service: ChatServiceDep,
    db: DBSession,
) -> StreamingResponse:
    """Отправить сообщение и получить потоковый ответ.

    Отправляет сообщение пользователя в чат-сессию и возвращает
    потоковый ответ ИИ через Server-Sent Events (SSE).

    Типы событий:
    - content: Частичный контент ответа
    - metadata: Метаданные ответа (токены, источники)
    - done: Завершение потока
    - error: Произошла ошибка

    Args:
        session_id: UUID сессии.
        message: Сообщение пользователя.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.
        db: Асинхронная сессия базы данных.

    Returns:
        Потоковый ответ с SSE-событиями.

    Raises:
        HTTPException: 404 если сессия не найдена.
    """
    # Получить workflow для чата
    workflow = await get_chat_workflow(db)

    async def event_generator():
        """Генерировать SSE-события."""
        try:
            async for chunk in service.stream_response(
                session_id=session_id,
                user_id=user_id,
                user_message=message,
                chat_workflow=workflow,
            ):
                yield chunk
        except Exception as e:
            logger.exception("Ошибка в SSE-потоке")
            error_data = {
                "event": "error",
                "error_code": "STREAM_ERROR",
                "message": str(e),
                "retry": False,
            }
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Отключить буферизацию nginx
        },
    )
