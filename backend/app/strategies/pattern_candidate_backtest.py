from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import statistics

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.liquidity_sweep import LiquiditySweepResult
from backend.app.analysis.retest import RetestResult


BACKTEST_VERSION = "1.1.0"
MIN_EFFECTIVE_SAMPLE = 30
Z_95 = 1.96
SUPPORTIVE = "supportive_evidence"
INSUFFICIENT = "insufficient_evidence"
MATURED = "matured"
IMMATURE = "immature"

# v1 only backtests hypotheses whose upstream detector already exposes every
# historical confirmation, not just the latest one: bos_choch/retest and
# liquidity_sweep now both keep a full observations history. market_structure
# still only exposes the latest confirmed regime state (a continuous-regime
# concept, not a discrete event), so it stays out of scope until that has its
# own well-defined historical-event semantics.
HYPOTHESIS_EVENT_DIRECTION = {
    "structure_break_long": "bullish",
    "structure_break_short": "bearish",
    "liquidity_sweep_reclaim_long": "bullish",
    "liquidity_sweep_reclaim_short": "bearish",
}
SUPPORTED_HYPOTHESES = frozenset(HYPOTHESIS_EVENT_DIRECTION)
STRUCTURE_BREAK_HYPOTHESES = frozenset({"structure_break_long", "structure_break_short"})

MAX_COST_COMPONENT_BPS = 1_000.0
MAX_COST_MULTIPLIER = 10.0


class PatternCandidateBacktestUnsupportedError(ValueError):
    pass


@dataclass(frozen=True)
class BacktestTrade:
    trigger_observed_at: str
    entry_bar_end_at: str
    entry_price: float
    exit_bar_end_at: str | None
    exit_price: float | None
    raw_return_percent: float | None
    status: str


@dataclass(frozen=True)
class BacktestCostScenario:
    scenario: str
    total_cost_bps: float
    effective_sample_size: int
    net_mean_return_percent: float | None
    hit_rate_percent: float | None
    standardized_effect_size: float | None
    sample_standard_deviation: float | None
    confidence_interval_low_percent: float | None
    confidence_interval_high_percent: float | None
    status: str
    reason: str


@dataclass(frozen=True)
class PatternCandidateBacktest:
    version: str
    candidate_id: str
    hypothesis_id: str
    direction: str
    horizon_bars: int
    total_events: int
    matured_events: int
    immature_events: int
    trades: tuple[BacktestTrade, ...]
    scenarios: tuple[BacktestCostScenario, ...]
    fingerprint: str
    interpretation: str = "historical_simulation_not_trading_signal_not_order"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _cost_component(name: str, value: float) -> float:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} cost assumption must be finite and non-negative")
    if value > MAX_COST_COMPONENT_BPS:
        raise ValueError(f"{name} cost assumption must not exceed {MAX_COST_COMPONENT_BPS:g} bps")
    return value


def _cost_multiplier(name: str, value: float) -> float:
    if not math.isfinite(value) or value < 1 or value > MAX_COST_MULTIPLIER:
        raise ValueError(f"{name} multiplier must be between 1 and {MAX_COST_MULTIPLIER:g}")
    return value


def _scenario_result(name: str, total_cost_bps: float, matured_raw: tuple[float, ...]) -> BacktestCostScenario:
    cost_percent = total_cost_bps / 100.0
    net = tuple(value - cost_percent for value in matured_raw)
    count = len(net)
    if not count:
        return BacktestCostScenario(name, total_cost_bps, 0, None, None, None, None, None, None, INSUFFICIENT, "no_matured_trades")
    mean = math.fsum(net) / count
    hit_rate = sum(value > 0 for value in net) / count * 100.0
    if count < MIN_EFFECTIVE_SAMPLE:
        return BacktestCostScenario(name, total_cost_bps, count, mean, hit_rate, None, None, None, None, INSUFFICIENT, "effective_sample_below_30")
    deviation = statistics.stdev(net)
    if deviation == 0:
        return BacktestCostScenario(name, total_cost_bps, count, mean, hit_rate, 0.0, 0.0, mean, mean, INSUFFICIENT, "zero_sample_variance")
    margin = Z_95 * deviation / math.sqrt(count)
    low, high = mean - margin, mean + margin
    status = SUPPORTIVE if low > 0 else INSUFFICIENT
    reason = "ci_entirely_above_zero_baseline" if status == SUPPORTIVE else "ci_crosses_or_is_below_zero_baseline"
    return BacktestCostScenario(name, total_cost_bps, count, mean, hit_rate, mean / deviation, deviation, low, high, status, reason)


