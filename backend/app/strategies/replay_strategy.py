from dataclasses import asdict, dataclass

from backend.app.analysis.replay_analysis import create_replay_analysis_context
from backend.app.database.replay_session_repository import ReplaySession
from backend.app.strategies.ema_close_relation import evaluate_ema_close_relation
from backend.app.strategies.rsi_regime_observation import evaluate_rsi_regime_observation
from backend.app.strategies.outcome_evaluation import evaluate_strategy_outcomes


STRATEGY_ANALYSIS_API_VERSION = "1.0.0"


@dataclass(frozen=True)
class ReplayStrategyAnalysis:
    session_id: str
    symbol: str
    timeframe: str
    parameters: dict[str, int | float]
    lineage: dict[str, object]
    strategies: tuple[dict[str, object], ...]
    interpretation: str = "research_observation_not_trading_signal"
    api_version: str = STRATEGY_ANALYSIS_API_VERSION


def create_replay_strategy_analysis(
    *, session: ReplaySession, timeframe: str, ema_period: int, rsi_period: int,
    rsi_low: float, rsi_high: float, bar_limit: int, outcome_horizon: int
) -> ReplayStrategyAnalysis:
    """Evaluate independently versioned research strategies on completed replay bars."""
    context = create_replay_analysis_context(
        session=session,
        timeframe=timeframe,
        ema_period=ema_period,
        rsi_period=rsi_period,
        atr_period=14,
        bar_limit=bar_limit,
    )
    ema_result = evaluate_ema_close_relation(
        symbol=session.symbol,
        timeframe=timeframe,
        bars=context.bars.bars,
        indicators=context.indicators,
        dataset_fingerprint=session.dataset_fingerprint,
    )
    rsi_result = evaluate_rsi_regime_observation(
        symbol=session.symbol, timeframe=timeframe, bars=context.bars.bars,
        indicators=context.indicators, dataset_fingerprint=session.dataset_fingerprint,
        low_threshold=rsi_low, high_threshold=rsi_high,
    )
    strategy_payloads: list[dict[str, object]] = []
    for strategy in (ema_result, rsi_result):
        payload = asdict(strategy)
        payload["outcome_evaluation"] = asdict(evaluate_strategy_outcomes(
            strategy=strategy,
            bars=context.bars.bars,
            horizon_bars=outcome_horizon,
        ))
        strategy_payloads.append(payload)

    return ReplayStrategyAnalysis(
        session_id=session.session_id,
        symbol=session.symbol,
        timeframe=timeframe,
        parameters={"ema_period": ema_period, "rsi_period": rsi_period,
                    "rsi_low": rsi_low, "rsi_high": rsi_high, "bar_limit": bar_limit,
                    "outcome_horizon": outcome_horizon},
        lineage=context.analysis.lineage,
        strategies=tuple(strategy_payloads),
    )
