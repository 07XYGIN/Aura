BEGIN;

CREATE TABLE IF NOT EXISTS aura_daily_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    local_date date NOT NULL,
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
    activity text NOT NULL,
    energy varchar(16) NOT NULL,
    mood varchar(24) NOT NULL,
    location varchar(160) NOT NULL,
    pet_event text,
    current_content text,
    daily_event text,
    generated_by varchar(16) NOT NULL DEFAULT 'deterministic',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_aura_daily_state_energy CHECK (energy IN ('rested', 'steady', 'low')),
    CONSTRAINT chk_aura_daily_state_mood CHECK (
        mood IN ('calm', 'focused', 'playful', 'annoyed', 'tired', 'cozy')
    ),
    CONSTRAINT chk_aura_daily_state_generated_by CHECK (
        generated_by IN ('deterministic', 'model', 'user')
    ),
    CONSTRAINT uq_aura_daily_state_user_date UNIQUE (user_id, local_date)
);
CREATE INDEX IF NOT EXISTS idx_aura_daily_state_user_date
    ON aura_daily_state (user_id, local_date DESC);

CREATE TABLE IF NOT EXISTS emotional_afterglow (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emotion varchar(24) NOT NULL,
    interaction_mode varchar(16) NOT NULL,
    intensity numeric(4, 3) NOT NULL,
    source_message_id varchar(128) NOT NULL,
    observed_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_emotional_afterglow_emotion CHECK (
        emotion IN ('happy', 'distressed', 'stressed', 'angry', 'lonely', 'tired',
                    'affectionate', 'unsettled')
    ),
    CONSTRAINT chk_emotional_afterglow_interaction_mode CHECK (
        interaction_mode IN ('natural', 'affection', 'repair')
    ),
    CONSTRAINT chk_emotional_afterglow_intensity CHECK (intensity BETWEEN 0 AND 1),
    CONSTRAINT chk_emotional_afterglow_version CHECK (version >= 1),
    CONSTRAINT uq_emotional_afterglow_user UNIQUE (user_id)
);
CREATE INDEX IF NOT EXISTS idx_emotional_afterglow_user_expires
    ON emotional_afterglow (user_id, expires_at);

CREATE TABLE IF NOT EXISTS shared_scene (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scene_type varchar(16) NOT NULL,
    world_layer varchar(24) NOT NULL DEFAULT 'imagined',
    place varchar(160) NOT NULL,
    participants jsonb NOT NULL DEFAULT '[]'::jsonb,
    objects jsonb NOT NULL DEFAULT '[]'::jsonb,
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(16) NOT NULL DEFAULT 'active',
    source_key varchar(160) NOT NULL,
    source_message_id varchar(128) NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_shared_scene_type CHECK (scene_type IN ('room', 'date', 'imagined')),
    CONSTRAINT chk_shared_scene_world_layer CHECK (world_layer IN ('imagined', 'wish')),
    CONSTRAINT chk_shared_scene_status CHECK (status IN ('active', 'closed')),
    CONSTRAINT chk_shared_scene_version CHECK (version >= 1),
    CONSTRAINT uq_shared_scene_user_source UNIQUE (user_id, source_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_shared_scene_active_user
    ON shared_scene (user_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_shared_scene_user_started
    ON shared_scene (user_id, started_at DESC);

COMMENT ON TABLE aura_daily_state IS
    'Aura 每个本地自然日唯一的设定内生活状态，保证一天内叙述一致，不作为现实外部证据';
COMMENT ON TABLE emotional_afterglow IS
    '当前用户情绪在有限时间内自然衰减的语气上下文，不是关系分数或心理诊断';
COMMENT ON TABLE shared_scene IS
    '双方有状态的共同想象场景；位置和物件连续，关闭后不得继续引用';

COMMIT;
