"""
Модели SQLAlchemy для карточек.

Этот модуль содержит модели данных для карточек Anki и связанных сущностей.

Основные компоненты:
    - CardStatus: статусы карточки в рабочем процессе
    - Card: модель карточки Anki
    - CardGenerationInfo: метаданные ИИ-генерации
    - CardEmbedding: векторные эмбеддинги для семантического поиска
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import BigInteger, Float, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.modules.decks.models import Deck
    from src.modules.templates.models import CardTemplate


class CardStatus(str, Enum):
    """
    Статус карточки в рабочем процессе ревью.

    Карточки проходят следующий рабочий процесс:
    - DRAFT: Новая, ожидает проверки
    - APPROVED: Проверена и одобрена, готова к синхронизации
    - REJECTED: Проверена и отклонена
    - SYNCED: Успешно синхронизирована с Anki
    """

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SYNCED = "synced"


class Card(UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    """
    Модель карточки Anki.

    Карточки содержат контент флеш-карточки, организованный по полям,
    соответствующим шаблону. Отслеживают статус в рабочем процессе
    и хранят ссылки на Anki после синхронизации.

    Attributes:
        id: Уникальный идентификатор (UUID7)
        deck_id: UUID колоды, которой принадлежит карточка
        template_id: UUID шаблона карточки
        fields: JSON-объект с полями (например, {"Front": "...", "Back": "..."})
        status: Текущий статус в рабочем процессе
        tags: Список тегов для организации и фильтрации
        anki_card_id: ID карточки в Anki после синхронизации
        anki_note_id: ID заметки в Anki после синхронизации
        created_at: Дата создания
        updated_at: Дата обновления
        deleted_at: Дата мягкого удаления
        deck: Связь с колодой
        template: Связь с шаблоном карточки
        generation_info: Метаданные генерации (если создана ИИ)
        embedding: Эмбеддинг для семантического поиска
    """

    __tablename__ = "cards"

    deck_id: Mapped[UUID] = mapped_column(
        ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("card_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[CardStatus] = mapped_column(
        SQLEnum(CardStatus, values_callable=lambda x: [e.value for e in x]),
        default=CardStatus.DRAFT,
        nullable=False,
        index=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=[],
        nullable=False,
    )
    anki_card_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    anki_note_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Relationships
    deck: Mapped[Deck] = relationship(back_populates="cards")
    template: Mapped[CardTemplate] = relationship()
    generation_info: Mapped[CardGenerationInfo | None] = relationship(
        back_populates="card",
        uselist=False,
    )
    embedding: Mapped[CardEmbedding | None] = relationship(
        back_populates="card",
        uselist=False,
    )

    __table_args__ = (Index("ix_cards_deck_status", "deck_id", "status"),)


class CardGenerationInfo(UUIDMixin, TimestampMixin, Base):
    """
    Метаданные ИИ-сгенерированных карточек.

    Отслеживает информацию о генерации карточки: использованный промпт,
    модель LLM и результаты проверки фактов.

    Attributes:
        id: Уникальный идентификатор (UUID7)
        card_id: UUID сгенерированной карточки
        prompt_id: UUID использованного шаблона промпта
        model_id: UUID использованной модели LLM
        user_request: Исходный запрос пользователя
        fact_check_result: JSON с результатами проверки фактов
        fact_check_confidence: Показатель достоверности
        created_at: Дата создания
        updated_at: Дата обновления
        card: Связь с карточкой
    """

    __tablename__ = "card_generation_info"

    card_id: Mapped[UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    prompt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("prompts.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("llm_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_request: Mapped[str] = mapped_column(Text, nullable=False)
    fact_check_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fact_check_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    card: Mapped[Card] = relationship(back_populates="generation_info")


class CardEmbedding(UUIDMixin, TimestampMixin, Base):
    """
    Векторный эмбеддинг для семантического поиска карточек.

    Хранит текстовый контент и вектор эмбеддинга для семантического
    поиска похожих карточек. Колонка вектора добавляется через
    миграцию Alembic с использованием pgvector.

    Attributes:
        id: Уникальный идентификатор (UUID7)
        card_id: UUID карточки
        embedder_id: UUID использованной модели эмбеддингов
        content_text: Текстовый контент для эмбеддинга
        created_at: Дата создания
        updated_at: Дата обновления
        card: Связь с карточкой
    """

    __tablename__ = "card_embeddings"

    card_id: Mapped[UUID] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    embedder_id: Mapped[UUID] = mapped_column(
        ForeignKey("embedding_models.id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Note: embedding vector column added via Alembic migration with pgvector

    # Relationships
    card: Mapped[Card] = relationship(back_populates="embedding")
