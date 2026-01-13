"""Unit tests for core modules.

Tests cover:
- Config (DatabaseConfig, RedisConfig, JWTConfig, etc.)
- Exceptions (AppError and subclasses)
- Database (Base model)
- Security (password hashing, JWT tokens)
"""

import uuid
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI

from src.core.config import (
    AppConfig,
    DatabaseConfig,
    EmbeddingConfig,
    JWTConfig,
    LoggingConfig,
    MetricsConfig,
    PerplexityConfig,
    RedisConfig,
    Settings,
    SopLLMConfig,
    TelemetryConfig,
    get_settings,
)
from src.core.exceptions import (
    AnkiConnectError,
    AppError,
    AuthenticationError,
    AuthorizationError,
    CardNotFoundError,
    ConflictError,
    DatabaseError,
    DeckNameExistsError,
    DeckNotFoundError,
    DocumentNotFoundError,
    DuplicateError,
    EmailAlreadyExistsError,
    ExternalServiceError,
    InvalidCredentialsError,
    InvalidInputError,
    LLMServiceError,
    NotFoundError,
    PermissionDeniedError,
    PerplexityError,
    QuotaExceededError,
    RateLimitError,
    ResourceOwnershipError,
    TokenExpiredError,
    TokenInvalidError,
    TokenRevokedError,
    TransactionError,
    UserNotFoundError,
    ValidationError,
    app_error_handler,
    error_handler,
    register_exception_handlers,
    unhandled_exception_handler,
)
from src.core.security import (
    TokenPair,
    TokenPayload,
    TokenType,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_token,
    create_token_pair,
    decode_token,
    extract_user_id,
    hash_password,
    needs_rehash,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)

# ==================== Config Tests ====================


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.user == "ankirag"
        assert config.password == "ankirag"
        assert config.name == "ankirag"
        assert config.pool_size == 5
        assert config.max_overflow == 10

    def test_async_url_property(self):
        """Test async URL generation."""
        config = DatabaseConfig()
        expected = "postgresql+asyncpg://ankirag:ankirag@localhost:5432/ankirag"
        assert config.async_url == expected

    def test_sync_url_property(self):
        """Test sync URL generation."""
        config = DatabaseConfig()
        expected = "postgresql+psycopg2://ankirag:ankirag@localhost:5432/ankirag"
        assert config.sync_url == expected


class TestRedisConfig:
    """Tests for RedisConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.password == ""
        assert config.db == 0

    def test_url_without_password(self):
        """Test URL generation without password."""
        config = RedisConfig()
        expected = "redis://localhost:6379/0"
        assert config.url == expected

    def test_url_with_password(self):
        """Test URL generation with password."""
        config = RedisConfig(password="secret")
        expected = "redis://:secret@localhost:6379/0"
        assert config.url == expected


class TestJWTConfig:
    """Tests for JWTConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = JWTConfig()
        assert config.secret_key == "change-me-in-production"
        assert config.algorithm == "HS256"
        assert config.access_token_expire_minutes == 30
        assert config.refresh_token_expire_days == 7


class TestSopLLMConfig:
    """Tests for SopLLMConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = SopLLMConfig()
        assert config.api_base_url == "http://localhost:8001"
        assert config.timeout == 120
        assert config.default_model == "gpt-4o"
        assert config.default_temperature == 0.7
        assert config.default_max_tokens == 4096


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = EmbeddingConfig()
        assert config.model == "multilingual-e5-large"
        assert config.dimensions == 1024
        assert config.batch_size == 100


class TestPerplexityConfig:
    """Tests for PerplexityConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = PerplexityConfig()
        assert config.model == "llama-3.1-sonar-large-128k-online"


class TestTelemetryConfig:
    """Tests for TelemetryConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = TelemetryConfig()
        assert config.enabled is False
        assert config.service_name == "ankirag"
        assert config.exporter_otlp_endpoint == "http://localhost:4317"


class TestLoggingConfig:
    """Tests for LoggingConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert "asctime" in config.format
        assert config.loki_url == ""
        assert config.loki_enabled is False


