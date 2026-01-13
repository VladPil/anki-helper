"""AnkiConnect API client for communicating with Anki."""

import logging
from typing import Any, Optional

import httpx

from src.core.exceptions import AnkiConnectError

logger = logging.getLogger(__name__)


class AnkiConnectClient:
    """Client for interacting with Anki via the AnkiConnect addon.

    AnkiConnect is an Anki addon that exposes a REST API for external
    applications to interact with Anki. This client provides a typed
    interface to that API.

    Example:
        >>> client = AnkiConnectClient()
        >>> decks = client.get_deck_names()
        >>> client.add_note("MyDeck", "Basic", {"Front": "Q", "Back": "A"})
    """

    def __init__(self, url: str = "http://localhost:8765") -> None:
        """Initialize the AnkiConnect client.

        Args:
            url: URL of the AnkiConnect server.
        """
        self.url = url
        self.client = httpx.Client(timeout=30.0)

    def _invoke(self, action: str, **params: Any) -> Any:
        """Invoke an AnkiConnect action.

        Args:
            action: The AnkiConnect action name.
            **params: Parameters to pass to the action.

        Returns:
            The result from AnkiConnect.

        Raises:
            AnkiConnectError: If the request fails or returns an error.
        """
        payload: dict[str, Any] = {
            "action": action,
            "version": 6,
        }
        if params:
            payload["params"] = params

        try:
            response = self.client.post(self.url, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("error"):
                raise AnkiConnectError(result["error"])

            return result.get("result")

        except httpx.ConnectError:
            raise AnkiConnectError(
                "Cannot connect to AnkiConnect. Make sure Anki is running "
                "and AnkiConnect addon is installed."
            )
        except httpx.TimeoutException:
            raise AnkiConnectError("AnkiConnect request timed out.")
        except httpx.HTTPStatusError as e:
            raise AnkiConnectError(f"HTTP error: {e.response.status_code}")

    def get_version(self) -> int:
        """Get AnkiConnect version."""
        return self._invoke("version")

    def get_deck_names(self) -> list[str]:
        """Get list of all deck names."""
        return self._invoke("deckNames")

    def get_deck_names_and_ids(self) -> dict[str, int]:
        """Get mapping of deck names to IDs."""
        return self._invoke("deckNamesAndIds")

    def create_deck(self, deck_name: str) -> int:
        """Create a new deck.

        Args:
            deck_name: Name of the deck to create.

        Returns:
            The deck ID.
        """
        return self._invoke("createDeck", deck=deck_name)

    def get_model_names(self) -> list[str]:
        """Get list of all note model names."""
        return self._invoke("modelNames")

    def get_model_field_names(self, model_name: str) -> list[str]:
        """Get field names for a note model.

        Args:
            model_name: Name of the note model.

        Returns:
            List of field names.
        """
        return self._invoke("modelFieldNames", modelName=model_name)

    def get_cards_info(self, card_ids: list[int]) -> list[dict[str, Any]]:
        """Get detailed information for cards.

        Args:
            card_ids: List of card IDs.

        Returns:
            List of card info dictionaries.
        """
        return self._invoke("cardsInfo", cards=card_ids)

    def get_notes_info(self, note_ids: list[int]) -> list[dict[str, Any]]:
        """Get detailed information for notes.

        Args:
            note_ids: List of note IDs.

        Returns:
            List of note info dictionaries.
        """
        return self._invoke("notesInfo", notes=note_ids)

    def add_note(
        self,
        deck_name: str,
        model_name: str,
        fields: dict[str, str],
        tags: Optional[list[str]] = None,
        audio: Optional[list[dict[str, Any]]] = None,
        picture: Optional[list[dict[str, Any]]] = None,
        allow_duplicate: bool = False,
    ) -> int:
        """Add a new note to Anki.

        Args:
            deck_name: Name of the deck to add to.
            model_name: Name of the note model to use.
            fields: Dictionary of field name to field content.
            tags: List of tags to apply.
            audio: List of audio attachments.
            picture: List of picture attachments.
            allow_duplicate: Whether to allow duplicate notes.

        Returns:
            The ID of the created note.

        Raises:
            AnkiConnectError: If note creation fails.
        """
        note: dict[str, Any] = {
            "deckName": deck_name,
            "modelName": model_name,
            "fields": fields,
            "tags": tags or [],
            "options": {
                "allowDuplicate": allow_duplicate,
            },
        }

        if audio:
            note["audio"] = audio
        if picture:
            note["picture"] = picture

        return self._invoke("addNote", note=note)

    def add_notes(self, notes: list[dict[str, Any]]) -> list[Optional[int]]:
        """Add multiple notes to Anki.

        Args:
            notes: List of note dictionaries (same format as add_note).

        Returns:
            List of note IDs (None for failed additions).
        """
        return self._invoke("addNotes", notes=notes)

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> None:
        """Update fields of an existing note.

        Args:
            note_id: ID of the note to update.
            fields: New field values.
        """
        self._invoke("updateNoteFields", note={
            "id": note_id,
            "fields": fields,
        })

    def add_tags(self, note_ids: list[int], tags: str) -> None:
        """Add tags to notes.

        Args:
            note_ids: List of note IDs.
            tags: Space-separated tags to add.
        """
        self._invoke("addTags", notes=note_ids, tags=tags)

    def remove_tags(self, note_ids: list[int], tags: str) -> None:
        """Remove tags from notes.

        Args:
            note_ids: List of note IDs.
            tags: Space-separated tags to remove.
        """
        self._invoke("removeTags", notes=note_ids, tags=tags)

    def find_cards(self, query: str) -> list[int]:
        """Find cards matching a query.

        Args:
            query: Anki search query (e.g., "deck:MyDeck", "tag:mytag").

        Returns:
            List of matching card IDs.
        """
        return self._invoke("findCards", query=query)

    def find_notes(self, query: str) -> list[int]:
        """Find notes matching a query.

        Args:
            query: Anki search query.

        Returns:
            List of matching note IDs.
        """
        return self._invoke("findNotes", query=query)

    def delete_notes(self, note_ids: list[int]) -> None:
        """Delete notes by ID.

        Args:
            note_ids: List of note IDs to delete.
        """
        self._invoke("deleteNotes", notes=note_ids)

    def sync(self) -> None:
        """Trigger Anki sync with AnkiWeb."""
        self._invoke("sync")

    def gui_browse(self, query: str) -> list[int]:
        """Open the card browser with a search query.

        Args:
            query: Search query to use.

        Returns:
            List of card IDs shown.
        """
        return self._invoke("guiBrowse", query=query)

    def gui_current_card(self) -> Optional[dict[str, Any]]:
        """Get information about the current card in reviewer."""
        return self._invoke("guiCurrentCard")

    def gui_show_question(self) -> bool:
        """Show the question side of the current card."""
        return self._invoke("guiShowQuestion")

    def gui_show_answer(self) -> bool:
        """Show the answer side of the current card."""
        return self._invoke("guiShowAnswer")

    def request_permission(self) -> dict[str, Any]:
        """Request permission to use AnkiConnect."""
        return self._invoke("requestPermission")

    def store_media_file(
        self,
        filename: str,
        data: Optional[str] = None,
        url: Optional[str] = None,
        path: Optional[str] = None,
    ) -> str:
        """Store a media file in Anki's media folder.

        Args:
            filename: Name to save the file as.
            data: Base64-encoded file data.
            url: URL to download the file from.
            path: Local path to the file.

        Returns:
            The filename as stored.

        Raises:
            ValueError: If no data source is provided.
        """
        params: dict[str, str] = {"filename": filename}
        if data:
            params["data"] = data
        elif url:
            params["url"] = url
        elif path:
            params["path"] = path
        else:
            raise ValueError("Must provide data, url, or path")

        return self._invoke("storeMediaFile", **params)

    def get_deck_note_ids(self, deck_name: str) -> list[int]:
        """Get all note IDs in a deck.

        Args:
            deck_name: Name of the deck.

        Returns:
            List of note IDs.
        """
        return self.find_notes(f'deck:"{deck_name}"')

    def get_notes_info_batch(
        self,
        note_ids: list[int],
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Get note info in batches to avoid timeouts.

        Args:
            note_ids: List of note IDs.
            batch_size: Number of notes per batch.

        Yields:
            Note info dictionaries.
        """
        all_notes = []
        for i in range(0, len(note_ids), batch_size):
            batch = note_ids[i : i + batch_size]
            logger.debug(
                f"Fetching notes batch {i // batch_size + 1}, "
                f"notes {i + 1}-{min(i + batch_size, len(note_ids))} of {len(note_ids)}"
            )
            notes = self.get_notes_info(batch)
            all_notes.extend(notes)
        return all_notes

    def extract_card_data(self, note: dict[str, Any]) -> dict[str, Any] | None:
        """Extract card data from note info.

        Args:
            note: Note info dictionary.

        Returns:
            Card data dictionary or None if invalid.
        """
        if not note.get("noteId"):
            return None

        fields = note.get("fields", {})
        front = ""
        back = ""

        # Try common field names
        if "Front" in fields:
            front = fields["Front"].get("value", "")
        elif "Text" in fields:
            front = fields["Text"].get("value", "")
        elif fields:
            first_field = list(fields.values())[0]
            front = first_field.get("value", "")

        # Try common field names for back (case-sensitive, then fallback)
        back_field_names = [
            "Back", "back", "Answer", "answer", "Meaning", "meaning",
            "Extra", "Definition", "definition", "Response", "response",
        ]
        for name in back_field_names:
            if name in fields:
                back = fields[name].get("value", "")
                break
        else:
            # Fallback: use second field if exists
            if len(fields) > 1:
                second_field = list(fields.values())[1]
                back = second_field.get("value", "")

        return {
            "anki_note_id": note["noteId"],
            "front": front,
            "back": back,
            "tags": note.get("tags", []),
            "model": note.get("modelName", "Basic"),
        }

    def get_all_decks_with_cards(self) -> dict[str, list[dict[str, Any]]]:
        """Get all decks with their cards for import to AnkiRAG.

        Returns:
            Dictionary mapping deck names to list of card data.
        """
        result: dict[str, list[dict[str, Any]]] = {}

        decks = self.get_deck_names()
        logger.info(f"Found {len(decks)} decks in Anki")

        for deck_name in decks:
            # Skip default deck if empty
            if deck_name == "Default":
                logger.debug("Skipping Default deck")
                continue

            # Find all notes in deck
            logger.debug(f"Getting notes for deck: {deck_name}")
            note_ids = self.find_notes(f'deck:"{deck_name}"')

            if not note_ids:
                logger.debug(f"No notes in deck: {deck_name}")
                continue

            logger.info(f"Deck '{deck_name}': {len(note_ids)} notes found")

            # Get note details in batches
            notes_info = self.get_notes_info_batch(note_ids)

            cards_data = []
            for note in notes_info:
                card_data = self.extract_card_data(note)
                if card_data:
                    cards_data.append(card_data)

            if cards_data:
                result[deck_name] = cards_data
                logger.info(f"Deck '{deck_name}': {len(cards_data)} cards extracted")

        logger.info(f"Total: {len(result)} decks with cards ready for import")
        return result

    def iter_deck_cards(
        self,
        deck_name: str,
        batch_size: int = 100,
    ):
        """Iterate over cards in a deck in batches.

        Args:
            deck_name: Name of the deck.
            batch_size: Number of notes to process per batch.

        Yields:
            Tuples of (batch_index, total_batches, list of card data).
        """
        note_ids = self.find_notes(f'deck:"{deck_name}"')

        if not note_ids:
            return

        total_batches = (len(note_ids) + batch_size - 1) // batch_size
        logger.info(
            f"Deck '{deck_name}': {len(note_ids)} notes, {total_batches} batches"
        )

        for i in range(0, len(note_ids), batch_size):
            batch_ids = note_ids[i : i + batch_size]
            batch_index = i // batch_size

            logger.debug(
                f"Processing batch {batch_index + 1}/{total_batches} "
                f"({len(batch_ids)} notes)"
            )

            notes_info = self.get_notes_info(batch_ids)
            cards_data = []

            for note in notes_info:
                card_data = self.extract_card_data(note)
                if card_data:
                    cards_data.append(card_data)

            yield batch_index, total_batches, cards_data

    def get_deck_stats(self) -> dict[str, dict[str, int]]:
        """Get statistics for all decks.

        Returns:
            Dictionary mapping deck names to stats (card count, etc.)
        """
        stats = {}
        decks = self.get_deck_names()

        for deck_name in decks:
            try:
                card_ids = self.find_cards(f'deck:"{deck_name}"')
                note_ids = self.find_notes(f'deck:"{deck_name}"')
                stats[deck_name] = {
                    "card_count": len(card_ids),
                    "note_count": len(note_ids),
                }
            except AnkiConnectError:
                stats[deck_name] = {"card_count": 0, "note_count": 0}

        return stats

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self) -> "AnkiConnectClient":
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        self.close()
