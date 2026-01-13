"""SQLAlchemy models for chat sessions and messages."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base
from src.shared.mixins import TimestampMixin, UUIDMixin


class ChatSession(UUIDMixin, TimestampMixin, Base):
    """Chat session model for storing conversation sessions.

    Attributes:
        id: UUID7 primary key.
        user_id: Foreign key to the user who owns the session.
        title: Display title for the session.
        context: Optional JSON context data (e.g., deck_id, topic).
        messages: List of messages in the session.
        created_at: Timestamp when session was created.
        updated_at: Timestamp when session was last updated.
    """

    __tablename__ = "chat_sessions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ChatMessage(UUIDMixin, TimestampMixin, Base):
    """Chat message model for storing individual messages.

    Attributes:
        id: UUID7 primary key.
        session_id: Foreign key to the parent session.
        role: Message role (user, assistant, system).
        content: Message text content.
        tokens: Token count for the message (optional).
        session: Parent chat session.
        created_at: Timestamp when message was created.
        updated_at: Timestamp when message was last updated.
    """

    __tablename__ = "chat_messages"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
