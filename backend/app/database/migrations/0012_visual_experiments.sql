CREATE TABLE visual_experiments
(
    experiment_id             TEXT PRIMARY KEY,
    created_by                TEXT NOT NULL,
    replay_session_id         TEXT NOT NULL,
    symbol                    TEXT NOT NULL,
    timeframe                 TEXT NOT NULL,
    source_bar_fingerprint    TEXT NOT NULL,
    render_spec_id            TEXT NOT NULL,
    render_spec_json          TEXT NOT NULL,
    label_spec_id             TEXT NOT NULL,
    label_spec_json           TEXT NOT NULL,
    observation_window_bars   INTEGER NOT NULL
                               CHECK (observation_window_bars > 0),
    train_end_at              TEXT NOT NULL,
    validation_end_at         TEXT NOT NULL,
    lifecycle_state            TEXT NOT NULL
                                CHECK (lifecycle_state IN (
                                    'registered',
                                    'rendering',
                                    'training',
                                    'evaluated',
                                    'accepted_for_shadow',
                                    'rejected',
                                    'archived',
                                    'blocked_by_data_quality',
                                    'invalid_leakage',
                                    'non_reproducible',
                                    'out_of_distribution',
                                    'insufficient_evidence',
                                    'failed',
                                    'cancelled'
                                )),
    state_version               INTEGER NOT NULL DEFAULT 0
                                 CHECK (state_version >= 0),
    created_at                  TEXT NOT NULL,
    updated_at                  TEXT NOT NULL,
    FOREIGN KEY (replay_session_id)
        REFERENCES replay_sessions(session_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_visual_experiments_owner
ON visual_experiments(created_by, created_at DESC, experiment_id DESC);

CREATE INDEX idx_visual_experiments_session
ON visual_experiments(replay_session_id);

CREATE TABLE visual_experiment_audit
(
    audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id  TEXT NOT NULL,
    actor          TEXT NOT NULL,
    actor_role     TEXT NOT NULL,
    action         TEXT NOT NULL,
    previous_state TEXT,
    next_state     TEXT NOT NULL,
    occurred_at    TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);

CREATE TRIGGER prevent_visual_experiment_audit_update
BEFORE UPDATE ON visual_experiment_audit
BEGIN
    SELECT RAISE(ABORT, 'visual experiment audit is append-only');
END;

CREATE TRIGGER prevent_visual_experiment_audit_delete
BEFORE DELETE ON visual_experiment_audit
BEGIN
    SELECT RAISE(ABORT, 'visual experiment audit is append-only');
END;

CREATE INDEX idx_visual_experiment_audit_experiment
ON visual_experiment_audit(experiment_id, audit_id);