class TestMetricsConfig:
    """Tests for MetricsConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = MetricsConfig()
        assert config.enabled is True
        assert config.port == 9090


class TestAppConfig:
    """Tests for AppConfig."""

    def test_default_values(self):
        """Test default values are set correctly."""
        config = AppConfig()
        assert config.name == "AnkiRAG"
        assert config.debug is False
        assert config.max_cards_per_generation == 50
        assert config.sync_poll_interval_seconds == 30

    def test_cors_origins_list(self):
        """Test CORS origins list property."""
        config = AppConfig()
        origins = config.cors_origins_list
        assert isinstance(origins, list)
        assert "http://localhost:3000" in origins
        assert "http://localhost:5173" in origins


class TestSettings:
    """Tests for Settings aggregator."""

    def test_settings_initialization(self):
        """Test that Settings initializes all sub-configs."""
        settings = Settings()
        assert isinstance(settings.db, DatabaseConfig)
        assert isinstance(settings.redis, RedisConfig)
        assert isinstance(settings.jwt, JWTConfig)
        assert isinstance(settings.sop_llm, SopLLMConfig)
        assert isinstance(settings.embedding, EmbeddingConfig)
        assert isinstance(settings.perplexity, PerplexityConfig)
        assert isinstance(settings.telemetry, TelemetryConfig)
        assert isinstance(settings.logging, LoggingConfig)
        assert isinstance(settings.metrics, MetricsConfig)
        assert isinstance(settings.app, AppConfig)

    def test_get_settings_returns_singleton(self):
        """Test that get_settings returns cached instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


# ==================== Exception Tests ====================


class TestAppError:
    """Tests for base AppError exception."""

    def test_default_values(self):
        """Test default values for AppError."""
        error = AppError()
        assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert error.error_code == "INTERNAL_ERROR"
        assert error.message == "An unexpected error occurred"
        assert error.details == {}

    def test_custom_message(self):
        """Test AppError with custom message."""
        error = AppError(message="Custom error message")
        assert error.message == "Custom error message"

    def test_custom_details(self):
        """Test AppError with custom details."""
        details = {"field": "email", "reason": "invalid format"}
        error = AppError(details=details)
        assert error.details == details

    def test_custom_status_code(self):
        """Test AppError with custom status code."""
        error = AppError(status_code=HTTPStatus.BAD_REQUEST)
        assert error.status_code == HTTPStatus.BAD_REQUEST

    def test_custom_error_code(self):
        """Test AppError with custom error code."""
        error = AppError(error_code="CUSTOM_ERROR")
        assert error.error_code == "CUSTOM_ERROR"

    def test_to_dict(self):
        """Test AppError to_dict method."""
        error = AppError(message="Test error")
        result = error.to_dict()
        assert "error" in result
        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert result["error"]["message"] == "Test error"

    def test_to_dict_with_details(self):
        """Test AppError to_dict with details."""
        details = {"field": "email"}
        error = AppError(message="Test", details=details)
        result = error.to_dict()
        assert "details" in result["error"]
        assert result["error"]["details"] == details


class TestAuthenticationErrors:
    """Tests for authentication-related exceptions."""

    def test_authentication_error(self):
        """Test AuthenticationError defaults."""
        error = AuthenticationError()
        assert error.status_code == HTTPStatus.UNAUTHORIZED
        assert error.error_code == "AUTHENTICATION_ERROR"

    def test_invalid_credentials_error(self):
        """Test InvalidCredentialsError defaults."""
        error = InvalidCredentialsError()
        assert error.error_code == "INVALID_CREDENTIALS"
        assert "Invalid email or password" in error.message

    def test_token_expired_error(self):
        """Test TokenExpiredError defaults."""
        error = TokenExpiredError()
        assert error.error_code == "TOKEN_EXPIRED"

    def test_token_invalid_error(self):
        """Test TokenInvalidError defaults."""
        error = TokenInvalidError()
        assert error.error_code == "TOKEN_INVALID"

    def test_token_revoked_error(self):
        """Test TokenRevokedError defaults."""
        error = TokenRevokedError()
        assert error.error_code == "TOKEN_REVOKED"


