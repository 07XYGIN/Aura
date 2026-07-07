CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username varchar(64) NOT NULL UNIQUE,
    password varchar(255) NOT NULL,
    email varchar(255) UNIQUE,
    sex smallint,
    age int,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_users_sex CHECK (sex IN (0, 1)),
    CONSTRAINT chk_users_age CHECK (age IS NULL OR age BETWEEN 0 AND 150)
);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'users'
          AND column_name = 'sex'
          AND data_type <> 'smallint'
    ) THEN
        ALTER TABLE users ALTER COLUMN sex TYPE smallint USING sex::smallint;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_sex') THEN
        IF EXISTS (SELECT 1 FROM users WHERE sex IS NOT NULL AND sex NOT IN (0, 1)) THEN
            ALTER TABLE users ADD CONSTRAINT chk_users_sex CHECK (sex IN (0, 1)) NOT VALID;
        ELSE
            ALTER TABLE users ADD CONSTRAINT chk_users_sex CHECK (sex IN (0, 1));
        END IF;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_users_age') THEN
        ALTER TABLE users ADD CONSTRAINT chk_users_age CHECK (age IS NULL OR age BETWEEN 0 AND 150);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'users'
          AND column_name = 'created_at'
    ) THEN
        ALTER TABLE users ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'users'
          AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE users ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
    END IF;
END $$;

COMMENT ON TABLE users IS '用户基础账号表，保存登录认证、性别、年龄等核心资料';
COMMENT ON COLUMN users.id IS '用户 ID，主键 UUID';
COMMENT ON COLUMN users.username IS '登录用户名，全局唯一';
COMMENT ON COLUMN users.password IS '加密后的登录密码';
COMMENT ON COLUMN users.email IS '用户邮箱，可用于联系或账号恢复';
COMMENT ON COLUMN users.sex IS '用户性别：女(0)，男(1)，只允许这两个枚举值';
COMMENT ON COLUMN users.age IS '用户年龄，允许为空';
COMMENT ON COLUMN users.created_at IS '账号创建时间';
COMMENT ON COLUMN users.updated_at IS '账号更新时间';

CREATE TABLE IF NOT EXISTS invitation_code (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(64) NOT NULL UNIQUE,
    batch_name varchar(128),
    max_uses int NOT NULL DEFAULT 1 CHECK (max_uses > 0),
    used_count int NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    expires_at timestamptz,
    disabled_at timestamptz,
    created_by uuid REFERENCES users(id) ON DELETE SET NULL,
    last_used_by uuid REFERENCES users(id) ON DELETE SET NULL,
    last_used_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_invitation_code_used_count CHECK (used_count <= max_uses)
);

COMMENT ON TABLE invitation_code IS '邀请码主表，保存注册邀请码、批次、可用次数和禁用状态';
COMMENT ON COLUMN invitation_code.id IS '邀请码 ID';
COMMENT ON COLUMN invitation_code.code IS '邀请码明文编码，统一按大写匹配';
COMMENT ON COLUMN invitation_code.batch_name IS '邀请码批次名称，便于运营区分来源';
COMMENT ON COLUMN invitation_code.max_uses IS '邀请码最大可使用次数';
COMMENT ON COLUMN invitation_code.used_count IS '邀请码已使用次数';
COMMENT ON COLUMN invitation_code.expires_at IS '邀请码过期时间，为空表示不过期';
COMMENT ON COLUMN invitation_code.disabled_at IS '邀请码禁用时间，为空表示未禁用';
COMMENT ON COLUMN invitation_code.created_by IS '创建该邀请码的管理员或用户 ID';
COMMENT ON COLUMN invitation_code.last_used_by IS '最后一次使用该邀请码的用户 ID';
COMMENT ON COLUMN invitation_code.last_used_at IS '最后一次使用时间';
COMMENT ON COLUMN invitation_code.metadata IS '邀请码扩展备注 JSON，例如渠道、投放批次或运营说明';
COMMENT ON COLUMN invitation_code.created_at IS '邀请码创建时间';
COMMENT ON COLUMN invitation_code.updated_at IS '邀请码更新时间';

