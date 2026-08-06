from backend.app.analysis.bars import MarketBar
from backend.app.analysis.return_series import (
    RETURN_SERIES_VERSION,
    compute_return_series,
)


def bar(index: int, *, tick_count: int, open_mid: float, close_mid: float) -> MarketBar:
    start = f"2026-08-06T10:{index:02d}:00.000000"
    end = f"2026-08-06T10:{index + 1:02d}:00.000000"
    return MarketBar(
        symbol="GOLD", timeframe="M1", start_at=start, end_at=end,
        open=open_mid, high=max(open_mid, close_mid), low=min(open_mid, close_mid),
        close=close_mid, tick_count=tick_count, tick_volume=tick_count,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:{tick_count - 1}",
    )


def bars(count: int, *, drift: float = 1.0) -> tuple[MarketBar, ...]:
    return tuple(
        bar(index, tick_count=2, open_mid=100.0 + index * drift, close_mid=100.5 + index * drift)
        for index in range(count)
    )


def test_computes_deterministic_log_return_per_window() -> None:
    windows = (bar(0, tick_count=2, open_mid=100.0, close_mid=110.0),)
    result = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    assert result.version == RETURN_SERIES_VERSION
    assert result.status == "completed"
    assert len(result.windows) == 1
    assert round(result.windows[0].log_return, 6) == round(0.09531017980432493, 6)
    assert result.mean == result.windows[0].log_return
    assert result.fingerprint.startswith("sha256:")


def test_single_tick_window_yields_no_return() -> None:
    windows = (
        bar(0, tick_count=1, open_mid=100.0, close_mid=100.0),
        bar(1, tick_count=2, open_mid=100.0, close_mid=101.0),
    )
    result = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    assert result.n_total == 2
    assert result.n_valid == 1
    assert result.n_excluded == 1
    assert result.count == 1


def test_below_minimum_sample_is_insufficient_data() -> None:
    result = compute_return_series(
        bars(5), symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=30,
    )
    assert result.status == "insufficient_data"
    assert result.mean is None
    assert result.p05 is None
    assert len(result.windows) == 5


def test_empty_bars_is_a_valid_insufficient_data_input() -> None:
    result = compute_return_series(
        (), symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
    )
    assert result.status == "insufficient_data"
    assert result.n_total == 0
    assert result.windows == ()


def test_at_least_minimum_sample_is_completed_with_percentiles() -> None:
    result = compute_return_series(
        bars(30), symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=30,
    )
    assert result.status == "completed"
    assert result.count == 30
    assert result.minimum <= result.p05 <= result.p25 <= result.median <= result.p75 <= result.p95 <= result.maximum
    assert result.std_dev is not None and result.std_dev > 0


def test_deterministic_fingerprint_for_same_input() -> None:
    first = compute_return_series(
        bars(3), symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    second = compute_return_series(
        bars(3), symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    assert first.fingerprint == second.fingerprint
    third = compute_return_series(
        bars(3, drift=2.0), symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    assert third.fingerprint != first.fingerprint


def test_rejects_bars_with_mismatched_symbol_or_timeframe() -> None:
    mismatched = bar(0, tick_count=2, open_mid=100.0, close_mid=101.0)
    try:
        compute_return_series(
            (mismatched,), symbol="SILVER", timeframe="M1",
            bar_fingerprint="sha256:source", minimum_window_returns=1,
        )
    except ValueError as error:
        assert "symbol" in str(error) or "timeframe" in str(error)
    else:
        raise AssertionError("expected a ValueError for mismatched symbol")


def test_rejects_unsafe_minimum_window_returns() -> None:
    for invalid in (0, -1, True):
        try:
            compute_return_series(
                bars(1), symbol="GOLD", timeframe="M1",
                bar_fingerprint="sha256:source", minimum_window_returns=invalid,
            )
        except ValueError:
            continue
        raise AssertionError(f"expected a ValueError for minimum_window_returns={invalid!r}")
