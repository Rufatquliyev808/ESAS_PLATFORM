from dataclasses import replace

from backend.app.strategies.cost_scenario_evaluation import evaluate_cost_scenarios
from backend.app.strategies.statistical_reliability import (
    INSUFFICIENT, SUPPORTIVE, evaluate_statistical_reliability,
)
from tests.backend.test_multi_window_walk_forward import evaluate


def subject(closes: list[float], *, horizon: int = 1):
    _, _, outcome, multi = evaluate(closes, horizon=horizon, windows=3)
    costs = evaluate_cost_scenarios(
        multi_window=multi, spread_bps=0, commission_bps=0,
        slippage_bps=0, latency_bps=0, adverse_multiplier=1.5,
        stress_multiplier=2.5,
    )
    return outcome, multi, costs, evaluate_statistical_reliability(
        outcome=outcome, multi_window=multi, cost_scenarios=costs,
    )


def test_small_sample_is_explicitly_insufficient() -> None:
    _, _, _, result = subject(list(range(100, 120)))
    assert result.overall_status == INSUFFICIENT
    assert all(item.reason == "effective_sample_below_30" for item in result.scenarios)


def test_zero_variance_is_not_presented_as_reliable() -> None:
    _, _, _, result = subject([100.0] * 100)
    assert all(item.status == INSUFFICIENT for item in result.scenarios)
    assert all(item.reason == "zero_sample_variance" for item in result.scenarios)


def test_negative_result_stays_visible_and_insufficient() -> None:
    _, _, _, result = subject([200 - index for index in range(100)])
    assert all(item.observed_mean_percent < 0 for item in result.scenarios)
    assert all(item.status == INSUFFICIENT for item in result.scenarios)


def test_strong_positive_result_can_be_supportive() -> None:
    closes = [100.0]
    for index in range(1, 150):
        closes.append(closes[-1] * (1.01 if index % 5 else 1.002))
    _, _, _, result = subject(closes)
    assert result.overall_status == SUPPORTIVE
    assert all(item.confidence_interval_low_percent > 0 for item in result.scenarios)


def test_horizon_purging_reduces_effective_sample_and_result_is_deterministic() -> None:
    outcome, multi, costs, first = subject([100 + index for index in range(100)], horizon=3)
    second = evaluate_statistical_reliability(
        outcome=outcome, multi_window=multi, cost_scenarios=costs,
    )
    assert first == second
    assert first.scenarios[0].effective_sample_size < multi.summary.matured_validation_observations


def test_mismatched_upstream_is_rejected() -> None:
    outcome, multi, costs, _ = subject([100 + index for index in range(100)])
    try:
        evaluate_statistical_reliability(
            outcome=outcome, multi_window=replace(multi, fingerprint="sha256:changed"),
            cost_scenarios=costs,
        )
    except ValueError as error:
        assert "cost scenarios" in str(error)
    else:
        raise AssertionError("mismatched upstream should fail")
