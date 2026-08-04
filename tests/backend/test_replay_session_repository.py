from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import create_replay_session
from backend.app.database.tick_replay_repository import TickPosition


BASE_TIME = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)


def prepare_schema(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def insert_tick(event_id: str, timestamp: datetime) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            )
            VALUES (?, 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0', 'GOLD',
                    4100.0, 4100.5, 4100.25, 1, 6, 1785744000000,
                    '1.6.0', '{}');
            """,
            (event_id, timestamp.isoformat(timespec="microseconds")),
        )


def create_default_session() -> object:
    return create_replay_session(
        created_by="TEST-USER",
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        mode="step",
        snapshot_batch_size=1,
    )


def test_session_and_initial_audit_are_created_atomically(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)
    insert_tick("GOLD:2", BASE_TIME)
    insert_tick("GOLD:1", BASE_TIME)

    session = create_default_session()

    assert session.session_id.startswith("rps_")
    assert session.state == "created"
    assert session.dataset_tick_count == 2
    assert session.first_position == TickPosition(BASE_TIME, "GOLD:1")
    assert session.last_position == TickPosition(BASE_TIME, "GOLD:2")
    assert session.processed_ticks == 0
    assert session.completed_at is None

    with get_connection() as connection:
        stored = connection.execute(
            "SELECT * FROM replay_sessions WHERE session_id = ?;",
            (session.session_id,),
        ).fetchone()
        audit = connection.execute(
            "SELECT * FROM replay_session_audit WHERE session_id = ?;",
            (session.session_id,),
        ).fetchall()

    assert stored["created_by"] == "TEST-USER"
    assert stored["symbol"] == "GOLD"
    assert stored["mode"] == "step"
    assert stored["state"] == "created"
    assert stored["dataset_tick_count"] == 2
    assert stored["dataset_fingerprint"] == session.dataset_fingerprint
    assert len(audit) == 1
    assert audit[0]["actor"] == "TEST-USER"
    assert audit[0]["actor_role"] == "operator"
    assert audit[0]["action"] == "create"
    assert audit[0]["previous_state"] is None
    assert audit[0]["next_state"] == "created"


def test_empty_dataset_is_created_as_completed(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)

    session = create_default_session()

    assert session.state == "completed"
    assert session.dataset_tick_count == 0
    assert session.first_position is None
    assert session.last_position is None
    assert session.completed_at is not None
    with get_connection() as connection:
        audit = connection.execute(
            """
            SELECT next_state FROM replay_session_audit
            WHERE session_id = ?;
            """,
            (session.session_id,),
        ).fetchone()
    assert audit["next_state"] == "completed"


def test_session_identifiers_are_unique_and_opaque(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)

    first = create_default_session()
    second = create_default_session()

    assert first.session_id != second.session_id
    assert len(first.session_id) >= 32
    assert len(second.session_id) >= 32


def test_audit_failure_rolls_back_session_insert(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_test_audit
            BEFORE INSERT ON replay_session_audit
            BEGIN
                SELECT RAISE(ABORT, 'forced audit failure');
            END;
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced audit failure"):
        create_default_session()

    with get_connection() as connection:
        session_count = connection.execute(
            "SELECT COUNT(*) FROM replay_sessions;"
        ).fetchone()[0]
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM replay_session_audit;"
        ).fetchone()[0]
    assert session_count == 0
    assert audit_count == 0


def test_session_creation_does_not_change_raw_ticks(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)
    insert_tick("GOLD:1", BASE_TIME)
    with get_connection() as connection:
        before = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events;"
        ).fetchall()

    create_default_session()

    with get_connection() as connection:
        after = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events;"
        ).fetchall()
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("created_by", " ", "created_by"),
        ("actor_role", " ", "actor_role"),
        ("symbol", " ", "symbol"),
        ("mode", "invalid", "mode"),
        ("replay_contract_version", " ", "replay_contract_version"),
        ("quality_rule_version", " ", "quality_rule_version"),
    ],
)
def test_session_creation_validates_inputs(
    isolated_database: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    prepare_schema(isolated_database)
    arguments = {
        "created_by": "TEST-USER",
        "actor_role": "operator",
        "symbol": "GOLD",
        "start_at": BASE_TIME,
        "end_at": BASE_TIME + timedelta(seconds=1),
        "mode": "step",
        "replay_contract_version": "1.0",
        "quality_rule_version": "1.0",
    }
    arguments[field] = value

    with pytest.raises(ValueError, match=message):
        create_replay_session(**arguments)
