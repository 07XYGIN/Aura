-- Aura PostgreSQL canonical fresh-database baseline.
--
-- This is the only SQL file in the repository. It creates the complete current
-- business schema from scratch; existing deployments use Alembic revisions.
-- LangGraph checkpoint_* tables are created by PostgresSaver.setup() at app
-- startup and are intentionally not duplicated here.

BEGIN;

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

CREATE TABLE IF NOT EXISTS proactive_message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trigger_type varchar(64) NOT NULL,
    title varchar(128),
    content text NOT NULL,
    scheduled_at timestamptz NOT NULL,
    sent_at timestamptz,
    dedupe_key varchar(160),
    delivery_message_id varchar(128) NOT NULL DEFAULT (gen_random_uuid())::text,
    attempt_count integer NOT NULL DEFAULT 0,
    claimed_until timestamptz,
    last_error text,
    cancelled_at timestamptz,
    status varchar(32) NOT NULL DEFAULT 'pending',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_proactive_message_status CHECK (
        status IN ('pending', 'processing', 'sent', 'skipped', 'failed', 'cancelled')
    ),
    CONSTRAINT uq_proactive_message_user_dedupe UNIQUE (user_id, dedupe_key)
);

CREATE TABLE IF NOT EXISTS conditional_message_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type varchar(24) NOT NULL,
    event_id varchar(128) NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    matched_count integer NOT NULL DEFAULT 0,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_conditional_message_event_type CHECK (
        event_type IN ('keyword', 'project_status', 'github_event', 'passphrase')
    ),
    CONSTRAINT chk_conditional_message_event_matched_count CHECK (matched_count >= 0),
    CONSTRAINT uq_conditional_message_event_user_event UNIQUE (user_id, event_type, event_id)
);

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
    CONSTRAINT chk_conditional_message_type CHECK (
        message_type IN ('time_capsule', 'secret_vault')
    ),
    CONSTRAINT chk_conditional_message_condition_type CHECK (
        condition_type IN ('time', 'keyword', 'project_status', 'github_event', 'passphrase')
    ),
    CONSTRAINT chk_conditional_message_status CHECK (
        status IN ('sealed', 'queued', 'delivered', 'cancelled', 'expired', 'failed')
    ),
    CONSTRAINT chk_conditional_message_time_requires_delivery CHECK (
        condition_type <> 'time' OR deliver_at IS NOT NULL
    ),
    CONSTRAINT chk_conditional_message_version CHECK (version >= 1),
    CONSTRAINT uq_conditional_message_user_dedupe UNIQUE (user_id, dedupe_key)
);

CREATE TABLE IF NOT EXISTS relationship_thread (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
    CONSTRAINT chk_relationship_thread_type CHECK (
        thread_type IN ('open_item', 'follow_up', 'conflict', 'promise', 'project_task')
    ),
    CONSTRAINT chk_relationship_thread_perspective CHECK (
        perspective IN ('user', 'aura', 'shared')
    ),
    CONSTRAINT chk_relationship_thread_world_layer CHECK (
        world_layer IN ('reality', 'shared_history', 'imagined', 'wish', 'promise')
    ),
    CONSTRAINT chk_relationship_thread_status CHECK (
        status IN ('pending', 'followed_up', 'resolved', 'abandoned')
    ),
    CONSTRAINT chk_relationship_thread_version CHECK (version >= 1),
    CONSTRAINT uq_relationship_thread_user_source UNIQUE (user_id, source_key)
);

