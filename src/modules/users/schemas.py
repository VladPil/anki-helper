"""Схемы Pydantic для пользовательских эндпоинтов."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Базовая схема данных пользователя."""

    email: EmailStr = Field(
        ...,
        description="Email пользователя для входа в систему",
        examples=["user@example.com"],
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Отображаемое имя пользователя",
        examples=["Иван Петров"],
    )


class UserCreate(UserBase):
    """Схема для создания нового пользователя."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Пароль пользователя (будет захеширован)",
    )


class UserUpdate(BaseModel):
    """Схема для обновления данных пользователя.

    Все поля опциональны - обновляются только переданные поля.
    """

    email: EmailStr | None = Field(
        default=None,
        description="Новый email пользователя",
        examples=["newemail@example.com"],
    )
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Новое отображаемое имя",
    )
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Новый пароль (будет захеширован)",
    )


class UserPreferencesBase(BaseModel):
    """Базовая схема настроек пользователя."""

    preferred_language: str = Field(
        default="ru",
        max_length=10,
        description="Предпочитаемый язык интерфейса",
        examples=["ru", "en"],
    )
    default_model_id: UUID | None = Field(
        default=None,
        description="ID модели LLM по умолчанию",
    )
    default_embedder_id: UUID | None = Field(
        default=None,
        description="ID модели эмбеддинга по умолчанию",
    )


class UserPreferencesCreate(UserPreferencesBase):
    """Схема для создания настроек пользователя."""

    pass


class UserPreferencesUpdate(BaseModel):
    """Схема для обновления настроек пользователя.

    Все поля опциональны - обновляются только переданные поля.
    """

    preferred_language: str | None = Field(
        default=None,
        max_length=10,
        description="Новый предпочитаемый язык",
    )
    default_model_id: UUID | None = Field(
        default=None,
        description="Новый ID модели LLM по умолчанию",
    )
    default_embedder_id: UUID | None = Field(
        default=None,
        description="Новый ID модели эмбеддинга по умолчанию",
    )


class UserPreferencesResponse(UserPreferencesBase):
    """Схема ответа с настройками пользователя."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(
        ...,
        description="Уникальный идентификатор записи настроек",
    )
    user_id: UUID = Field(
        ...,
        description="ID пользователя, которому принадлежат настройки",
    )
    created_at: datetime = Field(
        ...,
        description="Дата и время создания записи",
    )
    updated_at: datetime = Field(
        ...,
        description="Дата и время последнего обновления",
    )


class UserResponse(BaseModel):
    """Схема ответа с данными пользователя."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(
        ...,
        description="Уникальный идентификатор пользователя",
    )
    email: str = Field(
        ...,
        description="Email пользователя",
    )
    display_name: str = Field(
        ...,
        description="Отображаемое имя пользователя",
    )
    is_active: bool = Field(
        ...,
        description="Активен ли аккаунт пользователя",
    )
    created_at: datetime = Field(
        ...,
        description="Дата и время регистрации",
    )
    updated_at: datetime = Field(
        ...,
        description="Дата и время последнего обновления профиля",
    )
    preferences: UserPreferencesResponse | None = Field(
        default=None,
        description="Настройки пользователя (если загружены)",
    )


class UserListResponse(BaseModel):
    """Схема ответа со списком пользователей с пагинацией."""

    items: list[UserResponse] = Field(
        ...,
        description="Список пользователей",
    )
    total: int = Field(
        ...,
        description="Общее количество пользователей",
    )
    page: int = Field(
        ...,
        description="Текущий номер страницы",
    )
    per_page: int = Field(
        ...,
        description="Количество элементов на странице",
    )
