BEGIN;

-- 巴什博弈由确定性 Python 规则驱动。会话表保存当前权威状态，行动表保存
-- 不可变事件；同一用户最多只能有一局 active 游戏。

CREATE TABLE IF NOT EXISTS bash_game_session (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
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
    CONSTRAINT fk_bash_game_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_bash_game_initial_stones
        CHECK (initial_stones BETWEEN 5 AND 100),
    CONSTRAINT chk_bash_game_max_take
        CHECK (max_take BETWEEN 1 AND 10 AND max_take < initial_stones),
    CONSTRAINT chk_bash_game_remaining_stones
        CHECK (remaining_stones BETWEEN 0 AND initial_stones),
    CONSTRAINT chk_bash_game_first_player
        CHECK (first_player IN ('user', 'aura')),
    CONSTRAINT chk_bash_game_current_player
        CHECK (current_player IS NULL OR current_player IN ('user', 'aura')),
    CONSTRAINT chk_bash_game_difficulty
        CHECK (difficulty IN ('serious', 'casual', 'teaching')),
    CONSTRAINT chk_bash_game_status
        CHECK (status IN ('active', 'finished', 'resigned')),
    CONSTRAINT chk_bash_game_winner
        CHECK (winner IS NULL OR winner IN ('user', 'aura')),
    CONSTRAINT uq_bash_game_start_request UNIQUE (user_id, start_request_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bash_game_active_user
    ON bash_game_session (user_id)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_bash_game_user_created
    ON bash_game_session (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS bash_game_move (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL,
    turn_no integer NOT NULL,
    player varchar(16) NOT NULL,
    take_count smallint NOT NULL,
    remaining_before smallint NOT NULL,
    remaining_after smallint NOT NULL,
    strategy varchar(32),
    client_move_id varchar(128),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_bash_move_session
        FOREIGN KEY (session_id) REFERENCES bash_game_session(id) ON DELETE CASCADE,
    CONSTRAINT chk_bash_move_turn_no CHECK (turn_no >= 1),
    CONSTRAINT chk_bash_move_player CHECK (player IN ('user', 'aura')),
    CONSTRAINT chk_bash_move_take_count CHECK (take_count >= 1),
    CONSTRAINT chk_bash_move_remaining
        CHECK (remaining_before - remaining_after = take_count AND remaining_after >= 0),
    CONSTRAINT chk_bash_move_client_id
        CHECK (
            (player = 'user' AND client_move_id IS NOT NULL)
            OR (player = 'aura' AND client_move_id IS NULL)
        ),
    CONSTRAINT uq_bash_move_turn UNIQUE (session_id, turn_no),
    CONSTRAINT uq_bash_move_client_id UNIQUE (session_id, client_move_id)
);

CREATE INDEX IF NOT EXISTS idx_bash_move_session_created
    ON bash_game_move (session_id, created_at ASC);

COMMIT;
