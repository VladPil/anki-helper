"""FastAPI роутер для эндпоинтов пользователей."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.auth.dependencies import get_current_active_user, require_admin
from src.modules.users.models import User
from src.modules.users.schemas import (
    UserListResponse,
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserResponse,
    UserUpdate,
)
from src.modules.users.service import UserAlreadyExistsError, UserNotFoundError, UserService

router = APIRouter(prefix="/users", tags=["Пользователи"])


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserService:
    """Получить экземпляр сервиса пользователей.

    Args:
        session: Асинхронная сессия базы данных

    Returns:
        UserService: Экземпляр сервиса пользователей

    """
    return UserService(session)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить профиль текущего пользователя",
)
async def get_current_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Получить профиль текущего аутентифицированного пользователя.

    Возвращает профиль пользователя, включая его настройки и предпочтения.
    Требует действительного access-токена.

    Args:
        current_user: Текущий аутентифицированный пользователь

    Returns:
        User: Профиль пользователя с предпочтениями

    """
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить профиль текущего пользователя",
)
async def update_current_user(
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Обновить профиль текущего аутентифицированного пользователя.

    Позволяет обновить email, отображаемое имя и пароль. Все поля являются
    необязательными - обновляются только переданные поля.

    Args:
        user_data: Данные для обновления профиля
        current_user: Текущий аутентифицированный пользователь
        user_service: Сервис пользователей

    Returns:
        User: Обновлённый профиль пользователя

    Raises:
        HTTPException: 409 если указанный email уже занят другим пользователем

    """
    try:
        return await user_service.update(current_user.id, user_data)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.patch(
    "/me/preferences",
    response_model=UserPreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить настройки текущего пользователя",
)
async def update_current_user_preferences(
    preferences_data: UserPreferencesUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserPreferencesResponse:
    """Обновить настройки текущего аутентифицированного пользователя.

    Позволяет обновить предпочитаемый язык и настройки модели по умолчанию.
    Все поля являются необязательными - обновляются только переданные поля.

    Args:
        preferences_data: Данные настроек для обновления
        current_user: Текущий аутентифицированный пользователь
        user_service: Сервис пользователей

    Returns:
        UserPreferencesResponse: Обновлённые настройки пользователя

    """
    preferences = await user_service.update_preferences(current_user.id, preferences_data)
    return UserPreferencesResponse.model_validate(preferences)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить пользователя по ID",
    dependencies=[Depends(require_admin)],
)
async def get_user_by_id(
    user_id: Annotated[UUID, Path(description="Уникальный идентификатор пользователя")],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Получить пользователя по его ID (только для администраторов).

    Возвращает профиль пользователя по его уникальному идентификатору.
    Доступно только администраторам системы.

    Args:
        user_id: Уникальный идентификатор пользователя
        user_service: Сервис пользователей

    Returns:
        User: Профиль запрашиваемого пользователя

    Raises:
        HTTPException: 404 если пользователь не найден

    """
    user = await user_service.get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )
    return user


@router.get(
    "/",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить список пользователей",
    dependencies=[Depends(require_admin)],
)
async def list_users(
    user_service: Annotated[UserService, Depends(get_user_service)],
    page: Annotated[int, Query(ge=1, description="Номер страницы")] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, description="Элементов на странице")] = 20,
    include_inactive: Annotated[bool, Query(description="Включить неактивных")] = False,
) -> UserListResponse:
    """Получить список всех пользователей с пагинацией (только для администраторов).

    Возвращает постраничный список пользователей системы. Доступно только
    администраторам. Поддерживает фильтрацию по статусу активности.

    Args:
        user_service: Сервис пользователей
        page: Номер страницы (начиная с 1)
        per_page: Количество элементов на странице (от 1 до 100)
        include_inactive: Включить неактивных пользователей в выборку

    Returns:
        UserListResponse: Список пользователей с метаданными пагинации

    """
    users, total = await user_service.list_users(
        page=page,
        per_page=per_page,
        include_inactive=include_inactive,
    )
    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Деактивировать пользователя",
    dependencies=[Depends(require_admin)],
)
async def deactivate_user(
    user_id: Annotated[UUID, Path(description="Уникальный идентификатор пользователя")],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Деактивировать учётную запись пользователя (только для администраторов).

    Деактивированные пользователи не могут входить в систему или использовать
    приложение. Данные пользователя сохраняются и могут быть восстановлены.

    Args:
        user_id: Уникальный идентификатор пользователя
        user_service: Сервис пользователей

    Returns:
        User: Деактивированный профиль пользователя

    Raises:
        HTTPException: 404 если пользователь не найден

    """
    try:
        return await user_service.deactivate(user_id)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Активировать пользователя",
    dependencies=[Depends(require_admin)],
)
async def activate_user(
    user_id: Annotated[UUID, Path(description="Уникальный идентификатор пользователя")],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Активировать учётную запись пользователя (только для администраторов).

    Восстанавливает доступ для ранее деактивированной учётной записи.
    Пользователь снова сможет входить в систему.

    Args:
        user_id: Уникальный идентификатор пользователя
        user_service: Сервис пользователей

    Returns:
        User: Активированный профиль пользователя

    Raises:
        HTTPException: 404 если пользователь не найден

    """
    try:
        return await user_service.activate(user_id)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить пользователя",
    dependencies=[Depends(require_admin)],
)
async def delete_user(
    user_id: Annotated[UUID, Path(description="Уникальный идентификатор пользователя")],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    """Мягко удалить пользователя (только для администраторов).

    Выполняет мягкое удаление пользователя. Пользователь помечается как удалённый,
    но данные сохраняются в базе данных для возможного восстановления или аудита.

    Args:
        user_id: Уникальный идентификатор пользователя
        user_service: Сервис пользователей

    Raises:
        HTTPException: 404 если пользователь не найден

    """
    try:
        await user_service.delete(user_id)
    except UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
