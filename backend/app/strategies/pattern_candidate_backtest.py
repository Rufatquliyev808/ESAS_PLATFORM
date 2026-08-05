from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import statistics

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.retest import RetestResult


BACKTEST_VERSION = "1.0.0"
MIN_EFFECTIVE_SAMPLE = 30
Z_95 = 1.96
SUPPORTIVE = "supportive_evidence"
INSUFFICIENT = "insufficient_evidence"
MATURED = "matured"
IMMATURE = "immature"

# v1 only backtests hypotheses whose upstream detector already exposes every
# historical confirmation (bos_choch.observations / retest.observations), not
# just the latest one. market_structure and liquidity_sweep currently only
# expose the latest confirmed state, which is too small a sample to backtest
# honestly; extending them is separate, future work.
SUPPORTED_HYPOTHESES = frozenset({"structure_break_long", "structure_break_short"})

MAX_COST_COMPONENT_BPS = 1_000.0
MAX_COST_MULTIPLIER = 10.0


class PatternCandidateBacktestUnsupportedError(ValueError):
    pass


@dataclass(frozen=True)
class BacktestTrade:
    break_observed_at: str
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


def run_pattern_candidate_backtest(
    *,
    candidate_id: str,
    hypothesis_id: str,
    direction: str,
    bars: tuple[MarketBar, ...],
    retest: RetestResult,
    horizon_bars: int = 3,
    spread_bps: float = 2.0,
    commission_bps: float = 1.0,
    slippage_bps: float = 1.0,
    latency_bps: float = 0.5,
    adverse_multiplier: float = 1.5,
    stress_multiplier: float = 2.5,
) -> PatternCandidateBacktest:
    """Simulate every historical confirmation of a structure-break hypothesis.

    Entry is the confirming bar's own close (the bar on which the retest
    became known), matching the existing forward_closed_bar_outcome
    convention used elsewhere in this codebase, not a separate next-bar
    open -- this is a deliberate v1 simplification, not bid/ask-aware
    execution. Exit is the close horizon_bars later. This does not place
    orders; it only produces a deterministic historical simulation.
    """
    if hypothesis_id not in SUPPORTED_HYPOTHESES:
        raise PatternCandidateBacktestUnsupportedError(
            "backtest v1 only supports structure_break_long and structure_break_short"
        )
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be at least 1")
    normalized_direction = direction.strip().lower()
    if normalized_direction not in {"bullish", "bearish"}:
        raise ValueError("direction must be bullish or bearish")

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
    events = tuple(
        item for item in retest.observations
        if item.direction == normalized_direction and item.state == "confirmed_retest"
    )

    trades: list[BacktestTrade] = []
    for event in events:
        if event.observed_at is None:
            continue
        entry_index = index_by_end.get(event.observed_at)
        if entry_index is None:
            continue
        entry_bar = bars[entry_index]
        if not math.isfinite(entry_bar.close) or entry_bar.close <= 0:
            raise ValueError("entry bar close must be positive and finite")
        exit_index = entry_index + horizon_bars
        if exit_index >= len(bars):
            trades.append(BacktestTrade(
                event.break_observed_at or "", entry_bar.end_at, entry_bar.close,
                None, None, None, IMMATURE,
            ))
            continue
        exit_bar = bars[exit_index]
        raw_change = (exit_bar.close - entry_bar.close) / entry_bar.close * 100.0
        raw_return = raw_change if normalized_direction == "bullish" else -raw_change
        trades.append(BacktestTrade(
            event.break_observed_at or "", entry_bar.end_at, entry_bar.close,
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
        "direction": normalized_direction, "horizon_bars": horizon_bars,
        "retest_fingerprint": retest.fingerprint,
        "trades": [asdict(item) for item in trades],
        "scenarios": [asdict(item) for item in scenarios],
    }
    return PatternCandidateBacktest(
        version=BACKTEST_VERSION, candidate_id=candidate_id, hypothesis_id=hypothesis_id,
        direction=normalized_direction, horizon_bars=horizon_bars, total_events=len(trades),
        matured_events=sum(item.status == MATURED for item in trades),
        immature_events=sum(item.status == IMMATURE for item in trades),
        trades=tuple(trades), scenarios=scenarios, fingerprint=_fingerprint(payload),
    )
