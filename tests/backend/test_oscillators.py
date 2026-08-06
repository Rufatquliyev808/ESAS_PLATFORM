from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.oscillators import (
    INSUFFICIENT_DATA,
    OSCILLATOR_PACKAGE_VERSION,
    READY,
    build_oscillator_set,
    calculate_adx,
    calculate_cci,
    calculate_macd,
    calculate_stochastic_k,
    calculate_williams_r,
)


BASE_TIME = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


def bar(index: int, *, close: float, high: float | None = None, low: float | None = None) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=close, high=high if high is not None else close, low=low if low is not None else close,
        close=close, tick_count=1, tick_volume=1,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}", last_event_id=f"event:{index}",
    )


def bars_from(closes: list[float]) -> tuple[MarketBar, ...]:
    return tuple(bar(index, close=value) for index, value in enumerate(closes))


def test_stochastic_k_tracks_close_position_in_range() -> None:
    series = calculate_stochastic_k(bars_from([1, 2, 3, 2, 1]), period=3, smoothing=1)
    assert [point.status for point in series.points] == [
        INSUFFICIENT_DATA, INSUFFICIENT_DATA, READY, READY, READY,
    ]
    assert [point.value for point in series.points[2:]] == [100.0, 0.0, 0.0]


def test_stochastic_k_flat_range_is_midpoint() -> None:
    series = calculate_stochastic_k(bars_from([5, 5, 5, 5]), period=2, smoothing=1)
    assert [point.value for point in series.points[1:]] == [50.0, 50.0, 50.0]


def test_cci_exact_value_for_hand_verified_series() -> None:
    series = calculate_cci(bars_from([1, 2, 3]), period=3)
    assert series.points[0].status == INSUFFICIENT_DATA
    assert series.points[1].status == INSUFFICIENT_DATA
    assert series.points[2].value == pytest.approx(100.0)


def test_cci_flat_range_is_zero() -> None:
    series = calculate_cci(bars_from([10, 10, 10, 10]), period=2)
    assert series.points[1].value == 0.0
    assert series.points[3].value == 0.0


def test_williams_r_bounds_and_flat_midpoint() -> None:
    at_high = calculate_williams_r(bars_from([1, 2, 3]), period=3)
    assert at_high.points[2].value == pytest.approx(0.0)
    at_low = calculate_williams_r(bars_from([3, 2, 1]), period=3)
    assert at_low.points[2].value == pytest.approx(-100.0)
    flat = calculate_williams_r(bars_from([5, 5, 5]), period=3)
    assert flat.points[2].value == -50.0


def test_macd_line_and_signal_hand_verified_constant_case() -> None:
    macd_line, macd_signal = calculate_macd(
        bars_from([1, 2, 3, 4, 5, 6, 7, 8]), fast_period=2, slow_period=3, signal_period=2,
    )
    assert [point.value for point in macd_line.points] == [
        None, None, pytest.approx(0.5), pytest.approx(0.5), pytest.approx(0.5),
        pytest.approx(0.5), pytest.approx(0.5), pytest.approx(0.5),
    ]
    assert [point.value for point in macd_signal.points] == [
        None, None, None, pytest.approx(0.5), pytest.approx(0.5),
        pytest.approx(0.5), pytest.approx(0.5), pytest.approx(0.5),
    ]


def test_macd_rejects_fast_period_not_smaller_than_slow() -> None:
    with pytest.raises(ValueError, match="fast_period"):
        calculate_macd(bars_from([1, 2, 3]), fast_period=5, slow_period=5, signal_period=2)


def test_adx_clean_uptrend_has_zero_minus_di_and_positive_plus_di() -> None:
    bars = tuple(
        bar(index, close=(high + low) / 2, high=high, low=low)
        for index, (high, low) in enumerate(
            [(10, 9), (12, 10), (14, 11), (16, 12), (18, 13), (20, 14), (22, 15), (24, 16)]
        )
    )
    adx, plus_di, minus_di = calculate_adx(bars, period=2)
    ready_minus_di = [point.value for point in minus_di.points if point.status == READY]
    ready_plus_di = [point.value for point in plus_di.points if point.status == READY]
    assert ready_minus_di and all(value == 0.0 for value in ready_minus_di)
    assert ready_plus_di and all(value > 0.0 for value in ready_plus_di)
    assert any(point.status == READY for point in adx.points)
    assert all(0.0 <= point.value <= 100.0 for point in adx.points if point.value is not None)


def test_build_oscillator_set_is_deterministic() -> None:
    bars = bars_from([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    kwargs = dict(
        stochastic_period=3, stochastic_smoothing=1, cci_period=3, adx_period=2,
        macd_fast_period=2, macd_slow_period=3, macd_signal_period=2, williams_period=3,
    )
    first = build_oscillator_set(bars, bar_fingerprint="sha256:source", **kwargs)
    second = build_oscillator_set(bars, bar_fingerprint="sha256:source", **kwargs)
    assert first == second
    assert first.package_version == OSCILLATOR_PACKAGE_VERSION
    assert first.fingerprint.startswith("sha256:")
    different = build_oscillator_set(
        bars_from([1, 2, 3, 4, 5, 6, 7, 8, 9, 20]), bar_fingerprint="sha256:source", **kwargs
    )
    assert different.fingerprint != first.fingerprint


def test_build_oscillator_set_rejects_empty_bar_fingerprint() -> None:
    with pytest.raises(ValueError, match="bar_fingerprint"):
        build_oscillator_set(bars_from([1, 2, 3]), bar_fingerprint=" ")


def test_rejects_bars_with_mismatched_symbol_or_timeframe() -> None:
    first = bar(0, close=1)
    second = MarketBar(**{**bar(1, close=2).__dict__, "symbol": "SILVER"})
    with pytest.raises(ValueError, match="symbol"):
        calculate_cci((first, second), period=2)


def test_rejects_unsafe_periods() -> None:
    for invalid in (0, -1, True):
        with pytest.raises(ValueError):
            calculate_stochastic_k(bars_from([1, 2, 3]), period=invalid)
