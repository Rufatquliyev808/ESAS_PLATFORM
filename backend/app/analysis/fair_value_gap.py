from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math

from .bars import MarketBar


FVG_VERSION = "1.0.0"


@dataclass(frozen=True)
class FairValueGapObservation:
    direction: str
    state: str
    lower_bound: float | None
    upper_bound: float | None
    gap_bps: float | None
    formed_at: datetime | None
    first_touched_at: datetime | None
    observed_at: datetime | None
    fill_percent: float


@dataclass(frozen=True)
class FairValueGapResult:
    version: str
    minimum_gap_bps: float
    observations: tuple[FairValueGapObservation, ...]
    bullish_observation: FairValueGapObservation
    bearish_observation: FairValueGapObservation
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _empty(direction: str, state: str, observed_at: datetime | None) -> FairValueGapObservation:
    return FairValueGapObservation(direction, state, None, None, None, None, None, observed_at, 0.0)


def _validate(bars: tuple[MarketBar, ...], minimum_gap_bps: float) -> None:
    if not math.isfinite(minimum_gap_bps) or minimum_gap_bps < 0:
        raise ValueError("minimum_gap_bps must be finite and non-negative")
    if not bars:
        return
    symbol, timeframe = bars[0].symbol, bars[0].timeframe
    previous_end = None
    for bar in bars:
        values = (bar.open, bar.high, bar.low, bar.close)
        if bar.symbol != symbol or bar.timeframe != timeframe:
            raise ValueError("bars must share symbol and timeframe")
        if not all(math.isfinite(value) for value in values) or bar.high < max(bar.open, bar.low, bar.close) or bar.low > min(bar.open, bar.high, bar.close):
            raise ValueError("bars contain invalid OHLC values")
        if previous_end is not None and bar.end_at <= previous_end:
            raise ValueError("bars must be strictly chronological")
        previous_end = bar.end_at


def _resolve_state(direction: str, lower: float, upper: float, future: tuple[MarketBar, ...]) -> tuple[str, datetime | None, datetime | None, float]:
    state, first_touch, observed_at, fill = "open", None, None, 0.0
    width = upper - lower
    for bar in future:
        if direction == "bullish":
            touched = bar.low < upper
            candidate = (upper - min(upper, max(lower, bar.low))) / width * 100.0
            if bar.close < lower:
                state = "invalidated"
            elif bar.low <= lower:
                state = "filled"
            elif touched:
                state = "partially_filled"
        else:
            touched = bar.high > lower
            candidate = (min(upper, max(lower, bar.high)) - lower) / width * 100.0
            if bar.close > upper:
                state = "invalidated"
            elif bar.high >= upper:
                state = "filled"
            elif touched:
                state = "partially_filled"
        if touched and first_touch is None:
            first_touch = bar.end_at
        if touched:
            fill = max(fill, candidate)
        if state in {"filled", "invalidated"}:
            observed_at = bar.end_at
            break
    return state, first_touch, observed_at, round(fill, 6)


def detect_fair_value_gaps(
    bars: tuple[MarketBar, ...], *, bar_fingerprint: str, minimum_gap_bps: float = 1.0
) -> FairValueGapResult:
    _validate(bars, minimum_gap_bps)
    observations: list[FairValueGapObservation] = []
    for index in range(2, len(bars)):
        first, current = bars[index - 2], bars[index]
        candidates: list[tuple[str, float, float]] = []
        if current.low > first.high:
            candidates.append(("bullish", first.high, current.low))
        if current.high < first.low:
            candidates.append(("bearish", current.high, first.low))
        for direction, lower, upper in candidates:
            midpoint = (lower + upper) / 2.0
            gap_bps = (upper - lower) / midpoint * 10_000.0
            if gap_bps < minimum_gap_bps:
                continue
            state, touched_at, resolved_at, fill = _resolve_state(direction, lower, upper, bars[index + 1 :])
            observations.append(FairValueGapObservation(direction, state, lower, upper, round(gap_bps, 6), current.end_at, touched_at, resolved_at or bars[-1].end_at, fill))

    latest_at = bars[-1].end_at if bars else None
    fallback = "insufficient_data" if len(bars) < 3 else "no_gap"
    bullish = max((item for item in observations if item.direction == "bullish"), key=lambda item: item.formed_at, default=_empty("bullish", fallback, latest_at))
    bearish = max((item for item in observations if item.direction == "bearish"), key=lambda item: item.formed_at, default=_empty("bearish", fallback, latest_at))
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "version": FVG_VERSION,
        "minimum_gap_bps": minimum_gap_bps,
        "observations": [asdict(item) for item in observations],
        "bullish_observation": asdict(bullish),
        "bearish_observation": asdict(bearish),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=lambda value: value.isoformat(), allow_nan=False).encode()
    fingerprint = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    return FairValueGapResult(FVG_VERSION, minimum_gap_bps, tuple(observations), bullish, bearish, fingerprint)
