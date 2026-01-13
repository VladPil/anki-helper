"""FastAPI роутер для эндпоинтов шаблонов карточек."""

import logging
import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.templates.schemas import (
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from src.modules.templates.service import (
    SystemTemplateModificationError,
    TemplateNameExistsError,
    TemplateNotFoundError,
    TemplateService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["Шаблоны"])


def get_template_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TemplateService:
    """Получить экземпляр сервиса шаблонов.

    Args:
        session: Асинхронная сессия базы данных.

    Returns:
        Экземпляр TemplateService для работы с шаблонами.
    """
    return TemplateService(session)


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый шаблон карточки",
)
async def create_template(
    data: TemplateCreate,
    service: Annotated[TemplateService, Depends(get_template_service)],
    owner_id: Annotated[
        UUID | None,
        Query(description="ID пользователя-владельца шаблона"),
    ] = None,
) -> TemplateResponse:
    """Создать новый шаблон карточки.

    Создает пользовательский шаблон для генерации Anki-карточек.
    Шаблон определяет структуру полей и форматирование карточек.

    Args:
        data: Данные для создания шаблона.
        service: Экземпляр сервиса шаблонов.
        owner_id: Опциональный ID владельца шаблона.

    Returns:
        Созданный шаблон.

    Raises:
        HTTPException: 409 если шаблон с таким именем уже существует.
    """
    try:
        template = await service.create(data, owner_id=owner_id)
        return TemplateResponse.model_validate(template)
    except TemplateNameExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.get(
    "",
    response_model=TemplateListResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить список шаблонов",
)
async def list_templates(
    service: Annotated[TemplateService, Depends(get_template_service)],
    owner_id: Annotated[
        UUID | None,
        Query(description="Фильтр по ID владельца"),
    ] = None,
    include_system: Annotated[
        bool,
        Query(description="Включить системные шаблоны в результат"),
    ] = True,
    page: Annotated[
        int,
        Query(ge=1, description="Номер страницы (начиная с 1)"),
    ] = 1,
    size: Annotated[
        int,
        Query(ge=1, le=100, description="Количество элементов на странице"),
    ] = 20,
) -> TemplateListResponse:
    """Получить пагинированный список шаблонов.

    Возвращает список доступных шаблонов карточек с возможностью
    фильтрации по владельцу и включения/исключения системных шаблонов.

    Args:
        service: Экземпляр сервиса шаблонов.
        owner_id: Опциональный фильтр по ID владельца.
        include_system: Флаг включения системных шаблонов.
        page: Номер страницы (начиная с 1).
        size: Количество элементов на странице.

    Returns:
        Пагинированный список шаблонов.
    """
    templates, total = await service.get_list(
        owner_id=owner_id,
        include_system=include_system,
        page=page,
        size=size,
    )

    return TemplateListResponse(
        items=[TemplateResponse.model_validate(t) for t in templates],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить шаблон по ID",
)
async def get_template(
    template_id: Annotated[UUID, Path(description="Уникальный идентификатор шаблона")],
    service: Annotated[TemplateService, Depends(get_template_service)],
    owner_id: Annotated[
        UUID | None,
        Query(description="ID владельца для проверки доступа"),
    ] = None,
) -> TemplateResponse:
    """Получить шаблон по идентификатору.

    Возвращает детальную информацию о шаблоне, включая структуру
    полей и настройки форматирования.

    Args:
        template_id: UUID шаблона.
        service: Экземпляр сервиса шаблонов.
        owner_id: Опциональный ID владельца для контроля доступа.

    Returns:
        Запрошенный шаблон.

    Raises:
        HTTPException: 404 если шаблон не найден.
    """
    try:
        template = await service.get_by_id(template_id, owner_id=owner_id)
        return TemplateResponse.model_validate(template)
    except TemplateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/{template_id}",
    response_model=TemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить шаблон карточки",
)
async def update_template(
    template_id: Annotated[UUID, Path(description="Уникальный идентификатор шаблона")],
    data: TemplateUpdate,
    service: Annotated[TemplateService, Depends(get_template_service)],
    owner_id: Annotated[
        UUID | None,
        Query(description="ID владельца для проверки доступа"),
    ] = None,
) -> TemplateResponse:
    """Обновить шаблон карточки.

    Обновляет существующий шаблон карточки. Системные шаблоны
    не могут быть изменены.

    Args:
        template_id: UUID шаблона для обновления.
        data: Данные для обновления шаблона.
        service: Экземпляр сервиса шаблонов.
        owner_id: Опциональный ID владельца для контроля доступа.

    Returns:
        Обновленный шаблон.

    Raises:
        HTTPException: 404 если шаблон не найден.
        HTTPException: 403 при попытке изменить системный шаблон.
        HTTPException: 409 если новое имя уже занято.
    """
    try:
        template = await service.update(template_id, data, owner_id=owner_id)
        return TemplateResponse.model_validate(template)
    except TemplateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except SystemTemplateModificationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except TemplateNameExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить шаблон карточки",
)
async def delete_template(
    template_id: Annotated[UUID, Path(description="Уникальный идентификатор шаблона")],
    service: Annotated[TemplateService, Depends(get_template_service)],
    owner_id: Annotated[
        UUID | None,
        Query(description="ID владельца для проверки доступа"),
    ] = None,
) -> None:
    """Удалить шаблон карточки.

    Удаляет пользовательский шаблон карточки. Системные шаблоны
    не могут быть удалены.

    Args:
        template_id: UUID шаблона для удаления.
        service: Экземпляр сервиса шаблонов.
        owner_id: Опциональный ID владельца для контроля доступа.

    Raises:
        HTTPException: 404 если шаблон не найден.
        HTTPException: 403 при попытке удалить системный шаблон.
    """
    try:
        await service.delete(template_id, owner_id=owner_id)
    except TemplateNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except SystemTemplateModificationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