CREATE TABLE IF NOT EXISTS invitation_code_redemption (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invite_code_id uuid NOT NULL REFERENCES invitation_code(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    redeemed_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (invite_code_id, user_id)
);

COMMENT ON TABLE invitation_code_redemption IS '邀请码兑换记录表，记录用户使用邀请码完成注册的流水';
COMMENT ON COLUMN invitation_code_redemption.id IS '兑换记录 ID';
COMMENT ON COLUMN invitation_code_redemption.invite_code_id IS '被兑换的邀请码 ID';
COMMENT ON COLUMN invitation_code_redemption.user_id IS '兑换邀请码的用户 ID';
COMMENT ON COLUMN invitation_code_redemption.redeemed_at IS '兑换时间';
COMMENT ON COLUMN invitation_code_redemption.metadata IS '兑换扩展备注 JSON';

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

COMMENT ON TABLE aura_profile IS 'Aura 人设配置表，保存每个用户的虚拟伴侣昵称、人设、语气、边界和系统提示词';
COMMENT ON COLUMN aura_profile.id IS 'Aura 人设 ID';
COMMENT ON COLUMN aura_profile.user_id IS '所属用户 ID';
COMMENT ON COLUMN aura_profile.nickname IS 'Aura 昵称';
COMMENT ON COLUMN aura_profile.persona_summary IS '人设摘要';
COMMENT ON COLUMN aura_profile.voice_style IS '说话风格';
COMMENT ON COLUMN aura_profile.appearance IS '外观设定';
COMMENT ON COLUMN aura_profile.boundaries IS '陪伴边界和禁忌说明';
COMMENT ON COLUMN aura_profile.system_prompt IS '当前人设对应的系统提示词';
COMMENT ON COLUMN aura_profile.greeting_style IS '主动问候风格';
COMMENT ON COLUMN aura_profile.created_at IS '人设创建时间';
COMMENT ON COLUMN aura_profile.updated_at IS '人设更新时间';

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
    city_adcode varchar(6),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_user_profile_city_adcode CHECK (city_adcode IS NULL OR city_adcode ~ '^[0-9]{6}$')
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'user_profile'
          AND column_name = 'city_adcode'
    ) THEN
        ALTER TABLE user_profile ADD COLUMN city_adcode varchar(6);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_user_profile_city_adcode') THEN
        ALTER TABLE user_profile ADD CONSTRAINT chk_user_profile_city_adcode CHECK (city_adcode IS NULL OR city_adcode ~ '^[0-9]{6}$');
    END IF;
END $$;

COMMENT ON TABLE user_profile IS '用户偏好画像表，保存称呼、语言、时区、城市 adcode、偏好、边界和禁忌';
COMMENT ON COLUMN user_profile.user_id IS '用户 ID，和 users.id 一一对应';
COMMENT ON COLUMN user_profile.display_name IS '用户显示名称或希望被称呼的名字';
COMMENT ON COLUMN user_profile.birthday IS '用户生日';
COMMENT ON COLUMN user_profile.pronouns IS '用户偏好的称谓或代词';
COMMENT ON COLUMN user_profile.timezone IS '用户所在时区';
COMMENT ON COLUMN user_profile.locale IS '用户界面或对话语言';
COMMENT ON COLUMN user_profile.preferences IS '用户偏好 JSON，例如喜欢的话题、作息、互动方式';
COMMENT ON COLUMN user_profile.boundaries IS '用户边界 JSON';
COMMENT ON COLUMN user_profile.taboos IS '禁忌话题 JSON 数组';
COMMENT ON COLUMN user_profile.city_adcode IS '高德地图城市 adcode，用于天气等位置相关工具';
COMMENT ON COLUMN user_profile.created_at IS '画像创建时间';
COMMENT ON COLUMN user_profile.updated_at IS '画像更新时间';

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

COMMENT ON TABLE relationship_state IS '当前关系状态表，保存关系阶段、亲密度、信任度、好感度和当前情绪';
COMMENT ON COLUMN relationship_state.id IS '关系状态 ID';
COMMENT ON COLUMN relationship_state.user_id IS '所属用户 ID';
COMMENT ON COLUMN relationship_state.aura_profile_id IS '关联的 Aura 人设 ID';
COMMENT ON COLUMN relationship_state.relationship_stage IS '关系阶段，例如 new、warming、close、cooling、archived';
COMMENT ON COLUMN relationship_state.intimacy_level IS '亲密度，0 到 100';
COMMENT ON COLUMN relationship_state.trust_level IS '信任度，0 到 100';
COMMENT ON COLUMN relationship_state.affection_level IS '好感度，0 到 100';
COMMENT ON COLUMN relationship_state.conflict_level IS '冲突程度，0 到 100';
COMMENT ON COLUMN relationship_state.current_mood IS 'Aura 当前关系情绪';
COMMENT ON COLUMN relationship_state.last_interaction_at IS '最近一次互动时间';
COMMENT ON COLUMN relationship_state.metadata IS '关系状态扩展备注 JSON';
COMMENT ON COLUMN relationship_state.created_at IS '关系状态创建时间';
COMMENT ON COLUMN relationship_state.updated_at IS '关系状态更新时间';

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

COMMENT ON TABLE relationship_event IS '关系变化流水表，记录每次对话或行为导致的亲密度、信任度变化';
COMMENT ON COLUMN relationship_event.id IS '关系事件 ID';
COMMENT ON COLUMN relationship_event.user_id IS '所属用户 ID';
COMMENT ON COLUMN relationship_event.relationship_state_id IS '关联的关系状态 ID';
COMMENT ON COLUMN relationship_event.event_type IS '事件类型，例如 chat_turn、daily_checkin、cooling、repair';
COMMENT ON COLUMN relationship_event.title IS '事件标题';
COMMENT ON COLUMN relationship_event.description IS '事件描述';
COMMENT ON COLUMN relationship_event.delta_intimacy IS '亲密度变化值';
COMMENT ON COLUMN relationship_event.delta_trust IS '信任度变化值';
COMMENT ON COLUMN relationship_event.delta_affection IS '好感度变化值';
COMMENT ON COLUMN relationship_event.delta_conflict IS '冲突程度变化值';
COMMENT ON COLUMN relationship_event.occurred_at IS '事件发生时间';
COMMENT ON COLUMN relationship_event.metadata IS '事件扩展备注 JSON';
COMMENT ON COLUMN relationship_event.created_at IS '事件入库时间';

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

