"""FastAPI роутер для эндпоинтов чата."""

import json
import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import CurrentUserId
from src.core.rate_limit import CHAT_LIMITER, rate_limit
from src.modules.chat.schemas import (
    ChatMessageCreate,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatSessionWithMessages,
)
from src.modules.chat.service import ChatService
from src.modules.chat.workflows import get_chat_workflow
from src.shared.schemas import BaseSchema, PaginatedResponse, SuccessResponse

logger = logging.getLogger(__name__)


class SimpleChatRequest(BaseSchema):
    """Упрощённый запрос чата без привязки к сессии."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Сообщение пользователя",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="ID существующей сессии (опционально)",
    )
    deck_id: UUID | None = Field(
        default=None,
        description="ID колоды для контекста (опционально)",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Дополнительный контекст",
    )

router = APIRouter(prefix="/chat", tags=["Чат"])

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
    user_id: CurrentUserId,
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
    user_id: CurrentUserId,
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
    user_id: CurrentUserId,
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
    user_id: CurrentUserId,
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
    user_id: CurrentUserId,
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
@rate_limit(CHAT_LIMITER)
async def send_message(
    session_id: Annotated[UUID, Path(description="Уникальный идентификатор сессии")],
    message: ChatMessageCreate,
    user_id: CurrentUserId,
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


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Потоковый чат (упрощённый API)",
    responses={
        200: {
            "description": "Потоковый SSE-ответ",
            "content": {
                "text/event-stream": {
                    "example": 'data: {"content":"Привет!"}\n\n',
                }
            },
        }
    },
)
@rate_limit(CHAT_LIMITER)
async def stream_chat(
    request: SimpleChatRequest,
    user_id: CurrentUserId,
    service: ChatServiceDep,
    db: DBSession,
) -> StreamingResponse:
    """Упрощённый потоковый чат.

    Автоматически создаёт сессию если не указан conversation_id.
    Удобен для быстрого взаимодействия без управления сессиями.

    Args:
        request: Запрос с сообщением и опциональными параметрами.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.
        db: Асинхронная сессия базы данных.

    Returns:
        Потоковый ответ с SSE-событиями.
    """
    # Получить или создать сессию
    session_id = request.conversation_id
    if session_id is None:
        # Создать новую сессию автоматически
        context = request.context or {}
        if request.deck_id:
            context["deck_id"] = str(request.deck_id)

        session = await service.create_session(
            user_id,
            ChatSessionCreate(
                title=request.message[:50] + ("..." if len(request.message) > 50 else ""),
                context=context if context else None,
            ),
        )
        session_id = session.id

    async def event_generator():
        """Генерировать SSE-события."""
        try:
            # Сначала отправить ID сессии для frontend
            init_data = json.dumps({
                "event": "init",
                "conversationId": str(session_id),
            })
            yield f"data: {init_data}\n\n"

            # Попробовать получить workflow для чата
            try:
                workflow = await get_chat_workflow(db)
            except Exception as e:
                logger.warning(f"LLM workflow недоступен: {e}")
                workflow = None

            if workflow is None:
                # LLM недоступен - отправить placeholder ответ
                placeholder_response = (
                    "Извините, сервис ИИ временно недоступен. "
                    "Пожалуйста, попробуйте позже или проверьте настройки LLM."
                )

                # Отправить ответ по частям для имитации стриминга
                for i in range(0, len(placeholder_response), 10):
                    chunk = placeholder_response[i : i + 10]
                    data = json.dumps({"content": chunk, "done": False})
                    yield f"data: {data}\n\n"

                # Завершающее событие
                done_data = json.dumps({"content": "", "done": True})
                yield f"data: {done_data}\n\n"
                yield "data: [DONE]\n\n"
                return

            # LLM доступен - использовать нормальный стриминг
            user_message = ChatMessageCreate(content=request.message)
            async for chunk in service.stream_response(
                session_id=session_id,
                user_id=user_id,
                user_message=user_message,
                chat_workflow=workflow,
            ):
                yield chunk

        except Exception as e:
            logger.exception("Ошибка в SSE-потоке")
            error_data = json.dumps({
                "event": "error",
                "error_code": "STREAM_ERROR",
                "message": str(e),
                "retry": False,
            })
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/message",
    status_code=status.HTTP_200_OK,
    summary="Отправить сообщение (не-потоковый)",
)
async def send_message_simple(
    request: SimpleChatRequest,
    user_id: CurrentUserId,
    service: ChatServiceDep,
    db: DBSession,
) -> dict[str, Any]:
    """Отправить сообщение и получить полный ответ (без стриминга).

    Args:
        request: Запрос с сообщением.
        user_id: UUID текущего пользователя.
        service: Экземпляр сервиса чата.
        db: Асинхронная сессия базы данных.

    Returns:
        Полный ответ от ИИ.
    """
    # Получить или создать сессию
    session_id = request.conversation_id
    if session_id is None:
        context = request.context or {}
        if request.deck_id:
            context["deck_id"] = str(request.deck_id)

        session = await service.create_session(
            user_id,
            ChatSessionCreate(
                title=request.message[:50] + ("..." if len(request.message) > 50 else ""),
                context=context if context else None,
            ),
        )
        session_id = session.id

    # Попробовать получить workflow
    try:
        workflow = await get_chat_workflow(db)
    except Exception as e:
        logger.warning(f"LLM workflow недоступен: {e}")
        return {
            "response": "Извините, сервис ИИ временно недоступен.",
            "conversation_id": str(session_id),
            "error": str(e),
        }

    # Собрать полный ответ из стрима
    full_response = ""
    user_message = ChatMessageCreate(content=request.message)

    try:
        async for chunk in service.stream_response(
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            chat_workflow=workflow,
        ):
            # Парсить SSE-формат
            if chunk.startswith("data: "):
                data_str = chunk[6:].strip()
                if data_str and data_str != "[DONE]":
                    try:
                        data = json.loads(data_str)
                        if "content" in data:
                            full_response += data["content"]
                        elif "data" in data:
                            full_response += data["data"]
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.exception("Ошибка при получении ответа")
        return {
            "response": "Произошла ошибка при обработке запроса.",
            "conversation_id": str(session_id),
            "error": str(e),
        }

    return {
        "response": full_response,
        "conversation_id": str(session_id),
    }


# ==================== Alias endpoints for frontend compatibility ====================
# Frontend uses /conversations, backend uses /sessions


@router.get(
    "/conversations",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Получить список бесед (алиас для sessions)",
)
async def list_conversations(
    user_id: CurrentUserId,
    service: ChatServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Алиас для list_sessions - совместимость с frontend."""
    sessions, total = await service.list_sessions(user_id, limit=limit, offset=skip)
    return {
        "conversations": [
            {
                "id": str(s.id),
                "title": s.title,
                "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
                "createdAt": s.created_at.isoformat() if s.created_at else None,
                "messageCount": s.message_count,
            }
            for s in sessions
        ],
        "total": total,
    }


