"""Unit tests for LLM client (SopLLMClient).

Tests cover:
- SopLLMClient initialization and configuration
- Task creation and polling
- Text generation
- Structured output generation
- Fact checking
- Embedding generation
- Error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.exceptions import (
    LLMServiceError,
    PerplexityError,
    RateLimitError,
)
from src.services.llm.client import (
    EmbeddingResponse,
    FactCheckResult,
    LLMResponse,
    SopLLMClient,
    TaskStatus,
    close_llm_client,
    get_llm_client,
)

# ==================== SopLLMClient Tests ====================


class TestSopLLMClientInit:
    """Tests for SopLLMClient initialization."""

    def test_client_initialization(self):
        """Test client initializes with correct settings."""
        client = SopLLMClient()

        assert client.base_url is not None
        assert client.timeout > 0
        assert client.poll_interval > 0
        assert client._client is None

    def test_client_property_creates_client(self):
        """Test client property creates httpx client on access."""
        client = SopLLMClient()

        http_client = client.client

        assert http_client is not None
        assert isinstance(http_client, httpx.AsyncClient)


@pytest.mark.asyncio
class TestSopLLMClientContextManager:
    """Tests for async context manager."""

    async def test_aenter_returns_self(self):
        """Test __aenter__ returns the client instance."""
        client = SopLLMClient()

        async with client as ctx:
            assert ctx is client

    async def test_aexit_closes_client(self):
        """Test __aexit__ closes the HTTP client."""
        client = SopLLMClient()

        async with client:
            _ = client.client  # Create the client

        # Client should be closed
        assert client._client is None or client._client.is_closed


@pytest.mark.asyncio
class TestSopLLMClientCreateTask:
    """Tests for task creation."""

    async def test_create_task_success(self):
        """Test successful task creation."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"task_id": "test-task-123"}

        # Replace the client with a mock
        client._client = MagicMock()
        client._client.is_closed = False
        client._client.post = AsyncMock(return_value=mock_response)

        task_id = await client._create_task(
            model="gpt-4o",
            prompt="Test prompt",
            temperature=0.7,
            max_tokens=1000,
        )

        assert task_id == "test-task-123"

    async def test_create_task_rate_limit(self):
        """Test rate limit error handling."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(RateLimitError):
            await client._create_task(
                model="gpt-4o",
                prompt="Test prompt",
            )

    async def test_create_task_server_error(self):
        """Test server error handling."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMServiceError):
            await client._create_task(
                model="gpt-4o",
                prompt="Test prompt",
            )


@pytest.mark.asyncio
class TestSopLLMClientPollTask:
    """Tests for task polling."""

    async def test_poll_task_completed(self):
        """Test polling returns completed task."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": TaskStatus.COMPLETED.value,
            "result": {"text": "Generated text"},
        }

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.get = AsyncMock(return_value=mock_response)

        result = await client._poll_task("test-task-123")

        assert result["status"] == TaskStatus.COMPLETED.value

    async def test_poll_task_failed(self):
        """Test polling failed task raises error."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": TaskStatus.FAILED.value,
            "error": "Task failed",
        }

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMServiceError):
            await client._poll_task("test-task-123")


