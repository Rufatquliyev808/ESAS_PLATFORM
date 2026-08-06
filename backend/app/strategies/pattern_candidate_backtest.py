from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import random
import statistics

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.indicators import IndicatorSeries
from backend.app.analysis.liquidity_sweep import LiquiditySweepResult
from backend.app.analysis.market_structure import MarketStructureResult
from backend.app.analysis.retest import RetestResult


BACKTEST_VERSION = "1.4.0"
MIN_EFFECTIVE_SAMPLE = 30
Z_95 = 1.96
SUPPORTIVE = "supportive_evidence"
INSUFFICIENT = "insufficient_evidence"
MATURED = "matured"
IMMATURE = "immature"
RANDOM_TIMING_BASELINE_SAMPLE_SIZE = 500
# Fixed, non-tunable: a configurable baseline would itself become a
# multiple-testing parameter-shopping surface, defeating the point of
# comparing against "the simplest possible rule."
SINGLE_FEATURE_RSI_LOW_THRESHOLD = 30.0
SINGLE_FEATURE_RSI_HIGH_THRESHOLD = 70.0

# v1 only backtests hypotheses whose upstream detector already exposes every
# historical confirmation, not just the latest one: bos_choch/retest,
# liquidity_sweep, and market_structure all keep a full observations
# history now (market_structure fires one event per transition *into* a
# confirmed HH/HL or LH/LL regime, not on every pivot that keeps an
# already-confirmed regime going).
HYPOTHESIS_EVENT_DIRECTION = {
    "structure_break_long": "bullish",
    "structure_break_short": "bearish",
    "liquidity_sweep_reclaim_long": "bullish",
    "liquidity_sweep_reclaim_short": "bearish",
    "market_structure_long": "bullish",
    "market_structure_short": "bearish",
}
SUPPORTED_HYPOTHESES = frozenset(HYPOTHESIS_EVENT_DIRECTION)
STRUCTURE_BREAK_HYPOTHESES = frozenset({"structure_break_long", "structure_break_short"})
LIQUIDITY_SWEEP_HYPOTHESES = frozenset({"liquidity_sweep_reclaim_long", "liquidity_sweep_reclaim_short"})

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
    random_timing_baseline_sample_size: int
    random_timing_baseline_mean_return_percent: float | None
    beats_random_timing_baseline: bool | None
    single_feature_baseline_sample_size: int
    single_feature_baseline_mean_return_percent: float | None
    beats_single_feature_baseline: bool | None


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


def _random_timing_baseline_raw_returns(
    *, bars: tuple[MarketBar, ...], event_direction: str, horizon_bars: int, seed: int,
) -> tuple[float, ...]:
    """Deterministic (seeded), hypothesis-blind sample of raw returns from
    randomly chosen entry points in the same bar series, using the same
    direction convention and horizon as the real backtest.

    This estimates what a randomly-timed entry would have captured over the
    same period: if the candidate's own mean does not clear this baseline,
    its apparent edge is indistinguishable from generic market drift or
    volatility over the interval, not a real causal effect of the pattern.
    Same seed + same bars always produces the same sample (reproducibility).
    """
    eligible_count = len(bars) - horizon_bars
    if eligible_count <= 0:
        return ()
    rng = random.Random(seed)
    sample_size = min(RANDOM_TIMING_BASELINE_SAMPLE_SIZE, eligible_count)
    indices = rng.sample(range(eligible_count), sample_size)
    values: list[float] = []
    for entry_index in indices:
        entry_bar = bars[entry_index]
        if not math.isfinite(entry_bar.close) or entry_bar.close <= 0:
            continue
        exit_bar = bars[entry_index + horizon_bars]
        raw_change = (exit_bar.close - entry_bar.close) / entry_bar.close * 100.0
        values.append(raw_change if event_direction == "bullish" else -raw_change)
    return tuple(values)


