from dataclasses import asdict, dataclass
from datetime import datetime

from backend.app.analysis.bars import TIMEFRAME_SECONDS, build_closed_mid_bars
from backend.app.analysis.replay_analysis import ReplayDatasetChangedError
from backend.app.analysis.return_series import compute_return_series
from backend.app.analysis.spread import compute_spread_statistics
from backend.app.analysis.tick_rate import compute_tick_rate_statistics
from backend.app.analysis.volatility import compute_volatility
from backend.app.database.replay_session_repository import (
    ReplaySession,
    ReplayTransitionConflictError,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.replay.dataset_snapshot import create_dataset_snapshot


STATISTICAL_ANALYSIS_API_VERSION = "1.3.0"
MAX_STATISTICAL_ANALYSIS_WINDOWS = 50_000


@dataclass(frozen=True)
class ReplayStatisticalAnalysis:
    session_id: str
    symbol: str
    timeframe: str
    start_at: str
    end_at: str
    parameters: dict[str, object]
    lineage: dict[str, object]
    return_series: dict[str, object]
    volatility: dict[str, object]
    spread: dict[str, object]
    tick_rate: dict[str, object]
    interpretation: str = "research_observation_not_trading_signal"
    api_version: str = STATISTICAL_ANALYSIS_API_VERSION


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def create_replay_statistical_analysis(
    *, session: ReplaySession, timeframe: str, minimum_sample_size: int = 30,
) -> ReplayStatisticalAnalysis:
    """Build deterministic, causal descriptive statistics (Phase 3 SA-001, SA-002, SA-003)."""
    if session.state != "completed":
        raise ReplayTransitionConflictError("Replay session is not completed")
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError("Unsupported timeframe")

    start_at, end_at = _timestamp(session.start_at), _timestamp(session.end_at)
    window_count = int((end_at - start_at).total_seconds() // TIMEFRAME_SECONDS[timeframe]) + 1
    if window_count > MAX_STATISTICAL_ANALYSIS_WINDOWS:
        raise ValueError("selected range and timeframe exceed the safe window limit")

    snapshot = create_dataset_snapshot(symbol=session.symbol, start_at=start_at, end_at=end_at)
    if (
        snapshot.tick_count != session.dataset_tick_count
        or snapshot.fingerprint != session.dataset_fingerprint
        or snapshot.first_position != session.first_position
        or snapshot.last_position != session.last_position
    ):
        raise ReplayDatasetChangedError(
            "Replay dataset no longer matches the completed session snapshot"
        )

    ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=start_at, end_at=end_at)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe=timeframe, end_at=end_at, source_fingerprint=session.dataset_fingerprint,
    )
    return_series = compute_return_series(
        bar_result.bars,
        symbol=session.symbol,
        timeframe=timeframe,
        bar_fingerprint=bar_result.fingerprint,
        minimum_window_returns=minimum_sample_size,
    )
    volatility = compute_volatility(
        bar_result.bars,
        return_series,
        bar_fingerprint=bar_result.fingerprint,
        minimum_sample=minimum_sample_size,
    )
    spread = compute_spread_statistics(
        bar_result.bars,
        bar_fingerprint=bar_result.fingerprint,
        minimum_sample=minimum_sample_size,
    )
    rate_ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=start_at, end_at=end_at)
        for tick in batch
    )
    tick_rate = compute_tick_rate_statistics(
        rate_ticks,
        symbol=session.symbol,
        timeframe=timeframe,
        start_at=start_at,
        end_at=end_at,
        minimum_sample=minimum_sample_size,
    )

    return ReplayStatisticalAnalysis(
        session_id=session.session_id,
        symbol=session.symbol,
        timeframe=timeframe,
        start_at=start_at.isoformat(),
        end_at=end_at.isoformat(),
        parameters={"minimum_sample_size": minimum_sample_size},
        lineage={
            "replay_contract_version": session.replay_contract_version,
            "dataset_tick_count": session.dataset_tick_count,
            "dataset_fingerprint": session.dataset_fingerprint,
            "dataset_fingerprint_version": snapshot.fingerprint_version,
            "bar_count": len(bar_result.bars),
            "bar_builder_version": bar_result.builder_version,
            "bar_fingerprint": bar_result.fingerprint,
            "return_series_version": return_series.version,
            "return_series_fingerprint": return_series.fingerprint,
            "volatility_version": volatility.version,
            "volatility_fingerprint": volatility.fingerprint,
            "spread_version": spread.version,
            "spread_fingerprint": spread.fingerprint,
            "tick_rate_version": tick_rate.version,
            "tick_rate_fingerprint": tick_rate.fingerprint,
        },
        return_series=asdict(return_series),
        volatility=asdict(volatility),
        spread=asdict(spread),
        tick_rate=asdict(tick_rate),
    )
