"""Pytest configuration for unit tests.

This module provides fixtures for unit testing with mocked dependencies.
It imports all SQLAlchemy models to ensure mapper initialization happens correctly.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

# Import all models to ensure SQLAlchemy mapper is properly configured
# This is needed because models reference each other through relationships
from src.modules.users.models import User, UserPreferences
from src.modules.auth.models import RefreshToken
from src.modules.decks.models import Deck
from src.modules.cards.models import Card
from src.modules.templates.models import CardTemplate
from src.modules.chat.models import ChatSession, ChatMessage
from src.services.llm.models import LLMModel, EmbeddingModel
from src.modules.prompts.models import Prompt, PromptExecution


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing.

    This session mocks all common SQLAlchemy AsyncSession methods.
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.scalar = AsyncMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def sample_user_id():
    """Create a sample user ID."""
    return uuid4()


@pytest.fixture
def sample_user_mock():
    """Create a mock User object for testing."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.hashed_password = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.S.9gZFMGbPCNry"
    user.is_active = True
    user.deleted_at = None
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    user.preferences = MagicMock()
    user.preferences.preferred_language = "ru"
    return user


@pytest.fixture
def sample_deck_mock(sample_user_id):
    """Create a mock Deck object for testing."""
    deck = MagicMock()
    deck.id = uuid4()
    deck.name = "Test Deck"
    deck.description = "Test Description"
    deck.owner_id = sample_user_id
    deck.parent_id = None
    deck.anki_deck_id = None
    deck.deleted_at = None
    deck.created_at = datetime.now(timezone.utc)
    deck.updated_at = datetime.now(timezone.utc)
    deck.children = []
    deck.cards = []
    return deck


@pytest.fixture
def sample_refresh_token_mock(sample_user_id):
    """Create a mock RefreshToken object for testing."""
    token = MagicMock()
    token.id = uuid4()
    token.user_id = sample_user_id
    token.token = "test_refresh_token_string_123"
    token.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    token.revoked_at = None
    token.is_revoked = False
    token.is_expired = False
    token.is_valid = True
    return token
