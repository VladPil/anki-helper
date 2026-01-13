"""Async LLM client for SOP_LLM service.

This client integrates with SOP_LLM Executor service for all LLM operations.
SOP_LLM provides unified access to multiple LLM providers (OpenAI, Anthropic, Local, etc.)
through an asynchronous task-based API.
"""

import asyncio
import time
from enum import Enum
from typing import Any

import httpx
from opentelemetry import trace
from pydantic import BaseModel

from src.core.config import settings
from src.core.exceptions import (
    LLMServiceError,
    PerplexityError,
    RateLimitError,
)
from src.core.logging import get_structured_logger
from src.core.metrics import LLM_LATENCY, LLM_REQUEST_COUNT, LLM_TOKEN_COUNT

logger = get_structured_logger(__name__)
tracer = trace.get_tracer(__name__)


class TaskStatus(str, Enum):
    """Task status in SOP_LLM."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LLMResponse(BaseModel):
    """Response from LLM service."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str


class FactCheckResult(BaseModel):
    """Result of fact-checking via Perplexity."""

    confidence: float
    sources: list[str]
    reasoning: str


class EmbeddingResponse(BaseModel):
    """Response from embedding generation."""

    embeddings: list[list[float]]
    model: str
    dimensions: int


class SopLLMClient:
    """Async client for SOP_LLM Executor service.

    SOP_LLM is a task-based asynchronous LLM service that:
    - Supports multiple providers (OpenAI, Anthropic, Local GGUF, etc.)
    - Uses priority queue for task processing
    - Provides structured output support
    - Integrates with Langfuse for observability
    """

    def __init__(self) -> None:
        """Initialize the SOP_LLM client."""
        self.base_url = settings.sop_llm.api_base_url.rstrip("/")
        self.timeout = settings.sop_llm.timeout
        self.poll_interval = 0.5  # seconds between status polls
        self.max_poll_attempts = int(self.timeout / self.poll_interval) + 10
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=httpx.Timeout(self.timeout, connect=10.0),
            )
        return self._client

    async def _create_task(
        self,
        model: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: dict[str, Any] | None = None,
        priority: float = 5.0,
    ) -> str:
        """Create a generation task in SOP_LLM.

        Args:
            model: Model name (must be registered in SOP_LLM).
            prompt: The prompt text.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            response_format: Optional JSON schema for structured output.
            priority: Task priority (higher = more important).

        Returns:
            Task ID for polling.

        Raises:
            LLMServiceError: If task creation fails.
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "priority": priority,
        }

        if response_format:
            payload["response_format"] = response_format

        response = await self.client.post("/api/v1/tasks", json=payload)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise RateLimitError(f"SOP_LLM rate limit exceeded. Retry after {retry_after}s")

        if response.status_code >= 400:
            error_detail = response.text
            logger.error(
                "SOP_LLM task creation failed",
                status_code=response.status_code,
                error=error_detail,
            )
            raise LLMServiceError(f"SOP_LLM error: {response.status_code} - {error_detail}")

        data = response.json()
        return data["task_id"]  # type: ignore[no-any-return]

    async def _poll_task(self, task_id: str) -> dict[str, Any]:
        """Poll task status until completion.

        Args:
            task_id: The task ID to poll.

        Returns:
            Completed task response with result.

        Raises:
            LLMServiceError: If task fails or times out.
        """
        for attempt in range(self.max_poll_attempts):
            response = await self.client.get(f"/api/v1/tasks/{task_id}")

            if response.status_code >= 400:
                raise LLMServiceError(f"Failed to get task status: {response.text}")

            data = response.json()
            status = data.get("status")

            if status == TaskStatus.COMPLETED:
                return data  # type: ignore[no-any-return]

            if status == TaskStatus.FAILED:
                error_msg = data.get("error", "Unknown error")
                raise LLMServiceError(f"SOP_LLM task failed: {error_msg}")

            # Still processing, wait and poll again
            await asyncio.sleep(self.poll_interval)

        raise LLMServiceError(f"Task {task_id} timed out after {self.timeout}s")

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
        """Generate text using the specified model via SOP_LLM.

        Args:
            model_id: The model identifier (must be registered in SOP_LLM).
            system_prompt: System message for context.
            user_prompt: User message/prompt.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens to generate.
            trace_id: Optional trace ID for distributed tracing.
            response_format: Optional JSON schema for structured output.

        Returns:
            LLMResponse with generated content and metadata.

        Raises:
            LLMServiceError: If the LLM service returns an error.
            RateLimitError: If rate limit is exceeded.
        """
        with tracer.start_as_current_span(
            "sop_llm.generate",
            attributes={
                "llm.model": model_id,
                "llm.temperature": temperature,
                "llm.max_tokens": max_tokens,
            },
        ) as span:
            start_time = time.perf_counter()

            if trace_id:
                span.set_attribute("trace.id", trace_id)

            # Combine prompts into a single prompt for SOP_LLM
            full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"

            logger.info(
                "SOP_LLM request started",
                model=model_id,
                trace_id=trace_id,
            )

            try:
                # Create task
                task_id = await self._create_task(
                    model=model_id,
                    prompt=full_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                )

                span.set_attribute("sop_llm.task_id", task_id)

                # Poll for completion
                task_data = await self._poll_task(task_id)

                latency = time.perf_counter() - start_time
                LLM_LATENCY.labels(model=model_id).observe(latency)

                # Extract result
                result = task_data.get("result", {})
                usage = result.get("usage", {})

                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                # Record metrics
                LLM_REQUEST_COUNT.labels(model=model_id, status="success").inc()
                LLM_TOKEN_COUNT.labels(model=model_id, direction="input").inc(input_tokens)
                LLM_TOKEN_COUNT.labels(model=model_id, direction="output").inc(output_tokens)

                # Add to span
                span.set_attribute("llm.input_tokens", input_tokens)
                span.set_attribute("llm.output_tokens", output_tokens)
                span.set_attribute("llm.finish_reason", result.get("finish_reason", ""))

                logger.info(
                    "SOP_LLM request completed",
                    model=model_id,
                    task_id=task_id,
                    latency=latency,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

                return LLMResponse(
                    content=result.get("text", ""),
                    model=result.get("model", model_id),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    finish_reason=result.get("finish_reason", "stop"),
                )

            except RateLimitError:
                LLM_REQUEST_COUNT.labels(model=model_id, status="rate_limited").inc()
                raise

            except httpx.TimeoutException as e:
                LLM_REQUEST_COUNT.labels(model=model_id, status="timeout").inc()
                logger.error("SOP_LLM request timeout", model=model_id, error=str(e))
                raise LLMServiceError(f"SOP_LLM request timeout after {self.timeout}s") from e

            except httpx.HTTPError as e:
                LLM_REQUEST_COUNT.labels(model=model_id, status="error").inc()
                logger.error("SOP_LLM HTTP error", model=model_id, error=str(e))
                raise LLMServiceError(f"SOP_LLM HTTP error: {e}") from e

    async def generate_with_schema(
        self,
        model_id: str,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 2000,
        trace_id: str | None = None,
    ) -> LLMResponse:
        """Generate structured output using JSON schema.

        Args:
            model_id: The model identifier.
            system_prompt: System message for context.
            user_prompt: User message/prompt.
            json_schema: JSON schema for structured output.
            temperature: Sampling temperature (default 0.1 for structured output).
            max_tokens: Maximum tokens to generate.
            trace_id: Optional trace ID for distributed tracing.

        Returns:
            LLMResponse with JSON content.
        """
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "response",
                "schema": json_schema,
            },
        }

        return await self.generate(
            model_id=model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_id=trace_id,
            response_format=response_format,
        )

    async def fact_check(
        self,
        claim: str,
        context: str | None = None,
        trace_id: str | None = None,
    ) -> FactCheckResult:
        """Fact-check a claim via Perplexity through SOP_LLM.

        Args:
            claim: The claim to fact-check.
            context: Optional context for the claim.
            trace_id: Optional trace ID for distributed tracing.

        Returns:
            FactCheckResult with confidence, sources, and reasoning.

        Raises:
            PerplexityError: If fact-checking fails.
        """
        with tracer.start_as_current_span(
            "sop_llm.fact_check",
            attributes={"claim_length": len(claim)},
        ) as span:
            if trace_id:
                span.set_attribute("trace.id", trace_id)

            system_prompt = """You are a fact-checking assistant. \
