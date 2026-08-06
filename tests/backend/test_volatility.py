from backend.app.analysis.bars import MarketBar
from backend.app.analysis.return_series import compute_return_series
from backend.app.analysis.volatility import VOLATILITY_VERSION, compute_volatility


def bar(index: int, *, tick_count: int, open_mid: float, close_mid: float, high: float | None = None, low: float | None = None) -> MarketBar:
    start = f"2026-08-06T10:{index:02d}:00.000000"
    end = f"2026-08-06T10:{index + 1:02d}:00.000000"
    return MarketBar(
        symbol="GOLD", timeframe="M1", start_at=start, end_at=end,
        open=open_mid, high=high if high is not None else max(open_mid, close_mid),
        low=low if low is not None else min(open_mid, close_mid),
        close=close_mid, tick_count=tick_count, tick_volume=tick_count,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:{tick_count - 1}",
    )


def bars(count: int, *, drift: float = 1.0) -> tuple[MarketBar, ...]:
    return tuple(
        bar(index, tick_count=2, open_mid=100.0 + index * drift, close_mid=100.5 + index * drift)
        for index in range(count)
    )


def _volatility(count: int, *, minimum_sample: int = 30, drift: float = 1.0):
    windows = bars(count, drift=drift)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=minimum_sample,
    )
    return compute_volatility(
        windows, return_series, bar_fingerprint="sha256:source", minimum_sample=minimum_sample,
    ), return_series


def test_computes_window_range_and_robust_mad_once_minimum_sample_is_reached() -> None:
    result, _ = _volatility(30, minimum_sample=30)
    assert result.version == VOLATILITY_VERSION
    assert result.window_range_absolute.status == "completed"
    assert result.window_range_relative.status == "completed"
    assert result.window_log_return_abs.status == "completed"
    assert result.robust_mad_status == "completed"
    assert result.robust_mad is not None and result.robust_mad >= 0
    assert result.fingerprint.startswith("sha256:")


def test_below_minimum_sample_is_insufficient_data() -> None:
    result, _ = _volatility(5, minimum_sample=30)
    assert result.window_range_absolute.status == "insufficient_data"
    assert result.window_range_absolute.mean is None
    assert result.window_range_absolute.n_total == 5
    assert result.window_log_return_abs.status == "insufficient_data"
    assert result.robust_mad_status == "insufficient_data"
    assert result.robust_mad is None


def test_single_tick_window_still_counts_for_range_but_not_for_return() -> None:
    single_tick = bar(0, tick_count=1, open_mid=100.0, close_mid=100.0, high=101.0, low=99.5)
    rest = tuple(
        bar(index, tick_count=2, open_mid=100.0 + index, close_mid=100.5 + index)
        for index in range(1, 30)
    )
    windows = (single_tick, *rest)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    result = compute_volatility(
        windows, return_series, bar_fingerprint="sha256:source", minimum_sample=1,
    )
    assert result.window_range_absolute.n_total == 30
    assert result.window_range_absolute.n_valid == 30
    assert result.window_log_return_abs.n_total == 29
    assert result.window_log_return_abs.n_valid == 29


def test_range_absolute_matches_high_minus_low() -> None:
    windows = (bar(0, tick_count=2, open_mid=100.0, close_mid=100.5, high=101.0, low=99.0),)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    result = compute_volatility(
        windows, return_series, bar_fingerprint="sha256:source", minimum_sample=1,
    )
    assert result.window_range_absolute.minimum == 2.0
    assert result.window_range_absolute.maximum == 2.0
    assert round(result.window_range_relative.minimum, 6) == round(2.0 / 100.0, 6)


def test_deterministic_fingerprint_for_same_input() -> None:
    first, first_series = _volatility(10, minimum_sample=1)
    second, second_series = _volatility(10, minimum_sample=1)
    assert first.fingerprint == second.fingerprint
    third, third_series = _volatility(10, minimum_sample=1, drift=3.0)
    assert third.fingerprint != first.fingerprint


def test_rejects_bars_with_mismatched_symbol_or_timeframe() -> None:
    windows = bars(2)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    mismatched = tuple(
        MarketBar(**{**item.__dict__, "symbol": "SILVER"}) for item in windows
    )
    try:
        compute_volatility(mismatched, return_series, bar_fingerprint="sha256:source", minimum_sample=1)
    except ValueError as error:
        assert "symbol" in str(error) or "timeframe" in str(error)
    else:
        raise AssertionError("expected a ValueError for mismatched symbol")


def test_rejects_unsafe_minimum_sample() -> None:
    windows = bars(1)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    for invalid in (0, -1, True):
        try:
            compute_volatility(
                windows, return_series, bar_fingerprint="sha256:source", minimum_sample=invalid,
            )
        except ValueError:
            continue
        raise AssertionError(f"expected a ValueError for minimum_sample={invalid!r}")
