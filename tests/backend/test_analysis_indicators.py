from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import (
    INSUFFICIENT_DATA,
    READY,
    build_indicator_set,
    calculate_atr,
    calculate_ema,
    calculate_rsi,
)


BASE_TIME = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)


def bar(
    index: int,
    *,
    close: float,
    high: float | None = None,
    low: float | None = None,
) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD",
        timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        tick_count=1,
        tick_volume=1,
        spread_min=0.1,
        spread_max=0.1,
        spread_mean=0.1,
        first_event_id=f"event:{index}",
        last_event_id=f"event:{index}",
    )


def test_ema_uses_sma_seed_then_causal_updates() -> None:
    bars = tuple(bar(index, close=value) for index, value in enumerate([1, 2, 3, 4]))
    series = calculate_ema(bars, period=3)
    assert [point.status for point in series.points] == [
        INSUFFICIENT_DATA,
        INSUFFICIENT_DATA,
        READY,
        READY,
    ]
    assert [point.value for point in series.points] == [None, None, 2.0, 3.0]


def test_rsi_uses_wilder_smoothing_and_neutral_flat_market() -> None:
    rising = tuple(bar(index, close=value) for index, value in enumerate([1, 2, 3, 2, 4]))
    series = calculate_rsi(rising, period=3)
    assert [point.value for point in series.points[:3]] == [None, None, None]
    assert series.points[3].value == pytest.approx(66.6666666667)
    assert series.points[4].value == pytest.approx(83.3333333333)

    flat = tuple(bar(index, close=10) for index in range(4))
    assert calculate_rsi(flat, period=3).points[-1].value == 50.0


def test_atr_uses_true_range_and_wilder_smoothing() -> None:
    bars = (
        bar(0, close=9, high=10, low=8),
        bar(1, close=12, high=13, low=11),
        bar(2, close=10, high=11, low=9),
        bar(3, close=14, high=15, low=13),
    )
    series = calculate_atr(bars, period=3)
    assert [point.value for point in series.points[:2]] == [None, None]
    assert series.points[2].value == pytest.approx(3.0)
    assert series.points[3].value == pytest.approx(11 / 3)


def test_indicator_set_is_deterministic_and_bound_to_bar_fingerprint() -> None:
    bars = tuple(bar(index, close=100 + index) for index in range(6))
    first = build_indicator_set(
        bars,
        bar_fingerprint="sha256:bars",
        ema_period=3,
        rsi_period=3,
        atr_period=3,
    )
    second = build_indicator_set(
        bars,
        bar_fingerprint="sha256:bars",
        ema_period=3,
        rsi_period=3,
        atr_period=3,
    )
    changed_source = build_indicator_set(
        bars,
        bar_fingerprint="sha256:other",
        ema_period=3,
        rsi_period=3,
        atr_period=3,
    )
    assert first == second
    assert first.fingerprint.startswith("sha256:")
    assert first.fingerprint != changed_source.fingerprint


def test_future_bar_does_not_change_past_indicator_points() -> None:
    bars = tuple(bar(index, close=100 + index) for index in range(5))
    initial = build_indicator_set(
        bars,
        bar_fingerprint="sha256:initial",
        ema_period=3,
        rsi_period=3,
        atr_period=3,
    )
    extended = build_indicator_set(
        bars + (bar(5, close=500),),
        bar_fingerprint="sha256:extended",
        ema_period=3,
        rsi_period=3,
        atr_period=3,
    )
    assert initial.ema.points == extended.ema.points[:-1]
    assert initial.rsi.points == extended.rsi.points[:-1]
    assert initial.atr.points == extended.atr.points[:-1]


def test_missing_intervals_are_not_filled() -> None:
    bars = (bar(0, close=100), bar(2, close=102), bar(5, close=105))
    result = build_indicator_set(
        bars,
        bar_fingerprint="sha256:gaps",
        ema_period=2,
        rsi_period=2,
        atr_period=2,
    )
    assert len(result.ema.points) == len(bars)
    assert [point.bar_end_at for point in result.ema.points] == [
        item.end_at for item in bars
    ]


@pytest.mark.parametrize("period", [0, -1, True, 1.5])
def test_period_must_be_a_positive_integer(period) -> None:
    with pytest.raises(ValueError, match="period"):
        calculate_ema((bar(0, close=100),), period=period)


def test_rejects_mixed_or_inconsistent_bars() -> None:
    first = bar(0, close=100)
    with pytest.raises(ValueError, match="symbol"):
        calculate_atr(
            (first, replace(bar(1, close=101), symbol="EURUSD")), period=1
        )
    with pytest.raises(ValueError, match="OHLC"):
        calculate_rsi((replace(first, high=99),), period=1)
    with pytest.raises(ValueError, match="bar_fingerprint"):
        build_indicator_set((first,), bar_fingerprint=" ")
