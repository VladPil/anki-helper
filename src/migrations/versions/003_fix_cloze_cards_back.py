"""Fix cloze cards back field.

Revision ID: 003_fix_cloze_cards_back
Revises: 002_add_sync_fields
Create Date: 2026-01-13

This migration extracts cloze deletion answers from Front field
and populates the Back field for cards where Back is empty.

For example:
    Front: "Python {{c1::is great}}"
    Back: "" -> "is great"
"""

import json
import re

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "003_fix_cloze_cards_back"
down_revision = "002_add_sync_fields"
branch_labels = None
depends_on = None

# Regex to extract cloze deletions: {{c1::answer}} or {{c1::answer::hint}}
CLOZE_PATTERN = re.compile(r"\{\{c\d+::([^:}]+)(?:::[^}]*)?\}\}")


def extract_cloze_answers(front_text: str) -> str:
    """Extract all cloze answers from front text.

    Args:
        front_text: The front field containing cloze deletions.

    Returns:
        Concatenated cloze answers separated by "; ".
    """
    if not front_text:
        return ""

    matches = CLOZE_PATTERN.findall(front_text)
    if matches:
        return "; ".join(matches)
    return ""


def upgrade() -> None:
    """Populate Back field for cloze cards from cloze deletions."""
    conn = op.get_bind()

    # Get all cards with empty Back but non-empty Front containing cloze syntax
    result = conn.execute(
        text("""
            SELECT id, fields->>'Front' as front
            FROM cards
            WHERE (fields->>'Back' IS NULL OR fields->>'Back' = '')
              AND fields->>'Front' LIKE '%{{c%::%}}%'
        """)
    )

    updates = []
    for row in result:
        card_id = row[0]
        front = row[1] or ""
        back = extract_cloze_answers(front)

        if back:
            updates.append((card_id, back))

    # Update cards with extracted cloze answers
    for card_id, back in updates:
        # Properly escape the JSON value
        json_value = json.dumps(back)
        # Escape single quotes for SQL
        json_value_escaped = json_value.replace("'", "''")
        conn.execute(
            text(f"""
                UPDATE cards
                SET fields = jsonb_set(fields, '{{Back}}', '{json_value_escaped}'::jsonb)
                WHERE id = '{card_id}'
            """)
        )

    print(f"Updated {len(updates)} cloze cards with extracted answers.")


def downgrade() -> None:
    """Revert Back field to empty for cloze cards."""
    conn = op.get_bind()

    # Reset Back to empty for cards that have cloze syntax in Front
    conn.execute(
        text("""
            UPDATE cards
            SET fields = jsonb_set(fields, '{Back}', '""'::jsonb)
            WHERE fields->>'Front' LIKE '%{{c%::%}}%'
        """)
    )
