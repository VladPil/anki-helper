"""Card generation workflow using LangGraph.

This workflow implements the full card generation pipeline:
1. fetch_context - Retrieve relevant context from vector store
2. generate - Generate cards using LLM
3. check_duplicates - Check for duplicate cards
4. fact_check - Verify factual accuracy (optional)
5. route - Decide whether to save or filter cards
6. save - Save cards to database
"""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from src.core.logging import get_structured_logger
from src.services.llm.client import get_llm_client

from .base import BaseWorkflow

logger = get_structured_logger(__name__)


class CardGeneratorState(TypedDict, total=False):
    """State for card generation workflow."""

    # Input parameters
    topic: str
    num_cards: int
    card_type: str
    language: str
    difficulty: str
    context: str | None
    model_id: str | None
    fact_check: bool
    include_sources: bool
    tags: list[str]

    # Workflow state
    trace_id: str
    job_id: str
    step: str
    error: str | None
    progress: float
    is_cancelled: bool

    # Retrieved context
    retrieved_context: list[dict[str, Any]]
    context_sources: list[str]

    # Generated cards
    cards: list[dict[str, Any]]
    raw_generation: str

    # Duplicate checking
    duplicate_results: list[dict[str, Any]]

    # Fact checking
    fact_check_results: list[dict[str, Any]]

    # Final results
    approved_cards: list[dict[str, Any]]
    rejected_cards: list[dict[str, Any]]

    # Internal callbacks
    _on_progress: Any
    _is_cancelled: Any


