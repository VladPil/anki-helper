"""FastAPI роутер для эндпоинтов колод."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import CurrentUserId
from src.modules.decks.models import Deck
from src.modules.decks.schemas import (
    CardBriefResponse,
    DeckCreate,
    DeckResponse,
    DeckTreeResponse,
    DeckUpdate,
    DeckWithCards,
)
from src.modules.decks.service import (
    DeckAccessDeniedError,
    DeckCircularReferenceError,
    DeckNotFoundError,
    DeckService,
)
from src.shared.schemas import PaginatedResponse, PaginationParams, SuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decks", tags=["Колоды"])


async def get_deck_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeckService:
    """Получить экземпляр сервиса колод.

    Args:
        session: Асинхронная сессия базы данных

    Returns:
        DeckService: Экземпляр сервиса колод

    """
    return DeckService(session)


@router.post(
    "",
    response_model=DeckResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новую колоду",
    responses={
        201: {"description": "Колода успешно создана"},
        400: {"description": "Некорректная родительская колода"},
        401: {"description": "Не аутентифицирован"},
        403: {"description": "Доступ к родительской колоде запрещён"},
        404: {"description": "Родительская колода не найдена"},
    },
)
async def create_deck(
    data: DeckCreate,
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
) -> DeckResponse:
    """Создать новую колоду.

    Создаёт новую колоду для аутентифицированного пользователя. Опционально можно
    указать parent_id для создания вложенной колоды в иерархии.

    Args:
        data: Данные для создания колоды, включая название и описание
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод

    Returns:
        DeckResponse: Созданная колода

    Raises:
        HTTPException: 404 если родительская колода не найдена
        HTTPException: 403 если доступ к родительской колоде запрещён

    """
    try:
        deck = await service.create(
            owner_id=user_id,
            data=data,
            created_by=str(user_id),
        )
        return DeckResponse.model_validate(deck)
    except DeckNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent deck not found: {e.deck_id}",
        ) from e
    except DeckAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to parent deck",
        ) from e


@router.get(
    "",
    response_model=PaginatedResponse[DeckResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить список колод пользователя",
    responses={
        200: {"description": "Список колод"},
        401: {"description": "Не аутентифицирован"},
    },
)
async def list_decks(
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
    pagination: Annotated[PaginationParams, Depends()],
    parent_id: Annotated[
        UUID | None,
        Query(description="Фильтр по ID родительской колоды"),
    ] = None,
    root_only: Annotated[
        bool,
        Query(description="Возвращать только корневые колоды"),
    ] = False,
) -> PaginatedResponse[DeckResponse]:
    """Получить список колод аутентифицированного пользователя.

    Возвращает постраничный список колод с поддержкой фильтрации по родительской
    колоде. Можно запросить только корневые колоды (без родителя).

    Args:
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод
        pagination: Параметры пагинации
        parent_id: Фильтр по ID родительской колоды
        root_only: Если True, возвращать только корневые колоды

    Returns:
        PaginatedResponse[DeckResponse]: Постраничный список колод

    """
    if root_only:
        decks, total = await service.list_root_decks(
            owner_id=user_id,
            offset=pagination.offset,
            limit=pagination.limit,
        )
    else:
        decks, total = await service.list_by_owner(
            owner_id=user_id,
            parent_id=parent_id,
            offset=pagination.offset,
            limit=pagination.limit,
        )

    # Get card counts for all decks
    deck_ids = [deck.id for deck in decks]
    card_counts = await service.get_card_counts(deck_ids) if deck_ids else {}

    items = []
    for deck in decks:
        response = DeckResponse.model_validate(deck)
        response.card_count = card_counts.get(deck.id, 0)
        items.append(response)

    return PaginatedResponse.create(items=items, total=total, params=pagination)


@router.get(
    "/tree",
    response_model=list[DeckTreeResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить дерево колод",
    responses={
        200: {"description": "Дерево колод"},
        401: {"description": "Не аутентифицирован"},
    },
)
async def get_deck_tree(
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
    root_id: Annotated[
        UUID | None,
        Query(description="Начать с определённой колоды (по умолчанию: все корневые)"),
    ] = None,
) -> list[DeckTreeResponse]:
    """Получить иерархическое дерево колод.

    Возвращает вложенную структуру колод с их дочерними элементами.
    Полезно для отображения полной иерархии колод пользователя.

    Args:
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод
        root_id: ID корневой колоды для начала дерева

    Returns:
        list[DeckTreeResponse]: Список корневых колод с вложенными дочерними

    """
    decks = await service.get_deck_tree(
        owner_id=user_id,
        root_deck_id=root_id,
    )

    # Собрать все ID колод из дерева для получения card_count
    def collect_deck_ids(deck: Deck) -> list[UUID]:
        """Рекурсивно собрать ID всех колод в дереве."""
        ids = [deck.id]
        for child in deck.children:
            ids.extend(collect_deck_ids(child))
        return ids

    all_deck_ids: list[UUID] = []
    for deck in decks:
        all_deck_ids.extend(collect_deck_ids(deck))

    # Получить количества карточек для всех колод
    card_counts = await service.get_card_counts(all_deck_ids) if all_deck_ids else {}

    def build_tree(deck: Deck) -> DeckTreeResponse:
        """Рекурсивно построить ответ-дерево."""
        response = DeckTreeResponse.model_validate(deck)
        response.card_count = card_counts.get(deck.id, 0)
        response.children = [build_tree(child) for child in deck.children]
        return response

    return [build_tree(deck) for deck in decks]


@router.get(
    "/{deck_id}",
    response_model=DeckResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить колоду по ID",
    responses={
        200: {"description": "Данные колоды"},
        401: {"description": "Не аутентифицирован"},
        404: {"description": "Колода не найдена"},
    },
)
async def get_deck(
    deck_id: Annotated[UUID, Path(description="Уникальный идентификатор колоды")],
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
) -> DeckResponse:
    """Получить колоду по её ID.

    Возвращает детальную информацию о колоде по её уникальному идентификатору.
    Доступны только колоды, принадлежащие текущему пользователю.

    Args:
        deck_id: Уникальный идентификатор колоды
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод

    Returns:
        DeckResponse: Данные колоды

    Raises:
        HTTPException: 404 если колода не найдена или доступ запрещён

    """
    deck = await service.get_by_id_for_user(deck_id, user_id)
    if deck is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {deck_id}",
        )
    response = DeckResponse.model_validate(deck)
    card_counts = await service.get_card_counts([deck_id])
    response.card_count = card_counts.get(deck_id, 0)
    return response


@router.get(
    "/{deck_id}/cards",
    response_model=DeckWithCards,
    status_code=status.HTTP_200_OK,
    summary="Получить колоду с карточками",
    responses={
        200: {"description": "Колода с карточками"},
        401: {"description": "Не аутентифицирован"},
        404: {"description": "Колода не найдена"},
    },
)
async def get_deck_with_cards(
    deck_id: Annotated[UUID, Path(description="Уникальный идентификатор колоды")],
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
) -> DeckWithCards:
    """Получить колоду со всеми её карточками.

    Возвращает детальную информацию о колоде вместе со списком всех карточек,
    принадлежащих этой колоде. Удалённые карточки не включаются в ответ.

    Args:
        deck_id: Уникальный идентификатор колоды
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод

    Returns:
        DeckWithCards: Колода с карточками

    Raises:
        HTTPException: 404 если колода не найдена или доступ запрещён

    """
    deck = await service.get_with_cards(deck_id, user_id)
    if deck is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {deck_id}",
        )

    response = DeckWithCards.model_validate(deck)
    response.cards = [
        CardBriefResponse(id=card.id, status=card.status.value)
        for card in deck.cards
        if card.deleted_at is None
    ]
    response.card_count = len(response.cards)
    return response


@router.patch(
    "/{deck_id}",
    response_model=DeckResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить колоду",
    responses={
        200: {"description": "Колода успешно обновлена"},
        400: {"description": "Некорректное обновление (циклическая ссылка)"},
        401: {"description": "Не аутентифицирован"},
        404: {"description": "Колода не найдена"},
    },
)
async def update_deck(
    deck_id: Annotated[UUID, Path(description="Уникальный идентификатор колоды")],
    data: DeckUpdate,
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
) -> DeckResponse:
    """Обновить колоду.

    Частичное обновление данных колоды. Можно изменить название, описание
    или родительскую колоду. Передаются только те поля, которые необходимо изменить.

    Args:
        deck_id: Уникальный идентификатор колоды
        data: Данные для обновления
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод

    Returns:
        DeckResponse: Обновлённая колода

    Raises:
        HTTPException: 404 если колода не найдена
        HTTPException: 400 если изменение создаёт циклическую ссылку

    """
    try:
        deck = await service.update(
            deck_id=deck_id,
            user_id=user_id,
            data=data,
            updated_by=str(user_id),
        )
        response = DeckResponse.model_validate(deck)
        card_counts = await service.get_card_counts([deck_id])
        response.card_count = card_counts.get(deck_id, 0)
        return response
    except DeckNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {e.deck_id}",
        ) from e
    except DeckCircularReferenceError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set parent: would create circular reference",
        )


@router.delete(
    "/{deck_id}",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Удалить колоду",
    responses={
        200: {"description": "Колода успешно удалена"},
        401: {"description": "Не аутентифицирован"},
        404: {"description": "Колода не найдена"},
    },
)
async def delete_deck(
    deck_id: Annotated[UUID, Path(description="Уникальный идентификатор колоды")],
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
    hard: Annotated[
        bool,
        Query(description="Удалить безвозвратно (по умолчанию: мягкое удаление)"),
    ] = False,
) -> SuccessResponse:
    """Удалить колоду.

    По умолчанию выполняет мягкое удаление. Используйте hard=True для безвозвратного
    удаления. Дочерние колоды также будут удалены.

    Args:
        deck_id: Уникальный идентификатор колоды
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод
        hard: Безвозвратное удаление

    Returns:
        SuccessResponse: Подтверждение успешного удаления

    Raises:
        HTTPException: 404 если колода не найдена

    """
    try:
        await service.delete(
            deck_id=deck_id,
            user_id=user_id,
            hard_delete=hard,
        )
        return SuccessResponse(
            message=f"Deck {'permanently deleted' if hard else 'deleted'} successfully"
        )
    except DeckNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {e.deck_id}",
        ) from e


@router.post(
    "/{deck_id}/restore",
    response_model=DeckResponse,
    status_code=status.HTTP_200_OK,
    summary="Восстановить удалённую колоду",
    responses={
        200: {"description": "Колода успешно восстановлена"},
        401: {"description": "Не аутентифицирован"},
        404: {"description": "Колода не найдена"},
    },
)
async def restore_deck(
    deck_id: Annotated[UUID, Path(description="Уникальный идентификатор колоды")],
    user_id: CurrentUserId,
    service: Annotated[DeckService, Depends(get_deck_service)],
) -> DeckResponse:
    """Восстановить мягко удалённую колоду.

    Восстанавливает ранее удалённую колоду из корзины. Работает только
    с мягко удалёнными колодами, безвозвратно удалённые восстановить невозможно.

    Args:
        deck_id: Уникальный идентификатор колоды
        user_id: Идентификатор аутентифицированного пользователя
        service: Сервис колод

    Returns:
        DeckResponse: Восстановленная колода

    Raises:
        HTTPException: 404 если колода не найдена

    """
    try:
        deck = await service.restore(deck_id, user_id)
        response = DeckResponse.model_validate(deck)
        card_counts = await service.get_card_counts([deck_id])
        response.card_count = card_counts.get(deck_id, 0)
        return response
    except DeckNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deck not found: {e.deck_id}",
        ) from e
