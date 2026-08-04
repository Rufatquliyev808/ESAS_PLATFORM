from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from backend.app.analysis.bars import BarBuildResult, TIMEFRAME_SECONDS, build_closed_mid_bars
from backend.app.analysis.indicators import IndicatorSetResult, build_indicator_set
from backend.app.database.replay_session_repository import (
    ReplaySession,
    ReplayTransitionConflictError,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.replay.dataset_snapshot import create_dataset_snapshot


ANALYSIS_API_VERSION = "1.0.0"
MAX_ANALYSIS_BARS = 5_000


class ReplayDatasetChangedError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReplayTechnicalAnalysis:
    session_id: str
    symbol: str
    timeframe: str
    start_at: str
    end_at: str
    parameters: dict[str, int]
    lineage: dict[str, object]
    bars: tuple[dict[str, object], ...]
    indicators: dict[str, object]
    interpretation: str = "research_observation_not_trading_signal"
    api_version: str = ANALYSIS_API_VERSION


@dataclass(frozen=True)
class ReplayAnalysisContext:
    analysis: ReplayTechnicalAnalysis
    bars: BarBuildResult
    indicators: IndicatorSetResult


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def create_replay_technical_analysis(
    *,
    session: ReplaySession,
    timeframe: str,
    ema_period: int,
    rsi_period: int,
    atr_period: int,
    bar_limit: int,
) -> ReplayTechnicalAnalysis:
    return create_replay_analysis_context(
        session=session,
        timeframe=timeframe,
        ema_period=ema_period,
        rsi_period=rsi_period,
        atr_period=atr_period,
        bar_limit=bar_limit,
    ).analysis


def create_replay_analysis_context(
    *,
    session: ReplaySession,
    timeframe: str,
    ema_period: int,
    rsi_period: int,
    atr_period: int,
    bar_limit: int,
) -> ReplayAnalysisContext:
    """Build deterministic, read-only indicators from a completed replay snapshot."""
    if session.state != "completed":
        raise ReplayTransitionConflictError("Replay session is not completed")
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError("Unsupported timeframe")
    if not 1 <= bar_limit <= MAX_ANALYSIS_BARS:
        raise ValueError("bar_limit is outside the safe range")

    start_at = _timestamp(session.start_at)
    end_at = _timestamp(session.end_at)
    snapshot = create_dataset_snapshot(
        symbol=session.symbol,
        start_at=start_at,
        end_at=end_at,
    )
    if (
        snapshot.tick_count != session.dataset_tick_count
        or snapshot.fingerprint != session.dataset_fingerprint
        or snapshot.first_position != session.first_position
        or snapshot.last_position != session.last_position
    ):
        raise ReplayDatasetChangedError(
            "Replay dataset no longer matches the completed session snapshot"
        )

    analysis_start = max(
        start_at,
        end_at - timedelta(seconds=TIMEFRAME_SECONDS[timeframe] * bar_limit),
    )
    ticks = (
        tick
        for batch in iter_tick_batches(
            symbol=session.symbol,
            start_at=analysis_start,
            end_at=end_at,
        )
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks,
        timeframe=timeframe,
        end_at=end_at,
        source_fingerprint=session.dataset_fingerprint,
    )
    indicator_result = build_indicator_set(
        bar_result.bars,
        bar_fingerprint=bar_result.fingerprint,
        ema_period=ema_period,
        rsi_period=rsi_period,
        atr_period=atr_period,
    )

    analysis = ReplayTechnicalAnalysis(
        session_id=session.session_id,
        symbol=session.symbol,
        timeframe=timeframe,
        start_at=analysis_start.isoformat(),
        end_at=end_at.isoformat(),
        parameters={
            "ema_period": ema_period,
            "rsi_period": rsi_period,
            "atr_period": atr_period,
            "bar_limit": bar_limit,
        },
        lineage={
            "replay_contract_version": session.replay_contract_version,
            "dataset_tick_count": session.dataset_tick_count,
            "dataset_fingerprint": session.dataset_fingerprint,
            "dataset_fingerprint_version": snapshot.fingerprint_version,
            "bar_count": len(bar_result.bars),
            "bar_builder_version": bar_result.builder_version,
            "bar_fingerprint": bar_result.fingerprint,
            "indicator_package_version": indicator_result.package_version,
            "indicator_fingerprint": indicator_result.fingerprint,
        },
        bars=tuple(asdict(bar) for bar in bar_result.bars),
        indicators={
            "ema": asdict(indicator_result.ema),
            "rsi": asdict(indicator_result.rsi),
            "atr": asdict(indicator_result.atr),
        },
    )
    return ReplayAnalysisContext(analysis=analysis, bars=bar_result, indicators=indicator_result)
