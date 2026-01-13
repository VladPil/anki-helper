"""Схемы Pydantic для операций с колодами."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from src.shared.schemas import BaseSchema, UUIDTimestampSchema


class DeckCreate(BaseSchema):
    """Схема для создания новой колоды."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Название колоды",
        examples=["Японская лексика"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Описание колоды (опционально)",
        examples=["Основные японские слова и фразы"],
    )
    parent_id: UUID | None = Field(
        default=None,
        description="ID родительской колоды для создания иерархии",
    )


class DeckUpdate(BaseSchema):
    """Схема для обновления существующей колоды.

    Все поля опциональны - обновляются только переданные поля.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Новое название колоды",
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Новое описание колоды",
    )
    parent_id: UUID | None = Field(
        default=None,
        description="Новый ID родительской колоды",
    )


class DeckResponse(UUIDTimestampSchema):
    """Схема ответа с данными колоды."""

    name: str = Field(
        ...,
        description="Название колоды",
    )
    description: str | None = Field(
        default=None,
        description="Описание колоды",
    )
    owner_id: UUID = Field(
        ...,
        description="ID владельца колоды",
    )
    parent_id: UUID | None = Field(
        default=None,
        description="ID родительской колоды",
    )
    anki_deck_id: int | None = Field(
        default=None,
        description="Внутренний ID колоды в Anki",
    )


class DeckTreeResponse(DeckResponse):
    """Схема колоды с вложенными дочерними колодами.

    Используется для отображения иерархической структуры колод.
    """

    children: list[DeckTreeResponse] = Field(
        default_factory=list,
        description="Дочерние колоды в иерархии",
    )


class CardBriefResponse(BaseSchema):
    """Краткая информация о карточке для списка колоды."""

    id: UUID = Field(
        ...,
        description="Уникальный идентификатор карточки",
    )
    status: str = Field(
        ...,
        description="Статус карточки",
    )


class DeckWithCards(DeckResponse):
    """Схема ответа с колодой и связанными карточками.

    Используется при запросе детальной информации о колоде.
    """

    cards: list[CardBriefResponse] = Field(
        default_factory=list,
        description="Карточки в этой колоде",
    )
    card_count: int = Field(
        default=0,
        description="Общее количество карточек в колоде",
    )


# Разрешение forward references
DeckTreeResponse.model_rebuild()
