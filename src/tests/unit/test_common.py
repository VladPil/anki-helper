"""Unit tests for common modules.

Tests cover:
- UUID7 generation and TypeDecorator
- Model mixins (UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin)
- Base schemas (PaginationParams, PaginatedResponse, ErrorResponse, etc.)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.shared.uuid7 import UUID7, uuid7
from src.shared.mixins import (
    AuditMixin,
    FullMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)
from src.shared.schemas import (
    BaseSchema,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    PaginatedResponse,
    PaginationParams,
    SoftDeleteSchema,
    SuccessResponse,
    TimestampSchema,
    UUIDSchema,
    UUIDTimestampSchema,
)


# ==================== UUID7 Tests ====================


class TestUUID7Function:
    """Tests for uuid7 function."""

    def test_uuid7_returns_uuid(self):
        """Test that uuid7 returns a UUID object."""
        result = uuid7()
        assert isinstance(result, uuid.UUID)

    def test_uuid7_uniqueness(self):
        """Test that uuid7 generates unique IDs."""
        ids = [uuid7() for _ in range(1000)]
        assert len(set(ids)) == 1000

    def test_uuid7_is_time_ordered(self):
        """Test that uuid7 generates time-ordered UUIDs."""
        import time

        id1 = uuid7()
        time.sleep(0.001)  # Sleep 1ms
        id2 = uuid7()

        # Compare the integer representation (timestamp is in upper bits)
        assert id1.int < id2.int

    def test_uuid7_version_bits(self):
        """Test that uuid7 has correct version bits."""
        result = uuid7()
        # Check version is 7 (bits 48-51)
        version = (result.int >> 76) & 0xF
        assert version == 7


class TestUUID7TypeDecorator:
    """Tests for UUID7 SQLAlchemy TypeDecorator."""

    def test_process_bind_param_with_uuid(self):
        """Test converting UUID to string for database."""
        decorator = UUID7()
        test_uuid = uuid.uuid4()
        dialect = MagicMock()

        result = decorator.process_bind_param(test_uuid, dialect)
        assert result == str(test_uuid)

    def test_process_bind_param_with_string(self):
        """Test passing string through unchanged."""
        decorator = UUID7()
        test_str = "test-string"
        dialect = MagicMock()

        result = decorator.process_bind_param(test_str, dialect)
        assert result == test_str

    def test_process_bind_param_with_none(self):
        """Test handling None value."""
        decorator = UUID7()
        dialect = MagicMock()

        result = decorator.process_bind_param(None, dialect)
        assert result is None

    def test_process_result_value_with_uuid(self):
        """Test passing UUID through unchanged."""
        decorator = UUID7()
        test_uuid = uuid.uuid4()
        dialect = MagicMock()

        result = decorator.process_result_value(test_uuid, dialect)
        assert result == test_uuid

    def test_process_result_value_with_string(self):
        """Test converting string to UUID."""
        decorator = UUID7()
        test_uuid = uuid.uuid4()
        dialect = MagicMock()

        result = decorator.process_result_value(str(test_uuid), dialect)
        assert result == test_uuid

    def test_process_result_value_with_none(self):
        """Test handling None value."""
        decorator = UUID7()
        dialect = MagicMock()

        result = decorator.process_result_value(None, dialect)
        assert result is None

    def test_cache_ok_is_true(self):
        """Test that cache_ok is True for performance."""
        decorator = UUID7()
        assert decorator.cache_ok is True


# ==================== Mixin Tests ====================


class TestSoftDeleteMixin:
    """Tests for SoftDeleteMixin."""

    def test_is_deleted_when_not_deleted(self):
        """Test is_deleted returns False when deleted_at is None."""

        class TestModel(SoftDeleteMixin):
            pass

        model = TestModel()
        model.deleted_at = None
        assert model.is_deleted is False

    def test_is_deleted_when_deleted(self):
        """Test is_deleted returns True when deleted_at is set."""

        class TestModel(SoftDeleteMixin):
            pass

        model = TestModel()
        model.deleted_at = datetime.now(timezone.utc)
        assert model.is_deleted is True

    def test_soft_delete_sets_timestamp(self):
        """Test soft_delete sets deleted_at timestamp."""

        class TestModel(SoftDeleteMixin):
            pass

        model = TestModel()
        model.deleted_at = None
        model.soft_delete()
        assert model.deleted_at is not None
        assert isinstance(model.deleted_at, datetime)

    def test_restore_clears_timestamp(self):
        """Test restore clears deleted_at timestamp."""

        class TestModel(SoftDeleteMixin):
            pass

        model = TestModel()
        model.deleted_at = datetime.now(timezone.utc)
        model.restore()
        assert model.deleted_at is None


class TestAuditMixin:
    """Tests for AuditMixin."""

    def test_set_created_by(self):
        """Test set_created_by sets both created_by and updated_by."""

        class TestModel(AuditMixin):
            pass

        model = TestModel()
        model.created_by = None
        model.updated_by = None
        model.set_created_by("user123")

        assert model.created_by == "user123"
        assert model.updated_by == "user123"

    def test_set_updated_by(self):
        """Test set_updated_by only sets updated_by."""

        class TestModel(AuditMixin):
            pass

        model = TestModel()
        model.created_by = "user1"
        model.updated_by = "user1"
        model.set_updated_by("user2")

        assert model.created_by == "user1"
        assert model.updated_by == "user2"


# ==================== Schema Tests ====================


class TestPaginationParams:
    """Tests for PaginationParams schema."""

    def test_default_values(self):
        """Test default pagination values."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20

    def test_offset_calculation(self):
        """Test offset is calculated correctly."""
        params = PaginationParams(page=3, page_size=10)
        assert params.offset == 20  # (3-1) * 10

    def test_limit_property(self):
        """Test limit equals page_size."""
        params = PaginationParams(page_size=50)
        assert params.limit == 50

    def test_page_validation_minimum(self):
        """Test page must be at least 1."""
        with pytest.raises(ValueError):
            PaginationParams(page=0)

    def test_page_size_validation_minimum(self):
        """Test page_size must be at least 1."""
        with pytest.raises(ValueError):
            PaginationParams(page_size=0)

    def test_page_size_validation_maximum(self):
        """Test page_size cannot exceed 100."""
        with pytest.raises(ValueError):
            PaginationParams(page_size=101)


