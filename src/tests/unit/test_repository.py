"""Unit tests for BaseRepository and ReadOnlyRepository classes."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from src.shared.repository import BaseRepository, ReadOnlyRepository
from src.shared.schemas import PaginatedResponse, PaginationParams

# ==================== Test Models ====================


class Base(DeclarativeBase):
    """Test declarative base."""

    pass


class SampleModel(Base):
    """Simple test model without soft delete support."""

    __tablename__ = "sample_models"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    value = Column(Integer)


class SampleModelWithSoftDelete(Base):
    """Test model with soft delete support."""

    __tablename__ = "sample_models_soft_delete"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class SampleModelWithTimestamps(Base):
    """Test model with created_at for ordering tests."""

    __tablename__ = "sample_models_timestamps"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    created_at = Column(DateTime, default=datetime.now)


# ==================== Pydantic Schemas ====================


class CreateSchema(BaseModel):
    """Pydantic schema for create operations."""

    name: str
    value: int = 0


class UpdateSchema(BaseModel):
    """Pydantic schema for update operations."""

    name: str | None = None
    value: int | None = None


# ==================== Concrete Repository Classes ====================


class ConcreteRepository(BaseRepository[SampleModel, CreateSchema, UpdateSchema]):
    """Concrete implementation of BaseRepository for testing."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SampleModel)


class ConcreteRepositoryWithSoftDelete(
    BaseRepository[SampleModelWithSoftDelete, CreateSchema, UpdateSchema]
):
    """Concrete repository with soft delete support."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SampleModelWithSoftDelete)


class ConcreteRepositoryWithTimestamps(
    BaseRepository[SampleModelWithTimestamps, CreateSchema, UpdateSchema]
):
    """Concrete repository with timestamps."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SampleModelWithTimestamps)


class ConcreteReadOnlyRepository(ReadOnlyRepository[SampleModel]):
    """Concrete implementation of ReadOnlyRepository for testing."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, SampleModel)


# ==================== Fixtures ====================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session: AsyncMock) -> ConcreteRepository:
    """Create a ConcreteRepository instance with mocked session."""
    return ConcreteRepository(mock_session)


@pytest.fixture
def repository_soft_delete(mock_session: AsyncMock) -> ConcreteRepositoryWithSoftDelete:
    """Create a repository with soft delete support."""
    return ConcreteRepositoryWithSoftDelete(mock_session)


@pytest.fixture
def repository_timestamps(mock_session: AsyncMock) -> ConcreteRepositoryWithTimestamps:
    """Create a repository with timestamps support."""
    return ConcreteRepositoryWithTimestamps(mock_session)


@pytest.fixture
def readonly_repository(mock_session: AsyncMock) -> ConcreteReadOnlyRepository:
    """Create a ConcreteReadOnlyRepository instance with mocked session."""
    return ConcreteReadOnlyRepository(mock_session)


@pytest.fixture
def mock_instance() -> MagicMock:
    """Create a mock model instance."""
    instance = MagicMock(spec=SampleModel)
    instance.id = 1
    instance.name = "test"
    instance.value = 100
    return instance


@pytest.fixture
def mock_instance_soft_delete() -> MagicMock:
    """Create a mock model instance with soft delete support."""
    instance = MagicMock(spec=SampleModelWithSoftDelete)
    instance.id = 1
    instance.name = "test"
    instance.deleted_at = None
    return instance


# ==================== BaseRepository Tests ====================


class TestBaseRepositoryProperties:
    """Tests for BaseRepository properties."""

    def test_session_property(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test that session property returns the correct session."""
        assert repository.session is mock_session

    def test_model_property(self, repository: ConcreteRepository):
        """Test that model property returns the correct model class."""
        assert repository.model is SampleModel


