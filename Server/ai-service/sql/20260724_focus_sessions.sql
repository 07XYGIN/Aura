BEGIN;

-- Adds the focus tables introduced by the together-focus workflow. This is
-- safe to run after the 20260722 baseline and the 20260723 migrations.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

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

COMMIT;
