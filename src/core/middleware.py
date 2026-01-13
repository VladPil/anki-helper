"""
Middleware для обработки запросов.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import settings
from .logging import clear_request_context, get_structured_logger, set_request_context
from .metrics import (
    HTTP_REQUEST_COUNT,
    HTTP_REQUEST_IN_PROGRESS,
    HTTP_REQUEST_LATENCY,
    HTTP_REQUEST_SIZE_BYTES,
    HTTP_RESPONSE_SIZE_BYTES,
)
from .telemetry import get_span_id, get_trace_id

logger = get_structured_logger(__name__)


# ==================== Request Tracing Middleware ====================


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware для трейсинга и логирования запросов.

    Добавляет request ID ко всем запросам и логирует детали запросов/ответов.
    """

    # Endpoints для пропуска детального логирования
    SKIP_LOG_ENDPOINTS: set[str] = {
        "/observability/health",
        "/observability/ready",
        "/observability/live",
        "/observability/metrics",
        "/health",
        "/healthz",
        "/ready",
        "/readyz",
        "/metrics",
    }

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Обработать запрос с трейсингом и метриками."""
        # Генерация или извлечение request ID
        request_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or str(uuid.uuid4())
        )

        # Сохранение request ID в state запроса
        request.state.request_id = request_id

        # Извлечение user ID если есть (из предыдущего middleware или токена)
        user_id = getattr(request.state, "user_id", None)

        # Получение trace/span IDs из OpenTelemetry
        # Используем request_id как fallback если телеметрия отключена
        trace_id = get_trace_id() or request_id
        span_id = get_span_id()

        # Установка контекста логирования
        set_request_context(
            request_id=request_id,
            user_id=str(user_id) if user_id else None,
            trace_id=trace_id,
            span_id=span_id,
        )

        # Получение endpoint для метрик
        endpoint = self._get_endpoint(request)
        method = request.method

        # Отслеживание in-progress запросов
        HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        # Размер запроса
        request_size = int(request.headers.get("content-length", 0))
        if request_size > 0:
            HTTP_REQUEST_SIZE_BYTES.labels(method=method, endpoint=endpoint).observe(request_size)

        start_time = time.perf_counter()

        try:
            # Обработка запроса
            response = await call_next(request)

            # Вычисление времени
            duration = time.perf_counter() - start_time

            # Запись метрик
            HTTP_REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=response.status_code,
            ).inc()

            HTTP_REQUEST_LATENCY.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            # Размер ответа
            response_size = int(response.headers.get("content-length", 0))
            if response_size > 0:
                HTTP_RESPONSE_SIZE_BYTES.labels(method=method, endpoint=endpoint).observe(
                    response_size
                )

            # Добавление заголовков к ответу
            response.headers["X-Request-ID"] = request_id
            if trace_id:
                response.headers["X-Trace-ID"] = trace_id

            # Логирование запроса
            self._log_request(
                request=request,
                response=response,
                duration=duration,
                request_id=request_id,
            )

            return response

        except Exception as e:
            # Вычисление времени для ошибки
            duration = time.perf_counter() - start_time

            # Запись метрик ошибки
            HTTP_REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=500,
            ).inc()

            HTTP_REQUEST_LATENCY.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            # Логирование ошибки
            logger.error(
                "Request failed",
                request_id=request_id,
                method=method,
                path=str(request.url.path),
                duration_ms=round(duration * 1000, 2),
                error=str(e),
                exc_info=True,
            )

            raise

        finally:
            # Декремент in-progress счетчика
            HTTP_REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

            # Очистка контекста логирования
            clear_request_context()

    def _get_endpoint(self, request: Request) -> str:
        """Получить нормализованный endpoint для метрик.

        Заменяет динамические параметры пути на placeholders.
        """
        # Попытка получить matched route
        if hasattr(request, "scope") and "route" in request.scope:
            route = request.scope["route"]
            if hasattr(route, "path"):
                return route.path

        # Fallback на raw path (не идеально для кардинальности метрик)
        return request.url.path

    def _log_request(
        self,
        request: Request,
        response: Response,
        duration: float,
        request_id: str,
    ) -> None:
        """Логировать детали запроса."""
        # Пропуск логирования для health check endpoints
        if request.url.path in self.SKIP_LOG_ENDPOINTS:
            return

        log_level = "info" if response.status_code < 400 else "warning"
        if response.status_code >= 500:
            log_level = "error"

        log_method = getattr(logger, log_level)
        log_method(
            f"{request.method} {request.url.path}",
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            query_string=str(request.query_params) if request.query_params else None,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
            client_ip=self._get_client_ip(request),
            user_agent=request.headers.get("User-Agent", ""),
            content_type=request.headers.get("Content-Type", ""),
            referer=request.headers.get("Referer", ""),
        )

    def _get_client_ip(self, request: Request) -> str:
        """Извлечь IP клиента из запроса."""
        # Проверка forwarded заголовков (load balancer/proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback на прямой клиент
        if request.client:
            return request.client.host

        return "unknown"


# ==================== Security Headers Middleware ====================


class SecurityHeadersMiddleware:
    """Middleware для добавления заголовков безопасности."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        content_security_policy: str | None = None,
        strict_transport_security: bool = True,
        x_content_type_options: bool = True,
        x_frame_options: str = "DENY",
        x_xss_protection: bool = True,
        referrer_policy: str = "strict-origin-when-cross-origin",
    ) -> None:
        self.app = app
        self.headers: list[tuple[bytes, bytes]] = []

        if content_security_policy:
            self.headers.append((b"content-security-policy", content_security_policy.encode()))

        if strict_transport_security:
            self.headers.append(
                (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
            )

        if x_content_type_options:
            self.headers.append((b"x-content-type-options", b"nosniff"))

        if x_frame_options:
            self.headers.append((b"x-frame-options", x_frame_options.encode()))

        if x_xss_protection:
            self.headers.append((b"x-xss-protection", b"1; mode=block"))

        if referrer_policy:
            self.headers.append((b"referrer-policy", referrer_policy.encode()))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self.headers)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ==================== CORS Middleware ====================


