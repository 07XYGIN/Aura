CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS conversation_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    session_id uuid NOT NULL REFERENCES conversation_session(id) ON DELETE CASCADE,
    score int NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment text,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE conversation_feedback IS '对话理解度反馈表，记录用户在自然停顿后提交的“是否被理解”评分';
COMMENT ON COLUMN conversation_feedback.id IS '反馈记录 ID';
COMMENT ON COLUMN conversation_feedback.user_id IS '提交反馈的用户 ID';
COMMENT ON COLUMN conversation_feedback.session_id IS '反馈所属会话 ID';
COMMENT ON COLUMN conversation_feedback.score IS '1 到 5 星评分，衡量这次对话是否让用户感觉被理解';
COMMENT ON COLUMN conversation_feedback.comment IS '用户可选的一行文字反馈';
COMMENT ON COLUMN conversation_feedback.created_at IS '反馈提交时间';

CREATE TABLE IF NOT EXISTS user_behavior_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    session_id uuid REFERENCES conversation_session(id) ON DELETE SET NULL,
    message_id uuid REFERENCES chat_message(id) ON DELETE SET NULL,
    event_type varchar(64) NOT NULL,
    event_time timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE user_behavior_event IS '用户行为埋点表，记录对话频次、记忆引用、深夜使用、出戏标记等 MVP 指标';
COMMENT ON COLUMN user_behavior_event.id IS '行为事件 ID';
COMMENT ON COLUMN user_behavior_event.user_id IS '行为所属用户 ID';
COMMENT ON COLUMN user_behavior_event.session_id IS '行为所属会话 ID，可为空';
COMMENT ON COLUMN user_behavior_event.message_id IS '行为关联消息 ID，可为空';
COMMENT ON COLUMN user_behavior_event.event_type IS '事件类型，例如 chat_turn、memory_reference、off_model、conversation_feedback';
COMMENT ON COLUMN user_behavior_event.event_time IS '业务事件发生时间';
COMMENT ON COLUMN user_behavior_event.metadata IS '事件扩展信息 JSON，例如消息长度、会话耗时、是否深夜、记忆引用 query';
COMMENT ON COLUMN user_behavior_event.created_at IS '事件入库时间';

CREATE TABLE IF NOT EXISTS user_memory_entitlement (
    user_id uuid PRIMARY KEY,
    permanent_memory boolean NOT NULL DEFAULT false,
    expires_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE user_memory_entitlement IS '用户记忆权益表，用于控制免费 7 天记忆和付费永久记忆的检索权限';
COMMENT ON COLUMN user_memory_entitlement.user_id IS '用户 ID';
COMMENT ON COLUMN user_memory_entitlement.permanent_memory IS '是否拥有永久记忆权益';
COMMENT ON COLUMN user_memory_entitlement.expires_at IS '权益过期时间，为空表示永久或未设置过期';
COMMENT ON COLUMN user_memory_entitlement.metadata IS '权益扩展信息 JSON，例如来源、支付单号或运营备注';
COMMENT ON COLUMN user_memory_entitlement.created_at IS '权益记录创建时间';
COMMENT ON COLUMN user_memory_entitlement.updated_at IS '权益记录更新时间';

CREATE TABLE IF NOT EXISTS emotion_insight_report (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'preview',
    price_cents int NOT NULL DEFAULT 900,
    preview_keywords jsonb NOT NULL DEFAULT '[]'::jsonb,
    preview_text text NOT NULL,
    full_report jsonb NOT NULL DEFAULT '{}'::jsonb,
    paid_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE emotion_insight_report IS '情绪洞察报告表，保存累计对话达到阈值后的预览和付费完整报告';
COMMENT ON COLUMN emotion_insight_report.id IS '报告 ID';
COMMENT ON COLUMN emotion_insight_report.user_id IS '报告所属用户 ID';
COMMENT ON COLUMN emotion_insight_report.status IS '报告状态，preview 表示仅预览，paid 表示已付费解锁';
COMMENT ON COLUMN emotion_insight_report.price_cents IS '报告价格，单位为分，MVP 默认为 900';
COMMENT ON COLUMN emotion_insight_report.preview_keywords IS '预览展示的 3 个关键情绪词 JSON 数组';
COMMENT ON COLUMN emotion_insight_report.preview_text IS '预览洞察文案';
COMMENT ON COLUMN emotion_insight_report.full_report IS '完整报告 JSON，包含本周情绪关键词、模式分析和 Aura 观察';
COMMENT ON COLUMN emotion_insight_report.paid_at IS '付费解锁时间';
COMMENT ON COLUMN emotion_insight_report.created_at IS '报告创建时间';
COMMENT ON COLUMN emotion_insight_report.updated_at IS '报告更新时间';

CREATE INDEX IF NOT EXISTS idx_conversation_feedback_user_time ON conversation_feedback(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_feedback_session ON conversation_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_user_behavior_event_user_type_time ON user_behavior_event(user_id, event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_user_behavior_event_session_time ON user_behavior_event(session_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_user_behavior_event_metadata_gin ON user_behavior_event USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_user_memory_entitlement_expiry ON user_memory_entitlement(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_emotion_insight_report_user_time ON emotion_insight_report(user_id, created_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_conversation_feedback_user') THEN
        ALTER TABLE conversation_feedback ADD CONSTRAINT fk_conversation_feedback_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_behavior_event_user') THEN
        ALTER TABLE user_behavior_event ADD CONSTRAINT fk_user_behavior_event_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_memory_entitlement_user') THEN
        ALTER TABLE user_memory_entitlement ADD CONSTRAINT fk_user_memory_entitlement_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_emotion_insight_report_user') THEN
        ALTER TABLE emotion_insight_report ADD CONSTRAINT fk_emotion_insight_report_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;
