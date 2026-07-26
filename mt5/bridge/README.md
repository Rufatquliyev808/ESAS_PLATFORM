# ESAS MT5 Bridge

Version: 0.1.0

Status: EXPERIMENTAL

The MQL5 `#property version` uses `1.000` only because MetaEditor requires its
own `xxx.yyy` format. The authoritative module version is `0.1.0` in
`module.json`.

## Purpose

This module is the minimal MetaTrader 5 bridge for ESAS Platform Phase 1.

Its only responsibility in this version is to:

- receive live ticks from MT5;
- convert each tick into the standard ESAS event envelope;
- emit the serialized `TICK_RECEIVED` event to the MT5 log.

This version does not:

- analyze market behavior;
- generate signals;
- open, modify, or close trades;
- write to a database;
- communicate over the network.

## Files

- `module.json` — module identity, version, lifecycle status, and capabilities.
- `include/EsasTickEvent.mqh` — immutable tick-event snapshot and JSON serialization.
- `src/ESAS_MT5_Bridge.mq5` — minimal EA entry point.

## Current Output

Every accepted tick is printed as one JSON line in the MT5 Experts log.

The transport mechanism is intentionally isolated for a later version so the
event contract does not depend on SQLite, files, sockets, or an API.
