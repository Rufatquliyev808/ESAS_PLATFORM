from datetime import datetime, timedelta, timezone

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.fair_value_gap import detect_fair_value_gaps


BASE = datetime(2026, 8, 5, tzinfo=timezone.utc)


def bar(index: int, open_: float, high: float, low: float, close: float) -> MarketBar:
    start = BASE + timedelta(minutes=index)
    return MarketBar("GOLD", "M1", start, start + timedelta(minutes=1), open_, high, low, close, 1, 1, 0, 0, 0, f"e{index}", f"e{index}", "test")


def test_bullish_gap_is_formed_and_filled_only_by_future_bar():
    bars = (bar(0, 100, 101, 99, 100), bar(1, 100, 102, 100, 101), bar(2, 103, 104, 103, 104), bar(3, 104, 105, 100.5, 102))
    result = detect_fair_value_gaps(bars, bar_fingerprint="bars")
    item = result.bullish_observation
    assert item.state == "filled"
    assert item.lower_bound == 101
    assert item.upper_bound == 103
    assert item.formed_at == bars[2].end_at
    assert item.first_touched_at == bars[3].end_at
    assert item.fill_percent == 100.0


def test_bearish_gap_can_be_partially_filled():
    bars = (bar(0, 105, 106, 104, 105), bar(1, 104, 105, 102, 103), bar(2, 101, 102, 100, 101), bar(3, 101, 103, 100, 102))
    item = detect_fair_value_gaps(bars, bar_fingerprint="bars").bearish_observation
    assert item.state == "partially_filled"
    assert item.fill_percent == 50.0


def test_no_gap_and_insufficient_data_are_explicit():
    assert detect_fair_value_gaps((bar(0, 100, 101, 99, 100),), bar_fingerprint="one").bullish_observation.state == "insufficient_data"
    flat = tuple(bar(i, 100, 101, 99, 100) for i in range(3))
    assert detect_fair_value_gaps(flat, bar_fingerprint="flat").bearish_observation.state == "no_gap"


def test_fingerprint_is_deterministic():
    bars = tuple(bar(i, 100, 101, 99, 100) for i in range(3))
    first = detect_fair_value_gaps(bars, bar_fingerprint="same")
    second = detect_fair_value_gaps(bars, bar_fingerprint="same")
    assert first.fingerprint == second.fingerprint
