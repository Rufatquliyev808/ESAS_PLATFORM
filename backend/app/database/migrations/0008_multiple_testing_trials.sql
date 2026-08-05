CREATE TABLE multiple_testing_trials
(
    trial_id        TEXT PRIMARY KEY,
    family_key      TEXT NOT NULL,
    candidate_id    TEXT NOT NULL,
    backtest_id     TEXT NOT NULL,
    hypothesis_id   TEXT NOT NULL,
    actor           TEXT NOT NULL,
    family_sequence INTEGER NOT NULL CHECK (family_sequence >= 1),
    registered_at   TEXT NOT NULL,

    UNIQUE (backtest_id),
    FOREIGN KEY (candidate_id)
        REFERENCES pattern_candidates(candidate_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (backtest_id)
        REFERENCES pattern_candidate_backtests(backtest_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (family_key)
        REFERENCES replay_sessions(session_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_multiple_testing_trials_family
ON multiple_testing_trials(family_key, family_sequence);

CREATE INDEX idx_multiple_testing_trials_candidate
ON multiple_testing_trials(candidate_id);

CREATE TRIGGER prevent_multiple_testing_trials_update
BEFORE UPDATE ON multiple_testing_trials
BEGIN
    SELECT RAISE(ABORT, 'multiple testing trial registry is append-only');
END;

CREATE TRIGGER prevent_multiple_testing_trials_delete
BEFORE DELETE ON multiple_testing_trials
BEGIN
    SELECT RAISE(ABORT, 'multiple testing trial registry is append-only');
END;
