"""Интеграционные тесты для sop_llm сервиса.

Эти тесты выполняют реальные запросы к sop_llm.
Требуют запущенный sop_llm сервис.
"""

import httpx
import pytest

from src.core.config import settings
from src.core.llm_client import (
    LLMClient,
    LLMClientError,
    LLMConnectionError,
    get_llm_client,
)

# Default model to use in tests
# Use the local qwen model (always available), or claude-sonnet-4 if ANTHROPIC_API_KEY is set
TEST_MODEL = "qwen2.5-7b-ollama"
TEST_EMBEDDING_MODEL = "multilingual-e5-large"


@pytest.fixture
def llm_client() -> LLMClient:
    """Create LLM client for tests."""
    return LLMClient()


@pytest.fixture
async def available_model(llm_client: LLMClient) -> str | None:
    """Get an available model from sop_llm.

    Note: sop_llm uses internal model names for tasks that may differ
    from the display names in /api/v1/models/. We try to create a test
    task to determine the correct model name.
    """
    # First, try the default test model
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to create a minimal task to verify model availability
            response = await client.post(
                f"{llm_client.base_url}/api/v1/tasks/",
                json={"prompt": "test", "model": TEST_MODEL, "max_tokens": 1},
            )
            # Success is 201 Created
            if response.is_success:
                return TEST_MODEL
    except Exception:
        pass

    # If that fails, try to get model from the API and transform the name
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{llm_client.base_url}/api/v1/models/")
            if response.is_success:
                data = response.json()
                models = data.get("models", [])
                if models:
                    # Try the first model's name as-is
                    return models[0]["name"]
    except Exception:
        pass

    return None


@pytest.fixture
async def skip_if_llm_unavailable(llm_client: LLMClient):
    """Skip test if sop_llm is not available."""
    is_available = await llm_client.is_available()
    if not is_available:
        pytest.skip(f"sop_llm service not available at {settings.sop_llm.api_base_url}")


# ==================== Health Check Tests ====================


@pytest.mark.asyncio
@pytest.mark.integration
class TestLLMClientHealth:
    """Tests for LLM client health check."""

    async def test_is_available(self, llm_client: LLMClient):
        """Test health check returns boolean."""
        result = await llm_client.is_available()
        assert isinstance(result, bool)

    async def test_is_available_with_wrong_url(self):
        """Test health check with wrong URL returns False."""
        client = LLMClient(base_url="http://localhost:9999")
        result = await client.is_available()
        assert result is False


# ==================== Conversations API Tests ====================


@pytest.mark.asyncio
@pytest.mark.integration
class TestLLMClientConversations:
    """Tests for Conversations API."""

    async def test_create_conversation(
        self, llm_client: LLMClient, skip_if_llm_unavailable
    ):
        """Test creating a conversation."""
        result = await llm_client.create_conversation(
            system_prompt="You are a helpful assistant.",
            model=settings.sop_llm.default_model,
            metadata={"test": True},
        )

        assert "conversation_id" in result
        assert result["conversation_id"].startswith("conv_")

        # Cleanup
        await llm_client.delete_conversation(result["conversation_id"])

    async def test_get_conversation(
        self, llm_client: LLMClient, skip_if_llm_unavailable
    ):
        """Test getting a conversation."""
        # Create first
        create_result = await llm_client.create_conversation(
            system_prompt="Test system prompt",
        )
        conv_id = create_result["conversation_id"]

        # Get
        result = await llm_client.get_conversation(conv_id, include_messages=True)

        assert result is not None
        assert result["conversation_id"] == conv_id

        # Cleanup
        await llm_client.delete_conversation(conv_id)

    async def test_get_nonexistent_conversation(
        self, llm_client: LLMClient, skip_if_llm_unavailable
    ):
        """Test getting a nonexistent conversation returns None."""
        result = await llm_client.get_conversation("conv_nonexistent")
        assert result is None

    async def test_delete_conversation(
        self, llm_client: LLMClient, skip_if_llm_unavailable
    ):
        """Test deleting a conversation."""
        # Create first
        create_result = await llm_client.create_conversation()
        conv_id = create_result["conversation_id"]

        # Delete
        result = await llm_client.delete_conversation(conv_id)
        assert result is True

        # Verify deleted
        get_result = await llm_client.get_conversation(conv_id)
        assert get_result is None

    async def test_add_message_to_conversation(
        self, llm_client: LLMClient, skip_if_llm_unavailable
    ):
        """Test adding a message to a conversation."""
        # Create first
        create_result = await llm_client.create_conversation()
        conv_id = create_result["conversation_id"]

        # Add message
        result = await llm_client.add_message(
            conversation_id=conv_id,
            role="user",
            content="Hello, world!",
        )

        assert "content" in result or "id" in result

        # Cleanup
        await llm_client.delete_conversation(conv_id)


# ==================== Tasks API Tests ====================


