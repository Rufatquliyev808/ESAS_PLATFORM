import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.moving_averages import (
    EMA,
    MOVING_AVERAGE_PERIODS,
    SMA,
    build_moving_average_set,
    calculate_sma,
)


def bar(index: int, *, close: float) -> MarketBar:
    start = f"2026-08-06T10:{index:02d}:00.000000"
    end = f"2026-08-06T10:{index + 1:02d}:00.000000"
    return MarketBar(
        symbol="GOLD", timeframe="M1", start_at=start, end_at=end,
        open=close, high=close, low=close, close=close,
        tick_count=2, tick_volume=2, spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:1",
    )


def test_sma_hand_verified_values() -> None:
    closes = [10.0, 20.0, 30.0, 40.0, 50.0]
    bars = tuple(bar(index, close=value) for index, value in enumerate(closes))
    result = calculate_sma(bars, period=3)
    assert result.feature_id == "sma.close.3"
    assert result.ma_type == SMA
    assert result.period == 3
    values = [point.value for point in result.points]
    assert values == [None, None, pytest.approx(20.0), pytest.approx(30.0), pytest.approx(40.0)]


def test_sma_below_period_is_insufficient_data() -> None:
    bars = tuple(bar(index, close=100.0) for index in range(2))
    result = calculate_sma(bars, period=5)
    assert all(point.status == "insufficient_data" and point.value is None for point in result.points)


def test_build_moving_average_set_covers_all_periods_with_sma_then_ema() -> None:
    bars = tuple(bar(index, close=100.0 + index) for index in range(60))
    result = build_moving_average_set(bars, bar_fingerprint="sha256:source")
    assert [(item.ma_type, item.period) for item in result.series] == [
        (ma_type, period) for period in MOVING_AVERAGE_PERIODS for ma_type in (SMA, EMA)
    ]
    assert len(result.series) == 8
    # With enough bars, every series should have a ready final point.
    for series in result.series:
        assert series.points[-1].status == "ready"
        assert series.points[-1].value is not None


def test_build_moving_average_set_uses_custom_periods() -> None:
    bars = tuple(bar(index, close=100.0) for index in range(10))
    result = build_moving_average_set(bars, bar_fingerprint="sha256:source", periods=(5,))
    assert [(item.ma_type, item.period) for item in result.series] == [(SMA, 5), (EMA, 5)]


def test_ema_series_reuses_indicators_calculate_ema() -> None:
    bars = tuple(bar(index, close=100.0 + index) for index in range(10))
    result = build_moving_average_set(bars, bar_fingerprint="sha256:source", periods=(5,))
    ema_series = next(item for item in result.series if item.ma_type == EMA)
    from backend.app.analysis.indicators import calculate_ema
    expected = calculate_ema(bars, period=5)
    assert [point.value for point in ema_series.points] == [point.value for point in expected.points]


def test_empty_bars_is_a_valid_input() -> None:
    result = build_moving_average_set((), bar_fingerprint="sha256:source")
    assert len(result.series) == 8
    assert all(series.points == () for series in result.series)


def test_rejects_unsafe_period() -> None:
    bars = tuple(bar(0, close=100.0) for _ in range(1))
    with pytest.raises(ValueError, match="period"):
        calculate_sma(bars, period=0)
    with pytest.raises(ValueError, match="bar_fingerprint"):
        build_moving_average_set(bars, bar_fingerprint=" ")
    with pytest.raises(ValueError, match="periods"):
        build_moving_average_set(bars, bar_fingerprint="sha256:source", periods=())


def test_deterministic_fingerprint_for_same_input() -> None:
    bars = tuple(bar(index, close=100.0 + index) for index in range(10))
    first = build_moving_average_set(bars, bar_fingerprint="sha256:source")
    second = build_moving_average_set(bars, bar_fingerprint="sha256:source")
    assert first.fingerprint == second.fingerprint
    third = build_moving_average_set(
        tuple(bar(index, close=200.0 + index) for index in range(10)), bar_fingerprint="sha256:source",
    )
    assert third.fingerprint != first.fingerprint
