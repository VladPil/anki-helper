"""Unit tests for AuthService with mocked database sessions.

These tests use unittest.mock to mock AsyncSession and avoid real database interactions.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest

from src.core.config import settings
from src.modules.auth.schemas import LoginRequest, RegisterRequest, TokenResponse
from src.modules.auth.service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenRevokedError,
    UserInactiveError,
)

# ==================== Fixtures ====================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for testing."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def auth_service(mock_session):
    """Create AuthService instance with mocked session."""
    return AuthService(mock_session)


@pytest.fixture
def sample_user():
    """Create a sample User-like object for testing."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.hashed_password = "$2b$12$test_hashed_password"
    user.is_active = True
    user.deleted_at = None
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    user.preferences = MagicMock()
    return user


@pytest.fixture
def sample_refresh_token(sample_user):
    """Create a sample RefreshToken-like object for testing."""
    token = MagicMock()
    token.id = uuid4()
    token.user_id = sample_user.id
    token.token = "test_refresh_token_string_123"
    token.expires_at = datetime.now(UTC) + timedelta(days=7)
    token.revoked_at = None
    token.is_revoked = False
    token.is_expired = False
    token.is_valid = True
    return token


# ==================== register Tests ====================


@pytest.mark.asyncio
async def test_register_success(auth_service, mock_session):
    """Test successful user registration."""
    request = RegisterRequest(
        email="newuser@example.com",
        password="securepass123",
        display_name="New User",
    )

    # Mock get_by_email to return None (user doesn't exist)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Mock password hashing to avoid bcrypt issues
    with patch.object(auth_service._user_service, '_hash_password', return_value="$2b$12$mockedhash"):
        result = await auth_service.register(request)

    assert isinstance(result, TokenResponse)
    assert result.access_token is not None
    assert result.refresh_token is not None
    assert result.token_type == "bearer"
    assert result.expires_in > 0


