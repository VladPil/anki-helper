"""
Конфигурация приложения.
Все значения из переменных окружения. Дефолтов НЕТ.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Конфигурация подключения к PostgreSQL."""

    model_config = SettingsConfigDict(env_prefix="DB_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 5432
    user: str = "ankirag"
    password: str = "ankirag"
    name: str = "ankirag"
    pool_size: int = 5
    max_overflow: int = 10

    @property
    def async_url(self) -> str:
        """URL для asyncpg драйвера."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        )

    @property
    def sync_url(self) -> str:
        """URL для psycopg2 драйвера."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
        )


class RedisConfig(BaseSettings):
    """Конфигурация подключения к Redis."""

    model_config = SettingsConfigDict(env_prefix="REDIS_", env_file=".env", extra="ignore")

    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0

    @property
    def url(self) -> str:
        """URL для подключения к Redis."""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class JWTConfig(BaseSettings):
    """Конфигурация JWT токенов."""

    model_config = SettingsConfigDict(env_prefix="JWT_", env_file=".env", extra="ignore")

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7


class SopLLMConfig(BaseSettings):
    """Конфигурация SOP LLM сервиса.

    SOP_LLM - это внутренний сервис для работы с LLM.
    Все запросы к LLM должны идти через него.
    """

    model_config = SettingsConfigDict(env_prefix="SOP_LLM_", env_file=".env", extra="ignore")

    # URL сервиса sop_llm (по умолчанию локальный)
    api_base_url: str = "http://localhost:8001"
    # Таймаут ожидания ответа (в секундах)
    timeout: int = 120
    # Модель по умолчанию для генерации
    default_model: str = "gpt-4o"
    # Температура по умолчанию
    default_temperature: float = 0.7
    # Max tokens по умолчанию
    default_max_tokens: int = 4096


class EmbeddingConfig(BaseSettings):
    """Конфигурация эмбеддингов через SOP_LLM."""

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", env_file=".env", extra="ignore")

    # Модель для эмбеддингов (зарегистрирована в sop_llm)
    model: str = "multilingual-e5-large"
    # Размерность векторов
    dimensions: int = 1024
    # Размер батча
    batch_size: int = 100


class PerplexityConfig(BaseSettings):
    """Конфигурация Perplexity модели для fact-checking через SOP_LLM."""

    model_config = SettingsConfigDict(env_prefix="PERPLEXITY_", env_file=".env", extra="ignore")

    # Модель Perplexity (зарегистрирована в sop_llm)
    model: str = "llama-3.1-sonar-large-128k-online"


class TelemetryConfig(BaseSettings):
    """Конфигурация OpenTelemetry."""

    model_config = SettingsConfigDict(env_prefix="OTEL_", env_file=".env", extra="ignore")

    enabled: bool = False
    service_name: str = "ankirag"
    exporter_otlp_endpoint: str = "http://localhost:4317"


class LoggingConfig(BaseSettings):
    """Конфигурация логирования."""

    model_config = SettingsConfigDict(env_prefix="LOG_", env_file=".env", extra="ignore")

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    loki_url: str = ""
    loki_enabled: bool = False


class MetricsConfig(BaseSettings):
    """Конфигурация Prometheus метрик."""

    model_config = SettingsConfigDict(env_prefix="METRICS_", env_file=".env", extra="ignore")

    enabled: bool = True
    port: int = 9090


class WorkerConfig(BaseSettings):
    """Конфигурация FastStream worker."""

    model_config = SettingsConfigDict(env_prefix="WORKER_", env_file=".env", extra="ignore")

    max_concurrent_tasks: int = 10
    task_timeout: int = 600  # 10 minutes
    retry_attempts: int = 3
    retry_delay: int = 60  # seconds


class AgentConfig(BaseSettings):
    """Конфигурация локального агента.

    Токен для авторизации local-agent без JWT.
    Указывается в .env как AGENT_API_TOKEN и AGENT_USER_ID.
    """

    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env", extra="ignore")

    api_token: str = ""  # Токен для авторизации агента
    user_id: str = ""  # UUID пользователя для агента


class AppConfig(BaseSettings):
    """Общая конфигурация приложения."""

    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    name: str = "AnkiRAG"
    debug: bool = False
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    max_cards_per_generation: int = 50
    sync_poll_interval_seconds: int = 30

    @property
    def cors_origins_list(self) -> list[str]:
        """Список CORS origins."""
        return [o.strip() for o in self.cors_origins.split(",")]


class Settings:
    """Агрегатор всех конфигураций."""

    def __init__(self) -> None:
        self.db = DatabaseConfig()
        self.redis = RedisConfig()
        self.jwt = JWTConfig()
        self.sop_llm = SopLLMConfig()
        self.embedding = EmbeddingConfig()
        self.perplexity = PerplexityConfig()
        self.telemetry = TelemetryConfig()
        self.logging = LoggingConfig()
        self.metrics = MetricsConfig()
        self.worker = WorkerConfig()
        self.agent = AgentConfig()
        self.app = AppConfig()


@lru_cache
def get_settings() -> Settings:
    """Получить синглтон настроек (кешируется)."""
    return Settings()


settings = get_settings()
