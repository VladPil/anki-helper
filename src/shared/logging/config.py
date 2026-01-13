"""AnkiRAG - Logger Configuration.

Loguru-based structured logging configuration.
Based on Wiki-Engine patterns for observability.

This module configures a unified logger for the application:
- Loguru for application logs (pretty format, colors, structured data)
- Intercept handler for third-party library logs (uvicorn, fastapi, asyncpg)
- OpenTelemetry integration for trace correlation
"""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from src.core.config import Settings

# Default trace/span IDs when no active trace
NO_TRACE = "0" * 32
NO_SPAN = "0" * 16

# Sensitive field patterns for redaction
SENSITIVE_PATTERNS = re.compile(
    r"(password|token|secret|key|auth|credential|api_key|access_token|refresh_token)",
    re.IGNORECASE,
)

# Cache for settings to avoid repeated imports
_settings_cache: Settings | None = None


def _get_settings() -> Settings:
    """Get settings lazily to avoid circular imports."""
    global _settings_cache
    if _settings_cache is None:
        from src.core.config import settings
        _settings_cache = settings
    return _settings_cache


class InterceptHandler(logging.Handler):
    """Handler for intercepting standard logging and redirecting to Loguru.

    Many libraries (uvicorn, fastapi, sqlalchemy) use standard logging module.
    To have all logs in unified Loguru format, we intercept them through this handler.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Process a single log record from standard logging.

        This method is called automatically for each log from libraries
        using standard logging (e.g., uvicorn.info("Starting server")).

        Algorithm:
        1. Get log level (INFO, ERROR, etc.) from record
        2. Determine stack depth for correct file/line display
        3. Redirect log to Loguru with preserved context information

        Args:
            record: Log record from standard logging with all information
                   (level, message, file, line, exception, etc.)
        """
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        frame = logging.currentframe()
        depth = 2  # Minimum depth (usually sufficient)

        if frame:
            while frame.f_code.co_filename == logging.__file__:
                if frame.f_back:
                    frame = frame.f_back
                    depth += 1  # Increase depth for each logging frame
                else:
                    break

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _otel_patcher(record: dict[str, Any]) -> None:
    """Patcher for adding trace_id from OpenTelemetry to Loguru.

    This function is called for every log record to inject
    OpenTelemetry trace context for log correlation.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()

        if span == trace.INVALID_SPAN:
            record["extra"]["trace_id"] = NO_TRACE
            record["extra"]["span_id"] = NO_SPAN
        else:
            ctx = span.get_span_context()
            record["extra"]["trace_id"] = trace.format_trace_id(ctx.trace_id)
            record["extra"]["span_id"] = trace.format_span_id(ctx.span_id)
    except ImportError:
        # OpenTelemetry not installed, use defaults
        record["extra"]["trace_id"] = NO_TRACE
        record["extra"]["span_id"] = NO_SPAN


def _redact_sensitive_value(key: str, value: Any) -> Any:
    """Redact sensitive values based on key name.

    Args:
        key: The field name
        value: The field value

    Returns:
        Redacted value if sensitive, original value otherwise
    """
    if SENSITIVE_PATTERNS.search(key):
        return "***REDACTED***"
    return value


def _create_json_formatter(service_name: str) -> Any:
    """Create a JSON formatter closure with the service name.

    Args:
        service_name: Name of the service for log entries

    Returns:
        Formatter function for Loguru
    """
    def json_formatter(record: dict[str, Any]) -> str:
        """JSON formatter for production logging.

        Creates structured JSON log entries with automatic
        redaction of sensitive fields.

        Args:
            record: Loguru log record

        Returns:
            JSON-formatted log string with newline
        """
        log_entry: dict[str, Any] = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record.get("name", ""),
            "function": record["function"],
            "line": record["line"],
            "trace_id": record["extra"].get("trace_id", NO_TRACE),
            "span_id": record["extra"].get("span_id", NO_SPAN),
            "service": service_name,
        }

        # Add optional fields if present
        if "request_id" in record["extra"]:
            log_entry["request_id"] = record["extra"]["request_id"]

        if "user_id" in record["extra"]:
            log_entry["user_id"] = record["extra"]["user_id"]

        # Add extra fields from context (excluding known fields)
        excluded_keys = {"trace_id", "span_id", "request_id", "user_id", "name"}
        for key, value in record["extra"].items():
            if key not in excluded_keys:
                # Redact sensitive fields
                log_entry[key] = _redact_sensitive_value(key, value)

        # Add exception info if present
        if record.get("exception"):
            exc = record["exception"]
            log_entry["exception"] = {
                "type": exc.type.__name__ if exc.type else None,
                "value": str(exc.value) if exc.value else None,
                "traceback": (
                    "".join(str(tb) for tb in exc.traceback) if exc.traceback else None
                ),
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str) + "\n"

    return json_formatter


# Default JSON formatter for backwards compatibility
def json_formatter(record: dict[str, Any]) -> str:
    """JSON formatter for production logging (uses lazy settings).

    Creates structured JSON log entries with automatic
    redaction of sensitive fields.

    Args:
        record: Loguru log record

    Returns:
        JSON-formatted log string with newline
    """
    settings = _get_settings()
    formatter = _create_json_formatter(settings.app.name)
    return formatter(record)


def _create_json_sink(service_name: str) -> Any:
    """Create a JSON sink for stdout logging.

    Args:
        service_name: Name of the service for log entries

    Returns:
        Sink function for Loguru
    """
    def json_sink(message: Any) -> None:
        """Write JSON formatted log to stdout."""
        record = message.record
        log_entry: dict[str, Any] = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["extra"].get("name", record["name"]),
            "function": record["function"],
            "line": record["line"],
            "trace_id": record["extra"].get("trace_id", NO_TRACE),
            "span_id": record["extra"].get("span_id", NO_SPAN),
            "service": service_name,
        }

        # Add optional fields if present
        if "request_id" in record["extra"]:
            log_entry["request_id"] = record["extra"]["request_id"]

        if "user_id" in record["extra"]:
            log_entry["user_id"] = record["extra"]["user_id"]

        # Add extra fields from context (excluding known fields)
        excluded_keys = {"trace_id", "span_id", "request_id", "user_id", "name"}
        for key, value in record["extra"].items():
            if key not in excluded_keys:
                # Redact sensitive fields
                log_entry[key] = _redact_sensitive_value(key, value)

        # Add exception info if present
        if record.get("exception"):
            exc = record["exception"]
            log_entry["exception"] = {
                "type": exc.type.__name__ if exc.type else None,
                "value": str(exc.value) if exc.value else None,
                "traceback": (
                    "".join(str(tb) for tb in exc.traceback) if exc.traceback else None
                ),
            }

        sys.stdout.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()

    return json_sink


def _create_loki_sink(url: str, service_name: str, is_debug: bool) -> Any:
    """Create a Loki sink for log shipping.

    Args:
        url: Loki push URL
        service_name: Name of the service
        is_debug: Whether we're in debug mode

    Returns:
        Sink function for Loguru
    """
    import httpx

    loki_url = url.rstrip("/") + "/loki/api/v1/push"

    def loki_sink(message: str) -> None:
        """Send log message to Loki."""
        try:
            record = message.record
            labels = {
                "service": service_name,
                "level": record["level"].name.lower(),
                "env": "development" if is_debug else "production",
            }

            # Timestamp in nanoseconds
            timestamp_ns = str(int(record["time"].timestamp() * 1e9))

            payload = {
                "streams": [
                    {
                        "stream": labels,
                        "values": [[timestamp_ns, str(message)]],
                    }
                ]
            }

            with httpx.Client(timeout=5.0) as client:
                client.post(
                    loki_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
        except Exception:
            pass  # Don't fail on log shipping errors

    return loki_sink


def setup_logger() -> None:
    """Configure Loguru logger.

    Sets up:
    - Console handler with colored output (dev) or JSON format (prod)
    - OpenTelemetry trace correlation
    - Third-party library log interception
    - Optional Loki integration for log aggregation
    - Thread-safe async logging with enqueue=True
    """
    settings = _get_settings()

    # Remove default handler
    logger.remove()

    # Configure OpenTelemetry patcher for trace correlation
    logger.configure(patcher=_otel_patcher)

    # Determine if we're in production
    is_prod = settings.logging.format.lower() == "json"

    if is_prod:
        # JSON format for production (structured logging)
        logger.add(
            _create_json_sink(settings.app.name),
            level=settings.logging.level.upper(),
            backtrace=True,
            diagnose=False,  # Don't expose internal state in production
            enqueue=True,  # Thread-safe async logging
        )
    else:
        # Human-readable format for development
        dev_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level> | "
            "<dim>trace_id={extra[trace_id]}</dim>"
        )
        logger.add(
            sys.stdout,
            format=dev_format,
            level=settings.logging.level.upper(),
            colorize=True,
            backtrace=True,
            diagnose=settings.app.debug,
            enqueue=True,  # Thread-safe async logging
        )

    # Add Loki handler if enabled
    if settings.logging.loki_enabled and settings.logging.loki_url:
        logger.add(
            _create_loki_sink(
                settings.logging.loki_url,
                settings.app.name,
                settings.app.debug,
            ),
            level=settings.logging.level.upper(),
            enqueue=True,
        )

    # Configure third-party loggers
    configure_third_party_loggers()

    logger.info(
        "Logger configured",
        level=settings.logging.level,
        format="json" if is_prod else "console",
        loki_enabled=settings.logging.loki_enabled,
    )


def configure_third_party_loggers() -> None:
    """Configure logging for third-party libraries.

    This function:
    1. Intercepts logs from libraries (uvicorn, fastapi, asyncpg, sqlalchemy)
    2. Redirects them to Loguru for unified format
    3. Sets log levels (to avoid log spam)

    Why this is needed:
    - Libraries use standard logging, we use Loguru
    - Want to see ALL logs in one beautiful Loguru format
    - Need to control verbosity (e.g., asyncpg is very chatty at DEBUG)
    """
    settings = _get_settings()

    logging.root.handlers = []
    logging.root.setLevel(logging.INFO)

    loggers_to_configure = [
        "",  # root logger
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "asyncpg",
        "sqlalchemy",
        "sqlalchemy.engine",
        "httpx",
        "httpcore",
        "redis",
    ]

    is_prod = settings.logging.format.lower() == "json"

    for logger_name in loggers_to_configure:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers.clear()
        logging_logger.addHandler(InterceptHandler())
        logging_logger.propagate = False

        # Set appropriate levels for different loggers
        if logger_name in ["uvicorn.access", "asyncpg"]:
            logging_logger.setLevel(logging.WARNING if is_prod else logging.INFO)
        elif logger_name in ["sqlalchemy", "sqlalchemy.engine"]:
            logging_logger.setLevel(logging.WARNING)
        elif logger_name in ["httpx", "httpcore"]:
            logging_logger.setLevel(logging.WARNING)
        else:
            logging_logger.setLevel(logging.INFO)

    logger.debug("Third-party loggers configured")


def get_logger(name: str):
    """Get a logger with the specified name.

    Args:
        name: Logger name (usually __name__ of the module)

    Returns:
        Configured Loguru logger with bound name
    """
    return logger.bind(name=name)
