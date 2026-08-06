from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.main import app


def _prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def _headers(client: TestClient, user_code: str = "TEST-USER") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": user_code, "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_payload(risk_budget: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "planned_end_at": "2026-09-01T00:00:00+00:00",
        "code_commit": "abc123",
        "config_hash": "sha256:config",
        "feature_claim_versions": ["market_structure:1.0.0"],
        "symbols": ["GOLD"],
        "timeframes": ["M5"],
        "sessions": ["london"],
        "accepted_market_regimes": ["trending"],
        "minimum_market_open_duration_seconds": 3600,
        "minimum_eligible_decision_count": 30,
        "primary_metric": "net_return_percent",
        "primary_metric_threshold": 0.5,
        "secondary_metrics": {},
        "failure_rules": {},
        "theoretical_fill_model": {},
        "risk_budget": risk_budget or {},
        "data_quality_policy": {},
        "approved_by": "RISK-OFFICER",
        "rollback_plan": "halt and archive run",
        "participants": [{"role": "champion", "module_id": "structure_break_long", "module_version": "1.0.0"}],
    }


def test_create_and_get_shadow_run(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers)
        assert created.status_code == 200
        run_id = created.json()["data"]["shadow_run_id"]
        assert created.json()["data"]["execution_allowed"] is False
        assert created.json()["data"]["state"] == "registered"

        detail = client.get(f"/api/v2/shadow-runs/{run_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"]["shadow_run_id"] == run_id


def test_create_rejects_invalid_participants(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        payload = _create_payload()
        payload["participants"] = [
            {"role": "challenger", "module_id": "a", "module_version": "1.0.0"},
        ]
        response = client.post("/api/v2/shadow-runs", json=payload, headers=headers)
        assert response.status_code == 422


def test_unauthenticated_request_is_rejected(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        response = client.post("/api/v2/shadow-runs", json=_create_payload())
    assert response.status_code == 401


def test_list_shadow_runs_returns_created_run(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers)
        run_id = created.json()["data"]["shadow_run_id"]
        listed = client.get("/api/v2/shadow-runs", headers=headers)
    assert listed.status_code == 200
    assert any(item["shadow_run_id"] == run_id for item in listed.json()["data"])


def test_missing_shadow_run_returns_404(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.get("/api/v2/shadow-runs/missing", headers=headers)
    assert response.status_code == 404


def test_lifecycle_start_then_complete(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        started = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/start",
            json={"expected_state_version": created["state_version"]}, headers=headers,
        ).json()["data"]
        assert started["state"] == "started"
        completed = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/complete",
            json={"expected_state_version": started["state_version"]}, headers=headers,
        )
    assert completed.status_code == 200
    assert completed.json()["data"]["state"] == "completed"


def test_halt_from_registered_records_reason(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        halted = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/halt",
            json={"expected_state_version": created["state_version"], "reason": "order adapter call attempted"},
            headers=headers,
        )
    assert halted.status_code == 200
    assert halted.json()["data"]["state"] == "halted"
    assert halted.json()["data"]["halt_reason"] == "order adapter call attempted"


def test_stale_state_version_returns_409(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        response = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/start",
            json={"expected_state_version": created["state_version"] + 1}, headers=headers,
        )
    assert response.status_code == 409


def test_record_and_list_events(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        run_id = created["shadow_run_id"]
        recorded = client.post(
            f"/api/v2/shadow-runs/{run_id}/events",
            json={"event_type": "SHADOW_RUN_STARTED", "correlation_id": "corr-1", "payload": {"note": "manual"}},
            headers=headers,
        )
        assert recorded.status_code == 200
        listed = client.get(f"/api/v2/shadow-runs/{run_id}/events", headers=headers)
    assert listed.status_code == 200
    assert any(item["event_id"] == recorded.json()["data"]["event_id"] for item in listed.json()["data"])


def test_record_event_rejects_unsupported_type(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        response = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/events",
            json={"event_type": "ORDER_PLACED", "correlation_id": "corr-1", "payload": {}}, headers=headers,
        )
    assert response.status_code == 422


def test_open_list_close_position_and_summary_updates(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        run_id = created["shadow_run_id"]
        participant_id = created["participants"][0]["participant_id"]

        opened = client.post(
            f"/api/v2/shadow-runs/{run_id}/positions",
            json={
                "participant_id": participant_id, "symbol": "GOLD", "direction": "long",
                "theoretical_size": 1.0, "reserved_risk_amount": 2.0, "correlation_id": "corr-1",
            },
            headers=headers,
        )
        assert opened.status_code == 200
        assert opened.json()["data"]["opened"] is True
        position_id = opened.json()["data"]["position"]["position_id"]

        listed = client.get(f"/api/v2/shadow-runs/{run_id}/positions", headers=headers)
        assert any(item["position_id"] == position_id for item in listed.json()["data"])

        summary_before = client.get(f"/api/v2/shadow-runs/{run_id}/portfolio-summary", headers=headers).json()["data"]
        assert summary_before["open_position_count"] == 1
        assert summary_before["total_reserved_risk_amount"] == 2.0

        closed = client.post(
            f"/api/v2/shadow-runs/{run_id}/positions/{position_id}/close",
            json={"theoretical_pnl_percent": 1.5, "expected_state_version": 0, "correlation_id": "corr-2"},
            headers=headers,
        )
        assert closed.status_code == 200
        assert closed.json()["data"]["state"] == "closed"

        summary_after = client.get(f"/api/v2/shadow-runs/{run_id}/portfolio-summary", headers=headers).json()["data"]
        assert summary_after["open_position_count"] == 0
        assert summary_after["net_realized_theoretical_pnl_percent"] == 1.5


def test_position_open_blocked_by_risk_budget(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            "/api/v2/shadow-runs", json=_create_payload(risk_budget={"max_concurrent_positions": 1}), headers=headers,
        ).json()["data"]
        run_id = created["shadow_run_id"]
        participant_id = created["participants"][0]["participant_id"]
        body = {
            "participant_id": participant_id, "symbol": "GOLD", "direction": "long",
            "theoretical_size": 1.0, "reserved_risk_amount": 1.0, "correlation_id": "corr-1",
        }
        first = client.post(f"/api/v2/shadow-runs/{run_id}/positions", json=body, headers=headers)
        assert first.json()["data"]["opened"] is True
        second = client.post(f"/api/v2/shadow-runs/{run_id}/positions", json=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["opened"] is False
    assert second.json()["data"]["reason"] == "max_concurrent_positions_exceeded"


def test_close_position_from_wrong_run_returns_404(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        first_run = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        second_run = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        opened = client.post(
            f"/api/v2/shadow-runs/{first_run['shadow_run_id']}/positions",
            json={
                "participant_id": first_run["participants"][0]["participant_id"], "symbol": "GOLD",
                "direction": "long", "theoretical_size": 1.0, "reserved_risk_amount": 1.0,
                "correlation_id": "corr-1",
            },
            headers=headers,
        ).json()["data"]["position"]
        response = client.post(
            f"/api/v2/shadow-runs/{second_run['shadow_run_id']}/positions/{opened['position_id']}/close",
            json={"theoretical_pnl_percent": 1.0, "expected_state_version": 0, "correlation_id": "corr-2"},
            headers=headers,
        )
    assert response.status_code == 404
