"""Backend API client for communicating with AnkiRAG server."""

import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from src.core.exceptions import APIError
from src.core.models import CardData, SyncStatus

logger = logging.getLogger(__name__)


class BackendAPIClient:
    """Client for interacting with the AnkiRAG backend API.

    Handles authentication, card retrieval, and sync status reporting.

    Example:
        >>> client = BackendAPIClient("https://api.ankirag.com", "my-token")
        >>> cards = client.get_approved_cards(limit=100)
        >>> client.update_sync_status(card_id, anki_note_id, "synced")
    """

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        """Initialize the API client.

        Args:
            base_url: Base URL of the AnkiRAG API.
            token: Authentication token.
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = httpx.Client(timeout=30.0)

    def _get_headers(self) -> dict[str, str]:
        """Get request headers including authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Make an API request.

        Args:
            method: HTTP method.
            endpoint: API endpoint (without base URL).
            data: Request body data.
            params: Query parameters.

        Returns:
            Response JSON data.

        Raises:
            APIError: If the request fails.
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.client.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=self._get_headers(),
            )

            if response.status_code == 401:
                raise APIError("Authentication failed. Please login again.", 401)
            elif response.status_code == 403:
                raise APIError("Permission denied.", 403)
            elif response.status_code == 404:
                raise APIError("Resource not found.", 404)
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                    message = error_data.get("detail", str(error_data))
                except Exception:
                    message = response.text or f"HTTP {response.status_code}"
                raise APIError(message, response.status_code)

            if response.status_code == 204:
                return None

            return response.json()

        except httpx.ConnectError:
            raise APIError(
                f"Cannot connect to API at {self.base_url}. "
                "Please check the server is running."
            )
        except httpx.TimeoutException:
            raise APIError("API request timed out.")

    def verify_token(self) -> bool:
        """Verify that the current token is valid.

        Returns:
            True if token is valid, False otherwise.
        """
        try:
            self._request("GET", "/api/auth/verify")
            return True
        except APIError as e:
            if e.status_code in (401, 403):
                return False
            raise

    def get_user_info(self) -> dict[str, Any]:
        """Get current user information."""
        return self._request("GET", "/api/auth/me")

    def get_approved_cards(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CardData]:
        """Get approved cards ready for sync to Anki.

        Args:
            since: Only get cards approved after this time.
            limit: Maximum number of cards to return.
            offset: Offset for pagination.

        Returns:
            List of approved cards.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if since:
            params["since"] = since.isoformat()

        response = self._request("GET", "/api/cards/approved", params=params)
        return [CardData(**card) for card in response.get("cards", [])]

    def get_pending_cards(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CardData]:
        """Get cards pending approval.

        Args:
            limit: Maximum number of cards to return.
            offset: Offset for pagination.

        Returns:
            List of pending cards.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        response = self._request("GET", "/api/cards/pending", params=params)
        return [CardData(**card) for card in response.get("cards", [])]

    def get_card(self, card_id: str) -> CardData:
        """Get a specific card by ID.

        Args:
            card_id: Backend card ID.

        Returns:
            Card data.
        """
        response = self._request("GET", f"/api/cards/{card_id}")
        return CardData(**response)

    def update_sync_status(
        self,
        card_id: str,
        anki_note_id: int,
        status: str = "synced",
        error_message: Optional[str] = None,
    ) -> None:
        """Update the sync status of a card in the backend.

        Args:
            card_id: Backend card ID.
            anki_note_id: Anki note ID.
            status: Sync status ("synced", "error", "conflict").
            error_message: Error message if sync failed.
        """
        data: dict[str, Any] = {
            "anki_note_id": anki_note_id,
            "status": status,
            "synced_at": datetime.utcnow().isoformat(),
        }
        if error_message:
            data["error_message"] = error_message

        self._request("POST", f"/api/cards/{card_id}/sync-status", data=data)

    def bulk_update_sync_status(self, statuses: list[SyncStatus]) -> None:
        """Bulk update sync statuses for multiple cards.

        Args:
            statuses: List of sync status updates.
        """
        data = {"statuses": [s.model_dump() for s in statuses]}
        self._request("POST", "/api/cards/sync-status/bulk", data=data)

    def get_sync_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent sync history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of sync history entries.
        """
        return self._request("GET", "/api/sync/history", params={"limit": limit})

    def report_sync_complete(
        self,
        cards_synced: int,
        cards_failed: int,
        errors: Optional[list[str]] = None,
    ) -> None:
        """Report sync completion to the backend.

        Args:
            cards_synced: Number of cards successfully synced.
            cards_failed: Number of cards that failed to sync.
            errors: List of error messages.
        """
        self._request("POST", "/api/sync/complete", data={
            "cards_synced": cards_synced,
            "cards_failed": cards_failed,
            "errors": errors or [],
            "completed_at": datetime.utcnow().isoformat(),
        })

    def get_decks(self) -> list[dict[str, Any]]:
        """Get user's configured decks."""
        return self._request("GET", "/api/decks")

    def get_settings(self) -> dict[str, Any]:
        """Get user's sync settings from backend."""
        return self._request("GET", "/api/settings")

    def update_settings(self, settings: dict[str, Any]) -> dict[str, Any]:
        """Update user's sync settings.

        Args:
            settings: New settings values.

        Returns:
            Updated settings.
        """
        return self._request("PUT", "/api/settings", data=settings)

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "BackendAPIClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()
