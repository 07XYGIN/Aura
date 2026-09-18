"""Add Relationship Engine v2 events, phases, tones, and affect decay.

Revision ID: 20260918_0003
Revises: 20260918_0002
Create Date: 2026-09-18
"""

from typing import Sequence

from alembic import op


revision: str = "20260918_0003"
down_revision: str | Sequence[str] | None = "20260918_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "DROP CONSTRAINT IF EXISTS chk_relationship_dynamics_stage"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "DROP CONSTRAINT IF EXISTS chk_relationship_dynamics_tone"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "DROP CONSTRAINT IF EXISTS chk_relationship_dynamics_evidence"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "ADD COLUMN relationship_phase varchar(16) NOT NULL DEFAULT 'normal'"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics RENAME COLUMN current_tone TO relationship_tone"
    )
    op.execute(
        "UPDATE relationship_dynamics SET relationship_phase = CASE "
        "WHEN relationship_stage = 'temporary_distance' THEN 'distant' "
        "WHEN relationship_stage = 'conflict' THEN 'conflict' "
        "WHEN relationship_stage = 'repair' THEN 'repair' "
        "ELSE 'normal' END"
    )
    op.execute(
        "UPDATE relationship_dynamics SET relationship_tone = CASE relationship_tone "
        "WHEN 'neutral' THEN 'steady' "
        "WHEN 'tense' THEN 'guarded' "
        "WHEN 'distant' THEN 'guarded' "
        "WHEN 'repairing' THEN 'guarded' "
        "ELSE relationship_tone END"
    )
    op.execute(
        "UPDATE relationship_dynamics SET relationship_stage = CASE "
        "WHEN relationship_stage = 'stable' THEN 'established_romance' "
        "WHEN relationship_stage IN ('temporary_distance', 'conflict', 'repair') THEN 'ambiguous' "
        "ELSE relationship_stage END"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics DROP COLUMN stage_evidence_count"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics ADD CONSTRAINT chk_relationship_dynamics_stage "
        "CHECK (relationship_stage IN ('early_closeness', 'ambiguous', 'early_romance', "
        "'established_romance'))"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics ADD CONSTRAINT chk_relationship_dynamics_phase "
        "CHECK (relationship_phase IN ('normal', 'distant', 'conflict', 'repair'))"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics ADD CONSTRAINT chk_relationship_dynamics_tone "
        "CHECK (relationship_tone IN ('steady', 'warm', 'playful', 'tender', 'guarded'))"
    )

    op.execute(
        """
        CREATE TABLE relationship_event (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            event_type varchar(40) NOT NULL,
            actor varchar(16) NOT NULL,
            target varchar(16) NOT NULL,
            importance varchar(16) NOT NULL DEFAULT 'medium',
            summary text,
            source_turn_id varchar(128) NOT NULL,
            payload jsonb NOT NULL DEFAULT '{}'::jsonb,
            occurred_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT chk_relationship_event_type CHECK (
                event_type IN ('affection_expressed', 'aura_expressed_missing',
                    'important_disclosure', 'conflict_started', 'boundary_crossed',
                    'apology', 'repair_completed', 'promise_created', 'promise_fulfilled',
                    'shared_moment', 'relationship_milestone', 'distance_period',
                    'return_after_absence')
            ),
            CONSTRAINT chk_relationship_event_actor CHECK (actor IN ('user', 'aura', 'system')),
            CONSTRAINT chk_relationship_event_target CHECK (target IN ('user', 'aura', 'relationship')),
            CONSTRAINT chk_relationship_event_importance CHECK (importance IN ('low', 'medium', 'high')),
            CONSTRAINT uq_relationship_event_turn_type UNIQUE (user_id, source_turn_id, event_type)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE affect_state (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind varchar(24) NOT NULL,
            intensity varchar(16) NOT NULL,
            started_at timestamptz NOT NULL,
            last_reinforced_at timestamptz NOT NULL,
            decay_after timestamptz NOT NULL,
            source_event_id uuid REFERENCES relationship_event(id) ON DELETE SET NULL,
            resolved boolean NOT NULL DEFAULT false,
            resolved_at timestamptz,
            version integer NOT NULL DEFAULT 1,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT chk_affect_state_kind CHECK (kind IN ('jealousy', 'hurt', 'longing', 'unsettled')),
            CONSTRAINT chk_affect_state_intensity CHECK (intensity IN ('low', 'medium', 'high')),
            CONSTRAINT chk_affect_state_version CHECK (version >= 1),
            CONSTRAINT uq_affect_state_user_kind UNIQUE (user_id, kind)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_relationship_event_user_occurred "
        "ON relationship_event (user_id, occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_affect_state_user_decay "
        "ON affect_state (user_id, resolved, decay_after)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE affect_state")
    op.execute("DROP TABLE relationship_event")
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "DROP CONSTRAINT IF EXISTS chk_relationship_dynamics_stage"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "DROP CONSTRAINT IF EXISTS chk_relationship_dynamics_phase"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "DROP CONSTRAINT IF EXISTS chk_relationship_dynamics_tone"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics "
        "ADD COLUMN stage_evidence_count integer NOT NULL DEFAULT 0"
    )
    op.execute(
        "UPDATE relationship_dynamics SET relationship_stage = CASE relationship_phase "
        "WHEN 'distant' THEN 'temporary_distance' "
        "WHEN 'conflict' THEN 'conflict' "
        "WHEN 'repair' THEN 'repair' "
        "ELSE relationship_stage END"
    )
    op.execute(
        "UPDATE relationship_dynamics SET relationship_tone = CASE relationship_tone "
        "WHEN 'steady' THEN 'neutral' WHEN 'guarded' THEN 'tense' ELSE relationship_tone END"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics RENAME COLUMN relationship_tone TO current_tone"
    )
    op.execute("ALTER TABLE relationship_dynamics DROP COLUMN relationship_phase")
    op.execute(
        "ALTER TABLE relationship_dynamics ADD CONSTRAINT chk_relationship_dynamics_stage "
        "CHECK (relationship_stage IN ('early_closeness', 'ambiguous', 'early_romance', "
        "'established_romance', 'temporary_distance', 'conflict', 'repair', 'stable'))"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics ADD CONSTRAINT chk_relationship_dynamics_tone "
        "CHECK (current_tone IN ('neutral', 'warm', 'playful', 'tender', 'tense', "
        "'distant', 'repairing'))"
    )
    op.execute(
        "ALTER TABLE relationship_dynamics ADD CONSTRAINT chk_relationship_dynamics_evidence "
        "CHECK (stage_evidence_count >= 0)"
    )
