"""AnkiRAG - Shared Logging Configuration.

Loguru-based logging module with:
- Structured JSON logging for production
- Colored console output for development
- OpenTelemetry trace correlation
- Automatic sensitive data redaction
- Optional Loki integration
"""

from loguru import logger

from .config import (
    InterceptHandler,
    configure_third_party_loggers,
    get_logger,
    json_formatter,
    setup_logger,
)
from .event_logger import (
    log_embedding_request,
    log_fact_check_result,
    log_generation_completed,
    log_generation_failed,
    log_generation_progress,
    log_generation_started,
    log_llm_request,
    log_llm_response,
)

__all__ = [
    # Core logging
    "logger",
    "setup_logger",
    "get_logger",
    "json_formatter",
    "InterceptHandler",
    "configure_third_party_loggers",
    # Event logging
    "log_generation_started",
    "log_generation_completed",
    "log_generation_failed",
    "log_generation_progress",
    "log_llm_request",
    "log_llm_response",
    "log_embedding_request",
    "log_fact_check_result",
]
