"""Pytest configuration and fixtures for AnkiRAG backend tests."""

import asyncio
import os
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.core.database import Base, get_db
from src.core.dependencies import get_current_user_id, get_redis
from src.core.security import TokenType, create_token, hash_password
from src.modules.users.models import User, UserPreferences

# Test database URL - use environment variables or defaults matching docker setup
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://"
    f"{os.getenv('DB_USER', 'ankirag')}:{os.getenv('DB_PASSWORD', 'ankirag_secret')}"
    f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5433')}"
    f"/{os.getenv('DB_NAME', 'ankirag')}"
)


# ==================== Event Loop Fixture ====================


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== Database Fixtures ====================


@pytest.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a test database engine.

    Creates all tables at the start of the test session and drops them
    at the end. Uses NullPool to avoid connection issues with async tests.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for a test.

    Each test gets its own session with automatic rollback after the test
    completes to ensure test isolation.
    """
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def committed_db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session that commits changes.

    Use this fixture when you need changes to persist across
    different operations within the same test.
    """
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with async_session() as session:
        yield session
        # Note: Changes will persist until test cleanup


# ==================== Redis Fixtures ====================


@pytest.fixture
async def mock_redis() -> AsyncMock:
    """Create a mock Redis client for testing."""
    redis = AsyncMock(spec=Redis)
    redis.get.return_value = None
    redis.set.return_value = True
    redis.setex.return_value = True
    redis.delete.return_value = 1
    redis.exists.return_value = 0
    redis.pipeline.return_value = AsyncMock()
    return redis


