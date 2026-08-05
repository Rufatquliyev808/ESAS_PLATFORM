CREATE TABLE analysis_jobs
(
    job_id                TEXT PRIMARY KEY,
    job_type              TEXT NOT NULL
                           CHECK (job_type IN ('pattern_candidate_backtest')),
    created_by            TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    priority              INTEGER NOT NULL DEFAULT 3
                           CHECK (priority BETWEEN 1 AND 5),
    payload_json          TEXT NOT NULL,
    payload_hash          TEXT NOT NULL,
    idempotency_key_hash  TEXT NOT NULL,
    related_resource_id   TEXT NOT NULL,
    correlation_id        TEXT NOT NULL,

    state                 TEXT NOT NULL
                           CHECK (state IN (
                               'queued',
                               'claimed',
                               'running',
                               'pausing',
                               'paused',
                               'retry_wait',
                               'completed',
                               'cancelled',
                               'interrupted',
                               'failed'
                           )),
    state_version          INTEGER NOT NULL DEFAULT 0
                            CHECK (state_version >= 0),

    attempt_count           INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts            INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
    next_attempt_at         TEXT,

    lease_owner             TEXT,
    lease_expires_at        TEXT,
    fencing_token            INTEGER NOT NULL DEFAULT 0 CHECK (fencing_token >= 0),

    started_at               TEXT,
    last_heartbeat_at         TEXT,
    completed_at              TEXT,
    error_code                TEXT,
    result_json               TEXT,

    cancel_requested           INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0, 1)),

    updated_at                 TEXT NOT NULL,

    UNIQUE (job_type, idempotency_key_hash)
);

CREATE INDEX idx_analysis_jobs_claimable
ON analysis_jobs(job_type, state, priority, created_at);

CREATE INDEX idx_analysis_jobs_owner
ON analysis_jobs(created_by, created_at DESC, job_id DESC);

CREATE INDEX idx_analysis_jobs_resource
ON analysis_jobs(related_resource_id);

CREATE TABLE analysis_job_audit
(
    audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         TEXT NOT NULL,
    actor          TEXT NOT NULL,
    actor_kind     TEXT NOT NULL CHECK (actor_kind IN ('user', 'worker')),
    action         TEXT NOT NULL,
    previous_state TEXT,
    next_state     TEXT NOT NULL,
    fencing_token  INTEGER,
    details_json   TEXT,
    occurred_at    TEXT NOT NULL,
    FOREIGN KEY (job_id)
        REFERENCES analysis_jobs(job_id)
        ON DELETE RESTRICT
);

CREATE TRIGGER prevent_analysis_job_audit_update
BEFORE UPDATE ON analysis_job_audit
BEGIN
    SELECT RAISE(ABORT, 'analysis job audit is append-only');
END;

CREATE TRIGGER prevent_analysis_job_audit_delete
BEFORE DELETE ON analysis_job_audit
BEGIN
    SELECT RAISE(ABORT, 'analysis job audit is append-only');
END;

CREATE INDEX idx_analysis_job_audit_job
ON analysis_job_audit(job_id, audit_id);
