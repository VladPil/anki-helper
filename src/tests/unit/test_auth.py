"""Unit tests for authentication and authorization services.

Tests cover:
- User registration
- User login and authentication
- Token creation and validation
- Token refresh
- Password hashing and verification
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
)
from src.core.security import (
    TokenType,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_token,
    create_token_pair,
    decode_token,
    hash_password,
    needs_rehash,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)
from src.modules.users.models import User
from src.modules.users.service import UserAlreadyExistsError, UserNotFoundError, UserService

from src.tests.factories import UserFactory
from src.tests.fixtures.sample_data import SAMPLE_LOGIN_DATA, SAMPLE_USER_DATA


# ==================== Password Hashing Tests ====================


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password_returns_hash(self):
        """Test that hash_password returns a bcrypt hash."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix
        assert len(hashed) == 60  # bcrypt hash length

    def test_hash_password_different_hashes_for_same_password(self):
        """Test that hashing the same password twice produces different hashes."""
        password = "securepassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Due to different salts

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "securepassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "securepassword123"
        wrong_password = "wrongpassword"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty_password(self):
        """Test password verification with empty password."""
        hashed = hash_password("somepassword")

        assert verify_password("", hashed) is False

    def test_needs_rehash_fresh_hash(self):
        """Test that fresh hashes don't need rehashing."""
        hashed = hash_password("password123")

        assert needs_rehash(hashed) is False

    def test_hash_password_unicode(self):
        """Test password hashing with unicode characters."""
        password = "password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True


# ==================== Token Creation Tests ====================


class TestTokenCreation:
    """Tests for JWT token creation."""

    def test_create_access_token(self):
        """Test access token creation."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        token = create_access_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token can be decoded
        payload = decode_token(token)
        assert payload.sub == str(user_id)
        assert payload.type == TokenType.ACCESS

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        jti = "test-jti-123"
        token = create_refresh_token(user_id, jti=jti)

        assert isinstance(token, str)

        payload = decode_token(token)
        assert payload.sub == str(user_id)
        assert payload.type == TokenType.REFRESH
        assert payload.jti == jti

    def test_create_token_with_custom_expiry(self):
        """Test token creation with custom expiry time."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        expires_delta = timedelta(hours=2)
        token = create_token(user_id, TokenType.ACCESS, expires_delta=expires_delta)

        payload = decode_token(token)
        # Check that expiry is approximately 2 hours from now
        time_diff = (payload.exp - payload.iat).total_seconds()
        assert 7190 < time_diff < 7210  # ~2 hours with some tolerance

    def test_create_token_with_additional_claims(self):
        """Test token creation with additional claims."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        claims = {"role": "admin", "permissions": ["read", "write"]}
        token = create_token(
            user_id,
            TokenType.ACCESS,
            additional_claims=claims,
        )

        # Additional claims should be in the token but not in standard payload
        assert isinstance(token, str)

    def test_create_token_pair(self):
        """Test creation of access/refresh token pair."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        pair = create_token_pair(user_id, refresh_jti="test-jti")

        assert pair.access_token is not None
        assert pair.refresh_token is not None
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0

        # Verify both tokens
        access_payload = decode_token(pair.access_token)
        refresh_payload = decode_token(pair.refresh_token)

        assert access_payload.type == TokenType.ACCESS
        assert refresh_payload.type == TokenType.REFRESH
        assert refresh_payload.jti == "test-jti"


# ==================== Token Validation Tests ====================


