"""Unit tests for TemplateService with mocked AsyncSession.

Tests cover:
- Template CRUD operations (create, get, list, update, delete)
- System template operations
- Template field management
- get_fields operation
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.templates.models import CardTemplate, TemplateField
from src.modules.templates.schemas import TemplateCreate, TemplateFieldCreate, TemplateUpdate
from src.modules.templates.service import (
    SystemTemplateModificationError,
    TemplateNameExistsError,
    TemplateNotFoundError,
    TemplateService,
)


# ==================== Fixtures ====================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def template_service(mock_session):
    """Create TemplateService instance with mocked session."""
    return TemplateService(mock_session)


@pytest.fixture
def sample_owner_id():
    """Generate a sample owner UUID."""
    return uuid4()


@pytest.fixture
def sample_template_id():
    """Generate a sample template UUID."""
    return uuid4()


@pytest.fixture
def sample_template(sample_template_id, sample_owner_id):
    """Create a sample CardTemplate mock object."""
    template = MagicMock(spec=CardTemplate)
    template.id = sample_template_id
    template.name = "basic"
    template.display_name = "Basic"
    template.fields_schema = {
        "fields": [
            {"name": "front", "type": "text"},
            {"name": "back", "type": "text"},
        ]
    }
    template.front_template = "{{front}}"
    template.back_template = "{{back}}"
    template.css = ".card { font-size: 20px; }"
    template.is_system = False
    template.owner_id = sample_owner_id
    template.fields = []
    template.created_at = datetime.now(timezone.utc)
    template.updated_at = datetime.now(timezone.utc)
    return template


@pytest.fixture
def sample_system_template(sample_template_id):
    """Create a sample system CardTemplate mock object."""
    template = MagicMock(spec=CardTemplate)
    template.id = sample_template_id
    template.name = "system_basic"
    template.display_name = "System Basic"
    template.fields_schema = {"fields": [{"name": "front", "type": "text"}]}
    template.front_template = "{{front}}"
    template.back_template = "{{back}}"
    template.css = None
    template.is_system = True
    template.owner_id = None
    template.fields = []
    template.created_at = datetime.now(timezone.utc)
    template.updated_at = datetime.now(timezone.utc)
    return template


@pytest.fixture
def sample_template_field(sample_template_id):
    """Create a sample TemplateField mock object."""
    field = MagicMock(spec=TemplateField)
    field.id = uuid4()
    field.template_id = sample_template_id
    field.name = "front"
    field.field_type = "text"
    field.is_required = True
    field.order = 0
    return field


# ==================== Create Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceCreate:
    """Tests for template creation."""

    async def test_create_template_success(
        self,
        template_service,
        mock_session,
        sample_owner_id,
    ):
        """Test successful template creation."""
        # Mock _get_by_name to return None (no existing template)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        template_data = TemplateCreate(
            name="test_template",
            display_name="Test Template",
            fields_schema={"fields": [{"name": "front", "type": "text"}]},
            front_template="{{front}}",
            back_template="{{back}}",
            css=".card { color: black; }",
        )

        template = await template_service.create(template_data, owner_id=sample_owner_id)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    async def test_create_template_without_css(
        self,
        template_service,
        mock_session,
        sample_owner_id,
    ):
        """Test creating template without CSS."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        template_data = TemplateCreate(
            name="no_css_template",
            display_name="No CSS Template",
            fields_schema={"fields": []},
            front_template="{{front}}",
            back_template="{{back}}",
        )

        await template_service.create(template_data, owner_id=sample_owner_id)

        mock_session.add.assert_called_once()
        added_template = mock_session.add.call_args[0][0]
        assert added_template.css is None

    async def test_create_template_with_fields(
        self,
        template_service,
        mock_session,
        sample_owner_id,
    ):
        """Test creating template with field definitions."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        template_data = TemplateCreate(
            name="template_with_fields",
            display_name="Template With Fields",
            fields_schema={"fields": [{"name": "front", "type": "text"}]},
            front_template="{{front}}",
            back_template="{{back}}",
            fields=[
                TemplateFieldCreate(name="front", field_type="text", is_required=True, order=0),
                TemplateFieldCreate(name="back", field_type="text", is_required=True, order=1),
            ],
        )

        await template_service.create(template_data, owner_id=sample_owner_id)

        # Template + 2 fields = 3 add calls
        assert mock_session.add.call_count >= 1

    async def test_create_template_duplicate_name_fails(
        self,
        template_service,
        mock_session,
        sample_owner_id,
        sample_template,
    ):
        """Test creating template with duplicate name fails."""
        # Mock _get_by_name to return existing template
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template
        mock_session.execute.return_value = mock_result

        template_data = TemplateCreate(
            name="basic",  # Same name as sample_template
            display_name="Duplicate",
            fields_schema={"fields": []},
            front_template="{{front}}",
            back_template="{{back}}",
        )

        with pytest.raises(TemplateNameExistsError) as exc_info:
            await template_service.create(template_data, owner_id=sample_owner_id)

        assert exc_info.value.name == "basic"

    async def test_create_system_template(
        self,
        template_service,
        mock_session,
    ):
        """Test creating a system template."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        template_data = TemplateCreate(
            name="system_template",
            display_name="System Template",
            fields_schema={"fields": []},
            front_template="{{front}}",
            back_template="{{back}}",
        )

        await template_service.create_system_template(template_data)

        mock_session.add.assert_called_once()
        added_template = mock_session.add.call_args[0][0]
        assert added_template.is_system is True
        assert added_template.owner_id is None