CREATE TABLE IF NOT EXISTS relationship_thread_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid NOT NULL REFERENCES relationship_thread(id) ON DELETE CASCADE,
    sequence_no integer NOT NULL,
    actor varchar(16) NOT NULL,
    event_type varchar(24) NOT NULL,
    state_before jsonb NOT NULL DEFAULT '{}'::jsonb,
    state_after jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_message_id varchar(128),
    client_action_id varchar(128),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_relationship_thread_event_sequence CHECK (sequence_no >= 1),
    CONSTRAINT chk_relationship_thread_event_actor CHECK (actor IN ('user', 'aura', 'system')),
    CONSTRAINT chk_relationship_thread_event_type CHECK (
        event_type IN ('created', 'updated', 'followed_up', 'resolved', 'abandoned')
    ),
    CONSTRAINT uq_relationship_thread_event_sequence UNIQUE (thread_id, sequence_no),
    CONSTRAINT uq_relationship_thread_event_client_action UNIQUE (thread_id, client_action_id)
);

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
    CONSTRAINT chk_relationship_item_perspective CHECK (
        perspective IN ('user', 'aura', 'shared')
    ),
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

CREATE TABLE IF NOT EXISTS aura_internal_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mood varchar(24) NOT NULL DEFAULT 'calm',
    attachment_tone varchar(24) NOT NULL DEFAULT 'steady',
    missing_user varchar(16) NOT NULL DEFAULT 'none',
    desire_for_contact varchar(16) NOT NULL DEFAULT 'low',
    playfulness varchar(16) NOT NULL DEFAULT 'low',
    jealousy varchar(16) NOT NULL DEFAULT 'none',
    vulnerability varchar(16) NOT NULL DEFAULT 'low',
    unresolved_feeling text,
    current_desire varchar(64) NOT NULL DEFAULT 'none',
    last_meaningful_interaction text,
    last_user_seen_at timestamptz,
    last_proactive_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_aura_internal_state_mood CHECK (
        mood IN ('calm', 'warm', 'playful', 'concerned', 'unsettled', 'tired')
    ),
    CONSTRAINT chk_aura_internal_state_attachment_tone CHECK (
        attachment_tone IN ('guarded', 'steady', 'close', 'tender')
    ),
    CONSTRAINT chk_aura_internal_state_missing_user CHECK (
        missing_user IN ('none', 'slight', 'clear')
    ),
    CONSTRAINT chk_aura_internal_state_desire_for_contact CHECK (
        desire_for_contact IN ('none', 'low', 'medium', 'high')
    ),
    CONSTRAINT chk_aura_internal_state_playfulness CHECK (
        playfulness IN ('none', 'low', 'medium', 'high')
    ),
    CONSTRAINT chk_aura_internal_state_jealousy CHECK (jealousy IN ('none', 'low', 'medium', 'high')),
    CONSTRAINT chk_aura_internal_state_vulnerability CHECK (
        vulnerability IN ('low', 'medium', 'high')
    ),
    CONSTRAINT chk_aura_internal_state_version CHECK (version >= 1),
    CONSTRAINT uq_aura_internal_state_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS relationship_dynamics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    relationship_stage varchar(32) NOT NULL DEFAULT 'ambiguous',
    relationship_phase varchar(16) NOT NULL DEFAULT 'normal',
    relationship_tone varchar(24) NOT NULL DEFAULT 'warm',
    recent_closeness varchar(16) NOT NULL DEFAULT 'medium',
    unresolved_tension text,
    recent_positive_moment text,
    recent_distance text,
    current_expectation text,
    last_stage_change_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_relationship_dynamics_stage CHECK (
        relationship_stage IN ('early_closeness', 'ambiguous', 'early_romance',
                               'established_romance')
    ),
    CONSTRAINT chk_relationship_dynamics_phase CHECK (
        relationship_phase IN ('normal', 'distant', 'conflict', 'repair')
    ),
    CONSTRAINT chk_relationship_dynamics_tone CHECK (
        relationship_tone IN ('steady', 'warm', 'playful', 'tender', 'guarded')
    ),
    CONSTRAINT chk_relationship_dynamics_closeness CHECK (
        recent_closeness IN ('low', 'medium', 'high')
    ),
    CONSTRAINT chk_relationship_dynamics_version CHECK (version >= 1),
    CONSTRAINT uq_relationship_dynamics_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS relationship_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type varchar(40) NOT NULL,
    actor varchar(16) NOT NULL,
    target varchar(16) NOT NULL,
    importance varchar(16) NOT NULL DEFAULT 'medium',
    summary text,
    source_turn_id varchar(128) NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_relationship_event_type CHECK (
        event_type IN ('affection_expressed', 'aura_expressed_missing',
                       'important_disclosure', 'conflict_started', 'boundary_crossed',
                       'apology', 'repair_completed', 'promise_created', 'promise_fulfilled',
                       'shared_moment', 'relationship_milestone', 'distance_period',
                       'return_after_absence')
    ),
    CONSTRAINT chk_relationship_event_actor CHECK (actor IN ('user', 'aura', 'system')),
    CONSTRAINT chk_relationship_event_target CHECK (target IN ('user', 'aura', 'relationship')),
    CONSTRAINT chk_relationship_event_importance CHECK (importance IN ('low', 'medium', 'high')),
    CONSTRAINT uq_relationship_event_turn_type UNIQUE (user_id, source_turn_id, event_type)
);

