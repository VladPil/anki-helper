"""Add sync_error and sync_attempts fields to cards.

Revision ID: 002_add_sync_fields
Revises: 001_initial
Create Date: 2026-01-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_sync_fields"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add sync error tracking fields and SYNC_FAILED status."""
    # Add sync tracking columns first (these can be done in same transaction)
    op.add_column(
        "cards",
        sa.Column("sync_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "cards",
        sa.Column(
            "sync_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    # Add new status value to enum in separate connection with autocommit
    # PostgreSQL requires commit after ALTER TYPE before the new value can be used
    connection = op.get_bind()
    connection.execute(
        sa.text("ALTER TYPE cardstatus ADD VALUE IF NOT EXISTS 'sync_failed'")
    )
    connection.execute(sa.text("COMMIT"))

    # Add partial index for sync_failed status queries
    # Using text-based index creation to avoid enum value check issues
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cards_sync_failed "
        "ON cards (status) WHERE status = 'sync_failed'"
    )


def downgrade() -> None:
    """Remove sync tracking fields."""
    op.drop_index("ix_cards_sync_failed", table_name="cards")
    op.drop_column("cards", "sync_attempts")
    op.drop_column("cards", "sync_error")
    # Note: Cannot remove enum value in PostgreSQL without recreating the type
