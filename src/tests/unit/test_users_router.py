"""Unit tests for users router endpoints."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import status
from fastapi.testclient import TestClient

from src.modules.users.service import UserAlreadyExistsError, UserService


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
    user.deleted_at = None

    # Mock preferences
    preferences = MagicMock()
    preferences.id = uuid4()
    preferences.user_id = user.id
    preferences.preferred_language = "en"
    preferences.default_model_id = None
    preferences.default_embedder_id = None
    preferences.created_at = datetime.utcnow()
    preferences.updated_at = datetime.utcnow()
    user.preferences = preferences

    return user


@pytest.fixture
def mock_preferences():
    """Create a mock user preferences object."""
    preferences = MagicMock()
    preferences.id = uuid4()
    preferences.user_id = uuid4()
    preferences.preferred_language = "ru"
    preferences.default_model_id = None
    preferences.default_embedder_id = None
    preferences.created_at = datetime.utcnow()
    preferences.updated_at = datetime.utcnow()
    return preferences


@pytest.fixture
def app_with_mocked_db():
    """Create app with mocked database dependency."""
    from src.main import create_app
    from src.core.database import get_db

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_get_db

    yield app

    app.dependency_overrides.clear()


class TestGetMeEndpoint:
    """Tests for GET /api/v1/users/me endpoint."""

    def test_get_me_success(self, app_with_mocked_db, mock_user):
        """Test getting current user profile."""
        from src.modules.auth.dependencies import get_current_active_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == mock_user.email
        assert data["display_name"] == mock_user.display_name
        assert data["is_active"] == mock_user.is_active
        assert "id" in data

    def test_get_me_unauthorized(self, app_with_mocked_db):
        """Test getting current user without authentication returns 401/403."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/v1/users/me")

        # Should return unauthorized (401) or forbidden (403) without auth
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_get_me_includes_preferences(self, app_with_mocked_db, mock_user):
        """Test that get_me includes user preferences."""
        from src.modules.auth.dependencies import get_current_active_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.get("/api/v1/users/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Preferences should be included if present
        if mock_user.preferences:
            assert "preferences" in data or data.get("preferences") is not None


class TestUpdateMeEndpoint:
    """Tests for PATCH /api/v1/users/me endpoint."""

    def test_update_me_display_name(self, app_with_mocked_db, mock_user):
        """Test updating current user's display name."""
        from src.modules.auth.dependencies import get_current_active_user
        from src.modules.users.router import get_user_service

        updated_user = MagicMock()
        updated_user.id = mock_user.id
        updated_user.email = mock_user.email
        updated_user.display_name = "Updated Name"
        updated_user.is_active = True
        updated_user.created_at = mock_user.created_at
        updated_user.updated_at = datetime.utcnow()
        updated_user.preferences = mock_user.preferences

        mock_service = AsyncMock(spec=UserService)
        mock_service.update.return_value = updated_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user
        app_with_mocked_db.dependency_overrides[get_user_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={"display_name": "Updated Name"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["display_name"] == "Updated Name"

    def test_update_me_email(self, app_with_mocked_db, mock_user):
        """Test updating current user's email."""
        from src.modules.auth.dependencies import get_current_active_user
        from src.modules.users.router import get_user_service

        updated_user = MagicMock()
        updated_user.id = mock_user.id
        updated_user.email = "newemail@example.com"
        updated_user.display_name = mock_user.display_name
        updated_user.is_active = True
        updated_user.created_at = mock_user.created_at
        updated_user.updated_at = datetime.utcnow()
        updated_user.preferences = mock_user.preferences

        mock_service = AsyncMock(spec=UserService)
        mock_service.update.return_value = updated_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user
        app_with_mocked_db.dependency_overrides[get_user_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={"email": "newemail@example.com"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "newemail@example.com"

    def test_update_me_email_already_exists(self, app_with_mocked_db, mock_user):
        """Test updating email to existing email returns 409."""
        from src.modules.auth.dependencies import get_current_active_user
        from src.modules.users.router import get_user_service

        mock_service = AsyncMock(spec=UserService)
        mock_service.update.side_effect = UserAlreadyExistsError(
            "User with email existing@example.com already exists"
        )

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user
        app_with_mocked_db.dependency_overrides[get_user_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={"email": "existing@example.com"},
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_update_me_password(self, app_with_mocked_db, mock_user):
        """Test updating current user's password."""
        from src.modules.auth.dependencies import get_current_active_user
        from src.modules.users.router import get_user_service

        updated_user = MagicMock()
        updated_user.id = mock_user.id
        updated_user.email = mock_user.email
        updated_user.display_name = mock_user.display_name
        updated_user.is_active = True
        updated_user.created_at = mock_user.created_at
        updated_user.updated_at = datetime.utcnow()
        updated_user.preferences = mock_user.preferences

        mock_service = AsyncMock(spec=UserService)
        mock_service.update.return_value = updated_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user
        app_with_mocked_db.dependency_overrides[get_user_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={"password": "newpassword123"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_service.update.assert_called_once()

    def test_update_me_invalid_email(self, app_with_mocked_db, mock_user):
        """Test updating with invalid email returns 422."""
        from src.modules.auth.dependencies import get_current_active_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={"email": "invalid-email"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_me_short_password(self, app_with_mocked_db, mock_user):
        """Test updating with short password returns 422."""
        from src.modules.auth.dependencies import get_current_active_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={"password": "short"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_update_me_unauthorized(self, app_with_mocked_db):
        """Test updating profile without authentication returns 401/403."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={"display_name": "New Name"},
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_update_me_empty_body(self, app_with_mocked_db, mock_user):
        """Test updating with empty body succeeds (no changes)."""
        from src.modules.auth.dependencies import get_current_active_user
        from src.modules.users.router import get_user_service

        mock_service = AsyncMock(spec=UserService)
        mock_service.update.return_value = mock_user

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user
        app_with_mocked_db.dependency_overrides[get_user_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me",
            json={},
        )

        assert response.status_code == status.HTTP_200_OK


class TestUpdateMePreferencesEndpoint:
    """Tests for PATCH /api/v1/users/me/preferences endpoint."""

    def test_update_preferences_language(self, app_with_mocked_db, mock_user, mock_preferences):
        """Test updating user preferences language."""
        from src.modules.auth.dependencies import get_current_active_user
        from src.modules.users.router import get_user_service

        mock_preferences.preferred_language = "ru"
        mock_service = AsyncMock(spec=UserService)
        mock_service.update_preferences.return_value = mock_preferences

        app_with_mocked_db.dependency_overrides[get_current_active_user] = lambda: mock_user
        app_with_mocked_db.dependency_overrides[get_user_service] = lambda: mock_service

        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_language": "ru"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["preferred_language"] == "ru"

    def test_update_preferences_unauthorized(self, app_with_mocked_db):
        """Test updating preferences without auth returns 401/403."""
        client = TestClient(app_with_mocked_db, raise_server_exceptions=False)

        response = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_language": "ru"},
        )

        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]