class CORSMiddleware:
    """Custom CORS middleware с большим контролем.

    Note: Для большинства случаев используйте встроенный CORSMiddleware из FastAPI.
    Этот middleware предоставлен для продвинутой кастомизации.
    """

    def __init__(
        self,
        app: ASGIApp,
        allow_origins: list[str],
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        allow_credentials: bool = True,
        expose_headers: list[str] | None = None,
        max_age: int = 600,
    ) -> None:
        self.app = app
        self.allow_origins = set(allow_origins)
        self.allow_all_origins = "*" in allow_origins
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
        self.allow_credentials = allow_credentials
        self.expose_headers = expose_headers or []
        self.max_age = max_age

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = dict(scope.get("headers", []))
        origin = request_headers.get(b"origin", b"").decode()

        # Обработка preflight запросов
        if scope["method"] == "OPTIONS":
            response_headers = self._get_cors_headers(origin)
            response_headers.append((b"content-length", b"0"))

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": response_headers,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"",
                }
            )
            return

        # Добавление CORS заголовков к ответу
        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self._get_cors_headers(origin))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_cors)

    def _get_cors_headers(self, origin: str) -> list[tuple[bytes, bytes]]:
        """Сгенерировать CORS заголовки на основе origin."""
        headers: list[tuple[bytes, bytes]] = []

        if self.allow_all_origins:
            headers.append((b"access-control-allow-origin", b"*"))
        elif origin in self.allow_origins:
            headers.append((b"access-control-allow-origin", origin.encode()))

        if self.allow_credentials and not self.allow_all_origins:
            headers.append((b"access-control-allow-credentials", b"true"))

        headers.append(
            (
                b"access-control-allow-methods",
                ", ".join(self.allow_methods).encode(),
            )
        )

        headers.append(
            (
                b"access-control-allow-headers",
                ", ".join(self.allow_headers).encode(),
            )
        )

        if self.expose_headers:
            headers.append(
                (
                    b"access-control-expose-headers",
                    ", ".join(self.expose_headers).encode(),
                )
            )

        headers.append(
            (
                b"access-control-max-age",
                str(self.max_age).encode(),
            )
        )

        return headers


