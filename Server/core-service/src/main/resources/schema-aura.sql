CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS aura_profile (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE,
    nickname varchar(64) NOT NULL DEFAULT 'Aura',
    persona_summary text,
    voice_style text,
    appearance text,
    boundaries text,
    system_prompt text,
    greeting_style varchar(64) DEFAULT 'warm',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id uuid PRIMARY KEY,
    display_name varchar(64),
    birthday date,
    pronouns varchar(32),
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
    locale varchar(32) NOT NULL DEFAULT 'zh-CN',
    preferences jsonb NOT NULL DEFAULT '{}'::jsonb,
    boundaries jsonb NOT NULL DEFAULT '{}'::jsonb,
    taboos jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS relationship_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE,
    aura_profile_id uuid REFERENCES aura_profile(id) ON DELETE SET NULL,
    relationship_stage varchar(32) NOT NULL DEFAULT 'new',
    intimacy_level int NOT NULL DEFAULT 0 CHECK (intimacy_level BETWEEN 0 AND 100),
    trust_level int NOT NULL DEFAULT 0 CHECK (trust_level BETWEEN 0 AND 100),
    affection_level int NOT NULL DEFAULT 0 CHECK (affection_level BETWEEN 0 AND 100),
    conflict_level int NOT NULL DEFAULT 0 CHECK (conflict_level BETWEEN 0 AND 100),
    current_mood varchar(64) NOT NULL DEFAULT 'neutral',
    last_interaction_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS relationship_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    relationship_state_id uuid REFERENCES relationship_state(id) ON DELETE SET NULL,
    event_type varchar(64) NOT NULL,
    title varchar(128),
    description text,
    delta_intimacy int NOT NULL DEFAULT 0,
    delta_trust int NOT NULL DEFAULT 0,
    delta_affection int NOT NULL DEFAULT 0,
    delta_conflict int NOT NULL DEFAULT 0,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    aura_profile_id uuid REFERENCES aura_profile(id) ON DELETE SET NULL,
    channel varchar(32) NOT NULL DEFAULT 'chat',
    title varchar(128),
    status varchar(32) NOT NULL DEFAULT 'active',
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    summary text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES conversation_session(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    sender_type varchar(32) NOT NULL,
    sender_id varchar(128),
    content text NOT NULL,
    content_type varchar(32) NOT NULL DEFAULT 'text',
    emotion_label varchar(64),
    token_count int NOT NULL DEFAULT 0,
    is_proactive boolean NOT NULL DEFAULT false,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS emotion_snapshot (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    session_id uuid REFERENCES conversation_session(id) ON DELETE CASCADE,
    message_id uuid REFERENCES chat_message(id) ON DELETE SET NULL,
    source varchar(32) NOT NULL DEFAULT 'chat',
    dominant_emotion varchar(64),
    valence numeric(4, 3),
    arousal numeric(4, 3),
    intensity numeric(4, 3),
    emotion_scores jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_item (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    aura_profile_id uuid REFERENCES aura_profile(id) ON DELETE SET NULL,
    source_session_id uuid REFERENCES conversation_session(id) ON DELETE SET NULL,
    source_message_id uuid REFERENCES chat_message(id) ON DELETE SET NULL,
    memory_type varchar(64) NOT NULL DEFAULT 'preference',
    title varchar(128),
    content text NOT NULL,
    embedding vector(768),
    salience int NOT NULL DEFAULT 50 CHECK (salience BETWEEN 0 AND 100),
    confidence numeric(4, 3),
    status varchar(32) NOT NULL DEFAULT 'active',
    tags jsonb NOT NULL DEFAULT '[]'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_recalled_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_relation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id uuid NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
    relation_type varchar(64) NOT NULL,
    target_type varchar(64) NOT NULL,
    target_id uuid NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prompt_version (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(128) NOT NULL,
    version varchar(32) NOT NULL,
    prompt_type varchar(64) NOT NULL DEFAULT 'system',
    content text NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'draft',
    created_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS safety_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    session_id uuid REFERENCES conversation_session(id) ON DELETE SET NULL,
    message_id uuid REFERENCES chat_message(id) ON DELETE SET NULL,
    risk_type varchar(64) NOT NULL,
    risk_level varchar(32) NOT NULL DEFAULT 'low',
    intervention text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS daily_checkin (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    checkin_date date NOT NULL,
    morning_sent_at timestamptz,
    evening_sent_at timestamptz,
    interaction_count int NOT NULL DEFAULT 0,
    streak_days int NOT NULL DEFAULT 0,
    mood_label varchar(64),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, checkin_date)
);

CREATE TABLE IF NOT EXISTS notification_plan (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    plan_type varchar(64) NOT NULL,
    title varchar(128) NOT NULL,
    message_template text NOT NULL,
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
    morning_window_start time,
    morning_window_end time,
    evening_window_start time,
    evening_window_end time,
    next_fire_at timestamptz,
    random_seed varchar(64),
    status varchar(32) NOT NULL DEFAULT 'active',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proactive_message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    notification_plan_id uuid REFERENCES notification_plan(id) ON DELETE SET NULL,
    trigger_type varchar(64) NOT NULL,
    title varchar(128),
    content text NOT NULL,
    scheduled_at timestamptz NOT NULL,
    sent_at timestamptz,
    status varchar(32) NOT NULL DEFAULT 'pending',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_export_job (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    job_type varchar(64) NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'pending',
    file_url text,
    requested_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id uuid,
    action varchar(128) NOT NULL,
    target_type varchar(64),
    target_id varchar(128),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb,
    ip_address varchar(64),
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE aura_profile IS 'Aura 人设配置表，保存每个用户的虚拟伴侣昵称、人格摘要、语气、边界和系统提示词';
COMMENT ON COLUMN aura_profile.user_id IS '所属用户 ID';
COMMENT ON COLUMN aura_profile.nickname IS 'Aura 昵称';
COMMENT ON COLUMN aura_profile.persona_summary IS '人设摘要';
COMMENT ON COLUMN aura_profile.voice_style IS '说话风格';
COMMENT ON COLUMN aura_profile.appearance IS '外观设定';
COMMENT ON COLUMN aura_profile.boundaries IS '陪伴边界和禁忌说明';
COMMENT ON COLUMN aura_profile.system_prompt IS '当前人设对应的系统提示词';

COMMENT ON TABLE user_profile IS '用户偏好画像表，保存称呼、语言、时区、偏好、边界和禁忌';
COMMENT ON COLUMN user_profile.user_id IS '用户 ID，和 users.id 一一对应';
COMMENT ON COLUMN user_profile.display_name IS '用户显示名称或希望被称呼的名字';
COMMENT ON COLUMN user_profile.preferences IS '用户偏好 JSON，例如喜欢的话题、作息、互动方式';
COMMENT ON COLUMN user_profile.boundaries IS '用户边界 JSON';
COMMENT ON COLUMN user_profile.taboos IS '禁忌话题 JSON 数组';

COMMENT ON TABLE relationship_state IS '当前关系状态表，保存关系阶段、亲密度、信任度、好感度和当前情绪';
COMMENT ON COLUMN relationship_state.relationship_stage IS '关系阶段，例如 new、warming、close、cooling、archived';
COMMENT ON COLUMN relationship_state.intimacy_level IS '亲密度，0 到 100';
COMMENT ON COLUMN relationship_state.trust_level IS '信任度，0 到 100';
COMMENT ON COLUMN relationship_state.affection_level IS '好感度，0 到 100';
COMMENT ON COLUMN relationship_state.conflict_level IS '冲突程度，0 到 100';

COMMENT ON TABLE relationship_event IS '关系变化流水表，记录每次对话或行为导致的亲密度、信任度变化';
COMMENT ON COLUMN relationship_event.event_type IS '事件类型，例如 chat_turn、daily_checkin、cooling、repair';
COMMENT ON COLUMN relationship_event.delta_intimacy IS '亲密度变化值';
COMMENT ON COLUMN relationship_event.delta_trust IS '信任度变化值';

COMMENT ON TABLE conversation_session IS '会话主表，保存一次连续聊天的会话状态、标题、渠道和摘要';
COMMENT ON COLUMN conversation_session.channel IS '会话来源渠道，例如 chat、proactive、admin';
COMMENT ON COLUMN conversation_session.status IS '会话状态，例如 active、ended、archived';
COMMENT ON COLUMN conversation_session.summary IS '会话摘要';

COMMENT ON TABLE chat_message IS '消息明细表，保存用户和 Aura 的每条消息';
COMMENT ON COLUMN chat_message.sender_type IS '发送者类型，例如 user、assistant、system';
COMMENT ON COLUMN chat_message.content IS '消息正文';
COMMENT ON COLUMN chat_message.emotion_label IS '消息关联的主情绪标签';
COMMENT ON COLUMN chat_message.is_proactive IS '是否为 Aura 主动触发消息，例如沉默后的低压力问候';

COMMENT ON TABLE emotion_snapshot IS '情绪快照表，保存每轮对话识别出的用户情绪和强度';
COMMENT ON COLUMN emotion_snapshot.dominant_emotion IS '主导情绪';
COMMENT ON COLUMN emotion_snapshot.valence IS '情绪效价，负数偏消极，正数偏积极';
COMMENT ON COLUMN emotion_snapshot.arousal IS '情绪唤醒度';
COMMENT ON COLUMN emotion_snapshot.intensity IS '情绪强度或置信度';

COMMENT ON TABLE memory_item IS '长期记忆表，保存从对话中抽取出的稳定偏好、重要事实、计划和情绪线索';
COMMENT ON COLUMN memory_item.memory_type IS '记忆类型，例如 preference、fact、plan、emotion、chat_signal';
COMMENT ON COLUMN memory_item.salience IS '记忆重要度，0 到 100';
COMMENT ON COLUMN memory_item.confidence IS '抽取置信度';
COMMENT ON COLUMN memory_item.embedding IS '向量检索字段';

COMMENT ON TABLE memory_relation IS '记忆关联表，用于关联记忆与消息、关系事件或其他业务对象';
COMMENT ON TABLE prompt_version IS 'Prompt 版本表，保存系统提示词、工具提示词等版本';
COMMENT ON TABLE safety_event IS '安全事件表，记录风险内容、干预动作和审计信息';
COMMENT ON TABLE daily_checkin IS '每日陪伴签到表，记录早晚问候、互动次数和连续陪伴天数';
COMMENT ON TABLE notification_plan IS '主动通知计划表，保存早晚随机问候、纪念日和召回计划';
COMMENT ON TABLE proactive_message IS '主动消息表，保存计划发送、已发送或取消的主动问候内容';
COMMENT ON TABLE user_export_job IS '用户数据导出、注销、清理任务表';
COMMENT ON TABLE admin_audit_log IS '后台管理操作审计日志表';

CREATE INDEX IF NOT EXISTS idx_relationship_event_user_time ON relationship_event(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationship_event_state ON relationship_event(relationship_state_id);
CREATE INDEX IF NOT EXISTS idx_conversation_session_user_time ON conversation_session(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_session_aura_profile ON conversation_session(aura_profile_id);
CREATE INDEX IF NOT EXISTS idx_chat_message_session_time ON chat_message(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chat_message_user_time ON chat_message(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_message_proactive_user_time ON chat_message(user_id, created_at DESC) WHERE is_proactive;
CREATE INDEX IF NOT EXISTS idx_emotion_snapshot_user_time ON emotion_snapshot(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emotion_snapshot_session_time ON emotion_snapshot(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emotion_snapshot_message ON emotion_snapshot(message_id);
CREATE INDEX IF NOT EXISTS idx_memory_item_user_status ON memory_item(user_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_item_aura_profile ON memory_item(aura_profile_id);
CREATE INDEX IF NOT EXISTS idx_memory_item_source_session ON memory_item(source_session_id);
CREATE INDEX IF NOT EXISTS idx_memory_item_source_message ON memory_item(source_message_id);
CREATE INDEX IF NOT EXISTS idx_memory_item_tags_gin ON memory_item USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_memory_item_metadata_gin ON memory_item USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_memory_item_embedding_hnsw ON memory_item USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_relation_memory ON memory_relation(memory_id);
CREATE INDEX IF NOT EXISTS idx_memory_relation_target ON memory_relation(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_safety_event_user_time ON safety_event(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_safety_event_session ON safety_event(session_id);
CREATE INDEX IF NOT EXISTS idx_daily_checkin_user_date ON daily_checkin(user_id, checkin_date DESC);
CREATE INDEX IF NOT EXISTS idx_notification_plan_user_fire ON notification_plan(user_id, status, next_fire_at);
CREATE INDEX IF NOT EXISTS idx_proactive_message_user_schedule ON proactive_message(user_id, status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_proactive_message_plan ON proactive_message(notification_plan_id);
CREATE INDEX IF NOT EXISTS idx_user_export_job_user_status ON user_export_job(user_id, status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_admin_time ON admin_audit_log(admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_profile_preferences_gin ON user_profile USING gin(preferences);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_aura_profile_user') THEN
        ALTER TABLE aura_profile ADD CONSTRAINT fk_aura_profile_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_profile_user') THEN
        ALTER TABLE user_profile ADD CONSTRAINT fk_user_profile_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_relationship_state_user') THEN
        ALTER TABLE relationship_state ADD CONSTRAINT fk_relationship_state_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_relationship_event_user') THEN
        ALTER TABLE relationship_event ADD CONSTRAINT fk_relationship_event_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_conversation_session_user') THEN
        ALTER TABLE conversation_session ADD CONSTRAINT fk_conversation_session_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_chat_message_user') THEN
        ALTER TABLE chat_message ADD CONSTRAINT fk_chat_message_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_emotion_snapshot_user') THEN
        ALTER TABLE emotion_snapshot ADD CONSTRAINT fk_emotion_snapshot_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_memory_item_user') THEN
        ALTER TABLE memory_item ADD CONSTRAINT fk_memory_item_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_safety_event_user') THEN
        ALTER TABLE safety_event ADD CONSTRAINT fk_safety_event_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_daily_checkin_user') THEN
        ALTER TABLE daily_checkin ADD CONSTRAINT fk_daily_checkin_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_notification_plan_user') THEN
        ALTER TABLE notification_plan ADD CONSTRAINT fk_notification_plan_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_proactive_message_user') THEN
        ALTER TABLE proactive_message ADD CONSTRAINT fk_proactive_message_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_export_job_user') THEN
        ALTER TABLE user_export_job ADD CONSTRAINT fk_user_export_job_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_admin_audit_log_admin') THEN
        ALTER TABLE admin_audit_log ADD CONSTRAINT fk_admin_audit_log_admin
            FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;
