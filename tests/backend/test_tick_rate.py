from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.tick_rate import (
    COMPLETED,
    INSUFFICIENT_DATA,
    TICK_RATE_VERSION,
    compute_tick_rate_statistics,
)
from backend.app.database.tick_replay_repository import ReplayTick


BASE_TIME = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)


def _tick(index: int, timestamp: datetime, *, symbol: str = "GOLD") -> ReplayTick:
    return ReplayTick(
        event_id=f"event:{index:04d}",
        event_type="TICK_RECEIVED",
        event_timestamp=timestamp.isoformat(timespec="microseconds"),
        received_at=timestamp.isoformat(timespec="microseconds"),
        symbol=symbol,
        bid=100.0,
        ask=100.2,
        last=100.1,
        volume=1,
        flags=6,
        source_time_msc=int(timestamp.timestamp() * 1000),
        source="esas.mt5.bridge",
        event_version="1.0",
        module_version="1.6.0",
    )


def test_hand_verified_interval_percentiles_for_thirty_gaps() -> None:
    ticks = [_tick(0, BASE_TIME)]
    cumulative_micro = 0
    for k in range(1, 31):
        cumulative_micro += k * 100_000  # gap_k = k * 0.1s, exact in microseconds
        ticks.append(_tick(k, BASE_TIME + timedelta(microseconds=cumulative_micro)))

    result = compute_tick_rate_statistics(
        ticks, symbol="GOLD", timeframe="H1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(hours=1),
        minimum_sample=30,
    )
    assert result.version == TICK_RATE_VERSION
    interval = result.interval_seconds
    assert interval.status == COMPLETED
    assert interval.n_valid == 30
    assert interval.minimum == pytest.approx(0.1)
    assert interval.maximum == pytest.approx(3.0)
    assert interval.mean == pytest.approx(1.55)
    assert interval.median == pytest.approx(1.55)
    assert interval.p95 == pytest.approx(2.855)
    assert interval.p99 == pytest.approx(2.971)
    assert result.same_timestamp_tick_count == 0


def test_window_bucketing_matches_bars_epoch_alignment() -> None:
    offsets = [0, 10, 20, 30, 40, 50, 60, 72, 84, 96, 108, 120, 135, 150, 165]
    ticks = [_tick(index, BASE_TIME + timedelta(seconds=offset)) for index, offset in enumerate(offsets)]
    result = compute_tick_rate_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3),
        minimum_sample=3,
    )
    assert result.total_window_count == 3
    assert result.populated_window_count == 3
    assert result.empty_window_count == 0
    assert result.window_tick_count.status == COMPLETED
    assert result.window_tick_count.minimum == pytest.approx(4.0)
    assert result.window_tick_count.maximum == pytest.approx(6.0)
    assert result.window_tick_count.mean == pytest.approx(5.0)
    assert result.window_ticks_per_second.maximum == pytest.approx(6.0 / 60.0)


def test_empty_windows_are_counted_separately() -> None:
    ticks = [
        _tick(0, BASE_TIME + timedelta(seconds=5)),
        _tick(1, BASE_TIME + timedelta(seconds=125)),
    ]
    result = compute_tick_rate_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3),
        minimum_sample=1,
    )
    assert result.total_window_count == 3
    assert result.populated_window_count == 2
    assert result.empty_window_count == 1


def test_same_timestamp_ticks_are_counted() -> None:
    ticks = [
        _tick(0, BASE_TIME),
        _tick(1, BASE_TIME),
        _tick(2, BASE_TIME + timedelta(seconds=5)),
    ]
    result = compute_tick_rate_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        minimum_sample=1,
    )
    assert result.same_timestamp_tick_count == 1
    assert result.interval_seconds.n_valid == 2
    assert result.interval_seconds.minimum == pytest.approx(0.0)


def test_empty_ticks_is_a_valid_insufficient_data_input() -> None:
    result = compute_tick_rate_statistics(
        [], symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3),
    )
    assert result.total_window_count == 3
    assert result.populated_window_count == 0
    assert result.empty_window_count == 3
    assert result.window_tick_count.status == INSUFFICIENT_DATA
    assert result.interval_seconds.status == INSUFFICIENT_DATA
    assert result.same_timestamp_tick_count == 0
    assert result.symbol == "GOLD"
    assert result.timeframe == "M1"


def test_ticks_outside_requested_range_are_excluded() -> None:
    ticks = [
        _tick(0, BASE_TIME - timedelta(seconds=10)),
        _tick(1, BASE_TIME + timedelta(seconds=10)),
        _tick(2, BASE_TIME + timedelta(minutes=5)),
    ]
    result = compute_tick_rate_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        minimum_sample=1,
    )
    assert result.populated_window_count == 1
    assert result.window_tick_count.n_valid == 1
    assert result.interval_seconds.status == INSUFFICIENT_DATA
    assert result.interval_seconds.n_total == 0


def test_deterministic_fingerprint_for_same_input() -> None:
    ticks = [_tick(index, BASE_TIME + timedelta(seconds=index * 5)) for index in range(5)]
    first = compute_tick_rate_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    second = compute_tick_rate_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    assert first.fingerprint == second.fingerprint
    third = compute_tick_rate_statistics(
        ticks[:3], symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    assert third.fingerprint != first.fingerprint


def test_rejects_unsafe_parameters() -> None:
    ticks = [_tick(0, BASE_TIME)]
    with pytest.raises(ValueError, match="timeframe"):
        compute_tick_rate_statistics(
            ticks, symbol="GOLD", timeframe="M2",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="minimum_sample"):
        compute_tick_rate_statistics(
            ticks, symbol="GOLD", timeframe="M1",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=0,
        )
    with pytest.raises(ValueError, match="symbol"):
        compute_tick_rate_statistics(
            ticks, symbol=" ", timeframe="M1",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="start_at"):
        compute_tick_rate_statistics(
            ticks, symbol="GOLD", timeframe="M1", start_at=BASE_TIME, end_at=BASE_TIME,
        )
    with pytest.raises(ValueError, match="symbol"):
        compute_tick_rate_statistics(
            [_tick(0, BASE_TIME, symbol="OIL")], symbol="GOLD", timeframe="M1",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="timezone"):
        compute_tick_rate_statistics(
            ticks, symbol="GOLD", timeframe="M1",
            start_at=datetime(2026, 8, 7, 10, 0), end_at=BASE_TIME + timedelta(minutes=1),
        )
