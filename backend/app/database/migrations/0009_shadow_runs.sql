-- Phase 9 SHADOW validation contract (docs/architecture/PHASE_9_SHADOW_VALIDATION_CONTRACT.md).
-- This is the run manifest + append-only event registry skeleton only --
-- no live decision feed exists yet (Phase 5-8 are design-only), so nothing
-- writes to these tables in production yet. execution_allowed is locked to
-- 0 structurally: no application bug can ever flip it, per contract section 2
-- ("execution_allowed=false bütün SHADOW qərarlarında məcburidir").

CREATE TABLE shadow_runs
(
    shadow_run_id                        TEXT PRIMARY KEY,
    created_by                           TEXT NOT NULL,
    created_at                           TEXT NOT NULL,
    planned_end_at                       TEXT NOT NULL,
    code_commit                          TEXT NOT NULL,
    config_hash                          TEXT NOT NULL,
    feature_claim_versions_json          TEXT NOT NULL,
    symbols_json                         TEXT NOT NULL,
    timeframes_json                      TEXT NOT NULL,
    sessions_json                        TEXT NOT NULL,
    accepted_market_regimes_json         TEXT NOT NULL,
    minimum_market_open_duration_seconds INTEGER NOT NULL CHECK (minimum_market_open_duration_seconds >= 0),
    minimum_eligible_decision_count      INTEGER NOT NULL CHECK (minimum_eligible_decision_count >= 1),
    primary_metric                       TEXT NOT NULL,
    primary_metric_threshold             REAL NOT NULL,
    secondary_metrics_json               TEXT NOT NULL,
    failure_rules_json                   TEXT NOT NULL,
    theoretical_fill_model_json          TEXT NOT NULL,
    risk_budget_json                     TEXT NOT NULL,
    data_quality_policy_json             TEXT NOT NULL,
    approved_by                          TEXT NOT NULL,
    rollback_plan                        TEXT NOT NULL,

    -- Structural invariant, not just an application convention: SQLite itself
    -- refuses any row where this is not exactly 0.
    execution_allowed                    INTEGER NOT NULL DEFAULT 0 CHECK (execution_allowed = 0),

    state                                TEXT NOT NULL DEFAULT 'registered'
                                          CHECK (state IN ('registered', 'started', 'completed', 'halted')),
    state_version                        INTEGER NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    halt_reason                          TEXT,
    updated_at                           TEXT NOT NULL
);

CREATE INDEX idx_shadow_runs_owner
ON shadow_runs(created_by, created_at DESC);

-- Section 3: "Run başladıqdan sonra hədəf, metrik və hədlər dəyişdirilmir."
-- Every manifest field except state/state_version/halt_reason/updated_at is
-- frozen the instant the row is inserted -- this trigger makes that a DB
-- guarantee, not just an API convention.
CREATE TRIGGER prevent_shadow_run_manifest_mutation
BEFORE UPDATE ON shadow_runs
WHEN
    NEW.shadow_run_id != OLD.shadow_run_id OR
    NEW.created_by != OLD.created_by OR
    NEW.created_at != OLD.created_at OR
    NEW.planned_end_at != OLD.planned_end_at OR
    NEW.code_commit != OLD.code_commit OR
    NEW.config_hash != OLD.config_hash OR
    NEW.feature_claim_versions_json != OLD.feature_claim_versions_json OR
    NEW.symbols_json != OLD.symbols_json OR
    NEW.timeframes_json != OLD.timeframes_json OR
    NEW.sessions_json != OLD.sessions_json OR
    NEW.accepted_market_regimes_json != OLD.accepted_market_regimes_json OR
    NEW.minimum_market_open_duration_seconds != OLD.minimum_market_open_duration_seconds OR
    NEW.minimum_eligible_decision_count != OLD.minimum_eligible_decision_count OR
    NEW.primary_metric != OLD.primary_metric OR
    NEW.primary_metric_threshold != OLD.primary_metric_threshold OR
    NEW.secondary_metrics_json != OLD.secondary_metrics_json OR
    NEW.failure_rules_json != OLD.failure_rules_json OR
    NEW.theoretical_fill_model_json != OLD.theoretical_fill_model_json OR
    NEW.risk_budget_json != OLD.risk_budget_json OR
    NEW.data_quality_policy_json != OLD.data_quality_policy_json OR
    NEW.approved_by != OLD.approved_by OR
    NEW.rollback_plan != OLD.rollback_plan OR
    NEW.execution_allowed != OLD.execution_allowed
BEGIN
    SELECT RAISE(ABORT, 'shadow run manifest is immutable once created; only state may change');
END;

CREATE TABLE shadow_run_participants
(
    participant_id   TEXT PRIMARY KEY,
    shadow_run_id    TEXT NOT NULL,
    role              TEXT NOT NULL CHECK (role IN ('champion', 'challenger')),
    module_id         TEXT NOT NULL,
    module_version    TEXT NOT NULL,

    UNIQUE (shadow_run_id, role, module_id),
    FOREIGN KEY (shadow_run_id)
        REFERENCES shadow_runs(shadow_run_id)
        ON DELETE RESTRICT
);

CREATE TRIGGER prevent_shadow_run_participants_update
BEFORE UPDATE ON shadow_run_participants
BEGIN
    SELECT RAISE(ABORT, 'shadow run participants are append-only');
END;

CREATE TRIGGER prevent_shadow_run_participants_delete
BEFORE DELETE ON shadow_run_participants
BEGIN
    SELECT RAISE(ABORT, 'shadow run participants are append-only');
END;

-- Section 9 event families. No ORDER_* event type can ever exist here --
-- the CHECK constraint is the entire allow-list.
CREATE TABLE shadow_events
(
    event_id        TEXT PRIMARY KEY,
    shadow_run_id   TEXT NOT NULL,
    event_type      TEXT NOT NULL
                    CHECK (event_type IN (
                        'SHADOW_RUN_STARTED',
                        'SHADOW_DECISION_RECORDED',
                        'SHADOW_RISK_BLOCKED',
                        'SHADOW_THEORETICAL_POSITION_OPENED',
                        'SHADOW_THEORETICAL_POSITION_CLOSED',
                        'SHADOW_DATA_GAP_RECORDED',
                        'SHADOW_RUN_COMPLETED',
                        'SHADOW_PROMOTION_RECOMMENDED',
                        'SHADOW_PROMOTION_REJECTED'
                    )),
    correlation_id   TEXT NOT NULL,
    actor            TEXT NOT NULL,
    payload_json     TEXT NOT NULL,
    payload_hash     TEXT NOT NULL,
    occurred_at      TEXT NOT NULL,

    FOREIGN KEY (shadow_run_id)
        REFERENCES shadow_runs(shadow_run_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_shadow_events_run
ON shadow_events(shadow_run_id, occurred_at, event_id);

CREATE TRIGGER prevent_shadow_events_update
BEFORE UPDATE ON shadow_events
BEGIN
    SELECT RAISE(ABORT, 'shadow events are append-only');
END;

CREATE TRIGGER prevent_shadow_events_delete
BEFORE DELETE ON shadow_events
BEGIN
    SELECT RAISE(ABORT, 'shadow events are append-only');
END;
