from collections import Counter
from dataclasses import dataclass

from backend.app.analysis.visual_dataset import HOLDOUT, LABELED, TRAIN, VALIDATION
from backend.app.analysis.visual_materializer import dataset_fingerprint_for_identities
from backend.app.analysis.visual_model_spec import (
    ModelSpec,
    TrainingSpec,
    model_spec_id as compute_model_spec_id,
    training_configuration_checksum as compute_training_configuration_checksum,
    training_spec_id as compute_training_spec_id,
    validate_model_spec,
    validate_training_spec,
)
from backend.app.database.visual_dataset_repository import get_dataset_manifest, list_dataset_samples
from backend.app.database.visual_experiment_repository import (
    PersistedVisualExperiment,
    VisualExperimentOwnershipError,
    begin_training_atomically,
    block_experiment_for_data_quality,
    get_visual_experiment,
)
from backend.app.database.visual_training_repository import PersistedVisualTrainingConfig
from backend.app.storage.artifact_store import ArtifactIntegrityError, get_artifact, has_artifact


ARTIFACT_EXTENSION = "png"
REQUIRED_SPLITS = (TRAIN, VALIDATION, HOLDOUT)
# Deliberately conservative and not statistically meaningful -- this system does
# not train real models yet. The threshold exists to catch the degenerate case
# (a handful of samples) fail-closed, not to approximate a real ML minimum.
MINIMUM_TRAIN_SAMPLES = 10


class TrainingReadinessError(RuntimeError):
    """Raised when one or more training-readiness gates fail. `reasons` is
    every gate that failed (not just the first), so a caller/operator can see
    the full picture in one attempt rather than fixing issues one at a time.
    """

    def __init__(self, reasons: tuple[str, ...]):
        super().__init__("training readiness gates failed: " + "; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class VisualExperimentTrainingResult:
    experiment: PersistedVisualExperiment
    training_config: PersistedVisualTrainingConfig


def _evaluate_readiness(
    experiment: PersistedVisualExperiment,
) -> tuple[str, ...]:
    """Every training-readiness gate the Phase 5 `rendering -> training`
    contract requires: dataset manifest exists, dataset fingerprint has not
    drifted since materialization, every sample's PNG artifact exists and
    matches its checksum, train/validation/holdout splits are all present,
    no pending-horizon sample has leaked into train, and the train split
    meets a minimum size. Returns every failing reason, not just the first --
    an empty tuple means every gate passed.
    """
    reasons: list[str] = []

    manifest = get_dataset_manifest(experiment.experiment_id)
    if manifest is None:
        reasons.append("dataset_manifest_missing")

    samples = list_dataset_samples(experiment.experiment_id)
    if not samples:
        reasons.append("dataset_samples_missing")

    if manifest is not None and samples:
        identities = tuple(
            f"{sample.sample_id}:{sample.image_checksum}:{sample.split_id}" for sample in samples
        )
        recomputed_fingerprint = dataset_fingerprint_for_identities(
            bar_fingerprint=experiment.source_bar_fingerprint,
            render_spec_id=experiment.render_spec_id,
            label_spec_id=experiment.label_spec_id,
            observation_window_bars=experiment.observation_window_bars,
            train_end_at=experiment.train_end_at,
            validation_end_at=experiment.validation_end_at,
            sample_identities=identities,
        )
        if recomputed_fingerprint != manifest.dataset_fingerprint:
            reasons.append("dataset_fingerprint_changed")

    missing_artifacts = 0
    invalid_artifacts = 0
    for sample in samples:
        if not has_artifact(sample.artifact_checksum, extension=ARTIFACT_EXTENSION):
            missing_artifacts += 1
            continue
        try:
            get_artifact(sample.artifact_checksum, extension=ARTIFACT_EXTENSION, verify=True)
        except ArtifactIntegrityError:
            invalid_artifacts += 1
    if missing_artifacts:
        reasons.append(f"artifacts_missing:{missing_artifacts}")
    if invalid_artifacts:
        reasons.append(f"artifacts_checksum_invalid:{invalid_artifacts}")

    split_counts = Counter(sample.split_id for sample in samples)
    for split in REQUIRED_SPLITS:
        if split_counts.get(split, 0) < 1:
            reasons.append(f"split_missing:{split}")

    mislabeled_train = sum(
        1 for sample in samples if sample.split_id == TRAIN and sample.label_status != LABELED
    )
    if mislabeled_train:
        reasons.append(f"unlabeled_samples_in_train:{mislabeled_train}")

    if split_counts.get(TRAIN, 0) < MINIMUM_TRAIN_SAMPLES:
        reasons.append("insufficient_train_samples")

    return tuple(reasons)


def start_visual_experiment_training(
    experiment_id: str,
    *,
    actor: str,
    actor_role: str,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
) -> VisualExperimentTrainingResult:
    """Orchestrates the Phase 5 `rendering -> training` step. Every
    readiness gate is evaluated BEFORE any lifecycle transition is attempted
    -- an incomplete or corrupted dataset is never even offered the chance to
    reach `training`. If any gate fails, the experiment moves to
    `blocked_by_data_quality` (fail-closed, append-only audited) and
    `TrainingReadinessError` is raised with every failing reason. Only if all
    gates pass does the experiment move to `training` and the frozen
    ModelSpec/TrainingSpec get persisted, keyed by a deterministic
    `training_configuration_checksum` over (dataset_fingerprint,
    model_spec_id, training_spec_id) -- the same dataset and spec always
    produce the same checksum.

    Performs no actual model training, adds no ML dependency, and does not
    touch the frontend or production database -- this increment is the
    lifecycle contract and its safety gates only.

    The `training` transition, its audit row, and the persisted training
    configuration are written in ONE atomic step
    (`begin_training_atomically()`) rather than as two separate repository
    calls -- an experiment can never end up `training` with no recorded
    configuration, even if the process crashes mid-way.
    """
    validate_model_spec(model_spec)
    validate_training_spec(training_spec)

    experiment = get_visual_experiment(experiment_id)
    if experiment.created_by != actor:
        raise VisualExperimentOwnershipError("visual experiment belongs to another user")

    reasons = _evaluate_readiness(experiment)
    if reasons:
        block_experiment_for_data_quality(
            experiment_id=experiment.experiment_id, actor=actor, actor_role=actor_role,
            expected_state_version=experiment.state_version,
        )
        raise TrainingReadinessError(reasons)

    manifest = get_dataset_manifest(experiment.experiment_id)
    assert manifest is not None  # guaranteed by the readiness gate above

    computed_model_spec_id = compute_model_spec_id(model_spec)
    computed_training_spec_id = compute_training_spec_id(training_spec)
    checksum = compute_training_configuration_checksum(
        dataset_fingerprint=manifest.dataset_fingerprint,
        model_spec_id=computed_model_spec_id,
        training_spec_id=computed_training_spec_id,
    )

    trained_experiment, training_config = begin_training_atomically(
        experiment_id=experiment.experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=experiment.state_version,
        model_spec=model_spec, training_spec=training_spec,
        model_spec_id=computed_model_spec_id, training_spec_id=computed_training_spec_id,
        training_configuration_checksum=checksum, dataset_fingerprint=manifest.dataset_fingerprint,
    )

    return VisualExperimentTrainingResult(experiment=trained_experiment, training_config=training_config)
