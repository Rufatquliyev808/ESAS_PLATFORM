from dataclasses import dataclass
import time

from backend.app.analysis.visual_baseline_trainer import (
    BaselineModelArtifact,
    TrainingLogArtifact,
    baseline_model_artifact_bytes,
    build_training_log,
    compute_validation_metrics,
    fit_baseline_model,
    predict_validation,
    training_log_artifact_bytes,
)
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.database.visual_baseline_model_repository import (
    PersistedVisualBaselineModel,
    persist_baseline_model,
)
from backend.app.database.visual_dataset_repository import get_dataset_manifest
from backend.app.database.visual_experiment_repository import VisualExperimentOwnershipError, get_visual_experiment
from backend.app.storage.artifact_store import put_artifact
from backend.app.strategies.visual_training_input_pipeline import build_visual_training_input


MODEL_ARTIFACT_EXTENSION = "json"
LOG_ARTIFACT_EXTENSION = "json"
TRAINABLE_LIFECYCLE_STATES = frozenset({"training"})


class VisualBaselineTrainingError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualBaselineTrainingResult:
    model: BaselineModelArtifact
    log: TrainingLogArtifact
    persisted: PersistedVisualBaselineModel


def train_visual_baseline_model(
    experiment_id: str,
    *,
    actor: str,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
) -> VisualBaselineTrainingResult:
    """Phase 5 Deterministic CPU visual baseline trainer v1
    (`pixel_centroid_baseline_v1`): fits a nearest-centroid classifier from
    TRAIN samples only, scores VALIDATION samples against it, and persists
    both the model and its training log as content-addressed artifacts.

    Holdout is never given to this trainer at all in this phase:
    `build_visual_training_input()`'s `holdout_samples` are read here only
    to confirm the training-input pipeline still ran successfully -- they
    are never passed to `fit_baseline_model()` or `predict_validation()`.
    That is the "separated by construction" requirement, not a runtime
    check: neither of those functions even accepts a holdout parameter.

    The experiment's lifecycle state is left exactly as it was
    (`training`) -- no lifecycle transition happens here. `training ->
    evaluated` is a separate, later step that has not been built yet.
    """
    experiment = get_visual_experiment(experiment_id)
    if experiment.created_by != actor:
        raise VisualExperimentOwnershipError("visual experiment belongs to another user")
    if experiment.lifecycle_state not in TRAINABLE_LIFECYCLE_STATES:
        raise VisualBaselineTrainingError(
            f"experiment must be in 'training' state to fit a baseline model, is {experiment.lifecycle_state!r}"
        )

    manifest = get_dataset_manifest(experiment_id)
    if manifest is None:
        raise VisualBaselineTrainingError("experiment has no dataset manifest")

    training_input = build_visual_training_input(
        experiment_id, actor=actor, model_spec=model_spec, training_spec=training_spec,
    )
    # training_input.holdout_samples is deliberately never referenced below.

    started_at = time.perf_counter()
    model = fit_baseline_model(
        training_input.train_batches, preprocessing_state=training_input.preprocessing_state,
        model_spec=model_spec, training_spec=training_spec, dataset_fingerprint=manifest.dataset_fingerprint,
    )
    predictions = predict_validation(training_input.validation_samples, model)
    validation_metrics = compute_validation_metrics(predictions)
    duration_seconds = time.perf_counter() - started_at

    train_sample_count = sum(len(batch.samples) for batch in training_input.train_batches)
    log = build_training_log(
        model=model, validation_metrics=validation_metrics, train_sample_count=train_sample_count,
        validation_sample_count=len(training_input.validation_samples), duration_seconds=duration_seconds,
    )

    put_artifact(model.checksum, baseline_model_artifact_bytes(model), extension=MODEL_ARTIFACT_EXTENSION)
    put_artifact(log.checksum, training_log_artifact_bytes(log), extension=LOG_ARTIFACT_EXTENSION)

    persisted = persist_baseline_model(
        experiment_id=experiment_id, architecture_id=model.architecture_id, version=model.version,
        dataset_fingerprint=model.dataset_fingerprint, preprocessing_checksum=model.preprocessing_checksum,
        model_spec_id=model.model_spec_id, training_spec_id=model.training_spec_id,
        model_checksum=model.checksum, log_checksum=log.checksum,
    )

    return VisualBaselineTrainingResult(model=model, log=log, persisted=persisted)
