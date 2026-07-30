# ESAS MT5 Bridge

Version: 1.5.0

Status: EXPERIMENTAL

## Purpose

This module is the minimal MetaTrader 5 bridge for ESAS Platform Phase 1.

Its responsibilities are limited to:

- receive live ticks from MT5;
- convert each tick into the standard `TICK_RECEIVED` event;
- optionally print serialized events to the MT5 Experts log;
- optionally send events to the ESAS backend using HTTP.
- persist events to disk when backend delivery fails;
- retry queued events in FIFO batches when the backend becomes available;
- recover pending events after an EA or MT5 restart.
- persist rejected-event metrics across restarts;
- report queue health to the backend operational API.

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

- `include/EsasPersistentTickQueue.mqh`: persistent FIFO delivery queue.

## Inputs

- `InpEmitTickEvents` — prints tick events to the MT5 log.
- `InpSendTicksToBackend` — sends tick events to the backend.
- `InpBackendTickUrl` — backend tick endpoint.
- `InpBackendStatusUrl` — backend Bridge status endpoint.
- `InpHttpTimeoutMs` — HTTP request timeout.
- `InpTickBufferCapacity` — maximum number of pending events stored on disk.
- `InpRetryIntervalSeconds` — interval between queued delivery attempts.
- `InpRetryBatchSize` — maximum queued events delivered in one retry cycle.
- `InpStatusIntervalSeconds` — interval between Bridge status reports.

Default backend endpoint:

`http://127.0.0.1:8000/events/ticks`

MT5 must allow WebRequest access to:

`http://127.0.0.1:8000`

## Current Transport Limitation

Version 1.5.0 uses synchronous HTTP requests.

When delivery fails, events are appended to a persistent FIFO journal in the
MQL5 common file sandbox. The bridge retries queued events in configurable
batches after the backend becomes available.

Pending events and their acknowledgement checkpoint survive EA and MT5
restarts. Delivery is at least once: a crash after backend storage but before
checkpoint persistence can replay an event, and backend idempotency prevents a
second database row.

Queue capacity, pending count, persistent rejected-event count, and the latest
queue error are reported to `POST /status/bridge`. They are exposed by
`GET /status/operational` under `bridge_delivery`.
