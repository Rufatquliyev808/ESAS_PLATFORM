-- Phase 9 SHADOW validation contract, section 6 (nəzəri portfolio və risk).
-- Still a persistence skeleton -- no live decision feed exists yet (Phase
-- 5-8 are design-only), so nothing writes to this table in production yet.
-- This ledger has zero relationship to any real account/broker table by
-- construction: it only ever references shadow_runs/shadow_run_participants/
-- shadow_events, so it cannot touch a real balance or MT5 position even by
-- mistake.

CREATE TABLE shadow_theoretical_positions
(
    position_id               TEXT PRIMARY KEY,
    shadow_run_id             TEXT NOT NULL,
    participant_id            TEXT NOT NULL,
    symbol                    TEXT NOT NULL,
    direction                 TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    theoretical_size          REAL NOT NULL CHECK (theoretical_size > 0),
    reserved_risk_amount      REAL NOT NULL CHECK (reserved_risk_amount >= 0),

    opened_at                 TEXT NOT NULL,
    open_event_id             TEXT NOT NULL,

    state                     TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'closed')),
    state_version             INTEGER NOT NULL DEFAULT 0 CHECK (state_version >= 0),

    closed_at                 TEXT,
    close_event_id            TEXT,
    theoretical_pnl_percent   REAL,

    updated_at                TEXT NOT NULL,

    FOREIGN KEY (shadow_run_id)
        REFERENCES shadow_runs(shadow_run_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (participant_id)
        REFERENCES shadow_run_participants(participant_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (open_event_id)
        REFERENCES shadow_events(event_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (close_event_id)
        REFERENCES shadow_events(event_id)
        ON DELETE RESTRICT
);

CREATE INDEX idx_shadow_theoretical_positions_run
ON shadow_theoretical_positions(shadow_run_id, state);

CREATE INDEX idx_shadow_theoretical_positions_concentration
ON shadow_theoretical_positions(shadow_run_id, symbol, direction, state);

-- Every field except state/closed_at/close_event_id/theoretical_pnl_percent/
-- state_version/updated_at is frozen once a position is opened -- a
-- position's own identity (run, participant, symbol, direction, size,
-- reserved risk, open event) can never be silently rewritten.
CREATE TRIGGER prevent_shadow_theoretical_position_identity_mutation
BEFORE UPDATE ON shadow_theoretical_positions
WHEN
    NEW.position_id != OLD.position_id OR
    NEW.shadow_run_id != OLD.shadow_run_id OR
    NEW.participant_id != OLD.participant_id OR
    NEW.symbol != OLD.symbol OR
    NEW.direction != OLD.direction OR
    NEW.theoretical_size != OLD.theoretical_size OR
    NEW.reserved_risk_amount != OLD.reserved_risk_amount OR
    NEW.opened_at != OLD.opened_at OR
    NEW.open_event_id != OLD.open_event_id
BEGIN
    SELECT RAISE(ABORT, 'shadow theoretical position identity is immutable once opened');
END;
