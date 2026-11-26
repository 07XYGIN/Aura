"""Align persisted jealousy with the affect engine's full intensity range."""
from alembic import op

revision = "20260920_0004"
down_revision = "20260918_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize a legacy equivalent expression so SQL, metadata and catalog agree.
    op.drop_constraint("chk_users_sex", "users", type_="check")
    op.create_check_constraint("chk_users_sex", "users", "sex IS NULL OR sex IN (0, 1)")
    op.drop_constraint("chk_aura_internal_state_jealousy", "aura_internal_state", type_="check")
    op.create_check_constraint("chk_aura_internal_state_jealousy", "aura_internal_state", "jealousy IN ('none', 'low', 'medium', 'high')")


def downgrade() -> None:
    op.execute("UPDATE aura_internal_state SET jealousy = 'medium' WHERE jealousy = 'high'")
    op.drop_constraint("chk_aura_internal_state_jealousy", "aura_internal_state", type_="check")
    op.create_check_constraint("chk_aura_internal_state_jealousy", "aura_internal_state", "jealousy IN ('none', 'low', 'medium')")
