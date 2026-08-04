from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import create_replay_session
from backend.app.main import app


BASE = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)


def prepare(path: Path) -> None:
    initialize_database()
    apply_migrations(path, application_version="0.3.0")


def auth(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def tick(event_id: str, milliseconds: int) -> None:
    timestamp = BASE + timedelta(milliseconds=milliseconds)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO tick_events
            (event_id, event_type, event_timestamp, source, event_version,
             symbol, bid, ask, last, volume, flags, source_time_msc,
             module_version, raw_event_json)
            VALUES (?, 'TICK_RECEIVED', ?, 'esas.mt5.bridge', '1.0', 'GOLD',
                    1, 2, 1.5, 1, 6, ?, '1.6.0', '{"immutable":true}');
            """,
            (event_id, timestamp.isoformat(timespec="microseconds"), milliseconds),
        )


def session(owner: str = "TEST-USER"):
    return create_replay_session(
        created_by=owner,
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE,
        end_at=BASE + timedelta(seconds=1),
        mode="step",
    )


def test_events_require_auth_and_owner(isolated_database: Path) -> None:
    prepare(isolated_database)
    tick("GOLD:1", 1)
    owned = session()
    foreign = session("OTHER")
    with TestClient(app) as client:
        unauthenticated = client.get(
            f"/api/v2/replay-sessions/{owned.session_id}/events"
        )
        forbidden = client.get(
            f"/api/v2/replay-sessions/{foreign.session_id}/events",
            headers=auth(client),
        )
    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403


def test_events_are_deterministic_paginated_and_snapshot_bounded(
    isolated_database: Path,
) -> None:
    prepare(isolated_database)
    tick("GOLD:1", 1)
    tick("GOLD:2", 2)
    tick("GOLD:3", 3)
    replay = session()
    # Snapshot yaradıldıqdan sonra interval daxilində gələn tick görünməməlidir.
    tick("GOLD:4", 4)
    with get_connection() as connection:
        before = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id"
        ).fetchall()
    with TestClient(app) as client:
        headers = auth(client)
        first = client.get(
            f"/api/v2/replay-sessions/{replay.session_id}/events?page_size=2",
            headers=headers,
        )
        cursor = first.json()["page"]["next_cursor"]
        second = client.get(
            f"/api/v2/replay-sessions/{replay.session_id}/events",
            params={"page_size": 2, "cursor": cursor},
            headers=headers,
        )
    assert first.status_code == second.status_code == 200
    ids = [item["event_id"] for item in first.json()["data"] + second.json()["data"]]
    assert ids == ["GOLD:1", "GOLD:2", "GOLD:3"]
    assert first.json()["snapshot"]["dataset_tick_count"] == 3
    assert second.json()["page"]["has_more"] is False
    with get_connection() as connection:
        after = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id"
        ).fetchall()
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


def test_event_cursor_is_bound_to_user_and_session_and_rejects_tampering(
    isolated_database: Path,
) -> None:
    prepare(isolated_database)
    tick("GOLD:1", 1)
    tick("GOLD:2", 2)
    first_session = session()
    second_session = session()
    with TestClient(app) as client:
        headers = auth(client)
        first = client.get(
            f"/api/v2/replay-sessions/{first_session.session_id}/events?page_size=1",
            headers=headers,
        )
        cursor = first.json()["page"]["next_cursor"]
        wrong_session = client.get(
            f"/api/v2/replay-sessions/{second_session.session_id}/events",
            params={"cursor": cursor},
            headers=headers,
        )
        tampered = client.get(
            f"/api/v2/replay-sessions/{first_session.session_id}/events",
            params={"cursor": cursor[:-1] + ("0" if cursor[-1] != "0" else "1")},
            headers=headers,
        )
    assert wrong_session.status_code == tampered.status_code == 400


def test_missing_session_and_invalid_fields_fail_safely(
    isolated_database: Path,
) -> None:
    prepare(isolated_database)
    with TestClient(app) as client:
        headers = auth(client)
        missing = client.get("/api/v2/replay-sessions/missing/events", headers=headers)
        invalid_limit = client.get(
            "/api/v2/replay-sessions/missing/events?page_size=0", headers=headers
        )
    assert missing.status_code == 404
    assert invalid_limit.status_code == 422
