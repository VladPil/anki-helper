"""Unit tests for CardGeneratorWorkflow and FactCheckerWorkflow.

Tests cover:
- CardGeneratorWorkflow: context fetching, card generation, duplicate checking,
  fact checking, routing, saving
- FactCheckerWorkflow: claim parsing, source search, claim verification,
  aggregation
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.llm.client import FactCheckResult, LLMResponse


# ==================== Mock LLM Client ====================


class MockLLMClient:
    """Mock LLM client for testing workflows."""

    def __init__(
        self,
        generate_response: str | None = None,
        fact_check_result: FactCheckResult | None = None,
    ):
        self.generate_response = generate_response or json.dumps([
            {"front": "What is Q1?", "back": "Answer 1", "tags": ["test"]},
            {"front": "What is Q2?", "back": "Answer 2", "tags": ["test"]},
        ])
        self.fact_check_result = fact_check_result or FactCheckResult(
            confidence=0.85,
            sources=["Wikipedia", "Encyclopedia"],
            reasoning="The claim is well-supported by reliable sources.",
        )
        self.generate_calls = []
        self.fact_check_calls = []

    async def generate(
        self,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        trace_id: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Mock generate method."""
        self.generate_calls.append({
            "model_id": model_id,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "trace_id": trace_id,
        })
        return LLMResponse(
            content=self.generate_response,
            model=model_id,
            input_tokens=100,
            output_tokens=200,
            finish_reason="stop",
        )

    async def fact_check(
        self,
        claim: str,
        context: str | None = None,
        trace_id: str | None = None,
    ) -> FactCheckResult:
        """Mock fact_check method."""
        self.fact_check_calls.append({
            "claim": claim,
            "context": context,
            "trace_id": trace_id,
        })
        return self.fact_check_result


# ==================== Fixtures ====================


@pytest.fixture
def mock_llm_client() -> MockLLMClient:
    """Create a mock LLM client."""
    return MockLLMClient()


@pytest.fixture
def low_confidence_llm_client() -> MockLLMClient:
    """Create a mock LLM client with low confidence fact check."""
    return MockLLMClient(
        fact_check_result=FactCheckResult(
            confidence=0.2,
            sources=[],
            reasoning="Unable to verify the claim.",
        )
    )


# ==================== CardGeneratorWorkflow Tests ====================


