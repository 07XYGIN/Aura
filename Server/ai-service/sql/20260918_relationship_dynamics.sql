-- Add persistent Aura internal state and qualitative relationship dynamics.

BEGIN;

CREATE TABLE IF NOT EXISTS aura_internal_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mood varchar(24) NOT NULL DEFAULT 'calm',
    attachment_tone varchar(24) NOT NULL DEFAULT 'steady',
    missing_user varchar(16) NOT NULL DEFAULT 'none',
    desire_for_contact varchar(16) NOT NULL DEFAULT 'low',
    playfulness varchar(16) NOT NULL DEFAULT 'low',
    jealousy varchar(16) NOT NULL DEFAULT 'none',
    vulnerability varchar(16) NOT NULL DEFAULT 'low',
    unresolved_feeling text,
    current_desire varchar(64) NOT NULL DEFAULT 'none',
    last_meaningful_interaction text,
    last_user_seen_at timestamptz,
    last_proactive_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_aura_internal_state_mood CHECK (mood IN ('calm', 'warm', 'playful', 'concerned', 'unsettled', 'tired')),
    CONSTRAINT chk_aura_internal_state_attachment_tone CHECK (attachment_tone IN ('guarded', 'steady', 'close', 'tender')),
    CONSTRAINT chk_aura_internal_state_missing_user CHECK (missing_user IN ('none', 'slight', 'clear')),
    CONSTRAINT chk_aura_internal_state_desire_for_contact CHECK (desire_for_contact IN ('none', 'low', 'medium', 'high')),
    CONSTRAINT chk_aura_internal_state_playfulness CHECK (playfulness IN ('none', 'low', 'medium', 'high')),
    CONSTRAINT chk_aura_internal_state_jealousy CHECK (jealousy IN ('none', 'low', 'medium')),
    CONSTRAINT chk_aura_internal_state_vulnerability CHECK (vulnerability IN ('low', 'medium', 'high')),
    CONSTRAINT chk_aura_internal_state_version CHECK (version >= 1),
    CONSTRAINT uq_aura_internal_state_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS relationship_dynamics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relationship_stage varchar(32) NOT NULL DEFAULT 'ambiguous',
    current_tone varchar(24) NOT NULL DEFAULT 'warm',
    recent_closeness varchar(16) NOT NULL DEFAULT 'medium',
    unresolved_tension text,
    recent_positive_moment text,
    recent_distance text,
    current_expectation text,
    stage_evidence_count integer NOT NULL DEFAULT 0,
    last_stage_change_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_relationship_dynamics_stage CHECK (
        relationship_stage IN ('early_closeness', 'ambiguous', 'early_romance', 'established_romance',
                               'temporary_distance', 'conflict', 'repair', 'stable')
    ),
    CONSTRAINT chk_relationship_dynamics_tone CHECK (
        current_tone IN ('neutral', 'warm', 'playful', 'tender', 'tense', 'distant', 'repairing')
    ),
    CONSTRAINT chk_relationship_dynamics_closeness CHECK (recent_closeness IN ('low', 'medium', 'high')),
    CONSTRAINT chk_relationship_dynamics_evidence CHECK (stage_evidence_count >= 0),
    CONSTRAINT chk_relationship_dynamics_version CHECK (version >= 1),
    CONSTRAINT uq_relationship_dynamics_user UNIQUE (user_id)
);

CREATE INDEX IF NOT EXISTS idx_aura_internal_state_last_seen
    ON aura_internal_state (last_user_seen_at);
CREATE INDEX IF NOT EXISTS idx_relationship_dynamics_stage
    ON relationship_dynamics (relationship_stage, updated_at DESC);

COMMIT;