@pytest.mark.asyncio
@pytest.mark.integration
class TestLLMClientTasks:
    """Tests for Tasks API."""

    async def test_create_task_with_prompt(
        self, llm_client: LLMClient, skip_if_llm_unavailable, available_model
    ):
        """Test creating a task with a prompt."""
        if not available_model:
            pytest.skip("No LLM model available in sop_llm")

        result = await llm_client.create_task(
            prompt="Say 'Hello' and nothing else.",
            model=available_model,
            temperature=0.1,
            max_tokens=10,
        )

        assert "task_id" in result
        assert result["task_id"].startswith("task")  # task_id starts with "task-" or "task_"

    async def test_create_task_with_messages(
        self, llm_client: LLMClient, skip_if_llm_unavailable, available_model
    ):
        """Test creating a task with messages array."""
        if not available_model:
            pytest.skip("No LLM model available in sop_llm")

        result = await llm_client.create_task(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hi' and nothing else."},
            ],
            model=available_model,
            temperature=0.1,
            max_tokens=10,
        )

        assert "task_id" in result

    async def test_get_task(
        self, llm_client: LLMClient, skip_if_llm_unavailable, available_model
    ):
        """Test getting task status."""
        if not available_model:
            pytest.skip("No LLM model available in sop_llm")

        # Create task first
        create_result = await llm_client.create_task(
            prompt="Say 'Test'",
            model=available_model,
            max_tokens=5,
        )
        task_id = create_result["task_id"]

        # Get task
        result = await llm_client.get_task(task_id)

        assert result is not None
        assert result["task_id"] == task_id
        assert "status" in result

    async def test_wait_for_task(
        self, llm_client: LLMClient, skip_if_llm_unavailable, available_model
    ):
        """Test waiting for task completion."""
        if not available_model:
            pytest.skip("No LLM model available in sop_llm")

        # Create task
        create_result = await llm_client.create_task(
            prompt="Say exactly: 'Done'",
            model=available_model,
            temperature=0,
            max_tokens=10,
        )
        task_id = create_result["task_id"]

        # Wait for completion
        result = await llm_client.wait_for_task(task_id, poll_interval=0.5, max_wait=30)

        assert result["status"] == "completed"
        assert "result" in result

    @pytest.mark.slow
    async def test_stream_task(
        self, llm_client: LLMClient, skip_if_llm_unavailable, available_model
    ):
        """Test streaming task response via polling.

        sop_llm uses async task queue, not SSE streaming.
        stream_task creates a task, then polls for completion.
        """
        if not available_model:
            pytest.skip("No LLM model available in sop_llm")

        chunks = []

        async for chunk in llm_client.stream_task(
            prompt="Count from 1 to 3, one number per line.",
            model=available_model,
            temperature=0,
            max_tokens=50,
            poll_interval=1.0,  # Poll every 1 second for faster test
            max_wait=60.0,
        ):
            chunks.append(chunk)

        # Should have at least 1 chunk
        assert len(chunks) >= 1

        # Check for thinking, content, or error chunks
        thinking_chunks = [c for c in chunks if c.get("type") == "thinking"]
        content_chunks = [c for c in chunks if c.get("choices")]
        error_chunks = [c for c in chunks if c.get("type") == "error"]

        # First chunk should be "thinking" with task_id
        if thinking_chunks:
            assert "task_id" in thinking_chunks[0]

        # Should have either content or error
        assert len(content_chunks) > 0 or len(error_chunks) > 0

        # If content, verify it contains text
        if content_chunks:
            content = content_chunks[0].get("choices", [{}])[0].get("delta", {}).get("content", "")
            assert len(content) > 0


# ==================== Embeddings API Tests ====================


@pytest.fixture
async def skip_if_embedding_unavailable(llm_client: LLMClient):
    """Skip test if embedding model is not available."""
    try:
        # Try to generate a test embedding
        embeddings = await llm_client.generate_embeddings(
            texts=["test"],
            model=TEST_EMBEDDING_MODEL,
        )
        if not embeddings:
            pytest.skip(f"Embedding model {TEST_EMBEDDING_MODEL} not available")
    except Exception as e:
        pytest.skip(f"Embedding model not available: {e}")


