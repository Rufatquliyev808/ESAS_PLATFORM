# ESAS MT5 Bridge

Version: 1.3.0

Status: EXPERIMENTAL

## Purpose

This module is the minimal MetaTrader 5 bridge for ESAS Platform Phase 1.

Its responsibilities are limited to:

- receive live ticks from MT5;
- convert each tick into the standard `TICK_RECEIVED` event;
- optionally print serialized events to the MT5 Experts log;
- optionally send events to the ESAS backend using HTTP.
- buffer events in memory when backend delivery fails;
- retry buffered events in FIFO batches when the backend becomes available.

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
- `InpTickBufferCapacity` — maximum number of events stored in memory.
- `InpRetryIntervalSeconds` — interval between buffered delivery attempts.
- `InpRetryBatchSize` — maximum buffered events delivered in one retry cycle.

Default backend endpoint:

`http://127.0.0.1:8000/events/ticks`

MT5 must allow WebRequest access to:

`http://127.0.0.1:8000`

## Current Transport Limitation

Version 1.3.0 uses synchronous HTTP requests.

When delivery fails, events are stored in an in-memory FIFO buffer. The bridge retries buffered events in configurable batches after the backend becomes available.

The memory buffer protects against temporary backend outages, but its contents are lost when MT5 or the Expert Advisor stops. A later version will introduce persistent disk-backed delivery.