class CardGeneratorWorkflow(BaseWorkflow):
    """Workflow for generating Anki cards.

    Implements a complete card generation pipeline with:
    - Context retrieval from vector store
    - LLM-based card generation
    - Duplicate detection
    - Fact checking (optional)
    - Smart routing and filtering
    """

    def __init__(self) -> None:
        """Initialize the card generator workflow."""
        super().__init__(name="CardGenerator")
        self._llm_client = None

    @property
    def llm_client(self):
        """Get the LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    def _build_graph(self) -> StateGraph:
        """Build the card generation workflow graph.

        Graph structure:
        fetch_context -> generate -> check_duplicates -> fact_check (conditional) -> route -> save

        Returns:
            Configured StateGraph.
        """
        # Create the graph with our state type
        graph = StateGraph(CardGeneratorState)

        # Add nodes
        graph.add_node("fetch_context", self._fetch_context)
        graph.add_node("generate", self._generate)
        graph.add_node("check_duplicates", self._check_duplicates)
        graph.add_node("fact_check", self._fact_check)
        graph.add_node("route", self._route)
        graph.add_node("save", self._save)

        # Define edges
        graph.set_entry_point("fetch_context")

        graph.add_edge("fetch_context", "generate")
        graph.add_edge("generate", "check_duplicates")

        # Conditional edge for fact checking
        graph.add_conditional_edges(
            "check_duplicates",
            self._should_fact_check,
            {
                "fact_check": "fact_check",
                "skip": "route",
            },
        )

        graph.add_edge("fact_check", "route")
        graph.add_edge("route", "save")
        graph.add_edge("save", END)

        return graph

    async def _fetch_context(self, state: CardGeneratorState) -> dict[str, Any]:
        """Fetch relevant context from vector store.

        Args:
            state: Current workflow state.

        Returns:
            State updates with retrieved context.
        """
        logger.info(
            "Fetching context",
            topic=state.get("topic"),
            trace_id=state.get("trace_id"),
        )

        # TODO: Implement actual vector store search
        # For now, use provided context or empty
        context = state.get("context") or ""

        # Mock context retrieval results
        retrieved_context = []
        context_sources = []

        if context:
            retrieved_context.append(
                {
                    "content": context,
                    "source": "user_provided",
                    "relevance": 1.0,
                }
            )
            context_sources.append("User provided context")

        return {
            "retrieved_context": retrieved_context,
            "context_sources": context_sources,
            "progress": 20.0,
        }

    async def _generate(self, state: CardGeneratorState) -> dict[str, Any]:
        """Generate cards using LLM.

        Args:
            state: Current workflow state.

        Returns:
            State updates with generated cards.
        """
        logger.info(
            "Generating cards",
            topic=state.get("topic"),
            num_cards=state.get("num_cards"),
            trace_id=state.get("trace_id"),
        )

        # Build the system prompt
        system_prompt = self._build_system_prompt(state)

        # Build the user prompt
        user_prompt = self._build_user_prompt(state)

        # Get model ID
        model_id = state.get("model_id") or "gpt-4"

        try:
            # Call LLM
            response = await self.llm_client.generate(
                model_id=model_id,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=4000,
                trace_id=state.get("trace_id"),
            )

            # Parse the response
            cards = self._parse_cards(response.content, state)

            logger.info(
                "Cards generated",
                num_cards=len(cards),
                trace_id=state.get("trace_id"),
            )

            return {
                "cards": cards,
                "raw_generation": response.content,
                "progress": 50.0,
            }

        except Exception as e:
            logger.error("Card generation failed", error=str(e))
            return {
                "cards": [],
                "error": f"Card generation failed: {e}",
            }

    async def _check_duplicates(self, state: CardGeneratorState) -> dict[str, Any]:
        """Check for duplicate cards in the deck.

        Args:
            state: Current workflow state.

        Returns:
            State updates with duplicate check results.
        """
        logger.info(
            "Checking duplicates",
            num_cards=len(state.get("cards", [])),
            trace_id=state.get("trace_id"),
        )

        cards = state.get("cards", [])
        duplicate_results = []

        # TODO: Implement actual duplicate checking via embeddings
        # For now, mark all cards as non-duplicate
        for i, card in enumerate(cards):
            duplicate_results.append(
                {
                    "card_index": i,
                    "is_duplicate": False,
                    "similarity_score": 0.0,
                    "duplicate_card_id": None,
                }
            )

        return {
            "duplicate_results": duplicate_results,
            "progress": 65.0,
        }

    async def _fact_check(self, state: CardGeneratorState) -> dict[str, Any]:
        """Fact-check generated cards.

        Args:
            state: Current workflow state.

        Returns:
            State updates with fact check results.
        """
        logger.info(
            "Fact-checking cards",
            num_cards=len(state.get("cards", [])),
            trace_id=state.get("trace_id"),
        )

        cards = state.get("cards", [])
        fact_check_results = []

        for i, card in enumerate(cards):
            try:
                # Combine front and back for fact checking
                claim = f"Question: {card['front']}\nAnswer: {card['back']}"

                result = await self.llm_client.fact_check(
                    claim=claim,
                    context=state.get("context"),
                    trace_id=state.get("trace_id"),
                )

                fact_check_results.append(
                    {
                        "card_index": i,
                        "confidence": result.confidence,
                        "sources": result.sources,
                        "reasoning": result.reasoning,
                    }
                )

            except Exception as e:
                logger.warning(f"Fact check failed for card {i}", error=str(e))
                fact_check_results.append(
                    {
                        "card_index": i,
                        "confidence": 0.5,
                        "sources": [],
                        "reasoning": f"Fact check failed: {e}",
                    }
                )

        return {
            "fact_check_results": fact_check_results,
            "progress": 80.0,
        }

    async def _route(self, state: CardGeneratorState) -> dict[str, Any]:
        """Route cards based on quality checks.

        Args:
            state: Current workflow state.

        Returns:
            State updates with approved and rejected cards.
        """
        logger.info(
            "Routing cards",
            num_cards=len(state.get("cards", [])),
            trace_id=state.get("trace_id"),
        )

        cards = state.get("cards", [])
        duplicate_results = state.get("duplicate_results", [])
        fact_check_results = state.get("fact_check_results", [])

        approved_cards = []
        rejected_cards = []

        for i, card in enumerate(cards):
            # Get duplicate info
            dup_info = next(
                (d for d in duplicate_results if d.get("card_index") == i),
                {"is_duplicate": False},
            )

            # Get fact check info
            fact_info = next(
                (f for f in fact_check_results if f.get("card_index") == i),
                {"confidence": 1.0},
            )

            # Apply routing logic
            is_duplicate = dup_info.get("is_duplicate", False)
            confidence = fact_info.get("confidence", 1.0)

            # Add metadata to card
            enriched_card = {
                **card,
                "is_duplicate": is_duplicate,
                "duplicate_card_id": dup_info.get("duplicate_card_id"),
                "similarity_score": dup_info.get("similarity_score"),
                "confidence": confidence,
                "source": ", ".join(fact_info.get("sources", [])) or None,
            }

            # Route based on quality
            if is_duplicate:
                rejected_cards.append(
                    {
                        **enriched_card,
                        "rejection_reason": "duplicate",
                    }
                )
            elif confidence < 0.3:
                rejected_cards.append(
                    {
                        **enriched_card,
                        "rejection_reason": "low_confidence",
                    }
                )
            else:
                approved_cards.append(enriched_card)

        logger.info(
            "Cards routed",
            approved=len(approved_cards),
            rejected=len(rejected_cards),
            trace_id=state.get("trace_id"),
        )

        return {
            "approved_cards": approved_cards,
            "rejected_cards": rejected_cards,
            "progress": 90.0,
        }

    async def _save(self, state: CardGeneratorState) -> dict[str, Any]:
        """Save approved cards.

        Args:
            state: Current workflow state.

        Returns:
            State updates with final results.
        """
        logger.info(
            "Saving cards",
            num_cards=len(state.get("approved_cards", [])),
            trace_id=state.get("trace_id"),
        )

        approved_cards = state.get("approved_cards", [])

        # TODO: Implement actual card saving to database
        # For now, just return the cards
        final_cards = []
        for card in approved_cards:
            final_cards.append(
                {
                    "front": card["front"],
                    "back": card["back"],
                    "tags": card.get("tags", state.get("tags", [])),
                    "source": card.get("source"),
                    "confidence": card.get("confidence"),
                    "is_duplicate": card.get("is_duplicate", False),
                    "duplicate_card_id": card.get("duplicate_card_id"),
                    "similarity_score": card.get("similarity_score"),
                }
            )

        return {
            "cards": final_cards,
            "progress": 100.0,
        }

    def _should_fact_check(
        self,
        state: CardGeneratorState,
    ) -> Literal["fact_check", "skip"]:
        """Determine if fact checking should be performed.

        Args:
            state: Current workflow state.

        Returns:
            Route name: "fact_check" or "skip".
        """
        # Check for errors
        if state.get("error"):
            return "skip"

        # Check if fact checking is enabled
        if not state.get("fact_check", True):
            return "skip"

        # Check if we have cards to check
        if not state.get("cards"):
            return "skip"

        return "fact_check"

    def _build_system_prompt(self, state: CardGeneratorState) -> str:
        """Build the system prompt for card generation.

        Args:
            state: Current workflow state.

        Returns:
            System prompt string.
        """
        card_type = state.get("card_type", "basic")
        language = state.get("language", "en")
        difficulty = state.get("difficulty", "medium")

        card_type_instructions = {
            "basic": "Create basic flashcards with a question on the front and answer on the back.",
            "cloze": "Create cloze deletion cards where key terms are wrapped in {{c1::term}}.",
            "basic_reversed": "Create cards that can be studied in both directions.",
        }

        difficulty_guidelines = {
            "easy": "Focus on fundamental concepts. Use simple language and short answers.",
            "medium": "Cover moderate complexity. Include some details but stay concise.",
            "hard": "Cover advanced topics. Include nuanced details and connections.",
        }

        return f"""You are an expert flashcard creator for Anki. \
