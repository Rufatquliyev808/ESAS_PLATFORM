import math

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.return_series import compute_return_series
from backend.app.analysis.session_comparison import (
    CALENDAR_UNAVAILABLE_LIMITATION,
    COMPLETED,
    INSUFFICIENT_DATA,
    SESSION_COMPARISON_VERSION,
    compute_session_comparison,
)


def bar(
    index: int, *, hour: int, minute: int, tick_count: int,
    open_mid: float, close_mid: float, high: float | None = None, low: float | None = None,
) -> MarketBar:
    start = f"2026-08-06T{hour:02d}:{minute:02d}:00.000000"
    end_minute = minute + 1
    end_hour = hour
    if end_minute == 60:
        end_minute = 0
        end_hour += 1
    end = f"2026-08-06T{end_hour:02d}:{end_minute:02d}:00.000000"
    return MarketBar(
        symbol="GOLD", timeframe="M1", start_at=start, end_at=end,
        open=open_mid, high=high if high is not None else max(open_mid, close_mid),
        low=low if low is not None else min(open_mid, close_mid),
        close=close_mid, tick_count=tick_count, tick_volume=tick_count,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:{tick_count - 1}",
    )


def _return_series(bars: tuple[MarketBar, ...], *, minimum_window_returns: int = 1):
    return compute_return_series(
        bars, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=minimum_window_returns,
    )


def test_always_reports_calendar_unavailable_limitation() -> None:
    bars = (bar(0, hour=8, minute=0, tick_count=2, open_mid=100.0, close_mid=100.5),)
    return_series = _return_series(bars)
    result = compute_session_comparison(
        bars, return_series, bar_fingerprint="sha256:source", minimum_sample=1,
    )
    assert result.version == SESSION_COMPARISON_VERSION
    assert result.calendar_unavailable is True
    assert result.limitations == (CALENDAR_UNAVAILABLE_LIMITATION,)


def test_groups_windows_by_utc_hour_not_named_session() -> None:
    bars = (
        bar(0, hour=8, minute=0, tick_count=2, open_mid=100.0, close_mid=100.5),
        bar(1, hour=8, minute=1, tick_count=2, open_mid=100.0, close_mid=100.5),
        bar(2, hour=14, minute=0, tick_count=2, open_mid=100.0, close_mid=99.5),
    )
    return_series = _return_series(bars)
    result = compute_session_comparison(
        bars, return_series, bar_fingerprint="sha256:source", minimum_sample=1,
    )
    hours = {item.utc_hour for item in result.buckets}
    assert hours == {8, 14}
    bucket_8 = next(item for item in result.buckets if item.utc_hour == 8)
    assert bucket_8.n_total_windows == 2
    assert bucket_8.n_return_windows == 2
    assert bucket_8.status == COMPLETED


def test_below_minimum_sample_bucket_is_insufficient_data() -> None:
    bars = (bar(0, hour=8, minute=0, tick_count=2, open_mid=100.0, close_mid=100.5),)
    return_series = _return_series(bars)
    result = compute_session_comparison(
        bars, return_series, bar_fingerprint="sha256:source", minimum_sample=30,
    )
    bucket = result.buckets[0]
    assert bucket.status == INSUFFICIENT_DATA
    assert bucket.mean_return is None
    assert bucket.mean_range_relative is not None  # range is still valid at n=1


def test_hand_verified_mean_and_confidence_interval() -> None:
    # Four M1 windows in the same UTC hour, log-returns approx
    # [ln(1.01), ln(1.01), ln(0.99), ln(0.99)] via open/close pairs.
    bars = tuple(
        bar(
            index, hour=9, minute=index, tick_count=2,
            open_mid=100.0, close_mid=101.0 if index % 2 == 0 else 99.0,
        )
        for index in range(4)
    )
    return_series = _return_series(bars)
    result = compute_session_comparison(
        bars, return_series, bar_fingerprint="sha256:source", minimum_sample=4,
    )
    bucket = result.buckets[0]
    assert bucket.status == COMPLETED
    assert bucket.n_return_windows == 4
    expected_returns = sorted([math.log(1.01), math.log(1.01), math.log(0.99), math.log(0.99)])
    expected_mean = sum(expected_returns) / 4
    assert bucket.mean_return == pytest.approx(expected_mean, abs=1e-9)
    assert bucket.median_return == pytest.approx((expected_returns[1] + expected_returns[2]) / 2, abs=1e-9)
    assert bucket.return_confidence_interval_low < bucket.mean_return < bucket.return_confidence_interval_high


def test_empty_bars_is_a_valid_input_with_no_buckets() -> None:
    return_series = _return_series(())
    result = compute_session_comparison(
        (), return_series, bar_fingerprint="sha256:source", minimum_sample=1,
    )
    assert result.buckets == ()
    assert result.calendar_unavailable is True


def test_deterministic_fingerprint_for_same_input() -> None:
    bars = (
        bar(0, hour=8, minute=0, tick_count=2, open_mid=100.0, close_mid=100.5),
        bar(1, hour=8, minute=1, tick_count=2, open_mid=100.0, close_mid=100.6),
    )
    return_series = _return_series(bars)
    first = compute_session_comparison(
        bars, return_series, bar_fingerprint="sha256:source", minimum_sample=1,
    )
    second = compute_session_comparison(
        bars, return_series, bar_fingerprint="sha256:source", minimum_sample=1,
    )
    assert first.fingerprint == second.fingerprint
    third = compute_session_comparison(
        bars, return_series, bar_fingerprint="sha256:other", minimum_sample=1,
    )
    assert third.fingerprint != first.fingerprint


def test_rejects_bars_with_mismatched_symbol_or_timeframe() -> None:
    bars = (bar(0, hour=8, minute=0, tick_count=2, open_mid=100.0, close_mid=100.5),)
    return_series = _return_series(bars)
    mismatched = tuple(MarketBar(**{**item.__dict__, "symbol": "SILVER"}) for item in bars)
    with pytest.raises(ValueError, match="symbol|timeframe"):
        compute_session_comparison(
            mismatched, return_series, bar_fingerprint="sha256:source", minimum_sample=1,
        )


def test_rejects_unsafe_minimum_sample() -> None:
    bars = (bar(0, hour=8, minute=0, tick_count=2, open_mid=100.0, close_mid=100.5),)
    return_series = _return_series(bars)
    for invalid in (0, -1, True):
        with pytest.raises(ValueError, match="minimum_sample"):
            compute_session_comparison(
                bars, return_series, bar_fingerprint="sha256:source", minimum_sample=invalid,
            )


def test_rejects_empty_bar_fingerprint() -> None:
    bars = (bar(0, hour=8, minute=0, tick_count=2, open_mid=100.0, close_mid=100.5),)
    return_series = _return_series(bars)
    with pytest.raises(ValueError, match="bar_fingerprint"):
        compute_session_comparison(bars, return_series, bar_fingerprint=" ", minimum_sample=1)