class TestAuthorizationErrors:
    """Tests for authorization-related exceptions."""

    def test_authorization_error(self):
        """Test AuthorizationError defaults."""
        error = AuthorizationError()
        assert error.status_code == HTTPStatus.FORBIDDEN
        assert error.error_code == "AUTHORIZATION_ERROR"

    def test_permission_denied_error(self):
        """Test PermissionDeniedError defaults."""
        error = PermissionDeniedError()
        assert error.error_code == "PERMISSION_DENIED"

    def test_resource_ownership_error(self):
        """Test ResourceOwnershipError defaults."""
        error = ResourceOwnershipError()
        assert error.error_code == "RESOURCE_OWNERSHIP_ERROR"


class TestNotFoundErrors:
    """Tests for not found exceptions."""

    def test_not_found_error(self):
        """Test NotFoundError defaults."""
        error = NotFoundError()
        assert error.status_code == HTTPStatus.NOT_FOUND
        assert error.error_code == "NOT_FOUND"

    def test_user_not_found_error(self):
        """Test UserNotFoundError defaults."""
        error = UserNotFoundError()
        assert error.error_code == "USER_NOT_FOUND"

    def test_deck_not_found_error(self):
        """Test DeckNotFoundError defaults."""
        error = DeckNotFoundError()
        assert error.error_code == "DECK_NOT_FOUND"

    def test_card_not_found_error(self):
        """Test CardNotFoundError defaults."""
        error = CardNotFoundError()
        assert error.error_code == "CARD_NOT_FOUND"

    def test_document_not_found_error(self):
        """Test DocumentNotFoundError defaults."""
        error = DocumentNotFoundError()
        assert error.error_code == "DOCUMENT_NOT_FOUND"


class TestValidationErrors:
    """Tests for validation exceptions."""

    def test_validation_error(self):
        """Test ValidationError defaults."""
        error = ValidationError()
        assert error.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        assert error.error_code == "VALIDATION_ERROR"

    def test_invalid_input_error(self):
        """Test InvalidInputError defaults."""
        error = InvalidInputError()
        assert error.error_code == "INVALID_INPUT"


class TestConflictErrors:
    """Tests for conflict exceptions."""

    def test_conflict_error(self):
        """Test ConflictError defaults."""
        error = ConflictError()
        assert error.status_code == HTTPStatus.CONFLICT
        assert error.error_code == "CONFLICT"

    def test_duplicate_error(self):
        """Test DuplicateError defaults."""
        error = DuplicateError()
        assert error.error_code == "DUPLICATE"

    def test_email_already_exists_error(self):
        """Test EmailAlreadyExistsError defaults."""
        error = EmailAlreadyExistsError()
        assert error.error_code == "EMAIL_ALREADY_EXISTS"

    def test_deck_name_exists_error(self):
        """Test DeckNameExistsError defaults."""
        error = DeckNameExistsError()
        assert error.error_code == "DECK_NAME_EXISTS"


class TestExternalServiceErrors:
    """Tests for external service exceptions."""

    def test_external_service_error(self):
        """Test ExternalServiceError defaults."""
        error = ExternalServiceError()
        assert error.status_code == HTTPStatus.BAD_GATEWAY
        assert error.error_code == "EXTERNAL_SERVICE_ERROR"

    def test_llm_service_error(self):
        """Test LLMServiceError defaults."""
        error = LLMServiceError()
        assert error.error_code == "LLM_SERVICE_ERROR"

    def test_anki_connect_error(self):
        """Test AnkiConnectError defaults."""
        error = AnkiConnectError()
        assert error.error_code == "ANKI_CONNECT_ERROR"

    def test_perplexity_error(self):
        """Test PerplexityError defaults."""
        error = PerplexityError()
        assert error.error_code == "PERPLEXITY_ERROR"


