from fastapi.testclient import TestClient
from pathlib import Path

from backend.app.main import app
from backend.app.database.connection import DEFAULT_DATABASE_PATH


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "esas-platform-backend",
        "version": "0.2.0",
    }

def test_tick_endpoint_rejects_invalid_event() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/events/ticks",
            json={"event_id": "invalid-event"},
        )

    assert response.status_code == 422

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
        first_response = client.post("/events/ticks", json=event)
        second_response = client.post("/events/ticks", json=event)

    assert first_response.status_code == 202
    assert second_response.status_code == 202

    assert first_response.json()["status"] == "stored"
    assert second_response.json()["status"] == "duplicate"

def test_tick_statistics_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/statistics/ticks")

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
        response = client.get("/status/operational")

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
        post_response = client.post("/status/bridge", json=report)
        status_response = client.get("/status/operational")

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
        response = client.post("/status/bridge", json=report)

    assert response.status_code == 422