def _single_feature_rsi_reversal_raw_returns(
    *, bars: tuple[MarketBar, ...], rsi: IndicatorSeries | None, event_direction: str, horizon_bars: int,
) -> tuple[float, ...]:
    """Raw returns from a classic, fixed (non-tunable) single-indicator rule:
    enter on an RSI reversal out of its own oversold/overbought extreme, in
    the same direction as the candidate. A candidate that cannot beat this
    trivial, well-known rule offers nothing a much simpler rule would not
    already capture on its own.

    Returns an empty tuple (baseline skipped, not blocking) when no RSI
    series is available or it does not align with bars -- this baseline is
    an additional check, not a hard dependency of the backtest itself.
    """
    if rsi is None or len(rsi.points) != len(bars):
        return ()
    values: list[float] = []
    previous_value: float | None = None
    for index, (bar, point) in enumerate(zip(bars, rsi.points)):
        current_value = point.value
        if previous_value is not None and current_value is not None:
            crossed_up_from_oversold = previous_value <= SINGLE_FEATURE_RSI_LOW_THRESHOLD < current_value
            crossed_down_from_overbought = previous_value >= SINGLE_FEATURE_RSI_HIGH_THRESHOLD > current_value
            triggers = crossed_up_from_oversold if event_direction == "bullish" else crossed_down_from_overbought
            exit_index = index + horizon_bars
            if triggers and exit_index < len(bars) and math.isfinite(bar.close) and bar.close > 0:
                exit_bar = bars[exit_index]
                raw_change = (exit_bar.close - bar.close) / bar.close * 100.0
                values.append(raw_change if event_direction == "bullish" else -raw_change)
        previous_value = current_value
    return tuple(values)


def _scenario_result(
    name: str, total_cost_bps: float, matured_raw: tuple[float, ...],
    baseline_raw: tuple[float, ...], single_feature_raw: tuple[float, ...],
) -> BacktestCostScenario:
    cost_percent = total_cost_bps / 100.0
    baseline_net = tuple(value - cost_percent for value in baseline_raw)
    baseline_size = len(baseline_net)
    baseline_mean = math.fsum(baseline_net) / baseline_size if baseline_size else None

    single_feature_net = tuple(value - cost_percent for value in single_feature_raw)
    single_feature_size = len(single_feature_net)
    single_feature_mean = math.fsum(single_feature_net) / single_feature_size if single_feature_size else None

    net = tuple(value - cost_percent for value in matured_raw)
    count = len(net)
    if not count:
        return BacktestCostScenario(
            name, total_cost_bps, 0, None, None, None, None, None, None, INSUFFICIENT, "no_matured_trades",
            baseline_size, baseline_mean, None, single_feature_size, single_feature_mean, None,
        )
    mean = math.fsum(net) / count
    hit_rate = sum(value > 0 for value in net) / count * 100.0
    if count < MIN_EFFECTIVE_SAMPLE:
        return BacktestCostScenario(
            name, total_cost_bps, count, mean, hit_rate, None, None, None, None, INSUFFICIENT, "effective_sample_below_30",
            baseline_size, baseline_mean, None, single_feature_size, single_feature_mean, None,
        )
    deviation = statistics.stdev(net)
    if deviation == 0:
        return BacktestCostScenario(
            name, total_cost_bps, count, mean, hit_rate, 0.0, 0.0, mean, mean, INSUFFICIENT, "zero_sample_variance",
            baseline_size, baseline_mean, None, single_feature_size, single_feature_mean, None,
        )
    margin = Z_95 * deviation / math.sqrt(count)
    low, high = mean - margin, mean + margin
    clears_zero = low > 0
    beats_random = low > baseline_mean if baseline_mean is not None else None
    beats_single_feature = low > single_feature_mean if single_feature_mean is not None else None
    status = (
        SUPPORTIVE if clears_zero and beats_random in (True, None) and beats_single_feature in (True, None)
        else INSUFFICIENT
    )
    if not clears_zero:
        reason = "ci_crosses_or_is_below_zero_baseline"
    elif beats_random is False:
        reason = "ci_does_not_exceed_random_timing_baseline"
    elif beats_single_feature is False:
        reason = "ci_does_not_exceed_single_feature_baseline"
    else:
        reason = "ci_entirely_above_zero_baseline"
    return BacktestCostScenario(
        name, total_cost_bps, count, mean, hit_rate, mean / deviation, deviation, low, high, status, reason,
        baseline_size, baseline_mean, beats_random, single_feature_size, single_feature_mean, beats_single_feature,
    )


