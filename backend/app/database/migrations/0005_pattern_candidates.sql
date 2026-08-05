CREATE TABLE pattern_candidates
(
    candidate_id                 TEXT PRIMARY KEY,
    created_by                   TEXT NOT NULL,
    replay_session_id            TEXT NOT NULL,
    hypothesis_id                TEXT NOT NULL,
    hypothesis_version            TEXT NOT NULL,
    family                        TEXT NOT NULL,
    direction                     TEXT NOT NULL,
    condition_state                TEXT NOT NULL
                                    CHECK (condition_state = 'candidate_confirmed'),
    observed_at                   TEXT,
    evidence_json                  TEXT NOT NULL,
    pattern_candidate_version      TEXT NOT NULL,
    hypothesis_registry_version    TEXT NOT NULL,
    source_fingerprint             TEXT NOT NULL,
    timeframe                      TEXT NOT NULL,
    parameters_json                 TEXT NOT NULL,
    lifecycle_state                 TEXT NOT NULL
                                     CHECK (lifecycle_state IN (
                                         'registered',
                                         'running',
                                         'evaluated',
                                         'accepted_for_shadow',
                                         'rejected',
                                         'archived',
                                         'blocked_by_data_quality',
                                         'invalid_leakage',
                                         'insufficient_evidence',
                                         'failed',
                                         'cancelled'
                                     )),
    state_version                   INTEGER NOT NULL DEFAULT 0
                                     CHECK (state_version >= 0),
    created_at                      TEXT NOT NULL,
    updated_at                      TEXT NOT NULL,
    FOREIGN KEY (replay_session_id)
        REFERENCES replay_sessions(session_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_pattern_candidates_owner
ON pattern_candidates(created_by, created_at DESC, candidate_id DESC);

CREATE INDEX idx_pattern_candidates_session
ON pattern_candidates(replay_session_id);

CREATE TABLE pattern_candidate_audit
(
    audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id   TEXT NOT NULL,
    actor          TEXT NOT NULL,
    actor_role     TEXT NOT NULL,
    action         TEXT NOT NULL,
    previous_state TEXT,
    next_state     TEXT NOT NULL,
    occurred_at    TEXT NOT NULL,
    FOREIGN KEY (candidate_id)
        REFERENCES pattern_candidates(candidate_id)
        ON DELETE RESTRICT
);

CREATE TRIGGER prevent_pattern_candidate_audit_update
BEFORE UPDATE ON pattern_candidate_audit
BEGIN
    SELECT RAISE(ABORT, 'pattern candidate audit is append-only');
END;

CREATE TRIGGER prevent_pattern_candidate_audit_delete
BEFORE DELETE ON pattern_candidate_audit
BEGIN
    SELECT RAISE(ABORT, 'pattern candidate audit is append-only');
END;

CREATE INDEX idx_pattern_candidate_audit_candidate
ON pattern_candidate_audit(candidate_id, audit_id);
