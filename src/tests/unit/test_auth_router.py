"""Unit tests for authentication router endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.modules.auth.schemas import TokenResponse
from src.modules.auth.service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenRevokedError,
    UserInactiveError,
)
from src.modules.users.service import UserAlreadyExistsError


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.is_active = True
    user.hashed_password = "hashed_password"
    user.created_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    return user


@pytest.fixture
def mock_token_response():
    """Create a mock token response."""
    return TokenResponse(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_type="bearer",
        expires_in=3600,
    )


@pytest.fixture
def app_with_mocked_db():
    """Create app with mocked database dependency."""
    from src.core.database import get_db
    from src.main import create_app

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_get_db

    yield app

    app.dependency_overrides.clear()


class TestRegisterEndpoint:
    """Tests for POST /api/auth/register endpoint."""

    def test_register_success(self, app_with_mocked_db, mock_token_response):
        """Test successful user registration."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.register.return_value = mock_token_response

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "display_name": "New User",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_user_already_exists(self, app_with_mocked_db):
        """Test registration with existing email returns 409."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.register.side_effect = UserAlreadyExistsError(
            "User with email test@example.com already exists"
        )

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
                "display_name": "Test User",
            },
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_invalid_email(self, app_with_mocked_db):
        """Test registration with invalid email returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "invalid-email",
                "password": "securepassword123",
                "display_name": "Test User",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_short_password(self, app_with_mocked_db):
        """Test registration with short password returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
                "display_name": "Test User",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_empty_display_name(self, app_with_mocked_db):
        """Test registration with empty display name returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
                "display_name": "",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginEndpoint:
    """Tests for POST /api/auth/login endpoint."""

    def test_login_success(self, app_with_mocked_db, mock_token_response):
        """Test successful login."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.login.return_value = mock_token_response

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "correctpassword",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 3600

    def test_login_invalid_credentials(self, app_with_mocked_db):
        """Test login with invalid credentials returns 401."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.login.side_effect = InvalidCredentialsError(
            "Invalid email or password"
        )

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "WWW-Authenticate" in response.headers

    def test_login_inactive_user(self, app_with_mocked_db):
        """Test login with inactive user returns 403."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.login.side_effect = UserInactiveError(
            "User account is inactive"
        )

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/login",
            json={
                "email": "inactive@example.com",
                "password": "correctpassword",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_login_missing_email(self, app_with_mocked_db):
        """Test login without email returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/login",
            json={
                "password": "somepassword",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_missing_password(self, app_with_mocked_db):
        """Test login without password returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/login",
            json={
                "email": "test@example.com",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRefreshEndpoint:
    """Tests for POST /api/auth/refresh endpoint."""

    def test_refresh_success(self, app_with_mocked_db, mock_token_response):
        """Test successful token refresh."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.refresh_token.return_value = mock_token_response

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": "valid_refresh_token",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, app_with_mocked_db):
        """Test refresh with invalid token returns 401."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.refresh_token.side_effect = InvalidTokenError(
            "Invalid refresh token"
        )

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": "invalid_token",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "WWW-Authenticate" in response.headers

    def test_refresh_revoked_token(self, app_with_mocked_db):
        """Test refresh with revoked token returns 401."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.refresh_token.side_effect = TokenRevokedError(
            "Refresh token has been revoked"
        )

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": "revoked_token",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_inactive_user(self, app_with_mocked_db):
        """Test refresh for inactive user returns 403."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.refresh_token.side_effect = UserInactiveError(
            "User account is inactive"
        )

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/refresh",
            json={
                "refresh_token": "valid_token_inactive_user",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_refresh_missing_token(self, app_with_mocked_db):
        """Test refresh without token returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/refresh",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout endpoint."""

    def test_logout_success(self, app_with_mocked_db):
        """Test successful logout."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.logout.return_value = None

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/logout",
            json={
                "refresh_token": "valid_refresh_token",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Successfully logged out"

    def test_logout_with_invalid_token(self, app_with_mocked_db):
        """Test logout with invalid token still succeeds (idempotent)."""
        from src.modules.auth.router import get_auth_service

        mock_service = AsyncMock(spec=AuthService)
        mock_service.logout.return_value = None

        app_with_mocked_db.dependency_overrides[get_auth_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/logout",
            json={
                "refresh_token": "nonexistent_token",
            },
        )

        # Logout should be idempotent - always return success
        assert response.status_code == status.HTTP_200_OK

    def test_logout_missing_token(self, app_with_mocked_db):
        """Test logout without token returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/logout",
            json={},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_logout_empty_token(self, app_with_mocked_db):
        """Test logout with empty token returns 422."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.post(
            "/api/auth/logout",
            json={
                "refresh_token": "",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
