BEGIN;

CREATE TABLE IF NOT EXISTS aura_thought_seed (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    thought_type varchar(32) NOT NULL,
    content text NOT NULL,
    reason text NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'pending',
    dedupe_key varchar(160) NOT NULL,
    relevance numeric(4, 3) NOT NULL DEFAULT 1,
    visible_on_next_chat boolean NOT NULL DEFAULT false,
    source_message_id varchar(128),
    source_turn_id varchar(128),
    eligible_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    queued_at timestamptz,
    used_at timestamptz,
    cancelled_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_aura_thought_seed_type CHECK (
        thought_type IN ('second_thought', 'offline_reflection', 'surprise', 'night_reflection')
    ),
    CONSTRAINT chk_aura_thought_seed_status CHECK (
        status IN ('pending', 'queued', 'used', 'cancelled', 'expired')
    ),
    CONSTRAINT chk_aura_thought_seed_relevance CHECK (relevance BETWEEN 0 AND 1),
    CONSTRAINT uq_aura_thought_seed_user_dedupe UNIQUE (user_id, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_aura_thought_seed_status_eligible
    ON aura_thought_seed (status, eligible_at, expires_at);
CREATE INDEX IF NOT EXISTS idx_aura_thought_seed_user_created
    ON aura_thought_seed (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS aura_sleep_cycle (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    local_date date NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'processing',
    summary text NOT NULL,
    reflection text NOT NULL,
    open_threads jsonb NOT NULL DEFAULT '[]'::jsonb,
    avoid_topics jsonb NOT NULL DEFAULT '[]'::jsonb,
    consolidated_count integer NOT NULL DEFAULT 0,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    last_error text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_aura_sleep_cycle_status CHECK (status IN ('processing', 'completed', 'failed')),
    CONSTRAINT chk_aura_sleep_cycle_consolidated_count CHECK (consolidated_count >= 0),
    CONSTRAINT uq_aura_sleep_cycle_user_date UNIQUE (user_id, local_date)
);
CREATE INDEX IF NOT EXISTS idx_aura_sleep_cycle_user_date
    ON aura_sleep_cycle (user_id, local_date DESC);

COMMENT ON TABLE aura_thought_seed IS
    '基于真实对话、关系线程或整理结果产生的少量思绪候选；不保证展示，也不能伪装成现实见闻';
COMMENT ON TABLE aura_sleep_cycle IS
    'Aura 每天一次的关系与记忆整理运行；记录开放线索、避免话题、反思和去重结果';

COMMIT;