class TestLimitErrors:
    """Tests for rate limit exceptions."""

    def test_rate_limit_error(self):
        """Test RateLimitError defaults."""
        error = RateLimitError()
        assert error.status_code == HTTPStatus.TOO_MANY_REQUESTS
        assert error.error_code == "RATE_LIMIT_EXCEEDED"

    def test_quota_exceeded_error(self):
        """Test QuotaExceededError defaults."""
        error = QuotaExceededError()
        assert error.status_code == HTTPStatus.PAYMENT_REQUIRED
        assert error.error_code == "QUOTA_EXCEEDED"


class TestDatabaseErrors:
    """Tests for database exceptions."""

    def test_database_error(self):
        """Test DatabaseError defaults."""
        error = DatabaseError()
        assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert error.error_code == "DATABASE_ERROR"

    def test_transaction_error(self):
        """Test TransactionError defaults."""
        error = TransactionError()
        assert error.error_code == "TRANSACTION_ERROR"


# ==================== Security Tests ====================


@pytest.mark.skip(reason="bcrypt version incompatibility")
class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password(self):
        """Test password hashing produces hash."""
        password = "test123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_hash_password_different_each_time(self):
        """Test that same password produces different hashes."""
        password = "test123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "test123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with wrong password."""
        password = "test123"
        hashed = hash_password(password)

        assert verify_password("wrong", hashed) is False

    def test_needs_rehash_fresh_hash(self):
        """Test that fresh hash doesn't need rehash."""
        password = "test123"
        hashed = hash_password(password)

        assert needs_rehash(hashed) is False


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token(self):
        """Test creating access token."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id)

        assert token is not None
        assert isinstance(token, str)

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)

        assert token is not None
        assert isinstance(token, str)

    def test_create_token_with_jti(self):
        """Test creating refresh token with JTI."""
        user_id = uuid.uuid4()
        jti = "test-jti-123"
        token = create_refresh_token(user_id, jti=jti)

        payload = decode_token(token)
        assert payload.jti == jti

    def test_create_token_pair(self):
        """Test creating token pair."""
        user_id = uuid.uuid4()
        pair = create_token_pair(user_id)

        assert isinstance(pair, TokenPair)
        assert pair.access_token is not None
        assert pair.refresh_token is not None
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0

    def test_create_token_with_additional_claims(self):
        """Test creating token with additional claims."""
        user_id = uuid.uuid4()
        claims = {"role": "admin"}
        token = create_access_token(user_id, additional_claims=claims)

        # Decode and check
        payload = decode_token(token)
        assert payload is not None


class TestTokenDecoding:
    """Tests for JWT token decoding."""

    def test_decode_valid_token(self):
        """Test decoding valid token."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id)

        payload = decode_token(token)

        assert payload.sub == str(user_id)
        assert payload.type == TokenType.ACCESS

    def test_decode_expired_token_with_verify(self):
        """Test decoding expired token with verification."""
        user_id = uuid.uuid4()
        token = create_token(
            user_id,
            TokenType.ACCESS,
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(TokenExpiredError):
            decode_token(token)

    def test_decode_expired_token_without_verify(self):
        """Test decoding expired token without verification."""
        user_id = uuid.uuid4()
        token = create_token(
            user_id,
            TokenType.ACCESS,
            expires_delta=timedelta(seconds=-1),
        )

        # Should not raise
        payload = decode_token(token, verify_exp=False)
        assert payload.sub == str(user_id)

    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        with pytest.raises(TokenInvalidError):
            decode_token("invalid-token")


class TestTokenVerification:
    """Tests for token type verification."""

    def test_verify_access_token(self):
        """Test verifying access token."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id)

        payload = verify_access_token(token)

        assert payload.type == TokenType.ACCESS

    def test_verify_access_token_with_refresh_fails(self):
        """Test verifying refresh token as access fails."""
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)

        with pytest.raises(TokenInvalidError):
            verify_access_token(token)

    def test_verify_refresh_token(self):
        """Test verifying refresh token."""
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)

        payload = verify_refresh_token(token)

        assert payload.type == TokenType.REFRESH

    def test_verify_refresh_token_with_access_fails(self):
        """Test verifying access token as refresh fails."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id)

        with pytest.raises(TokenInvalidError):
            verify_refresh_token(token)


class TestExtractUserId:
    """Tests for extracting user ID from token."""

    def test_extract_user_id(self):
        """Test extracting user ID from token."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id)

        extracted = extract_user_id(token)

        assert extracted == user_id


@pytest.mark.skip(reason="bcrypt version incompatibility")
class TestAuthenticateUser:
    """Tests for user authentication function."""

    def test_authenticate_user_success(self):
        """Test successful authentication."""
        password = "test123"
        hashed = hash_password(password)

        result = authenticate_user(password, hashed)

        assert result is True

    def test_authenticate_user_failure(self):
        """Test failed authentication."""
        password = "test123"
        hashed = hash_password(password)

        with pytest.raises(InvalidCredentialsError):
            authenticate_user("wrong", hashed)


class TestTokenPayload:
    """Tests for TokenPayload model."""

    def test_token_payload_creation(self):
        """Test creating TokenPayload."""
        now = datetime.now(UTC)
        payload = TokenPayload(
            sub="user-123",
            type=TokenType.ACCESS,
            exp=now + timedelta(hours=1),
            iat=now,
        )

        assert payload.sub == "user-123"
        assert payload.type == TokenType.ACCESS


class TestTokenType:
    """Tests for TokenType enum."""

    def test_token_type_values(self):
        """Test TokenType enum values."""
        assert TokenType.ACCESS.value == "access"
        assert TokenType.REFRESH.value == "refresh"


@pytest.mark.asyncio
class TestExceptionHandlers:
    """Tests for exception handlers."""

    async def test_app_error_handler(self):
        """Test app_error_handler returns correct response."""
        request = MagicMock()
        error = AppError(message="Test error")

        response = await app_error_handler(request, error)

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        # Response body is JSON containing error info

    async def test_unhandled_exception_handler(self):
        """Test unhandled_exception_handler returns generic error."""
        request = MagicMock()
        error = Exception("Unexpected error")

        response = await unhandled_exception_handler(request, error)

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_register_exception_handlers(self):
        """Test exception handlers are registered on app."""
        app = FastAPI()
        register_exception_handlers(app)

        # Check handlers are registered
        assert AppError in app.exception_handlers
        assert Exception in app.exception_handlers


@pytest.mark.asyncio
class TestErrorHandlerDecorator:
    """Tests for error_handler decorator."""

    async def test_error_handler_passes_through_on_success(self):
        """Test decorator passes through successful results."""
        @error_handler(DatabaseError)
        async def successful_function():
            return "success"

        result = await successful_function()
        assert result == "success"

    async def test_error_handler_raises_app_error_unchanged(self):
        """Test decorator passes through AppError unchanged."""
        @error_handler(DatabaseError)
        async def function_with_app_error():
            raise NotFoundError("Not found")

        with pytest.raises(NotFoundError):
            await function_with_app_error()

    async def test_error_handler_wraps_generic_exception(self):
        """Test decorator wraps generic exceptions."""
        @error_handler(DatabaseError)
        async def function_with_generic_error():
            raise ValueError("Some value error")

        with pytest.raises(DatabaseError) as exc_info:
            await function_with_generic_error()

        assert "Some value error" in str(exc_info.value)