class TestPaginatedResponse:
    """Tests for PaginatedResponse schema."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        response = PaginatedResponse(
            items=["a", "b", "c"],
            total=100,
            page=1,
            page_size=20,
        )
        assert len(response.items) == 3
        assert response.total == 100

    def test_total_pages_calculation(self):
        """Test total_pages is calculated correctly."""
        response = PaginatedResponse(
            items=[],
            total=95,
            page=1,
            page_size=20,
        )
        assert response.total_pages == 5  # ceil(95/20)

    def test_total_pages_with_zero_items(self):
        """Test total_pages is 0 when no items."""
        response = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )
        assert response.total_pages == 0

    def test_has_next_true(self):
        """Test has_next returns True when more pages exist."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page=1,
            page_size=20,
        )
        assert response.has_next is True

    def test_has_next_false(self):
        """Test has_next returns False on last page."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page=5,
            page_size=20,
        )
        assert response.has_next is False

    def test_has_previous_true(self):
        """Test has_previous returns True when not on first page."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page=2,
            page_size=20,
        )
        assert response.has_previous is True

    def test_has_previous_false(self):
        """Test has_previous returns False on first page."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page=1,
            page_size=20,
        )
        assert response.has_previous is False

    def test_create_class_method(self):
        """Test create class method."""
        params = PaginationParams(page=2, page_size=10)
        response = PaginatedResponse.create(
            items=["a", "b"],
            total=50,
            params=params,
        )
        assert response.page == 2
        assert response.page_size == 10
        assert response.total == 50


class TestErrorDetail:
    """Tests for ErrorDetail schema."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        detail = ErrorDetail(message="Test error")
        assert detail.message == "Test error"
        assert detail.field is None
        assert detail.code is None

    def test_with_field(self):
        """Test with field specified."""
        detail = ErrorDetail(field="email", message="Invalid email")
        assert detail.field == "email"

    def test_with_code(self):
        """Test with error code."""
        detail = ErrorDetail(message="Error", code="VALIDATION_ERROR")
        assert detail.code == "VALIDATION_ERROR"


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        response = ErrorResponse(error="Something went wrong")
        assert response.error == "Something went wrong"
        assert response.code is None

    def test_with_code_and_details(self):
        """Test with error code and details."""
        details = [ErrorDetail(field="email", message="Invalid")]
        response = ErrorResponse(
            error="Validation failed",
            code="VALIDATION_ERROR",
            details=details,
        )
        assert response.code == "VALIDATION_ERROR"
        assert len(response.details) == 1

    def test_validation_error_factory(self):
        """Test validation_error class method."""
        errors = [
            {"loc": ["body", "email"], "msg": "Invalid email", "type": "value_error"},
            {"loc": ["body", "password"], "msg": "Too short", "type": "value_error.min_length"},
        ]
        response = ErrorResponse.validation_error(errors, request_id="req-123")

        assert response.error == "Validation failed"
        assert response.code == "VALIDATION_ERROR"
        assert len(response.details) == 2
        assert response.request_id == "req-123"
        assert response.details[0].field == "body.email"


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        response = HealthResponse(status="healthy")
        assert response.status == "healthy"
        assert response.is_healthy is True

    def test_is_healthy_property(self):
        """Test is_healthy property."""
        healthy = HealthResponse(status="healthy")
        unhealthy = HealthResponse(status="unhealthy")
        degraded = HealthResponse(status="degraded")

        assert healthy.is_healthy is True
        assert unhealthy.is_healthy is False
        assert degraded.is_healthy is False

    def test_healthy_factory(self):
        """Test healthy class method."""
        response = HealthResponse.healthy(version="1.0.0")
        assert response.status == "healthy"
        assert response.version == "1.0.0"

    def test_unhealthy_factory(self):
        """Test unhealthy class method."""
        checks = {"postgres": True, "redis": False}
        response = HealthResponse.unhealthy(checks=checks)
        assert response.status == "unhealthy"
        assert response.checks == checks

    def test_degraded_factory(self):
        """Test degraded class method."""
        response = HealthResponse.degraded()
        assert response.status == "degraded"