class TestTokenValidation:
    """Tests for JWT token validation."""

    def test_verify_access_token_valid(self):
        """Test validation of valid access token."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        token = create_access_token(user_id)

        payload = verify_access_token(token)

        assert payload.sub == str(user_id)
        assert payload.type == TokenType.ACCESS

    def test_verify_access_token_with_refresh_token_fails(self):
        """Test that refresh token fails access token validation."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        token = create_refresh_token(user_id)

        with pytest.raises(TokenInvalidError):
            verify_access_token(token)

    def test_verify_refresh_token_valid(self):
        """Test validation of valid refresh token."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        token = create_refresh_token(user_id, jti="test-jti")

        payload = verify_refresh_token(token)

        assert payload.sub == str(user_id)
        assert payload.type == TokenType.REFRESH

    def test_verify_refresh_token_with_access_token_fails(self):
        """Test that access token fails refresh token validation."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        token = create_access_token(user_id)

        with pytest.raises(TokenInvalidError):
            verify_refresh_token(token)

    def test_decode_expired_token(self):
        """Test decoding an expired token raises error."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        token = create_token(
            user_id,
            TokenType.ACCESS,
            expires_delta=timedelta(seconds=-1),
        )

        with pytest.raises(TokenExpiredError):
            decode_token(token)

    def test_decode_expired_token_without_verification(self):
        """Test decoding expired token without expiry verification."""
        user_id = UUID("00000000-0000-0000-0000-000000000001")
        token = create_token(
            user_id,
            TokenType.ACCESS,
            expires_delta=timedelta(seconds=-1),
        )

        payload = decode_token(token, verify_exp=False)
        assert payload.sub == str(user_id)

    def test_decode_invalid_token(self):
        """Test decoding an invalid token raises error."""
        with pytest.raises(TokenInvalidError):
            decode_token("invalid.token.string")

    def test_decode_malformed_token(self):
        """Test decoding a malformed token raises error."""
        with pytest.raises(TokenInvalidError):
            decode_token("not-a-jwt")

    def test_decode_empty_token(self):
        """Test decoding an empty token raises error."""
        with pytest.raises(TokenInvalidError):
            decode_token("")


# ==================== User Authentication Tests ====================


class TestAuthenticateUser:
    """Tests for user authentication."""

    def test_authenticate_user_correct_password(self):
        """Test authentication with correct password."""
        password = "securepassword123"
        hashed = hash_password(password)

        result = authenticate_user(password, hashed)
        assert result is True

    def test_authenticate_user_wrong_password(self):
        """Test authentication with wrong password raises error."""
        password = "securepassword123"
        hashed = hash_password(password)

        with pytest.raises(InvalidCredentialsError):
            authenticate_user("wrongpassword", hashed)

    def test_authenticate_user_empty_password(self):
        """Test authentication with empty password raises error."""
        hashed = hash_password("somepassword")

        with pytest.raises(InvalidCredentialsError):
            authenticate_user("", hashed)


# ==================== User Service Authentication Tests ====================


@pytest.mark.asyncio
class TestUserServiceAuthentication:
    """Tests for UserService authentication methods."""

    async def test_authenticate_valid_credentials(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test authentication with valid credentials."""
        service = UserService(db_session)

        user = await service.authenticate(
            email="test@example.com",
            password="testpassword123",
        )

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    async def test_authenticate_invalid_password(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test authentication with invalid password."""
        service = UserService(db_session)

        user = await service.authenticate(
            email="test@example.com",
            password="wrongpassword",
        )

        assert user is None

    async def test_authenticate_nonexistent_user(
        self,
        db_session: AsyncSession,
    ):
        """Test authentication with nonexistent user."""
        service = UserService(db_session)

        user = await service.authenticate(
            email="nonexistent@example.com",
            password="somepassword",
        )

        assert user is None

    async def test_authenticate_inactive_user(
        self,
        db_session: AsyncSession,
        inactive_user: User,
    ):
        """Test authentication with inactive user."""
        service = UserService(db_session)

        user = await service.authenticate(
            email="inactive@example.com",
            password="testpassword123",
        )

        assert user is None

    async def test_authenticate_deleted_user(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test authentication with soft-deleted user."""
        service = UserService(db_session)

        # Soft delete the user
        await service.delete(test_user.id)
        await db_session.flush()

        user = await service.authenticate(
            email="test@example.com",
            password="testpassword123",
        )

        assert user is None


# ==================== User Registration Tests ====================


@pytest.mark.asyncio
class TestUserRegistration:
    """Tests for user registration."""

    async def test_register_user_success(
        self,
        db_session: AsyncSession,
    ):
        """Test successful user registration."""
        service = UserService(db_session)
        user_data = SAMPLE_USER_DATA["valid"]

        from src.modules.users.schemas import UserCreate
        user = await service.create(
            UserCreate(
                email=user_data["email"],
                display_name=user_data["display_name"],
                password=user_data["password"],
            )
        )

        assert user is not None
        assert user.email == user_data["email"]
        assert user.display_name == user_data["display_name"]
        assert user.is_active is True
        assert user.preferences is not None

    async def test_register_duplicate_email(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test registration with duplicate email fails."""
        service = UserService(db_session)

        from src.modules.users.schemas import UserCreate
        with pytest.raises(UserAlreadyExistsError):
            await service.create(
                UserCreate(
                    email=test_user.email,  # Duplicate
                    display_name="Another User",
                    password="password123",
                )
            )

    async def test_register_creates_preferences(
        self,
        db_session: AsyncSession,
    ):
        """Test that registration creates default preferences."""
        service = UserService(db_session)

        from src.modules.users.schemas import UserCreate
        user = await service.create(
            UserCreate(
                email="newuser@example.com",
                display_name="New User",
                password="password123",
            )
        )

        assert user.preferences is not None
        assert user.preferences.preferred_language == "ru"  # Default

    async def test_register_password_is_hashed(
        self,
        db_session: AsyncSession,
    ):
        """Test that password is properly hashed during registration."""
        service = UserService(db_session)
        password = "plaintextpassword"

        from src.modules.users.schemas import UserCreate
        user = await service.create(
            UserCreate(
                email="hashtest@example.com",
                display_name="Hash Test",
                password=password,
            )
        )

        assert user.hashed_password != password
        assert user.hashed_password.startswith("$2b$")


# ==================== User Update Tests ====================


@pytest.mark.asyncio
class TestUserUpdate:
    """Tests for user profile updates."""

    async def test_update_user_display_name(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating user display name."""
        service = UserService(db_session)

        from src.modules.users.schemas import UserUpdate
        updated = await service.update(
            test_user.id,
            UserUpdate(display_name="New Display Name"),
        )

        assert updated.display_name == "New Display Name"

    async def test_update_user_email(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating user email."""
        service = UserService(db_session)

        from src.modules.users.schemas import UserUpdate
        updated = await service.update(
            test_user.id,
            UserUpdate(email="newemail@example.com"),
        )

        assert updated.email == "newemail@example.com"

    async def test_update_user_email_duplicate(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating email to existing email fails."""
        service = UserService(db_session)

        # Create another user
        from src.modules.users.schemas import UserCreate, UserUpdate
        await service.create(
            UserCreate(
                email="other@example.com",
                display_name="Other User",
                password="password123",
            )
        )

        with pytest.raises(UserAlreadyExistsError):
            await service.update(
                test_user.id,
                UserUpdate(email="other@example.com"),
            )

    async def test_update_user_password(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating user password."""
        service = UserService(db_session)
        new_password = "newpassword123"

        from src.modules.users.schemas import UserUpdate
        updated = await service.update(
            test_user.id,
            UserUpdate(password=new_password),
        )

        # Verify new password works
        assert service.verify_password(new_password, updated.hashed_password)

    async def test_update_nonexistent_user(
        self,
        db_session: AsyncSession,
    ):
        """Test updating nonexistent user fails."""
        service = UserService(db_session)

        from src.modules.users.schemas import UserUpdate
        with pytest.raises(UserNotFoundError):
            await service.update(
                UUID("00000000-0000-0000-0000-000000000999"),
                UserUpdate(display_name="Test"),
            )


# ==================== User Deletion Tests ====================


@pytest.mark.asyncio
class TestUserDeletion:
    """Tests for user deletion."""

    async def test_soft_delete_user(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test soft deleting a user."""
        service = UserService(db_session)

        await service.delete(test_user.id)
        await db_session.flush()

        # User should not be found via normal query
        user = await service.get_by_id(test_user.id)
        assert user is None

    async def test_delete_nonexistent_user(
        self,
        db_session: AsyncSession,
    ):
        """Test deleting nonexistent user fails."""
        service = UserService(db_session)

        with pytest.raises(UserNotFoundError):
            await service.delete(
                UUID("00000000-0000-0000-0000-000000000999")
            )


# ==================== User Activation Tests ====================


@pytest.mark.asyncio
class TestUserActivation:
    """Tests for user activation/deactivation."""

    async def test_deactivate_user(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test deactivating a user."""
        service = UserService(db_session)

        deactivated = await service.deactivate(test_user.id)

        assert deactivated.is_active is False

    async def test_activate_user(
        self,
        db_session: AsyncSession,
        inactive_user: User,
    ):
        """Test activating a user."""
        service = UserService(db_session)

        activated = await service.activate(inactive_user.id)

        assert activated.is_active is True

    async def test_deactivate_nonexistent_user(
        self,
        db_session: AsyncSession,
    ):
        """Test deactivating nonexistent user fails."""
        service = UserService(db_session)

        with pytest.raises(UserNotFoundError):
            await service.deactivate(
                UUID("00000000-0000-0000-0000-000000000999")
            )


# ==================== User Preferences Tests ====================


@pytest.mark.asyncio
class TestUserPreferences:
    """Tests for user preferences management."""

    async def test_update_preferences(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating user preferences."""
        service = UserService(db_session)

        from src.modules.users.schemas import UserPreferencesUpdate
        updated = await service.update_preferences(
            test_user.id,
            UserPreferencesUpdate(preferred_language="ja"),
        )

        assert updated.preferred_language == "ja"

    async def test_update_preferences_nonexistent_user(
        self,
        db_session: AsyncSession,
    ):
        """Test updating preferences for nonexistent user fails."""
        service = UserService(db_session)

        from src.modules.users.schemas import UserPreferencesUpdate
        with pytest.raises(UserNotFoundError):
            await service.update_preferences(
                UUID("00000000-0000-0000-0000-000000000999"),
                UserPreferencesUpdate(preferred_language="ja"),
            )


# ==================== User Listing Tests ====================


@pytest.mark.asyncio
class TestUserListing:
    """Tests for user listing and pagination."""

    async def test_list_users(
        self,
        db_session: AsyncSession,
        multiple_users: list[User],
    ):
        """Test listing users with pagination."""
        service = UserService(db_session)

        users, total = await service.list_users(page=1, per_page=10)

        assert len(users) <= 10
        assert total == len([u for u in multiple_users if u.is_active])

    async def test_list_users_include_inactive(
        self,
        db_session: AsyncSession,
        multiple_users: list[User],
    ):
        """Test listing users including inactive ones."""
        service = UserService(db_session)

        users, total = await service.list_users(
            page=1,
            per_page=10,
            include_inactive=True,
        )

        assert total == len(multiple_users)

    async def test_list_users_pagination(
        self,
        db_session: AsyncSession,
        multiple_users: list[User],
    ):
        """Test user listing pagination."""
        service = UserService(db_session)

        page1, total = await service.list_users(page=1, per_page=5)
        page2, _ = await service.list_users(page=2, per_page=5)

        assert len(page1) == 5
        assert len(page2) <= 5
        # Ensure different users on different pages
        page1_ids = {u.id for u in page1}
        page2_ids = {u.id for u in page2}
        assert page1_ids.isdisjoint(page2_ids)
