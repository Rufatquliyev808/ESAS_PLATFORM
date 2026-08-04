CREATE INDEX idx_tick_events_replay
ON tick_events(symbol, event_timestamp, event_id);