def _historical_events(
    hypothesis_id: str, event_direction: str, retest: RetestResult, liquidity_sweep: LiquiditySweepResult,
) -> tuple[tuple[str, str], ...]:
    """Return (trigger_observed_at, entry_reference_at) pairs for every historical confirmation."""
    if hypothesis_id in STRUCTURE_BREAK_HYPOTHESES:
        return tuple(
            (item.break_observed_at or item.observed_at, item.observed_at)
            for item in retest.observations
            if item.direction == event_direction and item.state == "confirmed_retest" and item.observed_at is not None
        )
    return tuple(
        (item.observed_at, item.observed_at)
        for item in liquidity_sweep.observations
        if item.direction == event_direction and item.state == "confirmed_sweep" and item.observed_at is not None
    )


def run_pattern_candidate_backtest(
    *,
    candidate_id: str,
    hypothesis_id: str,
    bars: tuple[MarketBar, ...],
    retest: RetestResult,
    liquidity_sweep: LiquiditySweepResult,
    horizon_bars: int = 3,
    spread_bps: float = 2.0,
    commission_bps: float = 1.0,
    slippage_bps: float = 1.0,
    latency_bps: float = 0.5,
    adverse_multiplier: float = 1.5,
    stress_multiplier: float = 2.5,
) -> PatternCandidateBacktest:
    """Simulate every historical confirmation of a supported hypothesis.

    Entry is the confirming bar's own close (matching the existing
    forward_closed_bar_outcome convention used elsewhere in this codebase),
    not a separate next-bar open -- this is a deliberate v1 simplification,
    not bid/ask-aware execution. Exit is the close horizon_bars later. This
    does not place orders; it only produces a deterministic simulation.

    hypothesis_id fully determines the causal (bullish/bearish) direction --
    the hypothesis registry's own "long"/"short" vocabulary is never used to
    filter upstream detector observations, which use "bullish"/"bearish".
    """
    if hypothesis_id not in SUPPORTED_HYPOTHESES:
        raise PatternCandidateBacktestUnsupportedError(
            "backtest v1 only supports structure_break_long/short and "
            "liquidity_sweep_reclaim_long/short"
        )
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be at least 1")
    event_direction = HYPOTHESIS_EVENT_DIRECTION[hypothesis_id]

    spread = _cost_component("spread", spread_bps)
    commission = _cost_component("commission", commission_bps)
    slippage = _cost_component("slippage", slippage_bps)
    latency = _cost_component("latency", latency_bps)
    adverse = _cost_multiplier("adverse", adverse_multiplier)
    stress = _cost_multiplier("stress", stress_multiplier)
    if stress < adverse:
        raise ValueError("stress multiplier must be greater than or equal to adverse multiplier")
    base_cost_bps = math.fsum((spread, commission, slippage, latency))

    index_by_end = {bar.end_at: index for index, bar in enumerate(bars)}
    events = _historical_events(hypothesis_id, event_direction, retest, liquidity_sweep)

    trades: list[BacktestTrade] = []
    for trigger_observed_at, entry_reference_at in events:
        entry_index = index_by_end.get(entry_reference_at)
        if entry_index is None:
            continue
        entry_bar = bars[entry_index]
        if not math.isfinite(entry_bar.close) or entry_bar.close <= 0:
            raise ValueError("entry bar close must be positive and finite")
        exit_index = entry_index + horizon_bars
        if exit_index >= len(bars):
            trades.append(BacktestTrade(
                trigger_observed_at, entry_bar.end_at, entry_bar.close,
                None, None, None, IMMATURE,
            ))
            continue
        exit_bar = bars[exit_index]
        raw_change = (exit_bar.close - entry_bar.close) / entry_bar.close * 100.0
        raw_return = raw_change if event_direction == "bullish" else -raw_change
        trades.append(BacktestTrade(
            trigger_observed_at, entry_bar.end_at, entry_bar.close,
            exit_bar.end_at, exit_bar.close, raw_return, MATURED,
        ))

    matured_raw = tuple(item.raw_return_percent for item in trades if item.status == MATURED and item.raw_return_percent is not None)
    scenario_definitions = (("normal", 1.0), ("adverse", adverse), ("stress", stress))
    scenarios = tuple(
        _scenario_result(name, base_cost_bps * multiplier, matured_raw)
        for name, multiplier in scenario_definitions
    )

    payload = {
        "version": BACKTEST_VERSION, "candidate_id": candidate_id, "hypothesis_id": hypothesis_id,
        "direction": event_direction, "horizon_bars": horizon_bars,
        "retest_fingerprint": retest.fingerprint, "liquidity_sweep_fingerprint": liquidity_sweep.fingerprint,
        "trades": [asdict(item) for item in trades],
        "scenarios": [asdict(item) for item in scenarios],
    }
    return PatternCandidateBacktest(
        version=BACKTEST_VERSION, candidate_id=candidate_id, hypothesis_id=hypothesis_id,
        direction=event_direction, horizon_bars=horizon_bars, total_events=len(trades),
        matured_events=sum(item.status == MATURED for item in trades),
        immature_events=sum(item.status == IMMATURE for item in trades),
        trades=tuple(trades), scenarios=scenarios, fingerprint=_fingerprint(payload),
    )