@pytest.mark.asyncio
async def test_register_creates_tokens(auth_service, mock_session):
    """Test that register creates both access and refresh tokens."""
    request = RegisterRequest(
        email="newuser@example.com",
        password="securepass123",
        display_name="New User",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Mock password hashing to avoid bcrypt issues
    with patch.object(auth_service._user_service, '_hash_password', return_value="$2b$12$mockedhash"):
        result = await auth_service.register(request)

    # Verify session.add was called (for user, preferences, and refresh token)
    assert mock_session.add.call_count >= 1


# ==================== login Tests ====================


@pytest.mark.asyncio
async def test_login_success(auth_service, mock_session, sample_user):
    """Test successful login."""
    request = LoginRequest(email="test@example.com", password="pass123")

    sample_user.hashed_password = "$2b$12$mockedhash"
    sample_user.is_active = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    # Mock password verification
    with patch.object(auth_service._user_service, 'verify_password', return_value=True):
        result = await auth_service.login(request)

    assert isinstance(result, TokenResponse)
    assert result.access_token is not None
    assert result.refresh_token is not None


@pytest.mark.asyncio
async def test_login_invalid_credentials(auth_service, mock_session):
    """Test login with invalid credentials."""
    request = LoginRequest(email="test@example.com", password="wrongpassword")

    # Return None for authentication
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(InvalidCredentialsError):
        await auth_service.login(request)


@pytest.mark.asyncio
async def test_login_inactive_user(auth_service, mock_session, sample_user):
    """Test login with inactive user.

    This tests the defensive check in AuthService.login - if authenticate
    returns a user that is not active, UserInactiveError should be raised.
    """
    request = LoginRequest(email="test@example.com", password="securepass")
    sample_user.is_active = False

    # Mock authenticate to return inactive user directly (bypassing UserService's is_active check)
    # This tests the defensive check in AuthService.login
    with patch.object(auth_service._user_service, 'authenticate', return_value=sample_user):
        with pytest.raises(UserInactiveError):
            await auth_service.login(request)


# ==================== refresh_token Tests ====================


@pytest.mark.asyncio
async def test_refresh_token_success(auth_service, mock_session, sample_user, sample_refresh_token):
    """Test successful token refresh."""
    # Mock finding the refresh token
    mock_result_token = MagicMock()
    mock_result_token.scalar_one_or_none.return_value = sample_refresh_token

    # Mock finding the user
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = sample_user

    mock_session.execute.side_effect = [mock_result_token, mock_result_user]

    result = await auth_service.refresh_token(sample_refresh_token.token)

    assert isinstance(result, TokenResponse)
    assert result.access_token is not None
    assert result.refresh_token is not None
    # Old token should be revoked
    sample_refresh_token.revoke.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_token_invalid(auth_service, mock_session):
    """Test refresh with invalid token."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(InvalidTokenError):
        await auth_service.refresh_token("invalid_token")


@pytest.mark.asyncio
async def test_refresh_token_revoked(auth_service, mock_session, sample_refresh_token):
    """Test refresh with revoked token."""
    sample_refresh_token.is_revoked = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_refresh_token
    mock_session.execute.return_value = mock_result

    with pytest.raises(TokenRevokedError):
        await auth_service.refresh_token(sample_refresh_token.token)


@pytest.mark.asyncio
async def test_refresh_token_expired(auth_service, mock_session, sample_refresh_token):
    """Test refresh with expired token."""
    sample_refresh_token.is_expired = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_refresh_token
    mock_session.execute.return_value = mock_result

    with pytest.raises(InvalidTokenError) as exc_info:
        await auth_service.refresh_token(sample_refresh_token.token)
    assert "expired" in str(exc_info.value)


@pytest.mark.asyncio
async def test_refresh_token_user_inactive(auth_service, mock_session, sample_user, sample_refresh_token):
    """Test refresh when user is inactive."""
    sample_user.is_active = False

    mock_result_token = MagicMock()
    mock_result_token.scalar_one_or_none.return_value = sample_refresh_token

    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = sample_user

    mock_session.execute.side_effect = [mock_result_token, mock_result_user]

    with pytest.raises(UserInactiveError):
        await auth_service.refresh_token(sample_refresh_token.token)


@pytest.mark.asyncio
async def test_refresh_token_user_not_found(auth_service, mock_session, sample_refresh_token):
    """Test refresh when user no longer exists."""
    mock_result_token = MagicMock()
    mock_result_token.scalar_one_or_none.return_value = sample_refresh_token

    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_result_token, mock_result_user]

    with pytest.raises(UserInactiveError):
        await auth_service.refresh_token(sample_refresh_token.token)


# ==================== logout Tests ====================


@pytest.mark.asyncio
async def test_logout_success(auth_service, mock_session, sample_refresh_token):
    """Test successful logout."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_refresh_token
    mock_session.execute.return_value = mock_result

    await auth_service.logout(sample_refresh_token.token)

    sample_refresh_token.revoke.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_logout_token_not_found(auth_service, mock_session):
    """Test logout with nonexistent token (should not raise)."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Should not raise any exception
    await auth_service.logout("nonexistent_token")


@pytest.mark.asyncio
async def test_logout_already_revoked(auth_service, mock_session, sample_refresh_token):
    """Test logout with already revoked token."""
    sample_refresh_token.is_revoked = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_refresh_token
    mock_session.execute.return_value = mock_result

    await auth_service.logout(sample_refresh_token.token)

    # revoke should not be called again
    sample_refresh_token.revoke.assert_not_called()


# ==================== logout_all Tests ====================


@pytest.mark.asyncio
async def test_logout_all_success(auth_service, mock_session, sample_user):
    """Test logout_all revokes all user tokens."""
    token1 = MagicMock()
    token2 = MagicMock()
    tokens = [token1, token2]

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = tokens
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    count = await auth_service.logout_all(sample_user.id)

    assert count == 2
    token1.revoke.assert_called_once()
    token2.revoke.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_logout_all_no_tokens(auth_service, mock_session, sample_user):
    """Test logout_all with no active tokens."""
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    count = await auth_service.logout_all(sample_user.id)

    assert count == 0


# ==================== verify_token Tests ====================


def test_verify_token_success(auth_service, sample_user):
    """Test successful token verification."""
    # Create a real token
    token = auth_service._create_access_token(sample_user.id)

    payload = auth_service.verify_token(token)

    assert payload["sub"] == str(sample_user.id)
    assert payload["type"] == "access"


def test_verify_token_invalid(auth_service):
    """Test verification of invalid token."""
    with pytest.raises(InvalidTokenError):
        auth_service.verify_token("invalid_token")


def test_verify_token_expired(auth_service, sample_user):
    """Test verification of expired token."""
    # Create an expired token
    token = auth_service._create_access_token(
        sample_user.id,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(InvalidTokenError) as exc_info:
        auth_service.verify_token(token)
    assert "expired" in str(exc_info.value).lower()


def test_verify_token_wrong_type(auth_service, sample_user):
    """Test verification fails for refresh token used as access token."""
    # Create a token with wrong type
    payload = {
        "sub": str(sample_user.id),
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        "type": "refresh",  # Wrong type
    }
    token = jwt.encode(payload, settings.jwt.secret_key, algorithm=auth_service.algorithm)

    with pytest.raises(InvalidTokenError) as exc_info:
        auth_service.verify_token(token)
    assert "type" in str(exc_info.value).lower()


# ==================== get_user_from_token Tests ====================


@pytest.mark.asyncio
async def test_get_user_from_token_success(auth_service, mock_session, sample_user):
    """Test successful user retrieval from token."""
    token = auth_service._create_access_token(sample_user.id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await auth_service.get_user_from_token(token)

    assert result == sample_user


@pytest.mark.asyncio
async def test_get_user_from_token_user_not_found(auth_service, mock_session, sample_user):
    """Test get_user_from_token when user doesn't exist."""
    token = auth_service._create_access_token(sample_user.id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(InvalidTokenError) as exc_info:
        await auth_service.get_user_from_token(token)
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_user_from_token_user_inactive(auth_service, mock_session, sample_user):
    """Test get_user_from_token when user is inactive."""
    sample_user.is_active = False

    token = auth_service._create_access_token(sample_user.id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    with pytest.raises(UserInactiveError):
        await auth_service.get_user_from_token(token)


# ==================== cleanup_expired_tokens Tests ====================


@pytest.mark.asyncio
async def test_cleanup_expired_tokens(auth_service, mock_session):
    """Test cleanup of expired tokens."""
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_session.execute.return_value = mock_result

    count = await auth_service.cleanup_expired_tokens()

    assert count == 5
    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_expired_tokens_none(auth_service, mock_session):
    """Test cleanup when no expired tokens exist."""
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute.return_value = mock_result

    count = await auth_service.cleanup_expired_tokens()

    assert count == 0


# ==================== _create_access_token Tests ====================


def test_create_access_token_returns_string(auth_service, sample_user):
    """Test that _create_access_token returns a JWT string."""
    token = auth_service._create_access_token(sample_user.id)

    assert isinstance(token, str)
    assert len(token) > 0
    # Should be a valid JWT (3 parts separated by dots)
    assert len(token.split('.')) == 3


def test_create_access_token_custom_expiry(auth_service, sample_user):
    """Test _create_access_token with custom expiry."""
    token = auth_service._create_access_token(
        sample_user.id,
        expires_delta=timedelta(hours=2),
    )

    # Decode and verify expiry
    payload = auth_service.verify_token(token)
    # Token should be valid (not expired)
    assert payload["sub"] == str(sample_user.id)


# ==================== _create_refresh_token Tests ====================


@pytest.mark.asyncio
async def test_create_refresh_token_success(auth_service, mock_session, sample_user):
    """Test _create_refresh_token creates and stores token."""
    result = await auth_service._create_refresh_token(sample_user.id)

    # Verify session.add was called
    mock_session.add.assert_called_once()
    mock_session.flush.assert_called_once()


def test_create_refresh_token_string(auth_service):
    """Test _create_refresh_token_string generates secure token."""
    token1 = auth_service._create_refresh_token_string()
    token2 = auth_service._create_refresh_token_string()

    assert isinstance(token1, str)
    assert len(token1) > 0
    # Each call should generate a unique token
    assert token1 != token2
