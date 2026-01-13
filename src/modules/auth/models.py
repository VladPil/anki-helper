"""Authentication-related SQLAlchemy models."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.modules.users.models import User


class RefreshToken(UUIDMixin, TimestampMixin, Base):
    """Refresh token model for JWT token refresh.

    Stores refresh tokens with expiration and revocation tracking.
    Each user can have multiple active refresh tokens (multi-device support).

    Attributes:
        id: UUID7 primary key (from UUIDMixin).
        user_id: Foreign key to the associated user.
        token: The refresh token string (hashed for security).
        expires_at: When the token expires.
        revoked_at: When the token was revoked (null if active).
        created_at: Timestamp when token was created (from TimestampMixin).
        updated_at: Timestamp when token was last updated (from TimestampMixin).
        user: Related user object (back-reference).
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    user: Mapped["User"] = relationship("User", lazy="selectin")

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired.

        Returns:
            True if the token has expired, False otherwise.
        """
        return datetime.now(UTC) > self.expires_at

    @property
    def is_revoked(self) -> bool:
        """Check if the token has been revoked.

        Returns:
            True if the token has been revoked, False otherwise.
        """
        return self.revoked_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if the token is valid (not expired and not revoked).

        Returns:
            True if the token is valid, False otherwise.
        """
        return not self.is_expired and not self.is_revoked

    def revoke(self) -> None:
        """Revoke this refresh token.

        Sets the revoked_at timestamp to the current time.
        """
        self.revoked_at = datetime.now(UTC)