@router.post(
    "/conversation",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Создать беседу (алиас)",
)
async def create_conversation(
    data: dict[str, Any],
    user_id: CurrentUserId,
    service: ChatServiceDep,
) -> dict[str, Any]:
    """Алиас для create_session."""
    session_data = ChatSessionCreate(
        title=data.get("title", "New Chat"),
        context={"deck_id": data["deckId"]} if data.get("deckId") else None,
    )
    session = await service.create_session(user_id, session_data)
    return {
        "id": str(session.id),
        "title": session.title,
        "createdAt": session.created_at.isoformat() if session.created_at else None,
    }


@router.get(
    "/conversation/{conversation_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Получить беседу (алиас)",
)
async def get_conversation(
    conversation_id: UUID,
    user_id: CurrentUserId,
    service: ChatServiceDep,
) -> dict[str, Any]:
    """Алиас для get_session."""
    session = await service.get_session(conversation_id, user_id)
    return {
        "id": str(session.id),
        "title": session.title,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
            }
            for m in session.messages
        ],
    }


@router.delete(
    "/conversation/{conversation_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Удалить беседу (алиас)",
)
async def delete_conversation(
    conversation_id: UUID,
    user_id: CurrentUserId,
    service: ChatServiceDep,
) -> SuccessResponse:
    """Алиас для delete_session."""
    await service.delete_session(conversation_id, user_id)
    return SuccessResponse(message="Conversation deleted")


@router.patch(
    "/conversation/{conversation_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Обновить беседу (алиас)",
)
async def update_conversation(
    conversation_id: UUID,
    data: dict[str, Any],
    user_id: CurrentUserId,
    service: ChatServiceDep,
) -> dict[str, Any]:
    """Алиас для update_session."""
    update_data = ChatSessionUpdate(title=data.get("title"))
    session = await service.update_session(conversation_id, user_id, update_data)
    return {
        "id": str(session.id),
        "title": session.title,
    }


@router.post(
    "/conversation/{conversation_id}/clear",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Очистить историю беседы",
)
async def clear_conversation(
    conversation_id: UUID,
    user_id: CurrentUserId,
    service: ChatServiceDep,
) -> SuccessResponse:
    """Очистить все сообщения в беседе."""
    # TODO: Implement clear messages in service
    # For now, just return success
    return SuccessResponse(message="Conversation cleared")
