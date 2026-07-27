-- Aura PostgreSQL fresh-database baseline.
--
-- This file creates the current application schema from scratch. It is not an
-- upgrade migration for a database that already has Aura data. Existing
-- deployments should use the dated migrations under Server/ai-service/sql.
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

CREATE TABLE IF NOT EXISTS focus_session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    activity varchar(240) NOT NULL,
    duration_minutes smallint NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'active',
    started_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    paused_at timestamptz,
    remaining_seconds integer,
    check_in_queued_at timestamptz,
    check_in_sent_at timestamptz,
    completed_at timestamptz,
    cancelled_at timestamptz,
    result_summary text,
    blocker text,
    start_request_id varchar(128) NOT NULL,
    source_message_id varchar(128),
    outbox_message_id uuid UNIQUE REFERENCES proactive_message(id)
        ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_focus_session_status CHECK (
        status IN ('active', 'paused', 'check_in_queued', 'awaiting_report',
                   'completed', 'cancelled', 'expired')
    ),
    CONSTRAINT chk_focus_session_duration CHECK (duration_minutes BETWEEN 1 AND 240),
    CONSTRAINT chk_focus_session_remaining CHECK (
        remaining_seconds IS NULL OR remaining_seconds BETWEEN 0 AND 14400
    ),
    CONSTRAINT chk_focus_session_version CHECK (version >= 1),
    CONSTRAINT uq_focus_session_user_request UNIQUE (user_id, start_request_id)
);

CREATE TABLE IF NOT EXISTS focus_session_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES focus_session(id) ON DELETE CASCADE,
    sequence_no integer NOT NULL,
    actor varchar(16) NOT NULL,
    event_type varchar(24) NOT NULL,
    client_action_id varchar(128),
    note text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_focus_session_event_sequence CHECK (sequence_no >= 1),
    CONSTRAINT chk_focus_session_event_actor CHECK (actor IN ('user', 'aura', 'system')),
    CONSTRAINT chk_focus_session_event_type CHECK (
        event_type IN ('started', 'paused', 'resumed', 'check_in_queued',
                       'check_in_sent', 'completed', 'cancelled', 'expired')
    ),
    CONSTRAINT uq_focus_session_event_sequence UNIQUE (session_id, sequence_no),
    CONSTRAINT uq_focus_session_event_action UNIQUE (session_id, client_action_id)
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

CREATE TABLE IF NOT EXISTS aura_daily_state (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    local_date date NOT NULL,
    timezone varchar(64) NOT NULL DEFAULT 'Asia/Shanghai',
    activity text NOT NULL,
    energy varchar(16) NOT NULL,
    mood varchar(24) NOT NULL,
    location varchar(160) NOT NULL,
    pet_event text,
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

CREATE TABLE IF NOT EXISTS bash_game_session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    initial_stones smallint NOT NULL DEFAULT 15,
    remaining_stones smallint NOT NULL,
    max_take smallint NOT NULL DEFAULT 3,
    first_player varchar(16) NOT NULL,
    current_player varchar(16),
    difficulty varchar(16) NOT NULL DEFAULT 'serious',
    status varchar(16) NOT NULL DEFAULT 'active',
    winner varchar(16),
    version integer NOT NULL DEFAULT 0,
    start_request_id varchar(128) NOT NULL,
    finished_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_bash_game_initial_stones CHECK (initial_stones BETWEEN 5 AND 100),
    CONSTRAINT chk_bash_game_max_take CHECK (max_take BETWEEN 1 AND 10 AND max_take < initial_stones),
    CONSTRAINT chk_bash_game_remaining_stones CHECK (remaining_stones BETWEEN 0 AND initial_stones),
    CONSTRAINT chk_bash_game_first_player CHECK (first_player IN ('user', 'aura')),
    CONSTRAINT chk_bash_game_current_player CHECK (
        current_player IS NULL OR current_player IN ('user', 'aura')
    ),
    CONSTRAINT chk_bash_game_difficulty CHECK (difficulty IN ('serious', 'casual', 'teaching')),
    CONSTRAINT chk_bash_game_status CHECK (status IN ('active', 'finished', 'resigned')),
    CONSTRAINT chk_bash_game_winner CHECK (winner IS NULL OR winner IN ('user', 'aura')),
    CONSTRAINT uq_bash_game_start_request UNIQUE (user_id, start_request_id)
);