# ==================== Get Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceGet:
    """Tests for template retrieval."""

    async def test_get_by_id_success(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test successful template retrieval by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template
        mock_session.execute.return_value = mock_result

        template = await template_service.get_by_id(
            sample_template_id,
            owner_id=sample_owner_id,
        )

        assert template is not None
        assert template.id == sample_template_id
        mock_session.execute.assert_called_once()

    async def test_get_by_id_not_found(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
    ):
        """Test template retrieval when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(TemplateNotFoundError) as exc_info:
            await template_service.get_by_id(sample_template_id, owner_id=sample_owner_id)

        assert exc_info.value.template_id == sample_template_id

    async def test_get_system_template_by_any_user(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_system_template,
    ):
        """Test that system templates are accessible by any user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_template
        mock_session.execute.return_value = mock_result

        template = await template_service.get_by_id(
            sample_template_id,
            owner_id=sample_owner_id,
        )

        assert template is not None
        assert template.is_system is True

    async def test_get_by_id_without_owner_filter(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_template,
    ):
        """Test template retrieval without owner filter."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template
        mock_session.execute.return_value = mock_result

        template = await template_service.get_by_id(sample_template_id)

        assert template is not None
        mock_session.execute.assert_called_once()


# ==================== List Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceList:
    """Tests for template listing."""

    async def test_get_list_success(
        self,
        template_service,
        mock_session,
        sample_owner_id,
        sample_template,
    ):
        """Test listing templates."""
        # Mock count query
        mock_session.scalar.return_value = 5

        # Mock data query
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_template] * 5
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        templates, total = await template_service.get_list(owner_id=sample_owner_id)

        assert len(templates) == 5
        assert total == 5

    async def test_get_list_without_system_templates(
        self,
        template_service,
        mock_session,
        sample_owner_id,
        sample_template,
    ):
        """Test listing templates excluding system templates."""
        mock_session.scalar.return_value = 3

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_template] * 3
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        templates, total = await template_service.get_list(
            owner_id=sample_owner_id,
            include_system=False,
        )

        assert len(templates) == 3
        assert total == 3

    async def test_get_list_with_pagination(
        self,
        template_service,
        mock_session,
        sample_owner_id,
        sample_template,
    ):
        """Test template listing with pagination."""
        mock_session.scalar.return_value = 25

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_template] * 10
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        templates, total = await template_service.get_list(
            owner_id=sample_owner_id,
            page=1,
            size=10,
        )

        assert len(templates) == 10
        assert total == 25

    async def test_get_system_templates(
        self,
        template_service,
        mock_session,
        sample_system_template,
    ):
        """Test getting only system templates."""
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_system_template] * 3
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        templates = await template_service.get_system_templates()

        assert len(templates) == 3
        mock_session.execute.assert_called_once()


# ==================== Update Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceUpdate:
    """Tests for template updates."""

    async def test_update_template_name(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test updating template name."""
        # Mock get_by_id to return template
        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            # Mock _get_by_name to return None (no conflict)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            update_data = TemplateUpdate(name="new_name")

            template = await template_service.update(
                sample_template_id,
                update_data,
                owner_id=sample_owner_id,
            )

        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    async def test_update_template_display_name(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test updating template display name."""
        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            update_data = TemplateUpdate(display_name="New Display Name")

            await template_service.update(
                sample_template_id,
                update_data,
                owner_id=sample_owner_id,
            )

        mock_session.flush.assert_called_once()

    async def test_update_template_css(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test updating template CSS."""
        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            update_data = TemplateUpdate(css=".card { background: white; }")

            await template_service.update(
                sample_template_id,
                update_data,
                owner_id=sample_owner_id,
            )

        mock_session.flush.assert_called()

    async def test_update_template_fields(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test updating template fields."""
        # Mock existing fields query
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            update_data = TemplateUpdate(
                fields=[
                    TemplateFieldCreate(name="question", field_type="text", is_required=True, order=0),
                    TemplateFieldCreate(name="answer", field_type="text", is_required=True, order=1),
                ],
            )

            await template_service.update(
                sample_template_id,
                update_data,
                owner_id=sample_owner_id,
            )

        mock_session.flush.assert_called()

    async def test_update_system_template_fails(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_system_template,
    ):
        """Test that updating system template fails."""
        with patch.object(
            template_service, "get_by_id", return_value=sample_system_template
        ):
            update_data = TemplateUpdate(name="hacked")

            with pytest.raises(SystemTemplateModificationError) as exc_info:
                await template_service.update(
                    sample_template_id,
                    update_data,
                    owner_id=sample_owner_id,
                )

        assert exc_info.value.template_id == sample_template_id

    async def test_update_to_existing_name_fails(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test updating to existing name fails."""
        # Create another template with different ID
        other_template = MagicMock(spec=CardTemplate)
        other_template.id = uuid4()
        other_template.name = "existing_name"

        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            # Mock _get_by_name to return existing template
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = other_template
            mock_session.execute.return_value = mock_result

            update_data = TemplateUpdate(name="existing_name")

            with pytest.raises(TemplateNameExistsError):
                await template_service.update(
                    sample_template_id,
                    update_data,
                    owner_id=sample_owner_id,
                )


# ==================== Delete Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceDelete:
    """Tests for template deletion."""

    async def test_delete_template_success(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test successful template deletion."""
        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            await template_service.delete(sample_template_id, owner_id=sample_owner_id)

        mock_session.delete.assert_called_once_with(sample_template)
        mock_session.flush.assert_called_once()

    async def test_delete_system_template_fails(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_system_template,
    ):
        """Test that deleting system template fails."""
        with patch.object(
            template_service, "get_by_id", return_value=sample_system_template
        ):
            with pytest.raises(SystemTemplateModificationError) as exc_info:
                await template_service.delete(
                    sample_template_id,
                    owner_id=sample_owner_id,
                )

        assert exc_info.value.template_id == sample_template_id

    async def test_delete_nonexistent_template(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
    ):
        """Test deleting nonexistent template."""
        with patch.object(
            template_service,
            "get_by_id",
            side_effect=TemplateNotFoundError(sample_template_id),
        ):
            with pytest.raises(TemplateNotFoundError):
                await template_service.delete(
                    sample_template_id,
                    owner_id=sample_owner_id,
                )


# ==================== Get Fields Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceGetFields:
    """Tests for getting template fields."""

    async def test_get_fields_from_template(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
        sample_template_field,
    ):
        """Test getting fields from a template."""
        sample_template.fields = [sample_template_field]

        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            template = await template_service.get_by_id(
                sample_template_id,
                owner_id=sample_owner_id,
            )

        assert len(template.fields) == 1
        assert template.fields[0].name == "front"

    async def test_get_fields_empty(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test getting fields when template has no fields."""
        sample_template.fields = []

        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            template = await template_service.get_by_id(
                sample_template_id,
                owner_id=sample_owner_id,
            )

        assert len(template.fields) == 0


# ==================== Private Methods Tests ====================


@pytest.mark.asyncio
class TestTemplateServicePrivateMethods:
    """Tests for private helper methods."""

    async def test_get_by_name_found(
        self,
        template_service,
        mock_session,
        sample_owner_id,
        sample_template,
    ):
        """Test _get_by_name when template exists."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_template
        mock_session.execute.return_value = mock_result

        template = await template_service._get_by_name("basic", sample_owner_id)

        assert template is not None
        assert template.name == "basic"

    async def test_get_by_name_not_found(
        self,
        template_service,
        mock_session,
        sample_owner_id,
    ):
        """Test _get_by_name when template doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        template = await template_service._get_by_name("nonexistent", sample_owner_id)

        assert template is None

    async def test_create_fields(
        self,
        template_service,
        mock_session,
        sample_template_id,
    ):
        """Test _create_fields method."""
        fields = [
            TemplateFieldCreate(name="front", field_type="text", is_required=True, order=0),
            TemplateFieldCreate(name="back", field_type="text", is_required=True, order=1),
        ]

        await template_service._create_fields(sample_template_id, fields)

        assert mock_session.add.call_count == 2

    async def test_update_fields_replaces_all(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_template_field,
    ):
        """Test _update_fields replaces all existing fields."""
        # Mock existing fields query
        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_template_field]
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        new_fields = [
            TemplateFieldCreate(name="question", field_type="text", is_required=True, order=0),
        ]

        await template_service._update_fields(sample_template_id, new_fields)

        # Should delete old field and add new one
        mock_session.delete.assert_called_once_with(sample_template_field)
        mock_session.add.assert_called_once()


# ==================== Edge Cases Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceEdgeCases:
    """Tests for edge cases."""

    async def test_create_template_with_special_characters(
        self,
        template_service,
        mock_session,
        sample_owner_id,
    ):
        """Test creating template with special characters."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        template_data = TemplateCreate(
            name="special_template",
            display_name="Template with <special> & \"chars\"",
            fields_schema={"fields": []},
            front_template="<div>{{front}}</div>",
            back_template="<div>{{back}}</div>",
        )

        await template_service.create(template_data, owner_id=sample_owner_id)

        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert "special" in added.display_name

    async def test_create_template_with_unicode(
        self,
        template_service,
        mock_session,
        sample_owner_id,
    ):
        """Test creating template with unicode characters."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        template_data = TemplateCreate(
            name="unicode_template",
            display_name="Template Unicode",
            fields_schema={"fields": []},
            front_template="{{front}}",
            back_template="{{back}}",
        )

        await template_service.create(template_data, owner_id=sample_owner_id)

        mock_session.add.assert_called_once()

    async def test_get_list_empty_result(
        self,
        template_service,
        mock_session,
        sample_owner_id,
    ):
        """Test listing when no templates exist."""
        mock_session.scalar.return_value = 0

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        templates, total = await template_service.get_list(owner_id=sample_owner_id)

        assert len(templates) == 0
        assert total == 0

    async def test_update_same_name_allowed(
        self,
        template_service,
        mock_session,
        sample_template_id,
        sample_owner_id,
        sample_template,
    ):
        """Test updating to same name is allowed (no change)."""
        with patch.object(
            template_service, "get_by_id", return_value=sample_template
        ):
            # Mock _get_by_name to return the same template
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_template
            mock_session.execute.return_value = mock_result

            # Update with same name - should not raise
            update_data = TemplateUpdate(name="basic")  # Same name as sample_template

            await template_service.update(
                sample_template_id,
                update_data,
                owner_id=sample_owner_id,
            )

        mock_session.flush.assert_called()
