from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.analysis.liquidity_overview import (
    COMPLETED,
    INSUFFICIENT_DATA,
    LIQUIDITY_OVERVIEW_API_VERSION,
    create_liquidity_overview,
)
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations


def _seed_recent_ticks(database_path: Path, *, minutes: int = 20, symbol: str = "GOLD") -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_anchor = datetime.now(UTC) - timedelta(minutes=5)
    base_time = end_anchor.replace(second=0, microsecond=0) - timedelta(minutes=minutes)
    rows = []
    price = 4270.0
    index = 0
    for minute in range(minutes):
        for second in range(0, 60, 5):
            ts = base_time + timedelta(minutes=minute, seconds=second)
            price += 0.05 if (minute + second) % 3 else -0.03
            index += 1
            rows.append((
                f"{symbol}:overview:{index:05d}",
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
            ) VALUES (?, 'TICK_RECEIVED', ?, ?, ?, '1.0',
                      ?, ?, ?, ?, 1, 6, ?, '1.6.1', '{}');
            """,
            [(row[0], row[1], row[2], row[0], symbol, row[3], row[4], row[5], row[6]) for row in rows],
        )


def test_create_liquidity_overview_covers_requested_timeframes(isolated_database: Path) -> None:
    _seed_recent_ticks(isolated_database, minutes=20)
    result = create_liquidity_overview(
        symbol="GOLD", timeframes=("S10", "M1"),
        bar_limits={"S10": 200, "M1": 20},
    )
    assert result.symbol == "GOLD"
    assert result.api_version == LIQUIDITY_OVERVIEW_API_VERSION
    assert result.interpretation == "research_observation_not_trading_signal"
    assert [item.timeframe for item in result.timeframes] == ["S10", "M1"]
    for overview in result.timeframes:
        assert overview.status in (COMPLETED, INSUFFICIENT_DATA)
        if overview.status == COMPLETED:
            assert overview.latest_close is not None
            assert overview.trend in ("bullish", "bearish", "neutral", "insufficient_data")
            assert "buy_side_statistics" in overview.reaction
            assert set(overview.segments.keys()) == {"buy_side", "sell_side"}


def test_create_liquidity_overview_handles_symbol_with_no_ticks(isolated_database: Path) -> None:
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    result = create_liquidity_overview(symbol="UNKNOWN", timeframes=("M1",), bar_limits={"M1": 10})
    assert result.timeframes[0].status == INSUFFICIENT_DATA
    assert result.timeframes[0].bar_count == 0
    assert result.timeframes[0].nearest_resistance is None
    assert result.timeframes[0].nearest_support is None


def test_rejects_unsafe_parameters(isolated_database: Path) -> None:
    _seed_recent_ticks(isolated_database, minutes=5)
    try:
        create_liquidity_overview(symbol=" ", timeframes=("M1",))
    except ValueError as error:
        assert "symbol" in str(error)
    else:
        raise AssertionError("expected a ValueError for empty symbol")

    try:
        create_liquidity_overview(symbol="GOLD", timeframes=("BAD",))
    except ValueError as error:
        assert "timeframe" in str(error).lower()
    else:
        raise AssertionError("expected a ValueError for an unsupported timeframe")

    try:
        create_liquidity_overview(symbol="GOLD", timeframes=())
    except ValueError as error:
        assert "timeframes" in str(error)
    else:
        raise AssertionError("expected a ValueError for empty timeframes")
