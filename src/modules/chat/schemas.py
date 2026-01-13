"""Pydantic schemas for chat module."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field

from src.shared.schemas import BaseSchema, UUIDTimestampSchema


class MessageRole(StrEnum):
    """Enumeration of message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class StreamEventType(StrEnum):
    """Enumeration of SSE stream event types."""

    CONTENT = "content"
    DONE = "done"
    ERROR = "error"
    METADATA = "metadata"


# ==================== Chat Session Schemas ====================


class ChatSessionCreate(BaseSchema):
    """Schema for creating a new chat session.

    Attributes:
        title: Display title for the session.
        context: Optional context data (e.g., deck_id, topic).
    """

    title: str = Field(
        min_length=1,
        max_length=255,
        description="Display title for the chat session",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Optional context data (e.g., deck_id, topic)",
    )


class ChatSessionUpdate(BaseSchema):
    """Schema for updating a chat session.

    Attributes:
        title: New display title for the session.
        context: Updated context data.
    """

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="New display title for the chat session",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Updated context data",
    )


class ChatSessionResponse(UUIDTimestampSchema):
    """Response schema for a chat session.

    Attributes:
        id: Session UUID.
        user_id: UUID of the session owner.
        title: Display title.
        context: Session context data.
        message_count: Number of messages in the session.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    user_id: UUID = Field(description="UUID of the session owner")
    title: str = Field(description="Display title for the chat session")
    context: dict[str, Any] | None = Field(description="Session context data")
    message_count: int = Field(
        default=0,
        description="Number of messages in the session",
    )


class ChatSessionWithMessages(ChatSessionResponse):
    """Response schema for a chat session with messages included.

    Attributes:
        messages: List of messages in the session.
    """

    messages: list["ChatMessageResponse"] = Field(
        default_factory=list,
        description="List of messages in the session",
    )


# ==================== Chat Message Schemas ====================


class ChatMessageCreate(BaseSchema):
    """Schema for creating a new chat message.

    Attributes:
        content: Message text content.
        context_query: Optional RAG query for context retrieval.
    """

    content: str = Field(
        min_length=1,
        max_length=10000,
        description="Message text content",
    )
    context_query: str | None = Field(
        default=None,
        description="Optional query for RAG context retrieval",
    )


class ChatMessageResponse(UUIDTimestampSchema):
    """Response schema for a chat message.

    Attributes:
        id: Message UUID.
        session_id: UUID of the parent session.
        role: Message role (user, assistant, system).
        content: Message text content.
        tokens: Token count for the message.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    session_id: UUID = Field(description="UUID of the parent session")
    role: MessageRole = Field(description="Message role")
    content: str = Field(description="Message text content")
    tokens: int | None = Field(
        default=None,
        description="Token count for the message",
    )


# ==================== Streaming Schemas ====================


class StreamChunk(BaseSchema):
    """Schema for a streaming response chunk.

    Used for Server-Sent Events (SSE) streaming responses.

    Attributes:
        event: Type of the stream event.
        data: Chunk data (content text or metadata).
        message_id: UUID of the message being streamed.
        done: Whether streaming is complete.
    """

    event: StreamEventType = Field(
        default=StreamEventType.CONTENT,
        description="Type of the stream event",
    )
    data: str = Field(description="Chunk data")
    message_id: UUID | None = Field(
        default=None,
        description="UUID of the message being streamed",
    )
    done: bool = Field(
        default=False,
        description="Whether streaming is complete",
    )


class StreamMetadata(BaseSchema):
    """Schema for stream metadata sent at the end of streaming.

    Attributes:
        message_id: UUID of the completed message.
        total_tokens: Total token count for the response.
        sources: List of sources used for RAG context.
    """

    message_id: UUID = Field(description="UUID of the completed message")
    total_tokens: int | None = Field(
        default=None,
        description="Total token count for the response",
    )
    sources: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of sources used for RAG context",
    )


class StreamError(BaseSchema):
    """Schema for stream error events.

    Attributes:
        error_code: Error code for programmatic handling.
        message: Human-readable error message.
        retry: Whether the client should retry.
    """

    error_code: str = Field(description="Error code for programmatic handling")
    message: str = Field(description="Human-readable error message")
    retry: bool = Field(
        default=False,
        description="Whether the client should retry",
    )


# Update forward references
ChatSessionWithMessages.model_rebuild()
