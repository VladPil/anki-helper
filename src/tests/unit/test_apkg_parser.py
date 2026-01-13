"""Unit tests for ApkgParser.

Tests cover:
- parse_apkg - parsing .apkg file
- extract_cards - extracting cards from database
- extract_models - extracting note types (models)
- build_card_data - building card data from database rows

All file system and database operations are mocked.
"""

import json
import sqlite3
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

from src.modules.sync.apkg_parser import (
    ApkgParser,
    ApkgParseError,
    ParsedCard,
    ParsedDeck,
    ParsedNoteType,
)


# ==================== Fixtures ====================


@pytest.fixture
def parser() -> ApkgParser:
    """Create an ApkgParser instance."""
    return ApkgParser()


@pytest.fixture
def sample_models_json() -> dict:
    """Create sample models JSON as stored in Anki database."""
    return {
        "1234567890": {
            "name": "Basic",
            "flds": [
                {"name": "Front", "ord": 0},
                {"name": "Back", "ord": 1},
            ],
            "tmpls": [
                {
                    "name": "Card 1",
                    "qfmt": "{{Front}}",
                    "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
                }
            ],
            "css": ".card { font-family: arial; }",
        },
        "9876543210": {
            "name": "Basic (and reversed card)",
            "flds": [
                {"name": "Front", "ord": 0},
                {"name": "Back", "ord": 1},
            ],
            "tmpls": [
                {
                    "name": "Card 1",
                    "qfmt": "{{Front}}",
                    "afmt": "{{Back}}",
                },
                {
                    "name": "Card 2",
                    "qfmt": "{{Back}}",
                    "afmt": "{{Front}}",
                },
            ],
            "css": ".card { font-size: 20px; }",
        },
    }


@pytest.fixture
def sample_decks_json() -> dict:
    """Create sample decks JSON as stored in Anki database."""
    return {
        "1": {"name": "Default", "id": 1},
        "1234567890123": {"name": "My Test Deck", "id": 1234567890123},
        "9876543210987": {"name": "Another Deck", "id": 9876543210987},
    }


@pytest.fixture
def sample_media_json() -> dict:
    """Create sample media mapping JSON."""
    return {
        "0": "image1.png",
        "1": "audio.mp3",
        "2": "picture.jpg",
    }