@pytest.mark.asyncio
class TestSopLLMClientGenerate:
    """Tests for text generation."""

    @patch("src.llm.client.LLM_LATENCY")
    @patch("src.llm.client.LLM_REQUEST_COUNT")
    @patch("src.llm.client.LLM_TOKEN_COUNT")
    async def test_generate_success(self, mock_tokens, mock_count, mock_latency):
        """Test successful text generation."""
        client = SopLLMClient()

        # Mock _create_task
        with patch.object(client, "_create_task", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = "task-123"

            # Mock _poll_task
            with patch.object(client, "_poll_task", new_callable=AsyncMock) as mock_poll:
                mock_poll.return_value = {
                    "status": TaskStatus.COMPLETED.value,
                    "result": {
                        "text": "Generated response",
                        "model": "gpt-4o",
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 50,
                        },
                        "finish_reason": "stop",
                    },
                }

                response = await client.generate(
                    model_id="gpt-4o",
                    system_prompt="You are helpful",
                    user_prompt="Hello",
                )

                assert isinstance(response, LLMResponse)
                assert response.content == "Generated response"
                assert response.input_tokens == 100
                assert response.output_tokens == 50

    @patch("src.llm.client.LLM_LATENCY")
    @patch("src.llm.client.LLM_REQUEST_COUNT")
    @patch("src.llm.client.LLM_TOKEN_COUNT")
    async def test_generate_timeout(self, mock_tokens, mock_count, mock_latency):
        """Test generation timeout handling."""
        client = SopLLMClient()

        with patch.object(client, "_create_task", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(LLMServiceError):
                await client.generate(
                    model_id="gpt-4o",
                    system_prompt="You are helpful",
                    user_prompt="Hello",
                )


@pytest.mark.asyncio
class TestSopLLMClientGenerateWithSchema:
    """Tests for structured output generation."""

    async def test_generate_with_schema_success(self):
        """Test successful structured output generation."""
        client = SopLLMClient()

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = LLMResponse(
                content='{"name": "test", "value": 42}',
                model="gpt-4o",
                input_tokens=100,
                output_tokens=50,
                finish_reason="stop",
            )

            json_schema = {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "number"},
                },
            }

            response = await client.generate_with_schema(
                model_id="gpt-4o",
                system_prompt="Generate structured data",
                user_prompt="Create an object",
                json_schema=json_schema,
            )

            assert response.content == '{"name": "test", "value": 42}'


@pytest.mark.asyncio
class TestSopLLMClientFactCheck:
    """Tests for fact checking."""

    async def test_fact_check_success(self):
        """Test successful fact checking."""
        client = SopLLMClient()

        with patch.object(client, "generate_with_schema", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(
                content='{"confidence": 0.9, "sources": ["Wikipedia"], "reasoning": "Well established fact"}',
                model="llama-sonar",
                input_tokens=100,
                output_tokens=50,
                finish_reason="stop",
            )

            result = await client.fact_check("The sky is blue")

            assert isinstance(result, FactCheckResult)
            assert result.confidence == 0.9
            assert "Wikipedia" in result.sources

    async def test_fact_check_invalid_json(self):
        """Test fact check with invalid JSON response."""
        client = SopLLMClient()

        with patch.object(client, "generate_with_schema", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = LLMResponse(
                content="Not valid JSON",
                model="llama-sonar",
                input_tokens=100,
                output_tokens=50,
                finish_reason="stop",
            )

            result = await client.fact_check("Some claim")

            # Should return default values
            assert result.confidence == 0.5
            assert result.sources == []

    async def test_fact_check_error(self):
        """Test fact check error handling."""
        client = SopLLMClient()

        with patch.object(client, "generate_with_schema", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = LLMServiceError("LLM error")

            with pytest.raises(PerplexityError):
                await client.fact_check("Some claim")


@pytest.mark.asyncio
class TestSopLLMClientEmbeddings:
    """Tests for embedding generation."""

    async def test_generate_embeddings_success(self):
        """Test successful embedding generation."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        }

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.post = AsyncMock(return_value=mock_response)

        embeddings = await client.generate_embeddings(
            texts=["Hello", "World"],
        )

        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]

    async def test_generate_embeddings_error(self):
        """Test embedding generation error handling."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMServiceError):
            await client.generate_embeddings(texts=["Hello"])


@pytest.mark.asyncio
class TestSopLLMClientSimilarity:
    """Tests for similarity calculation."""

    async def test_calculate_similarity_success(self):
        """Test successful similarity calculation."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"similarity": 0.85}

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.post = AsyncMock(return_value=mock_response)

        similarity = await client.calculate_similarity("Hello", "Hi there")

        assert similarity == 0.85

    async def test_calculate_similarity_error(self):
        """Test similarity calculation error handling."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(LLMServiceError):
            await client.calculate_similarity("Hello", "Hi")


@pytest.mark.asyncio
class TestSopLLMClientHealth:
    """Tests for health check."""

    async def test_health_check_healthy(self):
        """Test healthy service check."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 200

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.get = AsyncMock(return_value=mock_response)

        is_healthy = await client.health_check()

        assert is_healthy is True

    async def test_health_check_unhealthy(self):
        """Test unhealthy service check."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 503

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.get = AsyncMock(return_value=mock_response)

        is_healthy = await client.health_check()

        assert is_healthy is False

    async def test_health_check_exception(self):
        """Test health check with exception."""
        client = SopLLMClient()

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.get = AsyncMock(side_effect=Exception("Connection error"))

        is_healthy = await client.health_check()

        assert is_healthy is False


@pytest.mark.asyncio
class TestSopLLMClientListModels:
    """Tests for listing models."""

    async def test_list_models_success(self):
        """Test successful model listing."""
        client = SopLLMClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "gpt-4o", "type": "chat"},
                {"name": "llama-3", "type": "chat"},
            ]
        }

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.get = AsyncMock(return_value=mock_response)

        models = await client.list_models()

        assert len(models) == 2
        assert models[0]["name"] == "gpt-4o"

    async def test_list_models_error(self):
        """Test model listing with error."""
        client = SopLLMClient()

        client._client = MagicMock()
        client._client.is_closed = False
        client._client.get = AsyncMock(side_effect=Exception("Error"))

        models = await client.list_models()

        assert models == []


