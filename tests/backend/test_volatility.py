from datetime import UTC, datetime, timedelta
import math

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.return_series import compute_return_series
from backend.app.analysis.volatility import VOLATILITY_VERSION, compute_volatility
from backend.app.database.tick_replay_repository import ReplayTick


BASE_TIME = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
DEFAULT_END = BASE_TIME + timedelta(hours=1)


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


def _tick(index: int, timestamp: datetime, *, symbol: str = "GOLD", mid: float = 100.0) -> ReplayTick:
    return ReplayTick(
        event_id=f"event:{index:04d}",
        event_type="TICK_RECEIVED",
        event_timestamp=timestamp.isoformat(timespec="microseconds"),
        received_at=timestamp.isoformat(timespec="microseconds"),
        symbol=symbol,
        bid=mid, ask=mid, last=mid,
        volume=1, flags=6,
        source_time_msc=int(timestamp.timestamp() * 1000),
        source="esas.mt5.bridge", event_version="1.0", module_version="1.6.0",
    )


def _volatility(count: int, *, minimum_sample: int = 30, drift: float = 1.0, ticks: tuple[ReplayTick, ...] = ()):
    windows = bars(count, drift=drift)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=minimum_sample,
    )
    return compute_volatility(
        windows, return_series, ticks, bar_fingerprint="sha256:source",
        start_at=BASE_TIME, end_at=DEFAULT_END, minimum_sample=minimum_sample,
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
    assert result.tick_return.status == "insufficient_data"
    assert result.tick_return.mean is None


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
        windows, return_series, (), bar_fingerprint="sha256:source",
        start_at=BASE_TIME, end_at=DEFAULT_END, minimum_sample=1,
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
        windows, return_series, (), bar_fingerprint="sha256:source",
        start_at=BASE_TIME, end_at=DEFAULT_END, minimum_sample=1,
    )
    assert result.window_range_absolute.minimum == 2.0
    assert result.window_range_absolute.maximum == 2.0
    assert round(result.window_range_relative.minimum, 6) == round(2.0 / 100.0, 6)


def test_computes_tick_return_std_dev_from_raw_ticks() -> None:
    # Each consecutive mid-price step is exp(0.01), so every tick-to-tick
    # log-return is exactly 0.01 -- a clean, hand-verifiable fixture.
    ticks = tuple(
        _tick(index, BASE_TIME + timedelta(seconds=index), mid=100.0 * math.exp(0.01 * index))
        for index in range(31)
    )
    windows = bars(30, drift=1.0)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    result = compute_volatility(
        windows, return_series, ticks, bar_fingerprint="sha256:source",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=5), minimum_sample=30,
    )
    assert result.tick_return.status == "completed"
    assert result.tick_return.n_valid == 30
    assert result.tick_return.mean == pytest.approx(0.01, abs=1e-9)
    assert result.tick_return.median == pytest.approx(0.01, abs=1e-9)
    assert result.tick_return.std_dev == pytest.approx(0.0, abs=1e-9)
    assert result.tick_return.minimum == pytest.approx(0.01, abs=1e-9)
    assert result.tick_return.maximum == pytest.approx(0.01, abs=1e-9)


def test_tick_return_excludes_invalid_bid_ask_pairs() -> None:
    valid = [
        _tick(index, BASE_TIME + timedelta(seconds=index), mid=100.0 + index)
        for index in range(3)
    ]
    invalid = ReplayTick(
        event_id="event:invalid", event_type="TICK_RECEIVED",
        event_timestamp=(BASE_TIME + timedelta(seconds=3)).isoformat(timespec="microseconds"),
        received_at=(BASE_TIME + timedelta(seconds=3)).isoformat(timespec="microseconds"),
        symbol="GOLD", bid=100.0, ask=99.0, last=99.5, volume=1, flags=6,
        source_time_msc=0, source="esas.mt5.bridge", event_version="1.0", module_version="1.6.0",
    )
    windows = bars(1, drift=1.0)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    result = compute_volatility(
        windows, return_series, (*valid, invalid), bar_fingerprint="sha256:source",
        start_at=BASE_TIME, end_at=DEFAULT_END, minimum_sample=1,
    )
    assert result.tick_return.n_total == 2
    assert result.tick_return.n_valid == 2


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
        compute_volatility(
            mismatched, return_series, (), bar_fingerprint="sha256:source",
            start_at=BASE_TIME, end_at=DEFAULT_END, minimum_sample=1,
        )
    except ValueError as error:
        assert "symbol" in str(error) or "timeframe" in str(error)
    else:
        raise AssertionError("expected a ValueError for mismatched symbol")


def test_rejects_ticks_with_mismatched_symbol() -> None:
    windows = bars(1)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    foreign_tick = _tick(0, BASE_TIME, symbol="SILVER", mid=100.0)
    with pytest.raises(ValueError, match="symbol"):
        compute_volatility(
            windows, return_series, (foreign_tick,), bar_fingerprint="sha256:source",
            start_at=BASE_TIME, end_at=DEFAULT_END, minimum_sample=1,
        )


def test_rejects_unsafe_minimum_sample() -> None:
    windows = bars(1)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    for invalid in (0, -1, True):
        try:
            compute_volatility(
                windows, return_series, (), bar_fingerprint="sha256:source",
                start_at=BASE_TIME, end_at=DEFAULT_END, minimum_sample=invalid,
            )
        except ValueError:
            continue
        raise AssertionError(f"expected a ValueError for minimum_sample={invalid!r}")


def test_rejects_start_at_not_before_end_at() -> None:
    windows = bars(1)
    return_series = compute_return_series(
        windows, symbol="GOLD", timeframe="M1", bar_fingerprint="sha256:source",
        minimum_window_returns=1,
    )
    with pytest.raises(ValueError, match="start_at"):
        compute_volatility(
            windows, return_series, (), bar_fingerprint="sha256:source",
            start_at=BASE_TIME, end_at=BASE_TIME, minimum_sample=1,
        )
