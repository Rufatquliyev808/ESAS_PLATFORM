from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.bos_choch import StructureBreakObservation
from backend.app.analysis.retest import detect_retests


BASE = datetime(2026, 8, 5, tzinfo=UTC)


def _bar(index: int, *, close: float = 103.0, high: float = 104.0, low: float = 102.0) -> MarketBar:
    start = BASE + timedelta(minutes=index)
    return MarketBar("GOLD", "M1", start.isoformat(), (start + timedelta(minutes=1)).isoformat(), close, high, low, close, 1, 1, 0.1, 0.1, 0.1, f"e{index}", f"e{index}")


def _break(direction: str, index: int, level: float = 100.0) -> StructureBreakObservation:
    return StructureBreakObservation(direction, "confirmed_bos", "BOS", "high" if direction == "bullish" else "low", "HH" if direction == "bullish" else "LL", level, _bar(index - 1).end_at, _bar(index).end_at, 10.0)


def _detect(bars, breaks):
    return detect_retests(tuple(bars), tuple(breaks), bar_fingerprint="sha256:bars", bos_choch_fingerprint="sha256:breaks")


def test_confirms_bullish_and_bearish_retests_only_after_break_bar() -> None:
    bars = [_bar(i) for i in range(8)]
    bars[4] = _bar(4, close=101.0, high=103.0, low=99.9)
    bullish = _detect(bars, [_break("bullish", 3)])
    assert bullish.bullish_observation.state == "confirmed_retest"
    assert bullish.bullish_observation.touched_at == bars[4].end_at
    bars[4] = _bar(4, close=99.0, high=100.1, low=97.0)
    bearish = _detect(bars, [_break("bearish", 3)])
    assert bearish.bearish_observation.state == "confirmed_retest"


def test_marks_touch_without_accepted_close_and_invalidation_explicitly() -> None:
    bars = [_bar(i) for i in range(7)]
    bars[4] = _bar(4, close=99.95, high=101.0, low=99.5)
    unconfirmed = detect_retests(tuple(bars[:5]), (_break("bullish", 3),), bar_fingerprint="b", bos_choch_fingerprint="c", confirmation_close_bps=10)
    assert unconfirmed.bullish_observation.state == "unconfirmed_retest"
    bars[5] = _bar(5, close=98.0, high=100.0, low=97.0)
    invalid = _detect(bars, [_break("bullish", 3)])
    assert invalid.bullish_observation.state == "invalidated"


def test_is_deterministic_no_lookahead_and_validates_parameters() -> None:
    bars = [_bar(i) for i in range(8)]
    base = _detect(bars[:4], [_break("bullish", 3)])
    assert base.bullish_observation.state == "no_retest"
    extended = _detect(bars[:4] + [_bar(4, close=101.0, high=103.0, low=99.9)], [_break("bullish", 3)])
    assert extended.bullish_observation.state == "confirmed_retest"
    assert extended == _detect(bars[:4] + [_bar(4, close=101.0, high=103.0, low=99.9)], [_break("bullish", 3)])
    with pytest.raises(ValueError):
        detect_retests(tuple(bars), tuple(), bar_fingerprint="", bos_choch_fingerprint="x")
    with pytest.raises(ValueError):
        detect_retests(tuple(bars), tuple(), bar_fingerprint="x", bos_choch_fingerprint="y", touch_tolerance_bps=-1)
