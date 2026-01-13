"""Service layer for card templates operations."""

import logging
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import CardTemplate, TemplateField
from .schemas import TemplateCreate, TemplateFieldCreate, TemplateUpdate

logger = logging.getLogger(__name__)


class TemplateNotFoundError(Exception):
    """Raised when a template is not found."""

    def __init__(self, template_id: UUID) -> None:
        self.template_id = template_id
        super().__init__(f"Template with id {template_id} not found")


class TemplateNameExistsError(Exception):
    """Raised when a template name already exists for the user."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Template with name '{name}' already exists")


class SystemTemplateModificationError(Exception):
    """Raised when attempting to modify a system template."""

    def __init__(self, template_id: UUID) -> None:
        self.template_id = template_id
        super().__init__(f"Cannot modify system template {template_id}")


class TemplateService:
    """Service for managing card templates."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the template service.

        Args:
            session: SQLAlchemy async session for database operations.
        """
        self.session = session

    async def create(
        self,
        data: TemplateCreate,
        owner_id: UUID | None = None,
        is_system: bool = False,
    ) -> CardTemplate:
        """Create a new card template.

        Args:
            data: Template creation data.
            owner_id: ID of the user creating the template.
            is_system: Whether this is a system template.

        Returns:
            The created CardTemplate instance.

        Raises:
            TemplateNameExistsError: If template name already exists for user.
        """
        # Check for existing template with same name
        existing = await self._get_by_name(data.name, owner_id)
        if existing:
            raise TemplateNameExistsError(data.name)

        template = CardTemplate(
            name=data.name,
            display_name=data.display_name,
            fields_schema=data.fields_schema,
            front_template=data.front_template,
            back_template=data.back_template,
            css=data.css,
            is_system=is_system,
            owner_id=owner_id,
        )
        self.session.add(template)
        await self.session.flush()

        # Create template fields if provided
        if data.fields:
            await self._create_fields(template.id, data.fields)

        await self.session.refresh(template, ["fields"])
        logger.info(f"Created template {template.id} with name '{template.name}'")
        return template

    async def get_by_id(
        self,
        template_id: UUID,
        owner_id: UUID | None = None,
    ) -> CardTemplate:
        """Get a template by ID.

        Args:
            template_id: The template UUID.
            owner_id: Optional owner ID to filter by (also returns system templates).

        Returns:
            The CardTemplate instance.

        Raises:
            TemplateNotFoundError: If template not found or not accessible.
        """
        query = (
            select(CardTemplate)
            .options(selectinload(CardTemplate.fields))
            .where(CardTemplate.id == template_id)
        )

        if owner_id is not None:
            query = query.where(
                or_(
                    CardTemplate.owner_id == owner_id,
                    CardTemplate.is_system.is_(True),
                )
            )

        result = await self.session.execute(query)
        template = result.scalar_one_or_none()

        if template is None:
            raise TemplateNotFoundError(template_id)

        return template

    async def get_list(
        self,
        owner_id: UUID | None = None,
        include_system: bool = True,
        page: int = 1,
        size: int = 20,
    ) -> tuple[Sequence[CardTemplate], int]:
        """Get paginated list of templates.

        Args:
            owner_id: Filter by owner ID (also returns system templates if include_system).
            include_system: Include system templates in results.
            page: Page number (1-indexed).
            size: Number of items per page.

        Returns:
            Tuple of (templates list, total count).
        """
        query = select(CardTemplate).options(selectinload(CardTemplate.fields))

        if owner_id is not None:
            if include_system:
                query = query.where(
                    or_(
                        CardTemplate.owner_id == owner_id,
                        CardTemplate.is_system.is_(True),
                    )
                )
            else:
                query = query.where(CardTemplate.owner_id == owner_id)
        elif not include_system:
            query = query.where(CardTemplate.is_system.is_(False))

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.session.scalar(count_query) or 0

        # Apply pagination and ordering
        query = (
            query.order_by(CardTemplate.is_system.desc(), CardTemplate.name)
            .offset((page - 1) * size)
            .limit(size)
        )

        result = await self.session.execute(query)
        templates = result.scalars().all()

        return templates, total

    async def update(
        self,
        template_id: UUID,
        data: TemplateUpdate,
        owner_id: UUID | None = None,
    ) -> CardTemplate:
        """Update an existing template.

        Args:
            template_id: The template UUID.
            data: Template update data.
            owner_id: Owner ID for authorization check.

        Returns:
            The updated CardTemplate instance.

        Raises:
            TemplateNotFoundError: If template not found.
            SystemTemplateModificationError: If attempting to modify system template.
            TemplateNameExistsError: If new name already exists.
        """
        template = await self.get_by_id(template_id, owner_id)

        if template.is_system:
            raise SystemTemplateModificationError(template_id)

        # Check name uniqueness if changing name
        if data.name and data.name != template.name:
            existing = await self._get_by_name(data.name, owner_id)
            if existing and existing.id != template_id:
                raise TemplateNameExistsError(data.name)

        # Update fields
        update_data = data.model_dump(exclude_unset=True, exclude={"fields"})
        for field, value in update_data.items():
            setattr(template, field, value)

        # Update template fields if provided
        if data.fields is not None:
            await self._update_fields(template_id, data.fields)

        await self.session.flush()
        await self.session.refresh(template, ["fields"])

        logger.info(f"Updated template {template_id}")
        return template

    async def delete(
        self,
        template_id: UUID,
        owner_id: UUID | None = None,
    ) -> None:
        """Delete a template.

        Args:
            template_id: The template UUID.
            owner_id: Owner ID for authorization check.

        Raises:
            TemplateNotFoundError: If template not found.
            SystemTemplateModificationError: If attempting to delete system template.
        """
        template = await self.get_by_id(template_id, owner_id)

        if template.is_system:
            raise SystemTemplateModificationError(template_id)

        await self.session.delete(template)
        await self.session.flush()

        logger.info(f"Deleted template {template_id}")

    async def get_system_templates(self) -> Sequence[CardTemplate]:
        """Get all system templates.

        Returns:
            List of system CardTemplate instances.
        """
        query = (
            select(CardTemplate)
            .options(selectinload(CardTemplate.fields))
            .where(CardTemplate.is_system.is_(True))
            .order_by(CardTemplate.name)
        )

        result = await self.session.execute(query)
        return result.scalars().all()

    async def create_system_template(self, data: TemplateCreate) -> CardTemplate:
        """Create a system template.

        Args:
            data: Template creation data.

        Returns:
            The created system CardTemplate instance.
        """
        return await self.create(data, owner_id=None, is_system=True)

    async def _get_by_name(
        self,
        name: str,
        owner_id: UUID | None,
    ) -> CardTemplate | None:
        """Get template by name for a specific owner.

        Args:
            name: Template name.
            owner_id: Owner ID (checks system templates if None).

        Returns:
            CardTemplate if found, None otherwise.
        """
        query = select(CardTemplate).where(CardTemplate.name == name)

        if owner_id is not None:
            query = query.where(
                or_(
                    CardTemplate.owner_id == owner_id,
                    CardTemplate.is_system.is_(True),
                )
            )
        else:
            query = query.where(CardTemplate.is_system.is_(True))

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _create_fields(
        self,
        template_id: UUID,
        fields: list[TemplateFieldCreate],
    ) -> None:
        """Create template fields.

        Args:
            template_id: Parent template ID.
            fields: List of field creation data.
        """
        for field_data in fields:
            field = TemplateField(
                template_id=template_id,
                name=field_data.name,
                field_type=field_data.field_type,
                is_required=field_data.is_required,
                order=field_data.order,
            )
            self.session.add(field)

    async def _update_fields(
        self,
        template_id: UUID,
        fields: list[TemplateFieldCreate],
    ) -> None:
        """Update template fields (replace all).

        Args:
            template_id: Parent template ID.
            fields: New list of field data.
        """
        # Delete existing fields
        query = select(TemplateField).where(TemplateField.template_id == template_id)
        result = await self.session.execute(query)
        for field in result.scalars().all():
            await self.session.delete(field)

        # Create new fields
        await self._create_fields(template_id, fields)
