from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from backend.app.analysis.bars import TIMEFRAME_SECONDS, build_closed_mid_bars
from backend.app.analysis.indicator_consensus import compute_indicator_consensus
from backend.app.analysis.indicators import build_indicator_set
from backend.app.database.tick_replay_repository import iter_tick_batches


LIVE_ANALYSIS_API_VERSION = "1.0.0"
MAX_LIVE_ANALYSIS_BARS = 1_000


@dataclass(frozen=True)
class LiveTechnicalSummary:
    symbol: str
    timeframe: str
    generated_at: str
    start_at: str
    end_at: str
    parameters: dict[str, object]
    lineage: dict[str, object]
    indicators: dict[str, object]
    consensus: dict[str, object]
    interpretation: str = "research_observation_not_trading_signal"
    api_version: str = LIVE_ANALYSIS_API_VERSION


def create_live_technical_summary(
    *, symbol: str, timeframe: str, ema_period: int = 20, rsi_period: int = 14,
    atr_period: int = 14, bar_limit: int = 100,
) -> LiveTechnicalSummary:
    """Build a rolling, non-reproducible indicator consensus from the most recent
    ticks, up to now. Unlike every other analysis module, this deliberately does
    NOT operate on a fixed, fingerprinted replay snapshot -- a live view is
    expected to change on every call, so there is no dataset-drift guard here.
    """
    normalized_symbol = symbol.strip()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError("Unsupported timeframe")
    if not 1 <= bar_limit <= MAX_LIVE_ANALYSIS_BARS:
        raise ValueError("bar_limit is outside the safe range")

    end_at = datetime.now(UTC)
    start_at = end_at - timedelta(seconds=TIMEFRAME_SECONDS[timeframe] * bar_limit)
    ticks = (
        tick
        for batch in iter_tick_batches(symbol=normalized_symbol, start_at=start_at, end_at=end_at)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe=timeframe, end_at=end_at,
        source_fingerprint=f"live:{normalized_symbol}:{end_at.isoformat()}",
    )
    indicator_result = build_indicator_set(
        bar_result.bars, bar_fingerprint=bar_result.fingerprint,
        ema_period=ema_period, rsi_period=rsi_period, atr_period=atr_period,
    )
    if bar_result.bars:
        consensus = compute_indicator_consensus(bars=bar_result.bars, indicators=indicator_result)
        consensus_payload = asdict(consensus)
    else:
        consensus_payload = None

    return LiveTechnicalSummary(
        symbol=normalized_symbol,
        timeframe=timeframe,
        generated_at=end_at.isoformat(),
        start_at=start_at.isoformat(),
        end_at=end_at.isoformat(),
        parameters={
            "ema_period": ema_period, "rsi_period": rsi_period,
            "atr_period": atr_period, "bar_limit": bar_limit,
        },
        lineage={
            "bar_count": len(bar_result.bars),
            "bar_builder_version": bar_result.builder_version,
            "bar_fingerprint": bar_result.fingerprint,
            "indicator_package_version": indicator_result.package_version,
            "indicator_fingerprint": indicator_result.fingerprint,
            "reproducible": False,
            "reproducibility_note": (
                "rolling live window, not a fixed snapshot -- repeated calls "
                "will differ as new ticks arrive"
            ),
        },
        indicators={
            "ema": asdict(indicator_result.ema),
            "rsi": asdict(indicator_result.rsi),
            "atr": asdict(indicator_result.atr),
        },
        consensus=consensus_payload,
    )
