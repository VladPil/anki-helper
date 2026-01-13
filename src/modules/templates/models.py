"""SQLAlchemy models for card templates."""

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.mixins import TimestampMixin, UUIDMixin


class CardTemplate(UUIDMixin, TimestampMixin, Base):
    """Card template model for defining Anki card structures.

    Attributes:
        name: Unique identifier name for the template (e.g., 'basic', 'cloze').
        display_name: Human-readable name shown in UI.
        fields_schema: JSON schema defining the fields structure.
        front_template: HTML/Jinja2 template for card front.
        back_template: HTML/Jinja2 template for card back.
        css: Optional CSS styles for the card.
        is_system: Whether this is a system-provided template (non-deletable).
        owner_id: User who created the template (null for system templates).
    """

    __tablename__ = "card_templates"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    fields_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    front_template: Mapped[str] = mapped_column(Text, nullable=False)
    back_template: Mapped[str] = mapped_column(Text, nullable=False)
    css: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relationships
    fields: Mapped[list["TemplateField"]] = relationship(
        "TemplateField",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TemplateField.order",
    )


class TemplateField(UUIDMixin, Base):
    """Field definition for a card template.

    Attributes:
        template_id: Reference to the parent template.
        name: Field name used in templates (e.g., 'front', 'back', 'extra').
        field_type: Type of the field ('text', 'html', 'image', 'audio').
        is_required: Whether this field must be filled.
        order: Display order of the field.
    """

    __tablename__ = "template_fields"

    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("card_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    template: Mapped["CardTemplate"] = relationship(
        "CardTemplate",
        back_populates="fields",
    )
