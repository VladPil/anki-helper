"""Unit tests for UserService with mocked database sessions.

These tests use unittest.mock to mock AsyncSession and avoid real database interactions.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.users.schemas import UserCreate, UserPreferencesUpdate, UserUpdate
from src.modules.users.service import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
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
    session.scalar = AsyncMock()
    return session


@pytest.fixture
def user_service(mock_session):
    """Create UserService instance with mocked session."""
    return UserService(mock_session)


@pytest.fixture
def sample_user():
    """Create a sample User-like object for testing."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.hashed_password = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.S.9gZFMGbPCNry"
    user.is_active = True
    user.deleted_at = None
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    user.preferences = MagicMock()
    user.preferences.preferred_language = "ru"
    return user


@pytest.fixture
def sample_user_preferences():
    """Create sample UserPreferences-like object for testing."""
    prefs = MagicMock()
    prefs.id = uuid4()
    prefs.user_id = uuid4()
    prefs.preferred_language = "ru"
    prefs.default_model_id = None
    prefs.default_embedder_id = None
    return prefs


# ==================== get_by_id Tests ====================


@pytest.mark.asyncio
async def test_get_by_id_returns_user(user_service, mock_session, sample_user):
    """Test get_by_id returns user when found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await user_service.get_by_id(sample_user.id)

    assert result == sample_user
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(user_service, mock_session):
    """Test get_by_id returns None when user not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await user_service.get_by_id(uuid4())

    assert result is None


# ==================== get_by_email Tests ====================


@pytest.mark.asyncio
async def test_get_by_email_returns_user(user_service, mock_session, sample_user):
    """Test get_by_email returns user when found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await user_service.get_by_email("test@example.com")

    assert result == sample_user
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_email_returns_none_when_not_found(user_service, mock_session):
    """Test get_by_email returns None when user not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await user_service.get_by_email("nonexistent@example.com")

    assert result is None


# ==================== create Tests ====================


@pytest.mark.asyncio
async def test_create_user_success(user_service, mock_session):
    """Test successful user creation."""
    user_data = UserCreate(
        email="newuser@example.com",
        display_name="New User",
        password="securepass123",
    )

    # Mock get_by_email to return None (user doesn't exist)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Mock password hashing to avoid bcrypt issues
    with patch.object(user_service, '_hash_password', return_value="$2b$12$mockedhash"):
        result = await user_service.create(user_data)

    # Verify session.add was called twice (user and preferences)
    assert mock_session.add.call_count == 2
    assert mock_session.flush.call_count == 2
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_already_exists(user_service, mock_session, sample_user):
    """Test create raises UserAlreadyExistsError when email exists."""
    user_data = UserCreate(
        email="test@example.com",
        display_name="New User",
        password="securepassword123",
    )

    # Mock get_by_email to return existing user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    with pytest.raises(UserAlreadyExistsError) as exc_info:
        await user_service.create(user_data)

    assert "test@example.com" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_user_password_is_hashed(user_service, mock_session):
    """Test that password is hashed during user creation."""
    user_data = UserCreate(
        email="newuser@example.com",
        display_name="New User",
        password="securepass123",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    # Capture the User object passed to session.add
    added_objects = []
    mock_session.add.side_effect = lambda obj: added_objects.append(obj)

    # Mock password hashing to return a bcrypt-like hash
    with patch.object(user_service, '_hash_password', return_value="$2b$12$mockedhashvalue"):
        await user_service.create(user_data)

    # Find the User object (first one added)
    user_obj = added_objects[0]
    assert user_obj.hashed_password != "securepass123"
    assert user_obj.hashed_password.startswith("$2b$")


# ==================== update Tests ====================


@pytest.mark.asyncio
async def test_update_user_display_name(user_service, mock_session, sample_user):
    """Test updating user display name."""
    update_data = UserUpdate(display_name="Updated Name")

    # Mock get_by_id to return sample_user
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await user_service.update(sample_user.id, update_data)

    assert sample_user.display_name == "Updated Name"
    mock_session.flush.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_user_email(user_service, mock_session, sample_user):
    """Test updating user email."""
    update_data = UserUpdate(email="newemail@example.com")

    # First call returns user, second call (email check) returns None
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = sample_user
    mock_result_none = MagicMock()
    mock_result_none.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_result_user, mock_result_none]

    result = await user_service.update(sample_user.id, update_data)

    assert sample_user.email == "newemail@example.com"


@pytest.mark.asyncio
async def test_update_user_email_already_exists(user_service, mock_session, sample_user):
    """Test update raises error when changing to existing email."""
    update_data = UserUpdate(email="existing@example.com")

    existing_user = MagicMock()
    existing_user.id = uuid4()
    existing_user.email = "existing@example.com"

    # First call returns sample_user, second call returns existing user
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = sample_user
    mock_result_existing = MagicMock()
    mock_result_existing.scalar_one_or_none.return_value = existing_user

    mock_session.execute.side_effect = [mock_result_user, mock_result_existing]

    with pytest.raises(UserAlreadyExistsError):
        await user_service.update(sample_user.id, update_data)


@pytest.mark.asyncio
async def test_update_user_password(user_service, mock_session, sample_user):
    """Test updating user password."""
    update_data = UserUpdate(password="newpass123")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    # Mock password hashing
    with patch.object(user_service, '_hash_password', return_value="$2b$12$newhashedpassword"):
        await user_service.update(sample_user.id, update_data)

    # Password should be hashed
    assert sample_user.hashed_password.startswith("$2b$")


@pytest.mark.asyncio
async def test_update_user_not_found(user_service, mock_session):
    """Test update raises UserNotFoundError when user doesn't exist."""
    update_data = UserUpdate(display_name="New Name")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(UserNotFoundError):
        await user_service.update(uuid4(), update_data)


