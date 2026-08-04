from dataclasses import replace

import pytest

from backend.app.strategies.outcome_evaluation import evaluate_strategy_outcomes
from backend.app.strategies.walk_forward_evaluation import (
    INSUFFICIENT_DATA,
    READY,
    evaluate_walk_forward,
)
from tests.backend.test_strategy_outcome_evaluation import bar, strategy


def evaluate(closes: list[float], *, horizon: int = 1, ratio: float = 0.6):
    bars = tuple(bar(index, close) for index, close in enumerate(closes))
    strategy_result = strategy(bars)
    outcome = evaluate_strategy_outcomes(
        strategy=strategy_result, bars=bars, horizon_bars=horizon,
    )
    return bars, strategy_result, outcome, evaluate_walk_forward(
        strategy=strategy_result, outcome=outcome, bars=bars,
        development_ratio=ratio,
    )


def test_split_is_chronological_and_manifest_is_traceable() -> None:
    bars, strategy_result, outcome, result = evaluate([100, 101, 102, 103, 104], ratio=0.6)
    assert result.status == READY
    assert result.manifest.split_index == 3
    assert result.manifest.split_policy == "chronological_no_shuffle_validation_untouched"
    assert result.manifest.parameter_source == "development_configuration"
    assert result.manifest.parameters == strategy_result.parameters
    assert result.manifest.outcome_fingerprint == outcome.fingerprint
    assert result.development.start_bar_end_at == bars[0].end_at
    assert result.development.end_bar_end_at == bars[2].end_at
    assert result.validation.start_bar_end_at == bars[3].end_at
    assert result.validation.end_bar_end_at == bars[4].end_at


def test_development_outcome_crossing_validation_boundary_is_excluded() -> None:
    _, _, _, result = evaluate([100, 101, 102, 103, 104, 105], horizon=2, ratio=0.5)
    assert result.manifest.split_index == 3
    assert result.development.boundary_excluded == 2
    assert result.development.matured == 0
    assert result.development.not_applicable == 1
    assert result.validation.matured == 1
    assert result.validation.immature == 2


def test_validation_price_change_cannot_change_development_summary() -> None:
    bars, strategy_result, _, original = evaluate([100, 101, 102, 103, 104, 105], ratio=0.5)
    changed_bars = bars[:3] + tuple(replace(item, close=item.close * 10) for item in bars[3:])
    changed_outcome = evaluate_strategy_outcomes(
        strategy=strategy_result, bars=changed_bars, horizon_bars=1,
    )
    changed = evaluate_walk_forward(
        strategy=strategy_result, outcome=changed_outcome, bars=changed_bars,
        development_ratio=0.5,
    )
    assert original.development == changed.development
    assert original.fingerprint != changed.fingerprint


def test_same_input_is_deterministic() -> None:
    bars, strategy_result, outcome, first = evaluate([100, 99, 101, 98, 102])
    second = evaluate_walk_forward(
        strategy=strategy_result, outcome=outcome, bars=bars,
        development_ratio=0.6,
    )
    assert first == second
    assert first.fingerprint.startswith("sha256:")


def test_small_dataset_is_reported_without_fabricating_validation() -> None:
    _, _, _, result = evaluate([100], ratio=0.7)
    assert result.status == INSUFFICIENT_DATA
    assert result.manifest.split_index == 1
    assert result.development.total_observations == 1
    assert result.validation.total_observations == 0
    assert result.validation.start_bar_end_at is None


@pytest.mark.parametrize("ratio", [0.49, 0.91])
def test_unsafe_split_ratio_is_rejected(ratio: float) -> None:
    bars = tuple(bar(index, 100 + index) for index in range(3))
    strategy_result = strategy(bars)
    outcome = evaluate_strategy_outcomes(
        strategy=strategy_result, bars=bars, horizon_bars=1,
    )
    with pytest.raises(ValueError, match="between 0.5 and 0.9"):
        evaluate_walk_forward(
            strategy=strategy_result, outcome=outcome, bars=bars,
            development_ratio=ratio,
        )
