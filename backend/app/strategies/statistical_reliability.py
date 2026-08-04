from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import statistics

from backend.app.strategies.cost_scenario_evaluation import CostScenarioEvaluation
from backend.app.strategies.multi_window_walk_forward import MultiWindowEvaluation
from backend.app.strategies.outcome_evaluation import MATURED, StrategyOutcomeEvaluation


STATISTICAL_RELIABILITY_VERSION = "1.0.0"
SUPPORTIVE = "supportive_evidence"
INSUFFICIENT = "insufficient_evidence"
MIN_EFFECTIVE_SAMPLE = 30
Z_95 = 1.96


@dataclass(frozen=True)
class ReliabilityDefinition:
    evaluator_id: str = "purged_validation_mean_vs_zero_baseline"
    version: str = STATISTICAL_RELIABILITY_VERSION
    lifecycle: str = "experimental"
    interpretation: str = "historical_uncertainty_evidence_not_trading_signal"


@dataclass(frozen=True)
class ScenarioReliability:
    scenario: str
    status: str
    effective_sample_size: int
    observed_mean_percent: float | None
    baseline_mean_percent: float
    raw_effect_percentage_points: float | None
    standardized_effect_size: float | None
    sample_standard_deviation: float | None
    confidence_level_percent: float
    confidence_interval_low_percent: float | None
    confidence_interval_high_percent: float | None
    reason: str


@dataclass(frozen=True)
class ReliabilityManifest:
    primary_metric: str
    baseline: str
    acceptance_rule: str
    sampling_policy: str
    minimum_effective_sample_size: int
    upstream_outcome_fingerprint: str
    upstream_multi_window_fingerprint: str
    upstream_cost_scenario_fingerprint: str


@dataclass(frozen=True)
class StatisticalReliabilityEvaluation:
    definition: ReliabilityDefinition
    overall_status: str
    scenarios: tuple[ScenarioReliability, ...]
    manifest: ReliabilityManifest
    fingerprint: str
    interpretation: str = "historical_uncertainty_evidence_not_trading_signal"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _purged_validation_returns(
    outcome: StrategyOutcomeEvaluation, multi_window: MultiWindowEvaluation,
) -> tuple[float, ...]:
    values: list[float] = []
    step = outcome.horizon_bars
    for window in multi_window.windows:
        start = window.manifest.validation_start_index
        end = window.manifest.validation_end_index_exclusive
        for index in range(start, end, step):
            observation = outcome.observations[index]
            if observation.status == MATURED and observation.return_percent is not None:
                values.append(observation.return_percent)
    return tuple(values)


def _scenario_result(name: str, values: tuple[float, ...], cost_percent: float) -> ScenarioReliability:
    adjusted = tuple(value - cost_percent for value in values)
    count = len(adjusted)
    if not count:
        return ScenarioReliability(name, INSUFFICIENT, 0, None, 0.0, None, None,
                                   None, 95.0, None, None, "no_matured_validation_observations")
    mean = math.fsum(adjusted) / count
    if count < MIN_EFFECTIVE_SAMPLE:
        return ScenarioReliability(name, INSUFFICIENT, count, mean, 0.0, mean, None,
                                   None, 95.0, None, None, "effective_sample_below_30")
    deviation = statistics.stdev(adjusted)
    if deviation == 0:
        return ScenarioReliability(name, INSUFFICIENT, count, mean, 0.0, mean, None,
                                   0.0, 95.0, mean, mean, "zero_sample_variance")
    margin = Z_95 * deviation / math.sqrt(count)
    low, high = mean - margin, mean + margin
    status = SUPPORTIVE if low > 0 else INSUFFICIENT
    reason = "ci_entirely_above_zero_baseline" if status == SUPPORTIVE else "ci_crosses_or_is_below_zero_baseline"
    return ScenarioReliability(name, status, count, mean, 0.0, mean,
                               mean / deviation, deviation, 95.0, low, high, reason)


def evaluate_statistical_reliability(
    *, outcome: StrategyOutcomeEvaluation, multi_window: MultiWindowEvaluation,
    cost_scenarios: CostScenarioEvaluation,
) -> StatisticalReliabilityEvaluation:
    """Add a conservative, predeclared uncertainty layer to validation results."""
    if multi_window.manifest.outcome_fingerprint != outcome.fingerprint:
        raise ValueError("multi-window evaluation belongs to another outcome result")
    if cost_scenarios.manifest.upstream_multi_window_fingerprint != multi_window.fingerprint:
        raise ValueError("cost scenarios belong to another multi-window result")
    values = _purged_validation_returns(outcome, multi_window)
    scenarios = tuple(
        _scenario_result(item.assumption.scenario, values, item.assumption.total_cost_percent)
        for item in cost_scenarios.scenarios
    )
    overall = SUPPORTIVE if scenarios and all(item.status == SUPPORTIVE for item in scenarios) else INSUFFICIENT
    definition = ReliabilityDefinition()
    manifest = ReliabilityManifest(
        primary_metric="mean_cost_adjusted_forward_close_return_percent",
        baseline="zero_percent_change",
        acceptance_rule="n_at_least_30_non_overlapping_horizons_and_95pct_ci_low_above_zero",
        sampling_policy="chronological_validation_only_one_observation_per_outcome_horizon",
        minimum_effective_sample_size=MIN_EFFECTIVE_SAMPLE,
        upstream_outcome_fingerprint=outcome.fingerprint,
        upstream_multi_window_fingerprint=multi_window.fingerprint,
        upstream_cost_scenario_fingerprint=cost_scenarios.fingerprint,
    )
    payload = {"definition": asdict(definition), "overall_status": overall,
               "scenarios": [asdict(item) for item in scenarios], "manifest": asdict(manifest)}
    return StatisticalReliabilityEvaluation(definition, overall, scenarios, manifest,
                                            _fingerprint(payload))
