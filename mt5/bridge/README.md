# ESAS MT5 Bridge

Version: 0.2.0

Status: EXPERIMENTAL

## Purpose

This module is the minimal MetaTrader 5 bridge for ESAS Platform Phase 1.

Its responsibilities are limited to:

- receive live ticks from MT5;
- convert each tick into the standard `TICK_RECEIVED` event;
- optionally print serialized events to the MT5 Experts log;
- optionally send events to the ESAS backend using HTTP.

This module does not:

- analyze market behavior;
- generate trading signals;
- open, modify, or close trades;
- write directly to a database.

## Files

- `module.json` — module identity, version, lifecycle status, and capabilities.
- `include/EsasTickEvent.mqh` — tick-event structure and JSON serialization.
- `include/EsasHttpTransport.mqh` — isolated HTTP POST transport.
- `src/ESAS_MT5_Bridge.mq5` — minimal EA entry point.

## Inputs

- `InpEmitTickEvents` — prints tick events to the MT5 log.
- `InpSendTicksToBackend` — sends tick events to the backend.
- `InpBackendTickUrl` — backend tick endpoint.
- `InpHttpTimeoutMs` — HTTP request timeout.

Default backend endpoint:

`http://127.0.0.1:8000/events/ticks`

MT5 must allow WebRequest access to:

`http://127.0.0.1:8000`

## Current Transport Limitation

Version 0.2.0 sends one synchronous HTTP request per tick.

This implementation is suitable only for integration testing.

It must not remain enabled for long-running or high-frequency collection. A later version will introduce buffering or queued transport without changing the event contract.