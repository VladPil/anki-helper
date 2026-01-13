"""
Сервис аутентификации пользователей.

Этот модуль отвечает за регистрацию, вход и управление токенами JWT.

Основные компоненты:
    - AuthService: бизнес-логика аутентификации
    - AuthServiceError: базовое исключение для ошибок аутентификации
    - InvalidCredentialsError: неверные учетные данные
    - InvalidTokenError: недействительный или истекший токен
    - TokenRevokedError: отозванный токен
    - UserInactiveError: неактивный аккаунт пользователя
"""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.modules.users.models import User
from src.modules.users.schemas import UserCreate
from src.modules.users.service import UserService

from .models import RefreshToken
from .schemas import LoginRequest, RegisterRequest, TokenResponse


class AuthServiceError(Exception):
    """Базовое исключение для ошибок сервиса аутентификации."""

    pass


class InvalidCredentialsError(AuthServiceError):
    """Возникает при неверных учетных данных для входа."""

    pass


class InvalidTokenError(AuthServiceError):
    """Возникает при недействительном или истекшем токене."""

    pass


class TokenRevokedError(AuthServiceError):
    """Возникает при использовании отозванного токена."""

    pass


class UserInactiveError(AuthServiceError):
    """Возникает при попытке действий с неактивным аккаунтом."""

    pass


