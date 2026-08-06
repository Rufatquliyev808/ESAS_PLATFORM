from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.main import app


def _seed_recent_ticks(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_anchor = datetime.now(UTC) - timedelta(minutes=5)
    base_time = end_anchor.replace(second=0, microsecond=0)
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
                    f"GOLD:live:{index:04d}",
                    (base_time + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
                    (base_time + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
                    4100.0 + index,
                    4100.4 + index,
                    4100.2 + index,
                    int(base_time.timestamp() * 1000) + index * 5_000,
                )
                for index in range(1, 36)
            ],
        )


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_live_technical_summary_is_protected_and_research_only(isolated_database: Path) -> None:
    _seed_recent_ticks(isolated_database)
    url = (
        "/api/v2/live-technical-summary"
        "?symbol=GOLD&timeframe=M1&ema_period=2&rsi_period=2&atr_period=2&bar_limit=10"
    )
    with TestClient(app) as client:
        assert client.get(url).status_code == 401
        headers = _headers(client)
        response = client.get(url, headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["symbol"] == "GOLD"
    assert data["timeframe"] == "M1"
    assert data["interpretation"] == "research_observation_not_trading_signal"
    assert data["lineage"]["bar_count"] == 3
    assert data["lineage"]["reproducible"] is False
    consensus = data["consensus"]
    assert consensus["version"] == "1.0.0"
    assert consensus["interpretation"] == "research_observation_not_trading_signal"
    assert consensus["overall_summary"]["overall_lean"] in {
        "bullish_leaning", "bearish_leaning", "neutral", "insufficient_data",
    }
    serialized = str(response.json()).lower()
    assert "'order'" not in serialized
    assert "buy" not in serialized
    assert "sell" not in serialized
    assert "position_size" not in serialized


def test_live_technical_summary_rejects_unsafe_parameters(isolated_database: Path) -> None:
    _seed_recent_ticks(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        invalid_timeframe = client.get(
            "/api/v2/live-technical-summary?timeframe=M2", headers=headers,
        )
        invalid_bar_limit = client.get(
            "/api/v2/live-technical-summary?bar_limit=0", headers=headers,
        )
        invalid_symbol = client.get(
            "/api/v2/live-technical-summary?symbol=", headers=headers,
        )
    assert invalid_timeframe.status_code == 422
    assert invalid_bar_limit.status_code == 422
    assert invalid_symbol.status_code == 422


def test_live_technical_summary_handles_no_recent_ticks(isolated_database: Path) -> None:
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    with TestClient(app) as client:
        response = client.get(
            "/api/v2/live-technical-summary?symbol=UNKNOWN&timeframe=M1&bar_limit=5",
            headers=_headers(client),
        )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lineage"]["bar_count"] == 0
    assert data["consensus"] is None
