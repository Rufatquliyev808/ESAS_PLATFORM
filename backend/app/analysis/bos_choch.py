from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.market_structure import StructurePivot


BOS_CHOCH_VERSION = "1.0.0"


@dataclass(frozen=True)
class StructureBreakObservation:
    direction: str
    state: str
    break_type: str | None
    broken_pivot_kind: str | None
    broken_pivot_classification: str | None
    level: float | None
    pivot_confirmed_at: str | None
    observed_at: str | None
    close_distance_bps: float | None


@dataclass(frozen=True)
class BosChochResult:
    version: str
    minimum_close_break_bps: float
    maximum_pivot_age_bars: int
    observations: tuple[StructureBreakObservation, ...]
    bullish_observation: StructureBreakObservation
    bearish_observation: StructureBreakObservation
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _empty(direction: str, state: str) -> StructureBreakObservation:
    return StructureBreakObservation(direction, state, None, None, None, None, None, None, None)


def _regime_at(pivots: tuple[StructurePivot, ...], confirmation_index: int) -> str:
    known = [item for item in pivots if item.confirmation_bar_index <= confirmation_index]
    high = next((item for item in reversed(known) if item.kind == "high"), None)
    low = next((item for item in reversed(known) if item.kind == "low"), None)
    if high and low and high.classification == "HH" and low.classification == "HL":
        return "bullish"
    if high and low and high.classification == "LH" and low.classification == "LL":
        return "bearish"
    return "neutral"


def detect_bos_choch(
    bars: tuple[MarketBar, ...],
    pivots: tuple[StructurePivot, ...],
    *,
    bar_fingerprint: str,
    structure_fingerprint: str,
    minimum_close_break_bps: float = 1.0,
    maximum_pivot_age_bars: int = 250,
) -> BosChochResult:
    """Detect causal close-confirmed structure breaks after pivot confirmation."""
    if not bar_fingerprint.strip() or not structure_fingerprint.strip():
        raise ValueError("upstream fingerprints must not be empty")
    if not math.isfinite(minimum_close_break_bps) or minimum_close_break_bps < 0:
        raise ValueError("minimum_close_break_bps must be finite and non-negative")
    if maximum_pivot_age_bars < 1:
        raise ValueError("maximum_pivot_age_bars must be positive")

    symbol = bars[0].symbol if bars else None
    timeframe = bars[0].timeframe if bars else None
    last_end = ""
    for bar in bars:
        if bar.symbol != symbol or bar.timeframe != timeframe or bar.start_at < last_end:
            raise ValueError("bars must be ordered and compatible")
        if not all(math.isfinite(value) for value in (bar.open, bar.high, bar.low, bar.close)):
            raise ValueError("bar prices must be finite")
        if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close) or bar.low > bar.high:
            raise ValueError("inconsistent OHLC")
        last_end = bar.end_at

    observations: list[StructureBreakObservation] = []
    seen: set[tuple[str, str, float]] = set()
    for pivot in pivots:
        direction = "bullish" if pivot.kind == "high" else "bearish"
        regime = _regime_at(pivots, pivot.confirmation_bar_index)
        start = pivot.confirmation_bar_index + 1
        stop = min(len(bars), start + maximum_pivot_age_bars)
        for bar in bars[start:stop]:
            threshold = pivot.value * minimum_close_break_bps / 10_000
            distance = (bar.close - pivot.value) / pivot.value * 10_000
            broken = bar.close >= pivot.value + threshold if direction == "bullish" else bar.close <= pivot.value - threshold
            if not broken:
                continue
            break_type = "BOS" if regime == direction else "CHOCH" if regime != "neutral" else "unclassified_break"
            state = "confirmed_bos" if break_type == "BOS" else "confirmed_choch" if break_type == "CHOCH" else "unclassified_break"
            key = (direction, bar.end_at, pivot.value)
            if key not in seen:
                seen.add(key)
                observations.append(StructureBreakObservation(
                    direction, state, break_type, pivot.kind, pivot.classification,
                    pivot.value, pivot.confirmed_at, bar.end_at, abs(distance),
                ))
            break

    def latest(direction: str) -> StructureBreakObservation:
        matches = [item for item in observations if item.direction == direction]
        if matches:
            return max(matches, key=lambda item: item.observed_at or "")
        eligible = any(item.kind == ("high" if direction == "bullish" else "low") for item in pivots)
        return _empty(direction, "no_break" if eligible else "insufficient_data")

    bullish = latest("bullish")
    bearish = latest("bearish")
    if bullish.observed_at and bullish.observed_at == bearish.observed_at:
        bullish = StructureBreakObservation(**{**asdict(bullish), "state": "conflicting"})
        bearish = StructureBreakObservation(**{**asdict(bearish), "state": "conflicting"})

    payload = {
        "version": BOS_CHOCH_VERSION,
        "bar_fingerprint": bar_fingerprint.strip(),
        "structure_fingerprint": structure_fingerprint.strip(),
        "minimum_close_break_bps": minimum_close_break_bps,
        "maximum_pivot_age_bars": maximum_pivot_age_bars,
        "observations": [asdict(item) for item in observations],
        "bullish_observation": asdict(bullish),
        "bearish_observation": asdict(bearish),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return BosChochResult(
        BOS_CHOCH_VERSION, minimum_close_break_bps, maximum_pivot_age_bars,
        tuple(observations), bullish, bearish, f"sha256:{digest}",
    )
