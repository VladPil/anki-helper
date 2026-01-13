"""Service layer for prompts operations."""

import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from jinja2 import Environment, TemplateSyntaxError, UndefinedError, meta
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Prompt, PromptCategory, PromptExecution
from .schemas import PromptCreate, PromptExecutionCreate, PromptUpdate

logger = logging.getLogger(__name__)


class PromptNotFoundError(Exception):
    """Raised when a prompt is not found."""

    def __init__(self, prompt_id: UUID) -> None:
        self.prompt_id = prompt_id
        super().__init__(f"Prompt with id {prompt_id} not found")


class PromptNameExistsError(Exception):
    """Raised when a prompt name already exists."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Prompt with name '{name}' already exists")


class PromptRenderError(Exception):
    """Raised when prompt rendering fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


class PromptValidationError(Exception):
    """Raised when prompt validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)


class PromptService:
    """Service for managing prompts and their executions."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the prompt service.

        Args:
            session: SQLAlchemy async session for database operations.
        """
        self.session = session
        self._jinja_env = Environment(autoescape=True)

    async def create(
        self,
        data: PromptCreate,
        created_by: str | None = None,
    ) -> Prompt:
        """Create a new prompt.

        Args:
            data: Prompt creation data.
            created_by: ID of the user creating the prompt.

        Returns:
            The created Prompt instance.

        Raises:
            PromptNameExistsError: If prompt name already exists.
            PromptValidationError: If prompt template is invalid.
        """
        # Check for existing prompt with same name
        existing = await self._get_by_name(data.name)
        if existing:
            raise PromptNameExistsError(data.name)

        # Validate templates
        self._validate_template(data.user_prompt_template, data.variables_schema)

        prompt = Prompt(
            name=data.name,
            description=data.description,
            category=data.category,
            system_prompt=data.system_prompt,
            user_prompt_template=data.user_prompt_template,
            variables_schema=data.variables_schema,
            preferred_model_id=data.preferred_model_id,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            is_active=True,
            version=1,
        )

        if created_by:
            prompt.set_created_by(created_by)

        self.session.add(prompt)
        await self.session.flush()

        logger.info(f"Created prompt {prompt.id} with name '{prompt.name}'")
        return prompt

    async def get_by_id(self, prompt_id: UUID) -> Prompt:
        """Get a prompt by ID.

        Args:
            prompt_id: The prompt UUID.

        Returns:
            The Prompt instance.

        Raises:
            PromptNotFoundError: If prompt not found.
        """
        query = select(Prompt).where(Prompt.id == prompt_id)
        result = await self.session.execute(query)
        prompt = result.scalar_one_or_none()

        if prompt is None:
            raise PromptNotFoundError(prompt_id)

        return prompt

    async def get_list(
        self,
        category: PromptCategory | None = None,
        is_active: bool | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[Sequence[Prompt], int]:
        """Get paginated list of prompts.

        Args:
            category: Optional filter by category.
            is_active: Optional filter by active status.
            page: Page number (1-indexed).
            size: Number of items per page.

        Returns:
            Tuple of (prompts list, total count).
        """
        query = select(Prompt)

        if category is not None:
            query = query.where(Prompt.category == category)
        if is_active is not None:
            query = query.where(Prompt.is_active == is_active)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query) or 0

        # Apply pagination and ordering
        query = query.order_by(Prompt.category, Prompt.name).offset((page - 1) * size).limit(size)

        result = await self.session.execute(query)
        prompts = result.scalars().all()

        return prompts, total

    async def update(
        self,
        prompt_id: UUID,
        data: PromptUpdate,
        updated_by: str | None = None,
        create_version: bool = False,
    ) -> Prompt:
        """Update an existing prompt.

        Args:
            prompt_id: The prompt UUID.
            data: Prompt update data.
            updated_by: ID of the user updating the prompt.
            create_version: If True, creates a new version instead of updating in place.

        Returns:
            The updated Prompt instance.

        Raises:
            PromptNotFoundError: If prompt not found.
            PromptNameExistsError: If new name already exists.
            PromptValidationError: If prompt template is invalid.
        """
        prompt = await self.get_by_id(prompt_id)

        # Check name uniqueness if changing name
        if data.name and data.name != prompt.name:
            existing = await self._get_by_name(data.name)
            if existing and existing.id != prompt_id:
                raise PromptNameExistsError(data.name)

        # Validate template if updating
        if data.user_prompt_template or data.variables_schema:
            template = data.user_prompt_template or prompt.user_prompt_template
            schema = data.variables_schema or prompt.variables_schema
            self._validate_template(template, schema)

        if create_version:
            # Create a new version
            new_prompt = await self._create_version(prompt, data, updated_by)
            return new_prompt

        # Update in place
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(prompt, field, value)

        if updated_by:
            prompt.set_updated_by(updated_by)

        await self.session.flush()
        logger.info(f"Updated prompt {prompt_id}")
        return prompt

    async def delete(self, prompt_id: UUID) -> None:
        """Delete a prompt.

        Args:
            prompt_id: The prompt UUID.

        Raises:
            PromptNotFoundError: If prompt not found.
        """
        prompt = await self.get_by_id(prompt_id)
        await self.session.delete(prompt)
        await self.session.flush()

        logger.info(f"Deleted prompt {prompt_id}")

    async def render(
        self,
        prompt_id: UUID,
        variables: dict[str, Any],
    ) -> tuple[str, str]:
        """Render a prompt with the given variables.

        Args:
            prompt_id: The prompt UUID.
            variables: Variables to render into the template.

        Returns:
            Tuple of (rendered_system_prompt, rendered_user_prompt).

        Raises:
            PromptNotFoundError: If prompt not found.
            PromptRenderError: If rendering fails.
        """
        prompt = await self.get_by_id(prompt_id)

        if not prompt.is_active:
            raise PromptRenderError(
                f"Prompt {prompt_id} is not active",
                details={"prompt_id": str(prompt_id)},
            )

        try:
            # Render system prompt (may also have variables)
            system_template = self._jinja_env.from_string(prompt.system_prompt)
            rendered_system = system_template.render(**variables)

            # Render user prompt
            user_template = self._jinja_env.from_string(prompt.user_prompt_template)
            rendered_user = user_template.render(**variables)

            return rendered_system, rendered_user

        except UndefinedError as e:
            raise PromptRenderError(
                f"Missing variable in template: {e}",
                details={"error": str(e), "variables": list(variables.keys())},
            ) from e
        except TemplateSyntaxError as e:
            raise PromptRenderError(
                f"Template syntax error: {e}",
                details={"error": str(e), "line": e.lineno},
            ) from e

    async def record_execution(
        self,
        data: PromptExecutionCreate,
    ) -> PromptExecution:
        """Record a prompt execution.

        Args:
            data: Execution data to record.

        Returns:
            The created PromptExecution instance.
        """
        execution = PromptExecution(
            prompt_id=data.prompt_id,
            user_id=data.user_id,
            model_id=data.model_id,
            rendered_system_prompt=data.rendered_system_prompt,
            rendered_user_prompt=data.rendered_user_prompt,
            variables=data.variables,
            response_text=data.response_text,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            latency_ms=data.latency_ms,
            trace_id=data.trace_id,
        )

        self.session.add(execution)
        await self.session.flush()

        logger.info(f"Recorded execution {execution.id} for prompt {data.prompt_id}")
        return execution

    async def get_executions(
        self,
        prompt_id: UUID | None = None,
        user_id: UUID | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[Sequence[PromptExecution], int]:
        """Get paginated list of prompt executions.

        Args:
            prompt_id: Optional filter by prompt ID.
            user_id: Optional filter by user ID.
            page: Page number (1-indexed).
            size: Number of items per page.

        Returns:
            Tuple of (executions list, total count).
        """
        query = select(PromptExecution)

        if prompt_id is not None:
            query = query.where(PromptExecution.prompt_id == prompt_id)
        if user_id is not None:
            query = query.where(PromptExecution.user_id == user_id)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query) or 0

        # Apply pagination and ordering
        query = (
            query.order_by(PromptExecution.created_at.desc()).offset((page - 1) * size).limit(size)
        )

        result = await self.session.execute(query)
        executions = result.scalars().all()

        return executions, total

    async def get_versions(self, prompt_id: UUID) -> Sequence[Prompt]:
        """Get all versions of a prompt.

        Args:
            prompt_id: The prompt UUID (can be any version).

        Returns:
            List of all versions, ordered by version number.
        """
        # Find the root prompt
        prompt = await self.get_by_id(prompt_id)

        # Walk up to find the root
        root_id = prompt_id
        while prompt.parent_id is not None:
            root_id = prompt.parent_id
            prompt = await self.get_by_id(root_id)

        # Get all prompts in the version chain
        versions = [prompt]
        await self._collect_children(prompt.id, versions)

        return sorted(versions, key=lambda p: p.version)

    async def _collect_children(
        self,
        parent_id: UUID,
        versions: list[Prompt],
    ) -> None:
        """Recursively collect child versions.

        Args:
            parent_id: Parent prompt ID.
            versions: List to append children to.
        """
        query = select(Prompt).where(Prompt.parent_id == parent_id)
        result = await self.session.execute(query)

        for child in result.scalars().all():
            versions.append(child)
            await self._collect_children(child.id, versions)

    async def _create_version(
        self,
        original: Prompt,
        data: PromptUpdate,
        updated_by: str | None,
    ) -> Prompt:
        """Create a new version of a prompt.

        Args:
            original: The original prompt to version.
            data: Update data for the new version.
            updated_by: ID of the user creating the version.

        Returns:
            The new Prompt version.
        """
        # Deactivate original
        original.is_active = False

        # Create new version with merged data
        new_prompt = Prompt(
            name=data.name or original.name,
            description=data.description if data.description is not None else original.description,
            category=data.category or original.category,
            system_prompt=data.system_prompt or original.system_prompt,
            user_prompt_template=data.user_prompt_template or original.user_prompt_template,
            variables_schema=data.variables_schema or original.variables_schema,
            preferred_model_id=data.preferred_model_id
            if data.preferred_model_id is not None
            else original.preferred_model_id,
            temperature=data.temperature if data.temperature is not None else original.temperature,
            max_tokens=data.max_tokens if data.max_tokens is not None else original.max_tokens,
            is_active=True,
            version=original.version + 1,
            parent_id=original.id,
        )

        if updated_by:
            new_prompt.set_created_by(updated_by)

        self.session.add(new_prompt)
        await self.session.flush()

        logger.info(f"Created new version {new_prompt.version} of prompt {original.name}")
        return new_prompt

    async def _get_by_name(self, name: str) -> Prompt | None:
        """Get prompt by name.

        Args:
            name: Prompt name.

        Returns:
            Prompt if found, None otherwise.
        """
        query = select(Prompt).where(Prompt.name == name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    def _validate_template(
        self,
        template: str,
        variables_schema: dict[str, Any],
    ) -> None:
        """Validate a Jinja2 template against a variables schema.

        Args:
            template: The Jinja2 template string.
            variables_schema: JSON schema for variables.

        Raises:
            PromptValidationError: If template is invalid.
        """
        errors = []

        # Parse template to find variables
        try:
            ast = self._jinja_env.parse(template)
            template_vars = meta.find_undeclared_variables(ast)
        except TemplateSyntaxError as e:
            raise PromptValidationError(
                f"Invalid template syntax at line {e.lineno}: {e.message}",
                errors=[str(e)],
            ) from e

        # Get required variables from schema
        schema_properties = variables_schema.get("properties", {})
        required_vars = set(variables_schema.get("required", []))

        # Check for undefined variables
        schema_vars = set(schema_properties.keys())
        undefined_vars = template_vars - schema_vars

        if undefined_vars:
            errors.append(f"Template uses undefined variables: {', '.join(sorted(undefined_vars))}")

        # Check for unused required variables (warning, not error)
        unused_required = required_vars - template_vars
        if unused_required:
            logger.warning(
                f"Template does not use required variables: {', '.join(sorted(unused_required))}"
            )

        if errors:
            raise PromptValidationError(
                "Template validation failed",
                errors=errors,
            )

    def extract_template_variables(self, template: str) -> set[str]:
        """Extract variable names from a Jinja2 template.

        Args:
            template: The Jinja2 template string.

        Returns:
            Set of variable names used in the template.
        """
        try:
            ast = self._jinja_env.parse(template)
            return meta.find_undeclared_variables(ast)
        except TemplateSyntaxError:
            return set()
