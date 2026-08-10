from dataclasses import dataclass

from backend.app.analysis.visual_baseline_trainer import predict_validation
from backend.app.analysis.visual_evaluation import (
    EVALUATED,
    INSUFFICIENT_EVIDENCE,
    OUT_OF_DISTRIBUTION,
    EvaluationArtifact,
    build_evaluation_artifact,
    evaluation_artifact_bytes,
)
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.database.visual_evaluation_repository import PersistedVisualEvaluation, persist_evaluation
from backend.app.database.visual_experiment_repository import (
    PersistedVisualExperiment,
    get_visual_experiment,
    mark_evaluated,
    mark_insufficient_evidence,
    mark_out_of_distribution,
)
from backend.app.storage.artifact_store import put_artifact
from backend.app.strategies.visual_baseline_training import train_visual_baseline_model
from backend.app.strategies.visual_training_input_pipeline import build_visual_training_input


EVALUATION_ARTIFACT_EXTENSION = "json"

_TRANSITION_BY_OUTCOME = {
    INSUFFICIENT_EVIDENCE: mark_insufficient_evidence,
    OUT_OF_DISTRIBUTION: mark_out_of_distribution,
    EVALUATED: mark_evaluated,
}


@dataclass(frozen=True)
class VisualExperimentEvaluationResult:
    experiment: PersistedVisualExperiment
    evaluation: EvaluationArtifact
    persisted: PersistedVisualEvaluation


def evaluate_visual_experiment(
    experiment_id: str,
    *,
    actor: str,
    actor_role: str,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
) -> VisualExperimentEvaluationResult:
    """Orchestrates the Phase 5 `training -> evaluated` step: fits/re-fits
    the baseline model (idempotent -- `train_visual_baseline_model()`
    already verified ownership and that the experiment is in `training`
    state), then evaluates it against HOLDOUT -- the first and only place
    in the whole Phase 5 pipeline holdout data is actually used.

    Transitions to `evaluated`, `out_of_distribution`, or
    `insufficient_evidence` depending on `EvaluationArtifact.outcome`;
    never to anything else. Persists the full evaluation artifact to the
    content-addressed artifact store plus a summary row.
    """
    training_result = train_visual_baseline_model(
        experiment_id, actor=actor, model_spec=model_spec, training_spec=training_spec,
    )
    model = training_result.model
    # train_visual_baseline_model() already verified ownership and the
    # `training` lifecycle state -- re-read here only for a fresh
    # state_version to use in the transition below.
    experiment = get_visual_experiment(experiment_id)

    training_input = build_visual_training_input(
        experiment_id, actor=actor, model_spec=model_spec, training_spec=training_spec,
    )
    validation_predictions = predict_validation(training_input.validation_samples, model)
    holdout_predictions = predict_validation(training_input.holdout_samples, model)

    evaluation = build_evaluation_artifact(
        model=model, holdout_samples=training_input.holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    put_artifact(
        evaluation.checksum, evaluation_artifact_bytes(evaluation), extension=EVALUATION_ARTIFACT_EXTENSION,
    )

    transition = _TRANSITION_BY_OUTCOME[evaluation.outcome]
    transitioned_experiment = transition(
        experiment_id=experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=experiment.state_version,
    )

    persisted = persist_evaluation(
        experiment_id=experiment_id, model_checksum=model.checksum, outcome=evaluation.outcome,
        holdout_sample_count=evaluation.holdout_sample_count,
        holdout_accuracy=evaluation.holdout_metrics.accuracy,
        majority_baseline_accuracy=evaluation.majority_baseline_accuracy,
        evaluation_checksum=evaluation.checksum,
    )

    return VisualExperimentEvaluationResult(
        experiment=transitioned_experiment, evaluation=evaluation, persisted=persisted,
    )
