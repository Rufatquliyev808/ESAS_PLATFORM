from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.bos_choch import StructureBreakObservation


RETEST_VERSION = "1.0.0"


@dataclass(frozen=True)
class RetestObservation:
    direction: str
    state: str
    break_type: str | None
    level: float | None
    break_observed_at: str | None
    touched_at: str | None
    observed_at: str | None
    close_distance_bps: float | None


@dataclass(frozen=True)
class RetestResult:
    version: str
    touch_tolerance_bps: float
    confirmation_close_bps: float
    invalidation_close_bps: float
    maximum_retest_age_bars: int
    observations: tuple[RetestObservation, ...]
    bullish_observation: RetestObservation
    bearish_observation: RetestObservation
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _empty(direction: str, state: str) -> RetestObservation:
    return RetestObservation(direction, state, None, None, None, None, None, None)


def detect_retests(
    bars: tuple[MarketBar, ...],
    breaks: tuple[StructureBreakObservation, ...],
    *,
    bar_fingerprint: str,
    bos_choch_fingerprint: str,
    touch_tolerance_bps: float = 5.0,
    confirmation_close_bps: float = 0.0,
    invalidation_close_bps: float = 10.0,
    maximum_retest_age_bars: int = 100,
) -> RetestResult:
    """Observe causal post-break level retests using later closed bars only."""
    if not bar_fingerprint.strip() or not bos_choch_fingerprint.strip():
        raise ValueError("upstream fingerprints must not be empty")
    for value in (touch_tolerance_bps, confirmation_close_bps, invalidation_close_bps):
        if not math.isfinite(value) or value < 0:
            raise ValueError("retest bps parameters must be finite and non-negative")
    if maximum_retest_age_bars < 1:
        raise ValueError("maximum_retest_age_bars must be positive")

    index_by_end = {bar.end_at: index for index, bar in enumerate(bars)}
    observations: list[RetestObservation] = []
    for item in breaks:
        if item.level is None or item.observed_at is None or item.direction not in {"bullish", "bearish"}:
            continue
        break_index = index_by_end.get(item.observed_at)
        if break_index is None:
            continue
        level = item.level
        tolerance = level * touch_tolerance_bps / 10_000
        confirmation = level * confirmation_close_bps / 10_000
        invalidation = level * invalidation_close_bps / 10_000
        touched_at: str | None = None
        outcome: RetestObservation | None = None
        for bar in bars[break_index + 1 : break_index + 1 + maximum_retest_age_bars]:
            touched = (
                bar.low <= level + tolerance and bar.high >= level - tolerance
            )
            if touched and touched_at is None:
                touched_at = bar.end_at
            invalidated = (
                bar.close < level - invalidation
                if item.direction == "bullish"
                else bar.close > level + invalidation
            )
            confirmed = touched and (
                bar.close >= level + confirmation
                if item.direction == "bullish"
                else bar.close <= level - confirmation
            )
            distance = abs((bar.close - level) / level * 10_000)
            if confirmed:
                outcome = RetestObservation(item.direction, "confirmed_retest", item.break_type, level, item.observed_at, touched_at, bar.end_at, distance)
                break
            if invalidated:
                outcome = RetestObservation(item.direction, "invalidated", item.break_type, level, item.observed_at, touched_at, bar.end_at, distance)
                break
        if outcome is None:
            state = "unconfirmed_retest" if touched_at else "no_retest"
            outcome = RetestObservation(item.direction, state, item.break_type, level, item.observed_at, touched_at, bars[-1].end_at if bars else None, None)
        observations.append(outcome)

    def latest(direction: str) -> RetestObservation:
        matches = [item for item in observations if item.direction == direction]
        if matches:
            return max(matches, key=lambda item: item.break_observed_at or "")
        eligible = any(item.direction == direction and item.level is not None for item in breaks)
        return _empty(direction, "no_retest" if eligible else "insufficient_data")

    bullish, bearish = latest("bullish"), latest("bearish")
    if bullish.observed_at and bullish.observed_at == bearish.observed_at and bullish.state == bearish.state == "confirmed_retest":
        bullish = RetestObservation(**{**asdict(bullish), "state": "conflicting"})
        bearish = RetestObservation(**{**asdict(bearish), "state": "conflicting"})

    payload = {
        "version": RETEST_VERSION,
        "bar_fingerprint": bar_fingerprint.strip(),
        "bos_choch_fingerprint": bos_choch_fingerprint.strip(),
        "touch_tolerance_bps": touch_tolerance_bps,
        "confirmation_close_bps": confirmation_close_bps,
        "invalidation_close_bps": invalidation_close_bps,
        "maximum_retest_age_bars": maximum_retest_age_bars,
        "observations": [asdict(item) for item in observations],
        "bullish_observation": asdict(bullish),
        "bearish_observation": asdict(bearish),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return RetestResult(RETEST_VERSION, touch_tolerance_bps, confirmation_close_bps, invalidation_close_bps, maximum_retest_age_bars, tuple(observations), bullish, bearish, f"sha256:{digest}")
