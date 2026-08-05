from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.pattern_candidate_repository import register_pattern_candidate
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
                    f"GOLD:job-api:{index:04d}",
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


def _register_structure_break(session_id: str, created_by: str = "TEST-USER"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id="structure_break_long:job-api", hypothesis_id="structure_break_long",
        hypothesis_version="1.0.0", family="bos_choch_retest", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-04T21:00:10+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M1",
        parameters={
            "bar_limit": 10, "pivot_left": 2, "pivot_right": 2, "equality_tolerance_bps": 0.0,
            "liquidity_pool_tolerance_bps": 10.0, "liquidity_minimum_touches": 2,
            "liquidity_minimum_sweep_bps": 1.0, "liquidity_maximum_pool_age_bars": 250,
            "bos_choch_minimum_close_break_bps": 1.0, "bos_choch_maximum_pivot_age_bars": 250,
            "retest_touch_tolerance_bps": 5.0, "retest_confirmation_close_bps": 0.0,
            "retest_invalidation_close_bps": 10.0, "retest_maximum_age_bars": 100,
        },
    )


def _headers(client: TestClient, user_code: str = "TEST-USER") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": user_code, "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_enqueue_backtest_job_processes_via_background_task_and_completes(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs",
            json={"idempotency_key": "job-1", "horizon_bars": 2}, headers=headers,
        )
        assert created.status_code == 202
        job_id = created.json()["data"]["job_id"]
        detail = client.get(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs/{job_id}",
            headers=headers,
        )
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["state"] == "completed"
    assert body["result"]["result"]["hypothesis_id"] == "structure_break_long"


def test_enqueue_backtest_job_is_idempotent_by_key(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        first = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs",
            json={"idempotency_key": "dup"}, headers=headers,
        )
        second = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs",
            json={"idempotency_key": "dup"}, headers=headers,
        )
    assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]


def test_enqueue_backtest_job_missing_candidate_returns_404(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/pattern-candidates/does-not-exist/backtest-jobs",
            json={"idempotency_key": "k1"}, headers=headers,
        )
    assert response.status_code == 404


def test_job_detail_rejects_wrong_candidate_path(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs",
            json={"idempotency_key": "job-1"}, headers=headers,
        )
        job_id = created.json()["data"]["job_id"]
        mismatched = client.get(
            f"/api/v2/pattern-candidates/some-other-candidate/backtest-jobs/{job_id}",
            headers=headers,
        )
    assert mismatched.status_code == 404


def test_job_detail_missing_returns_404(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.get(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs/does-not-exist",
            headers=headers,
        )
    assert response.status_code == 404


def test_cancel_terminal_job_returns_409(isolated_database: Path) -> None:
    # The BackgroundTask attached to the enqueue call runs to completion inside
    # TestClient's synchronous request/response cycle, so by the time the client
    # sees the 202 the job has already finished -- cancel on it must be rejected.
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs",
            json={"idempotency_key": "job-1"}, headers=headers,
        )
        job_id = created.json()["data"]["job_id"]
        cancel = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs/{job_id}/cancel",
            headers=headers,
        )
    assert cancel.status_code == 409


def test_analysis_jobs_metrics_reports_depth(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest-jobs",
            json={"idempotency_key": "job-1"}, headers=headers,
        )
        metrics = client.get("/api/v2/analysis-jobs/metrics", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["data"]["job_type"] == "pattern_candidate_backtest"
    assert "completed" in metrics.json()["data"]["depth_by_state"]
