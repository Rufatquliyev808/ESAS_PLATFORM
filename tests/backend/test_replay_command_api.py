from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import create_replay_session
from backend.app.main import app


BASE_TIME = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)


def prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_tick(event_id: str, offset_ms: int) -> None:
    timestamp = BASE_TIME + timedelta(milliseconds=offset_ms)
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
                    1, 2, 1.5, 1, 6, ?, '1.6.0', '{"raw":true}');
            """,
            (event_id, timestamp.isoformat(timespec="microseconds"), offset_ms),
        )


def create(owner: str = "TEST-USER"):
    return create_replay_session(
        created_by=owner,
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(seconds=1),
        mode="step",
    )


def command_headers(auth: dict[str, str], key: str) -> dict[str, str]:
    return {**auth, "Idempotency-Key": key}


def test_command_requires_authentication_and_idempotency_key(
    isolated_database: Path,
) -> None:
    prepare(isolated_database)
    seed_tick("GOLD:1", 1)
    session = create()
    with TestClient(app) as client:
        unauthenticated = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/commands",
            json={"command": "start", "expected_state_version": 0},
            headers={"Idempotency-Key": "start-1"},
        )
        missing_key = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/commands",
            json={"command": "start", "expected_state_version": 0},
            headers=login(client),
        )
    assert unauthenticated.status_code == 401
    assert missing_key.status_code == 422


def test_owner_can_start_and_step_with_atomic_audit_and_raw_preservation(
    isolated_database: Path,
) -> None:
    prepare(isolated_database)
    seed_tick("GOLD:1", 1)
    seed_tick("GOLD:2", 2)
    session = create()
    with get_connection() as connection:
        raw_before = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id;"
        ).fetchall()
    with TestClient(app) as client:
        auth = login(client)
        started = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/commands",
            json={"command": "start", "expected_state_version": 0},
            headers=command_headers(auth, "start-1"),
        )
        stepped = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/commands",
            json={
                "command": "step",
                "expected_state_version": 1,
                "requested_ticks": 2,
            },
            headers=command_headers(auth, "step-1"),
        )
    assert started.status_code == 200
    assert started.json()["data"]["state_version"] == 1
    assert stepped.status_code == 200
    assert stepped.json()["data"]["state"] == "completed"
    assert stepped.json()["data"]["state_version"] == 2
    assert stepped.json()["data"]["processed_ticks"] == 2
    with get_connection() as connection:
        raw_after = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id;"
        ).fetchall()
        actions = connection.execute(
            "SELECT action FROM replay_session_audit WHERE session_id = ? ORDER BY audit_id;",
            (session.session_id,),
        ).fetchall()
        commands = connection.execute(
            "SELECT COUNT(*) FROM replay_commands WHERE session_id = ?;",
            (session.session_id,),
        ).fetchone()[0]
    assert [tuple(row) for row in raw_after] == [tuple(row) for row in raw_before]
    assert [row[0] for row in actions] == ["create", "start", "step"]
    assert commands == 2


def test_idempotent_retry_returns_prior_result_and_conflicts_fail_closed(
    isolated_database: Path,
) -> None:
    prepare(isolated_database)
    seed_tick("GOLD:1", 1)
    session = create()
    url = f"/api/v2/replay-sessions/{session.session_id}/commands"
    payload = {"command": "start", "expected_state_version": 0}
    with TestClient(app) as client:
        auth = login(client)
        first = client.post(url, json=payload, headers=command_headers(auth, "same"))
        retry = client.post(url, json=payload, headers=command_headers(auth, "same"))
        changed = client.post(
            url,
            json={"command": "cancel", "expected_state_version": 0},
            headers=command_headers(auth, "same"),
        )
        stale = client.post(
            url,
            json={"command": "pause", "expected_state_version": 0},
            headers=command_headers(auth, "new"),
        )
    assert first.status_code == retry.status_code == 200
    assert first.json()["data"]["idempotent_replay"] is False
    assert retry.json()["data"]["idempotent_replay"] is True
    assert changed.status_code == stale.status_code == 409
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM replay_commands;").fetchone()[0] == 1


def test_non_owner_and_audit_failure_leave_no_partial_command(
    isolated_database: Path,
) -> None:
    prepare(isolated_database)
    seed_tick("GOLD:1", 1)
    foreign = create(owner="OTHER")
    owned = create()
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_command_audit
            BEFORE INSERT ON replay_session_audit
            WHEN NEW.action = 'start'
            BEGIN SELECT RAISE(ABORT, 'forced audit failure'); END;
            """
        )
    with TestClient(app, raise_server_exceptions=False) as client:
        auth = login(client)
        forbidden = client.post(
            f"/api/v2/replay-sessions/{foreign.session_id}/commands",
            json={"command": "start", "expected_state_version": 0},
            headers=command_headers(auth, "foreign"),
        )
        failed = client.post(
            f"/api/v2/replay-sessions/{owned.session_id}/commands",
            json={"command": "start", "expected_state_version": 0},
            headers=command_headers(auth, "rollback"),
        )
    assert forbidden.status_code == 403
    assert failed.status_code == 503
    with get_connection() as connection:
        row = connection.execute(
            "SELECT state, state_version FROM replay_sessions WHERE session_id = ?;",
            (owned.session_id,),
        ).fetchone()
        assert tuple(row) == ("created", 0)
        assert connection.execute("SELECT COUNT(*) FROM replay_commands;").fetchone()[0] == 0
