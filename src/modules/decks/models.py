"""
Модели SQLAlchemy для колод.

Этот модуль содержит модели данных для колод Anki.

Основные компоненты:
    - Deck: модель колоды с поддержкой иерархии
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.modules.cards.models import Card
    from src.modules.users.models import User


class Deck(UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    """
    Модель колоды Anki.

    Колоды поддерживают иерархическую организацию через parent_id,
    что позволяет создавать вложенные структуры как в Anki.

    Attributes:
        id: Уникальный идентификатор (UUID7)
        name: Название колоды
        description: Описание колоды (опционально)
        owner_id: UUID владельца колоды
        parent_id: UUID родительской колоды (опционально)
        anki_deck_id: ID колоды в Anki после синхронизации
        created_at: Дата создания
        updated_at: Дата обновления
        deleted_at: Дата мягкого удаления
        owner: Связь с владельцем (User)
        parent: Связь с родительской колодой
        children: Дочерние колоды
        cards: Карточки в колоде
    """

    __tablename__ = "decks"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    anki_deck_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Relationships
    owner: Mapped[User] = relationship(back_populates="decks")
    parent: Mapped[Deck | None] = relationship(
        remote_side="Deck.id",
        back_populates="children",
    )
    children: Mapped[list[Deck]] = relationship(back_populates="parent")
    cards: Mapped[list[Card]] = relationship(
        back_populates="deck",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_decks_owner_parent", "owner_id", "parent_id"),
        UniqueConstraint("name", "owner_id", name="uq_decks_name_owner"),
    )
