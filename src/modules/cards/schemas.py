"""Схемы Pydantic для операций с карточками."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from src.shared.schemas import BaseSchema, UUIDTimestampSchema

from .models import CardStatus


class CardCreate(BaseSchema):
    """Схема для создания новой карточки.

    Поддерживает два формата:
    1. Полный формат: {deck_id, template_id, fields: {Front, Back}}
    2. Упрощённый формат: {deck_id, front, back}
    """

    deck_id: UUID = Field(
        ...,
        description="ID колоды, в которую добавляется карточка",
    )
    template_id: UUID | None = Field(
        default=None,
        description="ID шаблона карточки (опционально, используется 'basic' по умолчанию)",
    )
    fields: dict[str, Any] | None = Field(
        default=None,
        description="Значения полей согласно шаблону",
        examples=[{"Front": "Вопрос", "Back": "Ответ"}],
    )
    front: str | None = Field(
        default=None,
        description="Передняя сторона карточки (упрощённый формат)",
    )
    back: str | None = Field(
        default=None,
        description="Задняя сторона карточки (упрощённый формат)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Теги для организации карточек",
        examples=[["программирование", "python"]],
    )

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Валидация и нормализация тегов."""
        return [tag.strip() for tag in v if tag and tag.strip()]

    def model_post_init(self, __context: Any) -> None:
        """Нормализация данных после валидации."""
        # Если fields не передан, но есть front/back - создаём fields
        if self.fields is None:
            if self.front is not None or self.back is not None:
                object.__setattr__(self, "fields", {
                    "Front": self.front or "",
                    "Back": self.back or "",
                })
            else:
                raise ValueError(
                    "Необходимо указать либо 'fields', либо 'front'/'back'"
                )
        elif not self.fields:
            raise ValueError("Поля не могут быть пустыми")


class CardUpdate(BaseSchema):
    """Схема для обновления существующей карточки.

    Все поля опциональны - обновляются только переданные поля.
    """

    deck_id: UUID | None = Field(
        default=None,
        description="Новый ID колоды (перемещение карточки)",
    )
    template_id: UUID | None = Field(
        default=None,
        description="Новый ID шаблона (изменение типа карточки)",
    )
    fields: dict[str, Any] | None = Field(
        default=None,
        description="Обновленные значения полей",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Обновленные теги",
    )
    status: CardStatus | None = Field(
        default=None,
        description="Новый статус карточки",
    )

    @field_validator("fields")
    @classmethod
    def validate_fields_not_empty(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Проверка, что словарь полей не пустой, если передан."""
        if v is not None and not v:
            raise ValueError("Поля не могут быть пустыми")
        return v


class CardResponse(UUIDTimestampSchema):
    """Схема ответа с данными карточки."""

    deck_id: UUID = Field(
        ...,
        description="ID колоды, содержащей карточку",
    )
    template_id: UUID = Field(
        ...,
        description="ID шаблона карточки",
    )
    fields: dict[str, Any] = Field(
        ...,
        description="Значения полей карточки",
    )
    front: str = Field(
        default="",
        description="Передняя сторона карточки (из fields)",
    )
    back: str = Field(
        default="",
        description="Задняя сторона карточки (из fields)",
    )
    status: CardStatus = Field(
        ...,
        description="Текущий статус карточки",
    )
    tags: list[str] = Field(
        ...,
        description="Теги карточки",
    )
    anki_card_id: int | None = Field(
        default=None,
        description="ID карточки в Anki после синхронизации",
    )
    anki_note_id: int | None = Field(
        default=None,
        description="ID заметки в Anki после синхронизации",
    )

    @field_validator("front", "back", mode="before")
    @classmethod
    def extract_from_fields(cls, v: Any, info: Any) -> str:
        """Extract front/back from fields if not provided."""
        if v:
            return v
        # Will be set in model_validate
        return ""

    def model_post_init(self, __context: Any) -> None:
        """Extract front/back from fields after validation."""
        if self.fields:
            if not self.front:
                self.front = str(self.fields.get("Front", ""))
            if not self.back:
                self.back = str(self.fields.get("Back", ""))


class GenerationInfoResponse(BaseSchema):
    """Схема метаданных генерации карточки."""

    id: UUID = Field(
        ...,
        description="Уникальный идентификатор записи генерации",
    )
    prompt_id: UUID | None = Field(
        default=None,
        description="ID использованного шаблона промпта",
    )
    model_id: UUID | None = Field(
        default=None,
        description="ID использованной LLM модели",
    )
    user_request: str = Field(
        ...,
        description="Исходный запрос пользователя",
    )
    fact_check_result: dict[str, Any] | None = Field(
        default=None,
        description="Результаты проверки фактов",
    )
    fact_check_confidence: float | None = Field(
        default=None,
        description="Уровень уверенности проверки фактов",
    )
    created_at: datetime = Field(
        ...,
        description="Дата и время генерации карточки",
    )


class CardWithGenerationInfo(CardResponse):
    """Схема ответа с карточкой и метаданными генерации.

    Используется для AI-сгенерированных карточек с контекстом генерации.
    """

    generation_info: GenerationInfoResponse | None = Field(
        default=None,
        description="Метаданные AI-генерации (если применимо)",
    )


class CardBulkItem(BaseSchema):
    """Элемент для массового создания карточек."""

    fields: dict[str, Any] = Field(
        ...,
        description="Значения полей для этой карточки",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Теги для этой карточки",
    )


class CardBulkCreate(BaseSchema):
    """Схема для массового создания карточек."""

    deck_id: UUID = Field(
        ...,
        description="ID колоды для добавления карточек",
    )
    template_id: UUID = Field(
        ...,
        description="ID шаблона для всех карточек",
    )
    cards: list[CardBulkItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Список карточек для создания",
    )


class CardBulkError(BaseSchema):
    """Детали ошибки при массовом создании карточки."""

    index: int = Field(
        ...,
        description="Индекс карточки с ошибкой в исходном списке",
    )
    error: str = Field(
        ...,
        description="Текст ошибки",
    )


class CardBulkResponse(BaseSchema):
    """Ответ на операцию массового создания карточек."""

    created: list[CardResponse] = Field(
        ...,
        description="Успешно созданные карточки",
    )
    failed: list[CardBulkError] = Field(
        ...,
        description="Карточки, которые не удалось создать",
    )
    total_created: int = Field(
        ...,
        description="Количество созданных карточек",
    )
    total_failed: int = Field(
        ...,
        description="Количество неудачных попыток",
    )


class CardStatusUpdate(BaseSchema):
    """Схема для обновления статуса карточки."""

    status: CardStatus = Field(
        ...,
        description="Новый статус карточки",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Причина изменения статуса (опционально)",
    )


class CardApproveRequest(BaseSchema):
    """Схема для одобрения карточки."""

    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Примечание к одобрению (опционально)",
    )


class CardRejectRequest(BaseSchema):
    """Схема для отклонения карточки."""

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Причина отклонения",
    )
