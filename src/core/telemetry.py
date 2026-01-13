"""
OpenTelemetry setup with auto-instrumentation.

Simplified telemetry module based on Wiki-Engine patterns.
Uses NoOpSpanExporter when telemetry is disabled to avoid if-checks.
"""

from collections.abc import Callable, Sequence
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, Status, StatusCode

from src.core.config import settings
from src.core.database import db_manager
from src.shared.context import trace_id_var

# Excluded URLs for FastAPI instrumentation (health checks, metrics)
EXCLUDED_URLS = (
    "observability/health,"
    "observability/ready,"
    "observability/live,"
    "observability/metrics,"
    "health,healthz,ready,readyz,metrics"
)


class NoOpSpanExporter(SpanExporter):
    """No-op exporter that does nothing but allows spans to be recorded.

    This enables trace_id generation even when telemetry export is disabled.
    """

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def setup_telemetry(app: FastAPI) -> None:
    """Setup OpenTelemetry with auto-instrumentation for FastAPI app.

    This function configures tracing with either OTLP exporter (for production)
    or NoOp exporter (for development/when disabled). Auto-instruments:
    - FastAPI requests
    - SQLAlchemy queries
    - Redis operations
    - HTTPX client requests

    Args:
        app: FastAPI application instance.
    """
    if not settings.telemetry.enabled:
        return

    resource = Resource.create(
        attributes={
            "service.name": settings.telemetry.service_name,
            "service.version": "1.0.0",
            "deployment.environment": "development" if settings.app.debug else "production",
        }
    )

    # Setup TracerProvider
    tracer_provider = TracerProvider(resource=resource)

    # Configure exporter based on environment
    if settings.telemetry.exporter_otlp_endpoint:
        span_exporter = OTLPSpanExporter(
            endpoint=settings.telemetry.exporter_otlp_endpoint,
            insecure=True,
        )
    else:
        # NoOp exporter allows trace_id generation without output
        span_exporter = NoOpSpanExporter()

    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        excluded_urls=EXCLUDED_URLS,
    )

    # Auto-instrument SQLAlchemy (if database is initialized)
    try:
        engine = db_manager.engine
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine,
            tracer_provider=tracer_provider,
        )
    except RuntimeError:
        # Database not initialized yet, will be instrumented later if needed
        pass

    # Auto-instrument Redis
    RedisInstrumentor().instrument(tracer_provider=tracer_provider)

    # Auto-instrument HTTPX
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)


def instrument_sqlalchemy_engine(engine: Any) -> None:
    """Instrument SQLAlchemy engine after it's initialized.

    Call this after database initialization if setup_telemetry was called
    before db_manager.init().

    Args:
        engine: AsyncEngine instance from SQLAlchemy.
    """
    if not settings.telemetry.enabled:
        return

    tracer_provider = trace.get_tracer_provider()
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        tracer_provider=tracer_provider,
    )


# ==================== Span Helpers ====================
# These functions are kept for backward compatibility


def get_current_span() -> Span | None:
    """Get current span from OpenTelemetry context.

    Returns:
        Current span or None if not in a traced context.
    """
    span = trace.get_current_span()
    # INVALID_SPAN has trace_id of 0
    if span.get_span_context().trace_id == 0:
        return None
    return span


def get_trace_id() -> str | None:
    """Get trace ID of current span.

    Returns:
        Trace ID as hex string or None if not in a traced context.
    """
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None

    trace_id = format(context.trace_id, "032x")
    # Update context variable for use in logging
    trace_id_var.set(trace_id)
    return trace_id


def get_span_id() -> str | None:
    """Get span ID of current span.

    Returns:
        Span ID as hex string or None if not in a traced context.
    """
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return None

    return format(context.span_id, "016x")


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the current span.

    Args:
        **attributes: Key-value pairs to add as span attributes.
    """
    span = trace.get_current_span()
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current span.

    Args:
        name: Event name.
        attributes: Optional event attributes.
    """
    span = trace.get_current_span()
    span.add_event(name, attributes=attributes)


