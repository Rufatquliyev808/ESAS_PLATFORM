from dataclasses import dataclass
from hashlib import sha256

from backend.app.analysis.visual_dataset import HOLDOUT, TRAIN, VALIDATION
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.analysis.visual_render import CHANNELS, PngDecodeError, decode_canonical_png
from backend.app.analysis.visual_training_input import (
    LabeledImage,
    PreprocessingState,
    TrainingInputBatch,
    TrainingInputSample,
    apply_preprocessing,
    build_deterministic_batches,
    fit_preprocessing_state,
    preprocessing_state_artifact_bytes,
)
from backend.app.database.visual_dataset_repository import list_dataset_samples
from backend.app.database.visual_experiment_repository import VisualExperimentOwnershipError, get_visual_experiment
from backend.app.storage.artifact_store import ArtifactIntegrityError, ArtifactNotFoundError, get_artifact, put_artifact


PNG_ARTIFACT_EXTENSION = "png"
PREPROCESSING_ARTIFACT_EXTENSION = "json"


class VisualTrainingInputError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualTrainingInputResult:
    preprocessing_state: PreprocessingState
    train_batches: tuple[TrainingInputBatch, ...]
    validation_samples: tuple[TrainingInputSample, ...]
    holdout_samples: tuple[TrainingInputSample, ...]


def _load_split_images(
    experiment_id: str, split_id: str, *, width: int, height: int, channels: int,
) -> tuple[LabeledImage, ...]:
    """Reads persisted samples for one split, loads each PNG artifact with
    checksum verification, decodes it back to the raw pixel buffer, and
    re-verifies the decoded pixels against the persisted `image_checksum`
    -- fail-closed (never a best-effort skip) on any missing artifact,
    checksum mismatch, decode error, or unlabeled sample, matching the
    training-readiness gate's own defense-in-depth style rather than
    trusting that an earlier gate already checked this.
    """
    samples = tuple(
        sample for sample in list_dataset_samples(experiment_id) if sample.split_id == split_id
    )
    images: list[LabeledImage] = []
    for sample in samples:
        if sample.label_value is None:
            raise VisualTrainingInputError(
                f"sample {sample.sample_id} in split {split_id!r} has no label_value"
            )
        try:
            png_bytes = get_artifact(sample.artifact_checksum, extension=PNG_ARTIFACT_EXTENSION, verify=True)
        except ArtifactNotFoundError as error:
            raise VisualTrainingInputError(f"sample {sample.sample_id} artifact is missing on disk") from error
        except ArtifactIntegrityError as error:
            raise VisualTrainingInputError(
                f"sample {sample.sample_id} artifact failed checksum verification"
            ) from error
        try:
            pixels, decoded_width, decoded_height = decode_canonical_png(png_bytes)
        except PngDecodeError as error:
            raise VisualTrainingInputError(f"sample {sample.sample_id} PNG could not be decoded") from error
        if (decoded_width, decoded_height) != (width, height):
            raise VisualTrainingInputError(
                f"sample {sample.sample_id} image dimensions do not match the experiment's render spec"
            )
        if f"sha256:{sha256(pixels).hexdigest()}" != sample.image_checksum:
            raise VisualTrainingInputError(
                f"sample {sample.sample_id} decoded pixel checksum does not match its recorded image_checksum"
            )
        images.append(LabeledImage(sample_id=sample.sample_id, pixels=pixels, label_value=sample.label_value))
    return tuple(images)


def build_visual_training_input(
    experiment_id: str,
    *,
    actor: str,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
) -> VisualTrainingInputResult:
    """Phase 5 Deterministic training-input pipeline v1: reads an
    experiment's persisted, split-assigned dataset samples, loads and
    checksum-verifies their PNG artifacts, decodes them to fixed-size raw
    pixel buffers, fits per-channel normalization + class weights from
    TRAIN images only, applies that frozen state (unchanged) to
    validation/holdout, and produces a deterministic train batch order from
    `training_spec.seed`.

    `pending_horizon`/`purged_boundary_overlap` samples are never read here
    at all -- `_load_split_images` only ever queries `train`/`validation`/
    `holdout`, so those samples stay exactly as persisted in
    `visual_dataset_samples` (and therefore still counted in the dataset
    manifest) without ever entering training input.

    Holdout is separated from model selection and preprocessing fitting by
    CONSTRUCTION, not a runtime check: `fit_preprocessing_state()`'s
    signature only accepts train images, so there is no code path through
    which holdout (or validation) data could influence the fitted state.

    Performs no actual model training, adds no ML dependency, and does not
    touch the frontend or production database.
    """
    experiment = get_visual_experiment(experiment_id)
    if experiment.created_by != actor:
        raise VisualExperimentOwnershipError("visual experiment belongs to another user")

    width = experiment.render_spec["width"]
    height = experiment.render_spec["height"]

    train_images = _load_split_images(experiment_id, TRAIN, width=width, height=height, channels=CHANNELS)
    validation_images = _load_split_images(
        experiment_id, VALIDATION, width=width, height=height, channels=CHANNELS
    )
    holdout_images = _load_split_images(experiment_id, HOLDOUT, width=width, height=height, channels=CHANNELS)

    preprocessing_state = fit_preprocessing_state(
        train_images, width=width, height=height, channels=CHANNELS,
        class_weight_policy=model_spec.class_weight_policy,
    )

    train_samples = tuple(apply_preprocessing(image, preprocessing_state) for image in train_images)
    validation_samples = tuple(apply_preprocessing(image, preprocessing_state) for image in validation_images)
    holdout_samples = tuple(apply_preprocessing(image, preprocessing_state) for image in holdout_images)

    train_batches = build_deterministic_batches(
        train_samples, batch_size=training_spec.batch_size, seed=training_spec.seed,
    )

    artifact_bytes = preprocessing_state_artifact_bytes(preprocessing_state)
    put_artifact(preprocessing_state.checksum, artifact_bytes, extension=PREPROCESSING_ARTIFACT_EXTENSION)

    return VisualTrainingInputResult(
        preprocessing_state=preprocessing_state, train_batches=train_batches,
        validation_samples=validation_samples, holdout_samples=holdout_samples,
    )
