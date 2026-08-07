import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.regime_candidates import (
    COMPLETED,
    INSUFFICIENT_DATA,
    REGIME_VERSION,
    compute_regime_candidates,
)
from backend.app.analysis.return_series import compute_return_series


def bar(
    index: int, *, tick_count: int, open_mid: float, close_mid: float,
    high: float, low: float, spread_mean: float,
) -> MarketBar:
    start = f"2026-08-06T10:{index:02d}:00.000000"
    end = f"2026-08-06T10:{index + 1:02d}:00.000000"
    return MarketBar(
        symbol="GOLD", timeframe="M1", start_at=start, end_at=end,
        open=open_mid, high=high, low=low, close=close_mid,
        tick_count=tick_count, tick_volume=tick_count,
        spread_min=spread_mean, spread_max=spread_mean, spread_mean=spread_mean,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:{tick_count - 1}",
    )


def _four_quadrant_bars() -> tuple[MarketBar, ...]:
    return (
        bar(0, tick_count=2, open_mid=100.0, close_mid=100.5, high=100.1, low=99.9, spread_mean=0.05),
        bar(1, tick_count=5, open_mid=100.0, close_mid=99.0, high=101.0, low=98.0, spread_mean=0.5),
        bar(2, tick_count=2, open_mid=100.0, close_mid=99.0, high=100.1, low=99.9, spread_mean=0.05),
        bar(3, tick_count=5, open_mid=100.0, close_mid=101.0, high=101.5, low=98.5, spread_mean=0.5),
    )


def _return_series(bars: tuple[MarketBar, ...], *, minimum_window_returns: int = 1):
    return compute_return_series(
        bars, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=minimum_window_returns,
    )


def test_below_minimum_sample_is_insufficient_data() -> None:
    bars = _four_quadrant_bars()
    return_series = _return_series(bars)
    result = compute_regime_candidates(
        bars, return_series, bar_fingerprint="sha256:source",
        data_quality_status="pass", minimum_sample=30,
    )
    assert result.status == INSUFFICIENT_DATA
    assert result.n_total_windows == 4
    assert result.n_classified_windows == 0
    assert result.regimes == ()
    assert result.observations == ()


def test_hand_verified_median_split_and_lexicographic_regime_assignment() -> None:
    bars = _four_quadrant_bars()
    return_series = _return_series(bars)
    result = compute_regime_candidates(
        bars, return_series, bar_fingerprint="sha256:source",
        data_quality_status="pass", minimum_sample=4,
    )
    assert result.version == REGIME_VERSION
    assert result.status == COMPLETED
    assert result.n_total_windows == 4
    assert result.n_classified_windows == 4

    by_start = {item.start_at: item for item in result.observations}
    bar0, bar1, bar2, bar3 = bars
    # bar0: low volatility/spread/tick-speed, return up.
    obs0 = by_start[bar0.start_at]
    assert (obs0.volatility_tier, obs0.spread_tier, obs0.tick_speed_tier, obs0.return_direction) == (
        "low", "low", "low", "up",
    )
    # bar1: high volatility/spread/tick-speed, return down.
    obs1 = by_start[bar1.start_at]
    assert (obs1.volatility_tier, obs1.spread_tier, obs1.tick_speed_tier, obs1.return_direction) == (
        "high", "high", "high", "down",
    )
    # bar2: low/low/low, return down -- differs from bar0 only by direction.
    obs2 = by_start[bar2.start_at]
    assert (obs2.volatility_tier, obs2.spread_tier, obs2.tick_speed_tier, obs2.return_direction) == (
        "low", "low", "low", "down",
    )
    # bar3: high/high/high, return up -- differs from bar1 only by direction.
    obs3 = by_start[bar3.start_at]
    assert (obs3.volatility_tier, obs3.spread_tier, obs3.tick_speed_tier, obs3.return_direction) == (
        "high", "high", "high", "up",
    )

    # Four distinct feature tuples -> four distinct regimes, all singletons.
    assert len({obs0.regime, obs1.regime, obs2.regime, obs3.regime}) == 4
    assert len(result.regimes) == 4
    for summary in result.regimes:
        assert summary.observation_count == 1
        assert summary.confidence == pytest.approx(0.25)

    # "high..." tuples sort before "low..." tuples; within each, "down" sorts
    # before "up" -- so bar1 (high/high/high/down) is regime_1.
    assert obs1.regime == "regime_1"
    assert obs3.regime == "regime_2"
    assert obs2.regime == "regime_3"
    assert obs0.regime == "regime_4"


def test_single_tick_window_gets_unknown_return_direction() -> None:
    single_tick = bar(0, tick_count=1, open_mid=100.0, close_mid=100.0, high=100.1, low=99.9, spread_mean=0.05)
    normal = bar(1, tick_count=2, open_mid=100.0, close_mid=100.5, high=100.6, low=99.9, spread_mean=0.05)
    bars = (single_tick, normal)
    return_series = _return_series(bars)
    result = compute_regime_candidates(
        bars, return_series, bar_fingerprint="sha256:source",
        data_quality_status="pass", minimum_sample=2,
    )
    observation = next(item for item in result.observations if item.start_at == single_tick.start_at)
    assert observation.return_direction == "unknown"


def test_deterministic_fingerprint_for_same_input() -> None:
    bars = _four_quadrant_bars()
    return_series = _return_series(bars)
    first = compute_regime_candidates(
        bars, return_series, bar_fingerprint="sha256:source",
        data_quality_status="pass", minimum_sample=4,
    )
    second = compute_regime_candidates(
        bars, return_series, bar_fingerprint="sha256:source",
        data_quality_status="pass", minimum_sample=4,
    )
    assert first.fingerprint == second.fingerprint
    third = compute_regime_candidates(
        bars, return_series, bar_fingerprint="sha256:source",
        data_quality_status="review", minimum_sample=4,
    )
    assert third.fingerprint != first.fingerprint
    assert third.data_quality_status == "review"


def test_rejects_invalid_data_quality_status() -> None:
    bars = _four_quadrant_bars()
    return_series = _return_series(bars)
    with pytest.raises(ValueError, match="data_quality_status"):
        compute_regime_candidates(
            bars, return_series, bar_fingerprint="sha256:source",
            data_quality_status="unknown_status", minimum_sample=4,
        )


def test_rejects_bars_with_mismatched_symbol_or_timeframe() -> None:
    bars = _four_quadrant_bars()
    return_series = _return_series(bars)
    mismatched = tuple(MarketBar(**{**item.__dict__, "symbol": "SILVER"}) for item in bars)
    with pytest.raises(ValueError, match="symbol|timeframe"):
        compute_regime_candidates(
            mismatched, return_series, bar_fingerprint="sha256:source",
            data_quality_status="pass", minimum_sample=4,
        )


def test_rejects_unsafe_minimum_sample() -> None:
    bars = _four_quadrant_bars()
    return_series = _return_series(bars)
    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="minimum_sample"):
            compute_regime_candidates(
                bars, return_series, bar_fingerprint="sha256:source",
                data_quality_status="pass", minimum_sample=invalid,
            )
