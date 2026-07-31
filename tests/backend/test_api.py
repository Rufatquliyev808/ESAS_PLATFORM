import sqlite3

from fastapi.testclient import TestClient
from pathlib import Path

from backend.app.main import app
from backend.app.database.connection import (
    DEFAULT_DATABASE_PATH,
    get_connection,
    verify_database_writable,
)


def dashboard_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def bridge_headers() -> dict[str, str]:
    return {"X-ESAS-Bridge-Key": "test-bridge-api-key-at-least-32-chars"}


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "esas-platform-backend",
        "version": "0.3.0",
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )

def test_tick_endpoint_rejects_invalid_event() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/events/ticks",
            headers=bridge_headers(),
            json={"event_id": "invalid-event"},
        )

    assert response.status_code == 422


def test_bridge_ingestion_requires_valid_key() -> None:
    with TestClient(app) as client:
        missing_key = client.post("/events/ticks", json={})
        wrong_key = client.post(
            "/status/bridge",
            headers={"X-ESAS-Bridge-Key": "wrong-key"},
            json={},
        )

    assert missing_key.status_code == 401
    assert missing_key.json()["detail"] == "Invalid bridge credentials"
    assert wrong_key.status_code == 401
    assert wrong_key.json()["detail"] == "Invalid bridge credentials"

def test_tick_endpoint_stores_event_only_once() -> None:
    event = {
        "event_id": "TEST:GOLD:IDEMPOTENCY:1",
        "event_type": "TICK_RECEIVED",
        "timestamp": "2026-07-27T10:00:00.000Z",
        "source": "esas.mt5.bridge",
        "version": "1.0",
        "symbol": "GOLD",
        "payload": {
            "bid": 4052.66,
            "ask": 4053.19,
            "last": 4052.66,
            "volume": 1,
            "flags": 6,
            "source_time_msc": 1785146400000,
        },
        "metadata": {
            "module_version": "0.2.0",
        },
    }

    with TestClient(app) as client:
        first_response = client.post(
            "/events/ticks",
            headers=bridge_headers(),
            json=event,
        )
        second_response = client.post(
            "/events/ticks",
            headers=bridge_headers(),
            json=event,
        )

    assert first_response.status_code == 202
    assert second_response.status_code == 202

    assert first_response.json()["status"] == "stored"
    assert second_response.json()["status"] == "duplicate"

def test_tick_statistics_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/statistics/ticks",
            headers=dashboard_headers(client),
        )

    assert response.status_code == 200

    data = response.json()

    assert "total_ticks" in data
    assert "unique_event_ids" in data
    assert "duplicate_rows" in data
    assert data["total_ticks"] >= data["unique_event_ids"]
    assert data["duplicate_rows"] == (
        data["total_ticks"] - data["unique_event_ids"]
    )

def test_operational_status_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/status/operational",
            headers=dashboard_headers(client),
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] in {"ok", "degraded"}
    assert data["database"]["exists"] is True
    assert Path(data["database"]["path"]) != DEFAULT_DATABASE_PATH
    assert Path(data["database"]["path"]).name == "ESAS_PLATFORM_TEST.sqlite"
    assert data["tick_stream"]["status"] in {"waiting", "active", "stale"}
    assert data["tick_stream"]["stale_after_seconds"] == 30
    assert data["tick_stream"]["total_ticks"] >= 0
    assert data["bridge_delivery"]["status"] in {
        "waiting",
        "healthy",
        "degraded",
    }
    assert isinstance(data["bridge_delivery"]["bridges"], list)