Your task is to create high-quality educational flashcards.

CARD TYPE: {card_type}
{card_type_instructions.get(card_type, card_type_instructions["basic"])}

DIFFICULTY: {difficulty}
{difficulty_guidelines.get(difficulty, difficulty_guidelines["medium"])}

LANGUAGE: {language}
Create all content in {language}.

GUIDELINES:
1. Each card should focus on ONE concept
2. Questions should be clear and unambiguous
3. Answers should be concise but complete
4. Avoid yes/no questions
5. Include context when needed
6. Make cards that test understanding, not just recall

OUTPUT FORMAT:
Return cards as JSON array:
```json
[
    {{
        "front": "Question or prompt",
        "back": "Answer or response",
        "tags": ["tag1", "tag2"]
    }}
]
```"""

    def _build_user_prompt(self, state: CardGeneratorState) -> str:
        """Build the user prompt for card generation.

        Args:
            state: Current workflow state.

        Returns:
            User prompt string.
        """
        topic = state.get("topic", "")
        num_cards = state.get("num_cards", 5)
        tags = state.get("tags", [])

        prompt = f"Create {num_cards} flashcards about: {topic}"

        # Add context if available
        retrieved_context = state.get("retrieved_context", [])
        if retrieved_context:
            context_text = "\n\n".join(c.get("content", "") for c in retrieved_context)
            prompt += f"\n\nUSE THIS CONTEXT:\n{context_text}"

        # Add tags if specified
        if tags:
            prompt += f"\n\nInclude these tags: {', '.join(tags)}"

        return prompt

    def _parse_cards(
        self,
        content: str,
        state: CardGeneratorState,
    ) -> list[dict[str, Any]]:
        """Parse cards from LLM response.

        Args:
            content: Raw LLM response content.
            state: Current workflow state.

        Returns:
            List of parsed card dictionaries.
        """
        import json
        import re

        # Try to extract JSON from the response
        # Handle markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to find JSON array directly
            json_match = re.search(r"\[[\s\S]*\]", content)
            if json_match:
                json_str = json_match.group(0)
            else:
                logger.warning("No JSON found in LLM response")
                return []

        try:
            cards_data = json.loads(json_str)

            if not isinstance(cards_data, list):
                cards_data = [cards_data]

            cards = []
            default_tags = state.get("tags", [])

            for card in cards_data:
                if isinstance(card, dict) and "front" in card and "back" in card:
                    cards.append(
                        {
                            "front": str(card["front"]).strip(),
                            "back": str(card["back"]).strip(),
                            "tags": card.get("tags", default_tags),
                        }
                    )

            return cards

        except json.JSONDecodeError as e:
            logger.error("Failed to parse cards JSON", error=str(e))
            return []
