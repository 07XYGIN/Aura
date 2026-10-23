"""Adopt the current Aura schema as the Alembic baseline.

Revision ID: 20260918_0001
Revises:
Create Date: 2026-09-18

The current schema is already materialized by ``main.sql`` for new databases
and the dated SQL chain for existing databases. Deployments must stamp this
revision only after the schema guard passes. Future schema changes must use a
new Alembic revision instead of adding another standalone SQL migration.
"""

from typing import Sequence


revision: str = "20260918_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # A stamped baseline owns no DDL and therefore cannot safely drop tables.
    pass
