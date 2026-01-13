"""
Сервис управления колодами.

Этот модуль отвечает за бизнес-логику работы с колодами Anki.

Основные компоненты:
    - DeckService: CRUD-операции и управление иерархией колод
    - DeckNotFoundError: колода не найдена
    - DeckAccessDeniedError: нет доступа к колоде
    - DeckCircularReferenceError: циклическая ссылка в иерархии
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Deck
from .schemas import DeckCreate, DeckUpdate

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class DeckNotFoundError(Exception):
    """Возникает когда колода не найдена."""

    def __init__(self, deck_id: UUID) -> None:
        self.deck_id = deck_id
        super().__init__(f"Deck with ID {deck_id} not found")


class DeckAccessDeniedError(Exception):
    """Возникает когда у пользователя нет доступа к колоде."""

    def __init__(self, deck_id: UUID, user_id: UUID) -> None:
        self.deck_id = deck_id
        self.user_id = user_id
        super().__init__(f"User {user_id} does not have access to deck {deck_id}")


class DeckCircularReferenceError(Exception):
    """Возникает при попытке создать циклическую ссылку в иерархии колод."""

    def __init__(self, deck_id: UUID, parent_id: UUID) -> None:
        self.deck_id = deck_id
        self.parent_id = parent_id
        super().__init__(
            f"Setting parent {parent_id} for deck {deck_id} would create a circular reference"
        )


class DeckService:
    """
    Сервис управления колодами.

    Обрабатывает бизнес-логику колод, включая CRUD-операции,
    операции с иерархией и контроль доступа.

    Example:
        async with get_db() as session:
            service = DeckService(session)
            deck = await service.create(user_id, DeckCreate(name="New Deck"))
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Инициализировать сервис колод.

        Args:
            session: Асинхронная сессия SQLAlchemy для операций с БД
        """
        self._session = session

    async def create(
        self,
        owner_id: UUID,
        data: DeckCreate,
        *,
        created_by: str | None = None,
    ) -> Deck:
        """
        Создать новую колоду.

        Args:
            owner_id: UUID пользователя-владельца
            data: Данные для создания колоды
            created_by: Опциональный идентификатор для аудита

        Returns:
            Созданный экземпляр Deck

        Raises:
            DeckNotFoundError: Указанная родительская колода не существует
            DeckAccessDeniedError: Родительская колода принадлежит другому пользователю
        """
        # Validate parent deck if specified
        if data.parent_id:
            parent = await self.get_by_id(data.parent_id)
            if parent is None:
                raise DeckNotFoundError(data.parent_id)
            if parent.owner_id != owner_id:
                raise DeckAccessDeniedError(data.parent_id, owner_id)

        deck = Deck(
            name=data.name,
            description=data.description,
            owner_id=owner_id,
            parent_id=data.parent_id,
        )

        if created_by:
            deck.set_created_by(created_by)

        self._session.add(deck)
        await self._session.flush()
        await self._session.refresh(deck)

        logger.info(
            "Created deck %s for user %s",
            deck.id,
            owner_id,
            extra={"deck_id": str(deck.id), "owner_id": str(owner_id)},
        )

        return deck

    async def get_by_id(
        self,
        deck_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> Deck | None:
        """
        Получить колоду по ID.

        Args:
            deck_id: UUID колоды
            include_deleted: Включать ли мягко удаленные колоды

        Returns:
            Экземпляр Deck если найден, None в противном случае
        """
        stmt = select(Deck).where(Deck.id == deck_id)

        if not include_deleted:
            stmt = stmt.where(Deck.deleted_at.is_(None))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self,
        deck_id: UUID,
        user_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> Deck | None:
        """
        Получить колоду по ID с проверкой владельца.

        Args:
            deck_id: UUID колоды
            user_id: UUID пользователя-владельца
            include_deleted: Включать ли мягко удаленные колоды

        Returns:
            Экземпляр Deck если найден и принадлежит пользователю, None в противном случае
        """
        stmt = select(Deck).where(
            and_(
                Deck.id == deck_id,
                Deck.owner_id == user_id,
            )
        )

        if not include_deleted:
            stmt = stmt.where(Deck.deleted_at.is_(None))

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_cards(
        self,
        deck_id: UUID,
        user_id: UUID,
    ) -> Deck | None:
        """
        Получить колоду с загруженными карточками.

        Args:
            deck_id: UUID колоды
            user_id: UUID пользователя-владельца

        Returns:
            Экземпляр Deck с карточками, None если не найден
        """
        stmt = (
            select(Deck)
            .options(selectinload(Deck.cards))
            .where(
                and_(
                    Deck.id == deck_id,
                    Deck.owner_id == user_id,
                    Deck.deleted_at.is_(None),
                )
            )
        )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        owner_id: UUID,
        *,
        parent_id: UUID | None = None,
        include_children: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Deck], int]:
        """
        Получить список колод пользователя.

        Args:
            owner_id: UUID владельца колод
            parent_id: Фильтр по родительской колоде (None для корневых)
            include_children: Загружать ли дочерние колоды
            offset: Количество записей для пропуска
            limit: Максимальное количество записей

        Returns:
            Кортеж (список колод, общее количество)
        """
        # Base conditions
        conditions = [
            Deck.owner_id == owner_id,
            Deck.deleted_at.is_(None),
        ]

        # Filter by parent (including root decks where parent_id is None)
        if parent_id is not None:
            conditions.append(Deck.parent_id == parent_id)

        # Count query
        count_stmt = select(func.count()).select_from(Deck).where(*conditions)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Data query
        stmt = select(Deck).where(*conditions).offset(offset).limit(limit)
        stmt = stmt.order_by(Deck.name)

        if include_children:
            stmt = stmt.options(selectinload(Deck.children))

        result = await self._session.execute(stmt)
        decks = list(result.scalars().all())

        return decks, total

    async def list_root_decks(
        self,
        owner_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Deck], int]:
        """
        Получить список корневых колод (без родителя).

        Args:
            owner_id: UUID владельца колод
            offset: Количество записей для пропуска
            limit: Максимальное количество записей

        Returns:
            Кортеж (список корневых колод, общее количество)
        """
        conditions = [
            Deck.owner_id == owner_id,
            Deck.deleted_at.is_(None),
            Deck.parent_id.is_(None),
        ]

        # Count query
        count_stmt = select(func.count()).select_from(Deck).where(*conditions)
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # Data query
        stmt = select(Deck).where(*conditions).order_by(Deck.name).offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        decks = list(result.scalars().all())

        return decks, total

    async def get_deck_tree(
        self,
        owner_id: UUID,
        root_deck_id: UUID | None = None,
    ) -> list[Deck]:
        """
        Получить иерархическое дерево колод.

        Args:
            owner_id: UUID владельца колод
            root_deck_id: UUID корневой колоды (None для всех корневых)

        Returns:
            Список корневых колод с загруженными дочерними
        """
        # Build recursive CTE for tree traversal
        if root_deck_id:
            # Start from specific deck
            stmt = (
                select(Deck)
                .options(selectinload(Deck.children))
                .where(
                    and_(
                        Deck.id == root_deck_id,
                        Deck.owner_id == owner_id,
                        Deck.deleted_at.is_(None),
                    )
                )
            )
        else:
            # Get all root decks with children
            stmt = (
                select(Deck)
                .options(selectinload(Deck.children))
                .where(
                    and_(
                        Deck.owner_id == owner_id,
                        Deck.parent_id.is_(None),
                        Deck.deleted_at.is_(None),
                    )
                )
                .order_by(Deck.name)
            )

        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        deck_id: UUID,
        user_id: UUID,
        data: DeckUpdate,
        *,
        updated_by: str | None = None,
    ) -> Deck:
        """
        Обновить колоду.

        Args:
            deck_id: UUID колоды для обновления
            user_id: UUID пользователя, выполняющего обновление
            data: Данные для обновления
            updated_by: Опциональный идентификатор для аудита

        Returns:
            Обновленный экземпляр Deck

        Raises:
            DeckNotFoundError: Колода не существует или нет доступа
            DeckCircularReferenceError: Изменение родителя создаст цикл
        """
        deck = await self.get_by_id_for_user(deck_id, user_id)
        if deck is None:
            raise DeckNotFoundError(deck_id)

        # Validate parent change if specified
        if data.parent_id is not None:
            if data.parent_id == deck_id:
                raise DeckCircularReferenceError(deck_id, data.parent_id)

            # Check for circular reference
            if await self._would_create_cycle(deck_id, data.parent_id, user_id):
                raise DeckCircularReferenceError(deck_id, data.parent_id)

            # Validate parent exists and belongs to user
            parent = await self.get_by_id_for_user(data.parent_id, user_id)
            if parent is None:
                raise DeckNotFoundError(data.parent_id)

        # Apply updates
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(deck, field, value)

        if updated_by:
            deck.set_updated_by(updated_by)

        await self._session.flush()
        await self._session.refresh(deck)

        logger.info(
            "Updated deck %s",
            deck_id,
            extra={"deck_id": str(deck_id), "updated_fields": list(update_data.keys())},
        )

        return deck

    async def delete(
        self,
        deck_id: UUID,
        user_id: UUID,
        *,
        hard_delete: bool = False,
    ) -> bool:
        """
        Удалить колоду.

        По умолчанию выполняет мягкое удаление. Дочерние колоды также удаляются.

        Args:
            deck_id: UUID колоды для удаления
            user_id: UUID пользователя, выполняющего удаление
            hard_delete: Выполнить ли жесткое удаление

        Returns:
            True если колода удалена, False если не найдена

        Raises:
            DeckNotFoundError: Колода не существует или нет доступа
        """
        deck = await self.get_by_id_for_user(deck_id, user_id)
        if deck is None:
            raise DeckNotFoundError(deck_id)

        if hard_delete:
            await self._session.delete(deck)
        else:
            deck.soft_delete()
            # Also soft-delete children
            await self._soft_delete_children(deck_id, user_id)

        await self._session.flush()

        logger.info(
            "Deleted deck %s (hard=%s)",
            deck_id,
            hard_delete,
            extra={"deck_id": str(deck_id), "hard_delete": hard_delete},
        )

        return True

    async def restore(
        self,
        deck_id: UUID,
        user_id: UUID,
    ) -> Deck:
        """
        Восстановить мягко удаленную колоду.

        Args:
            deck_id: UUID колоды для восстановления
            user_id: UUID пользователя, выполняющего восстановление

        Returns:
            Восстановленный экземпляр Deck

        Raises:
            DeckNotFoundError: Колода не существует или нет доступа
        """
        deck = await self.get_by_id_for_user(deck_id, user_id, include_deleted=True)
        if deck is None:
            raise DeckNotFoundError(deck_id)

        deck.restore()
        await self._session.flush()
        await self._session.refresh(deck)

        logger.info(
            "Restored deck %s",
            deck_id,
            extra={"deck_id": str(deck_id)},
        )

        return deck

    async def move_to_parent(
        self,
        deck_id: UUID,
        new_parent_id: UUID | None,
        user_id: UUID,
    ) -> Deck:
        """
        Переместить колоду к новому родителю.

        Args:
            deck_id: UUID колоды для перемещения
            new_parent_id: UUID нового родителя (None для корневого уровня)
            user_id: UUID пользователя, выполняющего перемещение

        Returns:
            Перемещенный экземпляр Deck

        Raises:
            DeckNotFoundError: Колода или новый родитель не существует
            DeckCircularReferenceError: Перемещение создаст цикл
        """
        return await self.update(
            deck_id,
            user_id,
            DeckUpdate(parent_id=new_parent_id),
        )

    async def get_ancestors(
        self,
        deck_id: UUID,
        user_id: UUID,
    ) -> list[Deck]:
        """
        Получить всех предков колоды (цепочку родителей до корня).

        Args:
            deck_id: UUID колоды
            user_id: UUID пользователя

        Returns:
            Список колод-предков от непосредственного родителя до корня
        """
        ancestors: list[Deck] = []
        current_id = deck_id

        while current_id:
            deck = await self.get_by_id_for_user(current_id, user_id)
            if deck is None:
                break
            if deck.parent_id:
                parent = await self.get_by_id_for_user(deck.parent_id, user_id)
                if parent:
                    ancestors.append(parent)
                current_id = deck.parent_id
            else:
                break

        return ancestors

    async def get_descendants(
        self,
        deck_id: UUID,
        user_id: UUID,
    ) -> list[Deck]:
        """
        Получить всех потомков колоды (рекурсивно).

        Args:
            deck_id: UUID колоды
            user_id: UUID пользователя

        Returns:
            Список всех колод-потомков
        """
        descendants: list[Deck] = []
        await self._collect_descendants(deck_id, user_id, descendants)
        return descendants

    async def _collect_descendants(
        self,
        deck_id: UUID,
        user_id: UUID,
        result: list[Deck],
    ) -> None:
        """
        Рекурсивно собрать всех потомков колоды.

        Args:
            deck_id: UUID колоды
            user_id: UUID пользователя
            result: Список для добавления потомков
        """
        stmt = select(Deck).where(
            and_(
                Deck.parent_id == deck_id,
                Deck.owner_id == user_id,
                Deck.deleted_at.is_(None),
            )
        )

        db_result = await self._session.execute(stmt)
        children = list(db_result.scalars().all())

        for child in children:
            result.append(child)
            await self._collect_descendants(child.id, user_id, result)

    async def _would_create_cycle(
        self,
        deck_id: UUID,
        new_parent_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Проверить, создаст ли новый родитель циклическую ссылку.

        Args:
            deck_id: UUID изменяемой колоды
            new_parent_id: UUID предлагаемого нового родителя
            user_id: UUID пользователя

        Returns:
            True если изменение создаст цикл, False в противном случае
        """
        # Walk up the parent chain from new_parent_id
        current_id = new_parent_id
        visited: set[UUID] = set()

        while current_id:
            if current_id == deck_id:
                return True
            if current_id in visited:
                # Already a cycle in the data (shouldn't happen)
                return True
            visited.add(current_id)

            deck = await self.get_by_id_for_user(current_id, user_id)
            if deck is None:
                break
            current_id = deck.parent_id  # type: ignore[assignment]

        return False

    async def _soft_delete_children(
        self,
        deck_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Рекурсивно мягко удалить все дочерние колоды.

        Args:
            deck_id: UUID родительской колоды
            user_id: UUID пользователя
        """
        stmt = select(Deck).where(
            and_(
                Deck.parent_id == deck_id,
                Deck.owner_id == user_id,
                Deck.deleted_at.is_(None),
            )
        )

        result = await self._session.execute(stmt)
        children = list(result.scalars().all())

        for child in children:
            child.soft_delete()
            await self._soft_delete_children(child.id, user_id)