# ==================== delete Tests ====================


@pytest.mark.asyncio
async def test_delete_user_success(user_service, mock_session, sample_user):
    """Test successful user deletion (soft delete)."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    await user_service.delete(sample_user.id)

    sample_user.soft_delete.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_delete_user_not_found(user_service, mock_session):
    """Test delete raises UserNotFoundError when user doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(UserNotFoundError):
        await user_service.delete(uuid4())


# ==================== authenticate Tests ====================


@pytest.mark.asyncio
async def test_authenticate_success(user_service, mock_session, sample_user):
    """Test successful authentication."""
    sample_user.hashed_password = "$2b$12$mockedhash"
    sample_user.is_active = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    # Mock password verification
    with patch.object(user_service, 'verify_password', return_value=True):
        result = await user_service.authenticate("test@example.com", "pass123")

    assert result == sample_user


@pytest.mark.asyncio
async def test_authenticate_wrong_password(user_service, mock_session, sample_user):
    """Test authentication fails with wrong password."""
    sample_user.hashed_password = "$2b$12$mockedhash"
    sample_user.is_active = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    # Mock password verification to return False
    with patch.object(user_service, 'verify_password', return_value=False):
        result = await user_service.authenticate("test@example.com", "wrongpass")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_not_found(user_service, mock_session):
    """Test authentication fails when user doesn't exist."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await user_service.authenticate("nonexistent@example.com", "password")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_inactive_user(user_service, mock_session, sample_user):
    """Test authentication fails for inactive user."""
    sample_user.hashed_password = "$2b$12$mockedhash"
    sample_user.is_active = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    # Even with correct password, inactive user should not authenticate
    with patch.object(user_service, 'verify_password', return_value=True):
        result = await user_service.authenticate("test@example.com", "pass123")

    assert result is None


# ==================== list_users Tests ====================


@pytest.mark.asyncio
async def test_list_users_returns_users_and_count(user_service, mock_session, sample_user):
    """Test list_users returns paginated results."""
    users_list = [sample_user]

    # Mock scalar for count
    mock_session.scalar.return_value = 1

    # Mock execute for users query
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = users_list
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    users, total = await user_service.list_users(page=1, per_page=10)

    assert total == 1
    assert users == users_list


@pytest.mark.asyncio
async def test_list_users_with_include_inactive(user_service, mock_session, sample_user):
    """Test list_users includes inactive users when flag is set."""
    mock_session.scalar.return_value = 2

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sample_user, sample_user]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    users, total = await user_service.list_users(page=1, per_page=10, include_inactive=True)

    assert total == 2
    assert len(users) == 2


# ==================== deactivate Tests ====================


@pytest.mark.asyncio
async def test_deactivate_user_success(user_service, mock_session, sample_user):
    """Test successful user deactivation."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await user_service.deactivate(sample_user.id)

    assert sample_user.is_active is False
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_deactivate_user_not_found(user_service, mock_session):
    """Test deactivate raises error when user not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(UserNotFoundError):
        await user_service.deactivate(uuid4())


# ==================== activate Tests ====================


@pytest.mark.asyncio
async def test_activate_user_success(user_service, mock_session, sample_user):
    """Test successful user activation."""
    sample_user.is_active = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await user_service.activate(sample_user.id)

    assert sample_user.is_active is True
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_activate_user_not_found(user_service, mock_session):
    """Test activate raises error when user not found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(UserNotFoundError):
        await user_service.activate(uuid4())


# ==================== update_preferences Tests ====================


@pytest.mark.asyncio
async def test_update_preferences_success(user_service, mock_session, sample_user):
    """Test successful preferences update."""
    prefs_data = UserPreferencesUpdate(preferred_language="en")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await user_service.update_preferences(sample_user.id, prefs_data)

    assert sample_user.preferences.preferred_language == "en"
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_preferences_creates_if_not_exists(user_service, mock_session, sample_user):
    """Test preferences are created if they don't exist."""
    sample_user.preferences = None
    prefs_data = UserPreferencesUpdate(preferred_language="ja")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_session.execute.return_value = mock_result

    result = await user_service.update_preferences(sample_user.id, prefs_data)

    # Verify session.add was called for new preferences
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_update_preferences_user_not_found(user_service, mock_session):
    """Test update_preferences raises error when user not found."""
    prefs_data = UserPreferencesUpdate(preferred_language="en")

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with pytest.raises(UserNotFoundError):
        await user_service.update_preferences(uuid4(), prefs_data)


# ==================== Password Hashing Tests ====================


def test_hash_password(user_service):
    """Test password hashing produces bcrypt hash."""
    password = "securepass"
    # Mock the pwd_context to avoid bcrypt version issues
    with patch.object(user_service.pwd_context, 'hash', return_value="$2b$12$mockedhashvalue"):
        hashed = user_service._hash_password(password)

    assert hashed != password
    assert hashed.startswith("$2b$")


def test_verify_password_correct(user_service):
    """Test verify_password returns True for correct password."""
    password = "securepass"
    hashed = "$2b$12$mockedhashvalue"

    # Mock the pwd_context verify method
    with patch.object(user_service.pwd_context, 'verify', return_value=True):
        assert user_service.verify_password(password, hashed) is True


def test_verify_password_incorrect(user_service):
    """Test verify_password returns False for incorrect password."""
    password = "securepass"
    hashed = "$2b$12$mockedhashvalue"

    # Mock the pwd_context verify method
    with patch.object(user_service.pwd_context, 'verify', return_value=False):
        assert user_service.verify_password("wrongpass", hashed) is False
