-- Phase 5 `evaluated -> accepted_for_shadow | rejected` step: metadata for
-- the accept/reject decision made from an experiment's holdout evaluation.
-- The full decision artifact (thresholds, reasons) lives in the
-- content-addressed artifact store (storage/artifact_store.py); this table
-- only records the summary fields needed to query/audit decisions plus the
-- checksum that locates the full artifact, mirroring visual_evaluations'
-- idempotent-with-conflict pattern. This decision governs SHADOW
-- eligibility only -- it never authorizes real trading.

CREATE TABLE visual_acceptance_decisions
(
    experiment_id                TEXT PRIMARY KEY,
    evaluation_checksum          TEXT NOT NULL,
    decision                     TEXT NOT NULL
                                  CHECK (decision IN ('accepted_for_shadow', 'rejected')),
    holdout_accuracy             REAL NOT NULL,
    majority_baseline_accuracy   REAL NOT NULL,
    improvement_over_baseline    REAL NOT NULL,
    decision_checksum            TEXT NOT NULL,
    created_at                   TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_visual_acceptance_decisions_decision
ON visual_acceptance_decisions(decision);
