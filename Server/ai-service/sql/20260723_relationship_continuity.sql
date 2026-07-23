BEGIN;

-- 关系连续性采用“当前状态 + 不可变事件”双表结构。
-- relationship_thread 只保存跨对话事项的当前权威状态，便于聊天上下文和调度器快速查询；
-- relationship_thread_event 保存每次变更，支持审计、幂等重试与未来重放。
-- 该结构不设置亲密度分数，并通过 world_layer 明确隔离现实、共同经历与想象内容。

CREATE TABLE IF NOT EXISTS relationship_thread (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    thread_type varchar(32) NOT NULL,
    perspective varchar(16) NOT NULL,
    world_layer varchar(24) NOT NULL,
    title varchar(160) NOT NULL,
    summary text NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'pending',
    source_key varchar(160) NOT NULL,
    source_message_id varchar(128),
    source_turn_id varchar(128),
    follow_up_at timestamptz,
    last_followed_up_at timestamptz,
    resolved_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_relationship_thread_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_relationship_thread_type
        CHECK (thread_type IN ('open_item', 'follow_up', 'conflict', 'promise', 'project_task')),
    CONSTRAINT chk_relationship_thread_perspective
        CHECK (perspective IN ('user', 'aura', 'shared')),
    CONSTRAINT chk_relationship_thread_world_layer
        CHECK (world_layer IN ('reality', 'shared_history', 'imagined', 'wish', 'promise')),
    CONSTRAINT chk_relationship_thread_status
        CHECK (status IN ('pending', 'followed_up', 'resolved', 'abandoned')),
    CONSTRAINT chk_relationship_thread_version CHECK (version >= 1),
    CONSTRAINT uq_relationship_thread_user_source UNIQUE (user_id, source_key)
);

COMMENT ON TABLE relationship_thread IS
    '跨对话关系线程的当前状态，包括未完成事项、后续关心、冲突、承诺和共同项目任务';
COMMENT ON COLUMN relationship_thread.thread_type IS
    '线程用途：开放事项、后续关心、冲突修复、承诺或项目任务';
COMMENT ON COLUMN relationship_thread.perspective IS
    '事实视角：用户、Aura 或双方共同经历';
COMMENT ON COLUMN relationship_thread.world_layer IS
    '事实层级：现实、共同历史、共同想象、愿望或承诺，禁止跨层误记';
COMMENT ON COLUMN relationship_thread.source_key IS
    '来源稳定幂等键；同一用户重复处理同一来源时不得创建第二条线程';
COMMENT ON COLUMN relationship_thread.version IS
    '乐观并发版本，每次改变当前状态时必须递增';

CREATE INDEX IF NOT EXISTS idx_relationship_thread_user_status_follow_up
    ON relationship_thread (user_id, status, follow_up_at ASC);

CREATE TABLE IF NOT EXISTS relationship_thread_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid NOT NULL,
    sequence_no integer NOT NULL,
    actor varchar(16) NOT NULL,
    event_type varchar(24) NOT NULL,
    state_before jsonb NOT NULL DEFAULT '{}'::jsonb,
    state_after jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_message_id varchar(128),
    client_action_id varchar(128),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_relationship_thread_event_thread
        FOREIGN KEY (thread_id) REFERENCES relationship_thread(id) ON DELETE CASCADE,
    CONSTRAINT chk_relationship_thread_event_sequence CHECK (sequence_no >= 1),
    CONSTRAINT chk_relationship_thread_event_actor
        CHECK (actor IN ('user', 'aura', 'system')),
    CONSTRAINT chk_relationship_thread_event_type
        CHECK (event_type IN ('created', 'updated', 'followed_up', 'resolved', 'abandoned')),
    CONSTRAINT uq_relationship_thread_event_sequence UNIQUE (thread_id, sequence_no),
    CONSTRAINT uq_relationship_thread_event_client_action UNIQUE (thread_id, client_action_id)
);

COMMENT ON TABLE relationship_thread_event IS
    '关系线程的不可变状态事件；按 sequence_no 重放可还原线程生命周期';
COMMENT ON COLUMN relationship_thread_event.sequence_no IS
    '单条线程内从 1 开始严格递增的事件序号';
COMMENT ON COLUMN relationship_thread_event.state_before IS
    '本次变更发生前的业务状态快照；created 事件可使用空对象';
COMMENT ON COLUMN relationship_thread_event.state_after IS
    '本次变更完成后的业务状态快照';
COMMENT ON COLUMN relationship_thread_event.client_action_id IS
    '客户端写操作的稳定幂等键；空值表示后台系统事件';

CREATE INDEX IF NOT EXISTS idx_relationship_thread_event_thread_occurred
    ON relationship_thread_event (thread_id, occurred_at DESC);

COMMIT;
