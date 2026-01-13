"""Схемы Pydantic для модуля генерации карточек."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.shared.schemas import BaseSchema, UUIDTimestampSchema


class GenerationStatus(StrEnum):
    """Статус задачи генерации."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CardType(StrEnum):
    """Тип Anki-карточки для генерации."""

    BASIC = "basic"
    CLOZE = "cloze"
    BASIC_REVERSED = "basic_reversed"


class GenerationRequest(BaseSchema):
    """Схема запроса на генерацию карточек."""

    topic: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Тема или вопрос для генерации карточек",
        examples=["Основы Python", "Французские глаголы"],
    )
    deck_id: UUID = Field(
        ...,
        description="ID целевой колоды для сгенерированных карточек",
    )
    card_type: CardType = Field(
        default=CardType.BASIC,
        description="Тип генерируемых карточек",
    )
    num_cards: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Количество карточек для генерации",
    )
    difficulty: str = Field(
        default="medium",
        pattern="^(easy|medium|hard)$",
        description="Уровень сложности карточек",
    )
    language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Код языка для контента карточек",
        examples=["ru", "en", "de"],
    )
    include_sources: bool = Field(
        default=True,
        description="Включать ли ссылки на источники",
    )
    fact_check: bool = Field(
        default=True,
        description="Проверять ли сгенерированный контент на достоверность",
    )
    context: str | None = Field(
        default=None,
        max_length=5000,
        description="Дополнительный контекст для генерации",
    )
    model_id: str | None = Field(
        default=None,
        description="ID конкретной LLM модели для использования",
    )
    tags: list[str] = Field(
        default=[],
        max_length=20,
        description="Теги для присвоения сгенерированным карточкам",
    )


class GeneratedCard(BaseSchema):
    """Схема сгенерированной карточки."""

    front: str = Field(
        ...,
        description="Контент лицевой стороны (вопрос)",
    )
    back: str = Field(
        ...,
        description="Контент оборотной стороны (ответ)",
    )
    card_type: CardType = Field(
        ...,
        description="Тип карточки",
    )
    tags: list[str] = Field(
        default=[],
        description="Теги карточки",
    )
    source: str | None = Field(
        default=None,
        description="Ссылка на источник",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Уровень уверенности проверки фактов",
    )
    is_duplicate: bool = Field(
        default=False,
        description="Является ли карточка потенциальным дубликатом",
    )
    duplicate_card_id: UUID | None = Field(
        default=None,
        description="ID дубликата карточки, если обнаружен",
    )
    similarity_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Оценка сходства с существующими карточками",
    )


class GenerationResponse(BaseSchema):
    """Схема ответа на запрос генерации."""

    job_id: UUID = Field(
        ...,
        description="ID задачи генерации",
    )
    status: GenerationStatus = Field(
        ...,
        description="Текущий статус задачи",
    )
    message: str = Field(
        ...,
        description="Статусное сообщение",
    )


class GenerationJob(UUIDTimestampSchema):
    """Схема задачи генерации."""

    user_id: UUID = Field(
        ...,
        description="ID пользователя, создавшего задачу",
    )
    deck_id: UUID = Field(
        ...,
        description="ID целевой колоды",
    )
    status: GenerationStatus = Field(
        ...,
        description="Текущий статус задачи",
    )
    topic: str = Field(
        ...,
        description="Тема генерации",
    )
    card_type: CardType = Field(
        ...,
        description="Тип генерируемых карточек",
    )
    num_cards_requested: int = Field(
        ...,
        description="Запрошенное количество карточек",
    )
    num_cards_generated: int = Field(
        default=0,
        description="Количество успешно сгенерированных карточек",
    )
    cards: list[GeneratedCard] = Field(
        default=[],
        description="Сгенерированные карточки",
    )
    error_message: str | None = Field(
        default=None,
        description="Сообщение об ошибке при неудаче",
    )
    started_at: datetime | None = Field(
        default=None,
        description="Время начала обработки задачи",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Время завершения задачи",
    )
    metadata: dict[str, Any] = Field(
        default={},
        description="Дополнительные метаданные задачи",
    )


class GenerationJobStatus(BaseSchema):
    """Схема ответа о статусе задачи."""

    job_id: UUID = Field(
        ...,
        description="ID задачи генерации",
    )
    status: GenerationStatus = Field(
        ...,
        description="Текущий статус задачи",
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Процент выполнения",
    )
    num_cards_generated: int = Field(
        ...,
        description="Количество сгенерированных карточек на данный момент",
    )
    num_cards_requested: int = Field(
        ...,
        description="Общее запрошенное количество карточек",
    )
    current_step: str | None = Field(
        default=None,
        description="Текущий этап обработки",
    )
    error_message: str | None = Field(
        default=None,
        description="Сообщение об ошибке",
    )
    estimated_time_remaining: int | None = Field(
        default=None,
        description="Приблизительное оставшееся время в секундах",
    )


class StreamEvent(BaseSchema):
    """Схема события SSE-потока."""

    event: str = Field(
        ...,
        description="Тип события",
    )
    data: dict[str, Any] = Field(
        ...,
        description="Данные события",
    )


class GenerationStreamEvent(BaseSchema):
    """Схема события потока генерации."""

    type: str = Field(
        ...,
        description="Тип события: card, progress, error, complete",
    )
    card: GeneratedCard | None = Field(
        default=None,
        description="Сгенерированная карточка (для событий типа card)",
    )
    progress: float | None = Field(
        default=None,
        description="Процент выполнения",
    )
    step: str | None = Field(
        default=None,
        description="Текущий этап обработки",
    )
    message: str | None = Field(
        default=None,
        description="Статусное сообщение",
    )
    error: str | None = Field(
        default=None,
        description="Сообщение об ошибке",
    )
