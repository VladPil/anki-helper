"""Chat service for managing chat sessions and messages."""

import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import NotFoundError, ResourceOwnershipError

from .models import ChatMessage, ChatSession
from .schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatSessionWithMessages,
    MessageRole,
    StreamChunk,
    StreamError,
    StreamEventType,
    StreamMetadata,
)

logger = logging.getLogger(__name__)


class ChatSessionNotFoundError(NotFoundError):
    """Chat session not found error."""

    error_code = "CHAT_SESSION_NOT_FOUND"
    message = "Chat session not found"


class ChatService:
    """Service for managing chat sessions and messages.

    This service provides methods for:
    - Creating, retrieving, and deleting chat sessions
    - Adding messages to sessions
    - Streaming AI responses with SSE support

    Attributes:
        db: AsyncSession for database operations.
    """

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the chat service.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def create_session(
        self,
        user_id: UUID,
        data: ChatSessionCreate,
    ) -> ChatSessionResponse:
        """Create a new chat session.

        Args:
            user_id: UUID of the session owner.
            data: Session creation data.

        Returns:
            Created session response.
        """
        session = ChatSession(
            user_id=user_id,
            title=data.title,
            context=data.context,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)

        logger.info(
            "Created chat session %s for user %s",
            session.id,
            user_id,
        )

        return ChatSessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            context=session.context,
            message_count=0,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def get_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> ChatSessionWithMessages:
        """Get a chat session with messages.

        Args:
            session_id: UUID of the session.
            user_id: UUID of the requesting user.

        Returns:
            Session with messages.

        Raises:
            ChatSessionNotFoundError: If session doesn't exist.
            ResourceOwnershipError: If user doesn't own the session.
        """
        stmt = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id)
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            raise ChatSessionNotFoundError()

        if session.user_id != user_id:
            raise ResourceOwnershipError()

        messages = [
            ChatMessageResponse(
                id=msg.id,
                session_id=msg.session_id,
                role=MessageRole(msg.role),
                content=msg.content,
                tokens=msg.tokens,
                created_at=msg.created_at,
                updated_at=msg.updated_at,
            )
            for msg in session.messages
        ]

        return ChatSessionWithMessages(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            context=session.context,
            message_count=len(messages),
            messages=messages,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def list_sessions(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChatSessionResponse], int]:
        """List chat sessions for a user.

        Args:
            user_id: UUID of the user.
            limit: Maximum number of sessions to return.
            offset: Number of sessions to skip.

        Returns:
            Tuple of (sessions list, total count).
        """
        # Get total count
        count_stmt = (
            select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
        )
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get sessions with message counts
        stmt = (
            select(
                ChatSession,
                func.count(ChatMessage.id).label("message_count"),
            )
            .outerjoin(ChatMessage, ChatSession.id == ChatMessage.session_id)
            .where(ChatSession.user_id == user_id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        sessions = [
            ChatSessionResponse(
                id=session.id,
                user_id=session.user_id,
                title=session.title,
                context=session.context,
                message_count=message_count,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            for session, message_count in rows
        ]

        return sessions, total

    async def update_session(
        self,
        session_id: UUID,
        user_id: UUID,
        data: ChatSessionUpdate,
    ) -> ChatSessionResponse:
        """Update a chat session.

        Args:
            session_id: UUID of the session.
            user_id: UUID of the requesting user.
            data: Update data.

        Returns:
            Updated session response.

        Raises:
            ChatSessionNotFoundError: If session doesn't exist.
            ResourceOwnershipError: If user doesn't own the session.
        """
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            raise ChatSessionNotFoundError()

        if session.user_id != user_id:
            raise ResourceOwnershipError()

        if data.title is not None:
            session.title = data.title
        if data.context is not None:
            session.context = data.context

        await self.db.flush()
        await self.db.refresh(session)

        # Get message count
        count_stmt = (
            select(func.count())
            .select_from(ChatMessage)
            .where(ChatMessage.session_id == session_id)
        )
        count_result = await self.db.execute(count_stmt)
        message_count = count_result.scalar() or 0

        logger.info("Updated chat session %s", session_id)

        return ChatSessionResponse(
            id=session.id,
            user_id=session.user_id,
            title=session.title,
            context=session.context,
            message_count=message_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    async def delete_session(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> None:
        """Delete a chat session.

        Args:
            session_id: UUID of the session.
            user_id: UUID of the requesting user.

        Raises:
            ChatSessionNotFoundError: If session doesn't exist.
            ResourceOwnershipError: If user doesn't own the session.
        """
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            raise ChatSessionNotFoundError()

        if session.user_id != user_id:
            raise ResourceOwnershipError()

        await self.db.delete(session)
        logger.info("Deleted chat session %s", session_id)

    async def add_message(
        self,
        session_id: UUID,
        user_id: UUID,
        role: MessageRole,
        content: str,
        tokens: int | None = None,
    ) -> ChatMessageResponse:
        """Add a message to a chat session.

        Args:
            session_id: UUID of the session.
            user_id: UUID of the requesting user.
            role: Message role.
            content: Message content.
            tokens: Optional token count.

        Returns:
            Created message response.

        Raises:
            ChatSessionNotFoundError: If session doesn't exist.
            ResourceOwnershipError: If user doesn't own the session.
        """
        # Verify session ownership
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            raise ChatSessionNotFoundError()

        if session.user_id != user_id:
            raise ResourceOwnershipError()

        message = ChatMessage(
            session_id=session_id,
            role=role.value,
            content=content,
            tokens=tokens,
        )
        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)

        logger.debug(
            "Added %s message to session %s",
            role,
            session_id,
        )

        return ChatMessageResponse(
            id=message.id,
            session_id=message.session_id,
            role=MessageRole(message.role),
            content=message.content,
            tokens=message.tokens,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )

    async def get_conversation_history(
        self,
        session_id: UUID,
        limit: int = 20,
    ) -> list[dict]:
        """Get conversation history for a session.

        Args:
            session_id: UUID of the session.
            limit: Maximum number of messages to retrieve.

        Returns:
            List of message dicts with role and content.
        """
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = result.scalars().all()

        # Reverse to get chronological order
        return [{"role": msg.role, "content": msg.content} for msg in reversed(messages)]

    async def stream_response(
        self,
        session_id: UUID,
        user_id: UUID,
        user_message: ChatMessageCreate,
        chat_workflow: "ChatWorkflowProtocol",
    ) -> AsyncGenerator[str, None]:
        """Stream an AI response to a user message.

        This method:
        1. Saves the user message
        2. Retrieves conversation history
        3. Streams the AI response using the chat workflow
        4. Saves the complete assistant response

        Args:
            session_id: UUID of the session.
            user_id: UUID of the requesting user.
            user_message: User message data.
            chat_workflow: Chat workflow for generating responses.

        Yields:
            SSE-formatted strings for streaming.

        Raises:
            ChatSessionNotFoundError: If session doesn't exist.
            ResourceOwnershipError: If user doesn't own the session.
        """
        # Save user message
        await self.add_message(
            session_id=session_id,
            user_id=user_id,
            role=MessageRole.USER,
            content=user_message.content,
        )

        # Get session for context
        session = await self.get_session(session_id, user_id)

        # Get conversation history
        history = await self.get_conversation_history(session_id, limit=20)

        # Create placeholder for assistant message
        assistant_msg = await self.add_message(
            session_id=session_id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content="",  # Will be updated after streaming
        )

        accumulated_content = ""
        total_tokens = 0
        sources: list[dict] = []

        try:
            # Stream response from workflow
            async for chunk in chat_workflow.stream(
                message=user_message.content,
                history=history,
                context=session.context,
                context_query=user_message.context_query,
            ):
                if chunk.get("type") == "content":
                    content = chunk.get("content", "")
                    accumulated_content += content

                    stream_chunk = StreamChunk(
                        event=StreamEventType.CONTENT,
                        data=content,
                        message_id=assistant_msg.id,
                        done=False,
                    )
                    yield f"data: {stream_chunk.model_dump_json()}\n\n"

                elif chunk.get("type") == "metadata":
                    total_tokens = chunk.get("tokens", 0)
                    sources = chunk.get("sources", [])

            # Update assistant message with full content
            stmt = select(ChatMessage).where(ChatMessage.id == assistant_msg.id)
            result = await self.db.execute(stmt)
            msg = result.scalar_one()
            msg.content = accumulated_content
            msg.tokens = total_tokens if total_tokens > 0 else None
            await self.db.flush()

            # Send metadata
            metadata = StreamMetadata(
                message_id=assistant_msg.id,
                total_tokens=total_tokens if total_tokens > 0 else None,
                sources=sources,
            )
            yield f"event: metadata\ndata: {metadata.model_dump_json()}\n\n"

            # Send done event
            done_chunk = StreamChunk(
                event=StreamEventType.DONE,
                data="",
                message_id=assistant_msg.id,
                done=True,
            )
            yield f"event: done\ndata: {done_chunk.model_dump_json()}\n\n"

        except Exception as e:
            logger.exception("Error streaming response for session %s", session_id)

            # Update assistant message with error indicator
            stmt = select(ChatMessage).where(ChatMessage.id == assistant_msg.id)
            result = await self.db.execute(stmt)
            msg = result.scalar_one()
            msg.content = accumulated_content or "[Error generating response]"
            await self.db.flush()

            error = StreamError(
                error_code="STREAM_ERROR",
                message=str(e),
                retry=True,
            )
            yield f"event: error\ndata: {error.model_dump_json()}\n\n"


class ChatWorkflowProtocol:
    """Protocol for chat workflow implementations.

    This protocol defines the interface that chat workflows must implement
    to be used with ChatService.stream_response().
    """

    async def stream(
        self,
        message: str,
        history: list[dict],
        context: dict | None = None,
        context_query: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a response to a message.

        Args:
            message: User message content.
            history: Conversation history.
            context: Session context data.
            context_query: Optional RAG query.

        Yields:
            Response chunks with type and content.
        """
        raise NotImplementedError
        yield  # Make this a generator