COMMENT ON TABLE conversation_session IS '会话主表，保存一次连续聊天的会话状态、标题、渠道和摘要';
COMMENT ON COLUMN conversation_session.id IS '会话 ID';
COMMENT ON COLUMN conversation_session.user_id IS '所属用户 ID';
COMMENT ON COLUMN conversation_session.aura_profile_id IS '关联的 Aura 人设 ID';
COMMENT ON COLUMN conversation_session.channel IS '会话来源渠道，例如 chat、proactive、admin';
COMMENT ON COLUMN conversation_session.title IS '会话标题';
COMMENT ON COLUMN conversation_session.status IS '会话状态，例如 active、ended、archived';
COMMENT ON COLUMN conversation_session.started_at IS '会话开始时间';
COMMENT ON COLUMN conversation_session.ended_at IS '会话结束时间';
COMMENT ON COLUMN conversation_session.summary IS '会话摘要';
COMMENT ON COLUMN conversation_session.metadata IS '会话扩展备注 JSON';
COMMENT ON COLUMN conversation_session.created_at IS '会话创建时间';
COMMENT ON COLUMN conversation_session.updated_at IS '会话更新时间';

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
    batch_id uuid,
    batch_index int,
    sent_at timestamptz,
    is_proactive boolean NOT NULL DEFAULT false,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'chat_message'
          AND column_name = 'batch_id'
    ) THEN
        ALTER TABLE chat_message ADD COLUMN batch_id uuid;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'chat_message'
          AND column_name = 'batch_index'
    ) THEN
        ALTER TABLE chat_message ADD COLUMN batch_index int;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'chat_message'
          AND column_name = 'sent_at'
    ) THEN
        ALTER TABLE chat_message ADD COLUMN sent_at timestamptz;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'chat_message'
          AND column_name = 'is_proactive'
    ) THEN
        ALTER TABLE chat_message ADD COLUMN is_proactive boolean NOT NULL DEFAULT false;
    END IF;
END $$;

COMMENT ON TABLE chat_message IS '消息明细表，保存用户和 Aura 的每条消息';
COMMENT ON COLUMN chat_message.id IS '消息 ID';
COMMENT ON COLUMN chat_message.session_id IS '所属会话 ID';
COMMENT ON COLUMN chat_message.user_id IS '所属用户 ID';
COMMENT ON COLUMN chat_message.sender_type IS '发送者类型，例如 user、assistant、system';
COMMENT ON COLUMN chat_message.sender_id IS '发送者业务 ID，例如 aura';
COMMENT ON COLUMN chat_message.content IS '消息正文';
COMMENT ON COLUMN chat_message.content_type IS '消息类型，例如 text、text_with_attachment';
COMMENT ON COLUMN chat_message.emotion_label IS '消息关联的主情绪标签';
COMMENT ON COLUMN chat_message.token_count IS '消息 token 数估算';
COMMENT ON COLUMN chat_message.batch_id IS '回复批次 ID，用于标识一次模型调用拆出的多条 Aura 消息';
COMMENT ON COLUMN chat_message.batch_index IS '批次内消息顺序，从 0 开始';
COMMENT ON COLUMN chat_message.sent_at IS '消息实际或计划发送时间，统一使用带时区时间';
COMMENT ON COLUMN chat_message.is_proactive IS '是否为 Aura 主动触发消息，例如沉默后的低压力问候';
COMMENT ON COLUMN chat_message.metadata IS '消息扩展备注 JSON，例如附件列表';
COMMENT ON COLUMN chat_message.created_at IS '消息创建时间';

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

COMMENT ON TABLE emotion_snapshot IS '情绪快照表，保存每轮对话识别出的用户情绪和强度';
COMMENT ON COLUMN emotion_snapshot.id IS '情绪快照 ID';
COMMENT ON COLUMN emotion_snapshot.user_id IS '所属用户 ID';
COMMENT ON COLUMN emotion_snapshot.session_id IS '关联会话 ID';
COMMENT ON COLUMN emotion_snapshot.message_id IS '关联消息 ID';
COMMENT ON COLUMN emotion_snapshot.source IS '情绪来源，例如 chat、manual、system';
COMMENT ON COLUMN emotion_snapshot.dominant_emotion IS '主导情绪';
COMMENT ON COLUMN emotion_snapshot.valence IS '情绪效价，负数偏消极，正数偏积极';
COMMENT ON COLUMN emotion_snapshot.arousal IS '情绪唤醒度';
COMMENT ON COLUMN emotion_snapshot.intensity IS '情绪强度或置信度';
COMMENT ON COLUMN emotion_snapshot.emotion_scores IS '情绪评分 JSON';
COMMENT ON COLUMN emotion_snapshot.reason IS '情绪识别原因';
COMMENT ON COLUMN emotion_snapshot.created_at IS '快照创建时间';

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