CREATE TABLE IF NOT EXISTS affect_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind varchar(24) NOT NULL,
    intensity varchar(16) NOT NULL,
    started_at timestamptz NOT NULL,
    last_reinforced_at timestamptz NOT NULL,
    decay_after timestamptz NOT NULL,
    source_event_id uuid REFERENCES relationship_event(id) ON DELETE SET NULL,
    resolved boolean NOT NULL DEFAULT false,
    resolved_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_affect_state_kind CHECK (kind IN ('jealousy', 'hurt', 'longing', 'unsettled')),
    CONSTRAINT chk_affect_state_intensity CHECK (intensity IN ('low', 'medium', 'high')),
    CONSTRAINT chk_affect_state_version CHECK (version >= 1),
    CONSTRAINT uq_affect_state_user_kind UNIQUE (user_id, kind)
);

CREATE TABLE IF NOT EXISTS aura_daily_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    local_date date NOT NULL,
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
    activity text NOT NULL,
    energy varchar(16) NOT NULL,
    mood varchar(24) NOT NULL,
    location varchar(160) NOT NULL,
    current_content text,
    daily_event text,
    generated_by varchar(16) NOT NULL DEFAULT 'deterministic',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_aura_daily_state_energy CHECK (energy IN ('rested', 'steady', 'low')),
    CONSTRAINT chk_aura_daily_state_mood CHECK (
        mood IN ('calm', 'focused', 'playful', 'annoyed', 'tired', 'cozy')
    ),
    CONSTRAINT chk_aura_daily_state_generated_by CHECK (
        generated_by IN ('deterministic', 'model', 'user')
    ),
    CONSTRAINT uq_aura_daily_state_user_date UNIQUE (user_id, local_date)
);

