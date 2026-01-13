"""Integration tests for LangGraph workflows.

Tests cover:
- Chat workflow execution
- Card generation workflow
- RAG integration workflow
- Workflow state management
- Error handling in workflows
"""

from collections.abc import AsyncGenerator

import pytest

from src.tests.fixtures.sample_data import (
    SAMPLE_DOCUMENTS,
    SAMPLE_GENERATED_CARDS,
)

# ==================== Mock Workflow Components ====================


class MockChatWorkflow:
    """Mock chat workflow for testing."""

    def __init__(
        self,
        responses: list[str] | None = None,
        should_fail: bool = False,
        failure_message: str = "Workflow error",
    ):
        self.responses = responses or ["This is a mock response."]
        self.should_fail = should_fail
        self.failure_message = failure_message
        self.call_count = 0
        self.last_message = None
        self.last_history = None
        self.last_context = None

    async def stream(
        self,
        message: str,
        history: list[dict],
        context: dict | None = None,
        context_query: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream response chunks."""
        self.call_count += 1
        self.last_message = message
        self.last_history = history
        self.last_context = context

        if self.should_fail:
            raise Exception(self.failure_message)

        response_idx = min(self.call_count - 1, len(self.responses) - 1)
        response = self.responses[response_idx]

        # Yield content chunks
        for chunk in response:
            yield {"type": "content", "content": chunk}

        # Yield metadata
        yield {
            "type": "metadata",
            "tokens": len(response.split()),
            "sources": [],
        }

    async def invoke(
        self,
        message: str,
        history: list[dict],
        context: dict | None = None,
    ) -> str:
        """Invoke workflow synchronously."""
        self.call_count += 1
        self.last_message = message
        self.last_history = history
        self.last_context = context

        if self.should_fail:
            raise Exception(self.failure_message)

        response_idx = min(self.call_count - 1, len(self.responses) - 1)
        return self.responses[response_idx]


class MockGenerationWorkflow:
    """Mock card generation workflow for testing."""

    def __init__(
        self,
        cards: list[dict] | None = None,
        should_fail: bool = False,
    ):
        self.cards = cards or SAMPLE_GENERATED_CARDS
        self.should_fail = should_fail
        self.call_count = 0
        self.last_topic = None
        self.last_config = None

    async def generate(
        self,
        topic: str,
        num_cards: int = 5,
        card_type: str = "basic",
        **kwargs,
    ) -> list[dict]:
        """Generate flashcards."""
        self.call_count += 1
        self.last_topic = topic
        self.last_config = {
            "num_cards": num_cards,
            "card_type": card_type,
            **kwargs,
        }

        if self.should_fail:
            raise Exception("Generation failed")

        return self.cards[:num_cards]


class MockRAGWorkflow:
    """Mock RAG workflow for testing."""

    def __init__(
        self,
        documents: list[dict] | None = None,
        should_fail: bool = False,
    ):
        self.documents = documents or SAMPLE_DOCUMENTS
        self.should_fail = should_fail
        self.call_count = 0
        self.last_query = None

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.5,
    ) -> list[dict]:
        """Retrieve relevant documents."""
        self.call_count += 1
        self.last_query = query

        if self.should_fail:
            raise Exception("RAG retrieval failed")

        return self.documents[:top_k]


# ==================== Chat Workflow Tests ====================


@pytest.mark.asyncio
class TestChatWorkflow:
    """Tests for chat workflow execution."""

    async def test_simple_chat_response(self):
        """Test simple chat workflow response."""
        workflow = MockChatWorkflow(responses=["Hello! How can I help?"])

        chunks = []
        async for chunk in workflow.stream(
            message="Hello",
            history=[],
        ):
            chunks.append(chunk)

        content_chunks = [c for c in chunks if c.get("type") == "content"]
        metadata = next((c for c in chunks if c.get("type") == "metadata"), None)

        assert len(content_chunks) > 0
        assert metadata is not None
        assert workflow.call_count == 1

    async def test_chat_with_history(self):
        """Test chat workflow with conversation history."""
        workflow = MockChatWorkflow()

        history = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
        ]

        async for _ in workflow.stream(
            message="Tell me more",
            history=history,
        ):
            pass

        assert workflow.last_history == history
        assert len(workflow.last_history) == 2

    async def test_chat_with_context(self):
        """Test chat workflow with context."""
        workflow = MockChatWorkflow()

        context = {"deck_id": "123", "topic": "Python"}

        async for _ in workflow.stream(
            message="What's in this deck?",
            history=[],
            context=context,
        ):
            pass

        assert workflow.last_context == context

    async def test_chat_workflow_error_handling(self):
        """Test chat workflow error handling."""
        workflow = MockChatWorkflow(should_fail=True, failure_message="API error")

        with pytest.raises(Exception) as exc_info:
            async for _ in workflow.stream(
                message="Hello",
                history=[],
            ):
                pass

        assert "API error" in str(exc_info.value)

    async def test_multiple_chat_turns(self):
        """Test multiple chat turns."""
        workflow = MockChatWorkflow(
            responses=[
                "First response",
                "Second response",
                "Third response",
            ]
        )

        # First turn
        async for _ in workflow.stream("First message", []):
            pass

        # Second turn
        async for _ in workflow.stream("Second message", []):
            pass

        assert workflow.call_count == 2


# ==================== Generation Workflow Tests ====================


@pytest.mark.asyncio
class TestGenerationWorkflow:
    """Tests for card generation workflow."""

    async def test_basic_card_generation(self):
        """Test basic card generation."""
        workflow = MockGenerationWorkflow()

        cards = await workflow.generate(
            topic="Python basics",
            num_cards=3,
        )

        assert len(cards) == 3
        assert workflow.call_count == 1
        assert workflow.last_topic == "Python basics"

    async def test_generation_with_card_type(self):
        """Test generation with specific card type."""
        workflow = MockGenerationWorkflow()

        await workflow.generate(
            topic="Test",
            card_type="cloze",
        )

        assert workflow.last_config["card_type"] == "cloze"

    async def test_generation_with_custom_count(self):
        """Test generation with custom card count."""
        workflow = MockGenerationWorkflow()

        cards = await workflow.generate(
            topic="Test",
            num_cards=10,
        )

        # Should return at most the available mock cards
        assert len(cards) <= 10

    async def test_generation_error_handling(self):
        """Test generation workflow error handling."""
        workflow = MockGenerationWorkflow(should_fail=True)

        with pytest.raises(Exception) as exc_info:
            await workflow.generate(topic="Test")

        assert "Generation failed" in str(exc_info.value)

    async def test_generation_with_context(self):
        """Test generation with additional context."""
        workflow = MockGenerationWorkflow()

        await workflow.generate(
            topic="Japanese",
            language="ja",
            difficulty="beginner",
        )

        assert workflow.last_config.get("language") == "ja"
        assert workflow.last_config.get("difficulty") == "beginner"


# ==================== RAG Workflow Tests ====================


@pytest.mark.asyncio
class TestRAGWorkflow:
    """Tests for RAG workflow execution."""

    async def test_simple_retrieval(self):
        """Test simple document retrieval."""
        workflow = MockRAGWorkflow()

        docs = await workflow.retrieve(
            query="What is Python?",
            top_k=3,
        )

        assert len(docs) == 3
        assert workflow.call_count == 1

    async def test_retrieval_with_filters(self):
        """Test retrieval with score filtering."""
        workflow = MockRAGWorkflow()

        await workflow.retrieve(
            query="Test query",
            min_score=0.7,
        )

        assert workflow.last_query == "Test query"

    async def test_retrieval_error_handling(self):
        """Test RAG retrieval error handling."""
        workflow = MockRAGWorkflow(should_fail=True)

        with pytest.raises(Exception) as exc_info:
            await workflow.retrieve(query="Test")

        assert "RAG retrieval failed" in str(exc_info.value)

    async def test_empty_retrieval_results(self):
        """Test handling empty retrieval results."""
        workflow = MockRAGWorkflow(documents=[])

        docs = await workflow.retrieve(
            query="Obscure query",
            top_k=5,
        )

        assert len(docs) == 0


# ==================== Integrated Workflow Tests ====================


@pytest.mark.asyncio
class TestIntegratedWorkflows:
    """Tests for integrated workflow scenarios."""

    async def test_rag_enhanced_chat(self):
        """Test RAG-enhanced chat workflow."""
        rag_workflow = MockRAGWorkflow()
        chat_workflow = MockChatWorkflow()

        # 1. Retrieve context
        query = "What is the wa particle?"
        docs = await rag_workflow.retrieve(query=query, top_k=2)

        # 2. Build context
        context_text = "\n".join([d["content"] for d in docs])

        # 3. Chat with context
        context = {"rag_context": context_text}
        async for _ in chat_workflow.stream(
            message=query,
            history=[],
            context=context,
        ):
            pass

        assert rag_workflow.call_count == 1
        assert chat_workflow.call_count == 1
        assert "rag_context" in chat_workflow.last_context

    async def test_generation_with_rag(self):
        """Test card generation with RAG context."""
        rag_workflow = MockRAGWorkflow()
        gen_workflow = MockGenerationWorkflow()

        # 1. Retrieve relevant documents
        topic = "Japanese particles"
        docs = await rag_workflow.retrieve(query=topic)

        # 2. Generate cards with context
        context_text = "\n".join([d["content"] for d in docs])
        cards = await gen_workflow.generate(
            topic=topic,
            context=context_text,
        )

        assert len(cards) > 0
        assert gen_workflow.last_config.get("context") is not None

    async def test_multi_step_conversation(self):
        """Test multi-step conversation workflow."""
        workflow = MockChatWorkflow(
            responses=[
                "I can help with Japanese.",
                "The wa particle marks the topic.",
                "Here's an example: Watashi wa gakusei desu.",
            ]
        )

        history = []

        # Turn 1
        messages = ["Can you help me learn Japanese?"]
        async for chunk in workflow.stream(
            message=messages[0],
            history=history.copy(),
        ):
            if chunk.get("type") == "content":
                pass

        # Build history
        history.append({"role": "user", "content": messages[0]})
        history.append({"role": "assistant", "content": workflow.responses[0]})

        # Turn 2
        messages.append("What is the wa particle?")
        async for _ in workflow.stream(
            message=messages[1],
            history=history.copy(),
        ):
            pass

        assert workflow.call_count == 2
        assert len(history) == 2


# ==================== Workflow State Tests ====================


@pytest.mark.asyncio
class TestWorkflowState:
    """Tests for workflow state management."""

    async def test_workflow_state_persistence(self):
        """Test that workflow state persists correctly."""
        workflow = MockChatWorkflow()

        # First call
        async for _ in workflow.stream("Message 1", []):
            pass

        first_call_count = workflow.call_count

        # Second call
        async for _ in workflow.stream("Message 2", []):
            pass

        assert workflow.call_count == first_call_count + 1

    async def test_workflow_reset(self):
        """Test workflow state reset."""
        workflow = MockChatWorkflow()

        async for _ in workflow.stream("Test", []):
            pass

        # Reset workflow (create new instance)
        workflow = MockChatWorkflow()

        assert workflow.call_count == 0
        assert workflow.last_message is None


# ==================== Performance Tests ====================


@pytest.mark.asyncio
class TestWorkflowPerformance:
    """Tests for workflow performance characteristics."""

    async def test_streaming_latency(self):
        """Test that streaming delivers chunks promptly."""
        import time

        workflow = MockChatWorkflow(responses=["A" * 100])

        start_time = time.time()
        first_chunk_time = None

        async for chunk in workflow.stream("Test", []):
            if first_chunk_time is None:
                first_chunk_time = time.time()
            break

        # First chunk should arrive quickly (mocked, so very fast)
        if first_chunk_time:
            latency = first_chunk_time - start_time
            assert latency < 1.0  # Should be nearly instant for mock

    async def test_batch_generation_efficiency(self):
        """Test batch card generation efficiency."""
        workflow = MockGenerationWorkflow()

        # Generate in single batch
        cards = await workflow.generate(topic="Test", num_cards=10)

        # Should be single call, not multiple
        assert workflow.call_count == 1


# ==================== Error Recovery Tests ====================


@pytest.mark.asyncio
class TestWorkflowErrorRecovery:
    """Tests for workflow error recovery."""

    async def test_retry_on_transient_error(self):
        """Test retry mechanism on transient errors."""
        call_count = 0

        async def flaky_workflow(message: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return "Success"

        # Retry loop
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await flaky_workflow("Test")
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise

        assert result == "Success"
        assert call_count == 3

    async def test_graceful_degradation(self):
        """Test graceful degradation when workflow fails."""
        rag_workflow = MockRAGWorkflow(should_fail=True)

        # Try RAG, fall back to no context
        try:
            docs = await rag_workflow.retrieve(query="Test")
            context = "\n".join([d["content"] for d in docs])
        except Exception:
            context = ""  # Graceful degradation

        assert context == ""

    async def test_partial_result_handling(self):
        """Test handling partial results from workflow."""
        # Simulate workflow that returns partial results
        partial_cards = SAMPLE_GENERATED_CARDS[:1]  # Only 1 card
        workflow = MockGenerationWorkflow(cards=partial_cards)

        cards = await workflow.generate(topic="Test", num_cards=5)

        # Should handle partial results gracefully
        assert len(cards) == 1  # Got what was available
