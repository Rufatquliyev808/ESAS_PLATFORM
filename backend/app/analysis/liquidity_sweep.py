from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.market_structure import StructurePivot

LIQUIDITY_SWEEP_VERSION = "1.0.0"


@dataclass(frozen=True)
class LiquidityPool:
    side: str
    level: float
    touch_count: int
    first_pivot_at: str
    last_pivot_at: str
    available_at: str
    last_confirmation_bar_index: int


@dataclass(frozen=True)
class LiquiditySweepObservation:
    direction: str
    state: str
    pool_side: str
    pool_level: float | None
    pool_touch_count: int
    observed_at: str | None
    excursion_bps: float | None
    close_back_confirmed: bool


@dataclass(frozen=True)
class LiquiditySweepResult:
    version: str
    pool_tolerance_bps: float
    minimum_touches: int
    minimum_sweep_bps: float
    maximum_pool_age_bars: int
    pools: tuple[LiquidityPool, ...]
    observations: tuple[LiquiditySweepObservation, ...]
    bullish_observation: LiquiditySweepObservation
    bearish_observation: LiquiditySweepObservation
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _empty(direction: str, pool_side: str, state: str) -> LiquiditySweepObservation:
    return LiquiditySweepObservation(direction, state, pool_side, None, 0, None, None, False)


def _build_pools(pivots: tuple[StructurePivot, ...], tolerance_bps: float, minimum_touches: int) -> list[LiquidityPool]:
    pools: list[LiquidityPool] = []
    for kind, side in (("high", "buy_side"), ("low", "sell_side")):
        clusters: list[list[StructurePivot]] = []
        for pivot in (item for item in pivots if item.kind == kind):
            match = next((cluster for cluster in clusters if abs(pivot.value - sum(x.value for x in cluster) / len(cluster)) <= abs(sum(x.value for x in cluster) / len(cluster)) * tolerance_bps / 10_000), None)
            if match is None:
                match = [pivot]
                clusters.append(match)
            else:
                match.append(pivot)
            if len(match) < minimum_touches:
                continue
            level = sum(item.value for item in match) / len(match)
            last = max(match, key=lambda item: item.confirmation_bar_index)
            pools.append(LiquidityPool(side, level, len(match), match[0].pivot_bar_end_at, match[-1].pivot_bar_end_at, last.confirmed_at, last.confirmation_bar_index))
    return sorted(pools, key=lambda item: (item.last_confirmation_bar_index, item.side, item.level))


def detect_liquidity_sweeps(
    bars: tuple[MarketBar, ...], pivots: tuple[StructurePivot, ...], *,
    bar_fingerprint: str, structure_fingerprint: str,
    pool_tolerance_bps: float = 10.0, minimum_touches: int = 2,
    minimum_sweep_bps: float = 1.0, maximum_pool_age_bars: int = 250,
) -> LiquiditySweepResult:
    """Detect closed-bar wick sweeps from pools known before the observed bar."""
    if not bar_fingerprint.strip() or not structure_fingerprint.strip():
        raise ValueError("upstream fingerprints must not be empty")
    if minimum_touches < 2 or maximum_pool_age_bars < 1:
        raise ValueError("invalid liquidity configuration")
    if not all(math.isfinite(value) and value >= 0 for value in (pool_tolerance_bps, minimum_sweep_bps)):
        raise ValueError("invalid liquidity tolerance")
    for index, bar in enumerate(bars):
        if index and (bar.symbol != bars[0].symbol or bar.timeframe != bars[0].timeframe or bar.start_at < bars[index - 1].end_at):
            raise ValueError("bars must be ordered and compatible")
        if not all(math.isfinite(value) for value in (bar.open, bar.high, bar.low, bar.close)):
            raise ValueError("bar prices must be finite")
    pools = _build_pools(pivots, pool_tolerance_bps, minimum_touches)
    observations: list[LiquiditySweepObservation] = []
    bullish: LiquiditySweepObservation | None = None
    bearish: LiquiditySweepObservation | None = None
    for pool in pools:
        for index in range(pool.last_confirmation_bar_index + 1, min(len(bars), pool.last_confirmation_bar_index + maximum_pool_age_bars + 1)):
            bar = bars[index]
            if pool.side == "buy_side":
                excursion = (bar.high - pool.level) / pool.level * 10_000
                if excursion >= minimum_sweep_bps and bar.close <= pool.level:
                    candidate = LiquiditySweepObservation("bearish", "confirmed_sweep", pool.side, pool.level, pool.touch_count, bar.end_at, excursion, True)
                    observations.append(candidate)
                    if bearish is None or candidate.observed_at > bearish.observed_at:
                        bearish = candidate
                    break
            else:
                excursion = (pool.level - bar.low) / pool.level * 10_000
                if excursion >= minimum_sweep_bps and bar.close >= pool.level:
                    candidate = LiquiditySweepObservation("bullish", "confirmed_sweep", pool.side, pool.level, pool.touch_count, bar.end_at, excursion, True)
                    observations.append(candidate)
                    if bullish is None or candidate.observed_at > bullish.observed_at:
                        bullish = candidate
                    break
    observations.sort(key=lambda item: (item.observed_at or "", item.direction, item.pool_level or 0.0))
    pool_sides = {item.side for item in pools}
    bullish = bullish or _empty("bullish", "sell_side", "no_sweep" if "sell_side" in pool_sides else "insufficient_data")
    bearish = bearish or _empty("bearish", "buy_side", "no_sweep" if "buy_side" in pool_sides else "insufficient_data")
    if bullish.observed_at is not None and bullish.observed_at == bearish.observed_at:
        bullish = replace(bullish, state="conflicting")
        bearish = replace(bearish, state="conflicting")
    payload = {
        "version": LIQUIDITY_SWEEP_VERSION, "bar_fingerprint": bar_fingerprint.strip(),
        "structure_fingerprint": structure_fingerprint.strip(), "pool_tolerance_bps": pool_tolerance_bps,
        "minimum_touches": minimum_touches, "minimum_sweep_bps": minimum_sweep_bps,
        "maximum_pool_age_bars": maximum_pool_age_bars, "pools": [asdict(item) for item in pools],
        "observations": [asdict(item) for item in observations],
        "bullish_observation": asdict(bullish), "bearish_observation": asdict(bearish),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return LiquiditySweepResult(LIQUIDITY_SWEEP_VERSION, pool_tolerance_bps, minimum_touches, minimum_sweep_bps, maximum_pool_age_bars, tuple(pools), tuple(observations), bullish, bearish, f"sha256:{digest}")
