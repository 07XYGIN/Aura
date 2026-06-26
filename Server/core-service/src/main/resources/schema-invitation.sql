CREATE EXTENSION IF NOT EXISTS pgcrypto;

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

CREATE TABLE IF NOT EXISTS invitation_code_redemption (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invite_code_id uuid NOT NULL REFERENCES invitation_code(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    redeemed_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (invite_code_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_invitation_code_status
    ON invitation_code(code, expires_at, disabled_at);

CREATE INDEX IF NOT EXISTS idx_invitation_code_redemption_user
    ON invitation_code_redemption(user_id, redeemed_at DESC);

INSERT INTO invitation_code (code, batch_name, max_uses, metadata)
VALUES (
    'AURA-DEV-2026',
    'local-development',
    1000,
    '{"seed":true,"purpose":"local development and first-run testing"}'::jsonb
)
ON CONFLICT (code) DO NOTHING;
