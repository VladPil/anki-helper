"""
Сервис управления карточками.

Этот модуль отвечает за бизнес-логику работы с карточками Anki.

Основные компоненты:
    - CardService: CRUD-операции, управление статусами и массовые операции
    - CardNotFoundError: карточка не найдена
    - CardAccessDeniedError: нет доступа к карточке
    - InvalidCardStatusTransitionError: недопустимый переход статуса
    - DeckNotFoundError: колода не найдена
    - TemplateNotFoundError: шаблон карточки не найден
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Card, CardGenerationInfo, CardStatus
from .schemas import CardBulkItem, CardCreate, CardUpdate

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CardNotFoundError(Exception):
    """Возникает когда карточка не найдена."""

    def __init__(self, card_id: UUID) -> None:
        self.card_id = card_id
        super().__init__(f"Card with ID {card_id} not found")


class CardAccessDeniedError(Exception):
    """Возникает когда у пользователя нет доступа к карточке."""

    def __init__(self, card_id: UUID, user_id: UUID) -> None:
        self.card_id = card_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not have access to card {card_id}")


class InvalidCardStatusTransitionError(Exception):
    """Возникает при попытке недопустимого перехода статуса."""

    def __init__(
        self,
        card_id: UUID,
        current_status: CardStatus,
        target_status: CardStatus,
    ) -> None:
        self.card_id = card_id
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot transition card {card_id} from {current_status.value} to {target_status.value}"
        )


class DeckNotFoundError(Exception):
    """Возникает когда колода не найдена."""

    def __init__(self, deck_id: UUID) -> None:
        self.deck_id = deck_id
        super().__init__(f"Deck with ID {deck_id} not found")


class TemplateNotFoundError(Exception):
    """Возникает когда шаблон карточки не найден."""

    def __init__(self, template_id: UUID) -> None:
        self.template_id = template_id
        super().__init__(f"Template with ID {template_id} not found")


# Valid status transitions
VALID_TRANSITIONS: dict[CardStatus, set[CardStatus]] = {
    CardStatus.DRAFT: {CardStatus.APPROVED, CardStatus.REJECTED},
    CardStatus.APPROVED: {CardStatus.SYNCED, CardStatus.DRAFT},
    CardStatus.REJECTED: {CardStatus.DRAFT},
    CardStatus.SYNCED: set(),  # SYNCED is terminal
}


class CardService:
    """
    Сервис управления карточками.

    Обрабатывает бизнес-логику карточек, включая CRUD-операции,
    управление статусами и массовые операции.

    Example:
        async with get_db() as session:
            service = CardService(session)
            card = await service.create(user_id, CardCreate(...))
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Инициализировать сервис карточек.

        Args:
            session: Асинхронная сессия SQLAlchemy для операций с БД
        """
        self._session = session

    async def create(
        self,
        user_id: UUID,
        data: CardCreate,
        *,
        created_by: str | None = None,
    ) -> Card:
        """
        Создать новую карточку.

        Args:
            user_id: UUID пользователя-создателя
            data: Данные для создания карточки
            created_by: Опциональный идентификатор для аудита

        Returns:
            Созданный экземпляр Card

        Raises:
            DeckNotFoundError: Колода не существует или нет доступа
            TemplateNotFoundError: Шаблон не существует
        """
        # Verify deck exists and belongs to user
        from src.modules.decks.models import Deck

        deck_stmt = select(Deck).where(
            and_(
                Deck.id == data.deck_id,
                Deck.owner_id == user_id,
                Deck.deleted_at.is_(None),
            )
        )
        deck_result = await self._session.execute(deck_stmt)
        deck = deck_result.scalar_one_or_none()
        if deck is None:
            raise DeckNotFoundError(data.deck_id)

        card = Card(
            deck_id=data.deck_id,
            template_id=data.template_id,
            fields=data.fields,
            tags=data.tags,
            status=CardStatus.DRAFT,
        )

        if created_by:
            card.set_created_by(created_by)

        self._session.add(card)
        await self._session.flush()
        await self._session.refresh(card)

        logger.info(
            "Created card %s in deck %s",
            card.id,
            data.deck_id,
            extra={"card_id": str(card.id), "deck_id": str(data.deck_id)},
        )

        return card

    async def create_bulk(
        self,
        user_id: UUID,
        deck_id: UUID,
        template_id: UUID,
        items: list[CardBulkItem],
        *,
        created_by: str | None = None,
    ) -> tuple[list[Card], list[tuple[int, str]]]:
        """
        Создать несколько карточек массово.

        Args:
            user_id: UUID пользователя-создателя
            deck_id: UUID колоды для добавления карточек
            template_id: UUID шаблона карточки
            items: Список элементов для создания
            created_by: Опциональный идентификатор для аудита

        Returns:
            Кортеж (список созданных карточек, список (индекс, ошибка) для неудачных)

        Raises:
            DeckNotFoundError: Колода не существует или нет доступа
        """
        # Verify deck exists and belongs to user
        from src.modules.decks.models import Deck

        deck_stmt = select(Deck).where(
            and_(
                Deck.id == deck_id,
                Deck.owner_id == user_id,
                Deck.deleted_at.is_(None),
            )
        )
        deck_result = await self._session.execute(deck_stmt)
        deck = deck_result.scalar_one_or_none()
        if deck is None:
            raise DeckNotFoundError(deck_id)

        created_cards: list[Card] = []
        errors: list[tuple[int, str]] = []

        for index, item in enumerate(items):
            try:
                card = Card(
                    deck_id=deck_id,
                    template_id=template_id,
                    fields=item.fields,
                    tags=item.tags,
                    status=CardStatus.DRAFT,
                )

                if created_by:
                    card.set_created_by(created_by)

                self._session.add(card)
                await self._session.flush()
                await self._session.refresh(card)
                created_cards.append(card)

            except Exception as e:
                errors.append((index, str(e)))
                logger.warning(
                    "Failed to create card at index %d: %s",
                    index,
                    str(e),
                )

        logger.info(
            "Bulk created %d cards (failed: %d) in deck %s",
            len(created_cards),
            len(errors),
            deck_id,
            extra={
                "deck_id": str(deck_id),
                "cards_created": len(created_cards),
                "cards_failed": len(errors),
            },
        )

        return created_cards, errors

    async def get_by_id(
        self,
        card_id: UUID,
        *,
        include_deleted: bool = False,
        include_generation_info: bool = False,
    ) -> Card | None:
        """
        Получить карточку по ID.

        Args:
            card_id: UUID карточки
            include_deleted: Включать ли мягко удаленные карточки
            include_generation_info: Загружать ли информацию о генерации

        Returns:
            Экземпляр Card если найден, None в противном случае
        """
        stmt = select(Card).where(Card.id == card_id)

        if not include_deleted:
            stmt = stmt.where(Card.deleted_at.is_(None))

        if include_generation_info:
            stmt = stmt.options(selectinload(Card.generation_info))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self,
        card_id: UUID,
        user_id: UUID,
        *,
        include_deleted: bool = False,
        include_generation_info: bool = False,
    ) -> Card | None:
        """
        Получить карточку по ID с проверкой доступа через владельца колоды.

        Args:
            card_id: UUID карточки
            user_id: UUID пользователя с доступом
            include_deleted: Включать ли мягко удаленные карточки
            include_generation_info: Загружать ли информацию о генерации

        Returns:
            Экземпляр Card если найден и доступен, None в противном случае
        """
        from src.modules.decks.models import Deck

        stmt = (
            select(Card)
            .join(Deck)
            .where(
                and_(
                    Card.id == card_id,
                    Deck.owner_id == user_id,
                )
            )
        )

        if not include_deleted:
            stmt = stmt.where(Card.deleted_at.is_(None))

        if include_generation_info:
            stmt = stmt.options(selectinload(Card.generation_info))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_deck(
        self,
        deck_id: UUID,
        user_id: UUID,
        *,
        status: CardStatus | None = None,
        tags: list[str] | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Card], int]:
        """
        Получить список карточек в колоде.

        Args:
            deck_id: UUID колоды
            user_id: UUID пользователя (для контроля доступа)
            status: Опциональный фильтр по статусу
            tags: Опциональный фильтр по тегам (карточки с любым из тегов)
            offset: Количество записей для пропуска
            limit: Максимальное количество записей

        Returns:
            Кортеж (список карточек, общее количество)
        """
        from src.modules.decks.models import Deck

        # Base conditions
        conditions = [
            Card.deck_id == deck_id,
            Card.deleted_at.is_(None),
            Deck.owner_id == user_id,
        ]

        if status is not None:
            conditions.append(Card.status == status)

        # Tags filter using array overlap
        if tags:
            from sqlalchemy.dialects.postgresql import array

            conditions.append(Card.tags.overlap(array(tags)))

        # Count query
        count_stmt = select(func.count()).select_from(Card).join(Deck).where(*conditions)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Data query
        stmt = (
            select(Card)
            .join(Deck)
            .where(*conditions)
            .order_by(Card.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        cards = list(result.scalars().all())

        return cards, total

    async def list_by_status(
        self,
        user_id: UUID,
        status: CardStatus,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Card], int]:
        """
        Получить список карточек с определенным статусом во всех колодах пользователя.

        Args:
            user_id: UUID пользователя
            status: Статус для фильтрации
            offset: Количество записей для пропуска
            limit: Максимальное количество записей

        Returns:
            Кортеж (список карточек, общее количество)
        """
        from src.modules.decks.models import Deck

        conditions = [
            Card.status == status,
            Card.deleted_at.is_(None),
            Deck.owner_id == user_id,
        ]

        # Count query
        count_stmt = select(func.count()).select_from(Card).join(Deck).where(*conditions)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Data query
        stmt = (
            select(Card)
            .join(Deck)
            .where(*conditions)
            .order_by(Card.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        cards = list(result.scalars().all())

        return cards, total

    async def update(
        self,
        card_id: UUID,
        user_id: UUID,
        data: CardUpdate,
        *,
        updated_by: str | None = None,
    ) -> Card:
        """
        Обновить карточку.

        Args:
            card_id: UUID карточки для обновления
            user_id: UUID пользователя, выполняющего обновление
            data: Данные для обновления
            updated_by: Опциональный идентификатор для аудита

        Returns:
            Обновленный экземпляр Card

        Raises:
            CardNotFoundError: Карточка не существует или нет доступа
            InvalidCardStatusTransitionError: Недопустимый переход статуса
        """
        card = await self.get_by_id_for_user(card_id, user_id)
        if card is None:
            raise CardNotFoundError(card_id)

        # Validate status transition if changing status
        if data.status is not None and data.status != card.status:
            if data.status not in VALID_TRANSITIONS.get(card.status, set()):
                raise InvalidCardStatusTransitionError(card_id, card.status, data.status)

        # Validate new deck if changing deck
        if data.deck_id is not None and data.deck_id != card.deck_id:
            from src.modules.decks.models import Deck

            deck_stmt = select(Deck).where(
                and_(
                    Deck.id == data.deck_id,
                    Deck.owner_id == user_id,
                    Deck.deleted_at.is_(None),
                )
            )
            deck_result = await self._session.execute(deck_stmt)
            if deck_result.scalar_one_or_none() is None:
                raise DeckNotFoundError(data.deck_id)

        # Apply updates
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(card, field, value)

        if updated_by:
            card.set_updated_by(updated_by)

        await self._session.flush()
        await self._session.refresh(card)

        logger.info(
            "Updated card %s",
            card_id,
            extra={"card_id": str(card_id), "updated_fields": list(update_data.keys())},
        )

        return card

    async def delete(
        self,
        card_id: UUID,
        user_id: UUID,
        *,
        hard_delete: bool = False,
    ) -> bool:
        """
        Удалить карточку.

        Args:
            card_id: UUID карточки для удаления
            user_id: UUID пользователя, выполняющего удаление
            hard_delete: Выполнить ли жесткое удаление

        Returns:
            True если удалено, False если не найдено

        Raises:
            CardNotFoundError: Карточка не существует или нет доступа
        """
        card = await self.get_by_id_for_user(card_id, user_id)
        if card is None:
            raise CardNotFoundError(card_id)

        if hard_delete:
            await self._session.delete(card)
        else:
            card.soft_delete()

        await self._session.flush()

        logger.info(
            "Deleted card %s (hard=%s)",
            card_id,
            hard_delete,
            extra={"card_id": str(card_id), "hard_delete": hard_delete},
        )

        return True

    async def approve(
        self,
        card_id: UUID,
        user_id: UUID,
        *,
        reason: str | None = None,
        updated_by: str | None = None,
    ) -> Card:
        """
        Одобрить карточку для синхронизации с Anki.

        Args:
            card_id: UUID карточки для одобрения
            user_id: UUID пользователя, одобряющего карточку
            reason: Опциональные заметки об одобрении
            updated_by: Опциональный идентификатор для аудита

        Returns:
            Одобренный экземпляр Card

        Raises:
            CardNotFoundError: Карточка не существует или нет доступа
            InvalidCardStatusTransitionError: Карточка не может быть одобрена
        """
        card = await self.get_by_id_for_user(card_id, user_id)
        if card is None:
            raise CardNotFoundError(card_id)

        if CardStatus.APPROVED not in VALID_TRANSITIONS.get(card.status, set()):
            raise InvalidCardStatusTransitionError(card_id, card.status, CardStatus.APPROVED)

        card.status = CardStatus.APPROVED

        if updated_by:
            card.set_updated_by(updated_by)

        await self._session.flush()
        await self._session.refresh(card)

        logger.info(
            "Approved card %s",
            card_id,
            extra={"card_id": str(card_id), "reason": reason},
        )

        return card

    async def reject(
        self,
        card_id: UUID,
        user_id: UUID,
        reason: str,
        *,
        updated_by: str | None = None,
    ) -> Card:
        """
        Отклонить карточку.

        Args:
            card_id: UUID карточки для отклонения
            user_id: UUID пользователя, отклоняющего карточку
            reason: Причина отклонения
            updated_by: Опциональный идентификатор для аудита

        Returns:
            Отклоненный экземпляр Card

        Raises:
            CardNotFoundError: Карточка не существует или нет доступа
            InvalidCardStatusTransitionError: Карточка не может быть отклонена
        """
        card = await self.get_by_id_for_user(card_id, user_id)
        if card is None:
            raise CardNotFoundError(card_id)

        if CardStatus.REJECTED not in VALID_TRANSITIONS.get(card.status, set()):
            raise InvalidCardStatusTransitionError(card_id, card.status, CardStatus.REJECTED)

        card.status = CardStatus.REJECTED

        if updated_by:
            card.set_updated_by(updated_by)

        await self._session.flush()
        await self._session.refresh(card)

        logger.info(
            "Rejected card %s: %s",
            card_id,
            reason,
            extra={"card_id": str(card_id), "reason": reason},
        )

        return card

    async def mark_synced(
        self,
        card_id: UUID,
        anki_card_id: int,
        anki_note_id: int,
    ) -> Card:
        """
        Отметить карточку как синхронизированную с Anki.

        Args:
            card_id: UUID карточки
            anki_card_id: ID карточки в Anki
            anki_note_id: ID заметки в Anki

        Returns:
            Обновленный экземпляр Card

        Raises:
            CardNotFoundError: Карточка не существует
            InvalidCardStatusTransitionError: Карточка не может быть отмечена как синхронизированная
        """
        card = await self.get_by_id(card_id)
        if card is None:
            raise CardNotFoundError(card_id)

        if CardStatus.SYNCED not in VALID_TRANSITIONS.get(card.status, set()):
            raise InvalidCardStatusTransitionError(card_id, card.status, CardStatus.SYNCED)

        card.status = CardStatus.SYNCED
        card.anki_card_id = anki_card_id
        card.anki_note_id = anki_note_id

        await self._session.flush()
        await self._session.refresh(card)

        logger.info(
            "Marked card %s as synced (anki_card=%d, anki_note=%d)",
            card_id,
            anki_card_id,
            anki_note_id,
            extra={
                "card_id": str(card_id),
                "anki_card_id": anki_card_id,
                "anki_note_id": anki_note_id,
            },
        )

        return card

    async def bulk_approve(
        self,
        card_ids: list[UUID],
        user_id: UUID,
        *,
        updated_by: str | None = None,
    ) -> tuple[list[Card], list[tuple[UUID, str]]]:
        """
        Одобрить несколько карточек массово.

        Args:
            card_ids: Список UUID карточек для одобрения
            user_id: UUID пользователя, одобряющего карточки
            updated_by: Опциональный идентификатор для аудита

        Returns:
            Кортеж (список одобренных карточек, список (card_id, ошибка) для неудачных)
        """
        approved: list[Card] = []
        errors: list[tuple[UUID, str]] = []

        for card_id in card_ids:
            try:
                card = await self.approve(card_id, user_id, updated_by=updated_by)
                approved.append(card)
            except (CardNotFoundError, InvalidCardStatusTransitionError) as e:
                errors.append((card_id, str(e)))

        logger.info(
            "Bulk approved %d cards (failed: %d)",
            len(approved),
            len(errors),
            extra={"approved": len(approved), "failed": len(errors)},
        )

        return approved, errors

    async def bulk_reject(
        self,
        card_ids: list[UUID],
        user_id: UUID,
        reason: str,
        *,
        updated_by: str | None = None,
    ) -> tuple[list[Card], list[tuple[UUID, str]]]:
        """
        Отклонить несколько карточек массово.

        Args:
            card_ids: Список UUID карточек для отклонения
            user_id: UUID пользователя, отклоняющего карточки
            reason: Причина отклонения
            updated_by: Опциональный идентификатор для аудита

        Returns:
            Кортеж (список отклоненных карточек, список (card_id, ошибка) для неудачных)
        """
        rejected: list[Card] = []
        errors: list[tuple[UUID, str]] = []

        for card_id in card_ids:
            try:
                card = await self.reject(card_id, user_id, reason, updated_by=updated_by)
                rejected.append(card)
            except (CardNotFoundError, InvalidCardStatusTransitionError) as e:
                errors.append((card_id, str(e)))

        logger.info(
            "Bulk rejected %d cards (failed: %d)",
            len(rejected),
            len(errors),
            extra={"rejected": len(rejected), "failed": len(errors)},
        )

        return rejected, errors

    async def restore(
        self,
        card_id: UUID,
        user_id: UUID,
    ) -> Card:
        """
        Восстановить мягко удаленную карточку.

        Args:
            card_id: UUID карточки для восстановления
            user_id: UUID пользователя, выполняющего восстановление

        Returns:
            Восстановленный экземпляр Card

        Raises:
            CardNotFoundError: Карточка не существует или нет доступа
        """
        card = await self.get_by_id_for_user(card_id, user_id, include_deleted=True)
        if card is None:
            raise CardNotFoundError(card_id)

        card.restore()
        await self._session.flush()
        await self._session.refresh(card)

        logger.info(
            "Restored card %s",
            card_id,
            extra={"card_id": str(card_id)},
        )

        return card

    async def add_generation_info(
        self,
        card_id: UUID,
        prompt_id: UUID | None,
        model_id: UUID | None,
        user_request: str,
        fact_check_result: dict | None = None,
        fact_check_confidence: float | None = None,
    ) -> CardGenerationInfo:
        """
        Добавить метаданные генерации к карточке.

        Args:
            card_id: UUID карточки
            prompt_id: UUID использованного шаблона промпта
            model_id: UUID использованной LLM модели
            user_request: Исходный запрос пользователя
            fact_check_result: Опциональные результаты проверки фактов
            fact_check_confidence: Опциональный показатель достоверности

        Returns:
            Созданный экземпляр CardGenerationInfo
        """
        info = CardGenerationInfo(
            card_id=card_id,
            prompt_id=prompt_id,
            model_id=model_id,
            user_request=user_request,
            fact_check_result=fact_check_result,
            fact_check_confidence=fact_check_confidence,
        )

        self._session.add(info)
        await self._session.flush()
        await self._session.refresh(info)

        logger.info(
            "Added generation info to card %s",
            card_id,
            extra={"card_id": str(card_id)},
        )

        return info