class TestBaseRepositoryCreate:
    """Tests for BaseRepository.create method."""

    @pytest.mark.asyncio
    async def test_create_with_pydantic_schema(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test creating a record with Pydantic schema."""
        data = CreateSchema(name="test", value=42)

        # Setup mock to capture the created instance
        created_instance = None

        def capture_add(instance):
            nonlocal created_instance
            created_instance = instance

        mock_session.add.side_effect = capture_add

        result = await repository.create(data)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()
        assert created_instance is not None
        assert created_instance.name == "test"
        assert created_instance.value == 42

    @pytest.mark.asyncio
    async def test_create_with_dict_object(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test creating a record with a plain dict."""
        data = {"name": "dict_test", "value": 99}

        await repository.create(data)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()


class TestBaseRepositoryCreateMany:
    """Tests for BaseRepository.create_many method."""

    @pytest.mark.asyncio
    async def test_create_many_with_pydantic_schemas(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test creating multiple records with Pydantic schemas."""
        data_list = [
            CreateSchema(name="test1", value=1),
            CreateSchema(name="test2", value=2),
            CreateSchema(name="test3", value=3),
        ]

        result = await repository.create_many(data_list)

        mock_session.add_all.assert_called_once()
        # Check that add_all was called with 3 instances
        call_args = mock_session.add_all.call_args[0][0]
        assert len(call_args) == 3
        mock_session.flush.assert_called_once()
        # refresh should be called for each instance
        assert mock_session.refresh.call_count == 3

    @pytest.mark.asyncio
    async def test_create_many_with_empty_list(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test creating with an empty list."""
        result = await repository.create_many([])

        mock_session.add_all.assert_called_once_with([])
        mock_session.flush.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_create_many_with_dict_objects(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test creating multiple records with plain dicts."""
        data_list = [
            {"name": "item1", "value": 10},
            {"name": "item2", "value": 20},
        ]

        result = await repository.create_many(data_list)

        mock_session.add_all.assert_called_once()
        mock_session.flush.assert_called_once()


class TestBaseRepositoryGet:
    """Tests for BaseRepository.get method."""

    @pytest.mark.asyncio
    async def test_get_found(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test getting a record that exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        result = await repository.get(id=1)

        assert result is mock_instance
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test getting a record that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get(id=999)

        assert result is None


class TestBaseRepositoryGetById:
    """Tests for BaseRepository.get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test getting a record by ID that exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository.get_by_id(test_uuid)

        assert result is mock_instance


class TestBaseRepositoryGetOrRaise:
    """Tests for BaseRepository.get_or_raise method."""

    @pytest.mark.asyncio
    async def test_get_or_raise_found(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test get_or_raise when record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        result = await repository.get_or_raise(id=1)

        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_get_or_raise_not_found(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test get_or_raise raises ValueError when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(ValueError) as exc_info:
            await repository.get_or_raise(id=999)

        assert "SampleModel not found" in str(exc_info.value)
        assert "id" in str(exc_info.value)


class TestBaseRepositoryGetByIdOrRaise:
    """Tests for BaseRepository.get_by_id_or_raise method."""

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_found(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test get_by_id_or_raise when record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository.get_by_id_or_raise(test_uuid)

        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_get_by_id_or_raise_not_found(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test get_by_id_or_raise raises ValueError when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        with pytest.raises(ValueError):
            await repository.get_by_id_or_raise(test_uuid)


class TestBaseRepositoryList:
    """Tests for BaseRepository.list method."""

    @pytest.mark.asyncio
    async def test_list_basic(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test basic list without filters."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_instance]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list()

        assert len(result) == 1
        assert result[0] is mock_instance

    @pytest.mark.asyncio
    async def test_list_with_filters(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test list with filters."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_instance]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list(filters={"name": "test"})

        assert len(result) == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_offset_and_limit(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test list with pagination parameters."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list(offset=10, limit=5)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_order_by(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test list with custom ordering."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository.list(order_by=[SampleModel.name])

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_soft_delete_filter(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
    ):
        """Test list excludes soft-deleted records by default."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository_soft_delete.list()

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_include_deleted(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
    ):
        """Test list can include soft-deleted records."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository_soft_delete.list(include_deleted=True)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_default_order_by_created_at(
        self,
        repository_timestamps: ConcreteRepositoryWithTimestamps,
        mock_session: AsyncMock,
    ):
        """Test list uses created_at for default ordering when available."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repository_timestamps.list()

        mock_session.execute.assert_called_once()


class TestBaseRepositoryListPaginated:
    """Tests for BaseRepository.list_paginated method."""

    @pytest.mark.asyncio
    async def test_list_paginated(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test paginated list."""
        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 100

        # Mock list result
        mock_list_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_instance]
        mock_list_result.scalars.return_value = mock_scalars

        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        params = PaginationParams(page=1, page_size=10)
        result = await repository.list_paginated(params)

        assert isinstance(result, PaginatedResponse)
        assert result.total == 100
        assert result.page == 1
        assert result.page_size == 10
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_list_paginated_with_filters(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test paginated list with filters."""
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 5

        mock_list_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_list_result.scalars.return_value = mock_scalars

        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        params = PaginationParams(page=2, page_size=20)
        result = await repository.list_paginated(
            params, filters={"name": "test"}, order_by=[SampleModel.name]
        )

        assert result.total == 5
        assert result.page == 2
        assert result.page_size == 20


class TestBaseRepositoryCount:
    """Tests for BaseRepository.count method."""

    @pytest.mark.asyncio
    async def test_count_all(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test count all records."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result

        result = await repository.count()

        assert result == 42

    @pytest.mark.asyncio
    async def test_count_with_filters(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test count with filters."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 10
        mock_session.execute.return_value = mock_result

        result = await repository.count(filters={"name": "test"})

        assert result == 10

    @pytest.mark.asyncio
    async def test_count_excludes_soft_deleted(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
    ):
        """Test count excludes soft-deleted records by default."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute.return_value = mock_result

        result = await repository_soft_delete.count()

        assert result == 5

    @pytest.mark.asyncio
    async def test_count_include_deleted(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
    ):
        """Test count can include soft-deleted records."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 8
        mock_session.execute.return_value = mock_result

        result = await repository_soft_delete.count(include_deleted=True)

        assert result == 8


class TestBaseRepositoryExists:
    """Tests for BaseRepository.exists method."""

    @pytest.mark.asyncio
    async def test_exists_true(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test exists returns True when records exist."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await repository.exists(filters={"name": "test"})

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test exists returns False when no records exist."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        result = await repository.exists(filters={"name": "nonexistent"})

        assert result is False


class TestBaseRepositoryUpdate:
    """Tests for BaseRepository.update method."""

    @pytest.mark.asyncio
    async def test_update_with_pydantic_schema(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test updating a record with Pydantic schema."""
        update_data = UpdateSchema(name="updated_name")

        result = await repository.update(mock_instance, update_data)

        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(mock_instance)
        assert mock_instance.name == "updated_name"

    @pytest.mark.asyncio
    async def test_update_exclude_unset_true(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test update only modifies set fields when exclude_unset=True."""
        original_value = mock_instance.value
        update_data = UpdateSchema(name="new_name")  # value is not set

        result = await repository.update(mock_instance, update_data, exclude_unset=True)

        assert mock_instance.name == "new_name"
        # value should not be changed because it wasn't set in update_data

    @pytest.mark.asyncio
    async def test_update_exclude_unset_false(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test update modifies all fields when exclude_unset=False."""
        update_data = UpdateSchema(name="new_name")  # value defaults to None

        result = await repository.update(
            mock_instance, update_data, exclude_unset=False
        )

        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_dict_object(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test updating with a plain dict."""
        update_data = {"name": "dict_updated"}

        result = await repository.update(mock_instance, update_data)

        assert mock_instance.name == "dict_updated"
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_ignores_nonexistent_fields(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test update ignores fields that don't exist on the model."""
        # Remove the nonexistent_field attribute to simulate it not existing
        mock_instance.nonexistent_field = None
        del mock_instance.nonexistent_field

        class UpdateWithExtra(BaseModel):
            name: str = "updated"
            nonexistent_field: str = "ignored"

        update_data = UpdateWithExtra()

        # Should not raise an error
        result = await repository.update(mock_instance, update_data)
        mock_session.flush.assert_called_once()


class TestBaseRepositoryUpdateById:
    """Tests for BaseRepository.update_by_id method."""

    @pytest.mark.asyncio
    async def test_update_by_id_found(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test update_by_id when record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        update_data = UpdateSchema(name="updated")

        result = await repository.update_by_id(test_uuid, update_data)

        assert result is mock_instance
        assert mock_instance.name == "updated"

    @pytest.mark.asyncio
    async def test_update_by_id_not_found(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test update_by_id returns None when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        update_data = UpdateSchema(name="updated")

        result = await repository.update_by_id(test_uuid, update_data)

        assert result is None


class TestBaseRepositoryDelete:
    """Tests for BaseRepository.delete method."""

    @pytest.mark.asyncio
    async def test_delete(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test deleting a record."""
        await repository.delete(mock_instance)

        mock_session.delete.assert_called_once_with(mock_instance)
        mock_session.flush.assert_called_once()


class TestBaseRepositoryDeleteById:
    """Tests for BaseRepository.delete_by_id method."""

    @pytest.mark.asyncio
    async def test_delete_by_id_found(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test delete_by_id when record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository.delete_by_id(test_uuid)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_instance)

    @pytest.mark.asyncio
    async def test_delete_by_id_not_found(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test delete_by_id returns False when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository.delete_by_id(test_uuid)

        assert result is False
        mock_session.delete.assert_not_called()


class TestBaseRepositorySoftDelete:
    """Tests for BaseRepository.soft_delete method."""

    @pytest.mark.asyncio
    async def test_soft_delete(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
        mock_instance_soft_delete: MagicMock,
    ):
        """Test soft deleting a record."""
        result = await repository_soft_delete.soft_delete(mock_instance_soft_delete)

        assert mock_instance_soft_delete.deleted_at is not None
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(mock_instance_soft_delete)

    @pytest.mark.asyncio
    async def test_soft_delete_without_support(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test soft_delete raises error on model without soft delete support."""
        # Ensure the mock doesn't have deleted_at attribute
        del mock_instance.deleted_at

        with pytest.raises(AttributeError) as exc_info:
            await repository.soft_delete(mock_instance)

        assert "does not support soft delete" in str(exc_info.value)


class TestBaseRepositorySoftDeleteById:
    """Tests for BaseRepository.soft_delete_by_id method."""

    @pytest.mark.asyncio
    async def test_soft_delete_by_id_found(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
        mock_instance_soft_delete: MagicMock,
    ):
        """Test soft_delete_by_id when record exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance_soft_delete
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository_soft_delete.soft_delete_by_id(test_uuid)

        assert result is mock_instance_soft_delete
        assert mock_instance_soft_delete.deleted_at is not None

    @pytest.mark.asyncio
    async def test_soft_delete_by_id_not_found(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
    ):
        """Test soft_delete_by_id returns None when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository_soft_delete.soft_delete_by_id(test_uuid)

        assert result is None


class TestBaseRepositoryRestore:
    """Tests for BaseRepository.restore method."""

    @pytest.mark.asyncio
    async def test_restore(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
        mock_instance_soft_delete: MagicMock,
    ):
        """Test restoring a soft-deleted record."""
        mock_instance_soft_delete.deleted_at = datetime.now(UTC)

        result = await repository_soft_delete.restore(mock_instance_soft_delete)

        assert mock_instance_soft_delete.deleted_at is None
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(mock_instance_soft_delete)

    @pytest.mark.asyncio
    async def test_restore_without_support(
        self,
        repository: ConcreteRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test restore raises error on model without soft delete support."""
        # Ensure the mock doesn't have deleted_at attribute
        del mock_instance.deleted_at

        with pytest.raises(AttributeError) as exc_info:
            await repository.restore(mock_instance)

        assert "does not support soft delete" in str(exc_info.value)


class TestBaseRepositoryRestoreById:
    """Tests for BaseRepository.restore_by_id method."""

    @pytest.mark.asyncio
    async def test_restore_by_id_found(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
        mock_instance_soft_delete: MagicMock,
    ):
        """Test restore_by_id when record exists."""
        mock_instance_soft_delete.deleted_at = datetime.now(UTC)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance_soft_delete
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository_soft_delete.restore_by_id(test_uuid)

        assert result is mock_instance_soft_delete
        assert mock_instance_soft_delete.deleted_at is None

    @pytest.mark.asyncio
    async def test_restore_by_id_not_found(
        self,
        repository_soft_delete: ConcreteRepositoryWithSoftDelete,
        mock_session: AsyncMock,
    ):
        """Test restore_by_id returns None when record doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await repository_soft_delete.restore_by_id(test_uuid)

        assert result is None


class TestBaseRepositoryApplyFilters:
    """Tests for BaseRepository._apply_filters method."""

    @pytest.mark.asyncio
    async def test_filter_eq(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test equality filter."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.get(name="test")

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_ne(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test not equal filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__ne": "excluded"})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_gt(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test greater than filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"value__gt": 10})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_gte(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test greater than or equal filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"value__gte": 10})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_lt(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test less than filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"value__lt": 100})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_lte(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test less than or equal filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"value__lte": 100})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_in(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test IN filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__in": ["test1", "test2", "test3"]})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_not_in(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test NOT IN filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__not_in": ["excluded1", "excluded2"]})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_like(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test LIKE filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__like": "%test%"})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_ilike(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test case-insensitive LIKE filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__ilike": "%TEST%"})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_is_null_true(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test IS NULL filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__is_null": True})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_is_null_false(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test IS NOT NULL filter."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__is_null": False})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_none_value_skipped(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test that None values in filters are skipped."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name": None, "value": 10})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_nonexistent_field_skipped(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test that filters for non-existent fields are skipped."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"nonexistent_field": "value"})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_unknown_operation_defaults_to_eq(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test that unknown filter operations default to equality."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(filters={"name__unknown_op": "test"})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_multiple_filters(
        self, repository: ConcreteRepository, mock_session: AsyncMock
    ):
        """Test applying multiple filters at once."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        await repository.list(
            filters={
                "name__like": "%test%",
                "value__gte": 10,
                "value__lte": 100,
            }
        )

        mock_session.execute.assert_called_once()


# ==================== ReadOnlyRepository Tests ====================


class TestReadOnlyRepositoryProperties:
    """Tests for ReadOnlyRepository properties."""

    def test_session_property(
        self, readonly_repository: ConcreteReadOnlyRepository, mock_session: AsyncMock
    ):
        """Test that session property returns the correct session."""
        assert readonly_repository.session is mock_session

    def test_model_property(self, readonly_repository: ConcreteReadOnlyRepository):
        """Test that model property returns the correct model class."""
        assert readonly_repository.model is SampleModel


class TestReadOnlyRepositoryGet:
    """Tests for ReadOnlyRepository.get method."""

    @pytest.mark.asyncio
    async def test_get_found(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test getting a record that exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.get(id=1)

        assert result is mock_instance

    @pytest.mark.asyncio
    async def test_get_not_found(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test getting a record that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.get(id=999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_none_filter_value(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test get skips None values in filters."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.get(name=None, id=1)

        mock_session.execute.assert_called_once()


class TestReadOnlyRepositoryGetById:
    """Tests for ReadOnlyRepository.get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test getting a record by ID that exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_instance
        mock_session.execute.return_value = mock_result

        test_uuid = uuid.uuid4()
        result = await readonly_repository.get_by_id(test_uuid)

        assert result is mock_instance


class TestReadOnlyRepositoryList:
    """Tests for ReadOnlyRepository.list method."""

    @pytest.mark.asyncio
    async def test_list_basic(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
        mock_instance: MagicMock,
    ):
        """Test basic list without filters."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_instance]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.list()

        assert len(result) == 1
        assert result[0] is mock_instance

    @pytest.mark.asyncio
    async def test_list_with_filters(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test list with filters."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.list(filters={"name": "test"})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_none_filter_value(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test list skips None values in filters."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.list(filters={"name": None, "value": 10})

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_offset_and_limit(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test list with pagination parameters."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.list(offset=5, limit=10)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_order_by(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test list with custom ordering."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.list(order_by=[SampleModel.name])

        mock_session.execute.assert_called_once()


class TestReadOnlyRepositoryCount:
    """Tests for ReadOnlyRepository.count method."""

    @pytest.mark.asyncio
    async def test_count_all(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test count all records."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.count()

        assert result == 42

    @pytest.mark.asyncio
    async def test_count_with_filters(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test count with filters."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 10
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.count(filters={"name": "test"})

        assert result == 10

    @pytest.mark.asyncio
    async def test_count_with_none_filter_value(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test count skips None values in filters."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.count(filters={"name": None, "value": 10})

        assert result == 5


class TestReadOnlyRepositoryExists:
    """Tests for ReadOnlyRepository.exists method."""

    @pytest.mark.asyncio
    async def test_exists_true(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test exists returns True when records exist."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.exists(filters={"name": "test"})

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test exists returns False when no records exist."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.exists(filters={"name": "nonexistent"})

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_without_filters(
        self,
        readonly_repository: ConcreteReadOnlyRepository,
        mock_session: AsyncMock,
    ):
        """Test exists without filters."""
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 100
        mock_session.execute.return_value = mock_result

        result = await readonly_repository.exists()

        assert result is True
