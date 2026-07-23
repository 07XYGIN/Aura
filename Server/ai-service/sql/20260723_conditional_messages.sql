BEGIN;

-- 条件消息只保存业务状态；实际聊天投递继续复用 proactive_message outbox。
CREATE TABLE IF NOT EXISTS conditional_message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_type varchar(24) NOT NULL,
    condition_type varchar(24) NOT NULL,
    title varchar(160) NOT NULL,
    content text NOT NULL,
    status varchar(16) NOT NULL DEFAULT 'sealed',
    deliver_at timestamptz,
    condition jsonb NOT NULL DEFAULT '{}'::jsonb,
    unlock_secret_hash varchar(255),
    dedupe_key varchar(160) NOT NULL,
    outbox_message_id uuid UNIQUE REFERENCES proactive_message(id)
        ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    source_message_id varchar(128),
    source_turn_id varchar(128),
    triggered_at timestamptz,
    delivered_at timestamptz,
    cancelled_at timestamptz,
    expires_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_conditional_message_type
        CHECK (message_type IN ('time_capsule', 'secret_vault')),
    CONSTRAINT chk_conditional_message_condition_type
        CHECK (condition_type IN ('time', 'keyword', 'project_status', 'github_event', 'passphrase')),
    CONSTRAINT chk_conditional_message_status
        CHECK (status IN ('sealed', 'queued', 'delivered', 'cancelled', 'expired', 'failed')),
    CONSTRAINT chk_conditional_message_time_requires_delivery
        CHECK (condition_type <> 'time' OR deliver_at IS NOT NULL),
    CONSTRAINT chk_conditional_message_version CHECK (version >= 1),
    CONSTRAINT uq_conditional_message_user_dedupe UNIQUE (user_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_conditional_message_time_due
    ON conditional_message (status, deliver_at)
    WHERE condition_type = 'time';

CREATE INDEX IF NOT EXISTS idx_conditional_message_user_status
    ON conditional_message (user_id, status, created_at DESC);

COMMENT ON TABLE conditional_message IS
    '时间胶囊与秘密保险箱权威状态；条件成立后通过 proactive_message 投递';
COMMENT ON COLUMN conditional_message.content IS
    '密封正文；sealed、queued 和 expired 状态的 API 响应不得返回';
COMMENT ON COLUMN conditional_message.condition IS
    '经过白名单清洗的关键词、项目或 GitHub 匹配配置，不保存口令明文';
COMMENT ON COLUMN conditional_message.unlock_secret_hash IS
    '口令保险箱使用的单向摘要，永不通过接口或日志返回';
COMMENT ON COLUMN conditional_message.outbox_message_id IS
    '条件成立后生成的唯一主动消息 outbox，用于原子状态同步和崩溃对账';

-- 兼容已经执行过本迁移早期版本的开发数据库。ORM 可能先更新业务记录、再插入
-- outbox，因此引用必须在事务提交时统一检查，而不能在单条 UPDATE 后立即检查。
ALTER TABLE conditional_message
    DROP CONSTRAINT IF EXISTS conditional_message_outbox_message_id_fkey;
ALTER TABLE conditional_message
    ADD CONSTRAINT conditional_message_outbox_message_id_fkey
    FOREIGN KEY (outbox_message_id) REFERENCES proactive_message(id)
    ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

-- 一次性事件 inbox 防止客户端重试或 GitHub redelivery 重复消费。
CREATE TABLE IF NOT EXISTS conditional_message_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type varchar(24) NOT NULL,
    event_id varchar(128) NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    matched_count integer NOT NULL DEFAULT 0,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_conditional_message_event_type
        CHECK (event_type IN ('keyword', 'project_status', 'github_event', 'passphrase')),
    CONSTRAINT chk_conditional_message_event_matched_count CHECK (matched_count >= 0),
    CONSTRAINT uq_conditional_message_event_user_event
        UNIQUE (user_id, event_type, event_id)
);

CREATE INDEX IF NOT EXISTS idx_conditional_message_event_user_time
    ON conditional_message_event (user_id, occurred_at DESC);

COMMENT ON TABLE conditional_message_event IS
    '条件消息一次性事件 inbox；同一用户、类型和事件 ID 只能消费一次';
COMMENT ON COLUMN conditional_message_event.payload IS
    '规范化后的审计负载，不包含密封正文或口令';

COMMIT;