@pytest.mark.asyncio
class TestCardGeneratorWorkflowNodes:
    """Tests for individual CardGeneratorWorkflow nodes."""

    async def test_fetch_context_with_provided_context(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _fetch_context with user-provided context."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "topic": "Japanese particles",
            "context": "Focus on wa and ga particles",
            "trace_id": "test-trace-123",
        }

        result = await workflow._fetch_context(state)

        assert "retrieved_context" in result
        assert len(result["retrieved_context"]) == 1
        assert result["retrieved_context"][0]["content"] == "Focus on wa and ga particles"
        assert result["retrieved_context"][0]["source"] == "user_provided"
        assert result["progress"] == 20.0

    async def test_fetch_context_without_context(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _fetch_context without any context."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "topic": "Japanese particles",
            "context": None,
            "trace_id": "test-trace-123",
        }

        result = await workflow._fetch_context(state)

        assert "retrieved_context" in result
        assert len(result["retrieved_context"]) == 0
        assert len(result["context_sources"]) == 0

    async def test_generate_cards_success(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _generate with successful card generation."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()
        workflow._llm_client = mock_llm_client

        state = {
            "topic": "Japanese particles",
            "num_cards": 2,
            "card_type": "basic",
            "language": "en",
            "difficulty": "medium",
            "retrieved_context": [],
            "tags": ["test"],
            "trace_id": "test-trace-123",
            "model_id": "gpt-4",
        }

        result = await workflow._generate(state)

        assert "cards" in result
        assert len(result["cards"]) == 2
        assert result["cards"][0]["front"] == "What is Q1?"
        assert result["cards"][0]["back"] == "Answer 1"
        assert result["progress"] == 50.0

    async def test_generate_cards_with_context(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _generate includes context in prompt."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()
        workflow._llm_client = mock_llm_client

        state = {
            "topic": "Japanese particles",
            "num_cards": 2,
            "card_type": "basic",
            "language": "en",
            "difficulty": "medium",
            "retrieved_context": [
                {"content": "Important context about particles", "source": "test"},
            ],
            "tags": [],
            "trace_id": "test-trace-123",
            "model_id": "gpt-4",
        }

        await workflow._generate(state)

        # Verify context was included in the prompt
        assert len(mock_llm_client.generate_calls) == 1
        user_prompt = mock_llm_client.generate_calls[0]["user_prompt"]
        assert "Important context about particles" in user_prompt

    async def test_generate_cards_llm_error(
        self,
    ):
        """Test _generate handles LLM errors gracefully."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        # Create a mock that raises an exception
        error_client = MockLLMClient()
        async def raise_error(*args, **kwargs):
            raise Exception("LLM service unavailable")
        error_client.generate = raise_error
        workflow._llm_client = error_client

        state = {
            "topic": "Test topic",
            "num_cards": 2,
            "card_type": "basic",
            "language": "en",
            "difficulty": "medium",
            "retrieved_context": [],
            "tags": [],
            "trace_id": "test-trace-123",
            "model_id": "gpt-4",
        }

        result = await workflow._generate(state)

        assert result["cards"] == []
        assert "error" in result
        assert "LLM service unavailable" in result["error"]

    async def test_check_duplicates(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _check_duplicates marks cards as non-duplicate."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "cards": [
                {"front": "Q1", "back": "A1"},
                {"front": "Q2", "back": "A2"},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._check_duplicates(state)

        assert "duplicate_results" in result
        assert len(result["duplicate_results"]) == 2
        assert all(not r["is_duplicate"] for r in result["duplicate_results"])
        assert result["progress"] == 65.0

    async def test_fact_check_cards(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _fact_check verifies card content."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()
        workflow._llm_client = mock_llm_client

        state = {
            "cards": [
                {"front": "What is the capital of Japan?", "back": "Tokyo"},
            ],
            "context": None,
            "trace_id": "test-trace-123",
        }

        result = await workflow._fact_check(state)

        assert "fact_check_results" in result
        assert len(result["fact_check_results"]) == 1
        assert result["fact_check_results"][0]["confidence"] == 0.85
        assert result["progress"] == 80.0

    async def test_fact_check_handles_errors(
        self,
    ):
        """Test _fact_check handles individual card errors."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        # Create a mock that raises an exception
        error_client = MockLLMClient()
        async def raise_error(*args, **kwargs):
            raise Exception("Fact check service error")
        error_client.fact_check = raise_error
        workflow._llm_client = error_client

        state = {
            "cards": [
                {"front": "Q1", "back": "A1"},
            ],
            "context": None,
            "trace_id": "test-trace-123",
        }

        result = await workflow._fact_check(state)

        # Should handle error gracefully with default confidence
        assert len(result["fact_check_results"]) == 1
        assert result["fact_check_results"][0]["confidence"] == 0.5

    async def test_route_approves_good_cards(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _route approves cards with good scores."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "cards": [
                {"front": "Q1", "back": "A1"},
                {"front": "Q2", "back": "A2"},
            ],
            "duplicate_results": [
                {"card_index": 0, "is_duplicate": False, "similarity_score": 0.0},
                {"card_index": 1, "is_duplicate": False, "similarity_score": 0.0},
            ],
            "fact_check_results": [
                {"card_index": 0, "confidence": 0.9, "sources": []},
                {"card_index": 1, "confidence": 0.8, "sources": []},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._route(state)

        assert len(result["approved_cards"]) == 2
        assert len(result["rejected_cards"]) == 0
        assert result["progress"] == 90.0

    async def test_route_rejects_duplicates(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _route rejects duplicate cards."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "cards": [
                {"front": "Q1", "back": "A1"},
                {"front": "Q2", "back": "A2"},
            ],
            "duplicate_results": [
                {"card_index": 0, "is_duplicate": True, "similarity_score": 0.95},
                {"card_index": 1, "is_duplicate": False, "similarity_score": 0.0},
            ],
            "fact_check_results": [
                {"card_index": 0, "confidence": 0.9, "sources": []},
                {"card_index": 1, "confidence": 0.8, "sources": []},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._route(state)

        assert len(result["approved_cards"]) == 1
        assert len(result["rejected_cards"]) == 1
        assert result["rejected_cards"][0]["rejection_reason"] == "duplicate"

    async def test_route_rejects_low_confidence(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _route rejects cards with low confidence."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "cards": [
                {"front": "Q1", "back": "A1"},
                {"front": "Q2", "back": "A2"},
            ],
            "duplicate_results": [
                {"card_index": 0, "is_duplicate": False, "similarity_score": 0.0},
                {"card_index": 1, "is_duplicate": False, "similarity_score": 0.0},
            ],
            "fact_check_results": [
                {"card_index": 0, "confidence": 0.2, "sources": []},  # Low confidence
                {"card_index": 1, "confidence": 0.8, "sources": []},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._route(state)

        assert len(result["approved_cards"]) == 1
        assert len(result["rejected_cards"]) == 1
        assert result["rejected_cards"][0]["rejection_reason"] == "low_confidence"

    async def test_save_cards(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _save returns final cards."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "approved_cards": [
                {
                    "front": "Q1",
                    "back": "A1",
                    "tags": ["test"],
                    "confidence": 0.9,
                    "source": "Wikipedia",
                },
            ],
            "tags": ["default"],
            "trace_id": "test-trace-123",
        }

        result = await workflow._save(state)

        assert len(result["cards"]) == 1
        assert result["cards"][0]["front"] == "Q1"
        assert result["cards"][0]["confidence"] == 0.9
        assert result["progress"] == 100.0


@pytest.mark.asyncio
class TestCardGeneratorWorkflowConditionals:
    """Tests for CardGeneratorWorkflow conditional routing."""

    async def test_should_fact_check_enabled(self):
        """Test _should_fact_check returns 'fact_check' when enabled."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "fact_check": True,
            "cards": [{"front": "Q", "back": "A"}],
            "error": None,
        }

        result = workflow._should_fact_check(state)

        assert result == "fact_check"

    async def test_should_fact_check_disabled(self):
        """Test _should_fact_check returns 'skip' when disabled."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "fact_check": False,
            "cards": [{"front": "Q", "back": "A"}],
            "error": None,
        }

        result = workflow._should_fact_check(state)

        assert result == "skip"

    async def test_should_fact_check_skip_on_error(self):
        """Test _should_fact_check returns 'skip' when error exists."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "fact_check": True,
            "cards": [{"front": "Q", "back": "A"}],
            "error": "Some error occurred",
        }

        result = workflow._should_fact_check(state)

        assert result == "skip"

    async def test_should_fact_check_skip_no_cards(self):
        """Test _should_fact_check returns 'skip' when no cards."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "fact_check": True,
            "cards": [],
            "error": None,
        }

        result = workflow._should_fact_check(state)

        assert result == "skip"


@pytest.mark.asyncio
class TestCardGeneratorWorkflowPrompts:
    """Tests for CardGeneratorWorkflow prompt building."""

    async def test_build_system_prompt_basic(self):
        """Test _build_system_prompt for basic cards."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "card_type": "basic",
            "language": "en",
            "difficulty": "medium",
        }

        prompt = workflow._build_system_prompt(state)

        assert "basic" in prompt.lower() or "Basic" in prompt
        assert "en" in prompt
        assert "medium" in prompt.lower() or "Medium" in prompt

    async def test_build_system_prompt_cloze(self):
        """Test _build_system_prompt for cloze cards."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "card_type": "cloze",
            "language": "ja",
            "difficulty": "hard",
        }

        prompt = workflow._build_system_prompt(state)

        assert "cloze" in prompt.lower() or "{{c1::" in prompt

    async def test_build_user_prompt(self):
        """Test _build_user_prompt includes topic and count."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "topic": "Japanese particles wa and ga",
            "num_cards": 5,
            "tags": ["japanese", "grammar"],
            "retrieved_context": [],
        }

        prompt = workflow._build_user_prompt(state)

        assert "Japanese particles wa and ga" in prompt
        assert "5" in prompt
        assert "japanese" in prompt or "grammar" in prompt

    async def test_build_user_prompt_with_context(self):
        """Test _build_user_prompt includes retrieved context."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        state = {
            "topic": "Test topic",
            "num_cards": 3,
            "tags": [],
            "retrieved_context": [
                {"content": "Context about the topic", "source": "test"},
            ],
        }

        prompt = workflow._build_user_prompt(state)

        assert "Context about the topic" in prompt


