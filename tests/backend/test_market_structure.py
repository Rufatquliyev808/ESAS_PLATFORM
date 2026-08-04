from backend.app.analysis.bars import MarketBar
from backend.app.analysis.market_structure import detect_market_structure

def bar(index: int, high: float, low: float) -> MarketBar:
    return MarketBar("GOLD", "M1", f"2026-01-01T00:{index:02}:00+00:00", f"2026-01-01T00:{index+1:02}:00+00:00", low + 1, high, low, high - 1, 1, 1, 1, 1, 1, str(index), str(index))

def test_pivot_waits_for_right_bars() -> None:
    bars = tuple(bar(i, h, l) for i, (h, l) in enumerate([(2,0),(3,1),(5,2),(4,1),(3,0)]))
    assert detect_market_structure(bars[:4], bar_fingerprint="x").pivots == ()
    pivot = detect_market_structure(bars, bar_fingerprint="x").pivots[0]
    assert (pivot.pivot_bar_index, pivot.confirmation_bar_index, pivot.confirmed_at) == (2, 4, bars[4].end_at)

def test_deterministic_and_separate_sides() -> None:
    bars = tuple(bar(i, h, l) for i, (h, l) in enumerate([(2,0),(3,1),(5,2),(4,1),(3,0),(4,1),(6,3),(5,2),(4,1)]))
    first = detect_market_structure(bars, bar_fingerprint="bars")
    assert first == detect_market_structure(bars, bar_fingerprint="bars")
    assert first.long_observation.side == "long" and first.short_observation.side == "short"

def test_tolerance_classifies_equal_high() -> None:
    bars = tuple(bar(i, h, l) for i, (h, l) in enumerate([(2,0),(3,1),(5,2),(4,1),(3,0),(4,1),(5.004,2),(4,1),(3,0)]))
    result = detect_market_structure(bars, bar_fingerprint="bars", equality_tolerance_bps=10)
    assert [p.classification for p in result.pivots if p.kind == "high"] == ["initial_high", "EH"]
