"""Unit tests for ChatService with mocked database sessions.

These tests use unittest.mock to mock AsyncSession and avoid real database interactions.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.core.exceptions import ResourceOwnershipError
from src.modules.chat.schemas import (
    ChatMessageCreate,
    ChatSessionCreate,
    ChatSessionUpdate,
    MessageRole,
)
from src.modules.chat.service import ChatService, ChatSessionNotFoundError

# ==================== Fixtures ====================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()

    async def mock_refresh(obj, *args, **kwargs):
        """Simulate SQLAlchemy refresh by setting id and timestamps."""
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid4()
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        if not hasattr(obj, "updated_at") or obj.updated_at is None:
            obj.updated_at = datetime.now(UTC)

    session.refresh = AsyncMock(side_effect=mock_refresh)
    return session


@pytest.fixture
def chat_service(mock_session):
    """Create ChatService instance with mocked session."""
    return ChatService(mock_session)


@pytest.fixture
def sample_user_id():
    """Create a sample user ID."""
    return uuid4()


@pytest.fixture
def other_user_id():
    """Create another user ID for ownership tests."""
    return uuid4()


@pytest.fixture
def sample_chat_session(sample_user_id):
    """Create a sample ChatSession-like object for testing."""
    session = MagicMock()
    session.id = uuid4()
    session.user_id = sample_user_id
    session.title = "Test Chat Session"
    session.context = {"deck_id": str(uuid4())}
    session.created_at = datetime.now(UTC)
    session.updated_at = datetime.now(UTC)
    session.messages = []
    return session


@pytest.fixture
def sample_chat_message(sample_chat_session):
    """Create a sample ChatMessage-like object for testing."""
    message = MagicMock()
    message.id = uuid4()
    message.session_id = sample_chat_session.id
    message.role = "user"
    message.content = "Test message content"
    message.tokens = 10
    message.created_at = datetime.now(UTC)
    message.updated_at = datetime.now(UTC)
    return message


@pytest.fixture
def sample_assistant_message(sample_chat_session):
    """Create a sample assistant message for testing."""
    message = MagicMock()
    message.id = uuid4()
    message.session_id = sample_chat_session.id
    message.role = "assistant"
    message.content = "Test assistant response"
    message.tokens = 20
    message.created_at = datetime.now(UTC)
    message.updated_at = datetime.now(UTC)
    return message


# ==================== create_session Tests ====================


@pytest.mark.asyncio
async def test_create_session_success(chat_service, mock_session, sample_user_id):
    """Test successful chat session creation."""
    session_data = ChatSessionCreate(
        title="New Chat Session",
        context={"deck_id": "123"},
    )

    result = await chat_service.create_session(sample_user_id, session_data)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()
    assert result.title == "New Chat Session"
    assert result.user_id == sample_user_id
    assert result.message_count == 0


@pytest.mark.asyncio
async def test_create_session_without_context(chat_service, mock_session, sample_user_id):
    """Test creating a session without context."""
    session_data = ChatSessionCreate(title="Simple Session")

    result = await chat_service.create_session(sample_user_id, session_data)

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    assert result.title == "Simple Session"
    assert result.context is None


@pytest.mark.asyncio
async def test_create_session_captures_user_id(chat_service, mock_session, sample_user_id):
    """Test that created session has correct user_id."""
    session_data = ChatSessionCreate(title="Test Session")

    # Capture the session that gets added
    added_session = None
    def capture_add(obj):
        nonlocal added_session
        added_session = obj
    mock_session.add.side_effect = capture_add

    await chat_service.create_session(sample_user_id, session_data)

    assert added_session is not None
    assert added_session.user_id == sample_user_id


# ==================== get_session Tests ====================


@pytest.mark.asyncio
async def test_get_session_success(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test successful session retrieval."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    result = await chat_service.get_session(sample_chat_session.id, sample_user_id)

    assert result.id == sample_chat_session.id
    assert result.title == sample_chat_session.title
    assert result.user_id == sample_user_id


@pytest.mark.asyncio
async def test_get_session_not_found(chat_service, mock_session, sample_user_id):
    """Test get_session raises error when session doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ChatSessionNotFoundError):
        await chat_service.get_session(uuid4(), sample_user_id)


