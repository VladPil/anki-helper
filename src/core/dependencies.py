"""
FastAPI зависимости (dependencies).
"""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import db_manager
from .exceptions import (
    AuthenticationError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
)
from .security import TokenPayload, verify_access_token

# ==================== Security Scheme ====================

_bearer_scheme = HTTPBearer(auto_error=False)


# ==================== Database Dependency ====================


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения сессии базы данных.

    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy.
    """
    async for session in db_manager.get_session():
        yield session


DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


# ==================== Redis Dependency ====================


class RedisManager:
    """Менеджер Redis соединений."""

    _client: Redis | None = None

    @classmethod
    async def get_client(cls) -> Redis:
        """Получить клиент Redis."""
        if cls._client is None:
            cls._client = Redis.from_url(
                settings.redis.url,
                encoding="utf-8",
                decode_responses=True,
            )
        return cls._client

    @classmethod
    async def close(cls) -> None:
        """Закрыть соединение с Redis."""
        if cls._client is not None:
            await cls._client.close()
            cls._client = None


async def get_redis() -> AsyncGenerator[Redis, None]:
    """
    Dependency для получения клиента Redis.

    Yields:
        Redis: Асинхронный клиент Redis.
    """
    client = await RedisManager.get_client()
    yield client


RedisClient = Annotated[Redis, Depends(get_redis)]


# ==================== Token Blacklist ====================


class TokenBlacklist:
    """Сервис для работы с черным списком токенов."""

    PREFIX = "token:blacklist:"
    DEFAULT_TTL = 60 * 60 * 24 * 7  # 7 дней

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def add(self, jti: str, ttl: int | None = None) -> None:
        """Добавить токен в черный список."""
        key = f"{self.PREFIX}{jti}"
        await self._redis.setex(key, ttl or self.DEFAULT_TTL, "1")

    async def is_blacklisted(self, jti: str) -> bool:
        """Проверить, находится ли токен в черном списке."""
        key = f"{self.PREFIX}{jti}"
        return await self._redis.exists(key) > 0

    async def remove(self, jti: str) -> None:
        """Удалить токен из черного списка."""
        key = f"{self.PREFIX}{jti}"
        await self._redis.delete(key)


async def get_token_blacklist(
    redis: RedisClient,
) -> TokenBlacklist:
    """Dependency для получения сервиса черного списка токенов."""
    return TokenBlacklist(redis)


TokenBlacklistService = Annotated[TokenBlacklist, Depends(get_token_blacklist)]


# ==================== Authentication Dependencies ====================


async def get_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    authorization: str | None = Header(None, alias="Authorization"),
) -> str:
    """
    Извлечь токен из заголовка Authorization.

    Args:
        credentials: Credentials из HTTPBearer.
        authorization: Заголовок Authorization напрямую.

    Returns:
        Токен без префикса "Bearer ".

    Raises:
        AuthenticationError: Токен не предоставлен.
    """
    if credentials is not None:
        return credentials.credentials

    if authorization is not None:
        if authorization.lower().startswith("bearer "):
            return authorization[7:]
        return authorization

    raise AuthenticationError("Authorization header is required")


async def get_token_payload(
    token: str = Depends(get_token),
) -> TokenPayload:
    """
    Получить и валидировать payload токена.

    Args:
        token: JWT токен.

    Returns:
        Payload токена.

    Raises:
        TokenExpiredError: Токен истек.
        TokenInvalidError: Токен невалиден.
    """
    return verify_access_token(token)


async def get_current_user_id(
    payload: TokenPayload = Depends(get_token_payload),
    blacklist: TokenBlacklistService = None,  # type: ignore[assignment]
) -> UUID:
    """
    Получить ID текущего пользователя из токена.

    Args:
        payload: Payload токена.
        blacklist: Сервис черного списка токенов.

    Returns:
        UUID пользователя.

    Raises:
        TokenRevokedError: Токен отозван.
    """
    # Проверяем черный список, если есть jti
    if blacklist is not None and payload.jti:
        if await blacklist.is_blacklisted(payload.jti):
            raise TokenRevokedError()

    return UUID(payload.sub)


CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]


# ==================== Optional Authentication ====================


async def get_optional_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    authorization: str | None = Header(None, alias="Authorization"),
) -> str | None:
    """
    Опционально извлечь токен из заголовка Authorization.

    Returns:
        Токен или None.
    """
    try:
        return await get_token(credentials, authorization)
    except AuthenticationError:
        return None


async def get_optional_user_id(
    token: str | None = Depends(get_optional_token),
) -> UUID | None:
    """
    Опционально получить ID пользователя.

    Returns:
        UUID пользователя или None.
    """
    if token is None:
        return None

    try:
        payload = verify_access_token(token)
        return UUID(payload.sub)
    except (TokenExpiredError, TokenInvalidError):
        return None


OptionalUserId = Annotated[UUID | None, Depends(get_optional_user_id)]


# ==================== Request Context ====================


async def get_request_id(request: Request) -> str:
    """
    Получить ID запроса из заголовков или state.

    Args:
        request: FastAPI Request.

    Returns:
        ID запроса.
    """
    # Сначала проверяем state (устанавливается middleware)
    if hasattr(request.state, "request_id"):
        return request.state.request_id

    # Затем проверяем заголовки
    request_id = request.headers.get("X-Request-ID")
    if request_id:
        return request_id

    # Генерируем новый
    import uuid

    return str(uuid.uuid4())


RequestId = Annotated[str, Depends(get_request_id)]


# ==================== Pagination ====================


class PaginationParams:
    """Параметры пагинации."""

    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> None:
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)  # Максимум 100

    @property
    def offset(self) -> int:
        """Смещение для SQL запроса."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Лимит для SQL запроса."""
        return self.page_size


Pagination = Annotated[PaginationParams, Depends()]


# ==================== Lifecycle ====================


async def init_dependencies() -> None:
    """Инициализировать зависимости при старте приложения."""
    # Redis инициализируется лениво при первом запросе
    pass


async def close_dependencies() -> None:
    """Закрыть зависимости при остановке приложения."""
    await RedisManager.close()
