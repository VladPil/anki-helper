"""
Безопасность: хеширование паролей и работа с JWT токенами.
"""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from .config import settings
from .exceptions import (
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
)


class TokenType(StrEnum):
    """Типы JWT токенов."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    """Payload JWT токена."""

    sub: str  # user_id
    type: TokenType
    exp: datetime
    iat: datetime
    jti: str | None = None  # JWT ID для отзыва токенов


class TokenPair(BaseModel):
    """Пара access и refresh токенов."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # секунды до истечения access токена


# Контекст для хеширования паролей
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    """
    Захешировать пароль с использованием bcrypt.

    Args:
        password: Пароль в открытом виде.

    Returns:
        Хеш пароля.
    """
    return _pwd_context.hash(password)  # type: ignore[no-any-return]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверить соответствие пароля хешу.

    Args:
        plain_password: Пароль в открытом виде.
        hashed_password: Хеш пароля.

    Returns:
        True если пароль верный, False иначе.
    """
    return _pwd_context.verify(plain_password, hashed_password)  # type: ignore[no-any-return]


def needs_rehash(hashed_password: str) -> bool:
    """
    Проверить, нужно ли перехешировать пароль.

    Может понадобиться при обновлении алгоритма или параметров.

    Args:
        hashed_password: Текущий хеш пароля.

    Returns:
        True если нужен рехеш.
    """
    return _pwd_context.needs_update(hashed_password)  # type: ignore[no-any-return]


def create_token(
    user_id: UUID | str,
    token_type: TokenType,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
    jti: str | None = None,
) -> str:
    """
    Создать JWT токен.

    Args:
        user_id: ID пользователя.
        token_type: Тип токена (access/refresh).
        expires_delta: Время жизни токена.
        additional_claims: Дополнительные claims.
        jti: Уникальный ID токена для отзыва.

    Returns:
        Закодированный JWT токен.
    """
    now = datetime.now(UTC)

    if expires_delta is None:
        if token_type == TokenType.ACCESS:
            expires_delta = timedelta(minutes=settings.jwt.access_token_expire_minutes)
        else:
            expires_delta = timedelta(days=settings.jwt.refresh_token_expire_days)

    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type.value,
        "exp": expire,
        "iat": now,
    }

    if jti:
        payload["jti"] = jti

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm,
    )


def create_access_token(
    user_id: UUID | str,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    """
    Создать access токен.

    Args:
        user_id: ID пользователя.
        additional_claims: Дополнительные claims.

    Returns:
        Закодированный access токен.
    """
    return create_token(
        user_id=user_id,
        token_type=TokenType.ACCESS,
        additional_claims=additional_claims,
    )


def create_refresh_token(
    user_id: UUID | str,
    jti: str | None = None,
) -> str:
    """
    Создать refresh токен.

    Args:
        user_id: ID пользователя.
        jti: Уникальный ID для отзыва токена.

    Returns:
        Закодированный refresh токен.
    """
    return create_token(
        user_id=user_id,
        token_type=TokenType.REFRESH,
        jti=jti,
    )


def create_token_pair(
    user_id: UUID | str,
    additional_claims: dict[str, Any] | None = None,
    refresh_jti: str | None = None,
) -> TokenPair:
    """
    Создать пару access и refresh токенов.

    Args:
        user_id: ID пользователя.
        additional_claims: Дополнительные claims для access токена.
        refresh_jti: Уникальный ID для refresh токена.

    Returns:
        Пара токенов.
    """
    access_token = create_access_token(
        user_id=user_id,
        additional_claims=additional_claims,
    )

    refresh_token = create_refresh_token(
        user_id=user_id,
        jti=refresh_jti,
    )

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt.access_token_expire_minutes * 60,
    )


def decode_token(token: str, verify_exp: bool = True) -> TokenPayload:
    """
    Декодировать и валидировать JWT токен.

    Args:
        token: Закодированный JWT токен.
        verify_exp: Проверять ли срок действия.

    Returns:
        Payload токена.

    Raises:
        TokenExpiredError: Токен истек.
        TokenInvalidError: Токен невалиден.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm],
            options={"verify_exp": verify_exp},
        )

        return TokenPayload(
            sub=payload["sub"],
            type=TokenType(payload["type"]),
            exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
            iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
            jti=payload.get("jti"),
        )

    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError() from e
    except jwt.InvalidTokenError as e:
        raise TokenInvalidError() from e


def verify_access_token(token: str) -> TokenPayload:
    """
    Проверить access токен.

    Args:
        token: Закодированный JWT токен.

    Returns:
        Payload токена.

    Raises:
        TokenInvalidError: Токен не является access токеном.
    """
    payload = decode_token(token)

    if payload.type != TokenType.ACCESS:
        raise TokenInvalidError("Expected access token")

    return payload


def verify_refresh_token(token: str) -> TokenPayload:
    """
    Проверить refresh токен.

    Args:
        token: Закодированный JWT токен.

    Returns:
        Payload токена.

    Raises:
        TokenInvalidError: Токен не является refresh токеном.
    """
    payload = decode_token(token)

    if payload.type != TokenType.REFRESH:
        raise TokenInvalidError("Expected refresh token")

    return payload


def extract_user_id(token: str) -> UUID:
    """
    Извлечь user_id из токена.

    Args:
        token: Закодированный JWT токен.

    Returns:
        UUID пользователя.
    """
    payload = decode_token(token)
    return UUID(payload.sub)


def authenticate_user(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Аутентифицировать пользователя по паролю.

    Args:
        plain_password: Пароль в открытом виде.
        hashed_password: Хеш пароля из БД.

    Returns:
        True если аутентификация успешна.

    Raises:
        InvalidCredentialsError: Неверный пароль.
    """
    if not verify_password(plain_password, hashed_password):
        raise InvalidCredentialsError()
    return True
