from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    ReplayTransitionConflictError,
    create_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)


BASE_TIME = datetime(2026, 8, 4, 14, 0, tzinfo=UTC)


def prepare_session(database_path: Path, *, tick_count: int = 2005, mode: str = "max_speed") -> object:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    rows = []
    for index in range(1, tick_count + 1):
        timestamp = BASE_TIME + timedelta(microseconds=index)
        rows.append(
            (
                f"GOLD:{index:04d}",
                timestamp.isoformat(timespec="microseconds"),
                index,
            )
        )
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source,
                event_version, symbol, bid, ask, last, volume, flags,
                source_time_msc, module_version, raw_event_json
            )
            VALUES (?, 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0',
                    'GOLD', 4100.0, 4100.5, 4100.25, 1, 6, ?,
                    '1.6.0', '{}');
            """,
            rows,
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


def run(session: object, **limits: object):
    return run_max_speed_replay(
        session_id=session.session_id,
        actor="REPLAY-WORKER",
        actor_role="worker",
        **limits,
    )


def test_max_speed_completes_in_bounded_batches(isolated_database: Path) -> None:
    session = prepare_session(isolated_database)
    result = run(session, batch_size=1000)

    assert result.state == "completed"
    assert result.batches_processed == 3
    assert result.ticks_processed == 2005
    assert result.total_processed_ticks == 2005
    assert result.checkpoint_position.event_id == "GOLD:2005"
    with get_connection() as connection:
        audit = connection.execute(
            """
            SELECT processed_ticks, checkpoint_event, next_state
            FROM replay_session_audit
            WHERE session_id = ? AND action = 'max_speed_batch'
            ORDER BY audit_id;
            """,
            (session.session_id,),
        ).fetchall()
    assert [tuple(row) for row in audit] == [
        (1000, "GOLD:1000", "running"),
        (2000, "GOLD:2000", "running"),
        (2005, "GOLD:2005", "completed"),
    ]


def test_restart_continues_after_last_checkpoint(isolated_database: Path) -> None:
    session = prepare_session(isolated_database)
    first_run = run(session, batch_size=700, max_batches=1)
    resumed_run = run(session, batch_size=700)

    assert first_run.total_processed_ticks == 700
    assert first_run.state == "running"
    assert resumed_run.ticks_processed == 1305
    assert resumed_run.total_processed_ticks == 2005
    assert resumed_run.state == "completed"
    with get_connection() as connection:
        checkpoints = connection.execute(
            """
            SELECT checkpoint_event FROM replay_session_audit
            WHERE session_id = ? AND action = 'max_speed_batch'
            ORDER BY audit_id;
            """,
            (session.session_id,),
        ).fetchall()
    assert [row[0] for row in checkpoints] == [
        "GOLD:0700",
        "GOLD:1400",
        "GOLD:2005",
    ]


def test_pause_stops_until_session_is_resumed(isolated_database: Path) -> None:
    session = prepare_session(isolated_database, tick_count=12)
    first = run(session, batch_size=5, max_batches=1)
    transition_replay_session(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        action="pause",
        expected_state="running",
    )

    stopped = run(session, batch_size=5)
    assert stopped.state == "paused"
    assert stopped.batches_processed == 0
    assert stopped.total_processed_ticks == first.total_processed_ticks == 5

    transition_replay_session(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        action="resume",
        expected_state="paused",
    )
    completed = run(session, batch_size=5)
    assert completed.state == "completed"
    assert completed.ticks_processed == 7


@pytest.mark.parametrize("action", ["cancel", "interrupt"])
def test_stop_signal_prevents_the_next_batch(
    isolated_database: Path,
    action: str,
) -> None:
    session = prepare_session(isolated_database, tick_count=12)
    first = run(session, batch_size=5, max_batches=1)
    transition_replay_session(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        action=action,
        expected_state="running",
    )

    stopped = run(session, batch_size=5)
    expected_state = "cancelled" if action == "cancel" else "interrupted"
    assert stopped.state == expected_state
    assert stopped.batches_processed == 0
    assert stopped.total_processed_ticks == first.total_processed_ticks == 5
    assert stopped.checkpoint_position == first.checkpoint_position


def test_wrong_mode_and_invalid_limits_are_rejected(isolated_database: Path) -> None:
    session = prepare_session(isolated_database, tick_count=5, mode="step")
    with pytest.raises(ReplayTransitionConflictError, match="max_speed"):
        run(session)
    with pytest.raises(ValueError, match="between 1 and 1000"):
        run_max_speed_replay(
            session_id=session.session_id,
            actor="REPLAY-WORKER",
            actor_role="worker",
            batch_size=1001,
        )
    with pytest.raises(ValueError, match="positive"):
        run_max_speed_replay(
            session_id=session.session_id,
            actor="REPLAY-WORKER",
            actor_role="worker",
            max_batches=0,
        )


def test_changed_dataset_preserves_last_successful_checkpoint(isolated_database: Path) -> None:
    session = prepare_session(isolated_database, tick_count=12)
    first = run(session, batch_size=5, max_batches=1)
    with get_connection() as connection:
        connection.execute(
            "DELETE FROM tick_events WHERE event_id = 'GOLD:0008';"
        )
        replacement_time = BASE_TIME + timedelta(microseconds=8)
        connection.execute(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source,
                event_version, symbol, bid, ask, last, volume, flags,
                source_time_msc, module_version, raw_event_json
            )
            VALUES ('GOLD:0008-replaced', 'TICK_RECEIVED', ?,
                    'esas.mt5.bridge', '1.0', 'GOLD', 4100.0, 4100.5,
                    4100.25, 1, 6, 8, '1.6.0', '{}');
            """,
            (replacement_time.isoformat(timespec="microseconds"),),
        )

    with pytest.raises(ReplayTransitionConflictError, match="dataset changed"):
        run(session, batch_size=10)
    with get_connection() as connection:
        stored = connection.execute(
            """
            SELECT state, processed_ticks, checkpoint_event_id
            FROM replay_sessions WHERE session_id = ?;
            """,
            (session.session_id,),
        ).fetchone()
    assert tuple(stored) == ("running", 5, "GOLD:0005")
    assert first.total_processed_ticks == 5


def test_batch_audit_failure_rolls_back_checkpoint(isolated_database: Path) -> None:
    session = prepare_session(isolated_database, tick_count=5)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_max_speed_audit
            BEFORE INSERT ON replay_session_audit
            WHEN NEW.action = 'max_speed_batch'
            BEGIN
                SELECT RAISE(ABORT, 'forced max speed audit failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced max speed"):
        run(session)
    with get_connection() as connection:
        stored = connection.execute(
            """
            SELECT state, processed_ticks, checkpoint_event_id
            FROM replay_sessions WHERE session_id = ?;
            """,
            (session.session_id,),
        ).fetchone()
    assert tuple(stored) == ("running", 0, None)


def test_completed_session_is_not_processed_again(isolated_database: Path) -> None:
    session = prepare_session(isolated_database, tick_count=3)
    completed = run(session)
    repeated = run(session)

    assert completed.state == repeated.state == "completed"
    assert repeated.batches_processed == 0
    assert repeated.ticks_processed == 0
    assert repeated.total_processed_ticks == 3