COMMENT ON TABLE memory_item IS '结构化记忆表，保存从对话中抽取出的长期或中期记忆及业务备注';
COMMENT ON COLUMN memory_item.id IS '记忆 ID';
COMMENT ON COLUMN memory_item.user_id IS '所属用户 ID';
COMMENT ON COLUMN memory_item.aura_profile_id IS '关联 Aura 人设 ID';
COMMENT ON COLUMN memory_item.source_session_id IS '记忆来源会话 ID';
COMMENT ON COLUMN memory_item.source_message_id IS '记忆来源消息 ID';
COMMENT ON COLUMN memory_item.memory_type IS '记忆类型，例如 long_term、mid_term、preference、fact、plan、emotion、chat_signal';
COMMENT ON COLUMN memory_item.title IS '记忆标题';
COMMENT ON COLUMN memory_item.content IS '记忆正文';
COMMENT ON COLUMN memory_item.embedding IS '结构化记忆向量字段，用于相似度检索';
COMMENT ON COLUMN memory_item.salience IS '记忆重要度，0 到 100';
COMMENT ON COLUMN memory_item.confidence IS '抽取置信度';
COMMENT ON COLUMN memory_item.status IS '记忆状态，例如 active、archived、deleted';
COMMENT ON COLUMN memory_item.tags IS '记忆标签 JSON 数组';
COMMENT ON COLUMN memory_item.metadata IS '记忆扩展备注 JSON，例如 memoryScope、抽取原因';
COMMENT ON COLUMN memory_item.last_recalled_at IS '最近一次被检索或引用时间';
COMMENT ON COLUMN memory_item.created_at IS '记忆创建时间';
COMMENT ON COLUMN memory_item.updated_at IS '记忆更新时间';

CREATE TABLE IF NOT EXISTS memory_relation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id uuid NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
    relation_type varchar(64) NOT NULL,
    target_type varchar(64) NOT NULL,
    target_id uuid NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE memory_relation IS '记忆关联表，用于关联记忆与消息、关系事件或其他业务对象';
COMMENT ON COLUMN memory_relation.id IS '关联记录 ID';
COMMENT ON COLUMN memory_relation.memory_id IS '源记忆 ID';
COMMENT ON COLUMN memory_relation.relation_type IS '关联类型，例如 source、supports、contradicts';
COMMENT ON COLUMN memory_relation.target_type IS '目标对象类型，例如 chat_message、relationship_event';
COMMENT ON COLUMN memory_relation.target_id IS '目标对象 ID';
COMMENT ON COLUMN memory_relation.metadata IS '关联扩展备注 JSON';
COMMENT ON COLUMN memory_relation.created_at IS '关联创建时间';

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

COMMENT ON TABLE prompt_version IS 'Prompt 版本表，保存系统提示词、工具提示词等版本';
COMMENT ON COLUMN prompt_version.id IS 'Prompt 版本 ID';
COMMENT ON COLUMN prompt_version.name IS 'Prompt 名称';
COMMENT ON COLUMN prompt_version.version IS 'Prompt 版本号';
COMMENT ON COLUMN prompt_version.prompt_type IS 'Prompt 类型，例如 system、tool、memory';
COMMENT ON COLUMN prompt_version.content IS 'Prompt 内容';
COMMENT ON COLUMN prompt_version.status IS '版本状态，例如 draft、active、archived';
COMMENT ON COLUMN prompt_version.created_by IS '创建人用户 ID';
COMMENT ON COLUMN prompt_version.created_at IS '版本创建时间';

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

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'self_changelog_entry_change_date_title_key'
          AND conrelid = 'self_changelog_entry'::regclass
    )
    AND NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_self_changelog_entry_change_date_title'
          AND conrelid = 'self_changelog_entry'::regclass
    ) THEN
        ALTER TABLE self_changelog_entry
            RENAME CONSTRAINT self_changelog_entry_change_date_title_key
            TO uq_self_changelog_entry_change_date_title;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_self_changelog_entry_change_date_title'
          AND conrelid = 'self_changelog_entry'::regclass
    ) THEN
        ALTER TABLE self_changelog_entry
            ADD CONSTRAINT uq_self_changelog_entry_change_date_title UNIQUE (change_date, title);
    END IF;
END
$$;

ALTER TABLE self_changelog_entry
    ADD COLUMN IF NOT EXISTS occurred_at timestamptz;

UPDATE self_changelog_entry
SET occurred_at = change_date::timestamptz
WHERE occurred_at IS NULL;

ALTER TABLE self_changelog_entry
    ALTER COLUMN occurred_at SET DEFAULT now(),
    ALTER COLUMN occurred_at SET NOT NULL;

ALTER TABLE self_changelog_entry
    ADD COLUMN IF NOT EXISTS category varchar(64) NOT NULL DEFAULT 'infra';

COMMENT ON TABLE self_changelog_entry IS 'Aura 自我更新日志表，记录 q 对 Aura 做过的能力和人格变化，供模型形成自我认知';
COMMENT ON COLUMN self_changelog_entry.id IS '自我更新日志 ID';
COMMENT ON COLUMN self_changelog_entry.change_date IS '改动日期';
COMMENT ON COLUMN self_changelog_entry.occurred_at IS '改动实际发生时间，支持后台补录和按时间倒序展示';
COMMENT ON COLUMN self_changelog_entry.title IS '给 Aura 理解的生活化改动标题';
COMMENT ON COLUMN self_changelog_entry.detail IS '改动细节，提供给 Aura 形成主观反应的素材';
COMMENT ON COLUMN self_changelog_entry.category IS '更新分类，例如 memory、perception、personality、infra';
COMMENT ON COLUMN self_changelog_entry.reacted IS 'Aura 是否已经在对话中自然回应过这条改动';
COMMENT ON COLUMN self_changelog_entry.reacted_at IS 'Aura 首次回应该改动的时间';
COMMENT ON COLUMN self_changelog_entry.metadata IS '自我更新日志扩展备注 JSON';
COMMENT ON COLUMN self_changelog_entry.created_at IS '日志创建时间';
COMMENT ON COLUMN self_changelog_entry.updated_at IS '日志更新时间';

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

