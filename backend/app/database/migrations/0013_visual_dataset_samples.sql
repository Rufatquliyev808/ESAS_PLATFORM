CREATE TABLE visual_dataset_samples
(
    sample_id                    TEXT PRIMARY KEY,
    experiment_id                TEXT NOT NULL,
    symbol                       TEXT NOT NULL,
    timeframe                    TEXT NOT NULL,
    source_bar_fingerprint       TEXT NOT NULL,
    render_spec_id               TEXT NOT NULL,
    image_checksum               TEXT NOT NULL,
    observation_window_start_at  TEXT NOT NULL,
    observation_end_at           TEXT NOT NULL,
    label_spec_id                TEXT NOT NULL,
    label_available_at           TEXT,
    label_value                  TEXT,
    label_status                 TEXT NOT NULL
                                  CHECK (label_status IN ('labeled', 'pending_horizon')),
    quality_flags_json           TEXT NOT NULL,
    split_id                     TEXT NOT NULL,
    created_at                   TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_visual_dataset_samples_experiment
ON visual_dataset_samples(experiment_id, split_id);

CREATE TABLE visual_dataset_manifests
(
    experiment_id         TEXT PRIMARY KEY,
    dataset_fingerprint   TEXT NOT NULL,
    manifest_fingerprint  TEXT NOT NULL,
    total_samples         INTEGER NOT NULL
                           CHECK (total_samples >= 0),
    entries_json          TEXT NOT NULL,
    materialized_at       TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);
