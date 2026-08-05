import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.liquidity_sweep import detect_liquidity_sweeps
from backend.app.analysis.market_structure import StructurePivot


def _bar(index: int, *, high: float = 101, low: float = 99, close: float = 100) -> MarketBar:
    return MarketBar("GOLD", "M1", f"2026-01-01T00:{index:02d}:00+00:00", f"2026-01-01T00:{index + 1:02d}:00+00:00", 100, high, low, close, 1, 1, 0.1, 0.1, 0.1, str(index), str(index))


def _pivot(kind: str, value: float, pivot_index: int, confirmation_index: int) -> StructurePivot:
    return StructurePivot(kind, "EH" if kind == "high" else "EL", value, f"2026-01-01T00:{pivot_index + 1:02d}:00+00:00", f"2026-01-01T00:{confirmation_index + 1:02d}:00+00:00", pivot_index, confirmation_index)


def test_detects_bullish_and_bearish_closed_bar_sweeps_separately() -> None:
    bars = tuple(_bar(index) for index in range(10))
    bars = bars[:6] + (_bar(6, high=103, low=99, close=100), _bar(7, high=101, low=97, close=100)) + bars[8:]
    pivots = (_pivot("high", 102, 0, 1), _pivot("high", 102.05, 2, 3), _pivot("low", 98, 1, 2), _pivot("low", 97.96, 3, 4))
    result = detect_liquidity_sweeps(bars, pivots, bar_fingerprint="sha256:bars", structure_fingerprint="sha256:structure", pool_tolerance_bps=10, minimum_sweep_bps=1)
    assert result.bearish_observation.state == "confirmed_sweep"
    assert result.bearish_observation.pool_side == "buy_side"
    assert result.bullish_observation.state == "confirmed_sweep"
    assert result.bullish_observation.pool_side == "sell_side"
    assert result.fingerprint.startswith("sha256:")


def test_requires_close_back_and_waits_for_pool_confirmation() -> None:
    bars = tuple(_bar(index) for index in range(8))
    bars = bars[:4] + (_bar(4, high=104, close=103), _bar(5, high=104, close=100)) + bars[6:]
    pivots = (_pivot("high", 102, 0, 1), _pivot("high", 102.02, 2, 5))
    result = detect_liquidity_sweeps(bars, pivots, bar_fingerprint="sha256:bars", structure_fingerprint="sha256:structure")
    assert result.bearish_observation.state == "no_sweep"
    assert result.bullish_observation.state == "insufficient_data"


def test_result_is_deterministic_and_configuration_is_validated() -> None:
    bars = tuple(_bar(index) for index in range(4))
    kwargs = dict(bar_fingerprint="sha256:bars", structure_fingerprint="sha256:structure")
    assert detect_liquidity_sweeps(bars, (), **kwargs) == detect_liquidity_sweeps(bars, (), **kwargs)
    try:
        detect_liquidity_sweeps(bars, (), minimum_touches=1, **kwargs)
    except ValueError as error:
        assert "configuration" in str(error)
    else:
        raise AssertionError("unsafe configuration was accepted")


def test_pool_snapshot_does_not_gain_future_pivot_knowledge() -> None:
    bars = tuple(_bar(index) for index in range(10))
    bars = bars[:5] + (_bar(5, high=104, close=100),) + bars[6:]
    initial = (_pivot("high", 102, 0, 1), _pivot("high", 102.02, 2, 3))
    later = initial + (_pivot("high", 102.01, 7, 8),)
    kwargs = dict(bar_fingerprint="sha256:bars", structure_fingerprint="sha256:structure")
    prefix_result = detect_liquidity_sweeps(bars, initial, **kwargs)
    extended_result = detect_liquidity_sweeps(bars, later, **kwargs)
    assert prefix_result.bearish_observation.observed_at == bars[5].end_at
    assert extended_result.bearish_observation.observed_at == bars[5].end_at
    assert extended_result.pools[0].touch_count == 2


def test_same_closed_bar_sweeping_both_sides_is_explicitly_conflicting() -> None:
    bars = tuple(_bar(index) for index in range(8))
    bars = bars[:6] + (_bar(6, high=104, low=96, close=100),) + bars[7:]
    pivots = (
        _pivot("high", 102, 0, 1), _pivot("high", 102.02, 2, 3),
        _pivot("low", 98, 1, 2), _pivot("low", 97.98, 3, 4),
    )
    result = detect_liquidity_sweeps(
        bars, pivots, bar_fingerprint="sha256:bars", structure_fingerprint="sha256:structure"
    )
    assert result.bullish_observation.state == "conflicting"
    assert result.bearish_observation.state == "conflicting"


def test_observations_capture_every_pool_sweep_not_only_the_latest() -> None:
    bars = tuple(_bar(index) for index in range(16))
    bars = (
        bars[:4]
        + (_bar(4, high=103, low=99, close=100),)
        + bars[5:14]
        + (_bar(14, high=111, low=99, close=100),)
        + bars[15:]
    )
    pivots = (
        _pivot("high", 102, 0, 1), _pivot("high", 102.02, 2, 3),
        _pivot("high", 110, 10, 11), _pivot("high", 110.02, 12, 13),
    )
    result = detect_liquidity_sweeps(
        bars, pivots, bar_fingerprint="sha256:bars", structure_fingerprint="sha256:structure",
        pool_tolerance_bps=10, minimum_sweep_bps=1,
    )
    bearish_events = [item for item in result.observations if item.direction == "bearish"]
    assert len(bearish_events) == 2
    assert bearish_events[0].observed_at < bearish_events[1].observed_at
    assert bearish_events[0].pool_level == pytest.approx(102.01, abs=0.01)
    assert bearish_events[1].pool_level == pytest.approx(110.01, abs=0.01)
    assert result.bearish_observation.observed_at == bars[14].end_at
