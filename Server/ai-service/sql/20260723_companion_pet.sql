BEGIN;

-- 共同宠物不使用亲密度和惩罚性生存机制。companion_pet 保存当前状态，
-- pet_event 保存领养、照顾、改名和成长等不可变事实。

CREATE TABLE IF NOT EXISTS companion_pet (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
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
    CONSTRAINT fk_companion_pet_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_companion_pet_user UNIQUE (user_id),
    CONSTRAINT chk_companion_pet_species CHECK (species IN ('cat', 'dog', 'rabbit')),
    CONSTRAINT chk_companion_pet_personality
        CHECK (personality IN ('gentle', 'playful', 'curious', 'quiet')),
    CONSTRAINT chk_companion_pet_growth_stage
        CHECK (growth_stage IN ('baby', 'young', 'adult')),
    CONSTRAINT chk_companion_pet_satiety CHECK (satiety BETWEEN 0 AND 100),
    CONSTRAINT chk_companion_pet_energy CHECK (energy BETWEEN 0 AND 100),
    CONSTRAINT chk_companion_pet_cleanliness CHECK (cleanliness BETWEEN 0 AND 100),
    CONSTRAINT chk_companion_pet_mood
        CHECK (mood IN ('calm', 'content', 'playful', 'curious', 'sleepy')),
    CONSTRAINT chk_companion_pet_activity
        CHECK (current_activity IN ('idle', 'eating', 'playing', 'grooming', 'bathing', 'cuddling', 'sleeping')),
    CONSTRAINT chk_companion_pet_version CHECK (version >= 1)
);

CREATE TABLE IF NOT EXISTS pet_event (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pet_id uuid NOT NULL,
    actor varchar(16) NOT NULL,
    event_type varchar(24) NOT NULL,
    action varchar(32) NOT NULL,
    state_before jsonb NOT NULL DEFAULT '{}'::jsonb,
    state_after jsonb NOT NULL DEFAULT '{}'::jsonb,
    narrative text NOT NULL,
    client_action_id varchar(128),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_pet_event_pet
        FOREIGN KEY (pet_id) REFERENCES companion_pet(id) ON DELETE CASCADE,
    CONSTRAINT chk_pet_event_actor CHECK (actor IN ('user', 'aura', 'system')),
    CONSTRAINT chk_pet_event_type
        CHECK (event_type IN ('adoption', 'action', 'rename', 'growth', 'system')),
    CONSTRAINT uq_pet_event_client_action UNIQUE (pet_id, client_action_id)
);

CREATE INDEX IF NOT EXISTS idx_pet_event_pet_occurred
    ON pet_event (pet_id, occurred_at DESC);

COMMIT;
