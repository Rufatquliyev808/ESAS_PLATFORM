from dataclasses import replace

import pytest

from backend.app.strategies.cost_scenario_evaluation import evaluate_cost_scenarios
from tests.backend.test_multi_window_walk_forward import evaluate


def subject(**overrides):
    _, _, _, multi_window = evaluate(
        [100, 101, 102, 103, 104, 105, 106, 107], windows=2,
    )
    arguments = {
        "multi_window": multi_window,
        "spread_bps": 2.0,
        "commission_bps": 1.0,
        "slippage_bps": 1.0,
        "latency_bps": 0.5,
        "adverse_multiplier": 1.5,
        "stress_multiplier": 2.5,
    }
    arguments.update(overrides)
    return multi_window, evaluate_cost_scenarios(**arguments)


def test_raw_result_is_preserved_and_scenarios_are_deterministic() -> None:
    multi_window, first = subject()
    _, second = subject()
    assert first == second
    assert first.manifest.upstream_multi_window_fingerprint == multi_window.fingerprint
    assert first.manifest.raw_result_policy == "upstream_cost_free_results_preserved_unchanged"
    assert [item.assumption.scenario for item in first.scenarios] == ["normal", "adverse", "stress"]
    for scenario in first.scenarios:
        assert [item.window_number for item in scenario.windows] == [1, 2]
        for adjusted, raw in zip(scenario.windows, multi_window.windows, strict=True):
            assert adjusted.raw_mean_return_percent == raw.validation.mean_return_percent


def test_same_cost_rule_is_applied_to_every_window() -> None:
    _, result = subject()
    for scenario in result.scenarios:
        for window in scenario.windows:
            if window.raw_mean_return_percent is not None:
                assert window.net_mean_return_percent == pytest.approx(
                    window.raw_mean_return_percent - scenario.assumption.total_cost_percent
                )


def test_zero_cost_keeps_raw_and_net_equal() -> None:
    _, result = subject(
        spread_bps=0, commission_bps=0, slippage_bps=0, latency_bps=0,
    )
    for scenario in result.scenarios:
        assert scenario.assumption.total_cost_bps == 0
        assert scenario.summary.net_weighted_mean_return_percent == pytest.approx(
            scenario.summary.raw_weighted_mean_return_percent
        )


@pytest.mark.parametrize("field", ["spread_bps", "commission_bps", "slippage_bps", "latency_bps"])
def test_negative_cost_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        subject(**{field: -0.1})


@pytest.mark.parametrize("field", ["spread_bps", "commission_bps", "slippage_bps", "latency_bps"])
def test_excessive_cost_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        subject(**{field: 1000.1})


@pytest.mark.parametrize("field", ["spread_bps", "commission_bps", "slippage_bps", "latency_bps"])
def test_incomplete_cost_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match="is required"):
        subject(**{field: None})


def test_stress_cannot_be_lower_than_adverse() -> None:
    with pytest.raises(ValueError, match="greater than or equal"):
        subject(adverse_multiplier=2.0, stress_multiplier=1.5)


def test_fingerprint_changes_with_assumption_or_upstream_result() -> None:
    multi_window, baseline = subject()
    _, changed_assumption = subject(spread_bps=3.0)
    changed_upstream = replace(multi_window, fingerprint="sha256:changed")
    changed_result = evaluate_cost_scenarios(
        multi_window=changed_upstream, spread_bps=2, commission_bps=1,
        slippage_bps=1, latency_bps=.5, adverse_multiplier=1.5,
        stress_multiplier=2.5,
    )
    assert baseline.fingerprint != changed_assumption.fingerprint
    assert baseline.fingerprint != changed_result.fingerprint
