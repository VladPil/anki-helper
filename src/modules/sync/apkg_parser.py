"""Parser for Anki .apkg files.

The .apkg format is a ZIP archive containing:
- collection.anki2: SQLite database with cards, notes, decks, and models
- media: JSON mapping of media file names to actual files
- media files (numbered)

Database schema (simplified):
- col: Collection metadata (models, decks, tags)
- notes: Note data (id, guid, mid, tags, flds, sfld)
- cards: Card data (id, nid, did, ord, type, queue)
- revlog: Review history

Models (note types) are stored as JSON in col.models
Decks are stored as JSON in col.decks
"""

import json
import logging
import sqlite3
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ParsedNoteType:
    """Parsed note type (model) from .apkg file.

    Attributes:
        id: Note type ID.
        name: Note type name.
        fields: List of field names.
        templates: List of card templates.
        css: CSS styling for cards.
    """

    id: str
    name: str
    fields: list[str] = field(default_factory=list)
    templates: list[dict[str, Any]] = field(default_factory=list)
    css: str = ""


@dataclass
class ParsedCard:
    """Parsed card from .apkg file.

    Attributes:
        note_id: Original note ID.
        card_id: Original card ID.
        front: Card front content.
        back: Card back content.
        tags: List of tags.
        note_type: Note type name.
        deck_name: Deck name.
        fields: All field values.
        due: Due date/position.
        interval: Review interval.
        ease_factor: Ease factor.
        reviews: Number of reviews.
        lapses: Number of lapses.
    """

    note_id: str
    card_id: str
    front: str
    back: str
    tags: list[str] = field(default_factory=list)
    note_type: str = "Basic"
    deck_name: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    due: int = 0
    interval: int = 0
    ease_factor: int = 2500
    reviews: int = 0
    lapses: int = 0


@dataclass
class ParsedDeck:
    """Parsed deck from .apkg file.

    Attributes:
        name: Deck name.
        description: Deck description.
        cards: List of parsed cards.
        note_types: List of note types used.
        media_files: Mapping of media file names.
    """

    name: str
    description: str = ""
    cards: list[ParsedCard] = field(default_factory=list)
    note_types: list[ParsedNoteType] = field(default_factory=list)
    media_files: dict[str, str] = field(default_factory=dict)


class ApkgParseError(Exception):
    """Error parsing .apkg file."""

    pass