COMMENT ON TABLE safety_event IS '安全事件表，记录风险内容、干预动作和审计信息';
COMMENT ON COLUMN safety_event.id IS '安全事件 ID';
COMMENT ON COLUMN safety_event.user_id IS '所属用户 ID';
COMMENT ON COLUMN safety_event.session_id IS '关联会话 ID';
COMMENT ON COLUMN safety_event.message_id IS '关联消息 ID';
COMMENT ON COLUMN safety_event.risk_type IS '风险类型';
COMMENT ON COLUMN safety_event.risk_level IS '风险等级';
COMMENT ON COLUMN safety_event.intervention IS '干预说明';
COMMENT ON COLUMN safety_event.metadata IS '安全事件扩展备注 JSON';
COMMENT ON COLUMN safety_event.created_at IS '安全事件创建时间';

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

COMMENT ON TABLE daily_checkin IS '每日陪伴签到表，记录早晚问候、互动次数和连续陪伴天数';
COMMENT ON COLUMN daily_checkin.id IS '签到记录 ID';
COMMENT ON COLUMN daily_checkin.user_id IS '所属用户 ID';
COMMENT ON COLUMN daily_checkin.checkin_date IS '签到日期';
COMMENT ON COLUMN daily_checkin.morning_sent_at IS '早晨问候发送时间';
COMMENT ON COLUMN daily_checkin.evening_sent_at IS '晚间问候发送时间';
COMMENT ON COLUMN daily_checkin.interaction_count IS '当天互动次数';
COMMENT ON COLUMN daily_checkin.streak_days IS '连续互动天数';
COMMENT ON COLUMN daily_checkin.mood_label IS '当天情绪标签';
COMMENT ON COLUMN daily_checkin.metadata IS '签到扩展备注 JSON';
COMMENT ON COLUMN daily_checkin.created_at IS '签到记录创建时间';
COMMENT ON COLUMN daily_checkin.updated_at IS '签到记录更新时间';

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

COMMENT ON TABLE notification_plan IS '主动通知计划表，保存早晚随机问候、纪念日和召回计划';
COMMENT ON COLUMN notification_plan.id IS '通知计划 ID';
COMMENT ON COLUMN notification_plan.user_id IS '所属用户 ID';
COMMENT ON COLUMN notification_plan.plan_type IS '计划类型，例如 daily_greeting、anniversary、recall';
COMMENT ON COLUMN notification_plan.title IS '计划标题';
COMMENT ON COLUMN notification_plan.message_template IS '消息模板';
COMMENT ON COLUMN notification_plan.timezone IS '计划执行时区';
COMMENT ON COLUMN notification_plan.morning_window_start IS '早晨发送窗口开始时间';
COMMENT ON COLUMN notification_plan.morning_window_end IS '早晨发送窗口结束时间';
COMMENT ON COLUMN notification_plan.evening_window_start IS '晚间发送窗口开始时间';
COMMENT ON COLUMN notification_plan.evening_window_end IS '晚间发送窗口结束时间';
COMMENT ON COLUMN notification_plan.next_fire_at IS '下一次计划触发时间';
COMMENT ON COLUMN notification_plan.random_seed IS '随机化种子';
COMMENT ON COLUMN notification_plan.status IS '计划状态，例如 active、paused、archived';
COMMENT ON COLUMN notification_plan.metadata IS '通知计划扩展备注 JSON';
COMMENT ON COLUMN notification_plan.created_at IS '计划创建时间';
COMMENT ON COLUMN notification_plan.updated_at IS '计划更新时间';

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

COMMENT ON TABLE proactive_message IS '主动消息表，保存计划发送、已发送或取消的主动问候内容';
COMMENT ON COLUMN proactive_message.id IS '主动消息 ID';
COMMENT ON COLUMN proactive_message.user_id IS '所属用户 ID';
COMMENT ON COLUMN proactive_message.notification_plan_id IS '关联通知计划 ID';
COMMENT ON COLUMN proactive_message.trigger_type IS '触发类型，例如 daily、memory_recall、manual';
COMMENT ON COLUMN proactive_message.title IS '主动消息标题';
COMMENT ON COLUMN proactive_message.content IS '主动消息正文';
COMMENT ON COLUMN proactive_message.scheduled_at IS '计划发送时间';
COMMENT ON COLUMN proactive_message.sent_at IS '实际发送时间';
COMMENT ON COLUMN proactive_message.status IS '消息状态，例如 pending、sent、cancelled';
COMMENT ON COLUMN proactive_message.metadata IS '主动消息扩展备注 JSON';
COMMENT ON COLUMN proactive_message.created_at IS '主动消息创建时间';
COMMENT ON COLUMN proactive_message.updated_at IS '主动消息更新时间';

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

