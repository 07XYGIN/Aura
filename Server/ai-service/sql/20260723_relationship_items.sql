BEGIN;

-- 关系知识不使用亲密度分数。item 保存可更新的稳定投影，chapter 保存低频关系时间线。
CREATE TABLE IF NOT EXISTS relationship_item (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_type varchar(32) NOT NULL,
    perspective varchar(16) NOT NULL,
    world_layer varchar(24) NOT NULL,
    item_key varchar(160) NOT NULL,
    title varchar(160) NOT NULL,
    content text NOT NULL,
    usage_condition text,
    confidence numeric(4, 3) NOT NULL DEFAULT 1,
    can_change boolean NOT NULL DEFAULT true,
    status varchar(16) NOT NULL DEFAULT 'active',
    cooldown_days smallint NOT NULL DEFAULT 14,
    last_used_at timestamptz,
    use_count integer NOT NULL DEFAULT 0,
    source_message_id varchar(128),
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_relationship_item_type CHECK (
        item_type IN ('shared_memory', 'nickname', 'running_joke', 'codeword', 'ritual',
                      'shared_object', 'action_style', 'aura_stance', 'interaction_rule', 'boundary')
    ),
    CONSTRAINT chk_relationship_item_perspective CHECK (perspective IN ('user', 'aura', 'shared')),
    CONSTRAINT chk_relationship_item_world_layer CHECK (
        world_layer IN ('reality', 'shared_history', 'imagined', 'wish', 'promise')
    ),
    CONSTRAINT chk_relationship_item_status CHECK (status IN ('active', 'inactive', 'superseded')),
    CONSTRAINT chk_relationship_item_use_count CHECK (use_count >= 0),
    CONSTRAINT chk_relationship_item_cooldown CHECK (cooldown_days BETWEEN 0 AND 3650),
    CONSTRAINT chk_relationship_item_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT chk_relationship_item_version CHECK (version >= 1),
    CONSTRAINT uq_relationship_item_user_key UNIQUE (user_id, item_key)
);

-- 兼容曾经执行过较早草稿的开发数据库，新增字段后再统一重建检查约束。
ALTER TABLE relationship_item
    ADD COLUMN IF NOT EXISTS confidence numeric(4, 3) NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS can_change boolean NOT NULL DEFAULT true;
ALTER TABLE relationship_item DROP CONSTRAINT IF EXISTS chk_relationship_item_type;
ALTER TABLE relationship_item ADD CONSTRAINT chk_relationship_item_type CHECK (
    item_type IN ('shared_memory', 'nickname', 'running_joke', 'codeword', 'ritual',
                  'shared_object', 'action_style', 'aura_stance', 'interaction_rule', 'boundary')
);
ALTER TABLE relationship_item DROP CONSTRAINT IF EXISTS chk_relationship_item_confidence;
ALTER TABLE relationship_item ADD CONSTRAINT chk_relationship_item_confidence
    CHECK (confidence BETWEEN 0 AND 1);

CREATE INDEX IF NOT EXISTS idx_relationship_item_user_type_status
    ON relationship_item (user_id, item_type, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS relationship_chapter (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sequence_no integer NOT NULL,
    source_key varchar(160) NOT NULL,
    title varchar(160) NOT NULL,
    summary text NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'current',
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    representative_message_id varchar(128),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_relationship_chapter_sequence CHECK (sequence_no >= 1),
    CONSTRAINT chk_relationship_chapter_status CHECK (status IN ('current', 'closed')),
    CONSTRAINT uq_relationship_chapter_user_sequence UNIQUE (user_id, sequence_no),
    CONSTRAINT uq_relationship_chapter_user_source UNIQUE (user_id, source_key)
);

ALTER TABLE relationship_chapter ADD COLUMN IF NOT EXISTS source_key varchar(160);
UPDATE relationship_chapter
SET source_key = 'legacy:' || id::text
WHERE source_key IS NULL OR btrim(source_key) = '';
ALTER TABLE relationship_chapter ALTER COLUMN source_key SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_relationship_chapter_user_source'
    ) THEN
        ALTER TABLE relationship_chapter
            ADD CONSTRAINT uq_relationship_chapter_user_source UNIQUE (user_id, source_key);
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_relationship_chapter_current_user
    ON relationship_chapter (user_id) WHERE status = 'current';
CREATE INDEX IF NOT EXISTS idx_relationship_chapter_user_sequence
    ON relationship_chapter (user_id, sequence_no DESC);

COMMENT ON TABLE relationship_item IS
    '共同记忆、私人语言、Aura 立场、交互纠偏和边界等稳定关系知识，不含亲密度分数';
COMMENT ON COLUMN relationship_item.world_layer IS
    '现实、真实共同经历、共同想象、愿望或承诺的事实分层';
COMMENT ON COLUMN relationship_item.cooldown_days IS
    '私人语言或关系物件自然复用后的最短冷却天数，避免机械重复';
COMMENT ON COLUMN relationship_item.confidence IS
    '该投影由真实对话支持的置信度，不代表关系好坏或亲密度';
COMMENT ON TABLE relationship_chapter IS
    '由真实重要事件形成的关系时间线章节；每个用户至多一个 current 章节';
COMMENT ON COLUMN relationship_chapter.source_key IS
    '来源消息生成的稳定幂等键，SSE 重试不得重复创建章节';

COMMIT;
