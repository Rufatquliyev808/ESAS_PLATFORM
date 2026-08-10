import hashlib

import pytest

from backend.app.analysis.visual_acceptance import ACCEPTED_FOR_SHADOW, REJECTED
from backend.app.analysis.visual_evaluation import INSUFFICIENT_EVIDENCE, MINIMUM_HOLDOUT_SAMPLES
from backend.app.analysis.visual_statistical_acceptance import (
    bonferroni_corrected_alpha,
    compute_testing_family_id,
    decide_statistical_acceptance,
    one_sided_binomial_p_value,
    statistical_acceptance_decision_artifact_bytes,
    wilson_score_interval,
)


DEFAULT_KWARGS = dict(
    testing_family_id="sha256:family-a",
    trial_registered=True,
    reproduction_verified=True,
    evaluation_outcome="evaluated",
    evaluation_checksum="sha256:evaluation-a",
    model_checksum="sha256:model-a",
)


def test_one_sided_binomial_p_value_matches_known_reference_values() -> None:
    assert one_sided_binomial_p_value(9, 10, 0.5) == pytest.approx(0.0107421875)
    assert one_sided_binomial_p_value(5, 10, 0.5) == pytest.approx(0.623046875)
    assert one_sided_binomial_p_value(0, 5, 0.5) == pytest.approx(1.0)
    assert one_sided_binomial_p_value(5, 5, 0.5) == pytest.approx(0.5 ** 5)


def test_one_sided_binomial_p_value_edge_cases() -> None:
    assert one_sided_binomial_p_value(0, 0, 0.5) == 1.0
    assert one_sided_binomial_p_value(0, 5, 0.0) == 1.0
    assert one_sided_binomial_p_value(1, 5, 0.0) == 0.0
    assert one_sided_binomial_p_value(5, 5, 1.0) == 1.0


def test_one_sided_binomial_p_value_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        one_sided_binomial_p_value(6, 5, 0.5)
    with pytest.raises(ValueError):
        one_sided_binomial_p_value(-1, 5, 0.5)
    with pytest.raises(ValueError):
        one_sided_binomial_p_value(1, 5, 1.5)


def test_wilson_score_interval_contains_observed_proportion() -> None:
    lower, upper = wilson_score_interval(9, 10)
    assert lower < 0.9 < upper
    assert 0.0 <= lower <= upper <= 1.0


def test_wilson_score_interval_zero_samples_is_maximally_wide() -> None:
    assert wilson_score_interval(0, 0) == (0.0, 1.0)


def test_bonferroni_corrected_alpha_scales_inversely_with_trial_count() -> None:
    assert bonferroni_corrected_alpha(0.05, 1) == pytest.approx(0.05)
    assert bonferroni_corrected_alpha(0.05, 20) == pytest.approx(0.0025)
    assert bonferroni_corrected_alpha(0.05, 100) == pytest.approx(0.0005)


def test_bonferroni_corrected_alpha_rejects_non_positive_trial_count() -> None:
    with pytest.raises(ValueError):
        bonferroni_corrected_alpha(0.05, 0)


def test_compute_testing_family_id_is_deterministic_and_dataset_scoped() -> None:
    id_a1 = compute_testing_family_id("sha256:dataset-a")
    id_a2 = compute_testing_family_id("sha256:dataset-a")
    id_b = compute_testing_family_id("sha256:dataset-b")
    assert id_a1 == id_a2
    assert id_a1 != id_b


def test_decide_statistical_acceptance_accepts_single_trial_significant_result() -> None:
    # 11/11 correct vs a 0.5 baseline is exactly significant at alpha=0.05
    # even for a single trial (p = 0.5**11 ~= 0.000488).
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    assert decision.decision == ACCEPTED_FOR_SHADOW
    assert decision.reasons == ()
    assert decision.family_trial_count == 1
    assert decision.corrected_alpha == pytest.approx(0.05)


