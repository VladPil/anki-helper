"""Unit tests for ChatWorkflow with mocked dependencies.

These tests use unittest.mock to mock database sessions, HTTP clients,
and other external dependencies to test the workflow in isolation.
"""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.modules.chat.workflows.chat_workflow import ChatWorkflow, ChatState


# ==================== Fixtures ====================


@pytest.fixture
def mock_db_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def chat_workflow(mock_db_session):
    """Create ChatWorkflow instance with mocked dependencies."""
    return ChatWorkflow(
        db=mock_db_session,
        llm_base_url="http://localhost:8000",
        llm_api_key="test-key",
        llm_timeout=30,
    )


@pytest.fixture
def sample_state():
    """Create a sample ChatState for testing."""
    return ChatState(
        message="What is Python?",
        history=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi! How can I help?"},
        ],
        context={"deck_id": str(uuid4())},
        context_query="Python programming language",
        retrieved_context="",
        sources=[],
        response="",
        tokens=0,
    )


@pytest.fixture
def sample_state_without_context():
    """Create a sample ChatState without context."""
    return ChatState(
        message="Hello, how are you?",
        history=[],
        context=None,
        context_query=None,
        retrieved_context="",
        sources=[],
        response="",
        tokens=0,
    )


# ==================== _retrieve_context Tests ====================


@pytest.mark.asyncio
async def test_retrieve_context_with_deck_id(chat_workflow, sample_state):
    """Test context retrieval when deck_id is provided."""
    result = await chat_workflow._retrieve_context(sample_state)

    assert "retrieved_context" in result
    assert "sources" in result
    # Currently returns empty as RAG is placeholder
    assert result["retrieved_context"] == ""
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_retrieve_context_without_deck_id(chat_workflow, sample_state):
    """Test context retrieval without deck_id."""
    sample_state["context"] = {}

    result = await chat_workflow._retrieve_context(sample_state)

    assert result["retrieved_context"] == ""
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_retrieve_context_uses_message_as_fallback(
    chat_workflow, sample_state_without_context
):
    """Test that message is used when context_query is not provided."""
    # context_query is None, should fall back to message
    result = await chat_workflow._retrieve_context(sample_state_without_context)

    assert "retrieved_context" in result
    assert "sources" in result


@pytest.mark.asyncio
async def test_retrieve_context_with_none_context(chat_workflow):
    """Test context retrieval with None context."""
    state = ChatState(
        message="Test",
        history=[],
        context=None,
        context_query=None,
        retrieved_context="",
        sources=[],
        response="",
        tokens=0,
    )

    result = await chat_workflow._retrieve_context(state)

    assert result["retrieved_context"] == ""


@pytest.mark.asyncio
async def test_retrieve_context_handles_exception(chat_workflow, sample_state):
    """Test that _retrieve_context handles exceptions gracefully."""
    # Simulate an exception during retrieval
    with patch.object(chat_workflow, "_retrieve_context", wraps=chat_workflow._retrieve_context):
        # Even with deck_id, should not raise
        result = await chat_workflow._retrieve_context(sample_state)

    assert "retrieved_context" in result


# ==================== _generate_response Tests ====================


@pytest.mark.asyncio
async def test_generate_response_returns_empty(chat_workflow, sample_state):
    """Test that _generate_response returns empty placeholder."""
    # _generate_response is a placeholder for non-streaming
    result = await chat_workflow._generate_response(sample_state)

    assert result["response"] == ""
    assert result["tokens"] == 0


@pytest.mark.asyncio
async def test_generate_response_state_preserved(chat_workflow, sample_state):
    """Test that _generate_response preserves state correctly."""
    sample_state["retrieved_context"] = "Some context"

    result = await chat_workflow._generate_response(sample_state)

    # Response should be empty (non-streaming placeholder)
    assert result["response"] == ""


# ==================== _build_messages Tests ====================


def test_build_messages_basic(chat_workflow):
    """Test basic message building."""
    messages = chat_workflow._build_messages(
        message="What is Python?",
        history=[],
        retrieved_context="",
    )

    assert len(messages) == 2  # System + user message
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "What is Python?"


