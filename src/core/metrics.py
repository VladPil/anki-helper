"""
Prometheus метрики для мониторинга приложения.
"""

from collections.abc import Callable
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    multiprocess,
)

from .config import settings

# ==================== Type Variables ====================

P = ParamSpec("P")
R = TypeVar("R")


# ==================== Registry ====================


def create_registry() -> CollectorRegistry:
    """Создать registry для метрик."""
    registry = CollectorRegistry(auto_describe=True)

    # Для multiprocess режима (gunicorn с несколькими воркерами)
    try:
        multiprocess.MultiProcessCollector(registry)
    except ValueError:
        # Не в multiprocess режиме
        pass

    return registry


# Глобальный registry
REGISTRY = create_registry()


# ==================== Application Info ====================

APP_INFO = Info(
    "ankirag_app",
    "Application information",
    registry=REGISTRY,
)


# ==================== HTTP Metrics ====================

HTTP_REQUEST_COUNT = Counter(
    "ankirag_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

HTTP_REQUEST_LATENCY = Histogram(
    "ankirag_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
    registry=REGISTRY,
)

HTTP_REQUEST_IN_PROGRESS = Gauge(
    "ankirag_http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "endpoint"],
    registry=REGISTRY,
)

HTTP_REQUEST_SIZE_BYTES = Histogram(
    "ankirag_http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000),
    registry=REGISTRY,
)

HTTP_RESPONSE_SIZE_BYTES = Histogram(
    "ankirag_http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=(100, 1000, 10000, 100000, 1000000, 10000000),
    registry=REGISTRY,
)


# ==================== Database Metrics ====================

DB_CONNECTION_POOL_SIZE = Gauge(
    "ankirag_db_connection_pool_size",
    "Database connection pool size",
    registry=REGISTRY,
)

DB_CONNECTION_POOL_CHECKED_OUT = Gauge(
    "ankirag_db_connection_pool_checked_out",
    "Number of connections currently checked out from pool",
    registry=REGISTRY,
)

DB_CONNECTION_POOL_OVERFLOW = Gauge(
    "ankirag_db_connection_pool_overflow",
    "Current overflow count for connection pool",
    registry=REGISTRY,
)

DB_QUERY_COUNT = Counter(
    "ankirag_db_queries_total",
    "Total database queries",
    ["operation"],
    registry=REGISTRY,
)

DB_QUERY_LATENCY = Histogram(
    "ankirag_db_query_duration_seconds",
    "Database query latency in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
    registry=REGISTRY,
)

DB_QUERY_ERRORS = Counter(
    "ankirag_db_query_errors_total",
    "Total database query errors",
    ["operation", "error_type"],
    registry=REGISTRY,
)


# ==================== Redis Metrics ====================

REDIS_OPERATION_COUNT = Counter(
    "ankirag_redis_operations_total",
    "Total Redis operations",
    ["operation", "status"],
    registry=REGISTRY,
)

REDIS_OPERATION_LATENCY = Histogram(
    "ankirag_redis_operation_duration_seconds",
    "Redis operation latency in seconds",
    ["operation"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1),
    registry=REGISTRY,
)

REDIS_CONNECTION_POOL_SIZE = Gauge(
    "ankirag_redis_connection_pool_size",
    "Redis connection pool size",
    registry=REGISTRY,
)


# ==================== Authentication Metrics ====================

AUTH_ATTEMPTS_TOTAL = Counter(
    "ankirag_auth_attempts_total",
    "Total authentication attempts",
    ["result"],
    registry=REGISTRY,
)

AUTH_TOKEN_OPERATIONS = Counter(
    "ankirag_auth_token_operations_total",
    "Total token operations",
    ["operation", "status"],
    registry=REGISTRY,
)

ACTIVE_SESSIONS = Gauge(
    "ankirag_active_sessions",
    "Number of active user sessions",
    registry=REGISTRY,
)


# ==================== LLM Metrics ====================

LLM_REQUEST_COUNT = Counter(
    "ankirag_llm_requests_total",
    "Total LLM requests",
    ["provider", "model", "status"],
    registry=REGISTRY,
)

LLM_TOKEN_COUNT = Counter(
    "ankirag_llm_tokens_total",
    "Total LLM tokens used",
    ["provider", "model", "direction"],
    registry=REGISTRY,
)

LLM_LATENCY = Histogram(
    "ankirag_llm_request_duration_seconds",
    "LLM request latency in seconds",
    ["provider", "model"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

LLM_COST = Counter(
    "ankirag_llm_cost_total",
    "Total LLM cost in USD (estimated)",
    ["provider", "model"],
    registry=REGISTRY,
)


# ==================== Embedding Metrics ====================

EMBEDDING_REQUEST_COUNT = Counter(
    "ankirag_embedding_requests_total",
    "Total embedding requests",
    ["provider", "model", "status"],
    registry=REGISTRY,
)

EMBEDDING_LATENCY = Histogram(
    "ankirag_embedding_request_duration_seconds",
    "Embedding request latency in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

EMBEDDING_BATCH_SIZE = Histogram(
    "ankirag_embedding_batch_size",
    "Embedding batch size",
    ["provider", "model"],
    buckets=(1, 5, 10, 25, 50, 100, 250, 500),
    registry=REGISTRY,
)

EMBEDDING_DIMENSION = Gauge(
    "ankirag_embedding_dimension",
    "Embedding dimension",
    ["provider", "model"],
    registry=REGISTRY,
)


# ==================== Vector Search Metrics ====================

VECTOR_SEARCH_COUNT = Counter(
    "ankirag_vector_search_total",
    "Total vector search requests",
    ["status"],
    registry=REGISTRY,
)

VECTOR_SEARCH_LATENCY = Histogram(
    "ankirag_vector_search_duration_seconds",
    "Vector search latency in seconds",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
    registry=REGISTRY,
)

VECTOR_SEARCH_RESULTS = Histogram(
    "ankirag_vector_search_results_count",
    "Number of results returned by vector search",
    buckets=(0, 1, 5, 10, 25, 50, 100),
    registry=REGISTRY,
)


# ==================== Card Generation Metrics ====================

CARD_GENERATION_COUNT = Counter(
    "ankirag_card_generation_total",
    "Total card generation requests",
    ["status", "workflow", "source"],
    registry=REGISTRY,
)

CARD_GENERATION_LATENCY = Histogram(
    "ankirag_card_generation_duration_seconds",
    "Card generation latency in seconds",
    ["workflow"],
    buckets=(1.0, 2.5, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0, 300.0),
    registry=REGISTRY,
)

CARDS_GENERATED = Counter(
    "ankirag_cards_generated_total",
    "Total number of cards generated",
    ["deck", "card_type"],
    registry=REGISTRY,
)

CARDS_REJECTED = Counter(
    "ankirag_cards_rejected_total",
    "Total number of cards rejected during generation",
    ["reason"],
    registry=REGISTRY,
)


# ==================== Fact Checking Metrics ====================

FACT_CHECK_COUNT = Counter(
    "ankirag_fact_check_total",
    "Total fact check requests",
    ["status"],
    registry=REGISTRY,
)

FACT_CHECK_LATENCY = Histogram(
    "ankirag_fact_check_duration_seconds",
    "Fact check latency in seconds",
    buckets=(1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

FACT_CHECK_CONFIDENCE = Histogram(
    "ankirag_fact_check_confidence",
    "Fact check confidence scores",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=REGISTRY,
)

FACT_CHECK_VERDICT = Counter(
    "ankirag_fact_check_verdict_total",
    "Total fact check verdicts by type",
    ["verdict"],
    registry=REGISTRY,
)


# ==================== Anki Sync Metrics ====================

ANKI_SYNC_COUNT = Counter(
    "ankirag_anki_sync_total",
    "Total Anki sync operations",
    ["status"],
    registry=REGISTRY,
)

ANKI_SYNC_LATENCY = Histogram(
    "ankirag_anki_sync_duration_seconds",
    "Anki sync latency in seconds",
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

ANKI_CARDS_SYNCED = Counter(
    "ankirag_anki_cards_synced_total",
    "Total cards synced to Anki",
    ["operation"],
    registry=REGISTRY,
)

ANKI_CONNECTION_STATUS = Gauge(
    "ankirag_anki_connection_status",
    "Anki connection status (1=connected, 0=disconnected)",
    registry=REGISTRY,
)


# ==================== Document Processing Metrics ====================

DOCUMENT_UPLOAD_COUNT = Counter(
    "ankirag_document_uploads_total",
    "Total document uploads",
    ["status", "file_type"],
    registry=REGISTRY,
)

DOCUMENT_PROCESSING_LATENCY = Histogram(
    "ankirag_document_processing_duration_seconds",
    "Document processing latency in seconds",
    ["file_type"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=REGISTRY,
)

DOCUMENT_SIZE_BYTES = Histogram(
    "ankirag_document_size_bytes",
    "Document size in bytes",
    ["file_type"],
    buckets=(1000, 10000, 100000, 1000000, 10000000, 100000000),
    registry=REGISTRY,
)

DOCUMENT_CHUNKS_COUNT = Histogram(
    "ankirag_document_chunks_count",
    "Number of chunks extracted from documents",
    buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000),
    registry=REGISTRY,
)


# ==================== Background Job Metrics ====================

JOB_COUNT = Counter(
    "ankirag_jobs_total",
    "Total background jobs",
    ["job_type", "status"],
    registry=REGISTRY,
)

JOB_LATENCY = Histogram(
    "ankirag_job_duration_seconds",
    "Background job latency in seconds",
    ["job_type"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0),
    registry=REGISTRY,
)

JOBS_IN_PROGRESS = Gauge(
    "ankirag_jobs_in_progress",
    "Number of jobs currently in progress",
    ["job_type"],
    registry=REGISTRY,
)

JOB_QUEUE_SIZE = Gauge(
    "ankirag_job_queue_size",
    "Number of jobs waiting in queue",
    ["job_type"],
    registry=REGISTRY,
)


# ==================== Helper Functions ====================


def record_http_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float,
    request_size: int = 0,
    response_size: int = 0,
) -> None:
    """Записать метрики HTTP запроса."""
    HTTP_REQUEST_COUNT.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()

    HTTP_REQUEST_LATENCY.labels(
        method=method,
        endpoint=endpoint,
    ).observe(duration)

    if request_size > 0:
        HTTP_REQUEST_SIZE_BYTES.labels(method=method, endpoint=endpoint).observe(request_size)

    if response_size > 0:
        HTTP_RESPONSE_SIZE_BYTES.labels(method=method, endpoint=endpoint).observe(response_size)


def record_db_query(operation: str, duration: float) -> None:
    """Записать метрики запроса к БД."""
    DB_QUERY_COUNT.labels(operation=operation).inc()
    DB_QUERY_LATENCY.labels(operation=operation).observe(duration)


def record_db_error(operation: str, error_type: str) -> None:
    """Записать ошибку запроса к БД."""
    DB_QUERY_ERRORS.labels(operation=operation, error_type=error_type).inc()


def update_db_pool_metrics(pool_size: int, checked_out: int, overflow: int = 0) -> None:
    """Обновить метрики пула соединений БД."""
    DB_CONNECTION_POOL_SIZE.set(pool_size)
    DB_CONNECTION_POOL_CHECKED_OUT.set(checked_out)
    DB_CONNECTION_POOL_OVERFLOW.set(overflow)


def record_redis_operation(operation: str, duration: float, status: str = "success") -> None:
    """Записать метрики операции Redis."""
    REDIS_OPERATION_COUNT.labels(operation=operation, status=status).inc()
    REDIS_OPERATION_LATENCY.labels(operation=operation).observe(duration)


def record_auth_attempt(result: str) -> None:
    """Записать попытку аутентификации."""
    AUTH_ATTEMPTS_TOTAL.labels(result=result).inc()


def record_token_operation(operation: str, status: str = "success") -> None:
    """Записать операцию с токеном."""
    AUTH_TOKEN_OPERATIONS.labels(operation=operation, status=status).inc()


def update_active_sessions(count: int) -> None:
    """Обновить количество активных сессий."""
    ACTIVE_SESSIONS.set(count)


def record_llm_request(
    provider: str,
    model: str,
    status: str,
    duration: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float = 0.0,
) -> None:
    """Записать метрики LLM запроса."""
    LLM_REQUEST_COUNT.labels(provider=provider, model=model, status=status).inc()
    LLM_LATENCY.labels(provider=provider, model=model).observe(duration)

    if input_tokens > 0:
        LLM_TOKEN_COUNT.labels(provider=provider, model=model, direction="input").inc(input_tokens)
    if output_tokens > 0:
        LLM_TOKEN_COUNT.labels(provider=provider, model=model, direction="output").inc(
            output_tokens
        )
    if cost > 0:
        LLM_COST.labels(provider=provider, model=model).inc(cost)


def record_embedding_request(
    provider: str,
    model: str,
    status: str,
    duration: float,
    batch_size: int = 1,
) -> None:
    """Записать метрики запроса эмбеддингов."""
    EMBEDDING_REQUEST_COUNT.labels(provider=provider, model=model, status=status).inc()
    EMBEDDING_LATENCY.labels(provider=provider, model=model).observe(duration)
    EMBEDDING_BATCH_SIZE.labels(provider=provider, model=model).observe(batch_size)


def record_vector_search(status: str, duration: float, results_count: int) -> None:
    """Записать метрики векторного поиска."""
    VECTOR_SEARCH_COUNT.labels(status=status).inc()
    VECTOR_SEARCH_LATENCY.observe(duration)
    VECTOR_SEARCH_RESULTS.observe(results_count)


def record_card_generation(
    workflow: str,
    status: str,
    duration: float,
    source: str = "unknown",
    cards_count: int = 0,
    deck: str = "default",
    card_type: str = "basic",
) -> None:
    """Записать метрики генерации карточек."""
    CARD_GENERATION_COUNT.labels(status=status, workflow=workflow, source=source).inc()
    CARD_GENERATION_LATENCY.labels(workflow=workflow).observe(duration)

    if cards_count > 0:
        CARDS_GENERATED.labels(deck=deck, card_type=card_type).inc(cards_count)


def record_card_rejection(reason: str, count: int = 1) -> None:
    """Записать отклонение карточки."""
    CARDS_REJECTED.labels(reason=reason).inc(count)


def record_fact_check(status: str, duration: float, confidence: float, verdict: str) -> None:
    """Записать метрики проверки фактов."""
    FACT_CHECK_COUNT.labels(status=status).inc()
    FACT_CHECK_LATENCY.observe(duration)
    FACT_CHECK_CONFIDENCE.observe(confidence)
    FACT_CHECK_VERDICT.labels(verdict=verdict).inc()


def record_anki_sync(
    status: str,
    duration: float,
    cards_created: int = 0,
    cards_updated: int = 0,
    cards_deleted: int = 0,
) -> None:
    """Записать метрики синхронизации с Anki."""
    ANKI_SYNC_COUNT.labels(status=status).inc()
    ANKI_SYNC_LATENCY.observe(duration)

    if cards_created > 0:
        ANKI_CARDS_SYNCED.labels(operation="create").inc(cards_created)
    if cards_updated > 0:
        ANKI_CARDS_SYNCED.labels(operation="update").inc(cards_updated)
    if cards_deleted > 0:
        ANKI_CARDS_SYNCED.labels(operation="delete").inc(cards_deleted)


def update_anki_connection_status(connected: bool) -> None:
    """Обновить статус подключения к Anki."""
    ANKI_CONNECTION_STATUS.set(1 if connected else 0)


def record_document_upload(
    status: str,
    file_type: str,
    size_bytes: int,
    processing_duration: float = 0,
    chunks_count: int = 0,
) -> None:
    """Записать метрики загрузки документа."""
    DOCUMENT_UPLOAD_COUNT.labels(status=status, file_type=file_type).inc()
    DOCUMENT_SIZE_BYTES.labels(file_type=file_type).observe(size_bytes)

    if processing_duration > 0:
        DOCUMENT_PROCESSING_LATENCY.labels(file_type=file_type).observe(processing_duration)

    if chunks_count > 0:
        DOCUMENT_CHUNKS_COUNT.observe(chunks_count)


def record_job(job_type: str, status: str, duration: float) -> None:
    """Записать метрики фоновой задачи."""
    JOB_COUNT.labels(job_type=job_type, status=status).inc()
    JOB_LATENCY.labels(job_type=job_type).observe(duration)


def update_jobs_in_progress(job_type: str, count: int) -> None:
    """Обновить количество выполняемых задач."""
    JOBS_IN_PROGRESS.labels(job_type=job_type).set(count)


def update_job_queue_size(job_type: str, size: int) -> None:
    """Обновить размер очереди задач."""
    JOB_QUEUE_SIZE.labels(job_type=job_type).set(size)


# ==================== Decorators ====================


def timed(
    metric: Histogram,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор для измерения времени выполнения функции.

    Args:
        metric: Histogram метрика.
        labels: Метки для метрики.

    Usage:
        @timed(DB_QUERY_LATENCY, {"operation": "select_users"})
        async def get_users():
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = perf_counter()
            try:
                return await func(*args, **kwargs)  # type: ignore[misc, no-any-return]
            finally:
                duration = perf_counter() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = perf_counter() - start
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator


def counted(
    metric: Counter,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор для подсчета вызовов функции.

    Args:
        metric: Counter метрика.
        labels: Метки для метрики.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if labels:
                metric.labels(**labels).inc()
            else:
                metric.inc()
            return await func(*args, **kwargs)  # type: ignore[misc, no-any-return]

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if labels:
                metric.labels(**labels).inc()
            else:
                metric.inc()
            return func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator


def in_progress(
    metric: Gauge,
    labels: dict[str, str] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Декоратор для отслеживания количества выполняемых вызовов.

    Args:
        metric: Gauge метрика.
        labels: Метки для метрики.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            gauge = metric.labels(**labels) if labels else metric
            gauge.inc()
            try:
                return await func(*args, **kwargs)  # type: ignore[misc, no-any-return]
            finally:
                gauge.dec()

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            gauge = metric.labels(**labels) if labels else metric
            gauge.inc()
            try:
                return func(*args, **kwargs)
            finally:
                gauge.dec()

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper

    return decorator


# ==================== Metrics Endpoint ====================


def get_metrics() -> tuple[bytes, str]:
    """
    Получить метрики в формате Prometheus.

    Returns:
        Tuple из (содержимое, content-type).
    """
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


async def metrics_endpoint():
    """Endpoint для экспорта метрик."""
    from fastapi.responses import Response

    content, content_type = get_metrics()
    return Response(content=content, media_type=content_type)


# ==================== Initialization ====================


def init_app_info() -> None:
    """Инициализировать информацию о приложении."""
    APP_INFO.info(
        {
            "name": settings.app.name,
            "debug": str(settings.app.debug),
        }
    )


def init_metrics() -> None:
    """Инициализировать метрики при старте приложения."""
    if not settings.metrics.enabled:
        return

    init_app_info()

    # Инициализировать начальные значения gauges
    ANKI_CONNECTION_STATUS.set(0)
    ACTIVE_SESSIONS.set(0)