@pytest.mark.asyncio
@pytest.mark.integration
class TestLLMClientEmbeddings:
    """Tests for Embeddings API."""

    async def test_generate_embeddings_single(
        self, llm_client: LLMClient, skip_if_llm_unavailable, skip_if_embedding_unavailable
    ):
        """Test generating embedding for single text."""
        embeddings = await llm_client.generate_embeddings(
            texts=["Hello, world!"],
            model=TEST_EMBEDDING_MODEL,
        )

        assert len(embeddings) == 1
        assert isinstance(embeddings[0], list)
        assert len(embeddings[0]) > 0
        assert all(isinstance(x, float) for x in embeddings[0])

    async def test_generate_embeddings_batch(
        self, llm_client: LLMClient, skip_if_llm_unavailable, skip_if_embedding_unavailable
    ):
        """Test generating embeddings for multiple texts."""
        texts = [
            "First text for embedding",
            "Second text for embedding",
            "Third text for embedding",
        ]
        embeddings = await llm_client.generate_embeddings(
            texts=texts,
            model=TEST_EMBEDDING_MODEL,
        )

        assert len(embeddings) == 3
        # All embeddings should have same dimensions
        dims = [len(e) for e in embeddings]
        assert len(set(dims)) == 1

    async def test_generate_embeddings_empty(
        self, llm_client: LLMClient, skip_if_llm_unavailable
    ):
        """Test generating embeddings for empty list returns empty."""
        embeddings = await llm_client.generate_embeddings(texts=[])
        assert embeddings == []

    async def test_calculate_similarity(
        self, llm_client: LLMClient, skip_if_llm_unavailable, skip_if_embedding_unavailable
    ):
        """Test calculating similarity between texts."""
        similarity = await llm_client.calculate_similarity(
            text1="Machine learning is great",
            text2="ML is awesome",
            model=TEST_EMBEDDING_MODEL,
        )

        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0

    async def test_similarity_of_identical_texts(
        self, llm_client: LLMClient, skip_if_llm_unavailable, skip_if_embedding_unavailable
    ):
        """Test identical texts have high similarity."""
        text = "This is exactly the same text"
        similarity = await llm_client.calculate_similarity(
            text1=text,
            text2=text,
            model=TEST_EMBEDDING_MODEL,
        )

        # Identical texts should be very similar
        assert similarity > 0.95

    async def test_similarity_of_different_texts(
        self, llm_client: LLMClient, skip_if_llm_unavailable, skip_if_embedding_unavailable
    ):
        """Test very different texts have lower similarity."""
        similarity = await llm_client.calculate_similarity(
            text1="The quick brown fox jumps over the lazy dog",
            text2="Quantum mechanics describes nature at the atomic scale",
            model=TEST_EMBEDDING_MODEL,
        )

        # Different texts should have lower similarity
        assert similarity < 0.8


# ==================== Multi-turn Conversation Tests ====================


@pytest.mark.asyncio
@pytest.mark.integration
class TestLLMClientMultiTurn:
    """Tests for multi-turn conversation support."""

    @pytest.mark.slow
    async def test_conversation_with_context(
        self, llm_client: LLMClient, skip_if_llm_unavailable, available_model
    ):
        """Test multi-turn conversation maintains context."""
        if not available_model:
            pytest.skip("No LLM model available in sop_llm")

        # Create conversation
        create_result = await llm_client.create_conversation(
            system_prompt="You are a helpful assistant. Remember all details from our conversation.",
            model=available_model,
        )
        conv_id = create_result["conversation_id"]

        try:
            # First message
            task1 = await llm_client.create_task(
                prompt="My name is Alice. Please remember this.",
                conversation_id=conv_id,
                model=available_model,
                max_tokens=50,
                save_to_conversation=True,
            )
            await llm_client.wait_for_task(task1["task_id"])

            # Second message - should remember the name
            task2 = await llm_client.create_task(
                prompt="What is my name?",
                conversation_id=conv_id,
                model=available_model,
                max_tokens=50,
                save_to_conversation=True,
            )
            result = await llm_client.wait_for_task(task2["task_id"])

            # The response should contain "Alice"
            response_text = result.get("result", {}).get("text", "").lower()
            assert "alice" in response_text

        finally:
            # Cleanup
            await llm_client.delete_conversation(conv_id)


# ==================== Error Handling Tests ====================


@pytest.mark.asyncio
@pytest.mark.integration
class TestLLMClientErrors:
    """Tests for error handling."""

    async def test_connection_error_on_wrong_url(self):
        """Test connection error when URL is wrong."""
        client = LLMClient(base_url="http://localhost:9999")

        with pytest.raises(LLMConnectionError):
            await client.create_conversation()

    async def test_nonexistent_model(
        self, llm_client: LLMClient, skip_if_llm_unavailable
    ):
        """Test error when using nonexistent model."""
        with pytest.raises(LLMClientError):
            await llm_client.create_task(
                prompt="Test",
                model="nonexistent-model-xyz",
            )


# ==================== Singleton Tests ====================


class TestLLMClientSingleton:
    """Tests for LLM client singleton."""

    def test_get_llm_client_returns_same_instance(self):
        """Test get_llm_client returns the same instance."""
        client1 = get_llm_client()
        client2 = get_llm_client()

        assert client1 is client2

    def test_get_llm_client_is_configured(self):
        """Test get_llm_client is properly configured."""
        client = get_llm_client()

        assert client.base_url == settings.sop_llm.api_base_url
        assert client.timeout == settings.sop_llm.timeout
