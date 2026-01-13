"""Authentication module - JWT-based authentication and authorization."""

from .dependencies import (
    get_auth_service,
    get_current_active_user,
    get_current_user,
    get_optional_current_user,
    require_admin,
)
from .models import RefreshToken
from .schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from .service import (
    AuthService,
    AuthServiceError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenRevokedError,
    UserInactiveError,
)

__all__ = [
    # Models
    "RefreshToken",
    # Schemas
    "LoginRequest",
    "MessageResponse",
    "RefreshRequest",
    "RegisterRequest",
    "TokenResponse",
    # Service
    "AuthService",
    "AuthServiceError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "TokenRevokedError",
    "UserInactiveError",
    # Dependencies
    "get_auth_service",
    "get_current_active_user",
    "get_current_user",
    "get_optional_current_user",
    "require_admin",
    # Router
]