def test_decide_statistical_acceptance_same_result_rejected_with_larger_family() -> None:
    """The core multiple-testing acceptance criterion: the SAME holdout
    evidence that passes for a single-trial family is rejected once the
    family has accumulated enough OTHER trials that Bonferroni correction
    tightens the bar past what this result clears.
    """
    single_trial = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    large_family = decide_statistical_acceptance(
        family_trial_count=200, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    assert single_trial.decision == ACCEPTED_FOR_SHADOW
    assert large_family.decision == REJECTED
    assert any("corrected alpha" in reason or "p_value" in reason for reason in large_family.reasons)
    assert large_family.corrected_alpha < single_trial.corrected_alpha


def test_decide_statistical_acceptance_rejects_when_trial_not_preregistered() -> None:
    kwargs = dict(DEFAULT_KWARGS)
    kwargs["trial_registered"] = False
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **kwargs,
    )
    assert decision.decision == REJECTED
    assert "trial_not_preregistered" in decision.reasons


def test_decide_statistical_acceptance_rejects_when_reproduction_not_verified() -> None:
    kwargs = dict(DEFAULT_KWARGS)
    kwargs["reproduction_verified"] = False
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **kwargs,
    )
    assert decision.decision == REJECTED
    assert "model_reproduction_checksum_mismatch" in decision.reasons


def test_decide_statistical_acceptance_rejects_when_evaluation_outcome_not_evaluated() -> None:
    kwargs = dict(DEFAULT_KWARGS)
    kwargs["evaluation_outcome"] = "out_of_distribution"
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **kwargs,
    )
    assert decision.decision == REJECTED
    assert any("evaluation_outcome_not_evaluated" in reason for reason in decision.reasons)


def test_decide_statistical_acceptance_rejects_when_improvement_too_small() -> None:
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=11, holdout_correct_count=6,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    assert decision.decision == REJECTED
    assert any("improvement_over_baseline" in reason for reason in decision.reasons)


def test_decide_statistical_acceptance_insufficient_evidence_below_minimum_holdout() -> None:
    assert MINIMUM_HOLDOUT_SAMPLES >= 1
    n = MINIMUM_HOLDOUT_SAMPLES - 1
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=n, holdout_correct_count=n,
        majority_baseline_accuracy=0.1, **DEFAULT_KWARGS,
    )
    assert decision.decision == INSUFFICIENT_EVIDENCE


def test_decide_statistical_acceptance_insufficient_evidence_takes_priority_over_other_failures() -> None:
    kwargs = dict(DEFAULT_KWARGS)
    kwargs["trial_registered"] = False
    kwargs["reproduction_verified"] = False
    n = MINIMUM_HOLDOUT_SAMPLES - 1
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=n, holdout_correct_count=0,
        majority_baseline_accuracy=0.9, **kwargs,
    )
    assert decision.decision == INSUFFICIENT_EVIDENCE


def test_decide_statistical_acceptance_is_deterministic() -> None:
    first = decide_statistical_acceptance(
        family_trial_count=3, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    second = decide_statistical_acceptance(
        family_trial_count=3, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    assert first == second
    assert first.checksum == second.checksum


def test_statistical_acceptance_decision_artifact_bytes_hash_matches_checksum() -> None:
    decision = decide_statistical_acceptance(
        family_trial_count=1, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    artifact_bytes = statistical_acceptance_decision_artifact_bytes(decision)
    assert f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}" == decision.checksum


def test_decision_artifact_records_family_trial_count_and_corrected_alpha() -> None:
    decision = decide_statistical_acceptance(
        family_trial_count=7, holdout_sample_count=11, holdout_correct_count=11,
        majority_baseline_accuracy=0.5, **DEFAULT_KWARGS,
    )
    assert decision.family_trial_count == 7
    assert decision.corrected_alpha == pytest.approx(0.05 / 7)
    assert decision.base_alpha == pytest.approx(0.05)
