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

def test_confirmation_events_fire_only_on_transition_into_confirmed() -> None:
    highs_lows = [(15,3),(20,4),(16,10),(18,9),(24,14),(19,17),(20,13),(28,19),(21,12),(23,15),(20,14)]
    bars = tuple(bar(i, h, l) for i, (h, l) in enumerate(highs_lows))
    result = detect_market_structure(bars, bar_fingerprint="bars", pivot_left=1, pivot_right=1)
    # Two HH pivots keep the long regime confirmed, but only the *first*
    # one (the transition into confirmed_structure) should fire an event.
    assert [p.classification for p in result.pivots if p.kind == "high"] == ["initial_high", "HH", "HH", "LH"]
    assert len(result.observations) == 2
    bullish, bearish = result.observations
    assert bullish.direction == "bullish"
    assert bullish.observed_at == bars[7].end_at
    assert bearish.direction == "bearish"
    assert bearish.observed_at == bars[10].end_at
    assert bearish.observed_at > bullish.observed_at
    # The long side was later invalidated by a lower low, and the short
    # side is now confirmed -- no duplicate or stale event for either.
    assert result.long_observation.state == "conflicting"
    assert result.short_observation.state == "confirmed_structure"

def test_observations_are_deterministic() -> None:
    highs_lows = [(15,3),(20,4),(16,10),(18,9),(24,14),(19,17),(20,13),(28,19),(21,12),(23,15),(20,14)]
    bars = tuple(bar(i, h, l) for i, (h, l) in enumerate(highs_lows))
    first = detect_market_structure(bars, bar_fingerprint="bars", pivot_left=1, pivot_right=1)
    second = detect_market_structure(bars, bar_fingerprint="bars", pivot_left=1, pivot_right=1)
    assert first.observations == second.observations

def test_no_events_without_a_confirmed_regime() -> None:
    bars = tuple(bar(i, h, l) for i, (h, l) in enumerate([(15,3),(20,4),(16,10),(18,9)]))
    result = detect_market_structure(bars, bar_fingerprint="bars", pivot_left=1, pivot_right=1)
    assert result.observations == ()