@pytest.mark.asyncio
class TestSopLLMClientClose:
    """Tests for client cleanup."""

    async def test_close_client(self):
        """Test closing the HTTP client."""
        client = SopLLMClient()
        _ = client.client  # Create the client

        await client.close()

        assert client._client is None


class TestGetLLMClient:
    """Tests for get_llm_client singleton."""

    def test_get_llm_client_returns_client(self):
        """Test get_llm_client returns a client."""
        # Reset singleton for clean test
        import src.llm.client
        src.llm.client._llm_client = None

        client = get_llm_client()

        assert isinstance(client, SopLLMClient)

    def test_get_llm_client_singleton(self):
        """Test get_llm_client returns same instance."""
        client1 = get_llm_client()
        client2 = get_llm_client()

        assert client1 is client2


@pytest.mark.asyncio
class TestCloseLLMClient:
    """Tests for close_llm_client."""

    async def test_close_llm_client(self):
        """Test closing the singleton client."""
        # Get the client first
        _ = get_llm_client()

        await close_llm_client()

        # After closing, the singleton should be None
        import src.llm.client
        assert src.llm.client._llm_client is None


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.QUEUED.value == "queued"
        assert TaskStatus.PROCESSING.value == "processing"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_llm_response_creation(self):
        """Test creating LLMResponse."""
        response = LLMResponse(
            content="Test content",
            model="gpt-4o",
            input_tokens=100,
            output_tokens=50,
            finish_reason="stop",
        )

        assert response.content == "Test content"
        assert response.model == "gpt-4o"
        assert response.input_tokens == 100


class TestFactCheckResult:
    """Tests for FactCheckResult model."""

    def test_fact_check_result_creation(self):
        """Test creating FactCheckResult."""
        result = FactCheckResult(
            confidence=0.9,
            sources=["Source 1", "Source 2"],
            reasoning="This is well-established",
        )

        assert result.confidence == 0.9
        assert len(result.sources) == 2


class TestEmbeddingResponse:
    """Tests for EmbeddingResponse model."""

    def test_embedding_response_creation(self):
        """Test creating EmbeddingResponse."""
        response = EmbeddingResponse(
            embeddings=[[0.1, 0.2, 0.3]],
            model="text-embedding-3",
            dimensions=1024,
        )

        assert len(response.embeddings) == 1
        assert response.dimensions == 1024
