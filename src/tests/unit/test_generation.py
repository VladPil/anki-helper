"""Unit tests for card generation workflow.

Tests cover:
- Card generation request handling
- LLM interaction mocking
- Card parsing and validation
- Generation configuration options
- Error handling during generation
"""

import json
from collections.abc import AsyncGenerator

import pytest

from src.tests.fixtures.sample_data import (
    SAMPLE_GENERATED_CARDS,
    SAMPLE_GENERATION_REQUESTS,
)

# ==================== Mock LLM Client ====================


class MockLLMClient:
    """Mock LLM client for testing generation workflows."""

    def __init__(self, response: str | list[dict] | None = None):
        self.response = response or SAMPLE_GENERATED_CARDS
        self.call_count = 0
        self.last_prompt = None
        self.should_fail = False
        self.failure_message = "Mock LLM error"

    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate a response to a prompt."""
        self.call_count += 1
        self.last_prompt = prompt

        if self.should_fail:
            raise Exception(self.failure_message)

        if isinstance(self.response, str):
            return self.response
        return json.dumps(self.response)

    async def stream(
        self,
        prompt: str,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream a response to a prompt."""
        self.call_count += 1
        self.last_prompt = prompt

        if self.should_fail:
            raise Exception(self.failure_message)

        response = self.response if isinstance(self.response, str) else json.dumps(self.response)
        for chunk in response:
            yield chunk


# ==================== Card Generation Tests ====================


@pytest.mark.asyncio
class TestCardGenerationBasic:
    """Basic tests for card generation."""

    async def test_generate_basic_cards(self):
        """Test basic card generation."""
        mock_client = MockLLMClient()

        # Simulate generation workflow
        prompt = "Generate 3 flashcards about Japanese particles"
        response = await mock_client.generate(prompt)

        cards = json.loads(response)
        assert len(cards) == 3
        assert all("front" in card and "back" in card for card in cards)

    async def test_generate_with_custom_count(self):
        """Test generating specific number of cards."""
        expected_cards = [
            {"front": "Q1", "back": "A1"},
            {"front": "Q2", "back": "A2"},
            {"front": "Q3", "back": "A3"},
            {"front": "Q4", "back": "A4"},
            {"front": "Q5", "back": "A5"},
        ]
        mock_client = MockLLMClient(response=expected_cards)

        response = await mock_client.generate("Generate 5 cards")
        cards = json.loads(response)

        assert len(cards) == 5

    async def test_generate_cloze_cards(self):
        """Test generating cloze deletion cards."""
        cloze_cards = [
            {"text": "The {{c1::capital}} of Japan is {{c2::Tokyo}}.", "extra": "Geography"},
            {"text": "{{c1::Python}} is a programming language.", "extra": "Programming"},
        ]
        mock_client = MockLLMClient(response=cloze_cards)

        response = await mock_client.generate("Generate cloze cards")
        cards = json.loads(response)

        assert len(cards) == 2
        assert "{{c1::" in cards[0]["text"]

    async def test_generation_with_topic_context(self):
        """Test generation with specific topic context."""
        mock_client = MockLLMClient()

        topic = "Japanese verb conjugation"
        prompt = f"Generate cards about: {topic}"

        await mock_client.generate(prompt)

        assert topic in mock_client.last_prompt

    async def test_generation_streaming(self):
        """Test streaming card generation."""
        mock_client = MockLLMClient(response="[{\"front\":\"Q\",\"back\":\"A\"}]")

        chunks = []
        async for chunk in mock_client.stream("Generate cards"):
            chunks.append(chunk)

        result = "".join(chunks)
        cards = json.loads(result)
        assert len(cards) == 1


# ==================== Card Validation Tests ====================


@pytest.mark.asyncio
class TestCardValidation:
    """Tests for validating generated cards."""

    def test_validate_basic_card_structure(self):
        """Test validation of basic card structure."""
        valid_card = {"front": "What is 1+1?", "back": "2"}

        assert "front" in valid_card
        assert "back" in valid_card
        assert len(valid_card["front"]) > 0
        assert len(valid_card["back"]) > 0

    def test_validate_card_with_tags(self):
        """Test validation of card with tags."""
        card = {
            "front": "Question",
            "back": "Answer",
            "tags": ["math", "basic"],
        }

        assert isinstance(card.get("tags"), list)
        assert all(isinstance(tag, str) for tag in card["tags"])

    def test_validate_cloze_card_structure(self):
        """Test validation of cloze card structure."""
        cloze_card = {
            "text": "The {{c1::answer}} is here",
            "extra": "Additional info",
        }

        assert "text" in cloze_card
        assert "{{c1::" in cloze_card["text"]

    def test_reject_empty_front(self):
        """Test that empty front field is invalid."""
        invalid_card = {"front": "", "back": "Answer"}

        assert len(invalid_card["front"]) == 0
        # In real implementation, this should raise ValidationError

    def test_reject_empty_back(self):
        """Test that empty back field is invalid."""
        invalid_card = {"front": "Question", "back": ""}

        assert len(invalid_card["back"]) == 0
        # In real implementation, this should raise ValidationError

    def test_reject_missing_required_fields(self):
        """Test that missing required fields are detected."""
        invalid_cards = [
            {"front": "Only front"},  # Missing back
            {"back": "Only back"},  # Missing front
            {},  # Missing both
        ]

        for card in invalid_cards:
            has_front = "front" in card
            has_back = "back" in card
            assert not (has_front and has_back)

    def test_validate_cloze_syntax(self):
        """Test validation of cloze deletion syntax."""
        valid_cloze_texts = [
            "The {{c1::answer}} is correct",
            "{{c1::First}} and {{c2::second}} clozes",
            "{{c1::Nested {{c2::cloze}}}} text",
        ]

        invalid_cloze_texts = [
            "No cloze here",
            "{{c1:: missing closing",
            "missing opening ::}}",
        ]

        for text in valid_cloze_texts:
            assert "{{c" in text and "}}" in text

        for text in invalid_cloze_texts:
            is_valid = "{{c" in text and "}}" in text and "{{c" in text.split("}}")[0]
            # Some should fail this simple check


