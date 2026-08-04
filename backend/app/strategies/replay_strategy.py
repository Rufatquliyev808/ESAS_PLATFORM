from dataclasses import asdict, dataclass

from backend.app.analysis.replay_analysis import create_replay_analysis_context
from backend.app.database.replay_session_repository import ReplaySession
from backend.app.strategies.ema_close_relation import evaluate_ema_close_relation


STRATEGY_ANALYSIS_API_VERSION = "1.0.0"


@dataclass(frozen=True)
class ReplayStrategyAnalysis:
    session_id: str
    symbol: str
    timeframe: str
    parameters: dict[str, int]
    lineage: dict[str, object]
    strategies: tuple[dict[str, object], ...]
    interpretation: str = "research_observation_not_trading_signal"
    api_version: str = STRATEGY_ANALYSIS_API_VERSION


def create_replay_strategy_analysis(
    *, session: ReplaySession, timeframe: str, ema_period: int, bar_limit: int
) -> ReplayStrategyAnalysis:
    """Evaluate independently versioned research strategies on completed replay bars."""
    context = create_replay_analysis_context(
        session=session,
        timeframe=timeframe,
        ema_period=ema_period,
        rsi_period=14,
        atr_period=14,
        bar_limit=bar_limit,
    )
    result = evaluate_ema_close_relation(
        symbol=session.symbol,
        timeframe=timeframe,
        bars=context.bars.bars,
        indicators=context.indicators,
        dataset_fingerprint=session.dataset_fingerprint,
    )
    return ReplayStrategyAnalysis(
        session_id=session.session_id,
        symbol=session.symbol,
        timeframe=timeframe,
        parameters={"ema_period": ema_period, "bar_limit": bar_limit},
        lineage=context.analysis.lineage,
        strategies=(asdict(result),),
    )
