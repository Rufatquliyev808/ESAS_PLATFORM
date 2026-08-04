from dataclasses import dataclass
from datetime import UTC, datetime
import secrets

from backend.app.database.connection import get_connection
from backend.app.database.tick_replay_repository import ReplayTick, TickPosition
from backend.app.replay.dataset_snapshot import (
    ReplayDatasetSnapshot,
    create_dataset_snapshot,
)


REPLAY_CONTRACT_VERSION = "1.0"
QUALITY_RULE_VERSION = "1.0"
REPLAY_MODES = frozenset({"step", "max_speed"})
TERMINAL_STATES = frozenset({"completed", "cancelled", "failed"})
ALLOWED_TRANSITIONS = {
    "start": {"created": "running"},
    "pause": {"running": "paused"},
    "resume": {"paused": "running", "interrupted": "running"},
    "complete": {"running": "completed"},
    "cancel": {
        "created": "cancelled",
        "running": "cancelled",
        "paused": "cancelled",
        "interrupted": "cancelled",
    },
    "interrupt": {"running": "interrupted"},
    "fail": {"running": "failed"},
}


class ReplaySessionNotFoundError(LookupError):
    pass


class ReplayTransitionConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplaySession:
    session_id: str
    created_by: str
    symbol: str
    start_at: str
    end_at: str
    mode: str
    state: str
    replay_contract_version: str
    quality_rule_version: str
    dataset_tick_count: int
    dataset_fingerprint: str
    first_position: TickPosition | None
    last_position: TickPosition | None
    processed_ticks: int
    checkpoint_position: TickPosition | None
    last_batch_at: str | None
    error_category: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


@dataclass(frozen=True)
class ReplayStepResult:
    session_id: str
    state: str
    processed_ticks: int
    checkpoint_position: TickPosition
    ticks: tuple[ReplayTick, ...]
    idempotent_replay: bool


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _position_values(
    position: TickPosition | None,
) -> tuple[str | None, str | None]:
    if position is None:
        return None, None
    return (
        position.event_timestamp.astimezone(UTC).isoformat(
            timespec="microseconds"
        ),
        position.event_id,
    )


def _new_session_id() -> str:
    return f"rps_{secrets.token_urlsafe(24)}"


def create_replay_session(
    *,
    created_by: str,
    actor_role: str,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    mode: str,
    replay_contract_version: str = REPLAY_CONTRACT_VERSION,
    quality_rule_version: str = QUALITY_RULE_VERSION,
    snapshot_batch_size: int = 1000,
) -> ReplaySession:
    normalized_creator = _required_text(created_by, "created_by")
    normalized_role = _required_text(actor_role, "actor_role")
    normalized_symbol = _required_text(symbol, "symbol")
    normalized_mode = _required_text(mode, "mode")
    normalized_replay_version = _required_text(
        replay_contract_version,
        "replay_contract_version",
    )
    normalized_quality_version = _required_text(
        quality_rule_version,
        "quality_rule_version",
    )
    if normalized_mode not in REPLAY_MODES:
        raise ValueError("mode must be step or max_speed")

    snapshot = create_dataset_snapshot(
        symbol=normalized_symbol,
        start_at=start_at,
        end_at=end_at,
        batch_size=snapshot_batch_size,
    )
    return _store_session_and_initial_audit(
        created_by=normalized_creator,
        actor_role=normalized_role,
        symbol=normalized_symbol,
        start_at=start_at,
        end_at=end_at,
        mode=normalized_mode,
        replay_contract_version=normalized_replay_version,
        quality_rule_version=normalized_quality_version,
        snapshot=snapshot,
    )


