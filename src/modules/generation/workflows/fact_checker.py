"""Fact checking workflow using LangGraph.

This workflow provides standalone fact checking functionality:
1. parse_claims - Extract verifiable claims from content
2. search_sources - Search for relevant sources
3. verify_claims - Verify each claim against sources
4. aggregate - Combine results into final verdict
"""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from src.core.logging import get_structured_logger
from src.services.llm.client import get_llm_client

from .base import BaseWorkflow

logger = get_structured_logger(__name__)


class FactCheckerState(TypedDict, total=False):
    """State for fact checking workflow."""

    # Input parameters
    content: str
    context: str | None
    source_type: str  # "card", "text", "claim"

    # Workflow state
    trace_id: str
    step: str
    error: str | None
    progress: float
    is_cancelled: bool

    # Extracted claims
    claims: list[dict[str, Any]]

    # Source search results
    sources: list[dict[str, Any]]

    # Verification results
    verification_results: list[dict[str, Any]]

    # Final result
    overall_confidence: float
    verdict: str
    summary: str

    # Internal callbacks
    _on_progress: Any
    _is_cancelled: Any


class FactCheckerWorkflow(BaseWorkflow):
    """Workflow for fact-checking content.

    Implements a comprehensive fact-checking pipeline:
    - Claim extraction from content
    - Source search and retrieval
    - Claim verification against sources
    - Aggregated verdict generation
    """

    def __init__(self) -> None:
        """Initialize the fact checker workflow."""
        super().__init__(name="FactChecker")
        self._llm_client = None

    @property
    def llm_client(self):
        """Get the LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    def _build_graph(self) -> StateGraph:
        """Build the fact checking workflow graph.

        Graph structure:
        parse_claims -> search_sources -> verify_claims -> aggregate

        Returns:
            Configured StateGraph.
        """
        graph = StateGraph(FactCheckerState)

        # Add nodes
        graph.add_node("parse_claims", self._parse_claims)
        graph.add_node("search_sources", self._search_sources)
        graph.add_node("verify_claims", self._verify_claims)
        graph.add_node("aggregate", self._aggregate)

        # Define edges
        graph.set_entry_point("parse_claims")

        # Conditional edge after parsing - skip if no claims
        graph.add_conditional_edges(
            "parse_claims",
            self._has_claims,
            {
                "continue": "search_sources",
                "skip": "aggregate",
            },
        )

        graph.add_edge("search_sources", "verify_claims")
        graph.add_edge("verify_claims", "aggregate")
        graph.add_edge("aggregate", END)

        return graph

    async def _parse_claims(self, state: FactCheckerState) -> dict[str, Any]:
        """Parse and extract verifiable claims from content.

        Args:
            state: Current workflow state.

        Returns:
            State updates with extracted claims.
        """
        logger.info(
            "Parsing claims",
            content_length=len(state.get("content", "")),
            trace_id=state.get("trace_id"),
        )

        content = state.get("content", "")
        source_type = state.get("source_type", "text")

        if not content:
            return {
                "claims": [],
                "progress": 25.0,
            }

        # Build prompt based on source type
        if source_type == "card":
            system_prompt = """You are an expert at identifying factual claims in flashcard content.
Extract all verifiable factual claims from the given question-answer pair.
Focus on objective, checkable statements rather than opinions or definitions.

Respond with a JSON array of claims:
```json
[
    {
        "claim": "The factual statement",
        "type": "historical/scientific/definition/statistic",
        "importance": "high/medium/low"
    }
]
```"""
        else:
            system_prompt = """You are an expert at identifying factual claims in text.
Extract all verifiable factual claims from the given content.
Focus on objective, checkable statements rather than opinions.

