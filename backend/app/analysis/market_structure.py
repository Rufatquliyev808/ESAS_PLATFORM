from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar

MARKET_STRUCTURE_VERSION = "1.0.0"

@dataclass(frozen=True)
class StructurePivot:
    kind: str
    classification: str
    value: float
    pivot_bar_end_at: str
    confirmed_at: str
    pivot_bar_index: int
    confirmation_bar_index: int

@dataclass(frozen=True)
class StructureSideObservation:
    side: str
    state: str
    latest_high: str | None
    latest_low: str | None
    observed_at: str | None

@dataclass(frozen=True)
class StructureConfirmationObservation:
    direction: str
    state: str
    latest_high: str | None
    latest_low: str | None
    observed_at: str

@dataclass(frozen=True)
class MarketStructureResult:
    version: str
    pivot_left: int
    pivot_right: int
    equality_tolerance_bps: float
    warmup_bars: int
    pivots: tuple[StructurePivot, ...]
    observations: tuple[StructureConfirmationObservation, ...]
    long_observation: StructureSideObservation
    short_observation: StructureSideObservation
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"

def _classification(current: float, previous: float | None, kind: str, tolerance_bps: float) -> str:
    if previous is None:
        return "initial_high" if kind == "high" else "initial_low"
    if abs(current - previous) <= abs(previous) * tolerance_bps / 10_000:
        return "EH" if kind == "high" else "EL"
    if kind == "high":
        return "HH" if current > previous else "LH"
    return "HL" if current > previous else "LL"

def _side(side: str, high: str | None, low: str | None, observed_at: str | None) -> StructureSideObservation:
    expected = ("HH", "HL") if side == "long" else ("LH", "LL")
    if high is None and low is None: state = "insufficient_data"
    elif high == expected[0] and low == expected[1]: state = "confirmed_structure"
    elif high in {None, "initial_high"} or low in {None, "initial_low"}: state = "partial"
    elif high == "EH" or low == "EL": state = "neutral"
    else: state = "conflicting"
    return StructureSideObservation(side, state, high, low, observed_at)

def _confirmation_events(pivots: tuple[StructurePivot, ...]) -> tuple[StructureConfirmationObservation, ...]:
    """Fire one event per side each time it *becomes* confirmed_structure.

    Only the transition into confirmed_structure is recorded, not every
    later pivot that keeps a still-confirmed regime going -- otherwise a
    single long-lived trend would produce many overlapping, highly
    correlated "events" and inflate an effective sample size dishonestly.
    """
    events: list[StructureConfirmationObservation] = []
    high_classification: str | None = None
    low_classification: str | None = None
    previous_long_confirmed = False
    previous_short_confirmed = False
    for pivot in pivots:
        if pivot.kind == "high":
            high_classification = pivot.classification
        else:
            low_classification = pivot.classification
        long_confirmed = high_classification == "HH" and low_classification == "HL"
        short_confirmed = high_classification == "LH" and low_classification == "LL"
        if long_confirmed and not previous_long_confirmed:
            events.append(StructureConfirmationObservation("bullish", "confirmed_structure", high_classification, low_classification, pivot.confirmed_at))
        if short_confirmed and not previous_short_confirmed:
            events.append(StructureConfirmationObservation("bearish", "confirmed_structure", high_classification, low_classification, pivot.confirmed_at))
        previous_long_confirmed, previous_short_confirmed = long_confirmed, short_confirmed
    return tuple(events)

def detect_market_structure(bars: tuple[MarketBar, ...], *, bar_fingerprint: str, pivot_left: int = 2, pivot_right: int = 2, equality_tolerance_bps: float = 0.0) -> MarketStructureResult:
    """Confirm causal swings only after the configured right-side bars close."""
    if pivot_left < 1 or pivot_right < 1: raise ValueError("pivot sizes must be positive")
    if not math.isfinite(equality_tolerance_bps) or equality_tolerance_bps < 0: raise ValueError("invalid equality tolerance")
    if not bar_fingerprint.strip(): raise ValueError("bar_fingerprint must not be empty")
    pivots: list[StructurePivot] = []
    previous = {"high": None, "low": None}
    symbol = bars[0].symbol if bars else None
    timeframe = bars[0].timeframe if bars else None
    last_end = ""
    for index, bar in enumerate(bars):
        if bar.symbol != symbol or bar.timeframe != timeframe or bar.start_at < last_end: raise ValueError("bars must be ordered and compatible")
        if not all(math.isfinite(value) for value in (bar.open, bar.high, bar.low, bar.close)): raise ValueError("bar prices must be finite")
        if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close) or bar.low > bar.high: raise ValueError("inconsistent OHLC")
        last_end = bar.end_at
        if index < pivot_left + pivot_right: continue
        candidate_index = index - pivot_right
        candidate = bars[candidate_index]
        window = bars[candidate_index - pivot_left:index + 1]
        others = [item for offset, item in enumerate(window) if offset != pivot_left]
        for kind, value, is_pivot in (("high", candidate.high, all(candidate.high > item.high for item in others)), ("low", candidate.low, all(candidate.low < item.low for item in others))):
            if is_pivot:
                label = _classification(value, previous[kind], kind, equality_tolerance_bps)
                previous[kind] = value
                pivots.append(StructurePivot(kind, label, value, candidate.end_at, bar.end_at, candidate_index, index))
    latest_high = next((item for item in reversed(pivots) if item.kind == "high"), None)
    latest_low = next((item for item in reversed(pivots) if item.kind == "low"), None)
    observed_at = max((item.confirmed_at for item in (latest_high, latest_low) if item), default=None)
    long_observation = _side("long", latest_high.classification if latest_high else None, latest_low.classification if latest_low else None, observed_at)
    short_observation = _side("short", latest_high.classification if latest_high else None, latest_low.classification if latest_low else None, observed_at)
    observations = _confirmation_events(tuple(pivots))
    payload = {"bar_fingerprint": bar_fingerprint.strip(), "version": MARKET_STRUCTURE_VERSION, "pivot_left": pivot_left, "pivot_right": pivot_right, "equality_tolerance_bps": equality_tolerance_bps, "pivots": [asdict(item) for item in pivots], "observations": [asdict(item) for item in observations], "long_observation": asdict(long_observation), "short_observation": asdict(short_observation)}
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return MarketStructureResult(MARKET_STRUCTURE_VERSION, pivot_left, pivot_right, equality_tolerance_bps, pivot_left + pivot_right + 1, tuple(pivots), observations, long_observation, short_observation, f"sha256:{digest}")