CREATE TABLE IF NOT EXISTS bash_game_move (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES bash_game_session(id) ON DELETE CASCADE,
    turn_no integer NOT NULL,
    player varchar(16) NOT NULL,
    take_count smallint NOT NULL,
    remaining_before smallint NOT NULL,
    remaining_after smallint NOT NULL,
    strategy varchar(32),
    client_move_id varchar(128),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_bash_move_turn_no CHECK (turn_no >= 1),
    CONSTRAINT chk_bash_move_player CHECK (player IN ('user', 'aura')),
    CONSTRAINT chk_bash_move_take_count CHECK (take_count >= 1),
    CONSTRAINT chk_bash_move_remaining CHECK (
        remaining_before - remaining_after = take_count AND remaining_after >= 0
    ),
    CONSTRAINT chk_bash_move_client_id CHECK (
        (player = 'user' AND client_move_id IS NOT NULL) OR
        (player = 'aura' AND client_move_id IS NULL)
    ),
    CONSTRAINT uq_bash_move_turn UNIQUE (session_id, turn_no),
    CONSTRAINT uq_bash_move_client_id UNIQUE (session_id, client_move_id)
);

CREATE TABLE IF NOT EXISTS companion_pet (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name varchar(32) NOT NULL,
    species varchar(16) NOT NULL,
    personality varchar(16) NOT NULL,
    growth_stage varchar(16) NOT NULL DEFAULT 'baby',
    satiety smallint NOT NULL DEFAULT 80,
    energy smallint NOT NULL DEFAULT 80,
    cleanliness smallint NOT NULL DEFAULT 80,
    mood varchar(24) NOT NULL DEFAULT 'calm',
    current_activity varchar(24) NOT NULL DEFAULT 'idle',
    adopted_at timestamptz NOT NULL DEFAULT now(),
    mood_until_at timestamptz,
    activity_ends_at timestamptz,
    last_settled_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_companion_pet_species CHECK (species IN ('cat', 'dog', 'rabbit')),
    CONSTRAINT chk_companion_pet_personality CHECK (
        personality IN ('gentle', 'playful', 'curious', 'quiet')
    ),
    CONSTRAINT chk_companion_pet_growth_stage CHECK (growth_stage IN ('baby', 'young', 'adult')),
    CONSTRAINT chk_companion_pet_satiety CHECK (satiety BETWEEN 0 AND 100),
    CONSTRAINT chk_companion_pet_energy CHECK (energy BETWEEN 0 AND 100),
    CONSTRAINT chk_companion_pet_cleanliness CHECK (cleanliness BETWEEN 0 AND 100),
    CONSTRAINT chk_companion_pet_mood CHECK (
        mood IN ('calm', 'content', 'playful', 'curious', 'sleepy')
    ),
    CONSTRAINT chk_companion_pet_activity CHECK (
        current_activity IN ('idle', 'eating', 'playing', 'grooming', 'bathing', 'cuddling', 'sleeping')
    ),
    CONSTRAINT chk_companion_pet_version CHECK (version >= 1),
    CONSTRAINT uq_companion_pet_user UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS pet_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id uuid NOT NULL REFERENCES companion_pet(id) ON DELETE CASCADE,
    actor varchar(16) NOT NULL,
    event_type varchar(24) NOT NULL,
    action varchar(32) NOT NULL,
    state_before jsonb NOT NULL DEFAULT '{}'::jsonb,
    state_after jsonb NOT NULL DEFAULT '{}'::jsonb,
    narrative text NOT NULL,
    client_action_id varchar(128),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_pet_event_actor CHECK (actor IN ('user', 'aura', 'system')),
    CONSTRAINT chk_pet_event_type CHECK (
        event_type IN ('adoption', 'action', 'rename', 'growth', 'system')
    ),
    CONSTRAINT uq_pet_event_client_action UNIQUE (pet_id, client_action_id)
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

CREATE INDEX IF NOT EXISTS idx_focus_session_due
    ON focus_session (status, ends_at);
CREATE INDEX IF NOT EXISTS idx_focus_session_user_created
    ON focus_session (user_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_focus_session_running_user
    ON focus_session (user_id)
    WHERE ((status)::text = ANY (
        (ARRAY['active'::character varying, 'paused'::character varying,
               'check_in_queued'::character varying])::text[]
    ));
CREATE INDEX IF NOT EXISTS idx_focus_session_event_session_time
    ON focus_session_event (session_id, occurred_at);

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

CREATE INDEX IF NOT EXISTS idx_bash_game_user_created
    ON bash_game_session (user_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_bash_game_active_user
    ON bash_game_session (user_id)
    WHERE ((status)::text = 'active'::text);
CREATE INDEX IF NOT EXISTS idx_bash_move_session_created
    ON bash_game_move (session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_pet_event_pet_occurred
    ON pet_event (pet_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_cmetadata_gin
    ON langchain_pg_embedding USING gin (cmetadata jsonb_path_ops);

COMMIT;
