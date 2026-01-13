"""Base repository pattern with async CRUD operations."""

import builtins
import uuid
from abc import ABC
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import PaginatedResponse, PaginationParams

# Type variable for SQLAlchemy models
ModelT = TypeVar("ModelT")

# Type variable for create schema
CreateSchemaT = TypeVar("CreateSchemaT")

# Type variable for update schema
UpdateSchemaT = TypeVar("UpdateSchemaT")


class BaseRepository(Generic[ModelT, CreateSchemaT, UpdateSchemaT], ABC):
    """Abstract base repository providing async CRUD operations.

    This repository implements the repository pattern for database access,
    providing a clean abstraction over SQLAlchemy operations.

    Type Parameters:
        ModelT: The SQLAlchemy model class.
        CreateSchemaT: The Pydantic schema for create operations.
        UpdateSchemaT: The Pydantic schema for update operations.

    Example:
        class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
            def __init__(self, session: AsyncSession):
                super().__init__(session, User)

        # Usage
        repo = UserRepository(session)
        user = await repo.create(UserCreate(name="John", email="john@example.com"))
        users = await repo.list(page=1, page_size=10)
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        """Initialize the repository.

        Args:
            session: The async SQLAlchemy session.
            model: The SQLAlchemy model class.
        """
        self._session = session
        self._model = model

    @property
    def session(self) -> AsyncSession:
        """Get the current database session.

        Returns:
            The async SQLAlchemy session.
        """
        return self._session

    @property
    def model(self) -> type[ModelT]:
        """Get the model class.

        Returns:
            The SQLAlchemy model class.
        """
        return self._model

    async def create(self, data: CreateSchemaT) -> ModelT:
        """Create a new record.

        Args:
            data: The data for creating the record.

        Returns:
            The created model instance.
        """
        if hasattr(data, "model_dump"):
            # CreateSchemaT is expected to be a Pydantic model with model_dump
            create_data = data.model_dump(exclude_unset=True)
        else:
            # Fallback for dict-like objects
            create_data = dict(data)  # type: ignore[call-overload]

        instance = self._model(**create_data)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def create_many(self, data_list: list[CreateSchemaT]) -> list[ModelT]:
        """Create multiple records.

        Args:
            data_list: List of data for creating records.

        Returns:
            List of created model instances.
        """
        instances = []
        for data in data_list:
            if hasattr(data, "model_dump"):
                # CreateSchemaT is expected to be a Pydantic model
                create_data = data.model_dump(exclude_unset=True)
            else:
                create_data = dict(data)  # type: ignore[call-overload]
            instance = self._model(**create_data)
            instances.append(instance)

        self._session.add_all(instances)
        await self._session.flush()

        for instance in instances:
            await self._session.refresh(instance)

        return instances

    async def get(self, **filters: Any) -> ModelT | None:
        """Get a single record by filters.

        Args:
            **filters: Keyword arguments for filtering.

        Returns:
            The model instance if found, None otherwise.
        """
        query = select(self._model)
        query = self._apply_filters(query, filters)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        """Get a record by its ID.

        Args:
            id: The UUID of the record.

        Returns:
            The model instance if found, None otherwise.
        """
        return await self.get(id=id)

    async def get_or_raise(self, **filters: Any) -> ModelT:
        """Get a single record by filters or raise an exception.

        Args:
            **filters: Keyword arguments for filtering.

        Returns:
            The model instance.

        Raises:
            ValueError: If no record is found.
        """
        instance = await self.get(**filters)
        if instance is None:
            raise ValueError(f"{self._model.__name__} not found with filters: {filters}")
        return instance

    async def get_by_id_or_raise(self, id: uuid.UUID) -> ModelT:
        """Get a record by its ID or raise an exception.

        Args:
            id: The UUID of the record.

        Returns:
            The model instance.

        Raises:
            ValueError: If no record is found.
        """
        return await self.get_or_raise(id=id)

    async def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        order_by: builtins.list[Any] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        include_deleted: bool = False,
    ) -> Sequence[ModelT]:
        """List records with optional filtering, ordering, and pagination.

        Args:
            filters: Dictionary of filter conditions.
            order_by: List of columns to order by.
            offset: Number of records to skip.
            limit: Maximum number of records to return.
            include_deleted: Whether to include soft-deleted records.

        Returns:
            Sequence of model instances.
        """
        query = select(self._model)

        # Apply soft delete filter if model supports it
        if not include_deleted and hasattr(self._model, "deleted_at"):
            # hasattr check ensures attribute exists at runtime
            query = query.where(self._model.deleted_at.is_(None))  # type: ignore[attr-defined]

        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)

        # Apply ordering
        if order_by:
            query = query.order_by(*order_by)
        elif hasattr(self._model, "created_at"):
            # hasattr check ensures attribute exists at runtime
            query = query.order_by(self._model.created_at.desc())  # type: ignore[attr-defined]

        # Apply pagination
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        result = await self._session.execute(query)
        return result.scalars().all()

    async def list_paginated(
        self,
        params: PaginationParams,
        *,
        filters: dict[str, Any] | None = None,
        order_by: builtins.list[Any] | None = None,
        include_deleted: bool = False,
    ) -> PaginatedResponse[ModelT]:
        """List records with pagination.

        Args:
            params: Pagination parameters.
            filters: Dictionary of filter conditions.
            order_by: List of columns to order by.
            include_deleted: Whether to include soft-deleted records.

        Returns:
            Paginated response with items and metadata.
        """
        # Get total count
        total = await self.count(filters=filters, include_deleted=include_deleted)

        # Get items
        items = await self.list(
            filters=filters,
            order_by=order_by,
            offset=params.offset,
            limit=params.limit,
            include_deleted=include_deleted,
        )

        return PaginatedResponse.create(
            items=list(items),
            total=total,
            params=params,
        )

    async def count(
        self,
        *,
        filters: dict[str, Any] | None = None,
        include_deleted: bool = False,
    ) -> int:
        """Count records matching the filters.

        Args:
            filters: Dictionary of filter conditions.
            include_deleted: Whether to include soft-deleted records.

        Returns:
            The count of matching records.
        """
        query = select(func.count()).select_from(self._model)

        # Apply soft delete filter if model supports it
        if not include_deleted and hasattr(self._model, "deleted_at"):
            # hasattr check ensures attribute exists at runtime
            query = query.where(self._model.deleted_at.is_(None))  # type: ignore[attr-defined]

        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)

        result = await self._session.execute(query)
        return result.scalar_one()

    async def exists(
        self,
        *,
        filters: dict[str, Any] | None = None,
        include_deleted: bool = False,
    ) -> bool:
        """Check if any records match the filters.

        Args:
            filters: Dictionary of filter conditions.
            include_deleted: Whether to include soft-deleted records.

        Returns:
            True if any matching records exist, False otherwise.
        """
        count = await self.count(filters=filters, include_deleted=include_deleted)
        return count > 0

    async def update(
        self,
        instance: ModelT,
        data: UpdateSchemaT,
        *,
        exclude_unset: bool = True,
    ) -> ModelT:
        """Update an existing record.

        Args:
            instance: The model instance to update.
            data: The update data.
            exclude_unset: Whether to exclude unset fields from the update.

        Returns:
            The updated model instance.
        """
        if hasattr(data, "model_dump"):
            # UpdateSchemaT is expected to be a Pydantic model
            update_data = data.model_dump(exclude_unset=exclude_unset)
        else:
            update_data = dict(data)  # type: ignore[call-overload]

        for field, value in update_data.items():
            if hasattr(instance, field):
                setattr(instance, field, value)

        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update_by_id(
        self,
        id: uuid.UUID,
        data: UpdateSchemaT,
        *,
        exclude_unset: bool = True,
    ) -> ModelT | None:
        """Update a record by its ID.

        Args:
            id: The UUID of the record.
            data: The update data.
            exclude_unset: Whether to exclude unset fields from the update.

        Returns:
            The updated model instance if found, None otherwise.
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return None
        return await self.update(instance, data, exclude_unset=exclude_unset)

    async def delete(self, instance: ModelT) -> None:
        """Permanently delete a record.

        Args:
            instance: The model instance to delete.
        """
        await self._session.delete(instance)
        await self._session.flush()

    async def delete_by_id(self, id: uuid.UUID) -> bool:
        """Permanently delete a record by its ID.

        Args:
            id: The UUID of the record.

        Returns:
            True if the record was deleted, False if not found.
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return False
        await self.delete(instance)
        return True

    async def soft_delete(self, instance: ModelT) -> ModelT:
        """Soft delete a record by setting deleted_at.

        Args:
            instance: The model instance to soft delete.

        Returns:
            The soft-deleted model instance.

        Raises:
            AttributeError: If the model doesn't support soft delete.
        """
        if not hasattr(instance, "deleted_at"):
            raise AttributeError(f"{self._model.__name__} does not support soft delete")

        # hasattr check ensures attribute exists at runtime
        instance.deleted_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def soft_delete_by_id(self, id: uuid.UUID) -> ModelT | None:
        """Soft delete a record by its ID.

        Args:
            id: The UUID of the record.

        Returns:
            The soft-deleted model instance if found, None otherwise.
        """
        instance = await self.get_by_id(id)
        if instance is None:
            return None
        return await self.soft_delete(instance)

    async def restore(self, instance: ModelT) -> ModelT:
        """Restore a soft-deleted record.

        Args:
            instance: The model instance to restore.

        Returns:
            The restored model instance.

        Raises:
            AttributeError: If the model doesn't support soft delete.
        """
        if not hasattr(instance, "deleted_at"):
            raise AttributeError(f"{self._model.__name__} does not support soft delete")

        # hasattr check ensures attribute exists at runtime
        instance.deleted_at = None
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def restore_by_id(self, id: uuid.UUID) -> ModelT | None:
        """Restore a soft-deleted record by its ID.

        Args:
            id: The UUID of the record.

        Returns:
            The restored model instance if found, None otherwise.
        """
        # Need to include deleted to find soft-deleted records
        instance = await self.get(id=id)
        if instance is None:
            return None
        return await self.restore(instance)

    def _apply_filters(
        self,
        query: Select,
        filters: dict[str, Any],
    ) -> Select:
        """Apply filters to a query.

        Supports various filter operations through special suffixes:
            - field__eq: Equal (default)
            - field__ne: Not equal
            - field__gt: Greater than
            - field__gte: Greater than or equal
            - field__lt: Less than
            - field__lte: Less than or equal
            - field__in: In list
            - field__not_in: Not in list
            - field__like: LIKE pattern
            - field__ilike: Case-insensitive LIKE
            - field__is_null: IS NULL (value should be True/False)

        Args:
            query: The SQLAlchemy query to filter.
            filters: Dictionary of filter conditions.

        Returns:
            The filtered query.
        """
        for key, value in filters.items():
            if value is None:
                continue

            # Parse filter operation
            if "__" in key:
                field_name, operation = key.rsplit("__", 1)
            else:
                field_name = key
                operation = "eq"

            # Get the model column
            if not hasattr(self._model, field_name):
                continue

            column = getattr(self._model, field_name)

            # Apply the filter
            match operation:
                case "eq":
                    query = query.where(column == value)
                case "ne":
                    query = query.where(column != value)
                case "gt":
                    query = query.where(column > value)
                case "gte":
                    query = query.where(column >= value)
                case "lt":
                    query = query.where(column < value)
                case "lte":
                    query = query.where(column <= value)
                case "in":
                    query = query.where(column.in_(value))
                case "not_in":
                    query = query.where(column.not_in(value))
                case "like":
                    query = query.where(column.like(value))
                case "ilike":
                    query = query.where(column.ilike(value))
                case "is_null":
                    if value:
                        query = query.where(column.is_(None))
                    else:
                        query = query.where(column.is_not(None))
                case _:
                    # Default to equality
                    query = query.where(column == value)

        return query


class ReadOnlyRepository(Generic[ModelT], ABC):
    """Read-only repository for query operations only.

    Use this when you need to expose read-only access to data,
    for example in CQRS patterns or for aggregate views.

    Example:
        class UserQueryRepository(ReadOnlyRepository[User]):
            def __init__(self, session: AsyncSession):
                super().__init__(session, User)

            async def get_active_users(self) -> Sequence[User]:
                return await self.list(filters={"is_active": True})
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        """Initialize the read-only repository.

        Args:
            session: The async SQLAlchemy session.
            model: The SQLAlchemy model class.
        """
        self._session = session
        self._model = model

    @property
    def session(self) -> AsyncSession:
        """Get the current database session."""
        return self._session

    @property
    def model(self) -> type[ModelT]:
        """Get the model class."""
        return self._model

    async def get(self, **filters: Any) -> ModelT | None:
        """Get a single record by filters."""
        query = select(self._model)
        for key, value in filters.items():
            if hasattr(self._model, key) and value is not None:
                query = query.where(getattr(self._model, key) == value)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        """Get a record by its ID."""
        return await self.get(id=id)

    async def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        order_by: builtins.list[Any] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Sequence[ModelT]:
        """List records with optional filtering and pagination."""
        query = select(self._model)

        if filters:
            for key, value in filters.items():
                if hasattr(self._model, key) and value is not None:
                    query = query.where(getattr(self._model, key) == value)

        if order_by:
            query = query.order_by(*order_by)

        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self, *, filters: dict[str, Any] | None = None) -> int:
        """Count records matching the filters."""
        query = select(func.count()).select_from(self._model)

        if filters:
            for key, value in filters.items():
                if hasattr(self._model, key) and value is not None:
                    query = query.where(getattr(self._model, key) == value)

        result = await self._session.execute(query)
        return result.scalar_one()

    async def exists(self, *, filters: dict[str, Any] | None = None) -> bool:
        """Check if any records match the filters."""
        count = await self.count(filters=filters)
        return count > 0
