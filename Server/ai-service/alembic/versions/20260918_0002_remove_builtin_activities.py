"""Remove the retired focus, Bash game, and companion pet data planes.

Revision ID: 20260918_0002
Revises: 20260918_0001
Create Date: 2026-09-18
"""

from typing import Sequence

from alembic import op


revision: str = "20260918_0002"
down_revision: str | Sequence[str] | None = "20260918_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Child tables must be removed before their parents. IF EXISTS keeps the
    # revision valid for databases bootstrapped from the current main.sql.
    for table_name in (
        "focus_session_event",
        "focus_session",
        "bash_game_move",
        "bash_game_session",
        "pet_event",
        "companion_pet",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
    op.execute("ALTER TABLE aura_daily_state DROP COLUMN IF EXISTS pet_event")


def downgrade() -> None:
    # The removed activity history is intentionally not reconstructed.
    pass
