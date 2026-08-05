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
                    f"GOLD:pattern:{index:04d}",
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
    if completed:
        run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=10)
    return running


def _headers(client: TestClient, user_code: str = "TEST-USER") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": user_code, "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_register_requires_a_confirmed_candidate(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/pattern-candidates",
            json={
                "session_id": session.session_id, "hypothesis_id": "market_structure_long",
                "timeframe": "M1", "bar_limit": 10,
            },
            headers=headers,
        )
    assert response.status_code == 409


def test_register_rejects_unknown_hypothesis_ownership_and_incomplete_session(
    isolated_database: Path,
) -> None:
    incomplete = _prepare(isolated_database, completed=False)
    foreign = create_replay_session(
        created_by="OTHER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    # Reuses the ticks _prepare already inserted; a second session over the
    # same range just needs its own lifecycle to reach "completed".
    completed_session = create_replay_session(
        created_by="TEST-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    completed_running = transition_replay_session(
        session_id=completed_session.session_id, actor="TEST-USER", actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=completed_running.session_id, actor="WORKER", actor_role="worker", batch_size=10)
    with TestClient(app) as client:
        unauthorized = client.post(
            "/api/v2/pattern-candidates",
            json={"session_id": incomplete.session_id, "hypothesis_id": "market_structure_long"},
        )
        headers = _headers(client)
        unfinished = client.post(
            "/api/v2/pattern-candidates",
            json={"session_id": incomplete.session_id, "hypothesis_id": "market_structure_long"},
            headers=headers,
        )
        forbidden = client.post(
            "/api/v2/pattern-candidates",
            json={"session_id": foreign.session_id, "hypothesis_id": "market_structure_long"},
            headers=headers,
        )
        missing_session = client.post(
            "/api/v2/pattern-candidates",
            json={"session_id": "missing", "hypothesis_id": "market_structure_long"},
            headers=headers,
        )
        unknown_hypothesis = client.post(
            "/api/v2/pattern-candidates",
            json={"session_id": completed_session.session_id, "hypothesis_id": "not_a_real_hypothesis"},
            headers=headers,
        )
    assert unauthorized.status_code == 401
    assert unfinished.status_code == 409
    assert forbidden.status_code == 403
    assert missing_session.status_code == 404
    assert unknown_hypothesis.status_code == 422


def test_list_and_detail_are_owner_scoped_and_read_only(isolated_database: Path) -> None:
    session_mine = _prepare(isolated_database, owner="TEST-USER")
    session_theirs = create_replay_session(
        created_by="OTHER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    mine = register_pattern_candidate(
        created_by="TEST-USER", actor_role="operator", replay_session_id=session_mine.session_id,
        candidate_id="market_structure_long:mine", hypothesis_id="market_structure_long",
        hypothesis_version="1.0.0", family="market_structure", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={"latest_high": "HH"}, pattern_candidate_version="1.0.0",
        hypothesis_registry_version="1.0.0", source_fingerprint="sha256:pattern",
        timeframe="M5", parameters={"bar_limit": 500},
    )
    theirs = register_pattern_candidate(
        created_by="OTHER", actor_role="operator", replay_session_id=session_theirs.session_id,
        candidate_id="market_structure_long:theirs", hypothesis_id="market_structure_long",
        hypothesis_version="1.0.0", family="market_structure", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M5", parameters={},
    )
    with TestClient(app) as client:
        unauthorized_list = client.get("/api/v2/pattern-candidates")
        headers = _headers(client)
        listed = client.get("/api/v2/pattern-candidates", headers=headers)
        detail = client.get(f"/api/v2/pattern-candidates/{mine.candidate_id}", headers=headers)
        forbidden_detail = client.get(
            f"/api/v2/pattern-candidates/{theirs.candidate_id}", headers=headers,
        )
        missing_detail = client.get("/api/v2/pattern-candidates/missing", headers=headers)

    assert unauthorized_list.status_code == 401
    assert listed.status_code == 200
    assert [item["candidate_id"] for item in listed.json()["data"]] == [mine.candidate_id]
    assert detail.status_code == 200
    assert detail.json()["data"]["lifecycle_state"] == "registered"
    assert forbidden_detail.status_code == 403
    assert missing_detail.status_code == 404
    with get_connection() as connection:
        raw_tick_count = connection.execute("SELECT COUNT(*) FROM tick_events;").fetchone()[0]
    assert raw_tick_count == 35


def test_archive_transitions_via_api_and_enforces_optimistic_lock(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = register_pattern_candidate(
        created_by="TEST-USER", actor_role="operator", replay_session_id=session.session_id,
        candidate_id="market_structure_long:archive", hypothesis_id="market_structure_long",
        hypothesis_version="1.0.0", family="market_structure", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-05T00:10:00+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M5", parameters={},
    )
    with TestClient(app) as client:
        headers = _headers(client)
        stale = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/archive",
            json={"expected_state_version": candidate.state_version + 1},
            headers=headers,
        )
        archived = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/archive",
            json={"expected_state_version": candidate.state_version},
            headers=headers,
        )
        repeated = client.post(
            f"/api/v2/pattern-candidates/{candidate.candidate_id}/archive",
            json={"expected_state_version": candidate.state_version},
            headers=headers,
        )
    assert stale.status_code == 409
    assert archived.status_code == 200
    assert archived.json()["data"]["lifecycle_state"] == "archived"
    assert repeated.status_code == 409
