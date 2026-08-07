from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from backend.app.analysis.bars import TIMEFRAME_SECONDS, build_closed_mid_bars
from backend.app.analysis.indicators import build_indicator_set
from backend.app.analysis.liquidity_reaction import compute_liquidity_reaction_statistics
from backend.app.analysis.liquidity_reaction_segments import find_indicator_segments
from backend.app.analysis.liquidity_sweep import LiquidityPool, detect_liquidity_sweeps
from backend.app.analysis.market_structure import MarketStructureResult, detect_market_structure
from backend.app.analysis.oscillators import build_oscillator_set
from backend.app.database.tick_replay_repository import iter_tick_batches


LIQUIDITY_OVERVIEW_API_VERSION = "1.0.0"
OVERVIEW_TIMEFRAMES = ("M30", "H1", "H4", "D1")
DEFAULT_BAR_LIMITS = {"M30": 1000, "H1": 1000, "H4": 500, "D1": 180}
MAX_BAR_LIMIT = 5000
INSUFFICIENT_DATA = "insufficient_data"
COMPLETED = "completed"
COMPLETED_STRUCTURE_STATE = "confirmed_structure"
BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"


@dataclass(frozen=True)
class LiquidityLevel:
    side: str
    level: float
    touch_count: int
    distance_bps: float


@dataclass(frozen=True)
class TimeframeLiquidityOverview:
    timeframe: str
    status: str
    bar_count: int
    latest_close: float | None
    trend: str
    nearest_resistance: LiquidityLevel | None
    nearest_support: LiquidityLevel | None
    reaction: dict[str, object]
    segments: dict[str, object]


@dataclass(frozen=True)
class LiquidityOverviewResult:
    symbol: str
    generated_at: str
    timeframes: tuple[TimeframeLiquidityOverview, ...]
    interpretation: str = "research_observation_not_trading_signal"
    api_version: str = LIQUIDITY_OVERVIEW_API_VERSION


def _trend(structure_result: MarketStructureResult) -> str:
    if structure_result.long_observation.state == COMPLETED_STRUCTURE_STATE:
        return BULLISH
    if structure_result.short_observation.state == COMPLETED_STRUCTURE_STATE:
        return BEARISH
    if structure_result.long_observation.state == INSUFFICIENT_DATA:
        return INSUFFICIENT_DATA
    return NEUTRAL


def _nearest_level(pools: tuple[LiquidityPool, ...], side: str, current_price: float) -> LiquidityLevel | None:
    candidates = [pool for pool in pools if pool.side == side]
    if not candidates:
        return None
    beyond = [pool for pool in candidates if (pool.level >= current_price if side == "buy_side" else pool.level <= current_price)]
    chosen = (
        min(beyond, key=lambda pool: pool.level) if side == "buy_side" and beyond
        else max(beyond, key=lambda pool: pool.level) if beyond
        else min(candidates, key=lambda pool: abs(pool.level - current_price))
    )
    distance_bps = (chosen.level - current_price) / current_price * 10_000
    return LiquidityLevel(chosen.side, chosen.level, chosen.touch_count, distance_bps)


def _empty_timeframe(timeframe: str, bar_count: int) -> TimeframeLiquidityOverview:
    return TimeframeLiquidityOverview(timeframe, INSUFFICIENT_DATA, bar_count, None, INSUFFICIENT_DATA, None, None, {}, {})


def _timeframe_overview(
    *, symbol: str, timeframe: str, end_at: datetime, bar_limit: int,
    horizon_bars: int, reaction_threshold_bps: float,
) -> TimeframeLiquidityOverview:
    start_at = end_at - timedelta(seconds=TIMEFRAME_SECONDS[timeframe] * bar_limit)
    ticks = (
        tick
        for batch in iter_tick_batches(symbol=symbol, start_at=start_at, end_at=end_at)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe=timeframe, end_at=end_at,
        source_fingerprint=f"live:{symbol}:{timeframe}:{end_at.isoformat()}",
    )
    if not bar_result.bars:
        return _empty_timeframe(timeframe, 0)

    structure_result = detect_market_structure(bar_result.bars, bar_fingerprint=bar_result.fingerprint)
    sweep_result = detect_liquidity_sweeps(
        bar_result.bars, structure_result.pivots,
        bar_fingerprint=bar_result.fingerprint, structure_fingerprint=structure_result.fingerprint,
    )
    reaction_result = compute_liquidity_reaction_statistics(
        bar_result.bars, sweep_result.pools, bar_fingerprint=bar_result.fingerprint,
        horizon_bars=horizon_bars, reaction_threshold_bps=reaction_threshold_bps,
    )
    indicator_result = build_indicator_set(bar_result.bars, bar_fingerprint=bar_result.fingerprint)
    oscillator_result = build_oscillator_set(bar_result.bars, bar_fingerprint=bar_result.fingerprint)
    buy_segments = find_indicator_segments(
        reaction_result.events, "buy_side", indicators=indicator_result, oscillators=oscillator_result,
    )
    sell_segments = find_indicator_segments(
        reaction_result.events, "sell_side", indicators=indicator_result, oscillators=oscillator_result,
    )
    current_price = bar_result.bars[-1].close

    return TimeframeLiquidityOverview(
        timeframe=timeframe, status=COMPLETED, bar_count=len(bar_result.bars),
        latest_close=current_price, trend=_trend(structure_result),
        nearest_resistance=_nearest_level(sweep_result.pools, "buy_side", current_price),
        nearest_support=_nearest_level(sweep_result.pools, "sell_side", current_price),
        reaction=asdict(reaction_result),
        segments={"buy_side": asdict(buy_segments), "sell_side": asdict(sell_segments)},
    )


def create_liquidity_overview(
    *, symbol: str, timeframes: tuple[str, ...] = OVERVIEW_TIMEFRAMES,
    horizon_bars: int = 20, reaction_threshold_bps: float = 5.0,
    bar_limits: dict[str, int] | None = None,
) -> LiquidityOverviewResult:
    """Live, non-reproducible multi-timeframe liquidity overview (research
    only): for each timeframe, the current trend (from market structure),
    the nearest resistance/support levels to the current price, and the
    historical reaction backtest + indicator-segment statistics for that
    timeframe's liquidity pools. Like `live_analysis.py`, this does not
    operate on a fixed replay snapshot -- it is expected to change as new
    ticks arrive.
    """
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if not timeframes:
        raise ValueError("timeframes must not be empty")
    for timeframe in timeframes:
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

    limits = bar_limits or DEFAULT_BAR_LIMITS
    end_at = datetime.now(UTC)
    overviews = tuple(
        _timeframe_overview(
            symbol=normalized_symbol, timeframe=timeframe, end_at=end_at,
            bar_limit=min(limits.get(timeframe, 1000), MAX_BAR_LIMIT),
            horizon_bars=horizon_bars, reaction_threshold_bps=reaction_threshold_bps,
        )
        for timeframe in timeframes
    )
    return LiquidityOverviewResult(normalized_symbol, end_at.isoformat(), overviews)
