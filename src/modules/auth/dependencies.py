"""FastAPI dependencies for authentication."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.modules.users.models import User

from .service import AuthService, InvalidTokenError, UserInactiveError

# HTTP Bearer token security scheme
security = HTTPBearer(auto_error=True)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    """Dependency to get AuthService instance."""
    return AuthService(session)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    """Dependency to get the current authenticated user.

    Extracts the JWT token from the Authorization header and validates it.

    Args:
        credentials: HTTP Bearer credentials from the Authorization header.
        auth_service: AuthService instance.

    Returns:
        The authenticated User object.

    Raises:
        HTTPException: 401 if token is invalid or user not found.
    """
    try:
        user = await auth_service.get_user_from_token(credentials.credentials)
        return user
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except UserInactiveError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Dependency to get the current active user.

    Ensures the user account is active.

    Args:
        current_user: The authenticated user from get_current_user.

    Returns:
        The active User object.

    Raises:
        HTTPException: 403 if user is inactive.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return current_user


async def get_optional_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User | None:
    """Dependency to optionally get the current user.

    Returns None if no token is provided or token is invalid.
    Useful for endpoints that work for both authenticated and anonymous users.

    Args:
        credentials: Optional HTTP Bearer credentials.
        auth_service: AuthService instance.

    Returns:
        The User object if authenticated, None otherwise.
    """
    if credentials is None:
        return None

    try:
        return await auth_service.get_user_from_token(credentials.credentials)
    except (InvalidTokenError, UserInactiveError):
        return None


async def require_admin(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """Dependency to require admin privileges.

    Currently checks if the user has admin role or is a superuser.
    Placeholder implementation - extend based on your authorization model.

    Args:
        current_user: The authenticated active user.

    Returns:
        The admin User object.

    Raises:
        HTTPException: 403 if user is not an admin.
    """
    # TODO: Implement proper admin check based on your authorization model
    # For now, this is a placeholder that allows all authenticated users
    # In production, you should check for admin role or is_superuser flag
    #
    # Example implementation:
    # if not current_user.is_superuser and "admin" not in current_user.roles:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Admin privileges required",
    #     )
    return current_user
