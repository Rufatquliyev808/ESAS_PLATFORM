-- Phase 5 multiple-testing registry: every frozen (dataset, model spec,
-- training spec) combination is registered here as a trial BEFORE any
-- result is known, so a later acceptance decision can see how many
-- architecture/seed/hyperparameter attempts a "testing family" (all
-- trials against the SAME dataset) has accumulated, and correct its
-- significance threshold accordingly. Idempotent by (testing_family_id,
-- model_spec_id, training_spec_id) -- re-registering the identical trial
-- (e.g. an idempotent retry of training) never inflates the family's
-- trial count.

CREATE TABLE visual_testing_trials
(
    trial_id             TEXT PRIMARY KEY,
    testing_family_id    TEXT NOT NULL,
    experiment_id        TEXT NOT NULL,
    model_spec_id        TEXT NOT NULL,
    training_spec_id     TEXT NOT NULL,
    registered_at        TEXT NOT NULL,
    FOREIGN KEY (experiment_id)
        REFERENCES visual_experiments(experiment_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_visual_testing_trials_family
ON visual_testing_trials(testing_family_id);
