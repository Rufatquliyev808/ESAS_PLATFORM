import hashlib

import pytest

from backend.app.analysis.visual_acceptance import (
    ACCEPTED_FOR_SHADOW,
    MINIMUM_IMPROVEMENT_OVER_BASELINE,
    REJECTED,
    AcceptanceDecisionError,
    acceptance_decision_artifact_bytes,
    decide_acceptance,
)


EVALUATION_CHECKSUM = "sha256:evaluation-a"


def test_decide_acceptance_accepts_when_improvement_meets_minimum() -> None:
    decision = decide_acceptance(
        outcome="evaluated", evaluation_checksum=EVALUATION_CHECKSUM,
        holdout_accuracy=0.6, majority_baseline_accuracy=0.5,  # improvement exactly 0.1 >= 0.05
    )
    assert decision.decision == ACCEPTED_FOR_SHADOW
    assert decision.reasons == ()


def test_decide_acceptance_accepts_at_exact_minimum_boundary() -> None:
    holdout_accuracy = 0.5 + MINIMUM_IMPROVEMENT_OVER_BASELINE
    decision = decide_acceptance(
        outcome="evaluated", evaluation_checksum=EVALUATION_CHECKSUM,
        holdout_accuracy=holdout_accuracy, majority_baseline_accuracy=0.5,
    )
    assert decision.decision == ACCEPTED_FOR_SHADOW


def test_decide_acceptance_rejects_when_improvement_below_minimum() -> None:
    decision = decide_acceptance(
        outcome="evaluated", evaluation_checksum=EVALUATION_CHECKSUM,
        holdout_accuracy=0.52, majority_baseline_accuracy=0.5,  # improvement 0.02 < 0.05
    )
    assert decision.decision == REJECTED
    assert len(decision.reasons) == 1
    assert "improvement_over_baseline" in decision.reasons[0]


def test_decide_acceptance_rejects_when_model_worse_than_baseline() -> None:
    decision = decide_acceptance(
        outcome="evaluated", evaluation_checksum=EVALUATION_CHECKSUM,
        holdout_accuracy=0.0, majority_baseline_accuracy=1.0,
    )
    assert decision.decision == REJECTED
    assert decision.improvement_over_baseline == -1.0


def test_decide_acceptance_rejects_non_evaluated_outcome() -> None:
    with pytest.raises(AcceptanceDecisionError):
        decide_acceptance(
            outcome="out_of_distribution", evaluation_checksum=EVALUATION_CHECKSUM,
            holdout_accuracy=0.9, majority_baseline_accuracy=0.1,
        )


def test_decide_acceptance_is_deterministic() -> None:
    first = decide_acceptance(
        outcome="evaluated", evaluation_checksum=EVALUATION_CHECKSUM,
        holdout_accuracy=0.6, majority_baseline_accuracy=0.5,
    )
    second = decide_acceptance(
        outcome="evaluated", evaluation_checksum=EVALUATION_CHECKSUM,
        holdout_accuracy=0.6, majority_baseline_accuracy=0.5,
    )
    assert first == second
    assert first.checksum == second.checksum


def test_decide_acceptance_checksum_changes_with_evaluation_checksum() -> None:
    first = decide_acceptance(
        outcome="evaluated", evaluation_checksum="sha256:evaluation-a",
        holdout_accuracy=0.6, majority_baseline_accuracy=0.5,
    )
    second = decide_acceptance(
        outcome="evaluated", evaluation_checksum="sha256:evaluation-b",
        holdout_accuracy=0.6, majority_baseline_accuracy=0.5,
    )
    assert first.checksum != second.checksum


def test_acceptance_decision_artifact_bytes_hash_matches_checksum() -> None:
    decision = decide_acceptance(
        outcome="evaluated", evaluation_checksum=EVALUATION_CHECKSUM,
        holdout_accuracy=0.6, majority_baseline_accuracy=0.5,
    )
    artifact_bytes = acceptance_decision_artifact_bytes(decision)
    assert f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}" == decision.checksum
