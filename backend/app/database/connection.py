import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "ESAS_PLATFORM.sqlite"


def get_connection() -> sqlite3.Connection:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
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