@pytest.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Create a real Redis client for integration tests.

    Connects to a test Redis instance and flushes the database
    after each test to ensure isolation.
    """
    client = Redis.from_url(
        "redis://localhost:6379/15",  # Use database 15 for tests
        encoding="utf-8",
        decode_responses=True,
    )

    yield client

    await client.flushdb()
    await client.close()


# ==================== User Fixtures ====================


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the database.

    Returns a User instance with associated preferences.
    """
    user = User(
        email="test@example.com",
        display_name="Test User",
        hashed_password=hash_password("testpassword123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    preferences = UserPreferences(
        user_id=user.id,
        preferred_language="en",
    )
    db_session.add(preferences)
    await db_session.flush()

    await db_session.refresh(user, ["preferences"])
    return user


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create an inactive test user."""
    user = User(
        email="inactive@example.com",
        display_name="Inactive User",
        hashed_password=hash_password("testpassword123"),
        is_active=False,
    )
    db_session.add(user)
    await db_session.flush()

    preferences = UserPreferences(
        user_id=user.id,
        preferred_language="en",
    )
    db_session.add(preferences)
    await db_session.flush()

    await db_session.refresh(user, ["preferences"])
    return user


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    user = User(
        email="admin@example.com",
        display_name="Admin User",
        hashed_password=hash_password("adminpassword123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    preferences = UserPreferences(
        user_id=user.id,
        preferred_language="en",
    )
    db_session.add(preferences)
    await db_session.flush()

    await db_session.refresh(user, ["preferences"])
    return user


@pytest.fixture
async def multiple_users(db_session: AsyncSession) -> list[User]:
    """Create multiple test users for pagination tests."""
    users = []
    for i in range(25):
        user = User(
            email=f"user{i}@example.com",
            display_name=f"User {i}",
            hashed_password=hash_password("testpassword123"),
            is_active=i % 5 != 0,  # Every 5th user is inactive
        )
        db_session.add(user)
        await db_session.flush()

        preferences = UserPreferences(
            user_id=user.id,
            preferred_language="en" if i % 2 == 0 else "ru",
        )
        db_session.add(preferences)
        users.append(user)

    await db_session.flush()
    return users


# ==================== Token Fixtures ====================


@pytest.fixture
def access_token(test_user: User) -> str:
    """Create an access token for the test user."""
    return create_token(
        user_id=test_user.id,
        token_type=TokenType.ACCESS,
    )


@pytest.fixture
def refresh_token(test_user: User) -> str:
    """Create a refresh token for the test user."""
    return create_token(
        user_id=test_user.id,
        token_type=TokenType.REFRESH,
        jti="test-jti-123",
    )


@pytest.fixture
def expired_token() -> str:
    """Create an expired access token."""
    from datetime import timedelta
    return create_token(
        user_id="00000000-0000-0000-0000-000000000000",
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(seconds=-1),
    )


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Create an access token for the admin user."""
    return create_token(
        user_id=admin_user.id,
        token_type=TokenType.ACCESS,
    )


# ==================== HTTP Client Fixtures ====================


@pytest.fixture
async def app():
    """Get the FastAPI application instance.

    Imports the app lazily to avoid import errors during test collection.
    """
    # Import here to avoid circular imports and ensure proper initialization
    try:
        from src.main import app as fastapi_app
        return fastapi_app
    except ImportError:
        # Create a minimal app for testing if main doesn't exist
        from fastapi import FastAPI
        return FastAPI()


@pytest.fixture
async def client(
    app,
    db_session: AsyncSession,
    mock_redis: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for API testing.

    Overrides database and Redis dependencies to use test instances.
    """
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def authenticated_client(
    app,
    db_session: AsyncSession,
    test_user: User,
    access_token: str,
    mock_redis: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated HTTP client.

    Includes authentication headers and overrides the current user dependency.
    """
    async def override_get_db():
        yield db_session

    async def override_get_current_user_id():
        return test_user.id

    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {access_token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(
    app,
    db_session: AsyncSession,
    admin_user: User,
    admin_token: str,
    mock_redis: AsyncMock,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an authenticated HTTP client for admin user."""
    async def override_get_db():
        yield db_session

    async def override_get_current_user_id():
        return admin_user.id

    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_id] = override_get_current_user_id
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {admin_token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ==================== Service Fixtures ====================


@pytest.fixture
def user_service(db_session: AsyncSession):
    """Create a UserService instance."""
    from src.modules.users.service import UserService
    return UserService(db_session)


@pytest.fixture
def deck_service(db_session: AsyncSession):
    """Create a DeckService instance."""
    from src.modules.decks.service import DeckService
    return DeckService(db_session)


@pytest.fixture
def template_service(db_session: AsyncSession):
    """Create a TemplateService instance."""
    from src.modules.templates.service import TemplateService
    return TemplateService(db_session)


@pytest.fixture
def chat_service(db_session: AsyncSession):
    """Create a ChatService instance."""
    from src.modules.chat.service import ChatService
    return ChatService(db_session)


@pytest.fixture
def embedding_service(mock_redis: AsyncMock):
    """Create an EmbeddingService instance with mocked Redis."""
    from src.services.rag.embeddings import EmbeddingService
    return EmbeddingService(redis=mock_redis)


# ==================== Deck Fixtures ====================


@pytest.fixture
async def test_deck(db_session: AsyncSession, test_user: User):
    """Create a test deck in the database."""
    from src.modules.decks.models import Deck

    deck = Deck(
        name="Test Deck",
        description="Test Description",
        owner_id=test_user.id,
    )
    db_session.add(deck)
    await db_session.flush()
    await db_session.refresh(deck)
    return deck


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another test user for access control tests."""
    user = User(
        email="other@example.com",
        display_name="Other User",
        hashed_password=hash_password("otherpassword123"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    preferences = UserPreferences(
        user_id=user.id,
        preferred_language="en",
    )
    db_session.add(preferences)
    await db_session.flush()

    await db_session.refresh(user, ["preferences"])
    return user


@pytest.fixture
async def other_user_deck(db_session: AsyncSession, other_user: User):
    """Create a deck belonging to another user."""
    from src.modules.decks.models import Deck

    deck = Deck(
        name="Other User Deck",
        description="Belongs to another user",
        owner_id=other_user.id,
    )
    db_session.add(deck)
    await db_session.flush()
    await db_session.refresh(deck)
    return deck


# ==================== Template Fixtures ====================


@pytest.fixture
async def test_template(db_session: AsyncSession):
    """Create a test card template."""
    from src.modules.templates.models import CardTemplate

    template = CardTemplate(
        name="basic",
        display_name="Basic",
        fields_schema={
            "type": "object",
            "properties": {
                "front": {"type": "string"},
                "back": {"type": "string"},
            },
            "required": ["front", "back"],
        },
        front_template="<div>{{front}}</div>",
        back_template="<div>{{back}}</div>",
        css=".card { font-size: 20px; }",
    )
    db_session.add(template)
    await db_session.flush()
    await db_session.refresh(template)
    return template


# ==================== Card Fixtures ====================


@pytest.fixture
async def test_card(db_session: AsyncSession, test_deck, test_template):
    """Create a test card in the database."""
    from src.modules.cards.models import Card, CardStatus

    card = Card(
        deck_id=test_deck.id,
        template_id=test_template.id,
        fields={"front": "Test Question", "back": "Test Answer"},
        tags=["test"],
        status=CardStatus.DRAFT,
    )
    db_session.add(card)
    await db_session.flush()
    await db_session.refresh(card)
    return card


@pytest.fixture
async def approved_card(db_session: AsyncSession, test_deck, test_template):
    """Create an approved test card."""
    from src.modules.cards.models import Card, CardStatus

    card = Card(
        deck_id=test_deck.id,
        template_id=test_template.id,
        fields={"front": "Approved Question", "back": "Approved Answer"},
        tags=["approved"],
        status=CardStatus.APPROVED,
    )
    db_session.add(card)
    await db_session.flush()
    await db_session.refresh(card)
    return card


@pytest.fixture
async def synced_card(db_session: AsyncSession, test_deck, test_template):
    """Create a synced test card."""
    from src.modules.cards.models import Card, CardStatus

    card = Card(
        deck_id=test_deck.id,
        template_id=test_template.id,
        fields={"front": "Synced Question", "back": "Synced Answer"},
        tags=["synced"],
        status=CardStatus.SYNCED,
        anki_card_id=12345,
        anki_note_id=67890,
    )
    db_session.add(card)
    await db_session.flush()
    await db_session.refresh(card)
    return card


@pytest.fixture
async def other_user_card(db_session: AsyncSession, other_user_deck, test_template):
    """Create a card belonging to another user."""
    from src.modules.cards.models import Card, CardStatus

    card = Card(
        deck_id=other_user_deck.id,
        template_id=test_template.id,
        fields={"front": "Other Question", "back": "Other Answer"},
        tags=["other"],
        status=CardStatus.DRAFT,
    )
    db_session.add(card)
    await db_session.flush()
    await db_session.refresh(card)
    return card


# ==================== Mock Fixtures ====================


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Create a mock LLM client."""
    client = MagicMock()
    client.generate = AsyncMock(return_value="Generated text response")
    client.stream = AsyncMock()
    return client


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    """Create a mock embedding provider."""
    provider = AsyncMock()
    provider.embed.return_value = [[0.1] * 1536]  # OpenAI dimension
    provider.embed_single.return_value = [0.1] * 1536
    provider.dimension = 1536
    provider.model_name = "test-embedding-model"
    return provider


@pytest.fixture
def mock_anki_connect() -> AsyncMock:
    """Create a mock AnkiConnect client."""
    client = AsyncMock()
    client.sync.return_value = True
    client.add_note.return_value = 12345
    client.get_decks.return_value = ["Default", "Test Deck"]
    client.create_deck.return_value = True
    return client


# ==================== Helper Functions ====================


def create_test_uuid(index: int = 0) -> UUID:
    """Create a deterministic UUID for testing."""
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


def assert_datetime_recent(dt: datetime, seconds: int = 10) -> None:
    """Assert that a datetime is recent (within specified seconds)."""
    now = datetime.now(UTC)
    delta = abs((now - dt).total_seconds())
    assert delta < seconds, f"Datetime {dt} is not recent (delta: {delta}s)"


# ==================== Pytest Configuration ====================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests",
    )
    config.addinivalue_line(
        "markers",
        "unit: marks tests as unit tests",
    )


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    yield
    # Clean up any singletons that might persist between tests
    from src.core.database import DatabaseManager
    DatabaseManager._instance = None
    DatabaseManager._engine = None
    DatabaseManager._session_factory = None
