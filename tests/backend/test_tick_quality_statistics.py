from datetime import UTC, datetime, timedelta
from pathlib import Path
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.quality.statistics import calculate_tick_quality_statistics

BASE = datetime(2026, 8, 4, tzinfo=UTC)

def seed(path: Path, prices: list[tuple[float, float]]) -> None:
    initialize_database(); apply_migrations(path, application_version="0.3.0")
    with get_connection() as connection:
        for number, (bid, ask) in enumerate(prices):
            moment = BASE + timedelta(seconds=number * number)
            timestamp = moment.isoformat(timespec="microseconds")
            connection.execute("""INSERT INTO tick_events
                (event_id, event_type, event_timestamp, received_at, source,
                 event_version, symbol, bid, ask, last, volume, flags,
                 source_time_msc, module_version, raw_event_json)
                VALUES (?, 'TICK_RECEIVED', ?, ?, 'esas.mt5.bridge', '1.0',
                        'GOLD', ?, ?, 0, 1, 6, ?, '1.6.0', '{}')""",
                (f"GOLD:{number}", timestamp, timestamp, bid, ask,
                 int(moment.timestamp() * 1000)))

def stats(batch_size: int = 1000):
    return calculate_tick_quality_statistics(symbol="GOLD", start_at=BASE, end_at=BASE + timedelta(seconds=60), batch_size=batch_size)

def test_statistics_are_deterministic_and_batch_independent(isolated_database: Path) -> None:
    seed(isolated_database, [(10, 11), (20, 22), (30, 33), (40, 44), (50, 55)])
    result = stats(1)
    assert result == stats(3)
    assert result.tick_count == 5
    assert result.interval_seconds.minimum == 1
    assert result.interval_seconds.median == 3
    assert result.interval_seconds.p95 == 7
    assert result.spread.minimum == 1
    assert result.spread.median == 3
    assert result.spread.p95 == 5

def test_zero_and_partial_prices_are_separate(isolated_database: Path) -> None:
    seed(isolated_database, [(0, 0), (0, 2), (2, 0), (2, 3)])
    result = stats()
    assert (result.zero_price_pairs, result.partial_price_pairs, result.spread.count) == (1, 2, 1)

def test_empty_range_is_safe(isolated_database: Path) -> None:
    seed(isolated_database, [])
    result = stats()
    assert result.tick_count == 0
    assert result.interval_seconds.minimum is None
    assert result.spread.p95 is None
