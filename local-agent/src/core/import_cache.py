"""Import cache for tracking imported card IDs.

This allows resuming imports after crashes by skipping already imported cards.
"""

import json
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


class ImportCache:
    """Cache for tracking imported Anki note IDs.

    Stores imported note IDs in a JSON file to allow resuming
    interrupted imports without re-importing already imported cards.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize the import cache.

        Args:
            cache_dir: Directory for cache files. Defaults to local-agent/data.
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent / "data"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "imported_notes.json"
        self._imported_ids: Set[int] = set()
        self._load()

    def _load(self) -> None:
        """Load cached IDs from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    data = json.load(f)
                    self._imported_ids = set(data.get("imported_note_ids", []))
                logger.info(f"Loaded {len(self._imported_ids)} imported note IDs from cache")
            except Exception as e:
                logger.warning(f"Failed to load import cache: {e}")
                self._imported_ids = set()

    def _save(self) -> None:
        """Save cached IDs to file."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(
                    {"imported_note_ids": list(self._imported_ids)},
                    f,
                    indent=2,
                )
            logger.debug(f"Saved {len(self._imported_ids)} imported note IDs to cache")
        except Exception as e:
            logger.error(f"Failed to save import cache: {e}")

    def is_imported(self, note_id: int) -> bool:
        """Check if a note ID has been imported.

        Args:
            note_id: Anki note ID.

        Returns:
            True if already imported.
        """
        return note_id in self._imported_ids

    def mark_imported(self, note_ids: list[int]) -> None:
        """Mark note IDs as imported.

        Args:
            note_ids: List of Anki note IDs.
        """
        self._imported_ids.update(note_ids)
        self._save()

    def filter_not_imported(self, cards: list[dict]) -> list[dict]:
        """Filter out already imported cards.

        Args:
            cards: List of card data dicts with 'anki_note_id' key.

        Returns:
            List of cards not yet imported.
        """
        return [
            c for c in cards
            if c.get("anki_note_id") and c["anki_note_id"] not in self._imported_ids
        ]

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats.
        """
        return {
            "total_imported": len(self._imported_ids),
            "cache_file": str(self.cache_file),
        }

    def clear(self) -> None:
        """Clear all cached IDs."""
        self._imported_ids = set()
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("Import cache cleared")


# Global instance
import_cache = ImportCache()