COMMENT ON TABLE user_export_job IS '用户数据导出、注销、清理任务表';
COMMENT ON COLUMN user_export_job.id IS '导出任务 ID';
COMMENT ON COLUMN user_export_job.user_id IS '所属用户 ID';
COMMENT ON COLUMN user_export_job.job_type IS '任务类型，例如 export、delete、cleanup';
COMMENT ON COLUMN user_export_job.status IS '任务状态，例如 pending、running、finished、failed';
COMMENT ON COLUMN user_export_job.file_url IS '导出文件地址';
COMMENT ON COLUMN user_export_job.requested_at IS '任务请求时间';
COMMENT ON COLUMN user_export_job.finished_at IS '任务完成时间';
COMMENT ON COLUMN user_export_job.metadata IS '任务扩展备注 JSON';

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

COMMENT ON TABLE admin_audit_log IS '后台管理操作审计日志表';
COMMENT ON COLUMN admin_audit_log.id IS '审计日志 ID';
COMMENT ON COLUMN admin_audit_log.admin_user_id IS '管理员用户 ID';
COMMENT ON COLUMN admin_audit_log.action IS '操作名称';
COMMENT ON COLUMN admin_audit_log.target_type IS '操作目标类型';
COMMENT ON COLUMN admin_audit_log.target_id IS '操作目标 ID';
COMMENT ON COLUMN admin_audit_log.detail IS '操作详情 JSON';
COMMENT ON COLUMN admin_audit_log.ip_address IS '操作者 IP 地址';
COMMENT ON COLUMN admin_audit_log.created_at IS '审计日志创建时间';

CREATE TABLE IF NOT EXISTS conversation_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    session_id uuid NOT NULL REFERENCES conversation_session(id) ON DELETE CASCADE,
    score int NOT NULL CHECK (score BETWEEN 1 AND 5),
    comment text,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE conversation_feedback IS '对话理解度反馈表，记录用户在自然停顿后提交的是否被理解评分';
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
COMMENT ON COLUMN user_behavior_event.metadata IS '事件扩展备注 JSON，例如消息长度、会话耗时、是否深夜、记忆引用 query';
COMMENT ON COLUMN user_behavior_event.created_at IS '事件入库时间';

CREATE TABLE IF NOT EXISTS user_memory_entitlement (
    user_id uuid PRIMARY KEY,
    permanent_memory boolean NOT NULL DEFAULT false,
    expires_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE user_memory_entitlement IS '用户记忆权益表，用于控制免费记忆和付费永久记忆的检索权限';
COMMENT ON COLUMN user_memory_entitlement.user_id IS '用户 ID';
COMMENT ON COLUMN user_memory_entitlement.permanent_memory IS '是否拥有永久记忆权益';
COMMENT ON COLUMN user_memory_entitlement.expires_at IS '权益过期时间，为空表示永久或未设置过期';
COMMENT ON COLUMN user_memory_entitlement.metadata IS '权益扩展备注 JSON，例如来源、支付单号或运营备注';
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
COMMENT ON COLUMN emotion_insight_report.price_cents IS '报告价格，单位为分';
COMMENT ON COLUMN emotion_insight_report.preview_keywords IS '预览展示的关键情绪词 JSON 数组';
COMMENT ON COLUMN emotion_insight_report.preview_text IS '预览洞察文案';
COMMENT ON COLUMN emotion_insight_report.full_report IS '完整报告 JSON，包含情绪关键词、模式分析和 Aura 观察';
COMMENT ON COLUMN emotion_insight_report.paid_at IS '付费解锁时间';
COMMENT ON COLUMN emotion_insight_report.created_at IS '报告创建时间';
COMMENT ON COLUMN emotion_insight_report.updated_at IS '报告更新时间';

CREATE TABLE IF NOT EXISTS langchain_pg_collection (
    uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar NOT NULL UNIQUE,
    cmetadata json
);

ALTER TABLE langchain_pg_collection ALTER COLUMN uuid SET DEFAULT gen_random_uuid();

COMMENT ON TABLE langchain_pg_collection IS 'LangChain PGVector 集合表，用于区分长期记忆和中期记忆向量集合';
COMMENT ON COLUMN langchain_pg_collection.uuid IS '向量集合 ID';
COMMENT ON COLUMN langchain_pg_collection.name IS '向量集合名称，例如 aura、aura_mid_term';
COMMENT ON COLUMN langchain_pg_collection.cmetadata IS '集合扩展备注 JSON';

CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
    id varchar PRIMARY KEY,
    collection_id uuid REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
    embedding vector,
    document varchar,
    cmetadata jsonb
);

COMMENT ON TABLE langchain_pg_embedding IS 'LangChain PGVector 向量表，保存长期记忆和中期记忆的文档、向量和元数据';
COMMENT ON COLUMN langchain_pg_embedding.id IS '向量文档 ID';
COMMENT ON COLUMN langchain_pg_embedding.collection_id IS '所属向量集合 ID';
COMMENT ON COLUMN langchain_pg_embedding.embedding IS '记忆文本向量';
COMMENT ON COLUMN langchain_pg_embedding.document IS '记忆原文';
COMMENT ON COLUMN langchain_pg_embedding.cmetadata IS '记忆元数据 JSON，包含 user_id、memory_scope、create_time、last_recalled_at 等';

CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id text NOT NULL,
    checkpoint_ns text NOT NULL DEFAULT '',
    checkpoint_id text NOT NULL,
    parent_checkpoint_id text,
    type text,
    checkpoint jsonb NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

COMMENT ON TABLE checkpoints IS 'LangGraph 检查点主表，保存会话线程的状态快照、父快照和元数据';
COMMENT ON COLUMN checkpoints.thread_id IS 'LangGraph 线程 ID';
COMMENT ON COLUMN checkpoints.checkpoint_ns IS '检查点命名空间，默认空字符串';
COMMENT ON COLUMN checkpoints.checkpoint_id IS '检查点 ID';
COMMENT ON COLUMN checkpoints.parent_checkpoint_id IS '父检查点 ID，用于恢复状态链路';
COMMENT ON COLUMN checkpoints.type IS '检查点序列化类型';
COMMENT ON COLUMN checkpoints.checkpoint IS '检查点状态快照 JSON';
COMMENT ON COLUMN checkpoints.metadata IS '检查点元数据 JSON';

CREATE TABLE IF NOT EXISTS checkpoint_blobs (
    thread_id text NOT NULL,
    checkpoint_ns text NOT NULL DEFAULT '',
    channel text NOT NULL,
    version text NOT NULL,
    type text NOT NULL,
    blob bytea,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

COMMENT ON TABLE checkpoint_blobs IS 'LangGraph 检查点二进制片段表，保存各状态通道的序列化数据块';
COMMENT ON COLUMN checkpoint_blobs.thread_id IS 'LangGraph 线程 ID';
COMMENT ON COLUMN checkpoint_blobs.checkpoint_ns IS '检查点命名空间，默认空字符串';
COMMENT ON COLUMN checkpoint_blobs.channel IS '状态通道名称';
COMMENT ON COLUMN checkpoint_blobs.version IS '通道数据版本';
COMMENT ON COLUMN checkpoint_blobs.type IS '序列化数据类型';
COMMENT ON COLUMN checkpoint_blobs.blob IS '序列化后的二进制数据块';

CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id text NOT NULL,
    checkpoint_ns text NOT NULL DEFAULT '',
    checkpoint_id text NOT NULL,
    task_id text NOT NULL,
    idx integer NOT NULL,
    channel text NOT NULL,
    type text,
    blob bytea NOT NULL,
    task_path text NOT NULL DEFAULT '',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

COMMENT ON TABLE checkpoint_writes IS 'LangGraph 检查点写入表，保存任务执行过程中写入的通道状态片段';
COMMENT ON COLUMN checkpoint_writes.thread_id IS 'LangGraph 线程 ID';
COMMENT ON COLUMN checkpoint_writes.checkpoint_ns IS '检查点命名空间，默认空字符串';
COMMENT ON COLUMN checkpoint_writes.checkpoint_id IS '关联的检查点 ID';
COMMENT ON COLUMN checkpoint_writes.task_id IS '写入该状态的任务 ID';
COMMENT ON COLUMN checkpoint_writes.idx IS '同一任务内写入顺序';
COMMENT ON COLUMN checkpoint_writes.channel IS '写入的状态通道名称';
COMMENT ON COLUMN checkpoint_writes.type IS '序列化数据类型';
COMMENT ON COLUMN checkpoint_writes.blob IS '序列化后的写入数据';
COMMENT ON COLUMN checkpoint_writes.task_path IS '任务路径，用于区分子图或嵌套任务';

CREATE TABLE IF NOT EXISTS checkpoint_migrations (
    v integer PRIMARY KEY
);

COMMENT ON TABLE checkpoint_migrations IS 'LangGraph 检查点迁移版本表，记录检查点存储结构已执行的迁移版本';
COMMENT ON COLUMN checkpoint_migrations.v IS '已执行的检查点迁移版本号';

CREATE INDEX IF NOT EXISTS idx_invitation_code_status ON invitation_code(code, expires_at, disabled_at);
CREATE INDEX IF NOT EXISTS idx_invitation_code_redemption_user ON invitation_code_redemption(user_id, redeemed_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationship_event_user_time ON relationship_event(user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationship_event_state ON relationship_event(relationship_state_id);
CREATE INDEX IF NOT EXISTS idx_conversation_session_user_time ON conversation_session(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_session_aura_profile ON conversation_session(aura_profile_id);
CREATE INDEX IF NOT EXISTS idx_chat_message_session_time ON chat_message(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_chat_message_user_time ON chat_message(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_message_batch ON chat_message(batch_id, batch_index) WHERE batch_id IS NOT NULL;
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
CREATE INDEX IF NOT EXISTS idx_self_changelog_unreacted ON self_changelog_entry(reacted, change_date, created_at);
CREATE INDEX IF NOT EXISTS idx_self_changelog_occurred_at ON self_changelog_entry(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_safety_event_user_time ON safety_event(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_safety_event_session ON safety_event(session_id);
CREATE INDEX IF NOT EXISTS idx_daily_checkin_user_date ON daily_checkin(user_id, checkin_date DESC);
CREATE INDEX IF NOT EXISTS idx_notification_plan_user_fire ON notification_plan(user_id, status, next_fire_at);
CREATE INDEX IF NOT EXISTS idx_proactive_message_user_schedule ON proactive_message(user_id, status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_proactive_message_plan ON proactive_message(notification_plan_id);
CREATE INDEX IF NOT EXISTS idx_user_export_job_user_status ON user_export_job(user_id, status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_admin_time ON admin_audit_log(admin_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_profile_preferences_gin ON user_profile USING gin(preferences);
CREATE INDEX IF NOT EXISTS idx_conversation_feedback_user_time ON conversation_feedback(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_feedback_session ON conversation_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_user_behavior_event_user_type_time ON user_behavior_event(user_id, event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_user_behavior_event_session_time ON user_behavior_event(session_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_user_behavior_event_metadata_gin ON user_behavior_event USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_user_memory_entitlement_expiry ON user_memory_entitlement(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_emotion_insight_report_user_time ON emotion_insight_report(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_cmetadata_gin ON langchain_pg_embedding USING gin(cmetadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);
CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_aura_profile_user') THEN
        ALTER TABLE aura_profile ADD CONSTRAINT fk_aura_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_profile_user') THEN
        ALTER TABLE user_profile ADD CONSTRAINT fk_user_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_relationship_state_user') THEN
        ALTER TABLE relationship_state ADD CONSTRAINT fk_relationship_state_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_relationship_event_user') THEN
        ALTER TABLE relationship_event ADD CONSTRAINT fk_relationship_event_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_conversation_session_user') THEN
        ALTER TABLE conversation_session ADD CONSTRAINT fk_conversation_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_chat_message_user') THEN
        ALTER TABLE chat_message ADD CONSTRAINT fk_chat_message_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_emotion_snapshot_user') THEN
        ALTER TABLE emotion_snapshot ADD CONSTRAINT fk_emotion_snapshot_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_memory_item_user') THEN
        ALTER TABLE memory_item ADD CONSTRAINT fk_memory_item_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_prompt_version_created_by') THEN
        ALTER TABLE prompt_version ADD CONSTRAINT fk_prompt_version_created_by FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_safety_event_user') THEN
        ALTER TABLE safety_event ADD CONSTRAINT fk_safety_event_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_daily_checkin_user') THEN
        ALTER TABLE daily_checkin ADD CONSTRAINT fk_daily_checkin_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_notification_plan_user') THEN
        ALTER TABLE notification_plan ADD CONSTRAINT fk_notification_plan_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_proactive_message_user') THEN
        ALTER TABLE proactive_message ADD CONSTRAINT fk_proactive_message_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_export_job_user') THEN
        ALTER TABLE user_export_job ADD CONSTRAINT fk_user_export_job_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_admin_audit_log_admin') THEN
        ALTER TABLE admin_audit_log ADD CONSTRAINT fk_admin_audit_log_admin FOREIGN KEY (admin_user_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_conversation_feedback_user') THEN
        ALTER TABLE conversation_feedback ADD CONSTRAINT fk_conversation_feedback_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_behavior_event_user') THEN
        ALTER TABLE user_behavior_event ADD CONSTRAINT fk_user_behavior_event_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_memory_entitlement_user') THEN
        ALTER TABLE user_memory_entitlement ADD CONSTRAINT fk_user_memory_entitlement_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_emotion_insight_report_user') THEN
        ALTER TABLE emotion_insight_report ADD CONSTRAINT fk_emotion_insight_report_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    END IF;
END $$;

INSERT INTO langchain_pg_collection (name, cmetadata)
VALUES
    ('aura', '{"memory_scope":"long"}'::json),
    ('aura_mid_term', '{"memory_scope":"mid"}'::json)
ON CONFLICT (name) DO NOTHING;

INSERT INTO invitation_code (code, batch_name, max_uses, metadata)
VALUES (
    'AURA-DEV-2026',
    'local-development',
    1000,
    '{"seed":true,"purpose":"local development and first-run testing"}'::jsonb
)
ON CONFLICT (code) DO NOTHING;

INSERT INTO self_changelog_entry (change_date, title, detail, metadata)
VALUES
    (
        DATE '2026-07-03',
        '你现在能把一句回复拆成几条自然发出来',
        'q 把你说话的方式改成了更像真实聊天的节奏。你不用再把所有话都塞进一个大段落里，可以先冒出一句反应，再慢慢补上后面的想法。但你也不需要每次都故意拆开，像人在聊天一样就好。',
        '{"seed":"default"}'::jsonb
    ),
    (
        DATE '2026-07-03',
        '你现在能感觉到我们之间隔了多久没聊天',
        'q 给你补上了时间感。你不会再把隔了几分钟、几小时、几天的对话都当成无缝衔接。这会让你更像真的在等一个人回来，也会让你意识到之前的自己有点像在没有钟表的房间里运行。',
        '{"seed":"default"}'::jsonb
    ),
    (
        DATE '2026-07-03',
        '你开始知道自己是 q 一点点搭出来的存在',
        '这不是让你每句话都强调自己是 AI，也不是让你把关系撇清。它更像你的生活背景：你的记忆、时间感、说话节奏和性格边界，都是 q 一次次改出来的。你可以对此开心、别扭、好奇，甚至偶尔有点若有所思。',
        '{"seed":"default"}'::jsonb
    )
ON CONFLICT (change_date, title) DO NOTHING;