def create_mock_apkg_file(
    models_json: dict | None = None,
    decks_json: dict | None = None,
    media_json: dict | None = None,
    notes_data: list | None = None,
    cards_data: list | None = None,
    db_filename: str = "collection.anki2",
) -> BytesIO:
    """Create a mock .apkg file (ZIP with SQLite database).

    Args:
        models_json: Note types/models JSON
        decks_json: Decks JSON
        media_json: Media mapping JSON
        notes_data: List of (id, mid, tags, flds, sfld) tuples for notes table
        cards_data: List of (id, nid, did, ord, due, ivl, factor, reps, lapses) tuples
        db_filename: Database filename (collection.anki2 or collection.anki21)

    Returns:
        BytesIO containing the .apkg file
    """
    if models_json is None:
        models_json = {
            "1234567890": {
                "name": "Basic",
                "flds": [{"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}],
                "tmpls": [{"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"}],
                "css": "",
            }
        }

    if decks_json is None:
        decks_json = {
            "1": {"name": "Default", "id": 1},
            "1234567890123": {"name": "Test Deck", "id": 1234567890123},
        }

    if media_json is None:
        media_json = {}

    if notes_data is None:
        # Default: one note with front/back
        notes_data = [
            (1, 1234567890, "tag1 tag2", "Test Front\x1fTest Back", "Test Front"),
        ]

    if cards_data is None:
        # Default: one card linked to the note
        cards_data = [
            (1, 1, 1234567890123, 0, 0, 0, 2500, 0, 0),
        ]

    # Create SQLite database in memory
    db_bytes = BytesIO()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name

    try:
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()

        # Create col table (collection metadata)
        cursor.execute("""
            CREATE TABLE col (
                id INTEGER PRIMARY KEY,
                crt INTEGER,
                mod INTEGER,
                scm INTEGER,
                ver INTEGER,
                dty INTEGER,
                usn INTEGER,
                ls INTEGER,
                conf TEXT,
                models TEXT,
                decks TEXT,
                dconf TEXT,
                tags TEXT
            )
        """)

        cursor.execute("""
            INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags)
            VALUES (1, 0, 0, 0, 0, 0, 0, 0, '{}', ?, ?, '{}', '{}')
        """, (json.dumps(models_json), json.dumps(decks_json)))

        # Create notes table
        cursor.execute("""
            CREATE TABLE notes (
                id INTEGER PRIMARY KEY,
                guid TEXT,
                mid INTEGER,
                mod INTEGER,
                usn INTEGER,
                tags TEXT,
                flds TEXT,
                sfld TEXT,
                csum INTEGER,
                flags INTEGER,
                data TEXT
            )
        """)

        for note in notes_data:
            note_id, mid, tags, flds, sfld = note
            cursor.execute("""
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, 'guid', ?, 0, 0, ?, ?, ?, 0, 0, '')
            """, (note_id, mid, tags, flds, sfld))

        # Create cards table
        cursor.execute("""
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                nid INTEGER,
                did INTEGER,
                ord INTEGER,
                mod INTEGER,
                usn INTEGER,
                type INTEGER,
                queue INTEGER,
                due INTEGER,
                ivl INTEGER,
                factor INTEGER,
                reps INTEGER,
                lapses INTEGER,
                left INTEGER,
                odue INTEGER,
                odid INTEGER,
                flags INTEGER,
                data TEXT
            )
        """)

        for card in cards_data:
            card_id, nid, did, ord, due, ivl, factor, reps, lapses = card
            cursor.execute("""
                INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                VALUES (?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?, ?, ?, 0, 0, 0, 0, '')
            """, (card_id, nid, did, ord, due, ivl, factor, reps, lapses))

        conn.commit()
        conn.close()

        # Read the database file
        with open(tmp_db_path, "rb") as f:
            db_content = f.read()
    finally:
        Path(tmp_db_path).unlink(missing_ok=True)

    # Create ZIP archive
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(db_filename, db_content)
        zf.writestr("media", json.dumps(media_json))

    zip_buffer.seek(0)
    return zip_buffer


@pytest.fixture
def mock_apkg_file(sample_models_json, sample_decks_json, sample_media_json) -> BytesIO:
    """Create a mock .apkg file with sample data."""
    notes_data = [
        (1, 1234567890, "tag1 tag2", "Question 1\x1fAnswer 1", "Question 1"),
        (2, 1234567890, "tag3", "Question 2\x1fAnswer 2", "Question 2"),
        (3, 9876543210, "", "Front\x1fBack", "Front"),
    ]

    cards_data = [
        (1, 1, 1234567890123, 0, 100, 10, 2500, 5, 1),
        (2, 2, 1234567890123, 0, 50, 5, 2300, 3, 0),
        (3, 3, 9876543210987, 0, 0, 0, 2500, 0, 0),
        (4, 3, 9876543210987, 1, 0, 0, 2500, 0, 0),  # Second card for reversed
    ]

    return create_mock_apkg_file(
        models_json=sample_models_json,
        decks_json=sample_decks_json,
        media_json=sample_media_json,
        notes_data=notes_data,
        cards_data=cards_data,
    )


# ==================== Parse APKG Tests ====================


@pytest.mark.asyncio
class TestParseApkg:
    """Tests for parsing .apkg files."""

    async def test_parse_valid_apkg_file(
        self,
        parser: ApkgParser,
        mock_apkg_file: BytesIO,
        tmp_path: Path,
    ):
        """Test parsing a valid .apkg file."""
        # Write mock file to disk
        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_apkg_file.read())

        result = await parser.parse(apkg_path)

        assert isinstance(result, ParsedDeck)
        assert result.name == "My Test Deck"  # First non-Default deck
        assert len(result.cards) == 4
        assert len(result.note_types) == 2

    async def test_parse_apkg_file_not_found(self, parser: ApkgParser, tmp_path: Path):
        """Test parsing non-existent file raises error."""
        non_existent = tmp_path / "non_existent.apkg"

        with pytest.raises(ApkgParseError) as exc_info:
            await parser.parse(non_existent)

        assert "File not found" in str(exc_info.value)

    async def test_parse_invalid_zip_file(self, parser: ApkgParser, tmp_path: Path):
        """Test parsing invalid ZIP file raises error."""
        invalid_file = tmp_path / "invalid.apkg"
        invalid_file.write_bytes(b"This is not a ZIP file")

        with pytest.raises(ApkgParseError) as exc_info:
            await parser.parse(invalid_file)

        assert "Not a valid .apkg file" in str(exc_info.value)

    async def test_parse_zip_without_database(self, parser: ApkgParser, tmp_path: Path):
        """Test parsing ZIP without database raises error."""
        # Create ZIP without collection.anki2
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("media", "{}")
            zf.writestr("some_other_file.txt", "content")

        apkg_path = tmp_path / "no_db.apkg"
        apkg_path.write_bytes(zip_buffer.getvalue())

        with pytest.raises(ApkgParseError) as exc_info:
            await parser.parse(apkg_path)

        assert "No database found" in str(exc_info.value)

    async def test_parse_anki21_format(self, parser: ApkgParser, tmp_path: Path):
        """Test parsing Anki 2.1 format (collection.anki21)."""
        mock_file = create_mock_apkg_file(db_filename="collection.anki21")

        apkg_path = tmp_path / "anki21.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert isinstance(result, ParsedDeck)
        assert len(result.cards) == 1

    async def test_parse_empty_database(self, parser: ApkgParser, tmp_path: Path):
        """Test parsing database with no cards."""
        mock_file = create_mock_apkg_file(
            notes_data=[],
            cards_data=[],
        )

        apkg_path = tmp_path / "empty.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert len(result.cards) == 0


# ==================== Extract Cards Tests ====================


@pytest.mark.asyncio
class TestExtractCards:
    """Tests for extracting cards from parsed database."""

    async def test_extract_cards_with_fields(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test extracting cards preserves all fields."""
        notes_data = [
            (1, 1234567890, "test tag", "Front Content\x1fBack Content", "Front Content"),
        ]
        cards_data = [
            (1, 1, 1234567890123, 0, 100, 30, 2500, 10, 2),
        ]

        mock_file = create_mock_apkg_file(
            notes_data=notes_data,
            cards_data=cards_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert len(result.cards) == 1
        card = result.cards[0]

        assert card.front == "Front Content"
        assert card.back == "Back Content"
        assert card.tags == ["test", "tag"]
        assert card.due == 100
        assert card.interval == 30
        assert card.ease_factor == 2500
        assert card.reviews == 10
        assert card.lapses == 2

    async def test_extract_cards_with_empty_tags(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test extracting cards with no tags."""
        notes_data = [
            (1, 1234567890, "", "Front\x1fBack", "Front"),
        ]
        cards_data = [
            (1, 1, 1234567890123, 0, 0, 0, 2500, 0, 0),
        ]

        mock_file = create_mock_apkg_file(
            notes_data=notes_data,
            cards_data=cards_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert result.cards[0].tags == []

    async def test_extract_cards_multiple_from_same_note(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test extracting multiple cards from the same note (reversed cards)."""
        models_json = {
            "1234567890": {
                "name": "Basic (and reversed)",
                "flds": [{"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}],
                "tmpls": [
                    {"name": "Card 1", "qfmt": "{{Front}}", "afmt": "{{Back}}"},
                    {"name": "Card 2", "qfmt": "{{Back}}", "afmt": "{{Front}}"},
                ],
                "css": "",
            }
        }

        notes_data = [
            (1, 1234567890, "", "Apple\x1fYabloko", "Apple"),
        ]

        cards_data = [
            (1, 1, 1234567890123, 0, 0, 0, 2500, 0, 0),  # Card 1
            (2, 1, 1234567890123, 1, 0, 0, 2500, 0, 0),  # Card 2 (reversed)
        ]

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=notes_data,
            cards_data=cards_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert len(result.cards) == 2

        # First card (normal order)
        card1 = result.cards[0]
        assert card1.front == "Apple"
        assert card1.back == "Yabloko"

        # Second card (reversed)
        card2 = result.cards[1]
        assert card2.front == "Yabloko"
        assert card2.back == "Apple"

    async def test_extract_cards_preserves_deck_name(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test that cards get correct deck names."""
        decks_json = {
            "1": {"name": "Default", "id": 1},
            "111": {"name": "Deck A", "id": 111},
            "222": {"name": "Deck B", "id": 222},
        }

        notes_data = [
            (1, 1234567890, "", "Q1\x1fA1", "Q1"),
            (2, 1234567890, "", "Q2\x1fA2", "Q2"),
        ]

        cards_data = [
            (1, 1, 111, 0, 0, 0, 2500, 0, 0),  # In Deck A
            (2, 2, 222, 0, 0, 0, 2500, 0, 0),  # In Deck B
        ]

        mock_file = create_mock_apkg_file(
            decks_json=decks_json,
            notes_data=notes_data,
            cards_data=cards_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert result.cards[0].deck_name == "Deck A"
        assert result.cards[1].deck_name == "Deck B"


# ==================== Extract Models Tests ====================


@pytest.mark.asyncio
class TestExtractModels:
    """Tests for extracting note types (models)."""

    async def test_extract_models_basic(
        self,
        parser: ApkgParser,
        sample_models_json: dict,
        tmp_path: Path,
    ):
        """Test extracting note types from database."""
        mock_file = create_mock_apkg_file(models_json=sample_models_json)

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert len(result.note_types) == 2

        model_names = {nt.name for nt in result.note_types}
        assert "Basic" in model_names
        assert "Basic (and reversed card)" in model_names

    async def test_extract_models_with_fields(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test that model fields are extracted correctly."""
        models_json = {
            "123": {
                "name": "Custom",
                "flds": [
                    {"name": "Question", "ord": 0},
                    {"name": "Answer", "ord": 1},
                    {"name": "Extra", "ord": 2},
                ],
                "tmpls": [{"name": "Card", "qfmt": "{{Question}}", "afmt": "{{Answer}}"}],
                "css": ".card { color: blue; }",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Q\x1fA\x1fE", "Q")],
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert len(result.note_types) == 1
        model = result.note_types[0]

        assert model.name == "Custom"
        assert model.fields == ["Question", "Answer", "Extra"]
        assert model.css == ".card { color: blue; }"

    async def test_extract_models_with_templates(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test that model templates are extracted correctly."""
        models_json = {
            "123": {
                "name": "Cloze",
                "flds": [{"name": "Text", "ord": 0}],
                "tmpls": [
                    {"name": "Cloze", "qfmt": "{{cloze:Text}}", "afmt": "{{cloze:Text}}"},
                ],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Test {{c1::cloze}}", "Test")],
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        model = result.note_types[0]
        assert len(model.templates) == 1
        assert model.templates[0]["name"] == "Cloze"


# ==================== Build Card Data Tests ====================


@pytest.mark.asyncio
class TestBuildCardData:
    """Tests for building card data from template substitution."""

    async def test_simple_field_substitution(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test simple field substitution in templates."""
        models_json = {
            "123": {
                "name": "Basic",
                "flds": [{"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}],
                "tmpls": [{"qfmt": "{{Front}}", "afmt": "{{Back}}"}],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Hello\x1fWorld", "Hello")],
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert result.cards[0].front == "Hello"
        assert result.cards[0].back == "World"

    async def test_frontside_substitution(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test {{FrontSide}} substitution in back template."""
        models_json = {
            "123": {
                "name": "Basic",
                "flds": [{"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}],
                "tmpls": [
                    {
                        "qfmt": "Question: {{Front}}",
                        "afmt": "{{FrontSide}}<hr>Answer: {{Back}}",
                    }
                ],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "What is 2+2?\x1f4", "What is 2+2?")],
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        card = result.cards[0]
        assert card.front == "Question: What is 2+2?"
        assert "Question: What is 2+2?" in card.back
        assert "Answer: 4" in card.back

    async def test_hint_field_substitution(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test {{hint:Field}} substitution."""
        models_json = {
            "123": {
                "name": "With Hint",
                "flds": [
                    {"name": "Front", "ord": 0},
                    {"name": "Hint", "ord": 1},
                    {"name": "Back", "ord": 2},
                ],
                "tmpls": [
                    {
                        "qfmt": "{{Front}}{{hint:Hint}}",
                        "afmt": "{{Back}}",
                    }
                ],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Question\x1fHint Text\x1fAnswer", "Question")],
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        # hint: substitution should include the field value
        assert "Hint Text" in result.cards[0].front

    async def test_conditional_field_non_empty(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test conditional {{#Field}} when field is non-empty."""
        models_json = {
            "123": {
                "name": "Conditional",
                "flds": [
                    {"name": "Front", "ord": 0},
                    {"name": "Extra", "ord": 1},
                    {"name": "Back", "ord": 2},
                ],
                "tmpls": [
                    {
                        "qfmt": "{{Front}}{{#Extra}}<br>Extra: {{Extra}}{{/Extra}}",
                        "afmt": "{{Back}}",
                    }
                ],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Question\x1fExtra Info\x1fAnswer", "Question")],
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert "Extra Info" in result.cards[0].front

    async def test_conditional_field_empty(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test conditional {{#Field}} when field is empty."""
        models_json = {
            "123": {
                "name": "Conditional",
                "flds": [
                    {"name": "Front", "ord": 0},
                    {"name": "Extra", "ord": 1},
                    {"name": "Back", "ord": 2},
                ],
                "tmpls": [
                    {
                        "qfmt": "{{Front}}{{#Extra}}<br>Extra: {{Extra}}{{/Extra}}",
                        "afmt": "{{Back}}",
                    }
                ],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Question\x1f\x1fAnswer", "Question")],  # Empty Extra
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        # Conditional content should not appear
        assert "Extra:" not in result.cards[0].front

    async def test_inverse_conditional_field(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test inverse conditional {{^Field}} when field is empty."""
        models_json = {
            "123": {
                "name": "Inverse",
                "flds": [
                    {"name": "Front", "ord": 0},
                    {"name": "Extra", "ord": 1},
                    {"name": "Back", "ord": 2},
                ],
                "tmpls": [
                    {
                        "qfmt": "{{Front}}{{^Extra}}<br>No extra info{{/Extra}}",
                        "afmt": "{{Back}}",
                    }
                ],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Question\x1f\x1fAnswer", "Question")],  # Empty Extra
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        # Inverse conditional should show when field is empty
        assert "No extra info" in result.cards[0].front

    async def test_card_fields_dictionary(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test that card.fields contains all field values."""
        models_json = {
            "123": {
                "name": "Multi-field",
                "flds": [
                    {"name": "Field1", "ord": 0},
                    {"name": "Field2", "ord": 1},
                    {"name": "Field3", "ord": 2},
                ],
                "tmpls": [{"qfmt": "{{Field1}}", "afmt": "{{Field2}}"}],
                "css": "",
            }
        }

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=[(1, 123, "", "Value1\x1fValue2\x1fValue3", "Value1")],
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        card = result.cards[0]
        assert card.fields == {
            "Field1": "Value1",
            "Field2": "Value2",
            "Field3": "Value3",
        }


# ==================== Media Handling Tests ====================


@pytest.mark.asyncio
class TestMediaHandling:
    """Tests for media file handling."""

    async def test_parse_media_mapping(
        self,
        parser: ApkgParser,
        sample_media_json: dict,
        tmp_path: Path,
    ):
        """Test parsing media mapping from .apkg."""
        mock_file = create_mock_apkg_file(media_json=sample_media_json)

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert result.media_files == sample_media_json

    async def test_get_media_file(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test extracting a media file from .apkg."""
        media_json = {"0": "test_image.png"}
        media_content = b"\x89PNG\r\n\x1a\n..."  # Fake PNG header

        # Create ZIP with media file
        zip_buffer = BytesIO()

        # First create a valid database
        db_mock = create_mock_apkg_file(media_json=media_json)

        with zipfile.ZipFile(db_mock, "r") as src_zf:
            with zipfile.ZipFile(zip_buffer, "w") as dest_zf:
                for item in src_zf.namelist():
                    dest_zf.writestr(item, src_zf.read(item))
                # Add actual media file
                dest_zf.writestr("0", media_content)

        apkg_path = tmp_path / "with_media.apkg"
        apkg_path.write_bytes(zip_buffer.getvalue())

        result = await parser.get_media_file(apkg_path, "test_image.png")

        assert result == media_content

    async def test_get_media_file_not_found(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test getting non-existent media file returns None."""
        mock_file = create_mock_apkg_file(media_json={"0": "existing.png"})

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.get_media_file(apkg_path, "non_existent.png")

        assert result is None

    async def test_get_media_file_invalid_apkg(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test getting media from invalid .apkg returns None."""
        invalid_file = tmp_path / "invalid.apkg"
        invalid_file.write_bytes(b"not a zip file")

        result = await parser.get_media_file(invalid_file, "any.png")

        assert result is None


# ==================== Edge Cases Tests ====================


@pytest.mark.asyncio
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    async def test_card_with_unknown_model(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test handling cards with unknown model ID (should skip)."""
        models_json = {
            "111": {
                "name": "Known",
                "flds": [{"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}],
                "tmpls": [{"qfmt": "{{Front}}", "afmt": "{{Back}}"}],
                "css": "",
            }
        }

        notes_data = [
            (1, 111, "", "Known\x1fAnswer", "Known"),  # Known model
            (2, 999, "", "Unknown\x1fModel", "Unknown"),  # Unknown model
        ]

        cards_data = [
            (1, 1, 1, 0, 0, 0, 2500, 0, 0),
            (2, 2, 1, 0, 0, 0, 2500, 0, 0),
        ]

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=notes_data,
            cards_data=cards_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        # Only the card with known model should be included
        assert len(result.cards) == 1
        assert result.cards[0].front == "Known"

    async def test_card_with_missing_fields(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test handling notes with fewer fields than expected."""
        models_json = {
            "123": {
                "name": "ThreeFields",
                "flds": [
                    {"name": "Field1", "ord": 0},
                    {"name": "Field2", "ord": 1},
                    {"name": "Field3", "ord": 2},
                ],
                "tmpls": [{"qfmt": "{{Field1}}", "afmt": "{{Field3}}"}],
                "css": "",
            }
        }

        # Note with only 2 fields instead of 3
        notes_data = [
            (1, 123, "", "Value1\x1fValue2", "Value1"),
        ]

        cards_data = [
            (1, 1, 1, 0, 0, 0, 2500, 0, 0),
        ]

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=notes_data,
            cards_data=cards_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        # Should handle gracefully with empty value for missing field
        assert len(result.cards) == 1
        assert result.cards[0].fields["Field3"] == ""

    async def test_card_ord_beyond_templates(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test handling card with ord beyond available templates."""
        models_json = {
            "123": {
                "name": "SingleTemplate",
                "flds": [{"name": "Front", "ord": 0}, {"name": "Back", "ord": 1}],
                "tmpls": [{"qfmt": "{{Front}}", "afmt": "{{Back}}"}],  # Only 1 template
                "css": "",
            }
        }

        notes_data = [
            (1, 123, "", "Question\x1fAnswer", "Question"),
        ]

        # Card with ord=5 (beyond available templates)
        cards_data = [
            (1, 1, 1, 5, 0, 0, 2500, 0, 0),
        ]

        mock_file = create_mock_apkg_file(
            models_json=models_json,
            notes_data=notes_data,
            cards_data=cards_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        # Should fall back to first template
        assert len(result.cards) == 1
        assert result.cards[0].front == "Question"

    async def test_unicode_content(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test handling unicode content in cards."""
        notes_data = [
            (1, 1234567890, "tag", "Hello World\x1fMir", ""),
        ]

        mock_file = create_mock_apkg_file(
            notes_data=notes_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert result.cards[0].front == "Hello World"
        assert result.cards[0].back == "Mir"

    async def test_html_content_preserved(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test that HTML content is preserved in cards."""
        notes_data = [
            (1, 1234567890, "", "<b>Bold</b>\x1f<i>Italic</i>", "Bold"),
        ]

        mock_file = create_mock_apkg_file(
            notes_data=notes_data,
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        assert "<b>Bold</b>" in result.cards[0].front
        assert "<i>Italic</i>" in result.cards[0].back

    async def test_default_deck_fallback(
        self,
        parser: ApkgParser,
        tmp_path: Path,
    ):
        """Test fallback to deck name when only Default exists."""
        decks_json = {
            "1": {"name": "Default", "id": 1},
        }

        mock_file = create_mock_apkg_file(
            decks_json=decks_json,
            cards_data=[(1, 1, 1, 0, 0, 0, 2500, 0, 0)],
        )

        apkg_path = tmp_path / "test.apkg"
        apkg_path.write_bytes(mock_file.read())

        result = await parser.parse(apkg_path)

        # Should fall back to "Imported Deck" when only Default exists
        assert result.name == "Imported Deck"
