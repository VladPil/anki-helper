"""
Сервис управления пользователями.

Этот модуль предоставляет CRUD-операции для пользователей и их настроек.

Основные компоненты:
    - UserService: бизнес-логика управления пользователями
    - UserServiceError: базовое исключение для ошибок сервиса
    - UserNotFoundError: пользователь не найден
    - UserAlreadyExistsError: пользователь с таким email уже существует
"""

from uuid import UUID

from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import User, UserPreferences
from .schemas import (
    UserCreate,
    UserPreferencesUpdate,
    UserUpdate,
)


class UserServiceError(Exception):
    """Базовое исключение для ошибок сервиса пользователей."""

    pass


class UserNotFoundError(UserServiceError):
    """Возникает когда пользователь не найден."""

    pass


class UserAlreadyExistsError(UserServiceError):
    """Возникает при попытке создать пользователя с существующим email."""

    pass


class UserService:
    """
    Сервис управления пользователями.

    Предоставляет CRUD-операции для пользователей и их настроек
    с корректным хешированием паролей и обработкой ошибок.

    Attributes:
        pwd_context: Контекст хеширования паролей (bcrypt)
    """

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def __init__(self, session: AsyncSession) -> None:
        """
        Инициализировать сервис пользователей.

        Args:
            session: Асинхронная сессия SQLAlchemy для операций с БД
        """
        self._session = session

    def _hash_password(self, password: str) -> str:
        """
        Хешировать текстовый пароль.

        Args:
            password: Текстовый пароль для хеширования

        Returns:
            Хеш пароля (bcrypt)
        """
        return self.pwd_context.hash(password)  # type: ignore[no-any-return]

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Проверить пароль по его хешу.

        Args:
            plain_password: Текстовый пароль для проверки
            hashed_password: Хеш пароля (bcrypt) для сравнения

        Returns:
            True если пароль совпадает, False в противном случае
        """
        return self.pwd_context.verify(plain_password, hashed_password)  # type: ignore[no-any-return]

    async def get_by_id(self, user_id: UUID) -> User | None:
        """
        Получить пользователя по ID.

        Args:
            user_id: UUID пользователя

        Returns:
            Объект User если найден, None в противном случае
        """
        stmt = (
            select(User)
            .options(selectinload(User.preferences))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """
        Получить пользователя по email.

        Args:
            email: Email пользователя

        Returns:
            Объект User если найден, None в противном случае
        """
        stmt = (
            select(User)
            .options(selectinload(User.preferences))
            .where(User.email == email, User.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user_data: UserCreate) -> User:
        """
        Создать нового пользователя.

        Args:
            user_data: Данные для создания пользователя (email, имя, пароль)

        Returns:
            Созданный объект User

        Raises:
            UserAlreadyExistsError: Пользователь с таким email уже существует
        """
        # Check if user with this email already exists
        existing_user = await self.get_by_email(user_data.email)
        if existing_user is not None:
            raise UserAlreadyExistsError(f"User with email {user_data.email} already exists")

        # Create new user
        user = User(
            email=user_data.email,
            display_name=user_data.display_name,
            hashed_password=self._hash_password(user_data.password),
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()

        # Create default preferences
        preferences = UserPreferences(
            user_id=user.id,
            preferred_language="ru",
        )
        self._session.add(preferences)
        await self._session.flush()

        # Refresh to get relationships
        await self._session.refresh(user, ["preferences"])
        return user

    async def update(self, user_id: UUID, user_data: UserUpdate) -> User:
        """
        Обновить существующего пользователя.

        Args:
            user_id: UUID пользователя
            user_data: Данные для обновления (опциональные поля)

        Returns:
            Обновленный объект User

        Raises:
            UserNotFoundError: Пользователь не существует
            UserAlreadyExistsError: Email уже используется другим пользователем
        """
        user = await self.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        # Check email uniqueness if updating email
        if user_data.email is not None and user_data.email != user.email:
            existing_user = await self.get_by_email(user_data.email)
            if existing_user is not None:
                raise UserAlreadyExistsError(f"User with email {user_data.email} already exists")
            user.email = user_data.email

        if user_data.display_name is not None:
            user.display_name = user_data.display_name

        if user_data.password is not None:
            user.hashed_password = self._hash_password(user_data.password)

        await self._session.flush()
        await self._session.refresh(user, ["preferences"])
        return user

    async def delete(self, user_id: UUID) -> None:
        """
        Мягко удалить пользователя.

        Args:
            user_id: UUID пользователя

        Raises:
            UserNotFoundError: Пользователь не существует
        """
        user = await self.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        user.soft_delete()
        await self._session.flush()

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
        include_inactive: bool = False,
    ) -> tuple[list[User], int]:
        """
        Получить список пользователей с пагинацией.

        Args:
            page: Номер страницы (начиная с 1)
            per_page: Количество элементов на странице
            include_inactive: Включать ли неактивных пользователей

        Returns:
            Кортеж (список пользователей, общее количество)
        """
        # Build base query
        base_query = select(User).where(User.deleted_at.is_(None))
        if not include_inactive:
            base_query = base_query.where(User.is_active.is_(True))

        # Get total count
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = await self._session.scalar(count_stmt) or 0

        # Get paginated results
        stmt = (
            base_query.options(selectinload(User.preferences))
            .order_by(User.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self._session.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def deactivate(self, user_id: UUID) -> User:
        """
        Деактивировать аккаунт пользователя.

        Args:
            user_id: UUID пользователя

        Returns:
            Обновленный объект User

        Raises:
            UserNotFoundError: Пользователь не существует
        """
        user = await self.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        user.is_active = False
        await self._session.flush()
        await self._session.refresh(user, ["preferences"])
        return user

    async def activate(self, user_id: UUID) -> User:
        """
        Активировать аккаунт пользователя.

        Args:
            user_id: UUID пользователя

        Returns:
            Обновленный объект User

        Raises:
            UserNotFoundError: Пользователь не существует
        """
        user = await self.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        user.is_active = True
        await self._session.flush()
        await self._session.refresh(user, ["preferences"])
        return user

    async def update_preferences(
        self,
        user_id: UUID,
        preferences_data: UserPreferencesUpdate,
    ) -> UserPreferences:
        """
        Обновить настройки пользователя.

        Args:
            user_id: UUID пользователя
            preferences_data: Данные для обновления настроек

        Returns:
            Обновленный объект UserPreferences

        Raises:
            UserNotFoundError: Пользователь не существует
        """
        user = await self.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(f"User with ID {user_id} not found")

        preferences = user.preferences
        if preferences is None:
            # Create preferences if they don't exist
            preferences = UserPreferences(
                user_id=user_id,
                preferred_language=preferences_data.preferred_language or "ru",
                default_model_id=preferences_data.default_model_id,
                default_embedder_id=preferences_data.default_embedder_id,
            )
            self._session.add(preferences)
        else:
            if preferences_data.preferred_language is not None:
                preferences.preferred_language = preferences_data.preferred_language
            if preferences_data.default_model_id is not None:
                preferences.default_model_id = preferences_data.default_model_id
            if preferences_data.default_embedder_id is not None:
                preferences.default_embedder_id = preferences_data.default_embedder_id

        await self._session.flush()
        await self._session.refresh(preferences)
        return preferences

    async def authenticate(self, email: str, password: str) -> User | None:
        """
        Аутентифицировать пользователя по email и паролю.

        Args:
            email: Email пользователя
            password: Текстовый пароль

        Returns:
            Объект User при успешной аутентификации, None в противном случае
        """
        user = await self.get_by_email(email)
        if user is None:
            return None

        if not user.is_active:
            return None

        if not self.verify_password(password, user.hashed_password):
            return None

        return user