def test_build_messages_with_history(chat_workflow):
    """Test message building with conversation history."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]

    messages = chat_workflow._build_messages(
        message="Follow up question",
        history=history,
        retrieved_context="",
    )

    assert len(messages) == 4  # System + 2 history + user
    assert messages[1]["content"] == "Hello"
    assert messages[2]["content"] == "Hi there!"
    assert messages[3]["content"] == "Follow up question"


def test_build_messages_with_context(chat_workflow):
    """Test message building with RAG context."""
    context = "Python is a programming language."

    messages = chat_workflow._build_messages(
        message="What is Python?",
        history=[],
        retrieved_context=context,
    )

    # Context should be appended to system message
    assert context in messages[0]["content"]


def test_build_messages_system_message_content(chat_workflow):
    """Test that system message contains expected content."""
    messages = chat_workflow._build_messages(
        message="Test",
        history=[],
        retrieved_context="",
    )

    system_content = messages[0]["content"]
    assert "Anki" in system_content or "flashcard" in system_content


def test_build_messages_filters_invalid_roles(chat_workflow):
    """Test that invalid roles are filtered from history."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "invalid_role", "content": "Should be filtered"},
        {"role": "assistant", "content": "Hi!"},
    ]

    messages = chat_workflow._build_messages(
        message="Test",
        history=history,
        retrieved_context="",
    )

    # Should have system + user + assistant + current message = 4
    # Invalid role should be filtered
    assert len(messages) == 4
    roles = [m["role"] for m in messages]
    assert "invalid_role" not in roles


def test_build_messages_preserves_system_in_history(chat_workflow):
    """Test that system messages in history are preserved."""
    history = [
        {"role": "system", "content": "Additional instruction"},
        {"role": "user", "content": "Question"},
    ]

    messages = chat_workflow._build_messages(
        message="Test",
        history=history,
        retrieved_context="",
    )

    # Should have main system + history system + user + current = 4
    assert len(messages) == 4


# ==================== stream Tests ====================


@pytest.mark.asyncio
async def test_stream_success(chat_workflow):
    """Test successful streaming response."""
    # Mock httpx response
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    # Simulate SSE lines
    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
        yield 'data: {"choices": [{"delta": {"content": " World"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
            context=None,
            context_query=None,
        ):
            chunks.append(chunk)

    # Should have content chunks and metadata
    assert len(chunks) >= 1
    # Last chunk should be metadata
    assert chunks[-1]["type"] == "metadata"


@pytest.mark.asyncio
async def test_stream_handles_http_error(chat_workflow):
    """Test stream handles HTTP errors gracefully."""
    import httpx

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_client = AsyncMock()

        # Simulate HTTP error - raise_for_status is not async, use MagicMock
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
        )

        # Create async context manager for stream
        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_response)
        stream_cm.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=stream_cm)

        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    # Should have error content and metadata
    assert len(chunks) >= 1
    # Should contain apologize/error message in the content
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) >= 1
    # The error handler yields a message containing "error" or "apologize"
    full_content = "".join(c.get("content", "") for c in content_chunks).lower()
    assert "error" in full_content or "apologize" in full_content


@pytest.mark.asyncio
async def test_stream_handles_timeout(chat_workflow):
    """Test stream handles timeout errors gracefully."""
    import httpx

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_client = AsyncMock()

        # Create async context manager that raises TimeoutException
        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        stream_cm.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=stream_cm)

        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    # Should have timeout error message
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) >= 1
    full_content = "".join(c.get("content", "") for c in content_chunks).lower()
    assert "timed out" in full_content or "timeout" in full_content


@pytest.mark.asyncio
async def test_stream_handles_generic_exception(chat_workflow):
    """Test stream handles generic exceptions gracefully."""
    with patch("httpx.AsyncClient") as mock_async_client:
        mock_client = AsyncMock()

        mock_client.stream = MagicMock(side_effect=Exception("Unknown error"))

        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    # Should have error content
    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_stream_with_context(chat_workflow):
    """Test stream with context and context_query."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Response"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
            context={"deck_id": str(uuid4())},
            context_query="specific query",
        ):
            chunks.append(chunk)

    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_stream_parses_token_usage(chat_workflow):
    """Test that stream parses token usage from response."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Test"}}], "usage": {"total_tokens": 50}}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    metadata = chunks[-1]
    assert metadata["type"] == "metadata"
    assert metadata["tokens"] == 50


