from dataclasses import dataclass

from backend.app.analysis.visual_baseline_trainer import (
    compute_validation_metrics,
    fit_baseline_model,
    predict_validation,
)
from backend.app.analysis.visual_evaluation import INSUFFICIENT_EVIDENCE, compute_majority_baseline_accuracy
from backend.app.analysis.visual_model_spec import (
    ModelSpec,
    TrainingSpec,
    model_spec_id as compute_model_spec_id,
    training_spec_id as compute_training_spec_id,
)
from backend.app.analysis.visual_statistical_acceptance import (
    ACCEPTED_FOR_SHADOW,
    StatisticalAcceptanceDecision,
    compute_testing_family_id,
    decide_statistical_acceptance,
    statistical_acceptance_decision_artifact_bytes,
)
from backend.app.database.visual_acceptance_repository import (
    PersistedVisualAcceptanceDecision,
    persist_acceptance_decision,
)
from backend.app.database.visual_baseline_model_repository import get_baseline_model
from backend.app.database.visual_dataset_repository import get_dataset_manifest
from backend.app.database.visual_evaluation_repository import get_evaluation
from backend.app.database.visual_experiment_repository import (
    ACCEPTABLE_FROM_STATES,
    PersistedVisualExperiment,
    VisualExperimentOwnershipError,
    get_visual_experiment,
    mark_accepted_for_shadow,
    mark_insufficient_evidence,
    mark_rejected,
)
from backend.app.database.visual_testing_trial_repository import compute_trial_id, count_family_trials, get_trial
from backend.app.storage.artifact_store import put_artifact
from backend.app.strategies.visual_training_input_pipeline import build_visual_training_input


ACCEPTANCE_ARTIFACT_EXTENSION = "json"


class VisualAcceptanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualExperimentAcceptanceResult:
    experiment: PersistedVisualExperiment
    decision: StatisticalAcceptanceDecision
    persisted: PersistedVisualAcceptanceDecision | None


def decide_visual_experiment_acceptance(
    experiment_id: str,
    *,
    actor: str,
    actor_role: str,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
) -> VisualExperimentAcceptanceResult:
    """Orchestrates the Phase 5 statistical `evaluated -> accepted_for_shadow
    | rejected | insufficient_evidence` step. `accepted_for_shadow` is only
    reachable when ALL of the following hold -- there is no path to it that
    skips the registry:

    1. this exact (dataset, model spec, training spec) trial was
       pre-registered in `visual_testing_trials` (done automatically by
       `train_visual_baseline_model()`, BEFORE any result existed);
    2. the model reproduces byte-for-byte when recomputed fresh from the
       same persisted samples/artifacts right now;
    3. the persisted evaluation this decision is based on actually
       completed validly (`outcome == "evaluated"`);
    4. enough holdout samples to trust any conclusion;
    5. holdout accuracy beats the naive majority-baseline by the required
       margin;
    6. the one-sided exact binomial test clears alpha=0.05 AFTER
       Bonferroni correction for how many OTHER trials this dataset's
       testing family has accumulated -- more trials against the same
       dataset means a stricter bar for any one of them.

    This never recomputes the evaluation's PERSISTED summary fields from
    the DB -- it independently re-derives holdout accuracy/counts from a
    fresh model fit + fresh holdout predictions, which doubles as the
    reproduction check in #2 above.
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

    manifest = get_dataset_manifest(experiment_id)
    if manifest is None:
        raise VisualAcceptanceError("experiment has no dataset manifest")

    testing_family_id = compute_testing_family_id(manifest.dataset_fingerprint)
    model_spec_id_value = compute_model_spec_id(model_spec)
    training_spec_id_value = compute_training_spec_id(training_spec)
    trial_id = compute_trial_id(
        testing_family_id=testing_family_id, model_spec_id=model_spec_id_value,
        training_spec_id=training_spec_id_value,
    )
    trial_registered = get_trial(trial_id) is not None
    family_trial_count = max(1, count_family_trials(testing_family_id))

    # Recompute the model and holdout predictions fresh, from the same
    # persisted samples/artifacts, rather than trusting the DB summary --
    # this both re-derives exact holdout counts for the binomial test and
    # doubles as the model-reproduction check.
    training_input = build_visual_training_input(
        experiment_id, actor=actor, model_spec=model_spec, training_spec=training_spec,
    )
    recomputed_model = fit_baseline_model(
        training_input.train_batches, preprocessing_state=training_input.preprocessing_state,
        model_spec=model_spec, training_spec=training_spec, dataset_fingerprint=manifest.dataset_fingerprint,
    )
    persisted_model = get_baseline_model(experiment_id)
    reproduction_verified = (
        persisted_model is not None and recomputed_model.checksum == persisted_model.model_checksum
    )

    holdout_predictions = predict_validation(training_input.holdout_samples, recomputed_model)
    holdout_metrics = compute_validation_metrics(holdout_predictions)
    majority_baseline_accuracy = compute_majority_baseline_accuracy(
        recomputed_model, training_input.holdout_samples,
    )

    decision = decide_statistical_acceptance(
        testing_family_id=testing_family_id, family_trial_count=family_trial_count,
        trial_registered=trial_registered, reproduction_verified=reproduction_verified,
        evaluation_outcome=evaluation.outcome, holdout_sample_count=holdout_metrics.sample_count,
        holdout_correct_count=holdout_metrics.correct_count,
        majority_baseline_accuracy=majority_baseline_accuracy,
        evaluation_checksum=evaluation.evaluation_checksum, model_checksum=recomputed_model.checksum,
    )
    put_artifact(
        decision.checksum, statistical_acceptance_decision_artifact_bytes(decision),
        extension=ACCEPTANCE_ARTIFACT_EXTENSION,
    )

    if decision.decision == ACCEPTED_FOR_SHADOW:
        transition = mark_accepted_for_shadow
    elif decision.decision == INSUFFICIENT_EVIDENCE:
        transition = mark_insufficient_evidence
    else:
        transition = mark_rejected
    transitioned_experiment = transition(
        experiment_id=experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=experiment.state_version,
    )

    # visual_acceptance_decisions' `decision` column only ever means
    # "accepted_for_shadow" or "rejected" -- an insufficient_evidence
    # abstain is already fully recorded by the lifecycle transition's own
    # audit row plus the content-addressed decision artifact above, so
    # there is nothing meaningful left to summarize into that table.
    persisted = None
    if decision.decision != INSUFFICIENT_EVIDENCE:
        persisted = persist_acceptance_decision(
            experiment_id=experiment_id, evaluation_checksum=decision.evaluation_checksum,
            decision=decision.decision, holdout_accuracy=decision.holdout_accuracy,
            majority_baseline_accuracy=decision.majority_baseline_accuracy,
            improvement_over_baseline=decision.improvement_over_baseline, decision_checksum=decision.checksum,
        )

    return VisualExperimentAcceptanceResult(
        experiment=transitioned_experiment, decision=decision, persisted=persisted,
    )