def set_span_status(status: StatusCode, description: str | None = None) -> None:
    """Set status on the current span.

    Args:
        status: Status code (OK, ERROR, UNSET).
        description: Optional status description.
    """
    span = trace.get_current_span()
    span.set_status(Status(status, description))


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span.

    Args:
        exception: Exception to record.
    """
    span = trace.get_current_span()
    span.record_exception(exception)
    span.set_status(Status(StatusCode.ERROR, str(exception)))


# ==================== Backward Compatibility ====================
# These are kept for code that imports from the old module


class TelemetryManager:
    """Deprecated: Use setup_telemetry() instead.

    This class is kept for backward compatibility only.
    """

    _instance: "TelemetryManager | None" = None
    _initialized: bool = False

    def __new__(cls) -> "TelemetryManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def tracer(self):
        """Get tracer instance."""
        return trace.get_tracer(settings.telemetry.service_name, "1.0.0")

    @property
    def is_enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return settings.telemetry.enabled

    def init(self) -> None:
        """No-op for backward compatibility."""
        pass

    def instrument_app(self, app: Any) -> None:
        """No-op - use setup_telemetry() instead."""
        pass

    def instrument_sqlalchemy(self, engine: Any) -> None:
        """No-op - auto-instrumented by setup_telemetry()."""
        pass

    def instrument_redis(self) -> None:
        """No-op - auto-instrumented by setup_telemetry()."""
        pass

    def instrument_httpx(self) -> None:
        """No-op - auto-instrumented by setup_telemetry()."""
        pass

    def shutdown(self) -> None:
        """Shutdown tracer provider."""
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()


# Global instance for backward compatibility
telemetry_manager = TelemetryManager()


def init_telemetry() -> None:
    """Deprecated: Use setup_telemetry() instead."""
    pass


def shutdown_telemetry() -> None:
    """Shutdown telemetry."""
    telemetry_manager.shutdown()


# SpanContext kept for backward compatibility
class SpanContext:
    """Context manager for creating spans.

    Kept for backward compatibility with code using manual span creation.
    Prefer auto-instrumentation when possible.
    """

    def __init__(
        self,
        name: str,
        kind: Any = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        from opentelemetry.trace import SpanKind

        self.name = name
        self.kind = kind or SpanKind.INTERNAL
        self.attributes = attributes
        self._span: Any = None
        self._token: Any = None

    def __enter__(self) -> Span | None:
        if not settings.telemetry.enabled:
            return None

        tracer = trace.get_tracer(settings.telemetry.service_name, "1.0.0")
        self._span = tracer.start_span(
            self.name,
            kind=self.kind,
            attributes=self.attributes,
        )
        self._token = trace.use_span(self._span, end_on_exit=False).__enter__()
        return self._span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._span is None:
            return

        if exc_val is not None:
            self._span.record_exception(exc_val)
            self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))

        self._span.end()

        if self._token is not None:
            trace.use_span(self._span, end_on_exit=False).__exit__(exc_type, exc_val, exc_tb)

    async def __aenter__(self) -> Span | None:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)


_TracedP = ParamSpec("_TracedP")
_TracedR = TypeVar("_TracedR")


# traced decorator kept for backward compatibility but now optional
def traced(
    name: str | None = None,
    kind: Any = None,
    attributes: dict[str, Any] | None = None,
):
    """Decorator for tracing functions.

    Note: With auto-instrumentation, this decorator is often not needed.
    FastAPI endpoints, SQLAlchemy queries, Redis operations, and HTTPX
    requests are automatically traced.

    Args:
        name: Span name (defaults to function qualified name).
        kind: Span kind (default: INTERNAL).
        attributes: Additional span attributes.

    Returns:
        Decorated function.
    """
    from opentelemetry.trace import SpanKind

    def decorator(func: Callable[_TracedP, _TracedR]) -> Callable[_TracedP, _TracedR]:
        span_name = name or f"{func.__module__}.{func.__qualname__}"
        span_kind = kind or SpanKind.INTERNAL

        @wraps(func)
        async def async_wrapper(*args: _TracedP.args, **kwargs: _TracedP.kwargs) -> _TracedR:
            if not settings.telemetry.enabled:
                return await func(*args, **kwargs)  # type: ignore[misc, no-any-return]

            tracer = trace.get_tracer(settings.telemetry.service_name, "1.0.0")
            with tracer.start_as_current_span(
                span_name,
                kind=span_kind,
                attributes=attributes,
            ) as span:
                try:
                    result = await func(*args, **kwargs)  # type: ignore[misc]
                    return result  # type: ignore[no-any-return]
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        @wraps(func)
        def sync_wrapper(*args: _TracedP.args, **kwargs: _TracedP.kwargs) -> _TracedR:
            if not settings.telemetry.enabled:
                return func(*args, **kwargs)

            tracer = trace.get_tracer(settings.telemetry.service_name, "1.0.0")
            with tracer.start_as_current_span(
                span_name,
                kind=span_kind,
                attributes=attributes,
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator
