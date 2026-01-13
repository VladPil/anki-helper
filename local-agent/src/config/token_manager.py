"""Secure token management using system keyring."""

from typing import Optional

import keyring

# Keyring service name for secure credential storage
KEYRING_SERVICE = "ankirag-agent"
KEYRING_TOKEN_KEY = "api_token"


class TokenManager:
    """Secure API token storage using the system keyring.

    Uses the operating system's secure credential storage
    (Keychain on macOS, Secret Service on Linux, Credential Locker on Windows).
    """

    @staticmethod
    def get_token() -> Optional[str]:
        """Retrieve the API token from secure storage.

        Returns:
            The stored token, or None if not found or on error.
        """
        try:
            return keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
        except Exception:
            return None

    @staticmethod
    def set_token(token: str) -> bool:
        """Store the API token in secure storage.

        Args:
            token: The API token to store.

        Returns:
            True if successful, False on error.
        """
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY, token)
            return True
        except Exception:
            return False

    @staticmethod
    def delete_token() -> bool:
        """Remove the API token from secure storage.

        Returns:
            True if successful or token didn't exist, False on error.
        """
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
            return True
        except keyring.errors.PasswordDeleteError:
            # Token doesn't exist, which is fine
            return True
        except Exception:
            return False

    @staticmethod
    def has_token() -> bool:
        """Check if a token is stored.

        Returns:
            True if a token exists in storage.
        """
        return TokenManager.get_token() is not None


# Global token manager instance
token_manager = TokenManager()
