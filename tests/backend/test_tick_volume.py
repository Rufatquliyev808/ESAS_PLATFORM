from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.tick_volume import (
    COMPLETED,
    INSUFFICIENT_DATA,
    TICK_VOLUME_VERSION,
    compute_tick_volume_statistics,
)
from backend.app.database.tick_replay_repository import ReplayTick


BASE_TIME = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)


def _tick(
    index: int, timestamp: datetime, *, symbol: str = "GOLD",
    volume: int = 1, flags: int = 6, module_version: str = "1.6.0", event_version: str = "1.0",
) -> ReplayTick:
    return ReplayTick(
        event_id=f"event:{index:04d}",
        event_type="TICK_RECEIVED",
        event_timestamp=timestamp.isoformat(timespec="microseconds"),
        received_at=timestamp.isoformat(timespec="microseconds"),
        symbol=symbol,
        bid=100.0,
        ask=100.2,
        last=100.1,
        volume=volume,
        flags=flags,
        source_time_msc=int(timestamp.timestamp() * 1000),
        source="esas.mt5.bridge",
        event_version=event_version,
        module_version=module_version,
    )


def test_hand_verified_percentiles_for_thirty_ticks() -> None:
    ticks = [
        _tick(index, BASE_TIME + timedelta(seconds=index), volume=index + 1)
        for index in range(30)
    ]
    result = compute_tick_volume_statistics(
        ticks, symbol="GOLD", timeframe="H1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(hours=1),
        minimum_sample=30,
    )
    assert result.version == TICK_VOLUME_VERSION
    assert result.n_total == 30
    assert result.n_zero_volume == 0
    assert result.n_positive_volume == 30
    distribution = result.tick_volume
    assert distribution.status == COMPLETED
    assert distribution.minimum == pytest.approx(1.0)
    assert distribution.maximum == pytest.approx(30.0)
    assert distribution.mean == pytest.approx(15.5)
    assert distribution.median == pytest.approx(15.5)
    assert distribution.p95 == pytest.approx(28.55)
    assert distribution.p99 == pytest.approx(29.71)


def test_zero_and_positive_volume_are_counted_separately() -> None:
    ticks = [
        _tick(0, BASE_TIME, volume=0),
        _tick(1, BASE_TIME + timedelta(seconds=1), volume=0),
        _tick(2, BASE_TIME + timedelta(seconds=2), volume=5),
    ]
    result = compute_tick_volume_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    assert result.n_zero_volume == 2
    assert result.n_positive_volume == 1
    assert result.tick_volume.minimum == pytest.approx(0.0)
    assert result.tick_volume.maximum == pytest.approx(5.0)


def test_window_volume_sum_uses_one_point_per_populated_window() -> None:
    ticks = [
        _tick(0, BASE_TIME + timedelta(seconds=5), volume=2),
        _tick(1, BASE_TIME + timedelta(seconds=10), volume=3),
        _tick(2, BASE_TIME + timedelta(seconds=70), volume=10),
    ]
    result = compute_tick_volume_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=2), minimum_sample=2,
    )
    window_sum = result.window_volume_sum
    assert window_sum.status == COMPLETED
    assert window_sum.n_valid == 2
    assert window_sum.minimum == pytest.approx(5.0)
    assert window_sum.maximum == pytest.approx(10.0)


def test_flag_combinations_are_reported_undecoded() -> None:
    ticks = [
        _tick(0, BASE_TIME, flags=6),
        _tick(1, BASE_TIME + timedelta(seconds=1), flags=6),
        _tick(2, BASE_TIME + timedelta(seconds=2), flags=2),
    ]
    result = compute_tick_volume_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    assert result.flag_combinations[0].flags == 6
    assert result.flag_combinations[0].count == 2
    assert result.flag_combinations[1].flags == 2
    assert result.flag_combinations[1].count == 1


def test_version_segments_group_by_module_and_event_version_counts() -> None:
    ticks = [
        _tick(0, BASE_TIME, module_version="1.6.0", event_version="1.0"),
        _tick(1, BASE_TIME + timedelta(seconds=1), module_version="1.6.0", event_version="1.0"),
        _tick(2, BASE_TIME + timedelta(seconds=2), module_version="1.7.0", event_version="1.0"),
    ]
    result = compute_tick_volume_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    assert result.version_segments[0].module_version == "1.6.0"
    assert result.version_segments[0].count == 2
    assert result.version_segments[1].module_version == "1.7.0"
    assert result.version_segments[1].count == 1


def test_empty_ticks_is_a_valid_insufficient_data_input() -> None:
    result = compute_tick_volume_statistics(
        [], symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
    )
    assert result.n_total == 0
    assert result.n_zero_volume == 0
    assert result.n_positive_volume == 0
    assert result.tick_volume.status == INSUFFICIENT_DATA
    assert result.window_volume_sum.status == INSUFFICIENT_DATA
    assert result.flag_combinations == ()
    assert result.version_segments == ()
    assert result.symbol == "GOLD"


def test_deterministic_fingerprint_for_same_input() -> None:
    ticks = [_tick(index, BASE_TIME + timedelta(seconds=index * 5)) for index in range(5)]
    first = compute_tick_volume_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    second = compute_tick_volume_statistics(
        ticks, symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    assert first.fingerprint == second.fingerprint
    third = compute_tick_volume_statistics(
        ticks[:3], symbol="GOLD", timeframe="M1",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=1,
    )
    assert third.fingerprint != first.fingerprint


def test_rejects_unsafe_parameters() -> None:
    ticks = [_tick(0, BASE_TIME)]
    with pytest.raises(ValueError, match="timeframe"):
        compute_tick_volume_statistics(
            ticks, symbol="GOLD", timeframe="M2",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="minimum_sample"):
        compute_tick_volume_statistics(
            ticks, symbol="GOLD", timeframe="M1",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1), minimum_sample=0,
        )
    with pytest.raises(ValueError, match="symbol"):
        compute_tick_volume_statistics(
            ticks, symbol=" ", timeframe="M1",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="start_at"):
        compute_tick_volume_statistics(
            ticks, symbol="GOLD", timeframe="M1", start_at=BASE_TIME, end_at=BASE_TIME,
        )
    with pytest.raises(ValueError, match="symbol"):
        compute_tick_volume_statistics(
            [_tick(0, BASE_TIME, symbol="OIL")], symbol="GOLD", timeframe="M1",
            start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=1),
        )
