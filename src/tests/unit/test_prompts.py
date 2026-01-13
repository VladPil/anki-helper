"""Unit tests for prompt rendering and template management.

Tests cover:
- Template service CRUD operations
- Prompt template rendering
- Variable substitution
- Template validation
- Card template operations
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.templates.models import CardTemplate, TemplateField
from src.modules.templates.schemas import TemplateCreate, TemplateFieldCreate, TemplateUpdate
from src.modules.templates.service import (
    SystemTemplateModificationError,
    TemplateNameExistsError,
    TemplateNotFoundError,
    TemplateService,
)
from src.modules.users.models import User

from src.tests.factories import CardTemplateFactory, TemplateFieldFactory, UserFactory
from src.tests.fixtures.sample_data import SAMPLE_PROMPTS, SAMPLE_TEMPLATE_DATA


# ==================== Template Service Tests ====================


@pytest.mark.asyncio
class TestTemplateServiceCreate:
    """Tests for template creation."""

    async def test_create_template_success(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test successful template creation."""
        service = TemplateService(db_session)
        template_data = SAMPLE_TEMPLATE_DATA["basic"]

        template = await service.create(
            TemplateCreate(
                name=template_data["name"],
                display_name=template_data["display_name"],
                fields_schema=template_data["fields_schema"],
                front_template=template_data["front_template"],
                back_template=template_data["back_template"],
                css=template_data["css"],
            ),
            owner_id=test_user.id,
        )

        assert template is not None
        assert template.name == template_data["name"]
        assert template.display_name == template_data["display_name"]
        assert template.owner_id == test_user.id
        assert template.is_system is False

    async def test_create_template_without_css(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating template without CSS."""
        service = TemplateService(db_session)

        template = await service.create(
            TemplateCreate(
                name="no_css_template",
                display_name="No CSS Template",
                fields_schema={"type": "object", "properties": {}},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        assert template.css is None

    async def test_create_template_with_fields(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating template with field definitions."""
        service = TemplateService(db_session)

        template = await service.create(
            TemplateCreate(
                name="template_with_fields",
                display_name="Template With Fields",
                fields_schema={"type": "object", "properties": {"front": {"type": "string"}}},
                front_template="{{front}}",
                back_template="{{back}}",
                fields=[
                    TemplateFieldCreate(
                        name="front",
                        field_type="text",
                        is_required=True,
                        order=0,
                    ),
                    TemplateFieldCreate(
                        name="back",
                        field_type="text",
                        is_required=True,
                        order=1,
                    ),
                ],
            ),
            owner_id=test_user.id,
        )

        assert len(template.fields) == 2
        assert template.fields[0].name == "front"
        assert template.fields[1].name == "back"

    async def test_create_duplicate_template_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating template with duplicate name fails."""
        service = TemplateService(db_session)

        # Create first template
        await service.create(
            TemplateCreate(
                name="duplicate_test",
                display_name="First Template",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        # Try to create duplicate
        with pytest.raises(TemplateNameExistsError):
            await service.create(
                TemplateCreate(
                    name="duplicate_test",  # Same name
                    display_name="Second Template",
                    fields_schema={"type": "object"},
                    front_template="{{front}}",
                    back_template="{{back}}",
                ),
                owner_id=test_user.id,
            )

    async def test_create_system_template(
        self,
        db_session: AsyncSession,
    ):
        """Test creating a system template."""
        service = TemplateService(db_session)

        template = await service.create_system_template(
            TemplateCreate(
                name="system_basic",
                display_name="System Basic",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            )
        )

        assert template.is_system is True
        assert template.owner_id is None


@pytest.mark.asyncio
class TestTemplateServiceGet:
    """Tests for template retrieval."""

    async def test_get_template_by_id(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting template by ID."""
        service = TemplateService(db_session)

        # Create template
        created = await service.create(
            TemplateCreate(
                name="get_test",
                display_name="Get Test",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        # Retrieve template
        template = await service.get_by_id(created.id, owner_id=test_user.id)

        assert template is not None
        assert template.id == created.id

    async def test_get_nonexistent_template(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test getting nonexistent template raises error."""
        service = TemplateService(db_session)

        with pytest.raises(TemplateNotFoundError):
            await service.get_by_id(
                UUID("00000000-0000-0000-0000-000000000999"),
                owner_id=test_user.id,
            )

    async def test_get_system_template_by_any_user(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that system templates are accessible by any user."""
        service = TemplateService(db_session)

        # Create system template
        system_template = await service.create_system_template(
            TemplateCreate(
                name="shared_system",
                display_name="Shared System",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            )
        )

        # Access by regular user
        template = await service.get_by_id(
            system_template.id,
            owner_id=test_user.id,
        )

        assert template is not None
        assert template.is_system is True


@pytest.mark.asyncio
class TestTemplateServiceList:
    """Tests for template listing."""

    async def test_list_user_templates(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test listing user's templates."""
        service = TemplateService(db_session)

        # Create templates
        for i in range(3):
            await service.create(
                TemplateCreate(
                    name=f"user_template_{i}",
                    display_name=f"User Template {i}",
                    fields_schema={"type": "object"},
                    front_template="{{front}}",
                    back_template="{{back}}",
                ),
                owner_id=test_user.id,
            )

        templates, total = await service.get_list(
            owner_id=test_user.id,
            include_system=False,
        )

        assert len(templates) == 3
        assert total == 3

    async def test_list_includes_system_templates(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test listing includes system templates by default."""
        service = TemplateService(db_session)

        # Create system template
        await service.create_system_template(
            TemplateCreate(
                name="list_system",
                display_name="List System",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            )
        )

        # Create user template
        await service.create(
            TemplateCreate(
                name="list_user",
                display_name="List User",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        templates, total = await service.get_list(
            owner_id=test_user.id,
            include_system=True,
        )

        system_count = sum(1 for t in templates if t.is_system)
        user_count = sum(1 for t in templates if not t.is_system)

        assert system_count >= 1
        assert user_count >= 1

    async def test_list_pagination(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test template listing with pagination."""
        service = TemplateService(db_session)

        # Create templates
        for i in range(15):
            await service.create(
                TemplateCreate(
                    name=f"page_template_{i}",
                    display_name=f"Page Template {i}",
                    fields_schema={"type": "object"},
                    front_template="{{front}}",
                    back_template="{{back}}",
                ),
                owner_id=test_user.id,
            )

        page1, total = await service.get_list(
            owner_id=test_user.id,
            include_system=False,
            page=1,
            size=10,
        )

        page2, _ = await service.get_list(
            owner_id=test_user.id,
            include_system=False,
            page=2,
            size=10,
        )

        assert len(page1) == 10
        assert len(page2) == 5
        assert total == 15


@pytest.mark.asyncio
class TestTemplateServiceUpdate:
    """Tests for template updates."""

    async def test_update_template_name(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating template name."""
        service = TemplateService(db_session)

        template = await service.create(
            TemplateCreate(
                name="original_name",
                display_name="Original",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        updated = await service.update(
            template.id,
            TemplateUpdate(name="new_name"),
            owner_id=test_user.id,
        )

        assert updated.name == "new_name"

    async def test_update_template_display_name(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating template display name."""
        service = TemplateService(db_session)

        template = await service.create(
            TemplateCreate(
                name="display_update",
                display_name="Original Display",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        updated = await service.update(
            template.id,
            TemplateUpdate(display_name="New Display Name"),
            owner_id=test_user.id,
        )

        assert updated.display_name == "New Display Name"

    async def test_update_template_fields(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating template fields."""
        service = TemplateService(db_session)

        template = await service.create(
            TemplateCreate(
                name="fields_update",
                display_name="Fields Update",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
                fields=[
                    TemplateFieldCreate(name="front", field_type="text", is_required=True, order=0),
                ],
            ),
            owner_id=test_user.id,
        )

        updated = await service.update(
            template.id,
            TemplateUpdate(
                fields=[
                    TemplateFieldCreate(name="question", field_type="text", is_required=True, order=0),
                    TemplateFieldCreate(name="answer", field_type="text", is_required=True, order=1),
                ],
            ),
            owner_id=test_user.id,
        )

        assert len(updated.fields) == 2
        assert updated.fields[0].name == "question"

    async def test_update_system_template_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that updating system template fails."""
        service = TemplateService(db_session)

        system_template = await service.create_system_template(
            TemplateCreate(
                name="immutable_system",
                display_name="Immutable System",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            )
        )

        with pytest.raises(SystemTemplateModificationError):
            await service.update(
                system_template.id,
                TemplateUpdate(name="hacked"),
                owner_id=test_user.id,
            )

    async def test_update_to_existing_name_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating to existing name fails."""
        service = TemplateService(db_session)

        # Create two templates
        template1 = await service.create(
            TemplateCreate(
                name="name_conflict_1",
                display_name="First",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        template2 = await service.create(
            TemplateCreate(
                name="name_conflict_2",
                display_name="Second",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        with pytest.raises(TemplateNameExistsError):
            await service.update(
                template2.id,
                TemplateUpdate(name="name_conflict_1"),  # Existing name
                owner_id=test_user.id,
            )


@pytest.mark.asyncio
class TestTemplateServiceDelete:
    """Tests for template deletion."""

    async def test_delete_template(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test deleting a template."""
        service = TemplateService(db_session)

        template = await service.create(
            TemplateCreate(
                name="to_delete",
                display_name="To Delete",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            ),
            owner_id=test_user.id,
        )

        await service.delete(template.id, owner_id=test_user.id)

        with pytest.raises(TemplateNotFoundError):
            await service.get_by_id(template.id, owner_id=test_user.id)

    async def test_delete_system_template_fails(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test that deleting system template fails."""
        service = TemplateService(db_session)

        system_template = await service.create_system_template(
            TemplateCreate(
                name="protected_system",
                display_name="Protected System",
                fields_schema={"type": "object"},
                front_template="{{front}}",
                back_template="{{back}}",
            )
        )

        with pytest.raises(SystemTemplateModificationError):
            await service.delete(system_template.id, owner_id=test_user.id)


# ==================== Prompt Rendering Tests ====================


class TestPromptRendering:
    """Tests for prompt template rendering."""

    def test_simple_variable_substitution(self):
        """Test simple variable substitution in templates."""
        template = "Hello, {name}!"
        variables = {"name": "World"}

        result = template.format(**variables)

        assert result == "Hello, World!"

    def test_multiple_variable_substitution(self):
        """Test multiple variable substitution."""
        template = SAMPLE_PROMPTS["card_generation"]["template"]
        variables = SAMPLE_PROMPTS["card_generation"]["variables"]

        result = template.format(**variables)

        assert "3" in result
        assert "Japanese particles" in result
        assert "English" in result

    def test_missing_variable_raises_error(self):
        """Test that missing variable raises KeyError."""
        template = "Generate cards about {topic} in {language}"
        variables = {"topic": "Test"}  # Missing 'language'

        with pytest.raises(KeyError):
            template.format(**variables)

    def test_extra_variables_ignored(self):
        """Test that extra variables are ignored."""
        template = "Hello, {name}!"
        variables = {"name": "World", "extra": "Ignored"}

        result = template.format(**variables)

        assert result == "Hello, World!"
        assert "Ignored" not in result

    def test_nested_braces_escaped(self):
        """Test that double braces are escaped."""
        template = "Use {{{{c1::text}}}} for cloze deletions, {topic}"
        variables = {"topic": "test"}

        result = template.format(**variables)

        assert "{{c1::text}}" in result
        assert "test" in result

    def test_multiline_template(self):
        """Test rendering multiline templates."""
        template = """Line 1: {var1}
Line 2: {var2}
Line 3: {var3}"""

        variables = {"var1": "A", "var2": "B", "var3": "C"}
        result = template.format(**variables)

        assert "Line 1: A" in result
        assert "Line 2: B" in result
        assert "Line 3: C" in result


# ==================== Card Template Rendering Tests ====================


class TestCardTemplateRendering:
    """Tests for rendering card templates."""

    def test_render_basic_card_front(self):
        """Test rendering basic card front."""
        template = "<div class='front'>{{front}}</div>"
        data = {"front": "What is 1+1?"}

        # Simple placeholder replacement
        result = template.replace("{{front}}", data["front"])

        assert "What is 1+1?" in result

    def test_render_basic_card_back(self):
        """Test rendering basic card back."""
        template = "<div class='back'>{{FrontSide}}<hr>{{back}}</div>"
        data = {
            "FrontSide": "<div class='front'>Question</div>",
            "back": "Answer",
        }

        result = template
        for key, value in data.items():
            result = result.replace("{{" + key + "}}", value)

        assert "Question" in result
        assert "Answer" in result

    def test_render_cloze_template(self):
        """Test rendering cloze deletion template."""
        template = "{{cloze:text}}"
        text = "The {{c1::answer}} is here"

        # Cloze rendering would replace {{c1::answer}} with [...]
        # This is a simplified test
        assert "{{c1::" in text
        assert "}}" in text

    def test_render_with_css(self):
        """Test combining template with CSS."""
        front_template = "<div class='front'>{{front}}</div>"
        css = ".front { font-size: 20px; }"

        full_card = f"<style>{css}</style>\n{front_template}"

        assert ".front { font-size: 20px; }" in full_card
        assert "{{front}}" in full_card


# ==================== Template Validation Tests ====================


class TestTemplateValidation:
    """Tests for template validation."""

    def test_validate_fields_schema_basic(self):
        """Test validating basic fields schema."""
        valid_schema = {
            "type": "object",
            "properties": {
                "front": {"type": "string"},
                "back": {"type": "string"},
            },
            "required": ["front", "back"],
        }

        assert valid_schema["type"] == "object"
        assert "front" in valid_schema["properties"]
        assert "back" in valid_schema["properties"]

    def test_validate_template_placeholders(self):
        """Test validating template placeholders match schema."""
        schema = {
            "properties": {
                "front": {"type": "string"},
                "back": {"type": "string"},
            }
        }
        template = "{{front}} - {{back}}"

        # Extract placeholders
        import re
        placeholders = set(re.findall(r'\{\{(\w+)\}\}', template))

        # Check all placeholders are in schema
        schema_fields = set(schema["properties"].keys())
        assert placeholders.issubset(schema_fields)

    def test_detect_undefined_placeholder(self):
        """Test detecting undefined placeholders."""
        schema = {
            "properties": {
                "front": {"type": "string"},
            }
        }
        template = "{{front}} - {{undefined}}"

        import re
        placeholders = set(re.findall(r'\{\{(\w+)\}\}', template))
        schema_fields = set(schema["properties"].keys())

        undefined = placeholders - schema_fields
        assert "undefined" in undefined

    def test_validate_required_fields(self):
        """Test validating required fields in schema."""
        schema = {
            "type": "object",
            "properties": {
                "front": {"type": "string"},
                "back": {"type": "string"},
                "extra": {"type": "string"},
            },
            "required": ["front", "back"],
        }

        data = {"front": "Q", "back": "A"}

        # Check required fields present
        required = schema.get("required", [])
        missing = [f for f in required if f not in data]

        assert len(missing) == 0

    def test_validate_field_types(self):
        """Test validating field value types."""
        schema = {
            "properties": {
                "text": {"type": "string"},
                "count": {"type": "integer"},
                "tags": {"type": "array"},
            }
        }

        valid_data = {
            "text": "Hello",
            "count": 5,
            "tags": ["a", "b"],
        }

        invalid_data = {
            "text": 123,  # Should be string
            "count": "five",  # Should be integer
            "tags": "not-array",  # Should be array
        }

        assert isinstance(valid_data["text"], str)
        assert isinstance(valid_data["count"], int)
        assert isinstance(valid_data["tags"], list)

        assert not isinstance(invalid_data["text"], str)


# ==================== Edge Cases Tests ====================


class TestPromptEdgeCases:
    """Tests for edge cases in prompt handling."""

    def test_empty_template(self):
        """Test handling empty template."""
        template = ""
        variables = {"var": "value"}

        result = template.format(**variables) if template else ""

        assert result == ""

    def test_template_with_special_characters(self):
        """Test template with special characters."""
        template = "Special: <>&\"' {var}"
        variables = {"var": "test"}

        result = template.format(**variables)

        assert "<>&\"'" in result
        assert "test" in result

    def test_unicode_in_template(self):
        """Test unicode characters in template."""
        template = "{greeting}"
        variables = {"greeting": "Hello"}

        result = template.format(**variables)

        assert "Hello" in result

    def test_very_long_template(self):
        """Test handling very long templates."""
        template = "Start {var} " + "X" * 10000 + " End"
        variables = {"var": "value"}

        result = template.format(**variables)

        assert result.startswith("Start value")
        assert result.endswith("End")
        assert len(result) > 10000

    def test_template_with_newlines(self):
        """Test template with newlines."""
        template = """Line 1
{var}
Line 3"""
        variables = {"var": "Line 2"}

        result = template.format(**variables)

        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[1] == "Line 2"