def _store_session_and_initial_audit(
    *,
    created_by: str,
    actor_role: str,
    symbol: str,
    start_at: datetime,
    end_at: datetime,
    mode: str,
    replay_contract_version: str,
    quality_rule_version: str,
    snapshot: ReplayDatasetSnapshot,
) -> ReplaySession:
    session_id = _new_session_id()
    now = datetime.now(UTC).isoformat(timespec="microseconds")
    start_text = start_at.astimezone(UTC).isoformat(timespec="microseconds")
    end_text = end_at.astimezone(UTC).isoformat(timespec="microseconds")
    state = "completed" if snapshot.tick_count == 0 else "created"
    completed_at = now if state == "completed" else None
    first_timestamp, first_event_id = _position_values(
        snapshot.first_position
    )
    last_timestamp, last_event_id = _position_values(snapshot.last_position)

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        connection.execute(
            """
            INSERT INTO replay_sessions
            (
                session_id, created_by, symbol, start_at, end_at, mode, state,
                replay_contract_version, quality_rule_version,
                dataset_tick_count, dataset_fingerprint,
                first_event_timestamp, first_event_id,
                last_event_timestamp, last_event_id,
                processed_ticks, created_at, updated_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?);
            """,
            (
                session_id,
                created_by,
                symbol,
                start_text,
                end_text,
                mode,
                state,
                replay_contract_version,
                quality_rule_version,
                snapshot.tick_count,
                snapshot.fingerprint,
                first_timestamp,
                first_event_id,
                last_timestamp,
                last_event_id,
                now,
                now,
                completed_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO replay_session_audit
            (
                session_id, actor, actor_role, action, previous_state,
                next_state, processed_ticks, occurred_at
            )
            VALUES (?, ?, ?, 'create', NULL, ?, 0, ?);
            """,
            (session_id, created_by, actor_role, state, now),
        )

    return ReplaySession(
        session_id=session_id,
        created_by=created_by,
        symbol=symbol,
        start_at=start_text,
        end_at=end_text,
        mode=mode,
        state=state,
        replay_contract_version=replay_contract_version,
        quality_rule_version=quality_rule_version,
        dataset_tick_count=snapshot.tick_count,
        dataset_fingerprint=snapshot.fingerprint,
        first_position=snapshot.first_position,
        last_position=snapshot.last_position,
        processed_ticks=0,
        checkpoint_position=None,
        last_batch_at=None,
        error_category=None,
        created_at=now,
        updated_at=now,
        completed_at=completed_at,
    )


def _position_key(position: TickPosition) -> tuple[datetime, str]:
    return position.event_timestamp.astimezone(UTC), position.event_id


def _row_position(
    row: object,
    timestamp_field: str,
    event_field: str,
) -> TickPosition | None:
    timestamp = row[timestamp_field]
    event_id = row[event_field]
    if timestamp is None and event_id is None:
        return None
    if timestamp is None or event_id is None:
        raise RuntimeError("stored replay position is incomplete")
    return TickPosition(datetime.fromisoformat(timestamp), event_id)


def _session_from_row(row: object) -> ReplaySession:
    return ReplaySession(
        session_id=row["session_id"],
        created_by=row["created_by"],
        symbol=row["symbol"],
        start_at=row["start_at"],
        end_at=row["end_at"],
        mode=row["mode"],
        state=row["state"],
        replay_contract_version=row["replay_contract_version"],
        quality_rule_version=row["quality_rule_version"],
        dataset_tick_count=row["dataset_tick_count"],
        dataset_fingerprint=row["dataset_fingerprint"],
        first_position=_row_position(
            row,
            "first_event_timestamp",
            "first_event_id",
        ),
        last_position=_row_position(
            row,
            "last_event_timestamp",
            "last_event_id",
        ),
        processed_ticks=row["processed_ticks"],
        checkpoint_position=_row_position(
            row,
            "checkpoint_event_timestamp",
            "checkpoint_event_id",
        ),
        last_batch_at=row["last_batch_at"],
        error_category=row["error_category"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


def transition_replay_session(
    *,
    session_id: str,
    actor: str,
    actor_role: str,
    action: str,
    expected_state: str,
    processed_ticks: int | None = None,
    checkpoint_position: TickPosition | None = None,
    error_category: str | None = None,
) -> ReplaySession:
    normalized_session_id = _required_text(session_id, "session_id")
    normalized_actor = _required_text(actor, "actor")
    normalized_role = _required_text(actor_role, "actor_role")
    normalized_action = _required_text(action, "action")
    normalized_expected = _required_text(expected_state, "expected_state")
    transition = ALLOWED_TRANSITIONS.get(normalized_action)
    if transition is None:
        raise ValueError("unknown replay transition action")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = connection.execute(
            "SELECT * FROM replay_sessions WHERE session_id = ?;",
            (normalized_session_id,),
        ).fetchone()
        if row is None:
            raise ReplaySessionNotFoundError("replay session was not found")
        if row["state"] != normalized_expected:
            raise ReplayTransitionConflictError(
                "replay session state does not match expected_state"
            )

        next_state = transition.get(row["state"])
        if next_state is None:
            raise ReplayTransitionConflictError(
                f"action {normalized_action} is invalid from state {row['state']}"
            )

        current_processed = row["processed_ticks"]
        next_processed = (
            current_processed
            if processed_ticks is None
            else processed_ticks
        )
        if next_processed < current_processed:
            raise ValueError("processed_ticks must not move backwards")
        if next_processed > row["dataset_tick_count"]:
            raise ValueError("processed_ticks exceeds dataset_tick_count")

        current_checkpoint = _row_position(
            row,
            "checkpoint_event_timestamp",
            "checkpoint_event_id",
        )
        next_checkpoint = (
            current_checkpoint
            if checkpoint_position is None
            else checkpoint_position
        )
        if next_processed > 0 and next_checkpoint is None:
            raise ValueError("positive progress requires a checkpoint")
        if next_processed > current_processed and checkpoint_position is None:
            raise ValueError("progress increase requires a new checkpoint")
        if current_checkpoint is not None and checkpoint_position is not None:
            if _position_key(checkpoint_position) < _position_key(current_checkpoint):
                raise ValueError("checkpoint must not move backwards")
        if processed_ticks is not None and processed_ticks == current_processed:
            if checkpoint_position is not None and checkpoint_position != current_checkpoint:
                raise ValueError("checkpoint cannot change without progress")

        checkpoint_timestamp, checkpoint_event_id = _position_values(
            next_checkpoint
        )
        if next_checkpoint is not None:
            exists = connection.execute(
                """
                SELECT 1
                FROM tick_events
                WHERE symbol = ?
                  AND event_timestamp >= ?
                  AND event_timestamp < ?
                  AND event_timestamp = ?
                  AND event_id = ?;
                """,
                (
                    row["symbol"],
                    row["start_at"],
                    row["end_at"],
                    checkpoint_timestamp,
                    checkpoint_event_id,
                ),
            ).fetchone()
            if exists is None:
                raise ValueError("checkpoint is not part of the replay dataset")

        if next_state == "completed" and next_processed != row["dataset_tick_count"]:
            raise ValueError("completed session must process the full dataset")
        normalized_error = None
        if error_category is not None:
            normalized_error = _required_text(error_category, "error_category")
        if next_state == "failed" and normalized_error is None:
            raise ValueError("failed transition requires error_category")
        if next_state != "failed" and normalized_error is not None:
            raise ValueError("error_category is only valid for failed transition")

        now = datetime.now(UTC).isoformat(timespec="microseconds")
        last_batch_at = row["last_batch_at"]
        if next_processed > current_processed:
            last_batch_at = now
        completed_at = now if next_state in TERMINAL_STATES else None
        updated = connection.execute(
            """
            UPDATE replay_sessions
            SET state = ?,
                processed_ticks = ?,
                checkpoint_event_timestamp = ?,
                checkpoint_event_id = ?,
                last_batch_at = ?,
                error_category = ?,
                updated_at = ?,
                completed_at = ?
            WHERE session_id = ? AND state = ?;
            """,
            (
                next_state,
                next_processed,
                checkpoint_timestamp,
                checkpoint_event_id,
                last_batch_at,
                normalized_error,
                now,
                completed_at,
                normalized_session_id,
                normalized_expected,
            ),
        )
        if updated.rowcount != 1:
            raise ReplayTransitionConflictError(
                "replay session changed during transition"
            )

        connection.execute(
            """
            INSERT INTO replay_session_audit
            (
                session_id, actor, actor_role, action, previous_state,
                next_state, processed_ticks, checkpoint_time,
                checkpoint_event, error_category, occurred_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_session_id,
                normalized_actor,
                normalized_role,
                normalized_action,
                normalized_expected,
                next_state,
                next_processed,
                checkpoint_timestamp,
                checkpoint_event_id,
                normalized_error,
                now,
            ),
        )
        result_row = connection.execute(
            "SELECT * FROM replay_sessions WHERE session_id = ?;",
            (normalized_session_id,),
        ).fetchone()

    return _session_from_row(result_row)


def _read_step_ticks(
    connection: object,
    *,
    symbol: str,
    start_at: str,
    end_at: str,
    after_timestamp: str | None,
    after_event_id: str | None,
    limit: int,
) -> tuple[ReplayTick, ...]:
    continuation_sql = ""
    parameters: list[object] = [symbol, start_at, end_at]
    if after_timestamp is not None or after_event_id is not None:
        if after_timestamp is None or after_event_id is None:
            raise RuntimeError("stored replay checkpoint is incomplete")
        continuation_sql = """
          AND (
              event_timestamp > ?
              OR (event_timestamp = ? AND event_id > ?)
          )
        """
        parameters.extend(
            [after_timestamp, after_timestamp, after_event_id]
        )
    parameters.append(limit)
    rows = connection.execute(
        f"""
        SELECT
            event_id, event_timestamp, received_at, symbol, bid, ask, last,
            volume, flags, source_time_msc, source, event_version,
            module_version
        FROM tick_events
        WHERE symbol = ?
          AND event_timestamp >= ?
          AND event_timestamp < ?
          {continuation_sql}
        ORDER BY event_timestamp ASC, event_id ASC
        LIMIT ?;
        """,
        parameters,
    ).fetchall()
    return tuple(ReplayTick(**dict(row)) for row in rows)


def _step_result_from_command(
    connection: object,
    session_row: object,
    command_row: object,
) -> ReplayStepResult:
    ticks = _read_step_ticks(
        connection,
        symbol=session_row["symbol"],
        start_at=session_row["start_at"],
        end_at=session_row["end_at"],
        after_timestamp=command_row["previous_checkpoint_time"],
        after_event_id=command_row["previous_checkpoint_event"],
        limit=command_row["batch_tick_count"],
    )
    if len(ticks) != command_row["batch_tick_count"]:
        raise ReplayTransitionConflictError(
            "stored replay step no longer matches the dataset"
        )
    last_tick = ticks[-1]
    if (
        last_tick.event_timestamp
        != command_row["resulting_checkpoint_time"]
        or last_tick.event_id != command_row["resulting_checkpoint_event"]
    ):
        raise ReplayTransitionConflictError(
            "stored replay step checkpoint no longer matches the dataset"
        )
    return ReplayStepResult(
        session_id=session_row["session_id"],
        state=command_row["resulting_state"],
        processed_ticks=command_row["resulting_processed_ticks"],
        checkpoint_position=TickPosition(
            datetime.fromisoformat(
                command_row["resulting_checkpoint_time"]
            ),
            command_row["resulting_checkpoint_event"],
        ),
        ticks=ticks,
        idempotent_replay=True,
    )


def process_replay_step(
    *,
    session_id: str,
    actor: str,
    actor_role: str,
    idempotency_key: str,
    requested_ticks: int,
) -> ReplayStepResult:
    normalized_session_id = _required_text(session_id, "session_id")
    normalized_actor = _required_text(actor, "actor")
    normalized_role = _required_text(actor_role, "actor_role")
    normalized_key = _required_text(idempotency_key, "idempotency_key")
    if not 1 <= requested_ticks <= 1000:
        raise ValueError("requested_ticks must be between 1 and 1000")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        session_row = connection.execute(
            "SELECT * FROM replay_sessions WHERE session_id = ?;",
            (normalized_session_id,),
        ).fetchone()
        if session_row is None:
            raise ReplaySessionNotFoundError("replay session was not found")

        existing = connection.execute(
            """
            SELECT * FROM replay_step_commands
            WHERE session_id = ? AND idempotency_key = ?;
            """,
            (normalized_session_id, normalized_key),
        ).fetchone()
        if existing is not None:
            if (
                existing["actor"] != normalized_actor
                or existing["actor_role"] != normalized_role
                or existing["requested_ticks"] != requested_ticks
            ):
                raise ReplayTransitionConflictError(
                    "idempotency key was used with different step parameters"
                )
            return _step_result_from_command(
                connection,
                session_row,
                existing,
            )

        if session_row["mode"] != "step":
            raise ReplayTransitionConflictError(
                "replay session is not in step mode"
            )
        if session_row["state"] != "running":
            raise ReplayTransitionConflictError(
                "replay session must be running for a step command"
            )

        remaining = (
            session_row["dataset_tick_count"]
            - session_row["processed_ticks"]
        )
        if remaining <= 0:
            raise ReplayTransitionConflictError(
                "replay session has no remaining ticks"
            )
        batch_limit = min(requested_ticks, remaining)
        ticks = _read_step_ticks(
            connection,
            symbol=session_row["symbol"],
            start_at=session_row["start_at"],
            end_at=session_row["end_at"],
            after_timestamp=session_row["checkpoint_event_timestamp"],
            after_event_id=session_row["checkpoint_event_id"],
            limit=batch_limit,
        )
        if len(ticks) != batch_limit:
            raise ReplayTransitionConflictError(
                "replay dataset changed after session creation"
            )

        last_tick = ticks[-1]
        next_processed = session_row["processed_ticks"] + len(ticks)
        next_state = (
            "completed"
            if next_processed == session_row["dataset_tick_count"]
            else "running"
        )
        now = datetime.now(UTC).isoformat(timespec="microseconds")
        completed_at = now if next_state == "completed" else None
        updated = connection.execute(
            """
            UPDATE replay_sessions
            SET state = ?, processed_ticks = ?,
                checkpoint_event_timestamp = ?, checkpoint_event_id = ?,
                last_batch_at = ?, updated_at = ?, completed_at = ?
            WHERE session_id = ? AND state = 'running'
              AND processed_ticks = ?;
            """,
            (
                next_state,
                next_processed,
                last_tick.event_timestamp,
                last_tick.event_id,
                now,
                now,
                completed_at,
                normalized_session_id,
                session_row["processed_ticks"],
            ),
        )
        if updated.rowcount != 1:
            raise ReplayTransitionConflictError(
                "replay session changed during step processing"
            )

        connection.execute(
            """
            INSERT INTO replay_session_audit
            (
                session_id, actor, actor_role, action, previous_state,
                next_state, processed_ticks, checkpoint_time,
                checkpoint_event, occurred_at
            )
            VALUES (?, ?, ?, 'step', 'running', ?, ?, ?, ?, ?);
            """,
            (
                normalized_session_id,
                normalized_actor,
                normalized_role,
                next_state,
                next_processed,
                last_tick.event_timestamp,
                last_tick.event_id,
                now,
            ),
        )
        connection.execute(
            """
            INSERT INTO replay_step_commands
            (
                session_id, idempotency_key, actor, actor_role,
                requested_ticks, previous_processed_ticks,
                previous_checkpoint_time, previous_checkpoint_event,
                batch_tick_count, resulting_processed_ticks,
                resulting_checkpoint_time, resulting_checkpoint_event,
                resulting_state, occurred_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_session_id,
                normalized_key,
                normalized_actor,
                normalized_role,
                requested_ticks,
                session_row["processed_ticks"],
                session_row["checkpoint_event_timestamp"],
                session_row["checkpoint_event_id"],
                len(ticks),
                next_processed,
                last_tick.event_timestamp,
                last_tick.event_id,
                next_state,
                now,
            ),
        )

    return ReplayStepResult(
        session_id=normalized_session_id,
        state=next_state,
        processed_ticks=next_processed,
        checkpoint_position=TickPosition(
            datetime.fromisoformat(last_tick.event_timestamp),
            last_tick.event_id,
        ),
        ticks=ticks,
        idempotent_replay=False,
    )