def test_database_write_probe_leaves_no_schema_artifact() -> None:
    verify_database_writable()

    with get_connection() as connection:
        probe_table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = '__esas_write_probe';
            """
        ).fetchone()

    assert probe_table is None


def test_health_reports_unwritable_database(
    monkeypatch,
) -> None:
    with TestClient(app) as client:
        def fail_write_probe() -> None:
            raise sqlite3.OperationalError("attempt to write a readonly database")

        monkeypatch.setattr(
            "backend.app.main.verify_database_writable",
            fail_write_probe,
        )
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is not writable"}


def test_bridge_status_is_exposed_by_operational_endpoint() -> None:
    report = {
        "source": "esas.mt5.bridge",
        "module_version": "1.5.0",
        "symbol": "TEST_FULL",
        "queue_status": "full",
        "queue_count": 10,
        "queue_capacity": 10,
        "rejected_events": 3,
        "last_queue_error": "queue_full",
    }

    with TestClient(app) as client:
        post_response = client.post(
            "/status/bridge",
            headers=bridge_headers(),
            json=report,
        )
        status_response = client.get(
            "/status/operational",
            headers=dashboard_headers(client),
        )

    assert post_response.status_code == 202
    assert post_response.json()["status"] == "accepted"
    assert status_response.status_code == 200

    data = status_response.json()

    assert data["status"] == "degraded"
    assert data["bridge_delivery"]["status"] == "degraded"

    bridge = next(
        item
        for item in data["bridge_delivery"]["bridges"]
        if item["symbol"] == "TEST_FULL"
    )

    assert bridge["queue_status"] == "full"
    assert bridge["queue_count"] == 10
    assert bridge["queue_capacity"] == 10
    assert bridge["rejected_events"] == 3
    assert bridge["last_queue_error"] == "queue_full"
    assert bridge["reported_at"].endswith("Z")


def test_bridge_status_rejects_inconsistent_queue_count() -> None:
    report = {
        "source": "esas.mt5.bridge",
        "module_version": "1.5.0",
        "symbol": "TEST_INVALID",
        "queue_status": "healthy",
        "queue_count": 11,
        "queue_capacity": 10,
        "rejected_events": 0,
        "last_queue_error": "none",
    }

    with TestClient(app) as client:
        response = client.post(
            "/status/bridge",
            headers=bridge_headers(),
            json=report,
        )

    assert response.status_code == 422


def test_data_loss_acknowledgement_is_audited_and_versioned() -> None:
    report = {
        "source": "esas.mt5.bridge",
        "module_version": "1.5.0",
        "symbol": "TEST_ACK",
        "queue_status": "healthy",
        "queue_count": 0,
        "queue_capacity": 10,
        "rejected_events": 7,
        "last_queue_error": "queue_full",
    }

    with TestClient(app) as client:
        headers = dashboard_headers(client)
        assert client.post(
            "/status/bridge",
            headers=bridge_headers(),
            json=report,
        ).status_code == 202

        before = client.get(
            "/status/operational",
            headers=headers,
        ).json()
        before_bridge = next(
            item
            for item in before["bridge_delivery"]["bridges"]
            if item["symbol"] == "TEST_ACK"
        )
        assert before_bridge["loss_acknowledged"] is False

        acknowledgement = client.post(
            "/status/loss/acknowledge",
            headers=headers,
            json={
                "source": "esas.mt5.bridge",
                "symbol": "TEST_ACK",
            },
        )
        assert acknowledgement.status_code == 200
        assert acknowledgement.json()["status"] == "acknowledged"
        assert acknowledgement.json()["rejected_events"] == 7
        assert acknowledgement.json()["acknowledged_by"] == "TEST-USER"

        after = client.get(
            "/status/operational",
            headers=headers,
        ).json()
        after_bridge = next(
            item
            for item in after["bridge_delivery"]["bridges"]
            if item["symbol"] == "TEST_ACK"
        )
        assert after_bridge["loss_acknowledged"] is True
        assert after_bridge["acknowledged_rejected_events"] == 7
        assert after_bridge["loss_acknowledged_at"].endswith("Z")

        report["rejected_events"] = 8
        assert client.post(
            "/status/bridge",
            headers=bridge_headers(),
            json=report,
        ).status_code == 202
        increased = client.get(
            "/status/operational",
            headers=headers,
        ).json()
        increased_bridge = next(
            item
            for item in increased["bridge_delivery"]["bridges"]
            if item["symbol"] == "TEST_ACK"
        )
        assert increased_bridge["loss_acknowledged"] is False

    with get_connection() as connection:
        audit_rows = connection.execute(
            """
            SELECT COUNT(*) AS acknowledgement_count
            FROM loss_acknowledgements
            WHERE source = ? AND symbol = ?;
            """,
            ("esas.mt5.bridge", "TEST_ACK"),
        ).fetchone()

    assert audit_rows["acknowledgement_count"] == 1


def test_dashboard_endpoints_require_login() -> None:
    with TestClient(app) as client:
        statistics_response = client.get("/statistics/ticks")
        status_response = client.get("/status/operational")
        acknowledgement_response = client.post(
            "/status/loss/acknowledge",
            json={
                "source": "esas.mt5.bridge",
                "symbol": "GOLD",
            },
        )

    assert statistics_response.status_code == 401
    assert status_response.status_code == 401
    assert acknowledgement_response.status_code == 401


def test_login_rejects_wrong_password() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={"user_code": "TEST-USER", "password": "wrong-password"},
        )

    assert response.status_code == 401


def test_login_rate_limit_blocks_repeated_failures() -> None:
    with TestClient(app) as client:
        for _ in range(4):
            response = client.post(
                "/auth/login",
                json={
                    "user_code": "TEST-USER",
                    "password": "wrong-password",
                },
            )
            assert response.status_code == 401

        blocked_response = client.post(
            "/auth/login",
            json={
                "user_code": "TEST-USER",
                "password": "wrong-password",
            },
        )
        correct_password_while_blocked = client.post(
            "/auth/login",
            json={
                "user_code": "TEST-USER",
                "password": "test-password-123",
            },
        )

    assert blocked_response.status_code == 429
    assert int(blocked_response.headers["retry-after"]) > 0
    assert correct_password_while_blocked.status_code == 429


def test_successful_login_clears_previous_failures() -> None:
    with TestClient(app) as client:
        for _ in range(4):
            assert client.post(
                "/auth/login",
                json={
                    "user_code": "TEST-USER",
                    "password": "wrong-password",
                },
            ).status_code == 401

        successful_response = client.post(
            "/auth/login",
            json={
                "user_code": "TEST-USER",
                "password": "test-password-123",
            },
        )
        next_failure = client.post(
            "/auth/login",
            json={
                "user_code": "TEST-USER",
                "password": "wrong-password",
            },
        )

    assert successful_response.status_code == 200
    assert next_failure.status_code == 401


def test_logout_revokes_dashboard_session() -> None:
    with TestClient(app) as client:
        headers = dashboard_headers(client)
        assert client.get("/status/operational", headers=headers).status_code == 200

        logout_response = client.post("/auth/logout", headers=headers)
        rejected_after_logout = client.get(
            "/status/operational",
            headers=headers,
        )

    assert logout_response.status_code == 204
    assert rejected_after_logout.status_code == 401
