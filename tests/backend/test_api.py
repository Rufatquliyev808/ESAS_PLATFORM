from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "esas-platform-backend",
        "version": "0.1.0",
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

    assert first_response.json()["status"] in {"stored", "duplicate"}
    assert second_response.json()["status"] == "duplicate"