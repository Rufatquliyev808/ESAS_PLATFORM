from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.app.database.connection import configure_database_path


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path) -> Iterator[Path]:
    database_path = tmp_path / "ESAS_PLATFORM_TEST.sqlite"
    configure_database_path(database_path)

    yield database_path

    configure_database_path(None)
