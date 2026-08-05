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
                    f"GOLD:backtest:{index:04d}",
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


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _register_structure_break(session_id: str, created_by: str = "TEST-USER"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id="structure_break_long:api", hypothesis_id="structure_break_long",
        hypothesis_version="1.0.0", family="bos_choch_retest", direction="bullish",
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


def _register_market_structure(session_id: str, created_by: str = "TEST-USER"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id="market_structure_long:api", hypothesis_id="market_structure_long",
        hypothesis_version="1.0.0", family="market_structure", direction="long",
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


def test_backtest_run_and_read_round_trip_and_transitions_lifecycle(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        missing_before_run = client.get(f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest", headers=headers)
        run = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest",
            json={"horizon_bars": 2}, headers=headers,
        )
        read = client.get(f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest", headers=headers)
        detail = client.get(f"/api/v2/pattern-candidates/{candidate.candidate_id}", headers=headers)

    assert missing_before_run.status_code == 404
    assert run.status_code == 200
    assert run.json()["data"]["horizon_bars"] == 2
    assert run.json()["data"]["result"]["hypothesis_id"] == "structure_break_long"
    assert read.status_code == 200
    assert read.json()["data"]["backtest_id"] == run.json()["data"]["backtest_id"]
    assert detail.json()["data"]["lifecycle_state"] == "evaluated"


def test_backtest_rejects_unsupported_hypothesis(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_market_structure(session.session_id)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest",
            json={}, headers=headers,
        )
    assert response.status_code == 422


def test_backtest_enforces_ownership_and_missing_candidate(isolated_database: Path) -> None:
    session = _prepare(isolated_database, owner="TEST-USER")
    session_theirs = create_replay_session(
        created_by="OTHER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    theirs = register_pattern_candidate(
        created_by="OTHER", actor_role="operator", replay_session_id=session_theirs.session_id,
        candidate_id="structure_break_long:theirs", hypothesis_id="structure_break_long",
        hypothesis_version="1.0.0", family="bos_choch_retest", direction="bullish",
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
    del session
    with TestClient(app) as client:
        unauthorized = client.post(f"/api/v2/pattern-candidates/{theirs.candidate_id}/backtest", json={})
        headers = _headers(client)
        forbidden_run = client.post(
            f"/api/v2/pattern-candidates/{theirs.candidate_id}/backtest", json={}, headers=headers,
        )
        forbidden_read = client.get(f"/api/v2/pattern-candidates/{theirs.candidate_id}/backtest", headers=headers)
        missing_run = client.post("/api/v2/pattern-candidates/missing/backtest", json={}, headers=headers)
        missing_read = client.get("/api/v2/pattern-candidates/missing/backtest", headers=headers)
    assert unauthorized.status_code == 401
    assert forbidden_run.status_code == 403
    assert forbidden_read.status_code == 403
    assert missing_run.status_code == 404
    assert missing_read.status_code == 404
