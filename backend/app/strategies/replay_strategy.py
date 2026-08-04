from dataclasses import asdict, dataclass

from backend.app.analysis.replay_analysis import create_replay_analysis_context
from backend.app.database.replay_session_repository import ReplaySession
from backend.app.strategies.ema_close_relation import evaluate_ema_close_relation
from backend.app.strategies.rsi_regime_observation import evaluate_rsi_regime_observation
from backend.app.strategies.outcome_evaluation import evaluate_strategy_outcomes
from backend.app.strategies.walk_forward_evaluation import evaluate_walk_forward
from backend.app.strategies.multi_window_walk_forward import (
    evaluate_multi_window_walk_forward,
)
from backend.app.strategies.cost_scenario_evaluation import evaluate_cost_scenarios
from backend.app.strategies.statistical_reliability import evaluate_statistical_reliability


STRATEGY_ANALYSIS_API_VERSION = "1.2.0"


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
    rsi_low: float, rsi_high: float, bar_limit: int, outcome_horizon: int,
    development_ratio: float, walk_forward_windows: int,
    cost_spread_bps: float = 2.0, cost_commission_bps: float = 1.0,
    cost_slippage_bps: float = 1.0, cost_latency_bps: float = 0.5,
    adverse_cost_multiplier: float = 1.5, stress_cost_multiplier: float = 2.5,
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
        outcome = evaluate_strategy_outcomes(
            strategy=strategy,
            bars=context.bars.bars,
            horizon_bars=outcome_horizon,
        )
        payload["outcome_evaluation"] = asdict(outcome)
        payload["walk_forward_evaluation"] = asdict(evaluate_walk_forward(
            strategy=strategy, outcome=outcome, bars=context.bars.bars,
            development_ratio=development_ratio,
        ))
        multi_window = evaluate_multi_window_walk_forward(
            strategy=strategy, outcome=outcome, bars=context.bars.bars,
            development_ratio=development_ratio,
            window_count=walk_forward_windows,
        )
        payload["multi_window_evaluation"] = asdict(multi_window)
        cost_scenarios = evaluate_cost_scenarios(
            multi_window=multi_window, spread_bps=cost_spread_bps,
            commission_bps=cost_commission_bps, slippage_bps=cost_slippage_bps,
            latency_bps=cost_latency_bps,
            adverse_multiplier=adverse_cost_multiplier,
            stress_multiplier=stress_cost_multiplier,
        )
        payload["cost_scenario_evaluation"] = asdict(cost_scenarios)
        payload["statistical_reliability_evaluation"] = asdict(
            evaluate_statistical_reliability(
                outcome=outcome, multi_window=multi_window,
                cost_scenarios=cost_scenarios,
            )
        )
        strategy_payloads.append(payload)

    return ReplayStrategyAnalysis(
        session_id=session.session_id,
        symbol=session.symbol,
        timeframe=timeframe,
        parameters={"ema_period": ema_period, "rsi_period": rsi_period,
                    "rsi_low": rsi_low, "rsi_high": rsi_high, "bar_limit": bar_limit,
                    "outcome_horizon": outcome_horizon,
                    "development_ratio": development_ratio,
                    "walk_forward_windows": walk_forward_windows,
                    "cost_spread_bps": cost_spread_bps,
                    "cost_commission_bps": cost_commission_bps,
                    "cost_slippage_bps": cost_slippage_bps,
                    "cost_latency_bps": cost_latency_bps,
                    "adverse_cost_multiplier": adverse_cost_multiplier,
                    "stress_cost_multiplier": stress_cost_multiplier},
        lineage=context.analysis.lineage,
        strategies=tuple(strategy_payloads),
    )