@pytest.mark.asyncio
class TestCardGeneratorWorkflowParsing:
    """Tests for CardGeneratorWorkflow card parsing."""

    async def test_parse_cards_json_array(self):
        """Test _parse_cards with JSON array."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        content = '[{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]'
        state = {"tags": ["default"]}

        cards = workflow._parse_cards(content, state)

        assert len(cards) == 2
        assert cards[0]["front"] == "Q1"
        assert cards[1]["back"] == "A2"

    async def test_parse_cards_markdown_code_block(self):
        """Test _parse_cards with markdown code block."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        content = """Here are the flashcards:
```json
[{"front": "Question", "back": "Answer"}]
```
"""
        state = {"tags": []}

        cards = workflow._parse_cards(content, state)

        assert len(cards) == 1
        assert cards[0]["front"] == "Question"

    async def test_parse_cards_invalid_json(self):
        """Test _parse_cards with invalid JSON."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        content = "This is not valid JSON"
        state = {"tags": []}

        cards = workflow._parse_cards(content, state)

        assert len(cards) == 0

    async def test_parse_cards_filters_invalid(self):
        """Test _parse_cards filters cards without required fields."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        content = '[{"front": "Q1", "back": "A1"}, {"invalid": "card"}, {"front": "Q2"}]'
        state = {"tags": []}

        cards = workflow._parse_cards(content, state)

        assert len(cards) == 1
        assert cards[0]["front"] == "Q1"

    async def test_parse_cards_uses_default_tags(self):
        """Test _parse_cards uses default tags when card has none."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()

        content = '[{"front": "Q", "back": "A"}]'
        state = {"tags": ["default", "test"]}

        cards = workflow._parse_cards(content, state)

        assert cards[0]["tags"] == ["default", "test"]


