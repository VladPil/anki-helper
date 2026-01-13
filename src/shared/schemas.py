"""Базовые схемы Pydantic для обработки API запросов и ответов."""

import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Базовая схема с общей конфигурацией.

    Все схемы должны наследоваться от этого базового класса
    для обеспечения единообразного поведения в приложении.
    """

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )


class UUIDSchema(BaseSchema):
    """Схема с полем UUID-идентификатора."""

    id: uuid.UUID = Field(
        ...,
        description="Уникальный идентификатор",
    )


class TimestampSchema(BaseSchema):
    """Схема с полями временных меток."""

    created_at: datetime = Field(
        ...,
        description="Дата и время создания",
    )
    updated_at: datetime = Field(
        ...,
        description="Дата и время последнего обновления",
    )


class UUIDTimestampSchema(UUIDSchema, TimestampSchema):
    """Комбинированная схема с UUID и временными метками.

    Наиболее часто используемая база для схем ответов,
    включающая идентификатор и аудит-метки времени.
    """

    pass


class PaginationParams(BaseSchema):
    """Параметры пагинации для списочных эндпоинтов."""

    page: int = Field(
        default=1,
        ge=1,
        description="Номер страницы (начиная с 1)",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Количество элементов на странице",
    )

    @property
    def offset(self) -> int:
        """Вычисляет смещение для запросов к базе данных.

        Returns:
            Количество записей для пропуска.
        """
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Возвращает лимит для запросов к базе данных.

        Returns:
            Максимальное количество возвращаемых записей.
        """
        return self.page_size


T = TypeVar("T")


class PaginatedResponse(BaseSchema, Generic[T]):
    """Обобщенная обертка для пагинированных ответов."""

    items: list[T] = Field(
        ...,
        description="Список элементов",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Общее количество элементов",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Текущий номер страницы",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Количество элементов на странице",
    )

    @property
    def total_pages(self) -> int:
        """Вычисляет общее количество страниц.

        Returns:
            Общее количество страниц на основе total и page_size.
        """
        if self.total == 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """Проверяет наличие следующей страницы.

        Returns:
            True, если есть страницы после текущей.
        """
        return self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Проверяет наличие предыдущей страницы.

        Returns:
            True, если текущая страница не первая.
        """
        return self.page > 1

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        params: PaginationParams,
    ) -> "PaginatedResponse[T]":
        """Создает пагинированный ответ из элементов и параметров пагинации.

        Args:
            items: Список элементов для текущей страницы.
            total: Общее количество элементов по всем страницам.
            params: Параметры пагинации, использованные в запросе.

        Returns:
            Экземпляр PaginatedResponse.
        """
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )


class ErrorDetail(BaseSchema):
    """Детальная информация об ошибке.

    Используется внутри ErrorResponse для структурированных деталей ошибки.
    """

    field: str | None = Field(
        default=None,
        description="Поле, вызвавшее ошибку (если применимо)",
    )
    message: str = Field(
        ...,
        description="Текст ошибки",
    )
    code: str | None = Field(
        default=None,
        description="Код ошибки для программной обработки",
    )


class ErrorResponse(BaseSchema):
    """Стандартная схема ответа об ошибке.

    Используется для всех API-ошибок для обеспечения
    единообразного формата ошибок в приложении.
    """

    error: str = Field(
        ...,
        description="Человекочитаемое сообщение об ошибке",
    )
    code: str | None = Field(
        default=None,
        description="Код ошибки для программной обработки",
    )
    details: list[ErrorDetail] | None = Field(
        default=None,
        description="Детальная информация об ошибке",
    )
    request_id: str | None = Field(
        default=None,
        description="ID запроса для трассировки",
    )

    @classmethod
    def validation_error(
        cls,
        errors: list[dict[str, Any]],
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Создает ответ об ошибке из ошибок валидации.

        Args:
            errors: Список словарей с ошибками валидации.
            request_id: Опциональный ID запроса для трассировки.

        Returns:
            Экземпляр ErrorResponse, отформатированный для ошибок валидации.
        """
        details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in err.get("loc", [])),
                message=err.get("msg", "Ошибка валидации"),
                code=err.get("type"),
            )
            for err in errors
        ]
        return cls(
            error="Ошибка валидации",
            code="VALIDATION_ERROR",
            details=details,
            request_id=request_id,
        )


class HealthResponse(BaseSchema):
    """Схема ответа проверки работоспособности.

    Используется для эндпоинтов health check для отчета о состоянии сервиса.
    """

    status: str = Field(
        ...,
        description="Общий статус работоспособности",
        examples=["healthy", "unhealthy", "degraded"],
    )
    version: str | None = Field(
        default=None,
        description="Версия приложения",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(),
        description="Временная метка проверки",
    )
    dependencies: dict[str, str] | None = Field(
        default=None,
        description="Статус работоспособности отдельных зависимостей",
    )
    checks: dict[str, bool] | None = Field(
        default=None,
        description="Проверки отдельных компонентов (устарело, используйте dependencies)",
    )

    @property
    def is_healthy(self) -> bool:
        """Проверяет, работоспособен ли сервис.

        Returns:
            True, если статус 'healthy'.
        """
        return self.status == "healthy"

    @classmethod
    def healthy(
        cls,
        version: str | None = None,
        checks: dict[str, bool] | None = None,
    ) -> "HealthResponse":
        """Создает ответ о работоспособности.

        Args:
            version: Опциональная версия приложения.
            checks: Опциональные проверки компонентов.

        Returns:
            HealthResponse со статусом 'healthy'.
        """
        return cls(status="healthy", version=version, checks=checks)

    @classmethod
    def unhealthy(
        cls,
        version: str | None = None,
        checks: dict[str, bool] | None = None,
    ) -> "HealthResponse":
        """Создает ответ о неработоспособности.

        Args:
            version: Опциональная версия приложения.
            checks: Опциональные проверки компонентов.

        Returns:
            HealthResponse со статусом 'unhealthy'.
        """
        return cls(status="unhealthy", version=version, checks=checks)

    @classmethod
    def degraded(
        cls,
        version: str | None = None,
        checks: dict[str, bool] | None = None,
    ) -> "HealthResponse":
        """Создает ответ о деградированном состоянии.

        Args:
            version: Опциональная версия приложения.
            checks: Опциональные проверки компонентов.

        Returns:
            HealthResponse со статусом 'degraded'.
        """
        return cls(status="degraded", version=version, checks=checks)


class SuccessResponse(BaseSchema):
    """Обобщенный ответ об успехе для операций без специфичных возвращаемых данных."""

    success: bool = Field(
        default=True,
        description="Статус успешности операции",
    )
    message: str = Field(
        ...,
        description="Сообщение об успехе",
    )


class SoftDeleteSchema(BaseSchema):
    """Схема с полем мягкого удаления."""

    deleted_at: datetime | None = Field(
        default=None,
        description="Временная метка мягкого удаления",
    )

    @property
    def is_deleted(self) -> bool:
        """Проверяет, была ли запись мягко удалена.

        Returns:
            True, если deleted_at установлен.
        """
        return self.deleted_at is not None
