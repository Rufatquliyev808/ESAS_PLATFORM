from collections.abc import Iterator
from pathlib import Path
import os

import pytest

from backend.app.database.connection import configure_database_path
from backend.app.auth import reset_login_attempts


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path) -> Iterator[Path]:
    os.environ["ESAS_USER_CODE"] = "TEST-USER"
    os.environ["ESAS_USER_PASSWORD"] = "test-password-123"
    os.environ["ESAS_SESSION_SECRET"] = "test-session-secret-at-least-32-chars"
    reset_login_attempts()
    database_path = tmp_path / "ESAS_PLATFORM_TEST.sqlite"
    configure_database_path(database_path)

    yield database_path

    reset_login_attempts()
    configure_database_path(None)
