from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.app.database.connection import DEFAULT_DATABASE_PATH
from backend.app.database.migration_runner import apply_migrations


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup and migrate the ESAS production database.")
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument("--backup-dir", type=Path, default=Path(".runtime/phase2-migration"))
    args = parser.parse_args()
    if not args.allow_production:
        raise SystemExit("Refusing production migration without --allow-production")

    args.backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    backup_path = args.backup_dir / f"ESAS_PLATFORM-before-phase2-{stamp}.sqlite"
    with sqlite3.connect(DEFAULT_DATABASE_PATH) as source:
        if source.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SystemExit("Source database quick_check failed")
        with sqlite3.connect(backup_path) as target:
            source.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise SystemExit("Backup quick_check failed")

    result = apply_migrations(
        DEFAULT_DATABASE_PATH,
        application_version="0.3.0",
        allow_production=True,
    )
    with sqlite3.connect(DEFAULT_DATABASE_PATH) as connection:
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SystemExit("Migrated database quick_check failed")
    print(f"Backup: {backup_path}")
    print(f"Applied: {', '.join(result.applied_versions) or 'none'}")
    print(f"Current schema: {result.current_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
