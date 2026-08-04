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


def _prepare(database_path: Path, *, owner: str = "TEST-USER", completed: bool = True):
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
                    f"GOLD:analysis:{index:04d}",
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
        created_by=owner,
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(minutes=3),
        mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id,
        actor=owner,
        actor_role="operator",
        action="start",
        expected_state="created",
    )
    if completed:
        run_max_speed_replay(
            session_id=running.session_id,
            actor="WORKER",
            actor_role="worker",
            batch_size=10,
        )
    return running


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_analysis_api_is_protected_deterministic_and_read_only(
    isolated_database: Path,
) -> None:
    session = _prepare(isolated_database)
    url = (
        f"/api/v2/replay-sessions/{session.session_id}/technical-analysis"
        "?timeframe=M1&ema_period=2&rsi_period=2&atr_period=2&bar_limit=10"
    )
    with get_connection() as connection:
        before = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id"
        ).fetchall()
    with TestClient(app) as client:
        unauthorized = client.get(url)
        headers = _headers(client)
        first = client.get(url, headers=headers)
        second = client.get(url, headers=headers)

    assert unauthorized.status_code == 401
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    data = first.json()["data"]
    assert data["session_id"] == session.session_id
    assert data["timeframe"] == "M1"
    assert data["interpretation"] == "research_observation_not_trading_signal"
    assert len(data["bars"]) == 3
    assert data["lineage"]["dataset_fingerprint"].startswith("sha256:")
    assert data["lineage"]["bar_fingerprint"].startswith("sha256:")
    assert data["lineage"]["indicator_fingerprint"].startswith("sha256:")
    assert data["indicators"]["ema"]["points"][0]["status"] == "insufficient_data"
    with get_connection() as connection:
        after = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id"
        ).fetchall()
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


def test_analysis_api_enforces_owner_completed_state_and_safe_parameters(
    isolated_database: Path,
) -> None:
    incomplete = _prepare(isolated_database, completed=False)
    foreign = create_replay_session(
        created_by="OTHER",
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(minutes=3),
        mode="max_speed",
    )
    with TestClient(app) as client:
        headers = _headers(client)
        unfinished = client.get(
            f"/api/v2/replay-sessions/{incomplete.session_id}/technical-analysis",
            headers=headers,
        )
        forbidden = client.get(
            f"/api/v2/replay-sessions/{foreign.session_id}/technical-analysis",
            headers=headers,
        )
        invalid = client.get(
            f"/api/v2/replay-sessions/{incomplete.session_id}/technical-analysis"
            "?timeframe=M2&bar_limit=5001",
            headers=headers,
        )
        missing = client.get(
            "/api/v2/replay-sessions/missing/technical-analysis",
            headers=headers,
        )
    assert unfinished.status_code == 409
    assert forbidden.status_code == 403
    assert invalid.status_code == 422
    assert missing.status_code == 404