Respond with a JSON array of claims:
```json
[
    {
        "claim": "The factual statement",
        "type": "historical/scientific/definition/statistic",
        "importance": "high/medium/low"
    }
]
```"""

        try:
            response = await self.llm_client.generate(
                model_id="gpt-4",
                system_prompt=system_prompt,
                user_prompt=f"Extract claims from:\n{content}",
                temperature=0.3,
                max_tokens=1000,
                trace_id=state.get("trace_id"),
            )

            claims = self._parse_json_response(response.content)

            logger.info(
                "Claims extracted",
                num_claims=len(claims),
                trace_id=state.get("trace_id"),
            )

            return {
                "claims": claims,
                "progress": 25.0,
            }

        except Exception as e:
            logger.error("Claim parsing failed", error=str(e))
            # Fall back to treating entire content as one claim
            return {
                "claims": [{"claim": content, "type": "unknown", "importance": "medium"}],
                "progress": 25.0,
            }

    async def _search_sources(self, state: FactCheckerState) -> dict[str, Any]:
        """Search for relevant sources to verify claims.

        Args:
            state: Current workflow state.

        Returns:
            State updates with found sources.
        """
        logger.info(
            "Searching sources",
            num_claims=len(state.get("claims", [])),
            trace_id=state.get("trace_id"),
        )

        # Claims available in state but currently unused
        # claims = state.get("claims", [])
        sources = []

        # TODO: Implement actual source search (web search, knowledge base, etc.)
        # For now, we'll rely on the LLM's knowledge

        # Add context as a source if provided
        context = state.get("context")
        if context:
            sources.append(
                {
                    "type": "provided_context",
                    "content": context,
                    "reliability": 0.8,
                }
            )

        return {
            "sources": sources,
            "progress": 50.0,
        }

    async def _verify_claims(self, state: FactCheckerState) -> dict[str, Any]:
        """Verify each claim against available sources.

        Args:
            state: Current workflow state.

        Returns:
            State updates with verification results.
        """
        logger.info(
            "Verifying claims",
            num_claims=len(state.get("claims", [])),
            trace_id=state.get("trace_id"),
        )

        claims = state.get("claims", [])
        sources = state.get("sources", [])
        verification_results = []

        for i, claim_data in enumerate(claims):
            claim = claim_data.get("claim", "")

            try:
                # Use fact_check method from LLM client
                result = await self.llm_client.fact_check(
                    claim=claim,
                    context="\n".join(s.get("content", "") for s in sources),
                    trace_id=state.get("trace_id"),
                )

                verification_results.append(
                    {
                        "claim_index": i,
                        "claim": claim,
                        "confidence": result.confidence,
                        "sources": result.sources,
                        "reasoning": result.reasoning,
                        "verified": result.confidence >= 0.7,
                    }
                )

            except Exception as e:
                logger.warning(f"Verification failed for claim {i}", error=str(e))
                verification_results.append(
                    {
                        "claim_index": i,
                        "claim": claim,
                        "confidence": 0.5,
                        "sources": [],
                        "reasoning": f"Verification failed: {e}",
                        "verified": False,
                    }
                )

        return {
            "verification_results": verification_results,
            "progress": 75.0,
        }

    async def _aggregate(self, state: FactCheckerState) -> dict[str, Any]:
        """Aggregate verification results into final verdict.

        Args:
            state: Current workflow state.

        Returns:
            State updates with final verdict.
        """
        logger.info(
            "Aggregating results",
            trace_id=state.get("trace_id"),
        )

        verification_results = state.get("verification_results", [])

        if not verification_results:
            return {
                "overall_confidence": 0.5,
                "verdict": "unverifiable",
                "summary": "No claims could be extracted for verification.",
                "progress": 100.0,
            }

        # Calculate overall confidence
        confidences = [r.get("confidence", 0.5) for r in verification_results]
        overall_confidence = sum(confidences) / len(confidences)

        # Weight by importance if available
        claims = state.get("claims", [])
        importance_weights = {"high": 1.5, "medium": 1.0, "low": 0.5}

        if claims:
            weighted_sum = 0.0
            weight_total = 0.0

            for i, result in enumerate(verification_results):
                if i < len(claims):
                    importance = claims[i].get("importance", "medium")
                    weight = importance_weights.get(importance, 1.0)
                    weighted_sum += result.get("confidence", 0.5) * weight
                    weight_total += weight

            if weight_total > 0:
                overall_confidence = weighted_sum / weight_total

        # Determine verdict
        if overall_confidence >= 0.8:
            verdict = "verified"
        elif overall_confidence >= 0.6:
            verdict = "likely_accurate"
        elif overall_confidence >= 0.4:
            verdict = "uncertain"
        elif overall_confidence >= 0.2:
            verdict = "likely_inaccurate"
        else:
            verdict = "false"

        # Generate summary
        verified_count = sum(1 for r in verification_results if r.get("verified", False))
        total_count = len(verification_results)

        summary = f"{verified_count}/{total_count} claims verified. "

        if verdict == "verified":
            summary += "The content appears to be factually accurate."
        elif verdict == "likely_accurate":
            summary += "The content is mostly accurate with minor uncertainties."
        elif verdict == "uncertain":
            summary += "The content has mixed accuracy. Some claims could not be verified."
        elif verdict == "likely_inaccurate":
            summary += "The content contains significant inaccuracies."
        else:
            summary += "The content appears to contain false information."

        logger.info(
            "Aggregation complete",
            overall_confidence=overall_confidence,
            verdict=verdict,
            trace_id=state.get("trace_id"),
        )

        return {
            "overall_confidence": overall_confidence,
            "verdict": verdict,
            "summary": summary,
            "progress": 100.0,
        }

    def _has_claims(self, state: FactCheckerState) -> Literal["continue", "skip"]:
        """Check if there are claims to verify.

        Args:
            state: Current workflow state.

        Returns:
            Route name: "continue" or "skip".
        """
        if state.get("error"):
            return "skip"

        claims = state.get("claims", [])
        if not claims:
            return "skip"

        return "continue"

    def _parse_json_response(self, content: str) -> list[dict[str, Any]]:
        """Parse JSON from LLM response.

        Args:
            content: Raw LLM response.

        Returns:
            Parsed JSON list.
        """
        import json
        import re

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to find JSON array directly
            json_match = re.search(r"\[[\s\S]*\]", content)
            if json_match:
                json_str = json_match.group(0)
            else:
                return []

        try:
            data = json.loads(json_str)
            if isinstance(data, list):
                return data
            return [data]
        except json.JSONDecodeError:
            return []

    async def check(
        self,
        content: str,
        context: str | None = None,
        source_type: str = "text",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Convenience method to run fact checking.

        Args:
            content: Content to fact-check.
            context: Optional context for verification.
            source_type: Type of content (card, text, claim).
            trace_id: Optional trace ID.

        Returns:
            Fact check results.
        """
        result = await self.run(
            content=content,
            context=context,
            source_type=source_type,
            trace_id=trace_id,
        )

        return {
            "confidence": result.get("overall_confidence", 0.5),
            "verdict": result.get("verdict", "unknown"),
            "summary": result.get("summary", ""),
            "claims": result.get("claims", []),
            "verification_results": result.get("verification_results", []),
        }
