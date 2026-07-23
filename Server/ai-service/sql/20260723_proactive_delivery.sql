BEGIN;

-- 将 proactive_message 升级为 PostgreSQL 权威的可靠投递 outbox。
-- 迁移只扩展现有表，不删除或重建主动消息；所有 ADD COLUMN 都可重复执行。
-- delivery_message_id 使用 pgcrypto 的 gen_random_uuid()；基线已启用扩展，
-- 此处再次声明以支持脚本在符合既有表结构的独立数据库上执行。
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- delivery_message_id 和 attempt_count 先以可空形式加入，完成历史数据回填后再收紧，
-- 避免已有消息因新增非空列而无法迁移。
ALTER TABLE proactive_message
    ADD COLUMN IF NOT EXISTS dedupe_key varchar(160),
    ADD COLUMN IF NOT EXISTS delivery_message_id varchar(128),
    ADD COLUMN IF NOT EXISTS attempt_count integer,
    ADD COLUMN IF NOT EXISTS claimed_until timestamptz,
    ADD COLUMN IF NOT EXISTS last_error text,
    ADD COLUMN IF NOT EXISTS cancelled_at timestamptz;

-- 每条历史消息获得一次生成后永不变化的投递消息 ID。调度器重试时必须复用该值，
-- 从而让下游聊天历史写入能够按同一 ID 幂等去重。
UPDATE proactive_message
SET delivery_message_id = gen_random_uuid()::text
WHERE delivery_message_id IS NULL;

-- 旧消息尚未经历可靠 outbox 重试，尝试次数从 0 开始。
UPDATE proactive_message
SET attempt_count = 0
WHERE attempt_count IS NULL;

ALTER TABLE proactive_message
    ALTER COLUMN delivery_message_id SET DEFAULT (gen_random_uuid())::text,
    ALTER COLUMN delivery_message_id SET NOT NULL,
    ALTER COLUMN attempt_count SET DEFAULT 0,
    ALTER COLUMN attempt_count SET NOT NULL;

-- 按稳定名称补充约束，保证脚本重复执行时不会创建重复对象。
-- dedupe_key 允许为空；一旦业务提供该键，同一用户只能创建一条对应消息。
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'proactive_message'::regclass
          AND conname = 'uq_proactive_message_user_dedupe'
    ) THEN
        ALTER TABLE proactive_message
            ADD CONSTRAINT uq_proactive_message_user_dedupe UNIQUE (user_id, dedupe_key);
    END IF;
END
$$;

-- processing 表示消息已被一个 worker 租约领取；租约到期后其他 worker 可以安全接管。
-- failed 是达到重试上限后的终态，cancelled 则保留被取消的审计记录。
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'proactive_message'::regclass
          AND conname = 'chk_proactive_message_status'
    ) THEN
        ALTER TABLE proactive_message
            ADD CONSTRAINT chk_proactive_message_status
            CHECK (status IN ('pending', 'processing', 'sent', 'skipped', 'failed', 'cancelled'));
    END IF;
END
$$;

-- 领取查询先按状态和计划时间缩小候选集，再用 claimed_until 判断是否可新领或接管。
CREATE INDEX IF NOT EXISTS idx_proactive_message_claim
    ON proactive_message (status, scheduled_at, claimed_until);

COMMENT ON COLUMN proactive_message.dedupe_key IS
    '业务幂等键；同一用户的非空键唯一，防止重复创建同一主动消息';
COMMENT ON COLUMN proactive_message.delivery_message_id IS
    '稳定的下游消息 ID；首次创建后所有投递重试必须复用';
COMMENT ON COLUMN proactive_message.attempt_count IS
    '已经执行的投递尝试次数，首次领取前为 0';
COMMENT ON COLUMN proactive_message.claimed_until IS
    'worker 领取租约截止时间；processing 且租约过期的记录允许被接管';
COMMENT ON COLUMN proactive_message.last_error IS
    '最近一次投递失败的精简错误信息；成功后由业务层清空';
COMMENT ON COLUMN proactive_message.cancelled_at IS
    '消息进入 cancelled 终态的时间；保留记录用于审计和幂等判断';

COMMIT;
