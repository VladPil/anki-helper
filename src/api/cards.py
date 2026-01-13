"""FastAPI роутер для эндпоинтов карточек."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import CurrentUserId
from src.modules.cards.models import CardStatus
from src.modules.cards.schemas import (
    CardApproveRequest,
    CardBulkCreate,
    CardBulkError,
    CardBulkResponse,
    CardCreate,
    CardRejectRequest,
    CardResponse,
    CardUpdate,
    CardWithGenerationInfo,
    GenerationInfoResponse,
)
from src.modules.cards.service import (
    CardNotFoundError,
    CardService,
    DeckNotFoundError,
    InvalidCardStatusTransitionError,
    TemplateNotFoundError,
)
from src.shared.schemas import PaginatedResponse, PaginationParams, SuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cards", tags=["Карточки"])


async def get_card_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CardService:
    """Получить экземпляр сервиса карточек.

    Args:
        session: Асинхронная сессия базы данных.

    Returns:
        Экземпляр CardService для работы с карточками.
    """
    return CardService(session)


@router.post(
    "",
    response_model=CardResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую карточку",
    responses={
        201: {"description": "Карточка успешно создана"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Колода или шаблон не найдены"},
    },
)
async def create_card(
    data: CardCreate,
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardResponse:
    """Создать новую карточку.

    Создает новую флеш-карточку в указанной колоде с использованием
    заданного шаблона. Карточка создается в статусе DRAFT.

    Args:
        data: Данные для создания карточки (колода, шаблон, поля).
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Созданная карточка с присвоенным ID.

    Raises:
        HTTPException: 404 если колода или шаблон не найдены.
    """
    try:
        card = await service.create(
            user_id=user_id,
            data=data,
            created_by=str(user_id),
        )
        return CardResponse.model_validate(card)
    except DeckNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {e.deck_id}",
        ) from e
    except TemplateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {e.template_id}",
        ) from e


@router.post(
    "/bulk",
    response_model=CardBulkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать несколько карточек",
    responses={
        201: {"description": "Карточки созданы (возможен частичный успех)"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Колода не найдена"},
    },
)
async def create_cards_bulk(
    data: CardBulkCreate,
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardBulkResponse:
    """Массово создать несколько карточек.

    Создает несколько флеш-карточек за один запрос. Возвращает как
    успешно созданные карточки, так и информацию об ошибках.

    Args:
        data: Данные для массового создания (колода, шаблон, список карточек).
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Ответ с созданными карточками и списком ошибок.

    Raises:
        HTTPException: 404 если колода не найдена.
    """
    try:
        created, errors = await service.create_bulk(
            user_id=user_id,
            deck_id=data.deck_id,
            template_id=data.template_id,
            items=data.cards,
            created_by=str(user_id),
        )

        return CardBulkResponse(
            created=[CardResponse.model_validate(card) for card in created],
            failed=[CardBulkError(index=idx, error=err) for idx, err in errors],
            total_created=len(created),
            total_failed=len(errors),
        )
    except DeckNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {e.deck_id}",
        ) from e


@router.get(
    "",
    response_model=PaginatedResponse[CardResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить список карточек",
    responses={
        200: {"description": "Список карточек"},
        401: {"description": "Пользователь не аутентифицирован"},
    },
)
async def list_cards(
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
    pagination: Annotated[PaginationParams, Depends()],
    deck_id: Annotated[
        UUID | None,
        Query(alias="deckId", description="Фильтр по ID колоды"),
    ] = None,
    status_filter: Annotated[
        CardStatus | None,
        Query(alias="status", description="Фильтр по статусу карточки"),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Query(description="Фильтр по тегам (любое совпадение)"),
    ] = None,
) -> PaginatedResponse[CardResponse]:
    """Получить список карточек с фильтрацией.

    Возвращает карточки текущего пользователя с возможностью
    фильтрации по колоде, статусу и тегам.

    Args:
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.
        pagination: Параметры пагинации.
        deck_id: Опциональный фильтр по ID колоды.
        status_filter: Опциональный фильтр по статусу.
        tags: Опциональный фильтр по тегам.

    Returns:
        Пагинированный список карточек.
    """
    if deck_id:
        cards, total = await service.list_by_deck(
            deck_id=deck_id,
            user_id=user_id,
            status=status_filter,
            tags=tags,
            offset=pagination.offset,
            limit=pagination.limit,
        )
    elif status_filter:
        cards, total = await service.list_by_status(
            user_id=user_id,
            status=status_filter,
            offset=pagination.offset,
            limit=pagination.limit,
        )
    else:
        # По умолчанию: все карточки пользователя
        cards, total = await service.list_all(
            user_id=user_id,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    items = [CardResponse.model_validate(card) for card in cards]
    return PaginatedResponse.create(items=items, total=total, params=pagination)


@router.get(
    "/{card_id}",
    response_model=CardWithGenerationInfo,
    status_code=status.HTTP_200_OK,
    summary="Получить карточку по ID",
    responses={
        200: {"description": "Детали карточки"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Карточка не найдена"},
    },
)
async def get_card(
    card_id: Annotated[UUID, Path(description="Уникальный идентификатор карточки")],
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardWithGenerationInfo:
    """Получить карточку по идентификатору.

    Возвращает карточку с метаданными генерации, если карточка
    была создана с помощью ИИ.

    Args:
        card_id: UUID карточки для получения.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Карточка с информацией о генерации.

    Raises:
        HTTPException: 404 если карточка не найдена или доступ запрещен.
    """
    card = await service.get_by_id_for_user(card_id, user_id, include_generation_info=True)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {card_id}",
        )

    response = CardWithGenerationInfo.model_validate(card)
    if card.generation_info:
        response.generation_info = GenerationInfoResponse.model_validate(card.generation_info)

    return response


@router.patch(
    "/{card_id}",
    response_model=CardResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить карточку",
    responses={
        200: {"description": "Карточка успешно обновлена"},
        400: {"description": "Недопустимый переход статуса"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Карточка не найдена"},
    },
)
async def update_card(
    card_id: Annotated[UUID, Path(description="Уникальный идентификатор карточки")],
    data: CardUpdate,
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardResponse:
    """Обновить карточку.

    Обновляет поля карточки. Позволяет изменять содержимое,
    теги, колоду и статус карточки.

    Args:
        card_id: UUID карточки для обновления.
        data: Данные для обновления.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Обновленная карточка.

    Raises:
        HTTPException: 404 если карточка не найдена.
        HTTPException: 400 при недопустимом переходе статуса.
    """
    try:
        card = await service.update(
            card_id=card_id,
            user_id=user_id,
            data=data,
            updated_by=str(user_id),
        )
        return CardResponse.model_validate(card)
    except CardNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {e.card_id}",
        ) from e
    except DeckNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {e.deck_id}",
        ) from e
    except InvalidCardStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition: {e.current_status.value} -> {e.target_status.value}"
            ),
        ) from e


@router.delete(
    "/{card_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Удалить карточку",
    responses={
        200: {"description": "Карточка успешно удалена"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Карточка не найдена"},
    },
)
async def delete_card(
    card_id: Annotated[UUID, Path(description="Уникальный идентификатор карточки")],
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
    hard: Annotated[
        bool,
        Query(description="Полностью удалить (по умолчанию: мягкое удаление)"),
    ] = False,
) -> SuccessResponse:
    """Удалить карточку.

    По умолчанию выполняет мягкое удаление (soft delete).
    Используйте hard=True для полного удаления без возможности восстановления.

    Args:
        card_id: UUID карточки для удаления.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.
        hard: Флаг полного удаления.

    Returns:
        Подтверждение успешного удаления.

    Raises:
        HTTPException: 404 если карточка не найдена.
    """
    try:
        await service.delete(
            card_id=card_id,
            user_id=user_id,
            hard_delete=hard,
        )
        return SuccessResponse(
            message=f"Card {'permanently deleted' if hard else 'deleted'} successfully"
        )
    except CardNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {e.card_id}",
        ) from e


@router.post(
    "/{card_id}/approve",
    response_model=CardResponse,
    status_code=status.HTTP_200_OK,
    summary="Одобрить карточку",
    responses={
        200: {"description": "Карточка успешно одобрена"},
        400: {"description": "Недопустимый переход статуса"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Карточка не найдена"},
    },
)
async def approve_card(
    card_id: Annotated[UUID, Path(description="Уникальный идентификатор карточки")],
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
    data: CardApproveRequest | None = None,
) -> CardResponse:
    """Одобрить карточку для синхронизации с Anki.

    Переводит карточку из статуса DRAFT в статус APPROVED.
    Одобренные карточки готовы к синхронизации с Anki.

    Args:
        card_id: UUID карточки для одобрения.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.
        data: Опциональный запрос с причиной одобрения.

    Returns:
        Одобренная карточка.

    Raises:
        HTTPException: 404 если карточка не найдена.
        HTTPException: 400 при недопустимом статусе карточки.
    """
    try:
        card = await service.approve(
            card_id=card_id,
            user_id=user_id,
            reason=data.reason if data else None,
            updated_by=str(user_id),
        )
        return CardResponse.model_validate(card)
    except CardNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {e.card_id}",
        ) from e
    except InvalidCardStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve card with status: {e.current_status.value}",
        ) from e


@router.post(
    "/{card_id}/reject",
    response_model=CardResponse,
    status_code=status.HTTP_200_OK,
    summary="Отклонить карточку",
    responses={
        200: {"description": "Карточка успешно отклонена"},
        400: {"description": "Недопустимый переход статуса"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Карточка не найдена"},
    },
)
async def reject_card(
    card_id: Annotated[UUID, Path(description="Уникальный идентификатор карточки")],
    data: CardRejectRequest,
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardResponse:
    """Отклонить карточку.

    Переводит карточку из статуса DRAFT в статус REJECTED с указанием
    причины отклонения. Отклоненные карточки не синхронизируются с Anki.

    Args:
        card_id: UUID карточки для отклонения.
        data: Запрос с причиной отклонения.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Отклоненная карточка.

    Raises:
        HTTPException: 404 если карточка не найдена.
        HTTPException: 400 при недопустимом статусе карточки.
    """
    try:
        card = await service.reject(
            card_id=card_id,
            user_id=user_id,
            reason=data.reason,
            updated_by=str(user_id),
        )
        return CardResponse.model_validate(card)
    except CardNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {e.card_id}",
        ) from e
    except InvalidCardStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject card with status: {e.current_status.value}",
        ) from e


@router.post(
    "/bulk/approve",
    response_model=CardBulkResponse,
    status_code=status.HTTP_200_OK,
    summary="Массово одобрить карточки",
    responses={
        200: {"description": "Карточки одобрены (возможен частичный успех)"},
        401: {"description": "Пользователь не аутентифицирован"},
    },
)
async def approve_cards_bulk(
    card_ids: list[UUID],
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardBulkResponse:
    """Массово одобрить несколько карточек.

    Одобряет несколько карточек за один запрос. Возвращает как
    успешно одобренные карточки, так и информацию об ошибках.

    Args:
        card_ids: Список UUID карточек для одобрения.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Ответ с одобренными карточками и списком ошибок.
    """
    approved, errors = await service.bulk_approve(
        card_ids=card_ids,
        user_id=user_id,
        updated_by=str(user_id),
    )

    return CardBulkResponse(
        created=[CardResponse.model_validate(card) for card in approved],
        failed=[CardBulkError(index=0, error=f"{card_id}: {err}") for card_id, err in errors],
        total_created=len(approved),
        total_failed=len(errors),
    )


@router.post(
    "/bulk/reject",
    response_model=CardBulkResponse,
    status_code=status.HTTP_200_OK,
    summary="Массово отклонить карточки",
    responses={
        200: {"description": "Карточки отклонены (возможен частичный успех)"},
        401: {"description": "Пользователь не аутентифицирован"},
    },
)
async def reject_cards_bulk(
    card_ids: list[UUID],
    reason: str,
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardBulkResponse:
    """Массово отклонить несколько карточек.

    Отклоняет несколько карточек за один запрос с указанием общей
    причины отклонения. Возвращает как успешно отклоненные карточки,
    так и информацию об ошибках.

    Args:
        card_ids: Список UUID карточек для отклонения.
        reason: Причина отклонения.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Ответ с отклоненными карточками и списком ошибок.
    """
    rejected, errors = await service.bulk_reject(
        card_ids=card_ids,
        user_id=user_id,
        reason=reason,
        updated_by=str(user_id),
    )

    return CardBulkResponse(
        created=[CardResponse.model_validate(card) for card in rejected],
        failed=[CardBulkError(index=0, error=f"{card_id}: {err}") for card_id, err in errors],
        total_created=len(rejected),
        total_failed=len(errors),
    )


@router.post(
    "/{card_id}/restore",
    response_model=CardResponse,
    status_code=status.HTTP_200_OK,
    summary="Восстановить удаленную карточку",
    responses={
        200: {"description": "Карточка успешно восстановлена"},
        401: {"description": "Пользователь не аутентифицирован"},
        404: {"description": "Карточка не найдена"},
    },
)
async def restore_card(
    card_id: Annotated[UUID, Path(description="Уникальный идентификатор карточки")],
    user_id: CurrentUserId,
    service: Annotated[CardService, Depends(get_card_service)],
) -> CardResponse:
    """Восстановить мягко удаленную карточку.

    Восстанавливает карточку, которая была удалена с помощью
    мягкого удаления (soft delete).

    Args:
        card_id: UUID карточки для восстановления.
        user_id: ID аутентифицированного пользователя.
        service: Экземпляр сервиса карточек.

    Returns:
        Восстановленная карточка.

    Raises:
        HTTPException: 404 если карточка не найдена.
    """
    try:
        card = await service.restore(card_id, user_id)
        return CardResponse.model_validate(card)
    except CardNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card not found: {e.card_id}",
        ) from e
