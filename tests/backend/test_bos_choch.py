from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.bos_choch import detect_bos_choch
from backend.app.analysis.market_structure import StructurePivot


BASE = datetime(2026, 8, 5, tzinfo=UTC)


def _bar(index: int, close: float = 100.0, high: float | None = None, low: float | None = None) -> MarketBar:
    start = BASE + timedelta(minutes=index)
    return MarketBar("GOLD", "M1", start.isoformat(), (start + timedelta(minutes=1)).isoformat(), 100.0, high if high is not None else max(101.0, close), low if low is not None else min(99.0, close), close, 1, 1, 0.1, 0.1, 0.1, f"e{index}", f"e{index}")


def _pivot(kind: str, classification: str, value: float, pivot_index: int, confirmation_index: int) -> StructurePivot:
    return StructurePivot(kind, classification, value, _bar(pivot_index).end_at, _bar(confirmation_index).end_at, pivot_index, confirmation_index)


def _detect(bars: tuple[MarketBar, ...], pivots: tuple[StructurePivot, ...]):
    return detect_bos_choch(bars, pivots, bar_fingerprint="sha256:bars", structure_fingerprint="sha256:structure")


def test_detects_bullish_bos_and_bearish_choch_from_closed_bars() -> None:
    bars = tuple(_bar(index, close=103.0 if index == 6 else 97.0 if index == 8 else 100.0) for index in range(10))
    pivots = (
        _pivot("low", "HL", 90.0, 1, 2),
        _pivot("high", "HH", 102.0, 2, 3),
        _pivot("low", "HL", 98.0, 3, 4),
    )
    result = _detect(bars, pivots)
    assert result.bullish_observation.state == "confirmed_bos"
    assert result.bullish_observation.break_type == "BOS"
    assert result.bearish_observation.state == "confirmed_choch"
    assert result.bearish_observation.break_type == "CHOCH"
    assert result.interpretation == "research_observation_not_trading_signal"


def test_rejects_cross_before_pivot_confirmation_and_reports_no_break() -> None:
    bars = tuple(_bar(index, close=104.0 if index == 2 else 100.0) for index in range(7))
    pivots = (_pivot("high", "HH", 102.0, 1, 3),)
    result = _detect(bars, pivots)
    assert result.bullish_observation.state == "no_break"
    assert result.bullish_observation.observed_at is None
    assert result.bearish_observation.state == "insufficient_data"


def test_same_closed_bar_breaking_both_sides_is_explicitly_conflicting() -> None:
    bars = tuple(_bar(index, close=100.0, high=104.0, low=96.0) for index in range(7))
    bars = (*bars[:5], _bar(5, close=100.0, high=104.0, low=96.0), *bars[6:])
    pivots = (_pivot("low", "HL", 101.0, 1, 3), _pivot("high", "HH", 99.0, 2, 3))
    result = _detect(bars, pivots)
    assert result.bullish_observation.state == "conflicting"
    assert result.bearish_observation.state == "conflicting"


def test_is_deterministic_validates_configuration_and_preserves_prior_observation() -> None:
    bars = tuple(_bar(index, close=103.0 if index == 6 else 100.0) for index in range(9))
    pivots = (_pivot("low", "HL", 98.0, 1, 2), _pivot("high", "HH", 102.0, 2, 3))
    first = _detect(bars, pivots)
    assert first == _detect(bars, pivots)
    extended = _detect(bars + (_bar(9),), pivots + (_pivot("high", "HH", 105.0, 7, 8),))
    assert first.bullish_observation in extended.observations
    assert first.fingerprint.startswith("sha256:")
    with pytest.raises(ValueError):
        detect_bos_choch(bars, pivots, bar_fingerprint="", structure_fingerprint="x")
    with pytest.raises(ValueError):
        detect_bos_choch(bars, pivots, bar_fingerprint="x", structure_fingerprint="y", minimum_close_break_bps=-1)