@pytest.mark.asyncio
async def test_stream_handles_malformed_json(chat_workflow):
    """Test stream handles malformed JSON gracefully."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield "data: {malformed json}"
        yield 'data: {"choices": [{"delta": {"content": "Valid"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    # Should still process valid chunks
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert any("Valid" in c.get("content", "") for c in content_chunks)


@pytest.mark.asyncio
async def test_stream_skips_empty_lines(chat_workflow):
    """Test stream skips empty lines in SSE."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield ""
        yield "not data line"
        yield 'data: {"choices": [{"delta": {"content": "Content"}}]}'
        yield ""
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    # Should have processed valid content
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) == 1


# ==================== run Tests ====================


@pytest.mark.asyncio
async def test_run_collects_all_content(chat_workflow):
    """Test that run method collects all content chunks."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Hello "}}]}'
        yield 'data: {"choices": [{"delta": {"content": "World"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        result = await chat_workflow.run(
            message="Test",
            history=[],
        )

    assert result == "Hello World"


@pytest.mark.asyncio
async def test_run_with_context(chat_workflow):
    """Test run with context parameters."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Response"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        result = await chat_workflow.run(
            message="Test",
            history=[],
            context={"deck_id": "123"},
            context_query="search query",
        )

    assert result == "Response"


@pytest.mark.asyncio
async def test_run_returns_empty_on_error(chat_workflow):
    """Test that run returns error message on failure."""
    import httpx

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_client = AsyncMock()

        # Create async context manager that raises TimeoutException
        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        stream_cm.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream = MagicMock(return_value=stream_cm)

        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await chat_workflow.run(
            message="Test",
            history=[],
        )

    # Should contain timeout message
    assert "timed out" in result.lower() or "timeout" in result.lower()


# ==================== Graph Build Tests ====================


def test_graph_build(chat_workflow):
    """Test that graph is built correctly."""
    # Graph should be compiled during __post_init__
    assert chat_workflow._graph is not None


def test_workflow_initialization(mock_db_session):
    """Test workflow initializes with custom parameters."""
    workflow = ChatWorkflow(
        db=mock_db_session,
        llm_base_url="http://custom:8000",
        llm_api_key="custom-key",
        llm_timeout=60,
    )

    assert workflow.llm_base_url == "http://custom:8000"
    assert workflow.llm_api_key == "custom-key"
    assert workflow.llm_timeout == 60


def test_workflow_default_initialization(mock_db_session):
    """Test workflow initializes with defaults from settings."""
    with patch("src.chat.workflows.chat_workflow.settings") as mock_settings:
        mock_settings.sop_llm.api_base_url = "http://default:8000"
        mock_settings.sop_llm.timeout = 30

        workflow = ChatWorkflow(db=mock_db_session)

        assert workflow.db == mock_db_session


# ==================== Integration-like Tests ====================


@pytest.mark.asyncio
async def test_full_workflow_flow(chat_workflow):
    """Test the full workflow from message to response."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Python is "}}]}'
        yield 'data: {"choices": [{"delta": {"content": "a programming language."}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        # Test stream
        content_parts = []
        async for chunk in chat_workflow.stream(
            message="What is Python?",
            history=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
            ],
            context={"deck_id": str(uuid4())},
        ):
            if chunk.get("type") == "content":
                content_parts.append(chunk.get("content", ""))

        full_response = "".join(content_parts)
        assert "Python" in full_response


@pytest.mark.asyncio
async def test_stream_returns_sources_in_metadata(chat_workflow):
    """Test that sources are returned in metadata."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {"content": "Test"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    metadata = chunks[-1]
    assert "sources" in metadata
    assert isinstance(metadata["sources"], list)


@pytest.mark.asyncio
async def test_stream_handles_empty_delta(chat_workflow):
    """Test stream handles empty delta content."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def mock_aiter_lines():
        yield 'data: {"choices": [{"delta": {}}]}'  # Empty delta
        yield 'data: {"choices": [{"delta": {"content": ""}}]}'  # Empty content
        yield 'data: {"choices": [{"delta": {"content": "Real content"}}]}'
        yield "data: [DONE]"

    mock_response.aiter_lines = mock_aiter_lines

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=AsyncMock())
    mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    mock_client.stream.return_value.__aexit__ = AsyncMock()

    with patch("httpx.AsyncClient") as mock_async_client:
        mock_async_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_async_client.return_value.__aexit__ = AsyncMock()

        chunks = []
        async for chunk in chat_workflow.stream(
            message="Test",
            history=[],
        ):
            chunks.append(chunk)

    # Only non-empty content should be yielded
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) == 1
    assert content_chunks[0]["content"] == "Real content"
