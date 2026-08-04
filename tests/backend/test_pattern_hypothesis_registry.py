from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.strategies.pattern_hypothesis_registry import get_pattern_hypothesis_registry


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"user_code": "TEST-USER", "password": "test-password-123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_registry_is_deterministic_separate_and_research_only() -> None:
    first = get_pattern_hypothesis_registry()
    second = get_pattern_hypothesis_registry()
    assert first == second
    assert first["fingerprint"].startswith("sha256:")
    ids = [item["hypothesis_id"] for item in first["hypotheses"]]
    assert len(ids) == len(set(ids)) == 7
    assert {item["direction"] for item in first["hypotheses"]} == {"long", "short", "neutral"}
    assert all(item["lifecycle"] == "idea" for item in first["hypotheses"])
    assert "no_order" in first["execution_boundary"]


def test_registry_api_is_protected_and_read_only() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v2/research/pattern-hypotheses").status_code == 401
        response = client.get("/api/v2/research/pattern-hypotheses", headers=_headers(client))
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["registry_version"] == "1.0.0"
    assert data["interpretation"] == "research_hypothesis_not_trading_signal"
    serialized = str(data).lower()
    assert "position_size" not in serialized
    assert "buy" not in serialized
    assert "sell" not in serialized
