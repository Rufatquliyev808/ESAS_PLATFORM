from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import re
import sqlite3

from backend.app.database.connection import DEFAULT_DATABASE_PATH


MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATION_NAME = re.compile(
    r"^(?P<version>[0-9]{4})_(?P<description>[a-z0-9_]+)\.sql$"
)


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    checksum: str
    sql: str


@dataclass(frozen=True)
class MigrationResult:
    applied_versions: tuple[str, ...]
    current_version: str | None


def _load_migrations(migrations_dir: Path) -> tuple[Migration, ...]:
    migrations: list[Migration] = []
    seen_versions: set[str] = set()

    for migration_path in sorted(migrations_dir.glob("*.sql")):
        match = MIGRATION_NAME.fullmatch(migration_path.name)
        if match is None:
            raise ValueError(
                f"invalid migration filename: {migration_path.name}"
            )

        version = match.group("version")
        if version in seen_versions:
            raise ValueError(f"duplicate migration version: {version}")

        sql = migration_path.read_text(encoding="utf-8")
        if not sql.strip():
            raise ValueError(f"empty migration: {migration_path.name}")

        seen_versions.add(version)
        migrations.append(
            Migration(
                version=version,
                description=match.group("description").replace("_", " "),
                checksum=sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )

    return tuple(migrations)


def _statements(sql: str) -> tuple[str, ...]:
    statements: list[str] = []
    pending = ""

    for line in sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            if statement:
                statements.append(statement)
            pending = ""

    if pending.strip():
        without_comments = re.sub(
            r"--.*?$|/\*.*?\*/",
            " ",
            pending,
            flags=re.M | re.S,
        )
        if without_comments.strip():
            raise ValueError("migration contains an incomplete SQL statement")

    return tuple(statements)


def _refuse_unsafe_sql(migration: Migration) -> None:
    for statement in _statements(migration.sql):
        normalized = re.sub(
            r"--.*?$|/\*.*?\*/",
            " ",
            statement,
            flags=re.M | re.S,
        ).strip()
        if re.match(
            r"^(DROP|DELETE|UPDATE|REPLACE|TRUNCATE|VACUUM)\b",
            normalized,
            re.I,
        ):
            raise ValueError(
                f"migration {migration.version} contains a destructive statement"
            )


def apply_migrations(
    database_path: Path,
    *,
    application_version: str,
    migrations_dir: Path = MIGRATIONS_DIR,
    allow_production: bool = False,
) -> MigrationResult:
    resolved_path = database_path.resolve()
    if resolved_path == DEFAULT_DATABASE_PATH.resolve() and not allow_production:
        raise PermissionError(
            "production migration requires explicit allow_production=True"
        )
    if not resolved_path.is_file():
        raise FileNotFoundError(f"database does not exist: {resolved_path}")
    if not application_version.strip():
        raise ValueError("application_version must not be empty")

    migrations = _load_migrations(migrations_dir.resolve())
    if not migrations:
        raise ValueError("no migrations found")
    for migration in migrations:
        _refuse_unsafe_sql(migration)

    connection = sqlite3.connect(resolved_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    applied_versions: list[str] = []
    try:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.execute("PRAGMA busy_timeout = 5000;")
        connection.execute("BEGIN EXCLUSIVE;")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations
            (
                version         TEXT PRIMARY KEY,
                description     TEXT NOT NULL,
                checksum        TEXT NOT NULL,
                applied_at      TEXT NOT NULL,
                application_ver TEXT NOT NULL
            );
            """
        )

        known = {migration.version: migration for migration in migrations}
        existing_rows = connection.execute(
            """
            SELECT version, checksum
            FROM schema_migrations
            ORDER BY version ASC;
            """
        ).fetchall()
        for row in existing_rows:
            migration = known.get(row["version"])
            if migration is None:
                raise RuntimeError(
                    f"applied migration is missing locally: {row['version']}"
                )
            if row["checksum"] != migration.checksum:
                raise RuntimeError(
                    f"migration checksum mismatch: {row['version']}"
                )

        existing_versions = {row["version"] for row in existing_rows}
        applied_at = datetime.now(UTC).isoformat(timespec="microseconds")
        for migration in migrations:
            if migration.version in existing_versions:
                continue

            for statement in _statements(migration.sql):
                connection.execute(statement)
            connection.execute(
                """
                INSERT INTO schema_migrations
                (version, description, checksum, applied_at, application_ver)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    migration.version,
                    migration.description,
                    migration.checksum,
                    applied_at,
                    application_version.strip(),
                ),
            )
            applied_versions.append(migration.version)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    current_version = migrations[-1].version if migrations else None
    return MigrationResult(
        applied_versions=tuple(applied_versions),
        current_version=current_version,
    )
