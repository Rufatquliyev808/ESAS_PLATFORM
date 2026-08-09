-- Phase 5 `rendering -> training` contract: the frozen ModelSpec/
-- TrainingSpec used the one time an experiment successfully passes every
-- training-readiness gate (see backend/app/strategies/visual_experiment_training.py).
-- One row per experiment -- idempotent for an identical spec (same
-- training_configuration_checksum), refused as a conflict for a different
-- one, mirroring visual_dataset_manifests' idempotent-with-conflict pattern.
-- No new ML dependency and no actual training happen here; this table only
-- records WHAT was frozen for a training run, not the run itself.

CREATE TABLE visual_training_configs
(
    experiment_id                     TEXT PRIMARY KEY,
    model_spec_id                     TEXT NOT NULL,
    model_spec_json                   TEXT NOT NULL,
    training_spec_id                  TEXT NOT NULL,
    training_spec_json                TEXT NOT NULL,
    training_configuration_checksum   TEXT NOT NULL,
    dataset_fingerprint                TEXT NOT NULL,
    created_at                         TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_visual_training_configs_checksum
ON visual_training_configs(training_configuration_checksum);
