CREATE TABLE replay_step_commands
(
    command_id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id                   TEXT NOT NULL,
    idempotency_key              TEXT NOT NULL,
    actor                        TEXT NOT NULL,
    actor_role                   TEXT NOT NULL,
    requested_ticks              INTEGER NOT NULL
                                 CHECK (requested_ticks BETWEEN 1 AND 1000),
    previous_processed_ticks     INTEGER NOT NULL
                                 CHECK (previous_processed_ticks >= 0),
    previous_checkpoint_time     TEXT,
    previous_checkpoint_event    TEXT,
    batch_tick_count             INTEGER NOT NULL
                                 CHECK (batch_tick_count BETWEEN 1 AND 1000),
    resulting_processed_ticks    INTEGER NOT NULL
                                 CHECK (resulting_processed_ticks >= batch_tick_count),
    resulting_checkpoint_time    TEXT NOT NULL,
    resulting_checkpoint_event   TEXT NOT NULL,
    resulting_state              TEXT NOT NULL
                                 CHECK (resulting_state IN ('running', 'completed')),
    occurred_at                  TEXT NOT NULL,
    FOREIGN KEY (session_id)
        REFERENCES replay_sessions(session_id)
        ON DELETE RESTRICT,
    CHECK (
        resulting_processed_ticks
        = previous_processed_ticks + batch_tick_count
    ),
    CHECK (
        (
            previous_processed_ticks = 0
            AND previous_checkpoint_time IS NULL
            AND previous_checkpoint_event IS NULL
        )
        OR
        (
            previous_processed_ticks > 0
            AND previous_checkpoint_time IS NOT NULL
            AND previous_checkpoint_event IS NOT NULL
        )
    ),
    UNIQUE (session_id, idempotency_key)
);

CREATE INDEX idx_replay_step_commands_session
ON replay_step_commands(session_id, command_id);

CREATE TRIGGER prevent_replay_step_command_update
BEFORE UPDATE ON replay_step_commands
BEGIN
    SELECT RAISE(ABORT, 'replay step command is append-only');
END;

CREATE TRIGGER prevent_replay_step_command_delete
BEFORE DELETE ON replay_step_commands
BEGIN
    SELECT RAISE(ABORT, 'replay step command is append-only');
END;
