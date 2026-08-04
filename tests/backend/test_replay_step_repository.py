from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    ReplayTransitionConflictError,
    create_replay_session,
    process_replay_step,
    transition_replay_session,
)


BASE_TIME = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def prepare_running_session(database_path: Path, *, mode: str = "step") -> object:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    with get_connection() as connection:
        for index in range(1, 6):
            timestamp = BASE_TIME + timedelta(milliseconds=index)
            connection.execute(
                """
                INSERT OR IGNORE INTO tick_events
                (
                    event_id, event_type, event_timestamp, source,
                    event_version, symbol, bid, ask, last, volume, flags,
                    source_time_msc, module_version, raw_event_json
                )
                VALUES (?, 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0',
                        'GOLD', 4100.0, 4100.5, 4100.25, 1, 6, ?,
                        '1.6.0', '{}');
                """,
                (f"GOLD:{index}", timestamp.isoformat(timespec="microseconds"), index),
            )
    session = create_replay_session(
        created_by="TEST-USER",
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        mode=mode,
    )
    return transition_replay_session(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        action="start",
        expected_state="created",
    )


def step(session: object, key: str, count: int):
    return process_replay_step(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        idempotency_key=key,
        requested_ticks=count,
    )


def test_steps_are_ordered_without_gaps_or_duplicates(isolated_database: Path) -> None:
    session = prepare_running_session(isolated_database)

    first = step(session, "step-1", 2)
    second = step(session, "step-2", 2)
    final = step(session, "step-3", 2)

    ids = [tick.event_id for result in (first, second, final) for tick in result.ticks]
    assert ids == [f"GOLD:{index}" for index in range(1, 6)]
    assert first.processed_ticks == 2
    assert second.processed_ticks == 4
    assert final.processed_ticks == 5
    assert final.state == "completed"


def test_same_idempotency_key_returns_same_result_once(isolated_database: Path) -> None:
    session = prepare_running_session(isolated_database)
    first = step(session, "same-command", 3)
    repeated = step(session, "same-command", 3)

    assert repeated.idempotent_replay is True
    assert repeated.ticks == first.ticks
    assert repeated.processed_ticks == first.processed_ticks
    with get_connection() as connection:
        command_count = connection.execute(
            "SELECT COUNT(*) FROM replay_step_commands WHERE session_id = ?;",
            (session.session_id,),
        ).fetchone()[0]
        step_audit_count = connection.execute(
            """
            SELECT COUNT(*) FROM replay_session_audit
            WHERE session_id = ? AND action = 'step';
            """,
            (session.session_id,),
        ).fetchone()[0]
    assert (command_count, step_audit_count) == (1, 1)


def test_reused_key_with_different_parameters_is_rejected(isolated_database: Path) -> None:
    session = prepare_running_session(isolated_database)
    step(session, "same-command", 2)

    with pytest.raises(ReplayTransitionConflictError, match="different"):
        step(session, "same-command", 3)


@pytest.mark.parametrize("count", [0, 1001])
def test_step_limit_is_enforced(isolated_database: Path, count: int) -> None:
    session = prepare_running_session(isolated_database)
    with pytest.raises(ValueError, match="between 1 and 1000"):
        step(session, "invalid", count)


def test_only_running_step_sessions_can_advance(isolated_database: Path) -> None:
    session = prepare_running_session(isolated_database, mode="max_speed")
    with pytest.raises(ReplayTransitionConflictError, match="step mode"):
        step(session, "wrong-mode", 1)

    step_session = prepare_running_session(isolated_database)
    transition_replay_session(
        session_id=step_session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        action="pause",
        expected_state="running",
    )
    with pytest.raises(ReplayTransitionConflictError, match="running"):
        step(step_session, "paused", 1)


def test_audit_failure_rolls_back_step_and_idempotency(isolated_database: Path) -> None:
    session = prepare_running_session(isolated_database)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_step_audit
            BEFORE INSERT ON replay_session_audit
            WHEN NEW.action = 'step'
            BEGIN
                SELECT RAISE(ABORT, 'forced step audit failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced step"):
        step(session, "rollback", 2)

    with get_connection() as connection:
        stored = connection.execute(
            """
            SELECT state, processed_ticks, checkpoint_event_id
            FROM replay_sessions WHERE session_id = ?;
            """,
            (session.session_id,),
        ).fetchone()
        command_count = connection.execute(
            "SELECT COUNT(*) FROM replay_step_commands;"
        ).fetchone()[0]
    assert tuple(stored) == ("running", 0, None)
    assert command_count == 0


def test_step_command_rows_are_append_only(isolated_database: Path) -> None:
    session = prepare_running_session(isolated_database)
    step(session, "immutable", 1)

    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE replay_step_commands SET requested_ticks = 2;"
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute("DELETE FROM replay_step_commands;")