# ==================== FactCheckerWorkflow Tests ====================


@pytest.mark.asyncio
class TestFactCheckerWorkflowNodes:
    """Tests for individual FactCheckerWorkflow nodes."""

    async def test_parse_claims_from_text(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _parse_claims extracts claims from text."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        mock_llm_client.generate_response = json.dumps([
            {"claim": "The capital of Japan is Tokyo", "type": "historical", "importance": "high"},
            {"claim": "Japan is an island country", "type": "definition", "importance": "medium"},
        ])

        workflow = FactCheckerWorkflow()
        workflow._llm_client = mock_llm_client

        state = {
            "content": "The capital of Japan is Tokyo. Japan is an island country.",
            "source_type": "text",
            "trace_id": "test-trace-123",
        }

        result = await workflow._parse_claims(state)

        assert "claims" in result
        assert len(result["claims"]) == 2
        assert result["claims"][0]["claim"] == "The capital of Japan is Tokyo"
        assert result["progress"] == 25.0

    async def test_parse_claims_empty_content(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _parse_claims handles empty content."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()
        workflow._llm_client = mock_llm_client

        state = {
            "content": "",
            "source_type": "text",
            "trace_id": "test-trace-123",
        }

        result = await workflow._parse_claims(state)

        assert result["claims"] == []

    async def test_parse_claims_card_source_type(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _parse_claims with card source type."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        mock_llm_client.generate_response = json.dumps([
            {"claim": "Test claim", "type": "definition", "importance": "high"},
        ])

        workflow = FactCheckerWorkflow()
        workflow._llm_client = mock_llm_client

        state = {
            "content": "Q: What is X? A: X is Y",
            "source_type": "card",
            "trace_id": "test-trace-123",
        }

        result = await workflow._parse_claims(state)

        # Verify card-specific prompt was used
        assert len(mock_llm_client.generate_calls) == 1
        system_prompt = mock_llm_client.generate_calls[0]["system_prompt"]
        assert "flashcard" in system_prompt.lower()

    async def test_search_sources_with_context(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _search_sources includes provided context."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [{"claim": "Test claim", "type": "test", "importance": "high"}],
            "context": "Relevant context for verification",
            "trace_id": "test-trace-123",
        }

        result = await workflow._search_sources(state)

        assert "sources" in result
        assert len(result["sources"]) == 1
        assert result["sources"][0]["type"] == "provided_context"
        assert result["progress"] == 50.0

    async def test_search_sources_without_context(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _search_sources without context."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [{"claim": "Test claim", "type": "test", "importance": "high"}],
            "context": None,
            "trace_id": "test-trace-123",
        }

        result = await workflow._search_sources(state)

        assert result["sources"] == []

    async def test_verify_claims_success(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _verify_claims verifies all claims."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()
        workflow._llm_client = mock_llm_client

        state = {
            "claims": [
                {"claim": "Claim 1", "type": "test", "importance": "high"},
                {"claim": "Claim 2", "type": "test", "importance": "medium"},
            ],
            "sources": [],
            "trace_id": "test-trace-123",
        }

        result = await workflow._verify_claims(state)

        assert "verification_results" in result
        assert len(result["verification_results"]) == 2
        assert result["verification_results"][0]["confidence"] == 0.85
        assert result["progress"] == 75.0

    async def test_verify_claims_handles_errors(
        self,
    ):
        """Test _verify_claims handles individual claim errors."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        # Create a mock that raises an exception
        error_client = MockLLMClient()
        async def raise_error(*args, **kwargs):
            raise Exception("Verification error")
        error_client.fact_check = raise_error
        workflow._llm_client = error_client

        state = {
            "claims": [{"claim": "Test claim", "type": "test", "importance": "high"}],
            "sources": [],
            "trace_id": "test-trace-123",
        }

        result = await workflow._verify_claims(state)

        assert len(result["verification_results"]) == 1
        assert result["verification_results"][0]["confidence"] == 0.5
        assert "Verification failed" in result["verification_results"][0]["reasoning"]

    async def test_aggregate_verified(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _aggregate with verified claims."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [
                {"claim": "Claim 1", "type": "test", "importance": "high"},
                {"claim": "Claim 2", "type": "test", "importance": "high"},
            ],
            "verification_results": [
                {"claim_index": 0, "confidence": 0.9, "verified": True},
                {"claim_index": 1, "confidence": 0.85, "verified": True},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._aggregate(state)

        assert result["verdict"] == "verified"
        assert result["overall_confidence"] >= 0.8
        assert "2/2 claims verified" in result["summary"]
        assert result["progress"] == 100.0

    async def test_aggregate_likely_accurate(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _aggregate with mostly verified claims."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [
                {"claim": "Claim 1", "type": "test", "importance": "medium"},
                {"claim": "Claim 2", "type": "test", "importance": "medium"},
            ],
            "verification_results": [
                {"claim_index": 0, "confidence": 0.75, "verified": True},
                {"claim_index": 1, "confidence": 0.65, "verified": False},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._aggregate(state)

        assert result["verdict"] == "likely_accurate"

    async def test_aggregate_uncertain(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _aggregate with mixed results."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [
                {"claim": "Claim 1", "type": "test", "importance": "medium"},
                {"claim": "Claim 2", "type": "test", "importance": "medium"},
            ],
            "verification_results": [
                {"claim_index": 0, "confidence": 0.5, "verified": False},
                {"claim_index": 1, "confidence": 0.5, "verified": False},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._aggregate(state)

        assert result["verdict"] == "uncertain"

    async def test_aggregate_likely_inaccurate(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _aggregate with mostly unverified claims."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [
                {"claim": "Claim 1", "type": "test", "importance": "medium"},
            ],
            "verification_results": [
                {"claim_index": 0, "confidence": 0.3, "verified": False},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._aggregate(state)

        assert result["verdict"] == "likely_inaccurate"

    async def test_aggregate_false(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _aggregate with false claims."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [
                {"claim": "Claim 1", "type": "test", "importance": "medium"},
            ],
            "verification_results": [
                {"claim_index": 0, "confidence": 0.1, "verified": False},
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._aggregate(state)

        assert result["verdict"] == "false"

    async def test_aggregate_no_results(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _aggregate with no verification results."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [],
            "verification_results": [],
            "trace_id": "test-trace-123",
        }

        result = await workflow._aggregate(state)

        assert result["verdict"] == "unverifiable"
        assert result["overall_confidence"] == 0.5

    async def test_aggregate_weighted_by_importance(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test _aggregate weights results by importance."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [
                {"claim": "High importance claim", "type": "test", "importance": "high"},
                {"claim": "Low importance claim", "type": "test", "importance": "low"},
            ],
            "verification_results": [
                {"claim_index": 0, "confidence": 0.9, "verified": True},  # High importance
                {"claim_index": 1, "confidence": 0.2, "verified": False},  # Low importance
            ],
            "trace_id": "test-trace-123",
        }

        result = await workflow._aggregate(state)

        # High importance should have more weight, so overall should be closer to 0.9
        assert result["overall_confidence"] > 0.55


@pytest.mark.asyncio
class TestFactCheckerWorkflowConditionals:
    """Tests for FactCheckerWorkflow conditional routing."""

    async def test_has_claims_continue(self):
        """Test _has_claims returns 'continue' when claims exist."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [{"claim": "Test", "type": "test", "importance": "high"}],
            "error": None,
        }

        result = workflow._has_claims(state)

        assert result == "continue"

    async def test_has_claims_skip_no_claims(self):
        """Test _has_claims returns 'skip' when no claims."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [],
            "error": None,
        }

        result = workflow._has_claims(state)

        assert result == "skip"

    async def test_has_claims_skip_on_error(self):
        """Test _has_claims returns 'skip' when error exists."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        state = {
            "claims": [{"claim": "Test", "type": "test", "importance": "high"}],
            "error": "Some error",
        }

        result = workflow._has_claims(state)

        assert result == "skip"


