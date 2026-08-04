from dataclasses import dataclass
from datetime import UTC, datetime
import secrets

from backend.app.database.connection import get_connection
from backend.app.database.tick_replay_repository import TickPosition
from backend.app.replay.dataset_snapshot import (
    ReplayDatasetSnapshot,
    create_dataset_snapshot,
)


REPLAY_CONTRACT_VERSION = "1.0"
QUALITY_RULE_VERSION = "1.0"
REPLAY_MODES = frozenset({"step", "max_speed"})


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
    created_at: str
    updated_at: str
    completed_at: str | None


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
        created_at=now,
        updated_at=now,
        completed_at=completed_at,
    )
