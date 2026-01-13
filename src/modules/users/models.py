"""
Модели SQLAlchemy для пользователей.

Этот модуль содержит модели данных для пользователей и их настроек.

Основные компоненты:
    - User: модель пользователя приложения
    - UserPreferences: настройки пользователя
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.mixins import SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.modules.decks.models import Deck


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Модель пользователя.

    Attributes:
        id: Уникальный идентификатор (UUID7)
        email: Email для входа (уникальный)
        hashed_password: Хеш пароля (bcrypt)
        display_name: Отображаемое имя пользователя
        is_active: Активен ли аккаунт
        created_at: Дата создания (из TimestampMixin)
        updated_at: Дата обновления (из TimestampMixin)
        deleted_at: Дата мягкого удаления (из SoftDeleteMixin)
        decks: Колоды пользователя
        preferences: Настройки пользователя (один-к-одному)
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    decks: Mapped[list[Deck]] = relationship(back_populates="owner", lazy="selectin")
    preferences: Mapped[UserPreferences] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )


class UserPreferences(UUIDMixin, TimestampMixin, Base):
    """
    Модель настроек пользователя.

    Attributes:
        id: Уникальный идентификатор (UUID7)
        user_id: Внешний ключ на пользователя
        preferred_language: Предпочитаемый язык (например, 'ru', 'en')
        default_model_id: ID модели LLM по умолчанию для генерации
        default_embedder_id: ID модели эмбеддингов по умолчанию для RAG
        created_at: Дата создания (из TimestampMixin)
        updated_at: Дата обновления (из TimestampMixin)
        user: Связь с пользователем
    """

    __tablename__ = "user_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    preferred_language: Mapped[str] = mapped_column(String(10), default="ru", nullable=False)
    default_model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("llm_models.id"), nullable=True
    )
    default_embedder_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("embedding_models.id"), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="preferences")
