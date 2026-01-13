"""Core business logic and domain models."""

from src.core.exceptions import AnkiConnectError, APIError
from src.core.models import CardData, SyncResult, SyncStatus

__all__ = [
    "AnkiConnectError",
    "APIError",
    "CardData",
    "SyncResult",
    "SyncStatus",
]


def get_sync_service():
    """Lazy import to avoid circular dependency."""
    from src.core.sync_service import SyncService
    return SyncService