class ApkgParser:
    """Parser for Anki .apkg files.

    This parser extracts cards, notes, decks, and media from .apkg files.
    It supports both Anki 2.0 and 2.1 formats.

    Example:
        parser = ApkgParser()
        deck = await parser.parse(Path("my_deck.apkg"))
        for card in deck.cards:
            print(f"{card.front} -> {card.back}")
    """

    # Field separator in notes table
    FIELD_SEPARATOR = "\x1f"

    def __init__(self) -> None:
        """Initialize the parser."""
        self._models: dict[str, ParsedNoteType] = {}
        self._decks: dict[str, str] = {}

    async def parse(self, file_path: Path) -> ParsedDeck:
        """Parse an .apkg file.

        Args:
            file_path: Path to the .apkg file.

        Returns:
            ParsedDeck containing all cards and metadata.

        Raises:
            ApkgParseError: If the file cannot be parsed.
        """
        if not file_path.exists():
            raise ApkgParseError(f"File not found: {file_path}")

        if not zipfile.is_zipfile(file_path):
            raise ApkgParseError(f"Not a valid .apkg file: {file_path}")

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            try:
                # Extract the archive
                with zipfile.ZipFile(file_path, "r") as zf:
                    zf.extractall(tmp_path)

                # Find the database file
                db_path = self._find_database(tmp_path)
                if db_path is None:
                    raise ApkgParseError("No database found in .apkg file")

                # Parse media mapping
                media_files = self._parse_media_mapping(tmp_path)

                # Parse the database
                return self._parse_database(db_path, media_files)

            except sqlite3.Error as e:
                raise ApkgParseError(f"Database error: {e}") from e
            except json.JSONDecodeError as e:
                raise ApkgParseError(f"JSON parsing error: {e}") from e
            except Exception as e:
                raise ApkgParseError(f"Failed to parse .apkg: {e}") from e

    def _find_database(self, extract_path: Path) -> Path | None:
        """Find the database file in the extracted archive.

        Anki 2.0 uses collection.anki2
        Anki 2.1 uses collection.anki21

        Args:
            extract_path: Path to extracted archive.

        Returns:
            Path to database file, or None if not found.
        """
        # Try Anki 2.1 format first
        db_path = extract_path / "collection.anki21"
        if db_path.exists():
            return db_path

        # Fall back to Anki 2.0 format
        db_path = extract_path / "collection.anki2"
        if db_path.exists():
            return db_path

        return None

    def _parse_media_mapping(self, extract_path: Path) -> dict[str, str]:
        """Parse the media mapping file.

        Args:
            extract_path: Path to extracted archive.

        Returns:
            Mapping of numbered files to original names.
        """
        media_path = extract_path / "media"
        if not media_path.exists():
            return {}

        try:
            with open(media_path, encoding="utf-8") as f:
                result: dict[str, str] = json.load(f)
                return result
        except (OSError, json.JSONDecodeError):
            return {}

    def _parse_database(
        self,
        db_path: Path,
        media_files: dict[str, str],
    ) -> ParsedDeck:
        """Parse the SQLite database.

        Args:
            db_path: Path to the database file.
            media_files: Media file mapping.

        Returns:
            ParsedDeck with all data.
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        try:
            # Get collection metadata
            cursor = conn.execute("SELECT models, decks FROM col")
            row = cursor.fetchone()

            if row is None:
                raise ApkgParseError("Empty collection")

            # Parse models (note types)
            models_json = json.loads(row["models"])
            self._models = self._parse_models(models_json)

            # Parse decks
            decks_json = json.loads(row["decks"])
            self._decks = self._parse_decks(decks_json)

            # Get deck name (use the first non-default deck)
            deck_name = "Imported Deck"
            for deck_id, name in self._decks.items():
                if name != "Default":
                    deck_name = name
                    break

            # Parse notes and cards
            cards = self._parse_cards(conn)

            return ParsedDeck(
                name=deck_name,
                cards=cards,
                note_types=list(self._models.values()),
                media_files=media_files,
            )

        finally:
            conn.close()

    def _parse_models(self, models_json: dict[str, Any]) -> dict[str, ParsedNoteType]:
        """Parse note types (models) from JSON.

        Args:
            models_json: Models JSON from col table.

        Returns:
            Mapping of model ID to ParsedNoteType.
        """
        models = {}

        for model_id, model_data in models_json.items():
            fields = [f["name"] for f in model_data.get("flds", [])]
            templates = model_data.get("tmpls", [])
            css = model_data.get("css", "")

            models[model_id] = ParsedNoteType(
                id=model_id,
                name=model_data.get("name", "Unknown"),
                fields=fields,
                templates=templates,
                css=css,
            )

        return models

    def _parse_decks(self, decks_json: dict[str, Any]) -> dict[str, str]:
        """Parse decks from JSON.

        Args:
            decks_json: Decks JSON from col table.

        Returns:
            Mapping of deck ID to deck name.
        """
        decks = {}

        for deck_id, deck_data in decks_json.items():
            decks[deck_id] = deck_data.get("name", "Unknown")

        return decks

    def _parse_cards(self, conn: sqlite3.Connection) -> list[ParsedCard]:
        """Parse cards from the database.

        Args:
            conn: Database connection.

        Returns:
            List of ParsedCard objects.
        """
        cards = []

        # Query notes with their cards
        query = """
            SELECT
                n.id as note_id,
                n.mid as model_id,
                n.tags as tags,
                n.flds as fields,
                n.sfld as sort_field,
                c.id as card_id,
                c.did as deck_id,
                c.ord as card_ord,
                c.due as due,
                c.ivl as interval,
                c.factor as ease_factor,
                c.reps as reviews,
                c.lapses as lapses
            FROM notes n
            JOIN cards c ON c.nid = n.id
            ORDER BY n.id, c.ord
        """

        cursor = conn.execute(query)

        for row in cursor:
            try:
                card = self._create_card_from_row(row)
                if card:
                    cards.append(card)
            except Exception as e:
                logger.warning("Failed to parse card %s: %s", row["card_id"], e)

        return cards

    def _create_card_from_row(self, row: sqlite3.Row) -> ParsedCard | None:
        """Create a ParsedCard from a database row.

        Args:
            row: Database row.

        Returns:
            ParsedCard or None if parsing fails.
        """
        model_id = str(row["model_id"])
        model = self._models.get(model_id)

        if model is None:
            logger.warning("Unknown model ID: %s", model_id)
            return None

        # Parse fields
        field_values = row["fields"].split(self.FIELD_SEPARATOR)
        fields_dict = {}

        for i, field_name in enumerate(model.fields):
            if i < len(field_values):
                fields_dict[field_name] = field_values[i]
            else:
                fields_dict[field_name] = ""

        # Get front and back content
        front, back = self._render_card(model, fields_dict, row["card_ord"])

        # Parse tags
        tags = row["tags"].strip().split() if row["tags"] else []

        # Get deck name
        deck_id = str(row["deck_id"])
        deck_name = self._decks.get(deck_id, "Default")

        return ParsedCard(
            note_id=str(row["note_id"]),
            card_id=str(row["card_id"]),
            front=front,
            back=back,
            tags=tags,
            note_type=model.name,
            deck_name=deck_name,
            fields=fields_dict,
            due=row["due"] or 0,
            interval=row["interval"] or 0,
            ease_factor=row["ease_factor"] or 2500,
            reviews=row["reviews"] or 0,
            lapses=row["lapses"] or 0,
        )

    def _render_card(
        self,
        model: ParsedNoteType,
        fields: dict[str, str],
        card_ord: int,
    ) -> tuple[str, str]:
        """Render card front and back from template.

        For simplicity, this does basic field substitution.
        A full implementation would use Anki's template engine.

        Args:
            model: Note type.
            fields: Field values.
            card_ord: Card ordinal (template index).

        Returns:
            Tuple of (front, back) content.
        """
        # Get template for this card
        if card_ord < len(model.templates):
            template = model.templates[card_ord]
        else:
            # Fall back to first template
            template = model.templates[0] if model.templates else {}

        front_template = template.get("qfmt", "{{Front}}")
        back_template = template.get("afmt", "{{Back}}")

        # Simple field substitution
        front = self._substitute_fields(front_template, fields)
        back = self._substitute_fields(back_template, fields)

        # Handle {{FrontSide}} in back template
        back = back.replace("{{FrontSide}}", front)

        # Strip HTML for plain text (optional, keep HTML for now)
        # front = self._strip_html(front)
        # back = self._strip_html(back)

        return front, back

    def _substitute_fields(self, template: str, fields: dict[str, str]) -> str:
        """Substitute field placeholders in template.

        Handles:
        - {{FieldName}} - simple substitution
        - {{#FieldName}}...{{/FieldName}} - conditional (if field non-empty)
        - {{^FieldName}}...{{/FieldName}} - conditional (if field empty)
        - {{cloze:FieldName}} - cloze deletion

        Args:
            template: Template string.
            fields: Field values.

        Returns:
            Rendered string.
        """
        import re

        result = template

        # Handle simple field substitution
        for field_name, field_value in fields.items():
            # Standard substitution
            result = result.replace(f"{{{{{field_name}}}}}", field_value)

            # With hint
            result = result.replace(f"{{{{hint:{field_name}}}}}", field_value)

            # With type (for input fields)
            result = result.replace(f"{{{{type:{field_name}}}}}", "")

            # Cloze
            result = result.replace(f"{{{{cloze:{field_name}}}}}", field_value)

        # Handle conditionals (simplified)
        # {{#Field}}content{{/Field}} - show if Field is non-empty
        conditional_pattern = r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}"
        for match in re.finditer(conditional_pattern, result, re.DOTALL):
            field_name = match.group(1)
            content = match.group(2)
            if fields.get(field_name, "").strip():
                result = result.replace(match.group(0), content)
            else:
                result = result.replace(match.group(0), "")

        # {{^Field}}content{{/Field}} - show if Field is empty
        inverse_pattern = r"\{\{\^(\w+)\}\}(.*?)\{\{/\1\}\}"
        for match in re.finditer(inverse_pattern, result, re.DOTALL):
            field_name = match.group(1)
            content = match.group(2)
            if not fields.get(field_name, "").strip():
                result = result.replace(match.group(0), content)
            else:
                result = result.replace(match.group(0), "")

        return result

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags from string.

        Args:
            html: HTML string.

        Returns:
            Plain text string.
        """
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html)

        # Decode HTML entities
        import html as html_module

        text = html_module.unescape(text)

        return text.strip()

    async def get_media_file(
        self,
        file_path: Path,
        media_name: str,
    ) -> bytes | None:
        """Extract a media file from the .apkg.

        Args:
            file_path: Path to the .apkg file.
            media_name: Name of the media file.

        Returns:
            File content as bytes, or None if not found.
        """
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # Read media mapping
                try:
                    media_data = zf.read("media")
                    media_map = json.loads(media_data)
                except (KeyError, json.JSONDecodeError):
                    return None

                # Find the numbered file for this media name
                numbered_name = None
                for num, name in media_map.items():
                    if name == media_name:
                        numbered_name = num
                        break

                if numbered_name is None:
                    return None

                # Read the file
                try:
                    return zf.read(numbered_name)
                except KeyError:
                    return None

        except (OSError, zipfile.BadZipFile):
            return None
