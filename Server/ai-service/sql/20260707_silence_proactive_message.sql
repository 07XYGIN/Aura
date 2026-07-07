ALTER TABLE chat_message
    ADD COLUMN IF NOT EXISTS is_proactive boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN chat_message.is_proactive IS '是否为 Aura 主动触发消息，例如沉默后的低压力问候';

CREATE INDEX IF NOT EXISTS idx_chat_message_proactive_user_time
    ON chat_message(user_id, created_at DESC)
    WHERE is_proactive;
