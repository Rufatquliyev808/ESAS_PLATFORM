from pathlib import Path
import sqlite3

import pytest

from backend.app.database.connection import (
    DEFAULT_DATABASE_PATH,
    get_connection,
    initialize_database,
)
from backend.app.database.migration_runner import (
    MIGRATIONS_DIR,
    apply_migrations,
)


def insert_tick(event_id: str = "GOLD:1") -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            )
            VALUES (?, 'TICK_RECEIVED', '2026-08-03T08:00:00.000000+00:00',
                    'esas.mt5.bridge', '1.0', 'GOLD', 4100.0, 4100.5,
                    4100.25, 1, 6, 1785744000000, '1.6.0', '{}');
            """,
            (event_id,),
        )


def raw_tick_snapshot(database_path: Path) -> list[tuple[object, ...]]:
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            """
            SELECT event_id, event_timestamp, symbol, raw_event_json
            FROM tick_events
            ORDER BY event_id;
            """
        ).fetchall()


def test_migration_adds_versioned_replay_index_without_changing_ticks(
    isolated_database: Path,
) -> None:
    initialize_database()
    insert_tick()
    before = raw_tick_snapshot(isolated_database)

    result = apply_migrations(
        isolated_database,
        application_version="0.3.0",
    )

    assert result.applied_versions == ("0001", "0002", "0003")
    assert result.current_version == "0003"
    assert raw_tick_snapshot(isolated_database) == before

    with sqlite3.connect(isolated_database) as connection:
        migration = connection.execute(
            """
            SELECT version, description, checksum, application_ver
            FROM schema_migrations
            WHERE version = '0001';
            """
        ).fetchone()
        indexes = {
            row[1] for row in connection.execute("PRAGMA index_list(tick_events);")
        }
        query_plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT event_id
            FROM tick_events
            WHERE symbol = ?
              AND event_timestamp >= ?
              AND event_timestamp < ?
            ORDER BY event_timestamp, event_id;
            """,
            (
                "GOLD",
                "2026-08-03T00:00:00.000000+00:00",
                "2026-08-04T00:00:00.000000+00:00",
            ),
        ).fetchall()

    assert migration[0] == "0001"
    assert migration[1] == "tick replay index"
    assert len(migration[2]) == 64
    assert migration[3] == "0.3.0"
    assert "idx_tick_events_replay" in indexes
    assert any("idx_tick_events_replay" in row[3] for row in query_plan)


def test_second_migration_run_is_a_safe_no_op(
    isolated_database: Path,
) -> None:
    initialize_database()
    first = apply_migrations(isolated_database, application_version="0.3.0")
    second = apply_migrations(isolated_database, application_version="0.3.0")

    assert first.applied_versions == ("0001", "0002", "0003")
    assert second.applied_versions == ()
    with sqlite3.connect(isolated_database) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations;"
        ).fetchone()[0]
    assert count == 3


def test_changed_migration_checksum_fails_closed(
    isolated_database: Path,
    tmp_path: Path,
) -> None:
    initialize_database()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    original = MIGRATIONS_DIR / "0001_tick_replay_index.sql"
    copied = migrations_dir / original.name
    copied.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
    apply_migrations(
        isolated_database,
        application_version="0.3.0",
        migrations_dir=migrations_dir,
    )

    copied.write_text(
        original.read_text(encoding="utf-8") + "\n-- changed\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        apply_migrations(
            isolated_database,
            application_version="0.3.0",
            migrations_dir=migrations_dir,
        )


def test_failed_migration_rolls_back_schema_and_version_record(
    isolated_database: Path,
    tmp_path: Path,
) -> None:
    initialize_database()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "0001_broken.sql").write_text(
        "CREATE TABLE should_rollback (id INTEGER);\n"
        "CREATE TABLE tick_events (id INTEGER);\n",
        encoding="utf-8",
    )

    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(
            isolated_database,
            application_version="0.3.0",
            migrations_dir=migrations_dir,
        )

    with sqlite3.connect(isolated_database) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            )
        }
    assert "should_rollback" not in table_names
    assert "schema_migrations" not in table_names


def test_destructive_migration_is_rejected_before_database_change(
    isolated_database: Path,
    tmp_path: Path,
) -> None:
    initialize_database()
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "0001_unsafe.sql").write_text(
        "DROP TABLE tick_events;\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="destructive"):
        apply_migrations(
            isolated_database,
            application_version="0.3.0",
            migrations_dir=migrations_dir,
        )

    assert "tick_events" in {
        row[0]
        for row in sqlite3.connect(isolated_database).execute(
            "SELECT name FROM sqlite_master WHERE type = 'table';"
        )
    }


def test_production_database_requires_explicit_permission() -> None:
    with pytest.raises(PermissionError, match="explicit"):
        apply_migrations(DEFAULT_DATABASE_PATH, application_version="0.3.0")
