CREATE TABLE pattern_candidate_backtests
(
    backtest_id           TEXT PRIMARY KEY,
    candidate_id          TEXT NOT NULL,
    created_by            TEXT NOT NULL,
    horizon_bars           INTEGER NOT NULL CHECK (horizon_bars >= 1),
    cost_parameters_json    TEXT NOT NULL,
    result_json             TEXT NOT NULL,
    fingerprint             TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    FOREIGN KEY (candidate_id)
        REFERENCES pattern_candidates(candidate_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_pattern_candidate_backtests_candidate
ON pattern_candidate_backtests(candidate_id, created_at DESC);

CREATE TRIGGER prevent_pattern_candidate_backtest_update
BEFORE UPDATE ON pattern_candidate_backtests
BEGIN
    SELECT RAISE(ABORT, 'pattern candidate backtests are append-only');
END;

CREATE TRIGGER prevent_pattern_candidate_backtest_delete
BEFORE DELETE ON pattern_candidate_backtests
BEGIN
    SELECT RAISE(ABORT, 'pattern candidate backtests are append-only');
END;
