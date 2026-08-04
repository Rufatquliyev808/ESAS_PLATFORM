CREATE TABLE replay_sessions
(
    session_id                 TEXT PRIMARY KEY,
    created_by                 TEXT NOT NULL,
    symbol                     TEXT NOT NULL,
    start_at                   TEXT NOT NULL,
    end_at                     TEXT NOT NULL,
    mode                       TEXT NOT NULL
                               CHECK (mode IN ('step', 'max_speed')),
    state                      TEXT NOT NULL
                               CHECK (state IN (
                                   'created',
                                   'running',
                                   'paused',
                                   'interrupted',
                                   'completed',
                                   'cancelled',
                                   'failed'
                               )),
    replay_contract_version    TEXT NOT NULL,
    quality_rule_version       TEXT NOT NULL,
    dataset_tick_count         INTEGER NOT NULL
                               CHECK (dataset_tick_count >= 0),
    dataset_fingerprint        TEXT NOT NULL,
    first_event_timestamp      TEXT,
    first_event_id             TEXT,
    last_event_timestamp       TEXT,
    last_event_id              TEXT,
    processed_ticks            INTEGER NOT NULL DEFAULT 0
                               CHECK (
                                   processed_ticks >= 0
                                   AND processed_ticks <= dataset_tick_count
                               ),
    checkpoint_event_timestamp TEXT,
    checkpoint_event_id        TEXT,
    last_batch_at              TEXT,
    error_category             TEXT,
    created_at                 TEXT NOT NULL,
    updated_at                 TEXT NOT NULL,
    completed_at               TEXT,
    CHECK (end_at > start_at)
);

CREATE INDEX idx_replay_sessions_list
ON replay_sessions(created_at DESC, session_id DESC);

CREATE INDEX idx_replay_sessions_state
ON replay_sessions(state, updated_at);

CREATE INDEX idx_replay_sessions_owner
ON replay_sessions(created_by, created_at DESC, session_id DESC);

CREATE TABLE replay_session_audit
(
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL,
    actor             TEXT NOT NULL,
    actor_role        TEXT NOT NULL,
    action            TEXT NOT NULL,
    previous_state    TEXT,
    next_state        TEXT NOT NULL,
    processed_ticks   INTEGER NOT NULL CHECK (processed_ticks >= 0),
    checkpoint_time   TEXT,
    checkpoint_event  TEXT,
    error_category    TEXT,
    occurred_at       TEXT NOT NULL,
    FOREIGN KEY (session_id)
        REFERENCES replay_sessions(session_id)
        ON DELETE RESTRICT
);

CREATE TRIGGER prevent_replay_audit_update
BEFORE UPDATE ON replay_session_audit
BEGIN
    SELECT RAISE(ABORT, 'replay audit is append-only');
END;

CREATE TRIGGER prevent_replay_audit_delete
BEFORE DELETE ON replay_session_audit
BEGIN
    SELECT RAISE(ABORT, 'replay audit is append-only');
END;

CREATE INDEX idx_replay_audit_session
ON replay_session_audit(session_id, audit_id);
