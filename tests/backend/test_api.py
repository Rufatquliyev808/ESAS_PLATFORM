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