from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.spread import (
    COMPLETED,
    INSUFFICIENT_DATA,
    SPREAD_VERSION,
    compute_spread_statistics,
)


BASE_TIME = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)


def bar(index: int, *, close: float, spread_mean: float, spread_min: float | None = None, spread_max: float | None = None) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=close, high=close, low=close, close=close,
        tick_count=2, tick_volume=2,
        spread_min=spread_min if spread_min is not None else spread_mean,
        spread_max=spread_max if spread_max is not None else spread_mean,
        spread_mean=spread_mean,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:1",
    )


def test_below_minimum_sample_is_insufficient_data() -> None:
    bars = (bar(0, close=100.0, spread_mean=0.2), bar(1, close=100.0, spread_mean=0.3))
    result = compute_spread_statistics(bars, bar_fingerprint="sha256:source", minimum_sample=30)
    assert result.version == SPREAD_VERSION
    assert result.window_spread_absolute.status == INSUFFICIENT_DATA
    assert result.window_spread_absolute.n_total == 2
    assert result.window_spread_absolute.mean is None
    assert result.window_spread_relative_bps.status == INSUFFICIENT_DATA


def test_hand_verified_percentiles_for_thirty_windows() -> None:
    bars = tuple(
        bar(index, close=100.0, spread_mean=round((index + 1) * 0.1, 6))
        for index in range(30)
    )
    result = compute_spread_statistics(bars, bar_fingerprint="sha256:source", minimum_sample=30)
    absolute = result.window_spread_absolute
    assert absolute.status == COMPLETED
    assert absolute.count == 30
    assert absolute.minimum == pytest.approx(0.1)
    assert absolute.maximum == pytest.approx(3.0)
    assert absolute.mean == pytest.approx(1.55)
    assert absolute.median == pytest.approx(1.55)
    assert absolute.p05 == pytest.approx(0.245)
    assert absolute.p25 == pytest.approx(0.825)
    assert absolute.p75 == pytest.approx(2.275)
    assert absolute.p95 == pytest.approx(2.855)
    assert absolute.p99 == pytest.approx(2.971)

    relative = result.window_spread_relative_bps
    assert relative.status == COMPLETED
    assert relative.minimum == pytest.approx(10.0)
    assert relative.maximum == pytest.approx(300.0)
    assert relative.median == pytest.approx(155.0)
    assert relative.p25 == pytest.approx(82.5)
    assert relative.p75 == pytest.approx(227.5)


def test_relative_spread_scales_with_close_price() -> None:
    bars = tuple(
        bar(index, close=200.0, spread_mean=1.0) for index in range(30)
    )
    result = compute_spread_statistics(bars, bar_fingerprint="sha256:source", minimum_sample=30)
    # spread_mean=1.0 against close=200.0 -> 1/200*10000 = 50 bps for every window.
    assert result.window_spread_relative_bps.mean == pytest.approx(50.0)
    assert result.window_spread_relative_bps.std_dev == pytest.approx(0.0)


def test_empty_bars_is_a_valid_insufficient_data_input() -> None:
    result = compute_spread_statistics((), bar_fingerprint="sha256:source")
    assert result.window_spread_absolute.status == INSUFFICIENT_DATA
    assert result.window_spread_absolute.n_total == 0
    assert result.symbol == ""
    assert result.timeframe == ""


def test_deterministic_fingerprint_for_same_input() -> None:
    bars = tuple(bar(index, close=100.0, spread_mean=0.2) for index in range(5))
    first = compute_spread_statistics(bars, bar_fingerprint="sha256:source", minimum_sample=1)
    second = compute_spread_statistics(bars, bar_fingerprint="sha256:source", minimum_sample=1)
    assert first.fingerprint == second.fingerprint
    third = compute_spread_statistics(
        tuple(bar(index, close=100.0, spread_mean=0.5) for index in range(5)),
        bar_fingerprint="sha256:source", minimum_sample=1,
    )
    assert third.fingerprint != first.fingerprint


def test_rejects_unsafe_parameters() -> None:
    bars = (bar(0, close=100.0, spread_mean=0.2),)
    with pytest.raises(ValueError, match="minimum_sample"):
        compute_spread_statistics(bars, bar_fingerprint="sha256:source", minimum_sample=0)
    with pytest.raises(ValueError, match="bar_fingerprint"):
        compute_spread_statistics(bars, bar_fingerprint=" ")