@pytest.mark.asyncio
class TestFactCheckerWorkflowParsing:
    """Tests for FactCheckerWorkflow JSON parsing."""

    async def test_parse_json_response_array(self):
        """Test _parse_json_response with JSON array."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        content = '[{"claim": "Test 1"}, {"claim": "Test 2"}]'

        result = workflow._parse_json_response(content)

        assert len(result) == 2
        assert result[0]["claim"] == "Test 1"

    async def test_parse_json_response_markdown(self):
        """Test _parse_json_response with markdown code block."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        content = """```json
[{"claim": "Test claim"}]
```"""

        result = workflow._parse_json_response(content)

        assert len(result) == 1
        assert result[0]["claim"] == "Test claim"

    async def test_parse_json_response_invalid(self):
        """Test _parse_json_response with invalid JSON."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        content = "This is not JSON"

        result = workflow._parse_json_response(content)

        assert result == []

    async def test_parse_json_response_single_object(self):
        """Test _parse_json_response with single object wrapped in array."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        workflow = FactCheckerWorkflow()

        # The method looks for array pattern, so single objects need to be in array
        content = '[{"claim": "Single claim"}]'

        result = workflow._parse_json_response(content)

        assert len(result) == 1
        assert result[0]["claim"] == "Single claim"


@pytest.mark.asyncio
class TestFactCheckerWorkflowCheck:
    """Tests for FactCheckerWorkflow.check convenience method."""

    async def test_check_method(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test the check convenience method."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        mock_llm_client.generate_response = json.dumps([
            {"claim": "Test claim", "type": "test", "importance": "high"},
        ])

        workflow = FactCheckerWorkflow()
        workflow._llm_client = mock_llm_client

        # Mock the run method to avoid full workflow execution
        async def mock_run(**kwargs):
            return {
                "overall_confidence": 0.85,
                "verdict": "verified",
                "summary": "Test summary",
                "claims": [{"claim": "Test"}],
                "verification_results": [{"confidence": 0.85}],
            }

        workflow.run = mock_run

        result = await workflow.check(
            content="Test content",
            context="Test context",
            source_type="text",
        )

        assert result["confidence"] == 0.85
        assert result["verdict"] == "verified"
        assert result["summary"] == "Test summary"


# ==================== Integration Tests ====================


@pytest.mark.asyncio
class TestWorkflowIntegration:
    """Integration-style tests for workflows."""

    async def test_card_generator_full_flow(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test CardGeneratorWorkflow full execution with mocked compiled graph."""
        from src.modules.generation.workflows.card_generator import CardGeneratorWorkflow

        workflow = CardGeneratorWorkflow()
        workflow._llm_client = mock_llm_client

        # Mock the _compiled attribute directly instead of the property
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke.return_value = {
            "cards": [
                {
                    "front": "Q1",
                    "back": "A1",
                    "tags": ["test"],
                    "confidence": 0.9,
                },
            ],
            "progress": 100.0,
            "trace_id": "test-trace",
        }
        workflow._compiled = mock_compiled

        result = await workflow.run(
            topic="Test topic",
            num_cards=2,
            card_type="basic",
            language="en",
            difficulty="medium",
            context=None,
            fact_check=True,
            include_sources=True,
            tags=["test"],
        )

        assert "cards" in result
        assert result["progress"] == 100.0
        mock_compiled.ainvoke.assert_called_once()

    async def test_fact_checker_full_flow(
        self,
        mock_llm_client: MockLLMClient,
    ):
        """Test FactCheckerWorkflow full execution with mocked compiled graph."""
        from src.modules.generation.workflows.fact_checker import FactCheckerWorkflow

        mock_llm_client.generate_response = json.dumps([
            {"claim": "Test claim", "type": "test", "importance": "high"},
        ])

        workflow = FactCheckerWorkflow()
        workflow._llm_client = mock_llm_client

        # Mock the _compiled attribute directly
        mock_compiled = AsyncMock()
        mock_compiled.ainvoke.return_value = {
            "overall_confidence": 0.85,
            "verdict": "verified",
            "summary": "1/1 claims verified. The content appears to be factually accurate.",
            "claims": [{"claim": "Test claim"}],
            "verification_results": [{"confidence": 0.85}],
            "progress": 100.0,
            "trace_id": "test-trace",
        }
        workflow._compiled = mock_compiled

        result = await workflow.run(
            content="Test content to verify",
            context=None,
            source_type="text",
        )

        assert "verdict" in result
        assert result["progress"] == 100.0
        mock_compiled.ainvoke.assert_called_once()
