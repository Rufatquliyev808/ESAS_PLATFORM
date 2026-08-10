-- Phase 5 -> Phase 9 lineage-only connection: lets a SHADOW run's
-- "challenger" participant reference the specific `accepted_for_shadow`
-- Visual AI experiment it represents (docs/architecture/
-- PHASE_9_SHADOW_VALIDATION_CONTRACT.md section 7's champion/challenger
-- model). This is deliberately NOT a live decision feed -- Phase 6-8 are
-- still design-only, so nothing generates SHADOW_DECISION_RECORDED events
-- from a Visual AI model yet. It only gives a SHADOW run manifest a
-- verifiable, checksum-pinned audit trail back to exactly which trained
-- model and which statistical acceptance decision a challenger stands for,
-- captured as an immutable snapshot the instant the participant is
-- registered (backend/app/database/shadow_run_repository.py derives the
-- checksums fresh from the persisted records rather than trusting caller
-- input).

CREATE TABLE shadow_run_participant_visual_lineage
(
    participant_id                       TEXT PRIMARY KEY,
    shadow_run_id                        TEXT NOT NULL,
    visual_experiment_id                 TEXT NOT NULL,
    visual_model_checksum                TEXT NOT NULL,
    visual_acceptance_decision_checksum  TEXT NOT NULL,
    recorded_at                          TEXT NOT NULL,

    FOREIGN KEY (participant_id)
        REFERENCES shadow_run_participants(participant_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (shadow_run_id)
        REFERENCES shadow_runs(shadow_run_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_shadow_run_participant_visual_lineage_experiment
ON shadow_run_participant_visual_lineage(visual_experiment_id);

CREATE TRIGGER prevent_shadow_run_participant_visual_lineage_update
BEFORE UPDATE ON shadow_run_participant_visual_lineage
BEGIN
    SELECT RAISE(ABORT, 'shadow run participant visual lineage is append-only');
END;

CREATE TRIGGER prevent_shadow_run_participant_visual_lineage_delete
BEFORE DELETE ON shadow_run_participant_visual_lineage
BEGIN
    SELECT RAISE(ABORT, 'shadow run participant visual lineage is append-only');
END;