def _historical_events(
    hypothesis_id: str, event_direction: str, retest: RetestResult,
    liquidity_sweep: LiquiditySweepResult, market_structure: MarketStructureResult,
) -> tuple[tuple[str, str], ...]:
    """Return (trigger_observed_at, entry_reference_at) pairs for every historical confirmation."""
    if hypothesis_id in STRUCTURE_BREAK_HYPOTHESES:
        return tuple(
            (item.break_observed_at or item.observed_at, item.observed_at)
            for item in retest.observations
            if item.direction == event_direction and item.state == "confirmed_retest" and item.observed_at is not None
        )
    if hypothesis_id in LIQUIDITY_SWEEP_HYPOTHESES:
        return tuple(
            (item.observed_at, item.observed_at)
            for item in liquidity_sweep.observations
            if item.direction == event_direction and item.state == "confirmed_sweep" and item.observed_at is not None
        )
    return tuple(
        (item.observed_at, item.observed_at)
        for item in market_structure.observations
        if item.direction == event_direction and item.state == "confirmed_structure"
    )


ACCEPTED_FOR_SHADOW = "accepted_for_shadow"
REJECTED = "rejected"

def classify_backtest_verdict(*, status: str, reason: str) -> str:
    """Map the "normal" cost scenario's verdict to a candidate lifecycle outcome.

    supportive_evidence -> accepted_for_shadow (not a live-trading decision;
    Phase 9 SHADOW does not exist yet, this only records that the historical
    evidence met the predeclared bar -- the zero baseline, the random-timing
    baseline, and the single-feature RSI-reversal baseline, all at once).
    insufficient_evidence is split by reason: too few samples to conclude
    anything ("effective_sample_below_30") stays insufficient_evidence (may
    simply need a longer replay interval), while a large-enough sample whose
    CI does not clear zero, or clears zero but does not exceed one of the
    other baselines, is rejected -- all of these are refuting evidence (no
    edge, or an edge indistinguishable from generic drift or a trivial
    known rule), not missing data.
    """
    if status == SUPPORTIVE:
        return ACCEPTED_FOR_SHADOW
    if reason == "effective_sample_below_30":
        return INSUFFICIENT
    return REJECTED


