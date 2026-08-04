from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations


NOW = "2026-08-04T12:00:00.000000+00:00"
LATER = "2026-08-04T13:00:00.000000+00:00"


def migrate(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def insert_session(
    connection: sqlite3.Connection,
    *,
    session_id: str = "session-1",
    mode: str = "step",
    state: str = "created",
    start_at: str = NOW,
    end_at: str = LATER,
    dataset_tick_count: int = 2,
    processed_ticks: int = 0,
) -> None:
    connection.execute(
        """
        INSERT INTO replay_sessions
        (
            session_id, created_by, symbol, start_at, end_at, mode, state,
            replay_contract_version, quality_rule_version,
            dataset_tick_count, dataset_fingerprint,
            first_event_timestamp, first_event_id,
            last_event_timestamp, last_event_id,
            processed_ticks, created_at, updated_at
        )
        VALUES (?, 'TEST-USER', 'GOLD', ?, ?, ?, ?, '1.0', '1.0', ?,
                'sha256:test', ?, 'GOLD:1', ?, 'GOLD:2', ?, ?, ?);
        """,
        (
            session_id,
            start_at,
            end_at,
            mode,
            state,
            dataset_tick_count,
            start_at,
            end_at,
            processed_ticks,
            NOW,
            NOW,
        ),
    )


def test_replay_schema_and_indexes_are_created(
    isolated_database: Path,
) -> None:
    migrate(isolated_database)

    with sqlite3.connect(isolated_database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'index' AND name LIKE 'idx_replay_%';
                """
            )
        }
        triggers = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger';"
            )
        }

    assert {"replay_sessions", "replay_session_audit"} <= tables
    assert {
        "idx_replay_sessions_list",
        "idx_replay_sessions_state",
        "idx_replay_sessions_owner",
        "idx_replay_audit_session",
    } <= indexes
    assert {
        "prevent_replay_audit_update",
        "prevent_replay_audit_delete",
    } <= triggers


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "invalid"},
        {"state": "invalid"},
        {"start_at": LATER, "end_at": NOW},
        {"dataset_tick_count": -1},
        {"dataset_tick_count": 1, "processed_ticks": 2},
        {"processed_ticks": -1},
    ],
)
def test_replay_session_constraints_reject_invalid_rows(
    isolated_database: Path,
    overrides: dict[str, object],
) -> None:
    migrate(isolated_database)

    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            insert_session(connection, **overrides)


def test_audit_is_append_only_and_foreign_key_protected(
    isolated_database: Path,
) -> None:
    migrate(isolated_database)

    with get_connection() as connection:
        insert_session(connection)
        connection.execute(
            """
            INSERT INTO replay_session_audit
            (
                session_id, actor, actor_role, action, previous_state,
                next_state, processed_ticks, occurred_at
            )
            VALUES ('session-1', 'TEST-USER', 'operator', 'create', NULL,
                    'created', 0, ?);
            """,
            (NOW,),
        )

    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                """
                UPDATE replay_session_audit
                SET action = 'changed'
                WHERE session_id = 'session-1';
                """
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM replay_session_audit WHERE session_id = 'session-1';"
            )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                """
                INSERT INTO replay_session_audit
                (
                    session_id, actor, actor_role, action,
                    next_state, processed_ticks, occurred_at
                )
                VALUES ('missing', 'TEST-USER', 'operator', 'create',
                        'created', 0, ?);
                """,
                (NOW,),
            )


def test_session_delete_is_restricted_when_audit_exists(
    isolated_database: Path,
) -> None:
    migrate(isolated_database)

    with get_connection() as connection:
        insert_session(connection)
        connection.execute(
            """
            INSERT INTO replay_session_audit
            (
                session_id, actor, actor_role, action,
                next_state, processed_ticks, occurred_at
            )
            VALUES ('session-1', 'TEST-USER', 'operator', 'create',
                    'created', 0, ?);
            """,
            (NOW,),
        )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                "DELETE FROM replay_sessions WHERE session_id = 'session-1';"
            )


def test_migration_preserves_phase1_rows(isolated_database: Path) -> None:
    initialize_database()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO loss_acknowledgements
            (source, symbol, rejected_events, acknowledged_by)
            VALUES ('esas.mt5.bridge', 'GOLD', 5, 'TEST-USER');
            """
        )
        connection.execute(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            )
            VALUES ('GOLD:1', 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0',
                    'GOLD', 4100.0, 4100.5, 4100.25, 1, 6, 1, '1.6.0', '{}');
            """,
            (NOW,),
        )

    apply_migrations(isolated_database, application_version="0.3.0")

    with get_connection() as connection:
        tick_count = connection.execute(
            "SELECT COUNT(*) FROM tick_events;"
        ).fetchone()[0]
        acknowledgement_count = connection.execute(
            "SELECT COUNT(*) FROM loss_acknowledgements;"
        ).fetchone()[0]

    assert tick_count == 1
    assert acknowledgement_count == 1