CREATE TABLE IF NOT EXISTS emotional_afterglow (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    emotion varchar(24) NOT NULL,
    interaction_mode varchar(16) NOT NULL,
    intensity numeric(4, 3) NOT NULL,
    source_message_id varchar(128) NOT NULL,
    observed_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_emotional_afterglow_emotion CHECK (
        emotion IN ('happy', 'distressed', 'stressed', 'angry', 'lonely', 'tired',
                    'affectionate', 'unsettled')
    ),
    CONSTRAINT chk_emotional_afterglow_interaction_mode CHECK (
        interaction_mode IN ('natural', 'affection', 'repair')
    ),
    CONSTRAINT chk_emotional_afterglow_intensity CHECK (intensity BETWEEN 0 AND 1),
    CONSTRAINT chk_emotional_afterglow_version CHECK (version >= 1),
    CONSTRAINT uq_emotional_afterglow_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS shared_scene (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scene_type varchar(16) NOT NULL,
    world_layer varchar(24) NOT NULL DEFAULT 'imagined',
    place varchar(160) NOT NULL,
    participants jsonb NOT NULL DEFAULT '[]'::jsonb,
    objects jsonb NOT NULL DEFAULT '[]'::jsonb,
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    status varchar(16) NOT NULL DEFAULT 'active',
    source_key varchar(160) NOT NULL,
    source_message_id varchar(128) NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    closed_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_shared_scene_type CHECK (scene_type IN ('room', 'date', 'imagined')),
    CONSTRAINT chk_shared_scene_world_layer CHECK (world_layer IN ('imagined', 'wish')),
    CONSTRAINT chk_shared_scene_status CHECK (status IN ('active', 'closed')),
    CONSTRAINT chk_shared_scene_version CHECK (version >= 1),
    CONSTRAINT uq_shared_scene_user_source UNIQUE (user_id, source_key)
);

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

CREATE TABLE IF NOT EXISTS langchain_pg_collection (
    uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar NOT NULL UNIQUE,
    cmetadata json
);

CREATE TABLE IF NOT EXISTS langchain_pg_embedding (
    id varchar PRIMARY KEY,
    collection_id uuid REFERENCES langchain_pg_collection(uuid) ON DELETE CASCADE,
    embedding vector,
    document varchar,
    cmetadata jsonb
);

CREATE INDEX IF NOT EXISTS idx_self_changelog_occurred_at
    ON self_changelog_entry (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_self_changelog_unreacted
    ON self_changelog_entry (reacted, change_date, created_at);

CREATE INDEX IF NOT EXISTS idx_proactive_message_claim
    ON proactive_message (status, scheduled_at, claimed_until);
CREATE INDEX IF NOT EXISTS idx_proactive_message_user_schedule
    ON proactive_message (user_id, status, scheduled_at);

CREATE INDEX IF NOT EXISTS idx_conditional_message_event_user_time
    ON conditional_message_event (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_conditional_message_time_due
    ON conditional_message (status, deliver_at)
    WHERE ((condition_type)::text = 'time'::text);
CREATE INDEX IF NOT EXISTS idx_conditional_message_user_status
    ON conditional_message (user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_relationship_thread_user_status_follow_up
    ON relationship_thread (user_id, status, follow_up_at);
CREATE INDEX IF NOT EXISTS idx_relationship_thread_event_thread_occurred
    ON relationship_thread_event (thread_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationship_item_user_type_status
    ON relationship_item (user_id, item_type, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationship_chapter_user_sequence
    ON relationship_chapter (user_id, sequence_no DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_relationship_chapter_current_user
    ON relationship_chapter (user_id)
    WHERE ((status)::text = 'current'::text);
CREATE INDEX IF NOT EXISTS idx_aura_internal_state_last_seen
    ON aura_internal_state (last_user_seen_at);
CREATE INDEX IF NOT EXISTS idx_relationship_dynamics_stage
    ON relationship_dynamics (relationship_stage, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationship_event_user_occurred
    ON relationship_event (user_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_affect_state_user_decay
    ON affect_state (user_id, resolved, decay_after);

CREATE INDEX IF NOT EXISTS idx_aura_daily_state_user_date
    ON aura_daily_state (user_id, local_date DESC);
CREATE INDEX IF NOT EXISTS idx_emotional_afterglow_user_expires
    ON emotional_afterglow (user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_shared_scene_user_started
    ON shared_scene (user_id, started_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_shared_scene_active_user
    ON shared_scene (user_id)
    WHERE ((status)::text = 'active'::text);
CREATE INDEX IF NOT EXISTS idx_aura_thought_seed_status_eligible
    ON aura_thought_seed (status, eligible_at, expires_at);
CREATE INDEX IF NOT EXISTS idx_aura_thought_seed_user_created
    ON aura_thought_seed (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_aura_sleep_cycle_user_date
    ON aura_sleep_cycle (user_id, local_date DESC);

CREATE INDEX IF NOT EXISTS ix_cmetadata_gin
    ON langchain_pg_embedding USING gin (cmetadata jsonb_path_ops);

COMMIT;