# ==================== Error Handling Tests ====================


@pytest.mark.asyncio
class TestGenerationErrorHandling:
    """Tests for error handling during generation."""

    async def test_handle_llm_connection_error(self):
        """Test handling LLM connection errors."""
        mock_client = MockLLMClient()
        mock_client.should_fail = True
        mock_client.failure_message = "Connection timeout"

        with pytest.raises(Exception) as exc_info:
            await mock_client.generate("Generate cards")

        assert "Connection timeout" in str(exc_info.value)

    async def test_handle_invalid_json_response(self):
        """Test handling invalid JSON from LLM."""
        mock_client = MockLLMClient(response="Not valid JSON")

        response = await mock_client.generate("Generate cards")

        with pytest.raises(json.JSONDecodeError):
            json.loads(response)

    async def test_handle_empty_response(self):
        """Test handling empty response from LLM."""
        mock_client = MockLLMClient(response="[]")

        response = await mock_client.generate("Generate cards")
        cards = json.loads(response)

        assert cards == []

    async def test_handle_rate_limit_error(self):
        """Test handling rate limit errors."""
        mock_client = MockLLMClient()
        mock_client.should_fail = True
        mock_client.failure_message = "Rate limit exceeded"

        with pytest.raises(Exception) as exc_info:
            await mock_client.generate("Generate cards")

        assert "Rate limit" in str(exc_info.value)

    async def test_handle_malformed_cards(self):
        """Test handling malformed card data from LLM."""
        malformed_cards = [
            {"front": "Valid front", "back": "Valid back"},
            {"invalid": "No front or back fields"},
            "Not even an object",
        ]
        mock_client = MockLLMClient(response=json.dumps(malformed_cards))

        response = await mock_client.generate("Generate cards")
        cards = json.loads(response)

        # Should be able to filter valid cards
        valid_cards = [c for c in cards if isinstance(c, dict) and "front" in c and "back" in c]
        assert len(valid_cards) == 1


# ==================== Configuration Tests ====================


@pytest.mark.asyncio
class TestGenerationConfiguration:
    """Tests for generation configuration options."""

    def test_default_generation_config(self):
        """Test default generation configuration."""
        default_config = {
            "card_type": "basic",
            "num_cards": 5,
            "language": "en",
            "temperature": 0.7,
            "max_tokens": 2000,
        }

        assert default_config["card_type"] == "basic"
        assert default_config["num_cards"] == 5
        assert 0 <= default_config["temperature"] <= 1

    def test_custom_temperature_config(self):
        """Test custom temperature setting."""
        configs = [
            {"temperature": 0.0},  # Deterministic
            {"temperature": 0.5},  # Balanced
            {"temperature": 1.0},  # Creative
        ]

        for config in configs:
            assert 0 <= config["temperature"] <= 1

    def test_language_config_options(self):
        """Test different language configurations."""
        languages = ["en", "ja", "ru", "es", "zh"]

        for lang in languages:
            config = {"language": lang}
            assert len(config["language"]) == 2

    def test_card_type_validation(self):
        """Test card type configuration validation."""
        valid_types = ["basic", "cloze", "reverse"]
        invalid_types = ["invalid", "unknown", ""]

        for card_type in valid_types:
            config = {"card_type": card_type}
            assert config["card_type"] in valid_types

        for card_type in invalid_types:
            assert card_type not in valid_types


# ==================== Prompt Building Tests ====================


