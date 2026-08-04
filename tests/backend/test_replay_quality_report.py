from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    ReplayTransitionConflictError,
    create_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.quality.report import create_replay_quality_report
from backend.app.main import app


BASE_TIME = datetime(2026, 8, 4, 21, 0, tzinfo=UTC)


def prepare(database_path: Path, source_times: list[int], *, negative_spread: bool = False):
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
                      'GOLD', ?, ?, 4100.25, 1, 6, ?, '1.6.0', '{}');
            """,
            [
                (
                    f"GOLD:{index:04d}",
                    (BASE_TIME + timedelta(seconds=index)).isoformat(timespec="microseconds"),
                    (BASE_TIME + timedelta(seconds=index)).isoformat(timespec="microseconds"),
                    4101.0 if negative_spread and index == 2 else 4100.0,
                    4100.5,
                    int(BASE_TIME.timestamp() * 1000) + source_time,
                )
                for index, source_time in enumerate(source_times, start=1)
            ],
        )
    created = create_replay_session(
        created_by="TEST-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor="TEST-USER", actor_role="operator",
        action="start", expected_state="created",
    )
    return running


def complete(session: object, batch_size: int = 2) -> None:
    run_max_speed_replay(
        session_id=session.session_id, actor="WORKER", actor_role="worker",
        batch_size=batch_size,
    )


def test_report_pass_status(isolated_database: Path) -> None:
    session = prepare(isolated_database, [1000, 2000, 3000])
    complete(session)
    report = create_replay_quality_report(session_id=session.session_id)
    assert report.summary.status == "pass"
    assert report.summary.tick_count == 3
    assert report.report_id.startswith("dqr_")


def test_report_review_status(isolated_database: Path) -> None:
    session = prepare(isolated_database, [3000, 2000, 4000])
    complete(session)
    report = create_replay_quality_report(session_id=session.session_id)
    assert report.summary.status == "review"
    assert report.statistics.tick_count == report.summary.tick_count
    assert report.summary.warning_count == 1


def test_report_fail_status(isolated_database: Path) -> None:
    session = prepare(isolated_database, [1000, 2000, 3000], negative_spread=True)
    complete(session)
    report = create_replay_quality_report(session_id=session.session_id)
    assert report.summary.status == "fail"
    assert report.summary.critical_count == 1


def test_report_fingerprint_is_batch_independent(isolated_database: Path) -> None:
    session = prepare(isolated_database, [3000, 2000, 4000])
    complete(session)
    first = create_replay_quality_report(session_id=session.session_id, batch_size=1)
    second = create_replay_quality_report(session_id=session.session_id, batch_size=3)
    assert first == second


def test_incomplete_replay_is_rejected(isolated_database: Path) -> None:
    session = prepare(isolated_database, [1000, 2000, 3000])
    with pytest.raises(ReplayTransitionConflictError, match="completed"):
        create_replay_quality_report(session_id=session.session_id)


def dashboard_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_quality_report_api_is_authenticated_and_complete(isolated_database: Path) -> None:
    session = prepare(isolated_database, [1000, 2000, 3000])
    complete(session)
    with TestClient(app) as client:
        unauthorized = client.get(f"/internal/replay/{session.session_id}/quality-report")
        response = client.get(
            f"/internal/replay/{session.session_id}/quality-report",
            headers=dashboard_headers(client),
        )
    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["session_id"] == session.session_id
    assert response.json()["summary"]["status"] == "pass"
    assert response.json()["statistics"]["tick_count"] == 3


def test_quality_report_api_maps_safe_errors(isolated_database: Path) -> None:
    session = prepare(isolated_database, [1000])
    with TestClient(app) as client:
        headers = dashboard_headers(client)
        missing = client.get("/internal/replay/missing/quality-report", headers=headers)
        incomplete = client.get(
            f"/internal/replay/{session.session_id}/quality-report", headers=headers
        )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Replay session was not found"}
    assert incomplete.status_code == 409
    assert incomplete.json() == {"detail": "Replay session is not completed"}


def test_public_quality_report_has_stable_v2_contract_and_is_reproducible(
    isolated_database: Path,
) -> None:
    session = prepare(isolated_database, [1000, 2000, 3000])
    complete(session)
    with get_connection() as connection:
        before = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id;"
        ).fetchall()
    with TestClient(app) as client:
        headers = dashboard_headers(client)
        first = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/quality-report",
            headers=headers,
        )
        second = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/quality-report",
            headers=headers,
        )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["meta"] == {"api_version": "2"}
    assert first.json()["data"]["session_id"] == session.session_id
    assert first.json()["data"]["report_id"].startswith("dqr_")
    assert first.json()["data"]["content_fingerprint"].startswith("sha256:")
    with get_connection() as connection:
        after = connection.execute(
            "SELECT event_id, raw_event_json FROM tick_events ORDER BY event_id;"
        ).fetchall()
    assert [tuple(row) for row in after] == [tuple(row) for row in before]


def test_public_quality_report_enforces_auth_owner_and_completed_state(
    isolated_database: Path,
) -> None:
    incomplete = prepare(isolated_database, [1000])
    foreign = create_replay_session(
        created_by="OTHER",
        actor_role="operator",
        symbol="GOLD",
        start_at=BASE_TIME,
        end_at=BASE_TIME + timedelta(minutes=1),
        mode="max_speed",
    )
    url = f"/api/v2/replay-sessions/{incomplete.session_id}/quality-report"
    with TestClient(app) as client:
        unauthorized = client.get(url)
        headers = dashboard_headers(client)
        unfinished = client.get(url, headers=headers)
        forbidden = client.get(
            f"/api/v2/replay-sessions/{foreign.session_id}/quality-report",
            headers=headers,
        )
        missing = client.get(
            "/api/v2/replay-sessions/missing/quality-report",
            headers=headers,
        )
    assert unauthorized.status_code == 401
    assert unfinished.status_code == 409
    assert forbidden.status_code == 403
    assert missing.status_code == 404


def test_internal_quality_report_remains_backward_compatible(
    isolated_database: Path,
) -> None:
    session = prepare(isolated_database, [1000, 2000])
    complete(session)
    with TestClient(app) as client:
        headers = dashboard_headers(client)
        internal = client.get(
            f"/internal/replay/{session.session_id}/quality-report",
            headers=headers,
        )
        public = client.get(
            f"/api/v2/replay-sessions/{session.session_id}/quality-report",
            headers=headers,
        )
    assert internal.status_code == public.status_code == 200
    assert internal.json() == public.json()["data"]