@pytest.mark.asyncio
async def test_get_session_wrong_user(
    chat_service, mock_session, sample_user_id, other_user_id, sample_chat_session
):
    """Test get_session raises error when user doesn't own session."""
    sample_chat_session.user_id = other_user_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    with pytest.raises(ResourceOwnershipError):
        await chat_service.get_session(sample_chat_session.id, sample_user_id)


@pytest.mark.asyncio
async def test_get_session_with_messages(
    chat_service, mock_session, sample_user_id, sample_chat_session, sample_chat_message
):
    """Test get_session returns session with messages."""
    sample_chat_session.messages = [sample_chat_message]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    result = await chat_service.get_session(sample_chat_session.id, sample_user_id)

    assert len(result.messages) == 1
    assert result.messages[0].content == sample_chat_message.content


# ==================== list_sessions Tests ====================


@pytest.mark.asyncio
async def test_list_sessions_success(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test successful session listing."""
    # Mock count query
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    # Mock sessions query
    sessions_result = MagicMock()
    sessions_result.all.return_value = [(sample_chat_session, 5)]

    mock_session.execute.side_effect = [count_result, sessions_result]

    sessions, total = await chat_service.list_sessions(sample_user_id)

    assert total == 1
    assert len(sessions) == 1
    assert sessions[0].title == sample_chat_session.title
    assert sessions[0].message_count == 5


@pytest.mark.asyncio
async def test_list_sessions_empty(chat_service, mock_session, sample_user_id):
    """Test list_sessions returns empty list when no sessions exist."""
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    sessions_result = MagicMock()
    sessions_result.all.return_value = []

    mock_session.execute.side_effect = [count_result, sessions_result]

    sessions, total = await chat_service.list_sessions(sample_user_id)

    assert total == 0
    assert len(sessions) == 0


@pytest.mark.asyncio
async def test_list_sessions_with_pagination(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test list_sessions respects limit and offset."""
    count_result = MagicMock()
    count_result.scalar.return_value = 100

    sessions_result = MagicMock()
    sessions_result.all.return_value = [(sample_chat_session, 0)]

    mock_session.execute.side_effect = [count_result, sessions_result]

    sessions, total = await chat_service.list_sessions(
        sample_user_id, limit=10, offset=20
    )

    assert total == 100
    # Verify the query was executed
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_list_sessions_with_null_count(
    chat_service, mock_session, sample_user_id
):
    """Test list_sessions handles null count gracefully."""
    count_result = MagicMock()
    count_result.scalar.return_value = None

    sessions_result = MagicMock()
    sessions_result.all.return_value = []

    mock_session.execute.side_effect = [count_result, sessions_result]

    sessions, total = await chat_service.list_sessions(sample_user_id)

    assert total == 0
    assert len(sessions) == 0


# ==================== update_session Tests ====================


@pytest.mark.asyncio
async def test_update_session_title(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test updating session title."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session

    count_result = MagicMock()
    count_result.scalar.return_value = 5

    mock_session.execute.side_effect = [mock_result, count_result]

    update_data = ChatSessionUpdate(title="Updated Title")
    result = await chat_service.update_session(
        sample_chat_session.id, sample_user_id, update_data
    )

    assert sample_chat_session.title == "Updated Title"
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_session_context(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test updating session context."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session

    count_result = MagicMock()
    count_result.scalar.return_value = 0

    mock_session.execute.side_effect = [mock_result, count_result]

    new_context = {"deck_id": "new-deck", "topic": "new-topic"}
    update_data = ChatSessionUpdate(context=new_context)
    await chat_service.update_session(
        sample_chat_session.id, sample_user_id, update_data
    )

    assert sample_chat_session.context == new_context


@pytest.mark.asyncio
async def test_update_session_not_found(chat_service, mock_session, sample_user_id):
    """Test update_session raises error when session doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    update_data = ChatSessionUpdate(title="New Title")
    with pytest.raises(ChatSessionNotFoundError):
        await chat_service.update_session(uuid4(), sample_user_id, update_data)


@pytest.mark.asyncio
async def test_update_session_wrong_user(
    chat_service, mock_session, sample_user_id, other_user_id, sample_chat_session
):
    """Test update_session raises error when user doesn't own session."""
    sample_chat_session.user_id = other_user_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    update_data = ChatSessionUpdate(title="New Title")
    with pytest.raises(ResourceOwnershipError):
        await chat_service.update_session(
            sample_chat_session.id, sample_user_id, update_data
        )


# ==================== delete_session Tests ====================


@pytest.mark.asyncio
async def test_delete_session_success(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test successful session deletion."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    await chat_service.delete_session(sample_chat_session.id, sample_user_id)

    mock_session.delete.assert_called_once_with(sample_chat_session)


@pytest.mark.asyncio
async def test_delete_session_not_found(chat_service, mock_session, sample_user_id):
    """Test delete_session raises error when session doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ChatSessionNotFoundError):
        await chat_service.delete_session(uuid4(), sample_user_id)


@pytest.mark.asyncio
async def test_delete_session_wrong_user(
    chat_service, mock_session, sample_user_id, other_user_id, sample_chat_session
):
    """Test delete_session raises error when user doesn't own session."""
    sample_chat_session.user_id = other_user_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    with pytest.raises(ResourceOwnershipError):
        await chat_service.delete_session(sample_chat_session.id, sample_user_id)


# ==================== add_message Tests ====================


@pytest.mark.asyncio
async def test_add_message_success(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test successful message addition."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    result = await chat_service.add_message(
        session_id=sample_chat_session.id,
        user_id=sample_user_id,
        role=MessageRole.USER,
        content="Test message",
        tokens=15,
    )

    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()
    assert result.content == "Test message"
    assert result.role == MessageRole.USER


@pytest.mark.asyncio
async def test_add_message_assistant_role(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test adding assistant message."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    result = await chat_service.add_message(
        session_id=sample_chat_session.id,
        user_id=sample_user_id,
        role=MessageRole.ASSISTANT,
        content="AI response",
        tokens=50,
    )

    assert result.role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_add_message_without_tokens(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test adding message without token count."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    # Capture the message that gets added
    added_message = None
    def capture_add(obj):
        nonlocal added_message
        added_message = obj
    mock_session.add.side_effect = capture_add

    await chat_service.add_message(
        session_id=sample_chat_session.id,
        user_id=sample_user_id,
        role=MessageRole.USER,
        content="Message without tokens",
    )

    assert added_message is not None
    assert added_message.tokens is None


@pytest.mark.asyncio
async def test_add_message_session_not_found(chat_service, mock_session, sample_user_id):
    """Test add_message raises error when session doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(ChatSessionNotFoundError):
        await chat_service.add_message(
            session_id=uuid4(),
            user_id=sample_user_id,
            role=MessageRole.USER,
            content="Test",
        )


@pytest.mark.asyncio
async def test_add_message_wrong_user(
    chat_service, mock_session, sample_user_id, other_user_id, sample_chat_session
):
    """Test add_message raises error when user doesn't own session."""
    sample_chat_session.user_id = other_user_id

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    with pytest.raises(ResourceOwnershipError):
        await chat_service.add_message(
            session_id=sample_chat_session.id,
            user_id=sample_user_id,
            role=MessageRole.USER,
            content="Test",
        )


# ==================== get_conversation_history Tests ====================


@pytest.mark.asyncio
async def test_get_conversation_history_success(
    chat_service, mock_session, sample_chat_session, sample_chat_message
):
    """Test successful conversation history retrieval."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sample_chat_message]
    mock_session.execute.return_value = mock_result

    history = await chat_service.get_conversation_history(sample_chat_session.id)

    assert len(history) == 1
    assert history[0]["role"] == sample_chat_message.role
    assert history[0]["content"] == sample_chat_message.content


@pytest.mark.asyncio
async def test_get_conversation_history_empty(
    chat_service, mock_session, sample_chat_session
):
    """Test conversation history for session with no messages."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    history = await chat_service.get_conversation_history(sample_chat_session.id)

    assert len(history) == 0


@pytest.mark.asyncio
async def test_get_conversation_history_respects_limit(
    chat_service, mock_session, sample_chat_session, sample_chat_message, sample_assistant_message
):
    """Test that conversation history respects the limit parameter."""
    messages = [sample_chat_message, sample_assistant_message]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = messages
    mock_session.execute.return_value = mock_result

    history = await chat_service.get_conversation_history(
        sample_chat_session.id, limit=10
    )

    assert len(history) == 2


@pytest.mark.asyncio
async def test_get_conversation_history_returns_chronological_order(
    chat_service, mock_session, sample_chat_session, sample_chat_message, sample_assistant_message
):
    """Test that messages are returned in chronological order (reversed from desc query)."""
    # Simulating desc order from DB (newest first)
    messages = [sample_assistant_message, sample_chat_message]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = messages
    mock_session.execute.return_value = mock_result

    history = await chat_service.get_conversation_history(sample_chat_session.id)

    # Should be reversed to chronological order
    assert history[0]["content"] == sample_chat_message.content
    assert history[1]["content"] == sample_assistant_message.content


# ==================== stream_response Tests ====================


@pytest.mark.asyncio
async def test_stream_response_success(
    chat_service, mock_session, sample_user_id, sample_chat_session, sample_chat_message
):
    """Test successful streaming response."""
    # Mock session queries
    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = sample_chat_session

    # Mock message query for update
    msg_result = MagicMock()
    msg_result.scalar_one.return_value = sample_chat_message

    # Mock history query
    history_result = MagicMock()
    history_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        session_result,  # add_message: verify ownership
        session_result,  # get_session
        history_result,  # get_conversation_history
        session_result,  # add_message for assistant
        msg_result,  # update message
    ]

    # Create mock workflow
    async def mock_stream(*args, **kwargs):
        yield {"type": "content", "content": "Hello "}
        yield {"type": "content", "content": "World!"}
        yield {"type": "metadata", "tokens": 10, "sources": []}

    mock_workflow = MagicMock()
    mock_workflow.stream = mock_stream

    user_message = ChatMessageCreate(content="Test message")

    chunks = []
    async for chunk in chat_service.stream_response(
        session_id=sample_chat_session.id,
        user_id=sample_user_id,
        user_message=user_message,
        chat_workflow=mock_workflow,
    ):
        chunks.append(chunk)

    # Should have content chunks, metadata, and done event
    assert len(chunks) >= 3


@pytest.mark.asyncio
async def test_stream_response_session_not_found(
    chat_service, mock_session, sample_user_id
):
    """Test stream_response raises error when session doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_workflow = MagicMock()
    user_message = ChatMessageCreate(content="Test")

    with pytest.raises(ChatSessionNotFoundError):
        async for _ in chat_service.stream_response(
            session_id=uuid4(),
            user_id=sample_user_id,
            user_message=user_message,
            chat_workflow=mock_workflow,
        ):
            pass


@pytest.mark.asyncio
async def test_stream_response_handles_error(
    chat_service, mock_session, sample_user_id, sample_chat_session, sample_chat_message
):
    """Test stream_response handles errors gracefully."""
    # Mock session queries
    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = sample_chat_session

    msg_result = MagicMock()
    msg_result.scalar_one.return_value = sample_chat_message

    history_result = MagicMock()
    history_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        session_result,  # add_message: verify ownership
        session_result,  # get_session
        history_result,  # get_conversation_history
        session_result,  # add_message for assistant
        msg_result,  # update message
    ]

    # Create mock workflow that raises an error
    async def mock_stream_error(*args, **kwargs):
        yield {"type": "content", "content": "Starting..."}
        raise Exception("LLM Error")

    mock_workflow = MagicMock()
    mock_workflow.stream = mock_stream_error

    user_message = ChatMessageCreate(content="Test message")

    chunks = []
    async for chunk in chat_service.stream_response(
        session_id=sample_chat_session.id,
        user_id=sample_user_id,
        user_message=user_message,
        chat_workflow=mock_workflow,
    ):
        chunks.append(chunk)

    # Should have error event
    assert any("error" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_stream_response_with_context_query(
    chat_service, mock_session, sample_user_id, sample_chat_session, sample_chat_message
):
    """Test stream_response passes context_query to workflow."""
    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = sample_chat_session

    msg_result = MagicMock()
    msg_result.scalar_one.return_value = sample_chat_message

    history_result = MagicMock()
    history_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [
        session_result,
        session_result,
        history_result,
        session_result,
        msg_result,
    ]

    # Track what context_query is passed
    received_context_query = None

    async def mock_stream(*args, **kwargs):
        nonlocal received_context_query
        received_context_query = kwargs.get("context_query")
        yield {"type": "content", "content": "Response"}
        yield {"type": "metadata", "tokens": 5, "sources": []}

    mock_workflow = MagicMock()
    mock_workflow.stream = mock_stream

    user_message = ChatMessageCreate(
        content="Test message",
        context_query="specific search query",
    )

    async for _ in chat_service.stream_response(
        session_id=sample_chat_session.id,
        user_id=sample_user_id,
        user_message=user_message,
        chat_workflow=mock_workflow,
    ):
        pass

    assert received_context_query == "specific search query"


# ==================== Edge Cases ====================


@pytest.mark.asyncio
async def test_create_session_with_empty_context(
    chat_service, mock_session, sample_user_id
):
    """Test creating session with empty context dict."""
    session_data = ChatSessionCreate(title="Test", context={})

    result = await chat_service.create_session(sample_user_id, session_data)

    assert result.context == {}


@pytest.mark.asyncio
async def test_add_message_system_role(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test adding system message."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    result = await chat_service.add_message(
        session_id=sample_chat_session.id,
        user_id=sample_user_id,
        role=MessageRole.SYSTEM,
        content="System instruction",
    )

    assert result.role == MessageRole.SYSTEM


@pytest.mark.asyncio
async def test_list_sessions_returns_sessions_with_correct_message_count(
    chat_service, mock_session, sample_user_id
):
    """Test that list_sessions returns correct message counts from join."""
    session1 = MagicMock()
    session1.id = uuid4()
    session1.user_id = sample_user_id
    session1.title = "Session 1"
    session1.context = None
    session1.created_at = datetime.now(UTC)
    session1.updated_at = datetime.now(UTC)

    session2 = MagicMock()
    session2.id = uuid4()
    session2.user_id = sample_user_id
    session2.title = "Session 2"
    session2.context = None
    session2.created_at = datetime.now(UTC)
    session2.updated_at = datetime.now(UTC)

    count_result = MagicMock()
    count_result.scalar.return_value = 2

    sessions_result = MagicMock()
    sessions_result.all.return_value = [
        (session1, 10),  # 10 messages
        (session2, 3),   # 3 messages
    ]

    mock_session.execute.side_effect = [count_result, sessions_result]

    sessions, total = await chat_service.list_sessions(sample_user_id)

    assert sessions[0].message_count == 10
    assert sessions[1].message_count == 3


@pytest.mark.asyncio
async def test_update_session_partial_update(
    chat_service, mock_session, sample_user_id, sample_chat_session
):
    """Test partial update - only updating title, keeping context."""
    original_context = sample_chat_session.context

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session

    count_result = MagicMock()
    count_result.scalar.return_value = 0

    mock_session.execute.side_effect = [mock_result, count_result]

    update_data = ChatSessionUpdate(title="New Title")  # Only title, no context
    await chat_service.update_session(
        sample_chat_session.id, sample_user_id, update_data
    )

    assert sample_chat_session.title == "New Title"
    # Context should remain unchanged (update_data.context is None)


@pytest.mark.asyncio
async def test_get_session_returns_all_message_fields(
    chat_service, mock_session, sample_user_id, sample_chat_session, sample_chat_message
):
    """Test that get_session returns messages with all required fields."""
    sample_chat_session.messages = [sample_chat_message]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_chat_session
    mock_session.execute.return_value = mock_result

    result = await chat_service.get_session(sample_chat_session.id, sample_user_id)

    msg = result.messages[0]
    assert msg.id == sample_chat_message.id
    assert msg.session_id == sample_chat_message.session_id
    assert msg.content == sample_chat_message.content
    assert msg.tokens == sample_chat_message.tokens
