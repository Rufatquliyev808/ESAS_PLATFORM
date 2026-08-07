from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.liquidity_reaction import (
    AMBIGUOUS,
    CONTINUED,
    INSUFFICIENT_DATA,
    REACTION_VERSION,
    REVERSED,
    compute_liquidity_reaction_statistics,
)
from backend.app.analysis.liquidity_sweep import LiquidityPool


BASE_TIME = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)


def bar(index: int, *, close: float, high: float | None = None, low: float | None = None) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=close, high=high if high is not None else close, low=low if low is not None else close,
        close=close, tick_count=2, tick_volume=2,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:1",
    )


def buy_side_pool(*, level: float = 100.0, last_confirmation_bar_index: int = 0) -> LiquidityPool:
    return LiquidityPool(
        side="buy_side", level=level, touch_count=2,
        first_pivot_at=BASE_TIME.isoformat(), last_pivot_at=BASE_TIME.isoformat(),
        available_at=BASE_TIME.isoformat(), last_confirmation_bar_index=last_confirmation_bar_index,
    )


def sell_side_pool(*, level: float = 100.0, last_confirmation_bar_index: int = 0) -> LiquidityPool:
    return LiquidityPool(
        side="sell_side", level=level, touch_count=2,
        first_pivot_at=BASE_TIME.isoformat(), last_pivot_at=BASE_TIME.isoformat(),
        available_at=BASE_TIME.isoformat(), last_confirmation_bar_index=last_confirmation_bar_index,
    )


def test_buy_side_touch_that_closes_back_below_is_reversed() -> None:
    bars = (bar(0, close=99.0), bar(1, close=99.5, high=101.0))
    result = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=1, reaction_threshold_bps=10.0,
    )
    assert result.version == REACTION_VERSION
    assert len(result.events) == 1
    assert result.events[0].outcome == REVERSED
    assert result.events[0].excursion_bps == pytest.approx(50.0)


def test_buy_side_touch_that_closes_through_is_continued() -> None:
    bars = (bar(0, close=99.0), bar(1, close=101.5, high=101.5))
    result = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=1, reaction_threshold_bps=10.0,
    )
    assert result.events[0].outcome == CONTINUED
    assert result.events[0].excursion_bps == pytest.approx(150.0)


def test_small_move_below_threshold_is_ambiguous() -> None:
    bars = (bar(0, close=99.0), bar(1, close=100.05, high=101.0))
    result = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=1, reaction_threshold_bps=10.0,
    )
    assert result.events[0].outcome == AMBIGUOUS
    assert result.events[0].excursion_bps is None


def test_sell_side_pool_bounce_is_reversed_and_breakdown_is_continued() -> None:
    bounce = (bar(0, close=101.0), bar(1, close=100.5, low=99.0))
    result = compute_liquidity_reaction_statistics(
        bounce, (sell_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=1, reaction_threshold_bps=10.0,
    )
    assert result.events[0].outcome == REVERSED

    breakdown = (bar(0, close=101.0), bar(1, close=98.5, low=98.5))
    result2 = compute_liquidity_reaction_statistics(
        breakdown, (sell_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=1, reaction_threshold_bps=10.0,
    )
    assert result2.events[0].outcome == CONTINUED


def test_overlapping_touches_are_purged_with_embargo() -> None:
    bars = (
        bar(0, close=99.0),
        bar(1, close=99.5, high=101.0),
        bar(2, close=99.4, high=101.0),
        bar(3, close=99.3, high=101.0),
    )
    result = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=2, reaction_threshold_bps=10.0,
    )
    assert len(result.events) == 1


def test_below_minimum_sample_is_insufficient_data() -> None:
    bars = (bar(0, close=99.0), bar(1, close=99.5, high=101.0))
    result = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=1, reaction_threshold_bps=10.0,
    )
    assert result.buy_side_statistics.status == INSUFFICIENT_DATA
    assert result.buy_side_statistics.reversed_percent is None
    assert result.sell_side_statistics.status == INSUFFICIENT_DATA
    assert result.sell_side_statistics.n_total == 0


def test_completed_statistics_once_thirty_directional_touches_reached() -> None:
    bars = [bar(0, close=99.0)]
    for index in range(1, 61, 2):
        bars.append(bar(index, close=99.5, high=101.0))
        bars.append(bar(index + 1, close=99.0))
    result = compute_liquidity_reaction_statistics(
        tuple(bars), (buy_side_pool(),), bar_fingerprint="sha256:source",
        horizon_bars=1, reaction_threshold_bps=10.0,
    )
    stats = result.buy_side_statistics
    assert stats.status == "completed"
    assert stats.n_reversed == stats.n_total
    assert stats.reversed_percent == pytest.approx(100.0)
    assert stats.confidence_interval_low_percent is not None
    assert stats.confidence_interval_low_percent <= 100.0
    assert stats.confidence_interval_high_percent == pytest.approx(100.0)


def test_deterministic_fingerprint_for_same_input() -> None:
    bars = (bar(0, close=99.0), bar(1, close=99.5, high=101.0))
    first = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(),), bar_fingerprint="sha256:source", horizon_bars=1,
    )
    second = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(),), bar_fingerprint="sha256:source", horizon_bars=1,
    )
    assert first.fingerprint == second.fingerprint
    third = compute_liquidity_reaction_statistics(
        bars, (buy_side_pool(level=105.0),), bar_fingerprint="sha256:source", horizon_bars=1,
    )
    assert third.fingerprint != first.fingerprint


def test_rejects_unsafe_parameters() -> None:
    bars = (bar(0, close=99.0),)
    with pytest.raises(ValueError, match="horizon_bars"):
        compute_liquidity_reaction_statistics(bars, (), bar_fingerprint="sha256:source", horizon_bars=0)
    with pytest.raises(ValueError, match="reaction_threshold_bps"):
        compute_liquidity_reaction_statistics(bars, (), bar_fingerprint="sha256:source", reaction_threshold_bps=0)
    with pytest.raises(ValueError, match="bar_fingerprint"):
        compute_liquidity_reaction_statistics(bars, (), bar_fingerprint=" ")


def test_empty_pools_is_a_valid_insufficient_data_input() -> None:
    bars = (bar(0, close=99.0),)
    result = compute_liquidity_reaction_statistics(bars, (), bar_fingerprint="sha256:source")
    assert result.events == ()
    assert result.buy_side_statistics.status == INSUFFICIENT_DATA
    assert result.sell_side_statistics.status == INSUFFICIENT_DATA
