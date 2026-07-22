BEGIN;

-- Aura 当前是单用户私人陪伴服务。此迁移既可以清理旧数据库，也可以在空数据库
-- 创建当前五张业务/记忆表。四张 checkpoint_* 表仍由 PostgresSaver.setup() 管理。

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username varchar(64) NOT NULL UNIQUE,
    password varchar(255) NOT NULL,
    email varchar(255) UNIQUE,
    sex smallint,
    age integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_users_sex CHECK (sex IS NULL OR sex IN (0, 1)),
    CONSTRAINT chk_users_age CHECK (age IS NULL OR age BETWEEN 0 AND 150)
);

-- 兼容早期 users.sex 使用 integer 的数据库。
ALTER TABLE users
    ALTER COLUMN sex TYPE smallint USING sex::smallint;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'users'::regclass AND conname = 'chk_users_sex'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_sex
            CHECK (sex IS NULL OR sex IN (0, 1));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'users'::regclass AND conname = 'chk_users_age'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_age
            CHECK (age IS NULL OR age BETWEEN 0 AND 150);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS self_changelog_entry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    change_date date NOT NULL,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    title varchar(160) NOT NULL,
    detail text,
    category varchar(64) NOT NULL DEFAULT 'infra',
    reacted boolean NOT NULL DEFAULT false,
    reacted_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_self_changelog_entry_change_date_title UNIQUE (change_date, title)
);

CREATE INDEX IF NOT EXISTS idx_self_changelog_unreacted
    ON self_changelog_entry (reacted, change_date, created_at);
CREATE INDEX IF NOT EXISTS idx_self_changelog_occurred_at
    ON self_changelog_entry (occurred_at DESC);

CREATE TABLE IF NOT EXISTS proactive_message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    trigger_type varchar(64) NOT NULL,
    title varchar(128),
    content text NOT NULL,
    scheduled_at timestamptz NOT NULL,
    sent_at timestamptz,
    status varchar(32) NOT NULL DEFAULT 'pending',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_proactive_message_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 主动消息不再依赖未实现的通知计划表。
ALTER TABLE proactive_message
    DROP CONSTRAINT IF EXISTS proactive_message_notification_plan_id_fkey;
ALTER TABLE proactive_message
    DROP COLUMN IF EXISTS notification_plan_id;
DROP INDEX IF EXISTS ix_proactive_message_user_id;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'proactive_message'::regclass
          AND conname = 'fk_proactive_message_user'
    ) THEN
        ALTER TABLE proactive_message ADD CONSTRAINT fk_proactive_message_user
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_proactive_message_user_schedule
    ON proactive_message (user_id, status, scheduled_at);

-- LangChain PGVector 当前实际使用的唯一记忆数据源。
CREATE TABLE IF NOT EXISTS langchain_pg_collection (
    uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar NOT NULL UNIQUE,
    cmetadata json
);

ALTER TABLE langchain_pg_collection
    ALTER COLUMN cmetadata TYPE json USING cmetadata::json;

CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
    id varchar PRIMARY KEY,
    collection_id uuid,
    embedding vector,
    document varchar,
    cmetadata jsonb,
    CONSTRAINT langchain_pg_embedding_collection_id_fkey
        FOREIGN KEY (collection_id)
        REFERENCES langchain_pg_collection(uuid)
        ON DELETE CASCADE
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'langchain_pg_embedding'::regclass
          AND conname = 'langchain_pg_embedding_collection_id_fkey'
    ) THEN
        ALTER TABLE langchain_pg_embedding
            ADD CONSTRAINT langchain_pg_embedding_collection_id_fkey
            FOREIGN KEY (collection_id)
            REFERENCES langchain_pg_collection(uuid)
            ON DELETE CASCADE;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_cmetadata_gin
    ON langchain_pg_embedding USING gin (cmetadata jsonb_path_ops);

-- 删除早期关系积分、双轨聊天/记忆、情绪报告和多用户商业化遗留表。
DROP TABLE IF EXISTS relationship_event;
DROP TABLE IF EXISTS memory_relation;
DROP TABLE IF EXISTS safety_event;
DROP TABLE IF EXISTS user_behavior_event;
DROP TABLE IF EXISTS emotion_snapshot;
DROP TABLE IF EXISTS conversation_feedback;
DROP TABLE IF EXISTS memory_item;
DROP TABLE IF EXISTS chat_message;
DROP TABLE IF EXISTS conversation_session;
DROP TABLE IF EXISTS relationship_state;
DROP TABLE IF EXISTS aura_profile;

DROP TABLE IF EXISTS notification_plan;
DROP TABLE IF EXISTS invitation_code_redemption;
DROP TABLE IF EXISTS invitation_code;
DROP TABLE IF EXISTS daily_checkin;
DROP TABLE IF EXISTS emotion_insight_report;
DROP TABLE IF EXISTS prompt_version;
DROP TABLE IF EXISTS user_export_job;
DROP TABLE IF EXISTS admin_audit_log;
DROP TABLE IF EXISTS user_memory_entitlement;
DROP TABLE IF EXISTS user_profile;

-- 五张模型表必须存在。checkpoint_* 会在应用启动时由 LangGraph 创建并升级。
DO $$
DECLARE
    missing_table text;
BEGIN
    SELECT expected.table_name
    INTO missing_table
    FROM (
        VALUES
            ('users'),
            ('self_changelog_entry'),
            ('proactive_message'),
            ('langchain_pg_collection'),
            ('langchain_pg_embedding')
    ) AS expected(table_name)
    WHERE to_regclass('public.' || expected.table_name) IS NULL
    LIMIT 1;

    IF missing_table IS NOT NULL THEN
        RAISE EXCEPTION '迁移后缺少必要表：%', missing_table;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'proactive_message'
          AND column_name = 'notification_plan_id'
    ) THEN
        RAISE EXCEPTION 'proactive_message.notification_plan_id 仍然存在';
    END IF;
END
$$;

COMMIT;
