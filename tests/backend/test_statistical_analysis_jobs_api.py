from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    create_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.main import app


BASE_TIME = datetime(2026, 8, 4, 21, 0, tzinfo=UTC)


def _prepare(database_path: Path, *, owner: str = "TEST-USER"):
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, received_at, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            ) VALUES (?, 'TICK_RECEIVED', ?, ?, 'esas.mt5.bridge', '1.0',
                      'GOLD', ?, ?, ?, 1, 6, ?, '1.6.0', '{}');
            """,
            [
                (
                    f"GOLD:sa-job-api:{index:04d}",
                    (BASE_TIME + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
                    (BASE_TIME + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
                    4100.0 + index,
                    4100.4 + index,
                    4100.2 + index,
                    int(BASE_TIME.timestamp() * 1000) + index * 5_000,
                )
                for index in range(1, 36)
            ],
        )
    created = create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor=owner, actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=10)
    return running


def _headers(client: TestClient, user_code: str = "TEST-USER") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": user_code, "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_enqueue_statistical_analysis_job_processes_via_background_task_and_completes(
    isolated_database: Path,
) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs",
            json={"idempotency_key": "job-1", "timeframe": "M1", "minimum_sample_size": 3},
            headers=headers,
        )
        assert created.status_code == 202
        job_id = created.json()["data"]["job_id"]
        assert job_id.startswith("saj_")
        detail = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs/{job_id}",
            headers=headers,
        )
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["state"] == "completed"
    assert body["result"]["session_id"] == session.session_id
    assert body["result"]["return_series"]["status"] == "completed"
    assert body["result"]["interpretation"] == "research_observation_not_trading_signal"


def test_enqueue_statistical_analysis_job_is_idempotent_by_key(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        first = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs",
            json={"idempotency_key": "dup"}, headers=headers,
        )
        second = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs",
            json={"idempotency_key": "dup"}, headers=headers,
        )
    assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]


def test_enqueue_statistical_analysis_job_missing_session_returns_404(isolated_database: Path) -> None:
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/replay-sessions/does-not-exist/statistical-analysis-jobs",
            json={"idempotency_key": "k1"}, headers=headers,
        )
    assert response.status_code == 404


def test_job_detail_rejects_wrong_session_path(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs",
            json={"idempotency_key": "job-1"}, headers=headers,
        )
        job_id = created.json()["data"]["job_id"]
        mismatched = client.get(
            f"/api/v2/replay-sessions/some-other-session/statistical-analysis-jobs/{job_id}",
            headers=headers,
        )
    assert mismatched.status_code == 404


def test_job_detail_missing_returns_404(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs/does-not-exist",
            headers=headers,
        )
    assert response.status_code == 404


def test_cancel_terminal_job_returns_409(isolated_database: Path) -> None:
    # The BackgroundTask attached to the enqueue call runs to completion inside
    # TestClient's synchronous request/response cycle, so by the time the client
    # sees the 202 the job has already finished -- cancel on it must be rejected.
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs",
            json={"idempotency_key": "job-1"}, headers=headers,
        )
        job_id = created.json()["data"]["job_id"]
        cancel = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs/{job_id}/cancel",
            headers=headers,
        )
    assert cancel.status_code == 409


def test_job_endpoints_require_ownership(isolated_database: Path) -> None:
    # Session owned by a different user than the one who will authenticate --
    # both enqueueing a job against it and, if a job existed, viewing that
    # job must be rejected as belonging to another user's resource.
    session = _prepare(isolated_database, owner="OTHER-OWNER")
    with TestClient(app) as client:
        headers = _headers(client, user_code="TEST-USER")
        forbidden_create = client.post(
            f"/api/v2/replay-sessions/{session.session_id}/statistical-analysis-jobs",
            json={"idempotency_key": "job-1"}, headers=headers,
        )
    assert forbidden_create.status_code == 403
