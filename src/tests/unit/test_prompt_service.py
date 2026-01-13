"""Unit tests for PromptService with mocked AsyncSession.

Tests cover:
- Prompt CRUD operations (create, get, list, update, delete)
- Prompt rendering
- Template validation
- Prompt versioning
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.prompts.models import Prompt, PromptCategory, PromptExecution
from src.modules.prompts.schemas import PromptCreate, PromptExecutionCreate, PromptUpdate
from src.modules.prompts.service import (
    PromptNameExistsError,
    PromptNotFoundError,
    PromptRenderError,
    PromptService,
    PromptValidationError,
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
def prompt_service(mock_session):
    """Create PromptService instance with mocked session."""
    return PromptService(mock_session)


@pytest.fixture
def sample_prompt_id():
    """Generate a sample prompt UUID."""
    return uuid4()


@pytest.fixture
def sample_user_id():
    """Generate a sample user UUID."""
    return uuid4()


@pytest.fixture
def sample_model_id():
    """Generate a sample model UUID."""
    return uuid4()


@pytest.fixture
def sample_variables_schema():
    """Create a sample variables schema."""
    return {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "count": {"type": "integer"},
            "language": {"type": "string"},
        },
        "required": ["topic", "count"],
    }


@pytest.fixture
def sample_prompt(sample_prompt_id, sample_model_id, sample_variables_schema):
    """Create a sample Prompt mock object."""
    prompt = MagicMock(spec=Prompt)
    prompt.id = sample_prompt_id
    prompt.name = "test_prompt"
    prompt.description = "A test prompt for card generation"
    prompt.category = PromptCategory.GENERATION
    prompt.system_prompt = "You are a helpful assistant that creates flashcards."
    prompt.user_prompt_template = "Create {{ count }} flashcards about {{ topic }} in {{ language }}."
    prompt.variables_schema = sample_variables_schema
    prompt.preferred_model_id = sample_model_id
    prompt.temperature = 0.7
    prompt.max_tokens = 2000
    prompt.is_active = True
    prompt.version = 1
    prompt.parent_id = None
    prompt.created_at = datetime.now(UTC)
    prompt.updated_at = datetime.now(UTC)
    prompt.created_by = None
    prompt.updated_by = None
    return prompt


@pytest.fixture
def sample_inactive_prompt(sample_prompt):
    """Create an inactive prompt."""
    sample_prompt.is_active = False
    return sample_prompt


@pytest.fixture
def sample_prompt_execution(sample_prompt_id, sample_user_id, sample_model_id):
    """Create a sample PromptExecution mock object."""
    execution = MagicMock(spec=PromptExecution)
    execution.id = uuid4()
    execution.prompt_id = sample_prompt_id
    execution.user_id = sample_user_id
    execution.model_id = sample_model_id
    execution.rendered_system_prompt = "You are a helpful assistant."
    execution.rendered_user_prompt = "Create 5 flashcards about Python."
    execution.variables = {"topic": "Python", "count": 5, "language": "English"}
    execution.response_text = "Generated flashcard content..."
    execution.input_tokens = 100
    execution.output_tokens = 500
    execution.latency_ms = 1500
    execution.trace_id = "trace-123"
    execution.created_at = datetime.now(UTC)
    return execution


# ==================== Create Tests ====================


@pytest.mark.asyncio
class TestPromptServiceCreate:
    """Tests for prompt creation."""

    async def test_create_prompt_success(
        self,
        prompt_service,
        mock_session,
        sample_variables_schema,
    ):
        """Test successful prompt creation."""
        # Mock _get_by_name to return None (no existing prompt)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        prompt_data = PromptCreate(
            name="new_prompt",
            description="A new prompt",
            category=PromptCategory.GENERATION,
            system_prompt="You are a helpful assistant.",
            user_prompt_template="Create {{ count }} flashcards about {{ topic }}.",
            variables_schema=sample_variables_schema,
            temperature=0.8,
            max_tokens=1500,
        )

        prompt = await prompt_service.create(prompt_data)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_create_prompt_with_created_by(
        self,
        prompt_service,
        mock_session,
        sample_variables_schema,
    ):
        """Test prompt creation with created_by audit info."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        prompt_data = PromptCreate(
            name="audited_prompt",
            category=PromptCategory.CHAT,
            system_prompt="System prompt",
            user_prompt_template="User prompt",
            variables_schema=sample_variables_schema,
        )

        await prompt_service.create(prompt_data, created_by="user_123")

        mock_session.add.assert_called_once()
        added_prompt = mock_session.add.call_args[0][0]
        assert added_prompt.name == "audited_prompt"

    async def test_create_prompt_duplicate_name_fails(
        self,
        prompt_service,
        mock_session,
        sample_prompt,
        sample_variables_schema,
    ):
        """Test creating prompt with duplicate name fails."""
        # Mock _get_by_name to return existing prompt
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_prompt
        mock_session.execute.return_value = mock_result

        prompt_data = PromptCreate(
            name="test_prompt",  # Same name as sample_prompt
            category=PromptCategory.GENERATION,
            system_prompt="System",
            user_prompt_template="User",
            variables_schema=sample_variables_schema,
        )

        with pytest.raises(PromptNameExistsError) as exc_info:
            await prompt_service.create(prompt_data)

        assert exc_info.value.name == "test_prompt"

    async def test_create_prompt_invalid_template(
        self,
        prompt_service,
        mock_session,
    ):
        """Test creating prompt with invalid Jinja2 template."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Template uses undefined variable
        prompt_data = PromptCreate(
            name="invalid_template",
            category=PromptCategory.GENERATION,
            system_prompt="System",
            user_prompt_template="Create cards about {{ undefined_var }}",
            variables_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                },
            },
        )

        with pytest.raises(PromptValidationError):
            await prompt_service.create(prompt_data)

    async def test_create_prompt_with_all_categories(
        self,
        prompt_service,
        mock_session,
        sample_variables_schema,
    ):
        """Test creating prompts with different categories."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        categories = [
            PromptCategory.GENERATION,
            PromptCategory.FACT_CHECK,
            PromptCategory.CHAT,
            PromptCategory.IMPROVEMENT,
        ]

        for i, category in enumerate(categories):
            mock_session.add.reset_mock()

            prompt_data = PromptCreate(
                name=f"prompt_{category.value}_{i}",
                category=category,
                system_prompt="System",
                user_prompt_template="{{ topic }}",
                variables_schema=sample_variables_schema,
            )

            await prompt_service.create(prompt_data)
            mock_session.add.assert_called_once()


