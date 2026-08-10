-- Phase 5 Deterministic CPU visual baseline trainer v1
-- (pixel_centroid_baseline_v1): metadata for the model + training-log
-- artifacts a training run produced. The actual model/log CONTENT lives in
-- the content-addressed artifact store (storage/artifact_store.py); this
-- table only records which checksums belong to which experiment, mirroring
-- visual_training_configs' idempotent-with-conflict pattern (same
-- checksum -> no-op, different checksum -> refused, never silently
-- overwritten).

CREATE TABLE visual_baseline_models
(
    experiment_id             TEXT PRIMARY KEY,
    architecture_id           TEXT NOT NULL,
    version                   TEXT NOT NULL,
    dataset_fingerprint       TEXT NOT NULL,
    preprocessing_checksum    TEXT NOT NULL,
    model_spec_id             TEXT NOT NULL,
    training_spec_id          TEXT NOT NULL,
    model_checksum            TEXT NOT NULL,
    log_checksum              TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_visual_baseline_models_checksum
ON visual_baseline_models(model_checksum);