def test_analysis_api_detects_dataset_drift(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with get_connection() as connection:
        timestamp = (BASE_TIME + timedelta(seconds=2)).isoformat(timespec="microseconds")
        connection.execute(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, received_at, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            ) VALUES ('GOLD:late', 'TICK_RECEIVED', ?, ?, 'esas.mt5.bridge', '1.0',
                      'GOLD', 4100.0, 4100.4, 4100.2, 1, 6, 1,
                      '1.6.0', '{}');
            """,
            (timestamp, timestamp),
        )
    with TestClient(app) as client:
        response = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/technical-analysis",
            headers=_headers(client),
        )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Replay dataset no longer matches the session snapshot"
    }


def test_strategy_analysis_api_is_protected_deterministic_and_research_only(
    isolated_database: Path,
) -> None:
    session = _prepare(isolated_database)
    url = (
        f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis"
        "?timeframe=M1&ema_period=2&rsi_period=2&rsi_low=30&rsi_high=70"
        "&bar_limit=10&outcome_horizon=1&development_ratio=0.7&walk_forward_windows=3"
    )
    with TestClient(app) as client:
        assert client.get(url).status_code == 401
        headers = _headers(client)
        first = client.get(url, headers=headers)
        second = client.get(url, headers=headers)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    data = first.json()["data"]
    assert data["api_version"] == "1.2.0"
    assert data["interpretation"] == "research_observation_not_trading_signal"
    assert len(data["strategies"]) == 2
    strategy = data["strategies"][0]
    assert strategy["definition"]["strategy_id"] == "ema_close_relation"
    assert strategy["definition"]["version"] == "1.0.0"
    assert strategy["definition"]["lifecycle"] == "experimental"
    assert strategy["summary"] == {
        "ready": 2,
        "insufficient_data": 1,
        "above": 2,
        "below": 0,
        "equal": 0,
    }
    assert strategy["fingerprint"].startswith("sha256:")
    outcome = strategy["outcome_evaluation"]
    assert outcome["definition"]["version"] == "1.0.0"
    assert outcome["horizon_bars"] == 1
    assert outcome["summary"]["matured"] == 1
    assert outcome["summary"]["immature"] == 1
    assert outcome["interpretation"] == "historical_outcome_measurement_not_trading_signal"
    walk_forward = strategy["walk_forward_evaluation"]
    assert walk_forward["definition"]["version"] == "1.0.0"
    assert walk_forward["status"] == "ready"
    assert walk_forward["manifest"]["split_policy"] == "chronological_no_shuffle_validation_untouched"
    assert walk_forward["manifest"]["development_ratio"] == 0.7
    assert walk_forward["development"]["boundary_excluded"] == 1
    assert walk_forward["validation"]["total_observations"] == 1
    multi_window = strategy["multi_window_evaluation"]
    assert multi_window["definition"]["version"] == "1.0.0"
    assert multi_window["status"] == "insufficient_data"
    assert multi_window["manifest"]["requested_windows"] == 3
    assert multi_window["manifest"]["split_policy"] == (
        "expanding_development_non_overlapping_chronological_validation_no_shuffle"
    )
    assert multi_window["summary"]["completed_windows"] == 1
    assert len(multi_window["windows"]) == 1
    assert multi_window["windows"][0]["manifest"]["upstream_strategy_fingerprint"] == strategy["fingerprint"]
    cost = strategy["cost_scenario_evaluation"]
    assert cost["definition"]["version"] == "1.0.0"
    assert [item["assumption"]["scenario"] for item in cost["scenarios"]] == [
        "normal", "adverse", "stress",
    ]
    assert cost["manifest"]["upstream_multi_window_fingerprint"] == multi_window["fingerprint"]
    assert cost["manifest"]["source"] == "generic_research_assumption_not_broker_fact"
    assert cost["scenarios"][0]["assumption"]["total_cost_bps"] == 4.5
    assert cost["scenarios"][0]["summary"]["raw_weighted_mean_return_percent"] == multi_window["summary"]["weighted_mean_return_percent"]
    reliability = strategy["statistical_reliability_evaluation"]
    assert reliability["definition"]["version"] == "1.0.0"
    assert reliability["manifest"]["baseline"] == "zero_percent_change"
    assert reliability["manifest"]["upstream_cost_scenario_fingerprint"] == cost["fingerprint"]
    assert reliability["definition"]["interpretation"] == "historical_uncertainty_evidence_not_trading_signal"
    assert [item["scenario"] for item in reliability["scenarios"]] == [
        "normal", "adverse", "stress",
    ]
    rsi = data["strategies"][1]
    assert rsi["definition"]["strategy_id"] == "rsi_regime_observation"
    assert rsi["definition"]["version"] == "1.0.0"
    assert rsi["summary"]["ready"] == 1
    assert rsi["summary"]["insufficient_data"] == 2
    assert (
        rsi["cost_scenario_evaluation"]["scenarios"][0]["assumption"]
        == cost["scenarios"][0]["assumption"]
    )
    assert rsi["statistical_reliability_evaluation"]["fingerprint"].startswith("sha256:")
    serialized = str(first.json()).lower()
    assert "order" not in serialized
    assert "position_size" not in serialized


def test_strategy_analysis_rejects_crossed_rsi_thresholds(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis?rsi_low=70&rsi_high=30",
            headers=_headers(client),
        )
    assert response.status_code == 422


def test_strategy_analysis_rejects_unsafe_outcome_horizon(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis"
            "?outcome_horizon=0",
            headers=_headers(client),
        )
    assert response.status_code == 422


def test_strategy_analysis_rejects_unsafe_development_ratio(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis"
            "?development_ratio=0.95",
            headers=_headers(client),
        )
    assert response.status_code == 422


def test_strategy_analysis_rejects_unsafe_walk_forward_window_count(
    isolated_database: Path,
) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis"
            "?walk_forward_windows=1",
            headers=_headers(client),
        )
    assert response.status_code == 422


def test_strategy_analysis_rejects_unsafe_cost_assumptions(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        negative = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis?cost_spread_bps=-1",
            headers=headers,
        )
        excessive = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis?cost_slippage_bps=1001",
            headers=headers,
        )
        crossed = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/strategy-analysis"
            "?adverse_cost_multiplier=3&stress_cost_multiplier=2",
            headers=headers,
        )
    assert negative.status_code == 422
    assert excessive.status_code == 422
    assert crossed.status_code == 422


def test_strategy_analysis_api_enforces_owner_and_completed_state(
    isolated_database: Path,
) -> None:
    incomplete = _prepare(isolated_database, completed=False)
    foreign = create_replay_session(
        created_by="OTHER",
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(minutes=3),
        mode="max_speed",
    )
    with TestClient(app) as client:
        headers = _headers(client)
        unfinished = client.get(
            f"/api/v2/replay-sessions/{incomplete.session_id}/strategy-analysis",
            headers=headers,
        )
        forbidden = client.get(
            f"/api/v2/replay-sessions/{foreign.session_id}/strategy-analysis",
            headers=headers,
        )
    assert unfinished.status_code == 409
    assert forbidden.status_code == 403