Your task is to verify claims using your knowledge and provide a confidence score.

You must respond in the following JSON format:
{
    "confidence": <float between 0.0 and 1.0>,
    "sources": [<list of source descriptions or URLs if known>],
    "reasoning": "<your reasoning for the confidence score>"
}

Confidence levels:
- 0.9-1.0: Highly confident, well-established fact
- 0.7-0.9: Confident, generally accepted
- 0.5-0.7: Moderate confidence, some uncertainty
- 0.3-0.5: Low confidence, conflicting information
- 0.0-0.3: Very low confidence, likely false or unverifiable"""

            user_prompt = f"Please fact-check the following claim:\n\nClaim: {claim}"
            if context:
                user_prompt += f"\n\nContext: {context}"

            # JSON schema for structured output
            json_schema = {
                "type": "object",
                "properties": {
                    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "reasoning": {"type": "string"},
                },
                "required": ["confidence", "sources", "reasoning"],
            }

            try:
                # Use Perplexity model for fact-checking (online search capability)
                response = await self.generate_with_schema(
                    model_id=settings.perplexity.model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    json_schema=json_schema,
                    temperature=0.1,
                    max_tokens=1000,
                    trace_id=trace_id,
                )

                # Parse the JSON response
                import json

                try:
                    result = json.loads(response.content.strip())
                    return FactCheckResult(
                        confidence=float(result.get("confidence", 0.5)),
                        sources=result.get("sources", []),
                        reasoning=result.get("reasoning", "No reasoning provided"),
                    )

                except json.JSONDecodeError:
                    logger.warning(
                        "Failed to parse fact-check response as JSON",
                        response=response.content[:500],
                    )
                    return FactCheckResult(
                        confidence=0.5,
                        sources=[],
                        reasoning=response.content,
                    )

            except LLMServiceError as e:
                logger.error("Fact-check failed", error=str(e))
                raise PerplexityError(f"Fact-check failed: {e}") from e

    async def generate_embeddings(
        self,
        texts: list[str],
        model_name: str | None = None,
        trace_id: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for texts via SOP_LLM.

        Args:
            texts: List of texts to embed.
            model_name: Optional embedding model name.
            trace_id: Optional trace ID for distributed tracing.

        Returns:
            List of embedding vectors.

        Raises:
            LLMServiceError: If embedding generation fails.
        """
        with tracer.start_as_current_span(
            "sop_llm.generate_embeddings",
            attributes={"batch_size": len(texts)},
        ) as span:
            if trace_id:
                span.set_attribute("trace.id", trace_id)

            embedding_model = model_name or settings.embedding.model

            payload = {
                "texts": texts,
                "model_name": embedding_model,
            }

            try:
                response = await self.client.post("/api/v1/embeddings", json=payload)

                if response.status_code >= 400:
                    raise LLMServiceError(
                        f"Embedding error: {response.status_code} - {response.text}"
                    )

                data = response.json()
                embeddings = data.get("embeddings", [])

                span.set_attribute("embedding.dimension", len(embeddings[0]) if embeddings else 0)
                span.set_attribute("embedding.model", embedding_model)

                return embeddings  # type: ignore[no-any-return]

            except httpx.HTTPError as e:
                raise LLMServiceError(f"Embedding request failed: {e}") from e

    async def calculate_similarity(
        self,
        text1: str,
        text2: str,
        model_name: str | None = None,
    ) -> float:
        """Calculate cosine similarity between two texts via SOP_LLM.

        Args:
            text1: First text.
            text2: Second text.
            model_name: Optional embedding model name.

        Returns:
            Similarity score (0.0 to 1.0).

        Raises:
            LLMServiceError: If similarity calculation fails.
        """
        embedding_model = model_name or settings.embedding.model

        payload = {
            "text1": text1,
            "text2": text2,
            "model_name": embedding_model,
        }

        try:
            response = await self.client.post("/api/v1/embeddings/similarity", json=payload)

            if response.status_code >= 400:
                raise LLMServiceError(f"Similarity error: {response.status_code} - {response.text}")

            data = response.json()
            return data.get("similarity", 0.0)  # type: ignore[no-any-return]

        except httpx.HTTPError as e:
            raise LLMServiceError(f"Similarity request failed: {e}") from e

    async def health_check(self) -> bool:
        """Check if the SOP_LLM service is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            response = await self.client.get("/api/v1/monitor/health")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict[str, Any]]:
        """Get list of available models in SOP_LLM.

        Returns:
            List of model info dictionaries.
        """
        try:
            response = await self.client.get("/api/v1/models")
            if response.status_code == 200:
                data = response.json()
                return data.get("models", [])  # type: ignore[no-any-return]
            return []
        except Exception:
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "SopLLMClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Backwards compatibility alias
LLMClient = SopLLMClient

# Singleton instance
_llm_client: SopLLMClient | None = None


def get_llm_client() -> SopLLMClient:
    """Get or create the LLM client singleton.

    Returns:
        SopLLMClient instance.
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = SopLLMClient()
    return _llm_client


async def close_llm_client() -> None:
    """Close the LLM client singleton."""
    global _llm_client
    if _llm_client is not None:
        await _llm_client.close()
        _llm_client = None
