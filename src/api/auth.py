"""FastAPI роутер для эндпоинтов аутентификации."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.auth.schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from src.modules.auth.service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenRevokedError,
    UserInactiveError,
)
from src.modules.users.service import UserAlreadyExistsError

router = APIRouter(prefix="/auth", tags=["Авторизация"])


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    """Получить экземпляр сервиса аутентификации.

    Args:
        session: Асинхронная сессия базы данных

    Returns:
        AuthService: Экземпляр сервиса аутентификации

    """
    return AuthService(session)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(
    request: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Зарегистрировать новую учётную запись пользователя.

    Создаёт нового пользователя с указанными email, паролем и отображаемым именем.
    При успешной регистрации возвращает токены аутентификации для немедленного
    входа в систему.

    Args:
        request: Данные регистрации, включающие email, пароль и отображаемое имя
        auth_service: Сервис аутентификации

    Returns:
        TokenResponse: Токены доступа и обновления

    Raises:
        HTTPException: 409 если email уже зарегистрирован

    """
    try:
        return await auth_service.register(request)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Вход в систему",
)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Аутентифицировать пользователя и получить токены.

    Проверяет учётные данные пользователя и возвращает токены аутентификации.
    Access-токен используется для доступа к защищённым ресурсам, refresh-токен
    для получения новых токенов без повторного ввода пароля.

    Args:
        request: Учётные данные для входа (email и пароль)
        auth_service: Сервис аутентификации

    Returns:
        TokenResponse: Токены доступа и обновления

    Raises:
        HTTPException: 401 если учётные данные недействительны
        HTTPException: 403 если учётная запись пользователя неактивна

    """
    try:
        return await auth_service.login(request)
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновление токенов",
)
async def refresh_token(
    request: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Обновить токены аутентификации.

    Обменивает действительный refresh-токен на новую пару access и refresh токенов.
    Старый refresh-токен отзывается после успешного обновления для предотвращения
    повторного использования.

    Args:
        request: Запрос с refresh-токеном
        auth_service: Сервис аутентификации

    Returns:
        TokenResponse: Новые токены доступа и обновления

    Raises:
        HTTPException: 401 если refresh-токен недействителен или истёк
        HTTPException: 403 если учётная запись пользователя неактивна

    """
    try:
        return await auth_service.refresh_token(request.refresh_token)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except TokenRevokedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Выход из системы",
)
async def logout(
    request: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    """Выйти из системы путём отзыва refresh-токена.

    Инвалидирует предоставленный refresh-токен. Access-токен останется действительным
    до истечения срока его действия, но новые токены с отозванным refresh-токеном
    получить будет невозможно.

    Args:
        request: Refresh-токен для отзыва
        auth_service: Сервис аутентификации

    Returns:
        MessageResponse: Сообщение об успешном выходе

    """
    await auth_service.logout(request.refresh_token)
    return MessageResponse(message="Successfully logged out")
