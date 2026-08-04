from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import create_replay_session
from backend.app.main import app


BASE_TIME = datetime(2026, 8, 4, 8, 0, tzinfo=UTC)


def prepare_schema(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def dashboard_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_sessions(count: int) -> list[object]:
    sessions = []
    for index in range(count):
        sessions.append(
            create_replay_session(
                created_by="TEST-USER",
                actor_role="operator",
                symbol=f"TEST-{index}",
                start_at=BASE_TIME + timedelta(minutes=index),
                end_at=BASE_TIME + timedelta(minutes=index, seconds=1),
                mode="step",
            )
        )
    return sessions


def test_replay_session_endpoints_require_authentication(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)

    with TestClient(app) as client:
        list_response = client.get("/api/v2/replay-sessions")
        detail_response = client.get("/api/v2/replay-sessions/missing")

    assert list_response.status_code == 401
    assert detail_response.status_code == 401


def test_replay_sessions_are_cursor_paginated_without_duplicates(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)
    seeded = seed_sessions(3)

    with TestClient(app) as client:
        headers = dashboard_headers(client)
        first = client.get(
            "/api/v2/replay-sessions?page_size=2",
            headers=headers,
        )
        assert first.status_code == 200
        first_body = first.json()
        cursor = first_body["page"]["next_cursor"]
        assert cursor

        second = client.get(
            "/api/v2/replay-sessions",
            params={"page_size": 2, "cursor": cursor},
            headers=headers,
        )

    assert second.status_code == 200
    first_ids = [item["session_id"] for item in first_body["data"]]
    second_ids = [item["session_id"] for item in second.json()["data"]]
    assert len(first_ids) == 2
    assert len(second_ids) == 1
    assert set(first_ids + second_ids) == {
        session.session_id for session in seeded
    }
    assert not set(first_ids).intersection(second_ids)
    assert second.json()["page"]["next_cursor"] is None
    assert first_body["page"]["limit"] == 2
    assert first_body["page"]["has_more"] is True
    assert second.json()["page"]["has_more"] is False


def test_replay_session_cursor_rejects_tampering(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)
    seed_sessions(2)

    with TestClient(app) as client:
        headers = dashboard_headers(client)
        first = client.get(
            "/api/v2/replay-sessions?page_size=1",
            headers=headers,
        )
        cursor = first.json()["page"]["next_cursor"]
        replacement = "0" if cursor[-1] != "0" else "1"
        tampered = f"{cursor[:-1]}{replacement}"
        response = client.get(
            "/api/v2/replay-sessions",
            params={"cursor": tampered},
            headers=headers,
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Replay cursor is invalid or expired"


def test_replay_session_detail_returns_checkpoint_metadata(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)
    session = seed_sessions(1)[0]

    with TestClient(app) as client:
        response = client.get(
            f"/api/v2/replay-sessions/{session.session_id}",
            headers=dashboard_headers(client),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["session_id"] == session.session_id
    assert data["created_by"] == "TEST-USER"
    assert data["state"] == "completed"
    assert data["checkpoint_position"] is None
    assert response.json()["meta"] == {"api_version": "2"}


def test_replay_session_detail_hides_internal_not_found_information(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/replay-sessions/rps_missing",
            headers=dashboard_headers(client),
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Replay session was not found"}


def test_replay_session_page_size_is_bounded(
    isolated_database: Path,
) -> None:
    prepare_schema(isolated_database)

    with TestClient(app) as client:
        headers = dashboard_headers(client)
        too_small = client.get(
            "/api/v2/replay-sessions?page_size=0",
            headers=headers,
        )
        too_large = client.get(
            "/api/v2/replay-sessions?page_size=201",
            headers=headers,
        )

    assert too_small.status_code == 422
    assert too_large.status_code == 422
