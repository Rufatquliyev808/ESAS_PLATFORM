# ADR-0001: Persistent Tick Delivery Queue

Date: 2026-07-29

Status: Accepted

## Problem

The MT5 Bridge currently keeps failed tick deliveries in RAM. A backend outage is
handled, but stopping the Expert Advisor, MT5, or the computer destroys the
pending queue.

## Requirements

- Preserve the original serialized event without modification.
- Preserve FIFO delivery order.
- Remove an event only after a successful HTTP response.
- Recover pending events after an EA or MT5 restart.
- Prefer duplicate delivery over silent event loss.
- Detect invalid or incomplete records.
- Avoid DLLs and direct database access from the MT5 Bridge.
- Keep queue files inside the MQL5 file sandbox.
- Apply an explicit event-count limit and report rejected writes.

## Alternatives

### SQLite

SQLite provides transactions, indexing, and mature recovery behavior. MQL5 does
not provide the project with a native SQLite client, so this option would require
a DLL or a second local service. That adds deployment, security, and availability
dependencies to the component that must continue working while the backend is
unavailable.

### Text JSON Lines

JSON Lines is easy to inspect and append. A crash during a write can leave an
incomplete final line, and exact durable acknowledgement offsets depend on text
encoding and newline conversion.

### Length-prefixed binary journal

Each record contains a four-byte payload length followed by the UTF-8 event
bytes. A separate checkpoint stores the byte offset after the last acknowledged
record. This format supports exact offsets and detects truncated records without
changing the event payload.

## Decision

Use a length-prefixed binary append-only journal in the MQL5 `FILE_COMMON`
sandbox.

The queue key contains the account login and symbol so independent symbol streams
do not share one file. The queue has a `.queue` journal containing immutable
event records and a `.checkpoint` file containing the acknowledged byte offset.

Enqueue appends and flushes one complete record. Peek reads the record at the
checkpoint. Remove-first writes and flushes the next checkpoint only after the
backend accepted the event.

On startup the queue scans records from the checkpoint and rebuilds the pending
count. Invalid checkpoints are reset to zero, which can replay acknowledged
events but does not discard them. A truncated or invalid record causes
initialization to fail and leaves the journal untouched for diagnosis.

When all records are acknowledged, the journal and checkpoint are deleted. If
cleanup fails, the checkpoint remains at end-of-file and prevents acknowledged
records from being treated as pending.

## Capacity policy

The configured capacity is the maximum pending event count. Enqueue returns
failure when the limit is reached. The Bridge must emit an explicit log message
containing the capacity and pending count. Silent deletion and overwriting of old
events are forbidden.

## Failure semantics

- Crash before journal flush: the new event may be absent or detected as a
  truncated final record. Existing complete records remain untouched.
- Crash after journal flush: the event is recovered.
- Crash after backend storage but before checkpoint flush: the event is replayed.
  Backend idempotency prevents a second database row.
- Corrupt checkpoint: replay from the beginning; duplicate-safe and loss-averse.
- Corrupt journal record: stop queue initialization and preserve the file.
- Disk full or capacity reached: reject enqueue and log the failure explicitly.

The system provides at-least-once delivery, not exactly-once delivery.

## Consequences

Benefits:

- no dependency on backend availability, SQLite libraries, or DLLs;
- restart recovery with FIFO order;
- exact acknowledgement offsets;
- incomplete records are detectable;
- original event JSON remains unchanged.

Risks:

- synchronous disk flush can add tick-processing latency;
- duplicate replay is possible after a crash;
- manual recovery is required for a corrupt journal;
- finite disk and configured capacity can still be exhausted.

## Acceptance criteria

- Pending events survive EA removal and MT5 restart.
- Restart recovery preserves FIFO order.
- A record is acknowledged only after successful HTTP delivery.
- A failed HTTP delivery leaves the checkpoint unchanged.
- Truncated records are detected without deleting the journal.
- Queue limit failures are visible in logs.
- MetaEditor compilation completes with zero errors and warnings.
- Existing backend tests continue to pass.
- A live outage/restart/recovery test drains the queue to zero.