class TestSuccessResponse:
    """Tests for SuccessResponse schema."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        response = SuccessResponse(message="Operation completed")
        assert response.success is True
        assert response.message == "Operation completed"


class TestSoftDeleteSchema:
    """Tests for SoftDeleteSchema."""

    def test_not_deleted(self):
        """Test is_deleted when deleted_at is None."""
        schema = SoftDeleteSchema(deleted_at=None)
        assert schema.is_deleted is False

    def test_deleted(self):
        """Test is_deleted when deleted_at is set."""
        schema = SoftDeleteSchema(deleted_at=datetime.now(timezone.utc))
        assert schema.is_deleted is True


class TestBaseSchema:
    """Tests for BaseSchema configuration."""

    def test_from_attributes_enabled(self):
        """Test that from_attributes is enabled for ORM mode."""
        config = BaseSchema.model_config
        assert config.get("from_attributes") is True

    def test_validate_assignment_enabled(self):
        """Test that validate_assignment is enabled."""
        config = BaseSchema.model_config
        assert config.get("validate_assignment") is True

    def test_str_strip_whitespace_enabled(self):
        """Test that whitespace stripping is enabled."""
        config = BaseSchema.model_config
        assert config.get("str_strip_whitespace") is True


class TestUUIDSchema:
    """Tests for UUIDSchema."""

    def test_id_field(self):
        """Test id field is required UUID."""
        test_id = uuid.uuid4()
        schema = UUIDSchema(id=test_id)
        assert schema.id == test_id


class TestTimestampSchema:
    """Tests for TimestampSchema."""

    def test_timestamp_fields(self):
        """Test timestamp fields."""
        now = datetime.now(timezone.utc)
        schema = TimestampSchema(created_at=now, updated_at=now)
        assert schema.created_at == now
        assert schema.updated_at == now


class TestUUIDTimestampSchema:
    """Tests for UUIDTimestampSchema."""

    def test_combined_fields(self):
        """Test combined UUID and timestamp fields."""
        test_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        schema = UUIDTimestampSchema(id=test_id, created_at=now, updated_at=now)

        assert schema.id == test_id
        assert schema.created_at == now
        assert schema.updated_at == now
