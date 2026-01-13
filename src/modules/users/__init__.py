"""Users module - user management and preferences."""

from .models import User, UserPreferences
from .schemas import (
    UserCreate,
    UserListResponse,
    UserPreferencesCreate,
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserResponse,
    UserUpdate,
)
from .service import (
    UserAlreadyExistsError,
    UserNotFoundError,
    UserService,
    UserServiceError,
)

# Note: router is not imported here to avoid circular imports
# Import it directly: from src.modules.users.router import router

__all__ = [
    "User",
    "UserAlreadyExistsError",
    "UserCreate",
    "UserListResponse",
    "UserNotFoundError",
    "UserPreferences",
    "UserPreferencesCreate",
    "UserPreferencesResponse",
    "UserPreferencesUpdate",
    "UserResponse",
    "UserService",
    "UserServiceError",
    "UserUpdate",
]