def bonferroni_corrected_scenario(
    scenario: dict[str, object], *, family_trial_count: int, family_wise_alpha: float = 0.05,
) -> dict[str, object]:
    """Recompute a cost scenario's verdict under a Bonferroni family-wise error
    correction, without touching the original (uncorrected) stored backtest
    artifact -- multiple-testing correction is a downstream classification
    concern (Phase 3/4 contract: "multiple-testing qeydiyyatı olmadan namizəd
    qəbul edilmir"), not something that silently rewrites a stored result.

    Only a SUPPORTIVE scenario is recomputed: correction only ever narrows the
    confidence interval, so a scenario that was already insufficient at the
    flat 95% bar stays insufficient at the stricter corrected bar too.
    """
    if family_trial_count < 1:
        raise ValueError("family_trial_count must be at least 1")
    if not 0 < family_wise_alpha < 1:
        raise ValueError("family_wise_alpha must be between 0 and 1")
    if scenario["status"] != SUPPORTIVE:
        return dict(scenario)
    alpha_corrected = family_wise_alpha / family_trial_count
    z_corrected = statistics.NormalDist().inv_cdf(1 - alpha_corrected / 2)
    mean = scenario["net_mean_return_percent"]
    deviation = scenario["sample_standard_deviation"]
    count = scenario["effective_sample_size"]
    margin = z_corrected * deviation / math.sqrt(count)
    low, high = mean - margin, mean + margin
    clears_zero = low > 0
    baseline_mean = scenario.get("random_timing_baseline_mean_return_percent")
    beats_random = low > baseline_mean if baseline_mean is not None else None
    single_feature_mean = scenario.get("single_feature_baseline_mean_return_percent")
    beats_single_feature = low > single_feature_mean if single_feature_mean is not None else None
    status = (
        SUPPORTIVE if clears_zero and beats_random in (True, None) and beats_single_feature in (True, None)
        else INSUFFICIENT
    )
    if not clears_zero:
        reason = "multiple_testing_correction_ci_crosses_or_is_below_zero_baseline"
    elif beats_random is False:
        reason = "multiple_testing_correction_ci_does_not_exceed_random_timing_baseline"
    elif beats_single_feature is False:
        reason = "multiple_testing_correction_ci_does_not_exceed_single_feature_baseline"
    else:
        reason = "multiple_testing_correction_ci_still_above_zero_baseline"
    corrected = dict(scenario)
    corrected.update({
        "status": status, "reason": reason,
        "confidence_interval_low_percent": low, "confidence_interval_high_percent": high,
        "beats_random_timing_baseline": beats_random,
        "beats_single_feature_baseline": beats_single_feature,
        "family_trial_count": family_trial_count, "family_wise_alpha": family_wise_alpha,
        "alpha_corrected": alpha_corrected, "z_critical": z_corrected,
    })
    return corrected


def run_pattern_candidate_backtest(
    *,
    candidate_id: str,
    hypothesis_id: str,
    bars: tuple[MarketBar, ...],
    retest: RetestResult,
    liquidity_sweep: LiquiditySweepResult,
    market_structure: MarketStructureResult,
    rsi: IndicatorSeries | None = None,
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
            "backtest v1 only supports structure_break_long/short, "
            "liquidity_sweep_reclaim_long/short and market_structure_long/short"
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
    events = _historical_events(hypothesis_id, event_direction, retest, liquidity_sweep, market_structure)

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

    # Deterministic seed derived only from already-fixed inputs, so the same
    # candidate/hypothesis/horizon/dataset always draws the same "random"
    # baseline sample (reproducibility), without needing to persist the
    # sampled indices themselves.
    seed_source = json.dumps(
        [candidate_id, hypothesis_id, horizon_bars, len(bars),
         bars[0].start_at if bars else None, bars[-1].end_at if bars else None],
        ensure_ascii=True, separators=(",", ":"),
    ).encode("utf-8")
    seed = int.from_bytes(sha256(seed_source).digest()[:8], "big")
    baseline_raw = _random_timing_baseline_raw_returns(
        bars=bars, event_direction=event_direction, horizon_bars=horizon_bars, seed=seed,
    )
    single_feature_raw = _single_feature_rsi_reversal_raw_returns(
        bars=bars, rsi=rsi, event_direction=event_direction, horizon_bars=horizon_bars,
    )

    scenario_definitions = (("normal", 1.0), ("adverse", adverse), ("stress", stress))
    scenarios = tuple(
        _scenario_result(name, base_cost_bps * multiplier, matured_raw, baseline_raw, single_feature_raw)
        for name, multiplier in scenario_definitions
    )

    payload = {
        "version": BACKTEST_VERSION, "candidate_id": candidate_id, "hypothesis_id": hypothesis_id,
        "direction": event_direction, "horizon_bars": horizon_bars,
        "retest_fingerprint": retest.fingerprint, "liquidity_sweep_fingerprint": liquidity_sweep.fingerprint,
        "market_structure_fingerprint": market_structure.fingerprint,
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
