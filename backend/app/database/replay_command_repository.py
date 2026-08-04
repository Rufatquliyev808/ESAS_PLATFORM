from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import secrets

from backend.app.database.connection import get_connection
from backend.app.database.replay_session_repository import (
    ReplaySessionNotFoundError,
    ReplayTransitionConflictError,
    _read_step_ticks,
)
from backend.app.database.tick_replay_repository import TickPosition


COMMAND_TRANSITIONS = {
    "start": {"created": "running"},
    "pause": {"running": "paused"},
    "resume": {"paused": "running", "interrupted": "running"},
    "cancel": {
        "created": "cancelled",
        "running": "cancelled",
        "paused": "cancelled",
        "interrupted": "cancelled",
    },
}


class ReplayOwnershipError(PermissionError):
    pass


@dataclass(frozen=True)
class ReplayCommandResult:
    session_id: str
    command: str
    state: str
    state_version: int
    processed_ticks: int
    checkpoint_position: TickPosition | None
    idempotent_replay: bool


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _result_from_command(row: object, *, replayed: bool) -> ReplayCommandResult:
    checkpoint = None
    if row["resulting_checkpoint_time"] is not None:
        checkpoint = TickPosition(
            datetime.fromisoformat(row["resulting_checkpoint_time"]),
            row["resulting_checkpoint_event"],
        )
    return ReplayCommandResult(
        session_id=row["session_id"],
        command=row["command"],
        state=row["resulting_state"],
        state_version=row["resulting_state_version"],
        processed_ticks=row["resulting_processed_ticks"],
        checkpoint_position=checkpoint,
        idempotent_replay=replayed,
    )


def execute_replay_command(
    *,
    session_id: str,
    actor: str,
    actor_role: str,
    idempotency_key: str,
    command: str,
    expected_state_version: int,
    requested_ticks: int | None = None,
) -> ReplayCommandResult:
    normalized_session = _required_text(session_id, "session_id")
    normalized_actor = _required_text(actor, "actor")
    normalized_role = _required_text(actor_role, "actor_role")
    normalized_key = _required_text(idempotency_key, "idempotency_key")
    normalized_command = _required_text(command, "command")
    if expected_state_version < 0:
        raise ValueError("expected_state_version must not be negative")
    if normalized_command == "step":
        if requested_ticks is None or not 1 <= requested_ticks <= 1000:
            raise ValueError("requested_ticks must be between 1 and 1000")
    elif requested_ticks is not None:
        raise ValueError("requested_ticks is only valid for step")
    elif normalized_command not in COMMAND_TRANSITIONS:
        raise ValueError("unknown replay command")

    key_hash = hashlib.sha256(normalized_key.encode("utf-8")).hexdigest()
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "command": normalized_command,
                "expected_state_version": expected_state_version,
                "requested_ticks": requested_ticks,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        session = connection.execute(
            "SELECT * FROM replay_sessions WHERE session_id = ?;",
            (normalized_session,),
        ).fetchone()
        if session is None:
            raise ReplaySessionNotFoundError("replay session was not found")
        if session["created_by"] != normalized_actor:
            raise ReplayOwnershipError("replay session belongs to another user")

        existing = connection.execute(
            """
            SELECT * FROM replay_commands
            WHERE session_id = ? AND actor = ? AND idempotency_key_hash = ?;
            """,
            (normalized_session, normalized_actor, key_hash),
        ).fetchone()
        if existing is not None:
            if existing["request_fingerprint"] != fingerprint:
                raise ReplayTransitionConflictError(
                    "idempotency key was used with a different request"
                )
            return _result_from_command(existing, replayed=True)

        if session["state_version"] != expected_state_version:
            raise ReplayTransitionConflictError(
                "replay session state_version does not match"
            )

        previous_state = session["state"]
        next_state = previous_state
        next_processed = session["processed_ticks"]
        checkpoint_time = session["checkpoint_event_timestamp"]
        checkpoint_event = session["checkpoint_event_id"]
        action = normalized_command

        if normalized_command == "step":
            if session["mode"] != "step" or previous_state != "running":
                raise ReplayTransitionConflictError(
                    "step requires a running step-mode replay session"
                )
            remaining = session["dataset_tick_count"] - next_processed
            if remaining <= 0:
                raise ReplayTransitionConflictError(
                    "replay session has no remaining ticks"
                )
            limit = min(requested_ticks, remaining)
            ticks = _read_step_ticks(
                connection,
                symbol=session["symbol"],
                start_at=session["start_at"],
                end_at=session["end_at"],
                after_timestamp=checkpoint_time,
                after_event_id=checkpoint_event,
                limit=limit,
            )
            if len(ticks) != limit:
                raise ReplayTransitionConflictError(
                    "replay dataset changed after session creation"
                )
            last_tick = ticks[-1]
            next_processed += len(ticks)
            checkpoint_time = last_tick.event_timestamp
            checkpoint_event = last_tick.event_id
            if next_processed == session["dataset_tick_count"]:
                next_state = "completed"
        else:
            next_state = COMMAND_TRANSITIONS[normalized_command].get(previous_state)
            if next_state is None:
                raise ReplayTransitionConflictError(
                    f"command {normalized_command} is invalid from state {previous_state}"
                )

        now = datetime.now(UTC).isoformat(timespec="microseconds")
        next_version = expected_state_version + 1
        terminal_at = now if next_state in {"completed", "cancelled"} else None
        last_batch_at = now if normalized_command == "step" else session["last_batch_at"]
        updated = connection.execute(
            """
            UPDATE replay_sessions
            SET state = ?, state_version = ?, processed_ticks = ?,
                checkpoint_event_timestamp = ?, checkpoint_event_id = ?,
                last_batch_at = ?, updated_at = ?, completed_at = ?
            WHERE session_id = ? AND state_version = ?;
            """,
            (
                next_state, next_version, next_processed, checkpoint_time,
                checkpoint_event, last_batch_at, now, terminal_at,
                normalized_session, expected_state_version,
            ),
        )
        if updated.rowcount != 1:
            raise ReplayTransitionConflictError(
                "replay session changed during command processing"
            )
        connection.execute(
            """
            INSERT INTO replay_session_audit
            (
                session_id, actor, actor_role, action, previous_state,
                next_state, processed_ticks, checkpoint_time,
                checkpoint_event, occurred_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_session, normalized_actor, normalized_role, action,
                previous_state, next_state, next_processed, checkpoint_time,
                checkpoint_event, now,
            ),
        )
        connection.execute(
            """
            INSERT INTO replay_commands
            (
                command_id, session_id, idempotency_key_hash,
                request_fingerprint, actor, actor_role, command,
                expected_state_version, resulting_state_version,
                resulting_state, resulting_processed_ticks,
                resulting_checkpoint_time, resulting_checkpoint_event,
                occurred_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                f"rpc_{secrets.token_urlsafe(18)}", normalized_session,
                key_hash, fingerprint, normalized_actor, normalized_role,
                normalized_command, expected_state_version, next_version,
                next_state, next_processed, checkpoint_time, checkpoint_event,
                now,
            ),
        )
        stored = connection.execute(
            """
            SELECT * FROM replay_commands
            WHERE session_id = ? AND actor = ? AND idempotency_key_hash = ?;
            """,
            (normalized_session, normalized_actor, key_hash),
        ).fetchone()

    return _result_from_command(stored, replayed=False)
