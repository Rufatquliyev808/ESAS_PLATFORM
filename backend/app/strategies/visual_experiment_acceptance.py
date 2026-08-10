from dataclasses import dataclass

from backend.app.analysis.visual_acceptance import (
    ACCEPTED_FOR_SHADOW,
    AcceptanceDecision,
    acceptance_decision_artifact_bytes,
    decide_acceptance,
)
from backend.app.database.visual_acceptance_repository import (
    PersistedVisualAcceptanceDecision,
    persist_acceptance_decision,
)
from backend.app.database.visual_evaluation_repository import get_evaluation
from backend.app.database.visual_experiment_repository import (
    ACCEPTABLE_FROM_STATES,
    PersistedVisualExperiment,
    VisualExperimentOwnershipError,
    get_visual_experiment,
    mark_accepted_for_shadow,
    mark_rejected,
)
from backend.app.storage.artifact_store import put_artifact


ACCEPTANCE_ARTIFACT_EXTENSION = "json"


class VisualAcceptanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualExperimentAcceptanceResult:
    experiment: PersistedVisualExperiment
    decision: AcceptanceDecision
    persisted: PersistedVisualAcceptanceDecision


def decide_visual_experiment_acceptance(
    experiment_id: str, *, actor: str, actor_role: str,
) -> VisualExperimentAcceptanceResult:
    """Orchestrates the Phase 5 `evaluated -> accepted_for_shadow |
    rejected` step: reads the already-persisted holdout evaluation (never
    recomputes it -- this decision is about what was already measured, not
    a new evaluation run), applies the v1 accept/reject heuristic, persists
    the decision artifact, and transitions the experiment accordingly.

    Requires the experiment already be in `evaluated` state -- an
    experiment that abstained (`insufficient_evidence`) or was flagged
    `out_of_distribution` never reaches this step, since neither of those
    outcomes produced a trustworthy evaluation to decide from.

    This decision governs SHADOW eligibility only; it never authorizes
    real trading by itself.
    """
    experiment = get_visual_experiment(experiment_id)
    if experiment.created_by != actor:
        raise VisualExperimentOwnershipError("visual experiment belongs to another user")
    if experiment.lifecycle_state not in ACCEPTABLE_FROM_STATES:
        raise VisualAcceptanceError(
            f"experiment must be in 'evaluated' state to decide acceptance, is {experiment.lifecycle_state!r}"
        )

    evaluation = get_evaluation(experiment_id)
    if evaluation is None:
        raise VisualAcceptanceError("experiment has no persisted evaluation")

    decision = decide_acceptance(
        outcome=evaluation.outcome, evaluation_checksum=evaluation.evaluation_checksum,
        holdout_accuracy=evaluation.holdout_accuracy,
        majority_baseline_accuracy=evaluation.majority_baseline_accuracy,
    )
    put_artifact(
        decision.checksum, acceptance_decision_artifact_bytes(decision),
        extension=ACCEPTANCE_ARTIFACT_EXTENSION,
    )

    transition = mark_accepted_for_shadow if decision.decision == ACCEPTED_FOR_SHADOW else mark_rejected
    transitioned_experiment = transition(
        experiment_id=experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=experiment.state_version,
    )

    persisted = persist_acceptance_decision(
        experiment_id=experiment_id, evaluation_checksum=decision.evaluation_checksum,
        decision=decision.decision, holdout_accuracy=decision.holdout_accuracy,
        majority_baseline_accuracy=decision.majority_baseline_accuracy,
        improvement_over_baseline=decision.improvement_over_baseline, decision_checksum=decision.checksum,
    )

    return VisualExperimentAcceptanceResult(
        experiment=transitioned_experiment, decision=decision, persisted=persisted,
    )
