from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import create_replay_session
from backend.app.database.visual_experiment_repository import register_visual_experiment
from backend.app.main import app


BASE_TIME = datetime(2026, 8, 9, 21, 0, tzinfo=UTC)


def _prepare(database_path: Path, *, owner: str = "TEST-USER"):
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    return create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )


def _headers(client: TestClient, user_code: str = "TEST-USER") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": user_code, "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _registration_payload(session_id: str, **overrides: object) -> dict[str, object]:
    payload = {
        "session_id": session_id,
        "symbol": "GOLD",
        "timeframe": "M1",
        "source_bar_fingerprint": "sha256:bars",
        "render_spec_id": "sha256:render",
        "label_spec_id": "sha256:label",
        "observation_window_bars": 64,
        "train_end_at": "2026-08-10T00:00:00+00:00",
        "validation_end_at": "2026-08-11T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def test_register_and_fetch_visual_experiment(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            "/api/v2/visual-experiments",
            json=_registration_payload(session.session_id),
            headers=headers,
        )
        assert created.status_code == 201
        data = created.json()["data"]
        assert data["lifecycle_state"] == "registered"
        assert data["state_version"] == 0

        detail = client.get(f"/api/v2/visual-experiments/{data['experiment_id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"] == data


def test_registration_requires_authentication(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        response = client.post(
            "/api/v2/visual-experiments", json=_registration_payload(session.session_id),
        )
    assert response.status_code == 401


def test_registration_for_unknown_session_returns_404(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/visual-experiments",
            json=_registration_payload("rps_does_not_exist"),
            headers=headers,
        )
    assert response.status_code == 404


def test_registration_for_another_users_session_returns_403(isolated_database: Path) -> None:
    _prepare(isolated_database, owner="TEST-USER")
    foreign_session = create_replay_session(
        created_by="OTHER-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/visual-experiments",
            json=_registration_payload(foreign_session.session_id),
            headers=headers,
        )
    assert response.status_code == 403


def test_registration_rejects_invalid_timeframe(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/visual-experiments",
            json=_registration_payload(session.session_id, timeframe="M3"),
            headers=headers,
        )
    assert response.status_code == 422


def test_registration_rejects_validation_end_at_not_after_train_end_at(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/visual-experiments",
            json=_registration_payload(
                session.session_id,
                train_end_at="2026-08-11T00:00:00+00:00",
                validation_end_at="2026-08-10T00:00:00+00:00",
            ),
            headers=headers,
        )
    assert response.status_code == 422


def test_detail_for_unknown_experiment_returns_404(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.get("/api/v2/visual-experiments/sha256:does-not-exist", headers=headers)
    assert response.status_code == 404


def test_detail_for_another_users_experiment_returns_403(isolated_database: Path) -> None:
    _prepare(isolated_database, owner="TEST-USER")
    foreign_session = create_replay_session(
        created_by="OTHER-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    foreign = register_visual_experiment(
        created_by="OTHER-USER", actor_role="operator",
        replay_session_id=foreign_session.session_id,
        **{k: v for k, v in _registration_payload(foreign_session.session_id).items() if k != "session_id"},
    )
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.get(f"/api/v2/visual-experiments/{foreign.experiment_id}", headers=headers)
    assert response.status_code == 403


def test_archive_transitions_to_archived(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            "/api/v2/visual-experiments",
            json=_registration_payload(session.session_id),
            headers=headers,
        )
        data = created.json()["data"]

        archived = client.post(
            f"/api/v2/visual-experiments/{data['experiment_id']}/archive",
            json={"expected_state_version": data["state_version"]},
            headers=headers,
        )
    assert archived.status_code == 200
    assert archived.json()["data"]["lifecycle_state"] == "archived"


def test_list_returns_registered_experiments(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        client.post(
            "/api/v2/visual-experiments", json=_registration_payload(session.session_id), headers=headers,
        )
        listing = client.get("/api/v2/visual-experiments", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert len(body["data"]) == 1
    assert body["page"]["has_more"] is False


def test_list_excludes_other_users_experiments(isolated_database: Path) -> None:
    _prepare(isolated_database, owner="TEST-USER")
    foreign_session = create_replay_session(
        created_by="OTHER-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    register_visual_experiment(
        created_by="OTHER-USER", actor_role="operator",
        replay_session_id=foreign_session.session_id,
        **{k: v for k, v in _registration_payload(foreign_session.session_id).items() if k != "session_id"},
    )
    with TestClient(app) as client:
        headers = _headers(client)
        listing = client.get("/api/v2/visual-experiments", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["data"] == []


def test_archive_with_stale_state_version_returns_409(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            "/api/v2/visual-experiments",
            json=_registration_payload(session.session_id),
            headers=headers,
        )
        data = created.json()["data"]

        response = client.post(
            f"/api/v2/visual-experiments/{data['experiment_id']}/archive",
            json={"expected_state_version": data["state_version"] + 1},
            headers=headers,
        )
    assert response.status_code == 409