# ==================== Rate Limiting Middleware ====================


class RateLimitMiddleware:
    """Простой rate limiting middleware на основе IP.

    Для production рекомендуется использовать более надежные решения
    (например, slowapi или redis-based rate limiting).
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ) -> None:
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self._requests: dict[str, list[float]] = {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        client_ip = self._get_client_ip(scope)
        current_time = time.time()

        # Очистка старых записей
        self._cleanup_old_requests(client_ip, current_time)

        # Проверка rate limit
        if not self._is_allowed(client_ip, current_time):
            await self._send_rate_limit_response(send)
            return

        # Запись запроса
        if client_ip not in self._requests:
            self._requests[client_ip] = []
        self._requests[client_ip].append(current_time)

        await self.app(scope, receive, send)

    def _get_client_ip(self, scope: Scope) -> str:
        """Извлечь IP клиента из scope."""
        headers = dict(scope.get("headers", []))

        forwarded_for = headers.get(b"x-forwarded-for")
        if forwarded_for:
            return forwarded_for.decode().split(",")[0].strip()

        real_ip = headers.get(b"x-real-ip")
        if real_ip:
            return real_ip.decode()

        client = scope.get("client")
        if client:
            return client[0]

        return "unknown"

    def _cleanup_old_requests(self, client_ip: str, current_time: float) -> None:
        """Удалить записи старше минуты."""
        if client_ip not in self._requests:
            return

        cutoff = current_time - 60
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > cutoff]

    def _is_allowed(self, client_ip: str, current_time: float) -> bool:
        """Проверить, разрешен ли запрос."""
        if client_ip not in self._requests:
            return True

        requests = self._requests[client_ip]

        # Проверка общего лимита за минуту
        if len(requests) >= self.requests_per_minute:
            return False

        # Проверка burst (запросы за последнюю секунду)
        recent = [t for t in requests if t > current_time - 1]
        if len(recent) >= self.burst_size:
            return False

        return True

    async def _send_rate_limit_response(self, send: Send) -> None:
        """Отправить ответ о превышении rate limit."""
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"60"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": (
                    b'{"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"}}'
                ),
            }
        )


# ==================== Request Size Limit Middleware ====================


class RequestSizeLimitMiddleware:
    """Middleware для ограничения размера запроса."""

    def __init__(
        self,
        app: ASGIApp,
        max_size_bytes: int = 10 * 1024 * 1024,  # 10 MB
    ) -> None:
        self.app = app
        self.max_size_bytes = max_size_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")

        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    await self._send_payload_too_large(send)
                    return
            except ValueError:
                pass

        await self.app(scope, receive, send)

    async def _send_payload_too_large(self, send: Send) -> None:
        """Отправить ответ о превышении размера."""
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": (
                    b'{"error": {"code": "PAYLOAD_TOO_LARGE", '
                    b'"message": "Request payload too large"}}'
                ),
            }
        )


# ==================== Setup Function ====================


def setup_middleware(app: FastAPI) -> None:
    """Настроить все middleware для приложения.

    Args:
        app: FastAPI приложение.
    """
    # Порядок важен: последний добавленный - первый выполняемый

    # Request size limit
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_size_bytes=50 * 1024 * 1024,  # 50 MB
    )

    # Security headers (только в production)
    if not settings.app.debug:
        app.add_middleware(SecurityHeadersMiddleware)

    # Request tracing (должен быть ближе к концу для правильного измерения времени)
    app.add_middleware(RequestTracingMiddleware)


# Alias for compatibility
add_middleware = setup_middleware