# ==================== Get Tests ====================


@pytest.mark.asyncio
class TestPromptServiceGet:
    """Tests for prompt retrieval."""

    async def test_get_by_id_success(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test successful prompt retrieval by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_prompt
        mock_session.execute.return_value = mock_result

        prompt = await prompt_service.get_by_id(sample_prompt_id)

        assert prompt is not None
        assert prompt.id == sample_prompt_id
        mock_session.execute.assert_called_once()

    async def test_get_by_id_not_found(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
    ):
        """Test prompt retrieval when not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with pytest.raises(PromptNotFoundError) as exc_info:
            await prompt_service.get_by_id(sample_prompt_id)

        assert exc_info.value.prompt_id == sample_prompt_id


# ==================== List Tests ====================


@pytest.mark.asyncio
class TestPromptServiceList:
    """Tests for prompt listing."""

    async def test_get_list_success(
        self,
        prompt_service,
        mock_session,
        sample_prompt,
    ):
        """Test listing prompts."""
        mock_session.scalar.return_value = 5

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt] * 5
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        prompts, total = await prompt_service.get_list()

        assert len(prompts) == 5
        assert total == 5

    async def test_get_list_filter_by_category(
        self,
        prompt_service,
        mock_session,
        sample_prompt,
    ):
        """Test listing prompts filtered by category."""
        mock_session.scalar.return_value = 3

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt] * 3
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        prompts, total = await prompt_service.get_list(
            category=PromptCategory.GENERATION,
        )

        assert len(prompts) == 3
        assert total == 3

    async def test_get_list_filter_by_active_status(
        self,
        prompt_service,
        mock_session,
        sample_prompt,
    ):
        """Test listing only active prompts."""
        mock_session.scalar.return_value = 10

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt] * 10
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        prompts, total = await prompt_service.get_list(is_active=True)

        assert len(prompts) == 10
        assert total == 10

    async def test_get_list_with_pagination(
        self,
        prompt_service,
        mock_session,
        sample_prompt,
    ):
        """Test prompt listing with pagination."""
        mock_session.scalar.return_value = 30

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt] * 10
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        prompts, total = await prompt_service.get_list(page=1, size=10)

        assert len(prompts) == 10
        assert total == 30


# ==================== Update Tests ====================


@pytest.mark.asyncio
class TestPromptServiceUpdate:
    """Tests for prompt updates."""

    async def test_update_prompt_name(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating prompt name."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            # Mock _get_by_name to return None (no conflict)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            update_data = PromptUpdate(name="new_prompt_name")

            prompt = await prompt_service.update(sample_prompt_id, update_data)

        mock_session.flush.assert_called_once()

    async def test_update_prompt_system_prompt(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating prompt system prompt."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            update_data = PromptUpdate(
                system_prompt="You are a new helpful assistant.",
            )

            await prompt_service.update(sample_prompt_id, update_data)

        mock_session.flush.assert_called()

    async def test_update_prompt_template(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating prompt template."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            update_data = PromptUpdate(
                user_prompt_template="Generate {{ count }} cards about {{ topic }}.",
            )

            await prompt_service.update(sample_prompt_id, update_data)

        mock_session.flush.assert_called()

    async def test_update_prompt_to_existing_name_fails(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating to existing name fails."""
        other_prompt = MagicMock(spec=Prompt)
        other_prompt.id = uuid4()
        other_prompt.name = "existing_name"

        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = other_prompt
            mock_session.execute.return_value = mock_result

            update_data = PromptUpdate(name="existing_name")

            with pytest.raises(PromptNameExistsError):
                await prompt_service.update(sample_prompt_id, update_data)

    async def test_update_prompt_temperature(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating prompt temperature."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            update_data = PromptUpdate(temperature=0.5)

            await prompt_service.update(sample_prompt_id, update_data)

        mock_session.flush.assert_called()

    async def test_update_prompt_max_tokens(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating prompt max_tokens."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            update_data = PromptUpdate(max_tokens=3000)

            await prompt_service.update(sample_prompt_id, update_data)

        mock_session.flush.assert_called()

    async def test_update_prompt_is_active(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating prompt active status."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            update_data = PromptUpdate(is_active=False)

            await prompt_service.update(sample_prompt_id, update_data)

        mock_session.flush.assert_called()

    async def test_update_prompt_create_version(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating prompt with version creation."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            update_data = PromptUpdate(
                system_prompt="Updated system prompt",
            )

            await prompt_service.update(
                sample_prompt_id,
                update_data,
                create_version=True,
            )

        # Should add new prompt (new version)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


# ==================== Delete Tests ====================


@pytest.mark.asyncio
class TestPromptServiceDelete:
    """Tests for prompt deletion."""

    async def test_delete_prompt_success(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test successful prompt deletion."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            await prompt_service.delete(sample_prompt_id)

        mock_session.delete.assert_called_once_with(sample_prompt)
        mock_session.flush.assert_called_once()

    async def test_delete_prompt_not_found(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
    ):
        """Test deleting nonexistent prompt."""
        with patch.object(
            prompt_service,
            "get_by_id",
            side_effect=PromptNotFoundError(sample_prompt_id),
        ):
            with pytest.raises(PromptNotFoundError):
                await prompt_service.delete(sample_prompt_id)


# ==================== Render Tests ====================


@pytest.mark.asyncio
class TestPromptServiceRender:
    """Tests for prompt rendering."""

    async def test_render_success(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test successful prompt rendering."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            variables = {
                "topic": "Python basics",
                "count": 5,
                "language": "English",
            }

            system_prompt, user_prompt = await prompt_service.render(
                sample_prompt_id,
                variables,
            )

        assert "helpful assistant" in system_prompt
        assert "5" in user_prompt
        assert "Python basics" in user_prompt
        assert "English" in user_prompt

    async def test_render_inactive_prompt_fails(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_inactive_prompt,
    ):
        """Test rendering inactive prompt fails."""
        with patch.object(
            prompt_service, "get_by_id", return_value=sample_inactive_prompt
        ):
            variables = {"topic": "Test", "count": 1}

            with pytest.raises(PromptRenderError) as exc_info:
                await prompt_service.render(sample_prompt_id, variables)

        assert "not active" in str(exc_info.value)

    async def test_render_missing_variable_renders_empty(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test rendering with missing variable renders empty string.

        Note: Jinja2 by default replaces undefined variables with empty strings
        (unless StrictUndefined is used). This test verifies current behavior.
        If StrictUndefined is implemented, this test should be updated to expect
        PromptRenderError.
        """
        # Create a prompt with a template that uses variables
        sample_prompt.user_prompt_template = "Create {{ count }} cards about {{ topic }}"

        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            # Missing 'count' variable - Jinja2 with default Undefined renders as empty
            variables = {"topic": "Test"}  # Missing 'count'

            system_prompt, user_prompt = await prompt_service.render(
                sample_prompt_id, variables
            )

            # With default Undefined, missing variables are rendered as empty strings
            assert "Test" in user_prompt
            # 'count' is missing so it becomes empty
            assert "Create  cards" in user_prompt

    async def test_render_with_extra_variables(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test rendering with extra variables (should succeed)."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            variables = {
                "topic": "Test",
                "count": 3,
                "language": "Spanish",
                "extra_var": "ignored",
            }

            system_prompt, user_prompt = await prompt_service.render(
                sample_prompt_id,
                variables,
            )

        assert "3" in user_prompt
        assert "Test" in user_prompt

    async def test_render_prompt_not_found(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
    ):
        """Test rendering nonexistent prompt."""
        with patch.object(
            prompt_service,
            "get_by_id",
            side_effect=PromptNotFoundError(sample_prompt_id),
        ):
            with pytest.raises(PromptNotFoundError):
                await prompt_service.render(sample_prompt_id, {"topic": "Test"})


# ==================== Execution Recording Tests ====================


@pytest.mark.asyncio
class TestPromptServiceExecutionRecording:
    """Tests for prompt execution recording."""

    async def test_record_execution_success(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_user_id,
        sample_model_id,
    ):
        """Test recording prompt execution."""
        execution_data = PromptExecutionCreate(
            prompt_id=sample_prompt_id,
            user_id=sample_user_id,
            model_id=sample_model_id,
            rendered_system_prompt="System prompt",
            rendered_user_prompt="User prompt",
            variables={"topic": "Test", "count": 5},
            response_text="Generated response",
            input_tokens=100,
            output_tokens=500,
            latency_ms=1500,
            trace_id="trace-123",
        )

        execution = await prompt_service.record_execution(execution_data)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

        added = mock_session.add.call_args[0][0]
        assert added.prompt_id == sample_prompt_id
        assert added.input_tokens == 100
        assert added.output_tokens == 500

    async def test_record_execution_minimal(
        self,
        prompt_service,
        mock_session,
    ):
        """Test recording execution with minimal data."""
        execution_data = PromptExecutionCreate(
            rendered_system_prompt="System",
            rendered_user_prompt="User",
            variables={},
        )

        await prompt_service.record_execution(execution_data)

        mock_session.add.assert_called_once()


# ==================== Get Executions Tests ====================


@pytest.mark.asyncio
class TestPromptServiceGetExecutions:
    """Tests for retrieving prompt executions."""

    async def test_get_executions_success(
        self,
        prompt_service,
        mock_session,
        sample_prompt_execution,
    ):
        """Test getting executions."""
        mock_session.scalar.return_value = 10

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt_execution] * 10
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        executions, total = await prompt_service.get_executions()

        assert len(executions) == 10
        assert total == 10

    async def test_get_executions_by_prompt_id(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt_execution,
    ):
        """Test getting executions filtered by prompt ID."""
        mock_session.scalar.return_value = 5

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt_execution] * 5
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        executions, total = await prompt_service.get_executions(
            prompt_id=sample_prompt_id,
        )

        assert len(executions) == 5
        assert total == 5

    async def test_get_executions_by_user_id(
        self,
        prompt_service,
        mock_session,
        sample_user_id,
        sample_prompt_execution,
    ):
        """Test getting executions filtered by user ID."""
        mock_session.scalar.return_value = 3

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt_execution] * 3
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        executions, total = await prompt_service.get_executions(
            user_id=sample_user_id,
        )

        assert len(executions) == 3
        assert total == 3

    async def test_get_executions_with_pagination(
        self,
        prompt_service,
        mock_session,
        sample_prompt_execution,
    ):
        """Test getting executions with pagination."""
        mock_session.scalar.return_value = 50

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [sample_prompt_execution] * 20
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        executions, total = await prompt_service.get_executions(
            page=2,
            size=20,
        )

        assert len(executions) == 20
        assert total == 50


# ==================== Versioning Tests ====================


@pytest.mark.asyncio
class TestPromptServiceVersioning:
    """Tests for prompt versioning."""

    async def test_get_versions(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test getting all versions of a prompt."""
        # Create version chain: original -> v2
        v2 = MagicMock(spec=Prompt)
        v2.id = uuid4()
        v2.version = 2
        v2.parent_id = sample_prompt_id

        sample_prompt.parent_id = None  # Original has no parent

        with patch.object(
            prompt_service, "get_by_id", return_value=sample_prompt
        ):
            # Mock query for children
            mock_result = MagicMock()
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = [v2]
            mock_result.scalars.return_value = scalars_mock
            mock_session.execute.return_value = mock_result

            # Mock recursive call to return no more children
            with patch.object(
                prompt_service,
                "_collect_children",
                side_effect=[None, None],
            ):
                versions = await prompt_service.get_versions(sample_prompt_id)

        # At least the original version should be returned
        assert len(versions) >= 1

    async def test_create_version(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test creating a new version of a prompt."""
        sample_prompt.version = 1

        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            update_data = PromptUpdate(
                description="Updated description",
            )

            await prompt_service.update(
                sample_prompt_id,
                update_data,
                create_version=True,
            )

        # Should add new version
        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.version == 2
        assert added.parent_id == sample_prompt.id


# ==================== Template Validation Tests ====================


class TestPromptServiceTemplateValidation:
    """Tests for template validation.

    Note: These tests are synchronous as they test sync methods.
    """

    def test_validate_template_success(
        self,
        prompt_service,
    ):
        """Test validating a valid template."""
        template = "Create {{ count }} flashcards about {{ topic }}."
        schema = {
            "properties": {
                "count": {"type": "integer"},
                "topic": {"type": "string"},
            },
            "required": ["count", "topic"],
        }

        # Should not raise
        prompt_service._validate_template(template, schema)

    def test_validate_template_undefined_variable(
        self,
        prompt_service,
    ):
        """Test validating template with undefined variable."""
        template = "Create {{ count }} flashcards about {{ undefined_var }}."
        schema = {
            "properties": {
                "count": {"type": "integer"},
            },
        }

        with pytest.raises(PromptValidationError):
            prompt_service._validate_template(template, schema)

    def test_validate_template_syntax_error(
        self,
        prompt_service,
    ):
        """Test validating template with syntax error."""
        template = "Create {{ count flashcards"  # Missing closing braces
        schema = {"properties": {"count": {"type": "integer"}}}

        with pytest.raises(PromptValidationError):
            prompt_service._validate_template(template, schema)

    def test_extract_template_variables(
        self,
        prompt_service,
    ):
        """Test extracting variables from template."""
        template = "{{ var1 }} and {{ var2 }} and {{ var3 }}"

        variables = prompt_service.extract_template_variables(template)

        assert "var1" in variables
        assert "var2" in variables
        assert "var3" in variables
        assert len(variables) == 3

    def test_extract_template_variables_empty(
        self,
        prompt_service,
    ):
        """Test extracting variables from template with no variables."""
        template = "No variables here"

        variables = prompt_service.extract_template_variables(template)

        assert len(variables) == 0

    def test_extract_template_variables_invalid_template(
        self,
        prompt_service,
    ):
        """Test extracting variables from invalid template."""
        template = "{{ invalid syntax"

        variables = prompt_service.extract_template_variables(template)

        # Should return empty set on error
        assert len(variables) == 0


# ==================== Edge Cases Tests ====================


@pytest.mark.asyncio
class TestPromptServiceEdgeCases:
    """Tests for edge cases."""

    async def test_create_prompt_empty_description(
        self,
        prompt_service,
        mock_session,
        sample_variables_schema,
    ):
        """Test creating prompt without description."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        prompt_data = PromptCreate(
            name="no_description",
            category=PromptCategory.CHAT,
            system_prompt="System",
            user_prompt_template="{{ topic }}",
            variables_schema=sample_variables_schema,
        )

        await prompt_service.create(prompt_data)

        mock_session.add.assert_called_once()
        added = mock_session.add.call_args[0][0]
        assert added.description is None

    async def test_render_with_html_in_variables(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test rendering with HTML in variables (autoescape)."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            variables = {
                "topic": "<script>alert('xss')</script>",
                "count": 1,
                "language": "English",
            }

            system_prompt, user_prompt = await prompt_service.render(
                sample_prompt_id,
                variables,
            )

        # HTML should be escaped due to autoescape=True
        assert "<script>" not in user_prompt
        assert "&lt;script&gt;" in user_prompt

    async def test_get_list_empty(
        self,
        prompt_service,
        mock_session,
    ):
        """Test listing when no prompts exist."""
        mock_session.scalar.return_value = 0

        mock_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        mock_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = mock_result

        prompts, total = await prompt_service.get_list()

        assert len(prompts) == 0
        assert total == 0

    async def test_update_same_name_allowed(
        self,
        prompt_service,
        mock_session,
        sample_prompt_id,
        sample_prompt,
    ):
        """Test updating to same name is allowed."""
        with patch.object(prompt_service, "get_by_id", return_value=sample_prompt):
            # Mock _get_by_name to return the same prompt
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = sample_prompt
            mock_session.execute.return_value = mock_result

            update_data = PromptUpdate(name="test_prompt")  # Same name

            await prompt_service.update(sample_prompt_id, update_data)

        mock_session.flush.assert_called()
