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
    base_time = end_anchor.replace(second=0, microsecond=0) - timedelta(minutes=20)
    rows = []
    price = 4270.0
    index = 0
    for minute in range(20):
        for second in range(0, 60, 5):
            ts = base_time + timedelta(minutes=minute, seconds=second)
            price += 0.05 if (minute + second) % 3 else -0.03
            index += 1
            rows.append((
                f"GOLD:overview-api:{index:05d}",
                ts.isoformat(timespec="microseconds"),
                ts.isoformat(timespec="microseconds"),
                round(price, 2), round(price + 0.4, 2), round(price + 0.2, 2),
                int(ts.timestamp() * 1000),
            ))
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, received_at, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            ) VALUES (?, 'TICK_RECEIVED', ?, ?, 'esas.mt5.bridge', '1.0',
                      'GOLD', ?, ?, ?, 1, 6, ?, '1.6.1', '{}');
            """,
            [(row[0], row[1], row[2], row[3], row[4], row[5], row[6]) for row in rows],
        )


def _headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": "TEST-USER", "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_liquidity_overview_is_protected_deterministic_and_research_only(
    isolated_database: Path,
) -> None:
    _seed_recent_ticks(isolated_database)
    url = "/api/v2/liquidity-overview?symbol=GOLD"
    with TestClient(app) as client:
        assert client.get(url).status_code == 401
        headers = _headers(client)
        response = client.get(url, headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["symbol"] == "GOLD"
    assert data["interpretation"] == "research_observation_not_trading_signal"
    assert [item["timeframe"] for item in data["timeframes"]] == ["M30", "H1", "H4", "D1"]
    for overview in data["timeframes"]:
        assert overview["status"] in ("completed", "insufficient_data")
    # "buy_side"/"sell_side" are pre-existing liquidity-pool-side labels from
    # Phase 4's liquidity_sweep.py (structural, not action language), so they
    # are not checked here the way a bare "buy"/"sell" verb would be.
    serialized = str(response.json()).lower()
    assert "'order'" not in serialized
    assert "position_size" not in serialized
    assert "gözlənilir" not in serialized
    assert "expected" not in serialized


def test_liquidity_overview_rejects_unsafe_parameters(isolated_database: Path) -> None:
    _seed_recent_ticks(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        invalid_symbol = client.get("/api/v2/liquidity-overview?symbol=", headers=headers)
        invalid_horizon = client.get("/api/v2/liquidity-overview?horizon_bars=0", headers=headers)
        invalid_threshold = client.get(
            "/api/v2/liquidity-overview?reaction_threshold_bps=0", headers=headers,
        )
    assert invalid_symbol.status_code == 422
    assert invalid_horizon.status_code == 422
    assert invalid_threshold.status_code == 422
