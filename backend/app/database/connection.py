import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_DIR = PROJECT_ROOT / "database"
DEFAULT_DATABASE_PATH = DATABASE_DIR / "ESAS_PLATFORM.sqlite"
_database_path = DEFAULT_DATABASE_PATH


def get_database_path() -> Path:
    return _database_path


def configure_database_path(database_path: Path | None) -> None:
    global _database_path

    _database_path = (
        DEFAULT_DATABASE_PATH
        if database_path is None
        else database_path.resolve()
    )


def get_connection() -> sqlite3.Connection:
    database_path = get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA busy_timeout = 5000;")

    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tick_events
            (
                event_id        TEXT PRIMARY KEY,
                event_type      TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                source          TEXT NOT NULL,
                event_version   TEXT NOT NULL,
                symbol          TEXT NOT NULL,
                bid             REAL NOT NULL,
                ask             REAL NOT NULL,
                last            REAL NOT NULL,
                volume          INTEGER NOT NULL,
                flags           INTEGER NOT NULL,
                source_time_msc INTEGER NOT NULL,
                module_version  TEXT NOT NULL,
                raw_event_json  TEXT NOT NULL,
                received_at     TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS loss_acknowledgements
            (
                acknowledgement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source             TEXT NOT NULL,
                symbol             TEXT NOT NULL,
                rejected_events    INTEGER NOT NULL
                    CHECK (rejected_events > 0),
                acknowledged_by    TEXT NOT NULL,
                acknowledged_at    TEXT NOT NULL
                    DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            );
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_loss_ack_latest
            ON loss_acknowledgements
            (
                source,
                symbol,
                rejected_events DESC,
                acknowledgement_id DESC
            );
            """
        )


def verify_database_writable() -> None:
    """Verify main-database writes without leaving probe data behind."""
    with get_connection() as connection:
        try:
            connection.execute("BEGIN IMMEDIATE;")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS __esas_write_probe
                (
                    probe_id INTEGER NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO __esas_write_probe (probe_id) VALUES (1);"
            )
        finally:
            connection.rollback()
