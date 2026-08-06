from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.pattern_candidate_repository import (
    PatternCandidateConflictError,
    get_pattern_candidate,
    register_pattern_candidate,
)
from backend.app.database.replay_session_repository import (
    create_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.main import app
from backend.app.strategies.replay_pattern_candidates import (
    PatternCandidateBlockedByDataQualityError,
    evaluate_replay_pattern_candidate_backtest,
)


BASE_TIME = datetime(2026, 8, 4, 21, 0, tzinfo=UTC)


def _prepare(database_path: Path, *, owner: str = "TEST-USER", include_critical_finding: bool):
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    rows = [
        (
            f"GOLD:dq:{index:04d}",
            (BASE_TIME + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
            (BASE_TIME + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
            4100.0 + index, 4100.4 + index, 4100.2 + index,
            int(BASE_TIME.timestamp() * 1000) + index * 5_000,
        )
        for index in range(1, 36)
    ]
    if include_critical_finding:
        # DQ-005 (critical): ask lower than bid.
        rows.append((
            "GOLD:dq:bad",
            (BASE_TIME + timedelta(seconds=17.5)).isoformat(timespec="microseconds"),
            (BASE_TIME + timedelta(seconds=17.5)).isoformat(timespec="microseconds"),
            4200.0, 4100.0, 4150.0,
            int(BASE_TIME.timestamp() * 1000) + 17_500,
        ))
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
            rows,
        )
    created = create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor=owner, actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=50)
    return running


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _register(session_id: str, candidate_id: str = "structure_break_long:dq", created_by: str = "TEST-USER"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id=candidate_id, hypothesis_id="structure_break_long",
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


def test_backtest_blocks_candidate_when_session_has_critical_finding(isolated_database: Path) -> None:
    session = _prepare(isolated_database, include_critical_finding=True)
    candidate = _register(session.session_id)

    with pytest.raises(PatternCandidateBlockedByDataQualityError):
        evaluate_replay_pattern_candidate_backtest(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        )

    reloaded = get_pattern_candidate(candidate.candidate_id)
    assert reloaded.lifecycle_state == "blocked_by_data_quality"

    # Blocked terminally -- a second attempt cannot re-run the backtest.
    with pytest.raises(PatternCandidateConflictError):
        evaluate_replay_pattern_candidate_backtest(
            candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator",
        )


def test_backtest_proceeds_normally_without_critical_finding(isolated_database: Path) -> None:
    session = _prepare(isolated_database, include_critical_finding=False)
    candidate = _register(session.session_id)

    backtest = evaluate_replay_pattern_candidate_backtest(
        candidate_id=candidate.candidate_id, actor="TEST-USER", actor_role="operator", horizon_bars=2,
    )
    assert backtest.candidate_id == candidate.candidate_id

    reloaded = get_pattern_candidate(candidate.candidate_id)
    assert reloaded.lifecycle_state == "evaluated"


def test_backtest_api_returns_409_when_blocked_by_data_quality(isolated_database: Path) -> None:
    session = _prepare(isolated_database, include_critical_finding=True)
    candidate = _register(session.session_id)

    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/backtest", json={}, headers=headers,
        )
        detail = client.get(f"/api/v2/pattern-candidates/{candidate.candidate_id}", headers=headers)

    assert response.status_code == 409
    assert detail.json()["data"]["lifecycle_state"] == "blocked_by_data_quality"
