from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.liquidity_sweep import LiquidityPool


REACTION_VERSION = "1.0.0"
Z_95 = 1.96
MIN_EFFECTIVE_SAMPLE = 30
REVERSED = "reversed"
CONTINUED = "continued"
AMBIGUOUS = "ambiguous"
COMPLETED = "completed"
INSUFFICIENT_DATA = "insufficient_data"
BUY_SIDE = "buy_side"
SELL_SIDE = "sell_side"


@dataclass(frozen=True)
class ReactionEvent:
    pool_side: str
    pool_level: float
    touched_at: str
    outcome: str
    excursion_bps: float | None


@dataclass(frozen=True)
class ReactionStatistics:
    pool_side: str
    status: str
    n_total: int
    n_reversed: int
    n_continued: int
    n_ambiguous: int
    reversed_percent: float | None
    confidence_interval_low_percent: float | None
    confidence_interval_high_percent: float | None


@dataclass(frozen=True)
class LiquidityReactionResult:
    version: str
    symbol: str
    timeframe: str
    horizon_bars: int
    reaction_threshold_bps: float
    events: tuple[ReactionEvent, ...]
    buy_side_statistics: ReactionStatistics
    sell_side_statistics: ReactionStatistics
    fingerprint: str
    interpretation: str = "research_observation_not_trading_signal"


def _classify_touch_outcome(
    bars: tuple[MarketBar, ...], touch_index: int, pool: LiquidityPool,
    *, threshold_bps: float, horizon_bars: int,
) -> tuple[str, float | None]:
    """Look forward from the touch bar (inclusive, since it is already closed) up to
    `horizon_bars` further bars, tracking the largest close-based move away from the
    pool level in either direction. Reversed = price closes back on the approach
    side; continued = price closes through to the far side. Whichever crosses the
    threshold with the larger magnitude wins; if neither does, the touch is
    ambiguous (excluded from the directional percentage, not treated as either
    outcome)."""
    level = pool.level
    end = min(len(bars), touch_index + 1 + horizon_bars)
    best_reversal = 0.0
    best_continuation = 0.0
    for index in range(touch_index, end):
        close = bars[index].close
        if pool.side == BUY_SIDE:
            reversal_bps = (level - close) / level * 10_000
            continuation_bps = (close - level) / level * 10_000
        else:
            reversal_bps = (close - level) / level * 10_000
            continuation_bps = (level - close) / level * 10_000
        best_reversal = max(best_reversal, reversal_bps)
        best_continuation = max(best_continuation, continuation_bps)
    if best_reversal >= threshold_bps and best_reversal >= best_continuation:
        return REVERSED, best_reversal
    if best_continuation >= threshold_bps and best_continuation > best_reversal:
        return CONTINUED, best_continuation
    return AMBIGUOUS, None


def _touched(bar: MarketBar, pool: LiquidityPool) -> bool:
    return bar.high >= pool.level if pool.side == BUY_SIDE else bar.low <= pool.level


def _events_for_pool(
    bars: tuple[MarketBar, ...], pool: LiquidityPool,
    *, threshold_bps: float, horizon_bars: int,
) -> list[ReactionEvent]:
    events: list[ReactionEvent] = []
    embargo_until_index: int | None = None
    index = pool.last_confirmation_bar_index + 1
    while index < len(bars):
        if embargo_until_index is not None and index < embargo_until_index:
            index += 1
            continue
        bar = bars[index]
        if not _touched(bar, pool):
            index += 1
            continue
        outcome, excursion = _classify_touch_outcome(
            bars, index, pool, threshold_bps=threshold_bps, horizon_bars=horizon_bars,
        )
        events.append(ReactionEvent(pool.side, pool.level, bar.end_at, outcome, excursion))
        embargo_until_index = index + 1 + horizon_bars
        index = embargo_until_index
    return events


def _quantile_bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


def _summarize_side(side: str, events: list[ReactionEvent]) -> ReactionStatistics:
    n_total = len(events)
    n_reversed = sum(1 for item in events if item.outcome == REVERSED)
    n_continued = sum(1 for item in events if item.outcome == CONTINUED)
    n_ambiguous = sum(1 for item in events if item.outcome == AMBIGUOUS)
    directional = n_reversed + n_continued
    if directional < MIN_EFFECTIVE_SAMPLE:
        return ReactionStatistics(
            side, INSUFFICIENT_DATA, n_total, n_reversed, n_continued, n_ambiguous,
            None, None, None,
        )
    proportion = n_reversed / directional
    margin = Z_95 * math.sqrt(proportion * (1 - proportion) / directional)
    return ReactionStatistics(
        side, COMPLETED, n_total, n_reversed, n_continued, n_ambiguous,
        proportion * 100.0,
        _quantile_bounded((proportion - margin) * 100.0),
        _quantile_bounded((proportion + margin) * 100.0),
    )


def _fingerprint(
    *, bar_fingerprint: str, horizon_bars: int, reaction_threshold_bps: float,
    events: tuple[ReactionEvent, ...],
) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "events": [asdict(item) for item in events],
        "horizon_bars": horizon_bars,
        "reaction_threshold_bps": reaction_threshold_bps,
        "version": REACTION_VERSION,
    }
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def compute_liquidity_reaction_statistics(
    bars: tuple[MarketBar, ...], pools: tuple[LiquidityPool, ...],
    *, bar_fingerprint: str, horizon_bars: int = 20, reaction_threshold_bps: float = 5.0,
) -> LiquidityReactionResult:
    """Historical reaction statistics (SA/Phase-4-style backtest, research only):
    each time price touches a known liquidity pool level, classify whether it
    later reverses (closes back on the approach side) or continues through
    (closes past the level) within `horizon_bars`, then report the reversed
    percentage with a 95% confidence interval for buy_side (resistance,
    approached from below) and sell_side (support, approached from above)
    pools separately. Overlapping touches of the same pool are purged with an
    embargo of `horizon_bars`, matching the purge/embargo convention used
    elsewhere for pattern-candidate backtests.
    """
    if isinstance(horizon_bars, bool) or not isinstance(horizon_bars, int) or horizon_bars < 1:
        raise ValueError("horizon_bars must be a positive integer")
    if not math.isfinite(reaction_threshold_bps) or reaction_threshold_bps <= 0:
        raise ValueError("reaction_threshold_bps must be finite and positive")
    normalized_fingerprint = bar_fingerprint.strip()
    if not normalized_fingerprint:
        raise ValueError("bar_fingerprint must not be empty")
    symbol = bars[0].symbol if bars else ""
    timeframe = bars[0].timeframe if bars else ""

    all_events: list[ReactionEvent] = []
    for pool in pools:
        all_events.extend(
            _events_for_pool(bars, pool, threshold_bps=reaction_threshold_bps, horizon_bars=horizon_bars)
        )
    all_events.sort(key=lambda item: (item.touched_at, item.pool_side, item.pool_level))

    buy_side_events = [item for item in all_events if item.pool_side == BUY_SIDE]
    sell_side_events = [item for item in all_events if item.pool_side == SELL_SIDE]

    fingerprint = _fingerprint(
        bar_fingerprint=normalized_fingerprint, horizon_bars=horizon_bars,
        reaction_threshold_bps=reaction_threshold_bps, events=tuple(all_events),
    )

    return LiquidityReactionResult(
        REACTION_VERSION, symbol, timeframe, horizon_bars, reaction_threshold_bps,
        tuple(all_events),
        _summarize_side(BUY_SIDE, buy_side_events),
        _summarize_side(SELL_SIDE, sell_side_events),
        fingerprint,
    )
