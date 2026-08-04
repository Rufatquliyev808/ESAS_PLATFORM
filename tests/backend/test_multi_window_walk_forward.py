from dataclasses import replace

import pytest

from backend.app.strategies.multi_window_walk_forward import (
    INSUFFICIENT_DATA,
    READY,
    evaluate_multi_window_walk_forward,
)
from backend.app.strategies.outcome_evaluation import evaluate_strategy_outcomes
from tests.backend.test_strategy_outcome_evaluation import bar, strategy


def evaluate(
    closes: list[float], *, horizon: int = 1, ratio: float = 0.5,
    windows: int = 3,
):
    bars = tuple(bar(index, close) for index, close in enumerate(closes))
    strategy_result = strategy(bars)
    outcome = evaluate_strategy_outcomes(
        strategy=strategy_result, bars=bars, horizon_bars=horizon,
    )
    result = evaluate_multi_window_walk_forward(
        strategy=strategy_result, outcome=outcome, bars=bars,
        development_ratio=ratio, window_count=windows,
    )
    return bars, strategy_result, outcome, result


def test_windows_are_chronological_non_overlapping_and_development_expands() -> None:
    bars, _, _, result = evaluate(list(range(100, 112)), windows=3)
    assert result.status == READY
    assert result.summary.completed_windows == 3
    assert result.manifest.initial_development_bars == 6
    assert result.manifest.split_policy == (
        "expanding_development_non_overlapping_chronological_validation_no_shuffle"
    )
    boundaries = [
        (
            window.manifest.development_end_index_exclusive,
            window.manifest.validation_start_index,
            window.manifest.validation_end_index_exclusive,
        )
        for window in result.windows
    ]
    assert boundaries == [(6, 6, 8), (8, 8, 10), (10, 10, 12)]
    assert result.windows[0].validation.start_bar_end_at == bars[6].end_at
    assert result.windows[-1].validation.end_bar_end_at == bars[11].end_at
    assert all(
        left.manifest.validation_end_index_exclusive
        == right.manifest.validation_start_index
        for left, right in zip(result.windows, result.windows[1:])
    )


def test_each_development_window_excludes_outcomes_crossing_its_boundary() -> None:
    _, _, _, result = evaluate(list(range(100, 112)), horizon=2, windows=3)
    assert [window.development.boundary_excluded for window in result.windows] == [2, 2, 2]
    assert all(window.validation.boundary_excluded == 0 for window in result.windows)


def test_later_prices_cannot_change_first_development_summary() -> None:
    bars, strategy_result, _, original = evaluate(list(range(100, 112)), windows=3)
    changed_bars = bars[:6] + tuple(replace(item, close=item.close * 10) for item in bars[6:])
    changed_outcome = evaluate_strategy_outcomes(
        strategy=strategy_result, bars=changed_bars, horizon_bars=1,
    )
    changed = evaluate_multi_window_walk_forward(
        strategy=strategy_result, outcome=changed_outcome, bars=changed_bars,
        development_ratio=0.5, window_count=3,
    )
    assert changed.windows[0].development == original.windows[0].development
    assert changed.windows[0].manifest.development_bar_fingerprint == (
        original.windows[0].manifest.development_bar_fingerprint
    )


def test_result_and_per_window_manifests_are_deterministic_and_traceable() -> None:
    _, strategy_result, outcome, first = evaluate(list(range(100, 112)), windows=3)
    _, _, _, second = evaluate(list(range(100, 112)), windows=3)
    assert first == second
    assert first.manifest.strategy_fingerprint == strategy_result.fingerprint
    assert first.manifest.outcome_fingerprint == outcome.fingerprint
    assert len({window.fingerprint for window in first.windows}) == 3
    assert all(window.manifest.upstream_strategy_fingerprint == strategy_result.fingerprint for window in first.windows)


def test_summary_keeps_coverage_and_cost_free_returns_separate() -> None:
    _, _, _, result = evaluate([100, 101, 100, 103, 102, 105, 104, 107], windows=2)
    summary = result.summary
    assert summary.total_validation_observations == 4
    assert summary.matured_validation_observations + summary.immature_validation_observations + summary.not_applicable_validation_observations == 4
    assert summary.positive_windows + summary.negative_windows + summary.flat_windows == summary.windows_with_matured_observations
    assert summary.minimum_window_mean_return_percent is not None
    assert summary.maximum_window_mean_return_percent is not None
    assert summary.return_range_percentage_points == pytest.approx(
        summary.maximum_window_mean_return_percent - summary.minimum_window_mean_return_percent
    )


def test_small_dataset_is_explicitly_insufficient() -> None:
    _, _, _, empty = evaluate([], windows=3)
    _, _, _, one_bar = evaluate([100], windows=3)
    _, _, _, two_bars = evaluate([100, 101], windows=3)
    assert empty.status == INSUFFICIENT_DATA and not empty.windows
    assert one_bar.status == INSUFFICIENT_DATA and not one_bar.windows
    assert two_bars.status == INSUFFICIENT_DATA and len(two_bars.windows) == 1


@pytest.mark.parametrize("window_count", [1, 9])
def test_unsafe_window_count_is_rejected(window_count: int) -> None:
    with pytest.raises(ValueError, match="window count"):
        evaluate([100, 101, 102], windows=window_count)