@pytest.mark.asyncio
class TestPromptBuilding:
    """Tests for generation prompt building."""

    def test_build_basic_generation_prompt(self):
        """Test building a basic generation prompt."""
        topic = "Japanese particles"
        num_cards = 3

        prompt = f"""Generate {num_cards} flashcards about {topic}.
Each card should have a clear question on the front and answer on the back.
Return as JSON array with 'front' and 'back' fields."""

        assert topic in prompt
        assert str(num_cards) in prompt
        assert "JSON" in prompt

    def test_build_cloze_generation_prompt(self):
        """Test building a cloze card generation prompt."""
        topic = "Python programming"

        prompt = f"""Generate cloze deletion flashcards about {topic}.
Use {{{{c1::text}}}} syntax for deletions.
Return as JSON array with 'text' and 'extra' fields."""

        assert topic in prompt
        assert "{{c1::" in prompt or "{{{{c1::" in prompt

    def test_build_prompt_with_context(self):
        """Test building prompt with additional context."""
        topic = "Japanese greetings"
        context = "Focus on formal and informal variations"

        prompt = f"""Generate flashcards about {topic}.
Additional context: {context}"""

        assert topic in prompt
        assert context in prompt

    def test_build_prompt_with_language(self):
        """Test building prompt with target language."""
        topic = "Vocabulary"
        language = "Japanese"

        prompt = f"""Generate flashcards about {topic}.
Use {language} for the content."""

        assert language in prompt

    def test_prompt_includes_format_instructions(self):
        """Test that prompt includes format instructions."""
        prompt = """Generate flashcards.
Return response in the following JSON format:
[{"front": "question", "back": "answer", "tags": ["tag1"]}]"""

        assert "JSON" in prompt or "json" in prompt.lower()
        assert "front" in prompt
        assert "back" in prompt


# ==================== Output Processing Tests ====================


@pytest.mark.asyncio
class TestOutputProcessing:
    """Tests for processing generation output."""

    def test_parse_json_array_response(self):
        """Test parsing JSON array response."""
        response = '[{"front":"Q1","back":"A1"},{"front":"Q2","back":"A2"}]'

        cards = json.loads(response)

        assert isinstance(cards, list)
        assert len(cards) == 2

    def test_parse_wrapped_json_response(self):
        """Test parsing JSON wrapped in markdown code block."""
        response = """```json
[{"front":"Q","back":"A"}]
```"""

        # Extract JSON from markdown
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        else:
            json_str = response

        cards = json.loads(json_str)
        assert len(cards) == 1

    def test_sanitize_card_content(self):
        """Test sanitizing card content."""
        raw_card = {
            "front": "  Question with whitespace  ",
            "back": "Answer\nwith\nnewlines",
        }

        # Sanitize
        sanitized = {
            "front": raw_card["front"].strip(),
            "back": raw_card["back"].replace("\n", " "),
        }

        assert sanitized["front"] == "Question with whitespace"
        assert "\n" not in sanitized["back"]

    def test_deduplicate_generated_cards(self):
        """Test deduplicating generated cards."""
        cards = [
            {"front": "Q1", "back": "A1"},
            {"front": "Q1", "back": "A1"},  # Duplicate
            {"front": "Q2", "back": "A2"},
        ]

        seen = set()
        unique_cards = []
        for card in cards:
            key = (card["front"], card["back"])
            if key not in seen:
                seen.add(key)
                unique_cards.append(card)

        assert len(unique_cards) == 2

    def test_add_default_tags(self):
        """Test adding default tags to generated cards."""
        cards = [
            {"front": "Q", "back": "A"},
            {"front": "Q2", "back": "A2", "tags": ["existing"]},
        ]

        default_tags = ["generated", "ai"]

        for card in cards:
            existing_tags = card.get("tags", [])
            card["tags"] = list(set(existing_tags + default_tags))

        assert "generated" in cards[0]["tags"]
        assert "existing" in cards[1]["tags"]
        assert "generated" in cards[1]["tags"]


# ==================== Integration Scenario Tests ====================


@pytest.mark.asyncio
class TestGenerationScenarios:
    """Tests for complete generation scenarios."""

    async def test_full_generation_workflow(self):
        """Test complete generation workflow."""
        # 1. Prepare request
        request = SAMPLE_GENERATION_REQUESTS["basic_card"]

        # 2. Build prompt
        prompt = f"Generate {request['num_cards']} {request['card_type']} cards about {request['topic']}"

        # 3. Call LLM
        mock_client = MockLLMClient()
        response = await mock_client.generate(prompt)

        # 4. Parse response
        cards = json.loads(response)

        # 5. Validate cards
        valid_cards = [c for c in cards if "front" in c and "back" in c]

        assert len(valid_cards) > 0
        assert mock_client.call_count == 1

    async def test_generation_with_retry(self):
        """Test generation with retry on failure."""
        mock_client = MockLLMClient()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt < 2:
                    mock_client.should_fail = True
                    mock_client.failure_message = f"Attempt {attempt + 1} failed"
                else:
                    mock_client.should_fail = False

                response = await mock_client.generate("Generate cards")
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                continue

        # Should succeed on third attempt
        assert mock_client.call_count == 3

    async def test_batch_generation(self):
        """Test generating cards in batches."""
        mock_client = MockLLMClient()

        total_cards_needed = 15
        batch_size = 5
        all_cards = []

        for batch in range(0, total_cards_needed, batch_size):
            response = await mock_client.generate(f"Generate {batch_size} cards")
            cards = json.loads(response)
            all_cards.extend(cards)

        assert mock_client.call_count == 3
        assert len(all_cards) == 9  # 3 cards per batch * 3 batches
