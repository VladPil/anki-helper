"""SQLAlchemy model mixins for common functionality."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .uuid7 import UUID7, uuid7


class UUIDMixin:
    """Mixin providing a UUID7 primary key.

    This mixin adds an 'id' column that uses UUID7 for time-ordered
    unique identifiers. UUID7 is preferred over UUID4 for database
    primary keys as it provides better index locality.

    Example:
        class User(UUIDMixin, Base):
            __tablename__ = "users"
            name: Mapped[str] = mapped_column(String(100))
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID7,
        primary_key=True,
        default=uuid7,
        nullable=False,
    )


class TimestampMixin:
    """Mixin providing created_at and updated_at timestamps.

    Automatically sets created_at on insert and updates updated_at
    on every update operation.

    Example:
        class User(TimestampMixin, Base):
            __tablename__ = "users"
            name: Mapped[str] = mapped_column(String(100))
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin providing soft delete functionality.

    Instead of permanently deleting records, this mixin allows marking
    them as deleted by setting a deleted_at timestamp. Records with
    deleted_at set should be filtered out in normal queries.

    Example:
        class User(SoftDeleteMixin, Base):
            __tablename__ = "users"
            name: Mapped[str] = mapped_column(String(100))

        # To soft delete:
        user.deleted_at = datetime.now(timezone.utc)

        # To query non-deleted:
        query.where(User.deleted_at.is_(None))
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record has been soft deleted.

        Returns:
            True if the record is soft deleted, False otherwise.
        """
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as soft deleted.

        Sets the deleted_at timestamp to the current time.
        """

        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft deleted record.

        Clears the deleted_at timestamp, making the record active again.
        """
        self.deleted_at = None


class AuditMixin:
    """Mixin providing audit trail fields for user tracking.

    Tracks which user created and last updated the record. The user
    identifiers are stored as strings to accommodate various ID formats.

    Example:
        class Document(AuditMixin, Base):
            __tablename__ = "documents"
            title: Mapped[str] = mapped_column(String(200))
    """

    created_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
    )

    updated_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
    )

    def set_created_by(self, user_id: str) -> None:
        """Set the user who created this record.

        Args:
            user_id: The identifier of the user creating the record.
        """
        self.created_by = user_id
        self.updated_by = user_id

    def set_updated_by(self, user_id: str) -> None:
        """Set the user who last updated this record.

        Args:
            user_id: The identifier of the user updating the record.
        """
        self.updated_by = user_id


class FullMixin(UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Combined mixin providing all common fields.

    This mixin combines UUID primary key, timestamps, soft delete,
    and audit fields into a single convenient mixin.

    Includes:
        - id: UUID7 primary key
        - created_at, updated_at: Timestamps
        - deleted_at: Soft delete timestamp
        - created_by, updated_by: Audit user tracking

    Example:
        class User(FullMixin, Base):
            __tablename__ = "users"
            name: Mapped[str] = mapped_column(String(100))
    """

    pass
