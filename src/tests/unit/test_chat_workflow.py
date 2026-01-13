"""Unit tests for ChatWorkflow with mocked dependencies.

These tests use unittest.mock to mock database sessions, LLM client,
and other external dependencies to test the workflow in isolation.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.chat.workflows.chat_workflow import ChatState, ChatWorkflow

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
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock()
    client.generate_embeddings = AsyncMock(return_value=[[0.1, 0.2, 0.3] * 341])
    client.create_conversation = AsyncMock(return_value={"conversation_id": "conv_test123"})

    # Mock stream_task as an async generator
    async def mock_stream_task(**kwargs):
        yield {"choices": [{"delta": {"content": "Hello"}}]}
        yield {"choices": [{"delta": {"content": " World"}}]}
        yield {"usage": {"total_tokens": 50}}

    client.stream_task = mock_stream_task
    return client


@pytest.fixture
def chat_workflow(mock_db_session, mock_llm_client):
    """Create ChatWorkflow instance with mocked dependencies."""
    return ChatWorkflow(
        db=mock_db_session,
        llm_client=mock_llm_client,
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
    # Mock search_similar to return empty (no embeddings yet)
    with patch(
        "src.modules.chat.workflows.chat_workflow.EmbeddingService"
    ) as mock_embedding_cls:
        mock_embedding = AsyncMock()
        mock_embedding.search_similar = AsyncMock(return_value=[])
        mock_embedding_cls.return_value = mock_embedding

        result = await chat_workflow._retrieve_context(sample_state)

    assert "retrieved_context" in result
    assert "sources" in result
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
async def test_retrieve_context_with_rag_results(chat_workflow, sample_state):
    """Test context retrieval with actual RAG results."""
    # Mock card
    mock_card = MagicMock()
    mock_card.id = uuid4()
    mock_card.fields = {"Front": "Question", "Back": "Answer"}

    # Mock search_similar to return results
    with patch(
        "src.modules.chat.workflows.chat_workflow.EmbeddingService"
    ) as mock_embedding_cls:
        mock_embedding = AsyncMock()
        mock_embedding.search_similar = AsyncMock(return_value=[(mock_card, 0.85)])
        mock_embedding_cls.return_value = mock_embedding

        result = await chat_workflow._retrieve_context(sample_state)

    assert result["retrieved_context"] != ""
    assert len(result["sources"]) > 0
    assert "Question" in result["retrieved_context"]


@pytest.mark.asyncio
async def test_retrieve_context_handles_llm_connection_error(chat_workflow, sample_state):
    """Test that _retrieve_context handles LLM connection errors gracefully."""
    from src.core.llm_client import LLMConnectionError

    with patch(
        "src.modules.chat.workflows.chat_workflow.EmbeddingService"
    ) as mock_embedding_cls:
        mock_embedding = AsyncMock()
        mock_embedding.search_similar = AsyncMock(side_effect=LLMConnectionError("Connection failed"))
        mock_embedding_cls.return_value = mock_embedding

        result = await chat_workflow._retrieve_context(sample_state)

    # Should handle error gracefully
    assert result["retrieved_context"] == ""
    assert result["sources"] == []


# ==================== _generate_response Tests ====================


@pytest.mark.asyncio
async def test_generate_response_returns_empty(chat_workflow, sample_state):
    """Test that _generate_response returns empty placeholder."""
    result = await chat_workflow._generate_response(sample_state)

    assert result["response"] == ""
    assert result["tokens"] == 0


@pytest.mark.asyncio
async def test_generate_response_state_preserved(chat_workflow, sample_state):
    """Test that _generate_response preserves state correctly."""
    sample_state["retrieved_context"] = "Some context"

    result = await chat_workflow._generate_response(sample_state)

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
    assert "Anki" in system_content


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
async def test_stream_success(chat_workflow, mock_llm_client):
    """Test successful streaming response."""
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
async def test_stream_with_context(chat_workflow, mock_llm_client):
    """Test stream with context and context_query."""
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
async def test_stream_parses_token_usage(mock_db_session):
    """Test that stream parses token usage from response."""
    mock_client = AsyncMock()

    async def mock_stream_with_usage(**kwargs):
        yield {"choices": [{"delta": {"content": "Test"}}]}
        yield {"usage": {"total_tokens": 100}}

    mock_client.stream_task = mock_stream_with_usage
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    chunks = []
    async for chunk in workflow.stream(message="Test", history=[]):
        chunks.append(chunk)

    metadata = chunks[-1]
    assert metadata["type"] == "metadata"
    assert metadata["tokens"] == 100


@pytest.mark.asyncio
async def test_stream_handles_error_chunk(mock_db_session):
    """Test stream handles error chunks from LLM."""
    mock_client = AsyncMock()

    async def mock_stream_with_error(**kwargs):
        yield {"type": "error", "error": "Test error"}

    mock_client.stream_task = mock_stream_with_error
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    chunks = []
    async for chunk in workflow.stream(message="Test", history=[]):
        chunks.append(chunk)

    # Should have error content
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) >= 1
    assert "Ошибка" in content_chunks[0]["content"]


@pytest.mark.asyncio
async def test_stream_handles_thinking_chunk(mock_db_session):
    """Test stream handles thinking chunks (polling mode indicator)."""
    mock_client = AsyncMock()

    async def mock_stream_with_thinking(**kwargs):
        yield {"type": "thinking", "task_id": "task_abc123"}
        yield {"choices": [{"delta": {"content": "Response after thinking"}}]}
        yield {"usage": {"total_tokens": 50}}

    mock_client.stream_task = mock_stream_with_thinking
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    chunks = []
    async for chunk in workflow.stream(message="Test", history=[]):
        chunks.append(chunk)

    # Should have thinking chunk
    thinking_chunks = [c for c in chunks if c.get("type") == "thinking"]
    assert len(thinking_chunks) == 1
    assert thinking_chunks[0]["task_id"] == "task_abc123"

    # Should also have content
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) >= 1
    assert "Response after thinking" in content_chunks[0]["content"]


@pytest.mark.asyncio
async def test_stream_handles_llm_connection_error(mock_db_session):
    """Test stream handles LLM connection errors."""
    from src.core.llm_client import LLMConnectionError

    mock_client = AsyncMock()

    async def mock_stream_with_exception(**kwargs):
        raise LLMConnectionError("Cannot connect")
        yield  # Make it a generator

    mock_client.stream_task = mock_stream_with_exception
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    chunks = []
    async for chunk in workflow.stream(message="Test", history=[]):
        chunks.append(chunk)

    # Should have error message
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) >= 1
    assert "недоступен" in content_chunks[0]["content"]


@pytest.mark.asyncio
async def test_stream_handles_generic_exception(mock_db_session):
    """Test stream handles generic exceptions."""
    mock_client = AsyncMock()

    async def mock_stream_with_exception(**kwargs):
        raise Exception("Unknown error")
        yield  # Make it a generator

    mock_client.stream_task = mock_stream_with_exception
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    chunks = []
    async for chunk in workflow.stream(message="Test", history=[]):
        chunks.append(chunk)

    # Should have error content
    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) >= 1
    assert "ошибка" in content_chunks[0]["content"].lower()


@pytest.mark.asyncio
async def test_stream_handles_empty_delta(mock_db_session):
    """Test stream handles empty delta content."""
    mock_client = AsyncMock()

    async def mock_stream(**kwargs):
        yield {"choices": [{"delta": {}}]}  # Empty delta
        yield {"choices": [{"delta": {"content": ""}}]}  # Empty content
        yield {"choices": [{"delta": {"content": "Real content"}}]}

    mock_client.stream_task = mock_stream
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    chunks = []
    async for chunk in workflow.stream(message="Test", history=[]):
        chunks.append(chunk)

    content_chunks = [c for c in chunks if c.get("type") == "content"]
    assert len(content_chunks) == 1
    assert content_chunks[0]["content"] == "Real content"


@pytest.mark.asyncio
async def test_stream_with_sop_conversation_id(mock_db_session):
    """Test streaming with sop_conversation_id."""
    mock_client = AsyncMock()
    call_args = {}

    async def mock_stream(**kwargs):
        call_args.update(kwargs)
        yield {"choices": [{"delta": {"content": "Response"}}]}

    mock_client.stream_task = mock_stream
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    chunks = []
    async for chunk in workflow.stream(
        message="Test",
        history=[],
        sop_conversation_id="conv_test123",
    ):
        chunks.append(chunk)

    # Should have passed conversation_id to stream_task
    assert call_args.get("conversation_id") == "conv_test123"
    assert call_args.get("save_to_conversation") is True


# ==================== run Tests ====================


@pytest.mark.asyncio
async def test_run_collects_all_content(chat_workflow, mock_llm_client):
    """Test that run method collects all content chunks."""
    result = await chat_workflow.run(
        message="Test",
        history=[],
    )

    assert result == "Hello World"


@pytest.mark.asyncio
async def test_run_with_context(chat_workflow, mock_llm_client):
    """Test run with context parameters."""
    result = await chat_workflow.run(
        message="Test",
        history=[],
        context={"deck_id": "123"},
        context_query="search query",
    )

    assert "Hello" in result


@pytest.mark.asyncio
async def test_run_returns_error_message_on_failure(mock_db_session):
    """Test that run returns error message on failure."""
    from src.core.llm_client import LLMConnectionError

    mock_client = AsyncMock()

    async def mock_stream(**kwargs):
        raise LLMConnectionError("Cannot connect")
        yield

    mock_client.stream_task = mock_stream
    mock_client.generate_embeddings = AsyncMock(return_value=[])

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    result = await workflow.run(message="Test", history=[])

    assert "недоступен" in result


# ==================== create_sop_conversation Tests ====================


@pytest.mark.asyncio
async def test_create_sop_conversation_success(chat_workflow, mock_llm_client):
    """Test successful sop_llm conversation creation."""
    result = await chat_workflow.create_sop_conversation(
        system_prompt="Custom prompt",
        metadata={"test": True},
    )

    assert result == "conv_test123"


@pytest.mark.asyncio
async def test_create_sop_conversation_with_defaults(chat_workflow, mock_llm_client):
    """Test sop_llm conversation creation with default values."""
    result = await chat_workflow.create_sop_conversation()

    assert result == "conv_test123"


@pytest.mark.asyncio
async def test_create_sop_conversation_handles_error(mock_db_session):
    """Test sop_llm conversation creation handles errors."""
    from src.core.llm_client import LLMConnectionError

    mock_client = AsyncMock()
    mock_client.create_conversation = AsyncMock(
        side_effect=LLMConnectionError("Cannot connect")
    )

    workflow = ChatWorkflow(db=mock_db_session, llm_client=mock_client)

    result = await workflow.create_sop_conversation()

    assert result is None


# ==================== Graph Build Tests ====================


def test_graph_build(chat_workflow):
    """Test that graph is built correctly."""
    assert chat_workflow._graph is not None


def test_workflow_initialization(mock_db_session, mock_llm_client):
    """Test workflow initializes with custom LLM client."""
    workflow = ChatWorkflow(
        db=mock_db_session,
        llm_client=mock_llm_client,
    )

    assert workflow.db == mock_db_session
    assert workflow.llm_client == mock_llm_client


def test_workflow_default_initialization(mock_db_session):
    """Test workflow initializes with default LLM client from get_llm_client()."""
    from src.core.llm_client import LLMClient

    workflow = ChatWorkflow(db=mock_db_session)

    assert workflow.db == mock_db_session
    # The default_factory should create an LLMClient instance
    assert isinstance(workflow.llm_client, LLMClient)


# ==================== Integration-like Tests ====================


@pytest.mark.asyncio
async def test_full_workflow_flow(chat_workflow, mock_llm_client):
    """Test the full workflow from message to response."""
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
    assert "Hello" in full_response


@pytest.mark.asyncio
async def test_stream_returns_sources_in_metadata(chat_workflow, mock_llm_client):
    """Test that sources are returned in metadata."""
    chunks = []
    async for chunk in chat_workflow.stream(
        message="Test",
        history=[],
    ):
        chunks.append(chunk)

    metadata = chunks[-1]
    assert "sources" in metadata
    assert isinstance(metadata["sources"], list)
