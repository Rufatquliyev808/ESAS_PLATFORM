from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    ReplayTransitionConflictError,
    create_replay_session,
    transition_replay_session,
)
from backend.app.database.tick_replay_repository import TickPosition


BASE_TIME = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)


def prepare_session(database_path: Path) -> object:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    with get_connection() as connection:
        for index in range(1, 4):
            timestamp = BASE_TIME + timedelta(milliseconds=index)
            connection.execute(
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
                (f"GOLD:{index}", timestamp.isoformat(timespec="microseconds"), index),
            )
    return create_replay_session(
        created_by="TEST-USER",
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        mode="step",
    )


def transition(session: object, action: str, expected_state: str, **changes: object) -> object:
    return transition_replay_session(
        session_id=session.session_id,
        actor="TEST-USER",
        actor_role="operator",
        action=action,
        expected_state=expected_state,
        **changes,
    )


def checkpoint(index: int) -> TickPosition:
    return TickPosition(
        BASE_TIME + timedelta(milliseconds=index),
        f"GOLD:{index}",
    )


def test_legal_lifecycle_transitions_are_audited(isolated_database: Path) -> None:
    session = prepare_session(isolated_database)

    session = transition(session, "start", "created")
    session = transition(
        session,
        "pause",
        "running",
        processed_ticks=1,
        checkpoint_position=checkpoint(1),
    )
    session = transition(session, "resume", "paused")
    session = transition(session, "interrupt", "running")
    session = transition(session, "resume", "interrupted")
    session = transition(session, "cancel", "running")

    assert session.state == "cancelled"
    assert session.processed_ticks == 1
    assert session.checkpoint_position == checkpoint(1)
    assert session.completed_at is not None
    with get_connection() as connection:
        audit = connection.execute(
            """
            SELECT action, previous_state, next_state
            FROM replay_session_audit
            WHERE session_id = ?
            ORDER BY audit_id;
            """,
            (session.session_id,),
        ).fetchall()
    assert [tuple(row) for row in audit] == [
        ("create", None, "created"),
        ("start", "created", "running"),
        ("pause", "running", "paused"),
        ("resume", "paused", "running"),
        ("interrupt", "running", "interrupted"),
        ("resume", "interrupted", "running"),
        ("cancel", "running", "cancelled"),
    ]


def test_completed_transition_requires_full_progress(isolated_database: Path) -> None:
    session = prepare_session(isolated_database)
    session = transition(session, "start", "created")

    with pytest.raises(ValueError, match="full dataset"):
        transition(
            session,
            "complete",
            "running",
            processed_ticks=2,
            checkpoint_position=checkpoint(2),
        )

    completed = transition(
        session,
        "complete",
        "running",
        processed_ticks=3,
        checkpoint_position=checkpoint(3),
    )
    assert completed.state == "completed"
    assert completed.processed_ticks == 3
    assert completed.completed_at is not None


def test_terminal_and_illegal_transitions_do_not_write_audit(
    isolated_database: Path,
) -> None:
    session = prepare_session(isolated_database)
    session = transition(session, "cancel", "created")

    with pytest.raises(ReplayTransitionConflictError):
        transition(session, "resume", "cancelled")
    with get_connection() as connection:
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM replay_session_audit WHERE session_id = ?;",
            (session.session_id,),
        ).fetchone()[0]
    assert audit_count == 2


def test_expected_state_conflict_is_fail_closed(isolated_database: Path) -> None:
    session = prepare_session(isolated_database)
    running = transition(session, "start", "created")

    with pytest.raises(ReplayTransitionConflictError, match="expected_state"):
        transition(running, "cancel", "created")

    with get_connection() as connection:
        state = connection.execute(
            "SELECT state FROM replay_sessions WHERE session_id = ?;",
            (session.session_id,),
        ).fetchone()[0]
    assert state == "running"


@pytest.mark.parametrize(
    ("processed", "position", "message"),
    [
        (4, checkpoint(3), "exceeds"),
        (1, None, "requires a checkpoint"),
        (1, TickPosition(BASE_TIME, "missing"), "not part"),
    ],
)
def test_invalid_progress_is_rejected(
    isolated_database: Path,
    processed: int,
    position: TickPosition | None,
    message: str,
) -> None:
    session = prepare_session(isolated_database)
    session = transition(session, "start", "created")

    with pytest.raises(ValueError, match=message):
        transition(
            session,
            "pause",
            "running",
            processed_ticks=processed,
            checkpoint_position=position,
        )


def test_progress_and_checkpoint_never_move_backwards(
    isolated_database: Path,
) -> None:
    session = prepare_session(isolated_database)
    session = transition(session, "start", "created")
    session = transition(
        session,
        "pause",
        "running",
        processed_ticks=2,
        checkpoint_position=checkpoint(2),
    )
    session = transition(session, "resume", "paused")

    with pytest.raises(ValueError, match="processed_ticks"):
        transition(
            session,
            "pause",
            "running",
            processed_ticks=1,
            checkpoint_position=checkpoint(1),
        )
    with pytest.raises(ValueError, match="without progress"):
        transition(
            session,
            "pause",
            "running",
            processed_ticks=2,
            checkpoint_position=checkpoint(3),
        )


def test_failed_transition_requires_safe_error_category(
    isolated_database: Path,
) -> None:
    session = prepare_session(isolated_database)
    session = transition(session, "start", "created")

    with pytest.raises(ValueError, match="error_category"):
        transition(session, "fail", "running")
    failed = transition(
        session,
        "fail",
        "running",
        error_category="dataset_changed",
    )
    assert failed.state == "failed"
    assert failed.error_category == "dataset_changed"


def test_audit_failure_rolls_back_state_and_checkpoint(
    isolated_database: Path,
) -> None:
    session = prepare_session(isolated_database)
    session = transition(session, "start", "created")
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_transition_audit
            BEFORE INSERT ON replay_session_audit
            WHEN NEW.action = 'pause'
            BEGIN
                SELECT RAISE(ABORT, 'forced transition audit failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced transition"):
        transition(
            session,
            "pause",
            "running",
            processed_ticks=1,
            checkpoint_position=checkpoint(1),
        )

    with get_connection() as connection:
        stored = connection.execute(
            """
            SELECT state, processed_ticks, checkpoint_event_id
            FROM replay_sessions WHERE session_id = ?;
            """,
            (session.session_id,),
        ).fetchone()
    assert tuple(stored) == ("running", 0, None)


def test_transition_preserves_immutable_session_fields(
    isolated_database: Path,
) -> None:
    session = prepare_session(isolated_database)
    with get_connection() as connection:
        before = connection.execute(
            """
            SELECT created_by, symbol, start_at, end_at, mode,
                   replay_contract_version, quality_rule_version,
                   dataset_tick_count, dataset_fingerprint
            FROM replay_sessions WHERE session_id = ?;
            """,
            (session.session_id,),
        ).fetchone()

    transition(session, "start", "created")

    with get_connection() as connection:
        after = connection.execute(
            """
            SELECT created_by, symbol, start_at, end_at, mode,
                   replay_contract_version, quality_rule_version,
                   dataset_tick_count, dataset_fingerprint
            FROM replay_sessions WHERE session_id = ?;
            """,
            (session.session_id,),
        ).fetchone()
    assert tuple(after) == tuple(before)
