-- Phase 5 `training -> evaluated` step: metadata for the holdout
-- evaluation of a baseline model. The full evaluation artifact (holdout
-- metrics, majority-baseline comparison, OOD check) lives in the
-- content-addressed artifact store (storage/artifact_store.py); this table
-- only records the summary fields needed to query/audit evaluations plus
-- the checksum that locates the full artifact, mirroring
-- visual_baseline_models' idempotent-with-conflict pattern.

CREATE TABLE visual_evaluations
(
    experiment_id                TEXT PRIMARY KEY,
    model_checksum                TEXT NOT NULL,
    outcome                       TEXT NOT NULL
                                   CHECK (outcome IN ('evaluated', 'insufficient_evidence', 'out_of_distribution')),
    holdout_sample_count          INTEGER NOT NULL
                                   CHECK (holdout_sample_count >= 0),
    holdout_accuracy              REAL NOT NULL,
    majority_baseline_accuracy    REAL NOT NULL,
    evaluation_checksum           TEXT NOT NULL,
    created_at                    TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_visual_evaluations_outcome
ON visual_evaluations(outcome);