class AuthService:
    """
    Сервис аутентификации.

    Обрабатывает регистрацию пользователей, вход, генерацию токенов,
    обновление токенов и выход из системы. Использует JWT для access-токенов
    и хранит refresh-токены в базе данных.

    Attributes:
        algorithm: Алгоритм подписи JWT
        access_token_expire_minutes: Время жизни access-токена в минутах
        refresh_token_expire_days: Время жизни refresh-токена в днях
    """

    algorithm = settings.jwt.algorithm
    access_token_expire_minutes = settings.jwt.access_token_expire_minutes
    refresh_token_expire_days = settings.jwt.refresh_token_expire_days

    def __init__(self, session: AsyncSession) -> None:
        """
        Инициализировать сервис аутентификации.

        Args:
            session: Асинхронная сессия SQLAlchemy для операций с БД
        """
        self._session = session
        self._user_service = UserService(session)

    def _create_access_token(self, user_id: UUID, expires_delta: timedelta | None = None) -> str:
        """
        Создать JWT access-токен.

        Args:
            user_id: UUID пользователя для кодирования в токене
            expires_delta: Опциональное время истечения токена

        Returns:
            Закодированный JWT access-токен
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.access_token_expire_minutes)

        expire = datetime.now(UTC) + expires_delta
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.now(UTC),
            "type": "access",
        }
        return jwt.encode(payload, settings.jwt.secret_key, algorithm=self.algorithm)

    def _create_refresh_token_string(self) -> str:
        """
        Сгенерировать безопасную случайную строку refresh-токена.

        Returns:
            URL-безопасная случайная строка токена
        """
        return secrets.token_urlsafe(64)

    async def _create_refresh_token(self, user_id: UUID) -> RefreshToken:
        """
        Создать и сохранить refresh-токен в базе данных.

        Args:
            user_id: UUID пользователя

        Returns:
            Созданный объект RefreshToken
        """
        token_string = self._create_refresh_token_string()
        expires_at = datetime.now(UTC) + timedelta(days=self.refresh_token_expire_days)

        refresh_token = RefreshToken(
            user_id=user_id,
            token=token_string,
            expires_at=expires_at,
        )
        self._session.add(refresh_token)
        await self._session.flush()
        return refresh_token

    async def register(self, request: RegisterRequest) -> TokenResponse:
        """
        Зарегистрировать нового пользователя и вернуть токены.

        Args:
            request: Данные регистрации, включая email, пароль и отображаемое имя

        Returns:
            TokenResponse с access- и refresh-токенами

        Raises:
            UserAlreadyExistsError: Пользователь с таким email уже существует
        """
        # Create user using UserService
        user_data = UserCreate(
            email=request.email,
            password=request.password,
            display_name=request.display_name,
        )
        user = await self._user_service.create(user_data)

        # Generate tokens
        access_token = self._create_access_token(user.id)
        refresh_token = await self._create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token.token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,
        )

    async def login(self, request: LoginRequest) -> TokenResponse:
        """
        Аутентифицировать пользователя и вернуть токены.

        Args:
            request: Данные входа, включая email и пароль

        Returns:
            TokenResponse с access- и refresh-токенами

        Raises:
            InvalidCredentialsError: Неверный email или пароль
            UserInactiveError: Аккаунт пользователя неактивен
        """
        user = await self._user_service.authenticate(request.email, request.password)
        if user is None:
            raise InvalidCredentialsError("Invalid email or password")

        if not user.is_active:
            raise UserInactiveError("User account is inactive")

        # Generate tokens
        access_token = self._create_access_token(user.id)
        refresh_token = await self._create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token.token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,
        )

    async def refresh_token(self, refresh_token_string: str) -> TokenResponse:
        """
        Обновить access-токен с использованием refresh-токена.

        Старый refresh-токен отзывается и выдается новый.

        Args:
            refresh_token_string: Refresh-токен для обмена

        Returns:
            TokenResponse с новыми access- и refresh-токенами

        Raises:
            InvalidTokenError: Refresh-токен недействителен или истек
            TokenRevokedError: Refresh-токен был отозван
            UserInactiveError: Аккаунт пользователя неактивен
        """
        # Find the refresh token
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token_string)
        result = await self._session.execute(stmt)
        token = result.scalar_one_or_none()

        if token is None:
            raise InvalidTokenError("Invalid refresh token")

        if token.is_revoked:
            raise TokenRevokedError("Refresh token has been revoked")

        if token.is_expired:
            raise InvalidTokenError("Refresh token has expired")

        # Check user is still active
        user = await self._user_service.get_by_id(token.user_id)
        if user is None or not user.is_active:
            raise UserInactiveError("User account is inactive or not found")

        # Revoke old refresh token
        token.revoke()

        # Generate new tokens
        access_token = self._create_access_token(user.id)
        new_refresh_token = await self._create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token.token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,
        )

    async def logout(self, refresh_token_string: str) -> None:
        """
        Выйти из системы, отозвав refresh-токен.

        Args:
            refresh_token_string: Refresh-токен для отзыва
        """
        stmt = select(RefreshToken).where(RefreshToken.token == refresh_token_string)
        result = await self._session.execute(stmt)
        token = result.scalar_one_or_none()

        if token is not None and not token.is_revoked:
            token.revoke()
            await self._session.flush()

    async def logout_all(self, user_id: UUID) -> int:
        """
        Отозвать все refresh-токены пользователя.

        Args:
            user_id: UUID пользователя

        Returns:
            Количество отозванных токенов
        """
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        result = await self._session.execute(stmt)
        tokens = result.scalars().all()

        count = 0
        for token in tokens:
            token.revoke()
            count += 1

        await self._session.flush()
        return count

    def verify_token(self, token: str) -> dict:
        """
        Проверить и декодировать JWT access-токен.

        Args:
            token: JWT access-токен для проверки

        Returns:
            Декодированные данные токена

        Raises:
            InvalidTokenError: Токен недействителен или истек
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt.secret_key,
                algorithms=[self.algorithm],
            )
            if payload.get("type") != "access":
                raise InvalidTokenError("Invalid token type")
            return payload
        except jwt.ExpiredSignatureError as e:
            raise InvalidTokenError("Token has expired") from e
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError("Invalid token") from e

    async def get_user_from_token(self, token: str) -> User:
        """
        Получить пользователя по access-токену.

        Args:
            token: JWT access-токен

        Returns:
            Объект User

        Raises:
            InvalidTokenError: Токен недействителен
            UserInactiveError: Пользователь неактивен или не найден
        """
        payload = self.verify_token(token)
        user_id = UUID(payload["sub"])

        user = await self._user_service.get_by_id(user_id)
        if user is None:
            raise InvalidTokenError("User not found")

        if not user.is_active:
            raise UserInactiveError("User account is inactive")

        return user

    async def cleanup_expired_tokens(self) -> int:
        """
        Удалить истекшие refresh-токены из базы данных.

        Returns:
            Количество удаленных токенов
        """
        stmt = delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC))
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0
