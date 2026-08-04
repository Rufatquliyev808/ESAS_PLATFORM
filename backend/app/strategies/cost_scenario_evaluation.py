from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math

from backend.app.strategies.multi_window_walk_forward import MultiWindowEvaluation


COST_SCENARIO_VERSION = "1.0.0"
MAX_COMPONENT_BPS = 1_000.0
MAX_MULTIPLIER = 10.0


@dataclass(frozen=True)
class CostScenarioDefinition:
    evaluator_id: str = "historical_cost_stress_adjustment"
    version: str = COST_SCENARIO_VERSION
    lifecycle: str = "experimental"
    interpretation: str = "research_assumption_not_broker_fact_or_trading_signal"


@dataclass(frozen=True)
class CostAssumption:
    scenario: str
    spread_bps: float
    commission_bps: float
    slippage_bps: float
    latency_bps: float
    multiplier: float
    total_cost_bps: float
    total_cost_percent: float
    unit: str = "basis_points_per_matured_observation"
    source: str = "generic_research_assumption_not_broker_fact"


@dataclass(frozen=True)
class CostAdjustedWindow:
    window_number: int
    matured_observations: int
    raw_mean_return_percent: float | None
    net_mean_return_percent: float | None


@dataclass(frozen=True)
class CostScenarioSummary:
    matured_observations: int
    total_validation_observations: int
    coverage_percent: float
    raw_weighted_mean_return_percent: float | None
    net_weighted_mean_return_percent: float | None
    cost_per_observation_percent: float
    aggregate_modeled_cost_percentage_points: float
    positive_net_windows: int
    negative_net_windows: int
    flat_net_windows: int


@dataclass(frozen=True)
class CostScenarioResult:
    assumption: CostAssumption
    summary: CostScenarioSummary
    windows: tuple[CostAdjustedWindow, ...]


@dataclass(frozen=True)
class CostScenarioManifest:
    upstream_multi_window_fingerprint: str
    scenario_policy: str
    source: str
    raw_result_policy: str


@dataclass(frozen=True)
class CostScenarioEvaluation:
    definition: CostScenarioDefinition
    scenarios: tuple[CostScenarioResult, ...]
    manifest: CostScenarioManifest
    fingerprint: str
    interpretation: str = "historical_cost_adjustment_not_trade_pnl_or_trading_signal"


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _validate_component(name: str, value: float | None) -> float:
    if value is None or not isinstance(value, (int, float)):
        raise ValueError(f"{name} cost assumption is required")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{name} cost assumption must be finite and non-negative")
    if numeric > MAX_COMPONENT_BPS:
        raise ValueError(f"{name} cost assumption must not exceed {MAX_COMPONENT_BPS:g} bps")
    return numeric


def _validate_multiplier(name: str, value: float | None) -> float:
    if value is None or not isinstance(value, (int, float)):
        raise ValueError(f"{name} multiplier is required")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 1 or numeric > MAX_MULTIPLIER:
        raise ValueError(f"{name} multiplier must be between 1 and {MAX_MULTIPLIER:g}")
    return numeric


def evaluate_cost_scenarios(
    *, multi_window: MultiWindowEvaluation, spread_bps: float | None,
    commission_bps: float | None, slippage_bps: float | None,
    latency_bps: float | None, adverse_multiplier: float | None,
    stress_multiplier: float | None,
) -> CostScenarioEvaluation:
    """Apply transparent deterministic assumptions without mutating raw results."""
    components = {
        "spread": _validate_component("spread", spread_bps),
        "commission": _validate_component("commission", commission_bps),
        "slippage": _validate_component("slippage", slippage_bps),
        "latency": _validate_component("latency", latency_bps),
    }
    adverse = _validate_multiplier("adverse", adverse_multiplier)
    stress = _validate_multiplier("stress", stress_multiplier)
    if stress < adverse:
        raise ValueError("stress multiplier must be greater than or equal to adverse multiplier")

    base_cost_bps = math.fsum(components.values())
    definitions = (("normal", 1.0), ("adverse", adverse), ("stress", stress))
    scenarios: list[CostScenarioResult] = []
    total_observations = multi_window.summary.total_validation_observations
    matured = multi_window.summary.matured_validation_observations

    for scenario_name, multiplier in definitions:
        total_cost_bps = base_cost_bps * multiplier
        cost_percent = total_cost_bps / 100.0
        adjusted_windows = tuple(
            CostAdjustedWindow(
                window_number=window.window_number,
                matured_observations=window.validation.matured,
                raw_mean_return_percent=window.validation.mean_return_percent,
                net_mean_return_percent=(
                    window.validation.mean_return_percent - cost_percent
                    if window.validation.mean_return_percent is not None else None
                ),
            )
            for window in multi_window.windows
        )
        net_values = [
            item.net_mean_return_percent for item in adjusted_windows
            if item.net_mean_return_percent is not None
        ]
        raw_mean = multi_window.summary.weighted_mean_return_percent
        assumption = CostAssumption(
            scenario=scenario_name,
            spread_bps=components["spread"] * multiplier,
            commission_bps=components["commission"] * multiplier,
            slippage_bps=components["slippage"] * multiplier,
            latency_bps=components["latency"] * multiplier,
            multiplier=multiplier,
            total_cost_bps=total_cost_bps,
            total_cost_percent=cost_percent,
        )
        scenarios.append(CostScenarioResult(
            assumption=assumption,
            summary=CostScenarioSummary(
                matured_observations=matured,
                total_validation_observations=total_observations,
                coverage_percent=(matured / total_observations * 100.0 if total_observations else 0.0),
                raw_weighted_mean_return_percent=raw_mean,
                net_weighted_mean_return_percent=(raw_mean - cost_percent if raw_mean is not None else None),
                cost_per_observation_percent=cost_percent,
                aggregate_modeled_cost_percentage_points=cost_percent * matured,
                positive_net_windows=sum(value > 0 for value in net_values),
                negative_net_windows=sum(value < 0 for value in net_values),
                flat_net_windows=sum(value == 0 for value in net_values),
            ),
            windows=adjusted_windows,
        ))

    definition = CostScenarioDefinition()
    manifest = CostScenarioManifest(
        upstream_multi_window_fingerprint=multi_window.fingerprint,
        scenario_policy="same_component_assumptions_scaled_deterministically_across_all_validation_windows",
        source="generic_research_assumption_not_broker_fact",
        raw_result_policy="upstream_cost_free_results_preserved_unchanged",
    )
    payload = {
        "definition": asdict(definition),
        "scenarios": [asdict(item) for item in scenarios],
        "manifest": asdict(manifest),
    }
    return CostScenarioEvaluation(
        definition=definition,
        scenarios=tuple(scenarios),
        manifest=manifest,
        fingerprint=_fingerprint(payload),
    )
