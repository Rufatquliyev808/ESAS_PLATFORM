ALTER TABLE replay_sessions
ADD COLUMN state_version INTEGER NOT NULL DEFAULT 0
CHECK (state_version >= 0);

CREATE TABLE replay_commands
(
    command_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    idempotency_key_hash TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    actor TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    command TEXT NOT NULL,
    expected_state_version INTEGER NOT NULL,
    resulting_state_version INTEGER NOT NULL,
    resulting_state TEXT NOT NULL,
    resulting_processed_ticks INTEGER NOT NULL,
    resulting_checkpoint_time TEXT,
    resulting_checkpoint_event TEXT,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES replay_sessions(session_id),
    UNIQUE (session_id, actor, idempotency_key_hash)
);

CREATE TRIGGER replay_commands_no_update
BEFORE UPDATE ON replay_commands
BEGIN
    SELECT RAISE(ABORT, 'replay_commands is append-only');
END;

CREATE TRIGGER replay_commands_no_delete
BEFORE DELETE ON replay_commands
BEGIN
    SELECT RAISE(ABORT, 'replay_commands is append-only');
END;
