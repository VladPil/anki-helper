"""AnkiRAG - Event Logger.

Structured event logging for card generation events.
Provides type-safe logging functions for observability.
"""

from loguru import logger


def log_generation_started(
    job_id: str,
    topic: str,
    num_cards: int,
    *,
    user_id: str | None = None,
    deck_id: str | None = None,
) -> None:
    """Log the start of a card generation job.

    Args:
        job_id: Unique identifier for the generation job
        topic: Topic or subject for card generation
        num_cards: Number of cards requested
        user_id: Optional user identifier
        deck_id: Optional deck identifier
    """
    logger.info(
        "Card generation started",
        event="generation.started",
        job_id=job_id,
        topic=topic,
        num_cards=num_cards,
        user_id=user_id,
        deck_id=deck_id,
    )


def log_generation_completed(
    job_id: str,
    cards_generated: int,
    duration_ms: int,
    *,
    user_id: str | None = None,
    model: str | None = None,
) -> None:
    """Log the successful completion of a card generation job.

    Args:
        job_id: Unique identifier for the generation job
        cards_generated: Number of cards actually generated
        duration_ms: Total duration in milliseconds
        user_id: Optional user identifier
        model: Optional model used for generation
    """
    logger.info(
        "Card generation completed",
        event="generation.completed",
        job_id=job_id,
        cards_generated=cards_generated,
        duration_ms=duration_ms,
        user_id=user_id,
        model=model,
    )


def log_generation_failed(
    job_id: str,
    error: str,
    retry_count: int,
    *,
    user_id: str | None = None,
    error_type: str | None = None,
    recoverable: bool = True,
) -> None:
    """Log a card generation failure.

    Args:
        job_id: Unique identifier for the generation job
        error: Error message describing the failure
        retry_count: Number of retries attempted
        user_id: Optional user identifier
        error_type: Optional error classification
        recoverable: Whether the error is recoverable with retry
    """
    log_level = logger.warning if recoverable else logger.error
    log_level(
        "Card generation failed",
        event="generation.failed",
        job_id=job_id,
        error=error,
        retry_count=retry_count,
        user_id=user_id,
        error_type=error_type,
        recoverable=recoverable,
    )


def log_generation_progress(
    job_id: str,
    cards_completed: int,
    total_cards: int,
    *,
    current_step: str | None = None,
) -> None:
    """Log generation progress update.

    Args:
        job_id: Unique identifier for the generation job
        cards_completed: Number of cards completed so far
        total_cards: Total number of cards to generate
        current_step: Optional description of current step
    """
    progress_pct = (cards_completed / total_cards * 100) if total_cards > 0 else 0
    logger.debug(
        "Card generation progress",
        event="generation.progress",
        job_id=job_id,
        cards_completed=cards_completed,
        total_cards=total_cards,
        progress_pct=round(progress_pct, 1),
        current_step=current_step,
    )


def log_llm_request(
    job_id: str,
    model: str,
    prompt_tokens: int,
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> None:
    """Log an LLM API request.

    Args:
        job_id: Job identifier for correlation
        model: Model name/identifier
        prompt_tokens: Number of tokens in the prompt
        temperature: Optional temperature setting
        max_tokens: Optional max tokens setting
    """
    logger.debug(
        "LLM request sent",
        event="llm.request",
        job_id=job_id,
        model=model,
        prompt_tokens=prompt_tokens,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def log_llm_response(
    job_id: str,
    model: str,
    completion_tokens: int,
    duration_ms: int,
    *,
    total_tokens: int | None = None,
) -> None:
    """Log an LLM API response.

    Args:
        job_id: Job identifier for correlation
        model: Model name/identifier
        completion_tokens: Number of tokens in the response
        duration_ms: Request duration in milliseconds
        total_tokens: Optional total tokens used
    """
    logger.debug(
        "LLM response received",
        event="llm.response",
        job_id=job_id,
        model=model,
        completion_tokens=completion_tokens,
        duration_ms=duration_ms,
        total_tokens=total_tokens,
    )


def log_embedding_request(
    job_id: str,
    num_texts: int,
    model: str,
) -> None:
    """Log an embedding request.

    Args:
        job_id: Job identifier for correlation
        num_texts: Number of texts to embed
        model: Embedding model name
    """
    logger.debug(
        "Embedding request sent",
        event="embedding.request",
        job_id=job_id,
        num_texts=num_texts,
        model=model,
    )


def log_fact_check_result(
    job_id: str,
    card_id: str,
    is_valid: bool,
    *,
    confidence: float | None = None,
    sources: list[str] | None = None,
) -> None:
    """Log a fact-check result.

    Args:
        job_id: Job identifier for correlation
        card_id: Card being fact-checked
        is_valid: Whether the card passed fact-check
        confidence: Optional confidence score
        sources: Optional list of source URLs
    """
    logger.info(
        "Fact-check completed",
        event="factcheck.result",
        job_id=job_id,
        card_id=card_id,
        is_valid=is_valid,
        confidence=confidence,
        sources_count=len(sources) if sources else 0,
    )
