from dataclasses import dataclass
from hashlib import sha256
import json

from backend.app.analysis.visual_label import DOWN, FLAT, UP
from backend.app.analysis.visual_model_spec import (
    ModelSpec,
    TrainingSpec,
    model_spec_id as compute_model_spec_id,
    training_spec_id as compute_training_spec_id,
)
from backend.app.analysis.visual_training_input import PreprocessingState, TrainingInputBatch, TrainingInputSample


BASELINE_ARCHITECTURE_ID = "pixel_centroid_baseline_v1"
BASELINE_TRAINER_VERSION = "1.0.0"
SINGLE_PASS_CENTROID_FIT = "single_pass_centroid_fit"
FROZEN_LABELS = frozenset({UP, DOWN, FLAT})


class BaselineTrainerError(ValueError):
    pass


@dataclass(frozen=True)
class BaselineModelArtifact:
    """Everything a later step needs to reproduce or audit this exact
    model: which architecture/version produced it, which dataset and
    preprocessing state it was fit from, which frozen spec ids it used, the
    frozen class mapping, the per-class centroids themselves, how many
    train samples went into each class, and a checksum tying it all
    together. Deliberately carries no reference to validation or holdout
    data -- nothing here could have come from anywhere but train.
    """

    architecture_id: str
    version: str
    dataset_fingerprint: str
    preprocessing_checksum: str
    model_spec_id: str
    training_spec_id: str
    class_mapping: tuple[tuple[str, int], ...]
    centroids: tuple[tuple[float, ...], ...]
    train_class_counts: tuple[tuple[str, int], ...]
    checksum: str


@dataclass(frozen=True)
class ValidationPrediction:
    sample_id: str
    true_class_index: int
    predicted_class_index: int
    distances: tuple[float, ...]
    score: float


@dataclass(frozen=True)
class ValidationMetrics:
    sample_count: int
    correct_count: int
    accuracy: float
    mean_score: float
    predicted_class_counts: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class TrainingLogArtifact:
    operation: str
    architecture_id: str
    version: str
    train_sample_count: int
    validation_sample_count: int
    duration_seconds: float
    validation_metrics: ValidationMetrics
    checksum: str


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _model_payload(
    *,
    architecture_id: str,
    version: str,
    dataset_fingerprint: str,
    preprocessing_checksum: str,
    model_spec_id_value: str,
    training_spec_id_value: str,
    class_mapping: tuple[tuple[str, int], ...],
    centroids: tuple[tuple[float, ...], ...],
    train_class_counts: tuple[tuple[str, int], ...],
) -> dict:
    return {
        "architecture_id": architecture_id,
        "centroids": [list(centroid) for centroid in centroids],
        "class_mapping": [list(item) for item in class_mapping],
        "dataset_fingerprint": dataset_fingerprint,
        "model_spec_id": model_spec_id_value,
        "preprocessing_checksum": preprocessing_checksum,
        "train_class_counts": [list(item) for item in train_class_counts],
        "training_spec_id": training_spec_id_value,
        "version": version,
    }


def baseline_model_artifact_bytes(model: BaselineModelArtifact) -> bytes:
    """The exact bytes `model.checksum` is a sha256 over -- what gets
    written to the content-addressed artifact store for this model.
    """
    payload = _model_payload(
        architecture_id=model.architecture_id, version=model.version,
        dataset_fingerprint=model.dataset_fingerprint, preprocessing_checksum=model.preprocessing_checksum,
        model_spec_id_value=model.model_spec_id, training_spec_id_value=model.training_spec_id,
        class_mapping=model.class_mapping, centroids=model.centroids,
        train_class_counts=model.train_class_counts,
    )
    return _canonical_json(payload)


def fit_baseline_model(
    train_batches: tuple[TrainingInputBatch, ...],
    *,
    preprocessing_state: PreprocessingState,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
    dataset_fingerprint: str,
) -> BaselineModelArtifact:
    """Fits `pixel_centroid_baseline_v1`: one centroid per class, each the
    elementwise mean of every TRAIN sample's normalized pixel vector in
    that class. There is no `validation_samples`/`holdout_samples`
    parameter anywhere in this function -- separation by construction, not
    a runtime check.

    Deterministic: for each class, samples are summed in a FIXED order
    (sorted by `sample_id`) rather than whatever order `train_batches`
    happens to arrive in (batch order depends on the seeded shuffle, which
    must not affect the fitted weights). The same train data always
    produces bit-identical centroids and therefore the same checksum.
    """
    if model_spec.architecture_id != BASELINE_ARCHITECTURE_ID:
        raise BaselineTrainerError(
            f"model_spec.architecture_id must be {BASELINE_ARCHITECTURE_ID!r} for this trainer, "
            f"got {model_spec.architecture_id!r}"
        )
    unknown_labels = sorted(
        {label for label, _ in preprocessing_state.class_mapping} - FROZEN_LABELS
    )
    if unknown_labels:
        raise BaselineTrainerError(
            f"class labels outside the frozen up/down/flat scheme: {unknown_labels}"
        )

    samples: list[TrainingInputSample] = [sample for batch in train_batches for sample in batch.samples]
    if not samples:
        raise BaselineTrainerError("cannot fit a baseline model from zero train samples")
    dimensions = len(samples[0].normalized_pixels)

    by_class: dict[int, list[TrainingInputSample]] = {}
    for sample in samples:
        by_class.setdefault(sample.class_index, []).append(sample)
    label_by_index = {index: label for label, index in preprocessing_state.class_mapping}

    centroids: list[tuple[float, ...]] = []
    class_counts: list[tuple[str, int]] = []
    for class_index in range(len(preprocessing_state.class_mapping)):
        label = label_by_index[class_index]
        class_samples = sorted(by_class.get(class_index, ()), key=lambda sample: sample.sample_id)
        class_counts.append((label, len(class_samples)))
        if not class_samples:
            raise BaselineTrainerError(f"train split has zero samples for class {label!r}")

        sums = [0.0] * dimensions
        for sample in class_samples:
            for dimension, value in enumerate(sample.normalized_pixels):
                sums[dimension] += value
        centroids.append(tuple(value / len(class_samples) for value in sums))

    model_spec_id_value = compute_model_spec_id(model_spec)
    training_spec_id_value = compute_training_spec_id(training_spec)
    payload = _model_payload(
        architecture_id=BASELINE_ARCHITECTURE_ID, version=BASELINE_TRAINER_VERSION,
        dataset_fingerprint=dataset_fingerprint, preprocessing_checksum=preprocessing_state.checksum,
        model_spec_id_value=model_spec_id_value, training_spec_id_value=training_spec_id_value,
        class_mapping=preprocessing_state.class_mapping, centroids=tuple(centroids),
        train_class_counts=tuple(class_counts),
    )
    checksum = f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"

    return BaselineModelArtifact(
        architecture_id=BASELINE_ARCHITECTURE_ID, version=BASELINE_TRAINER_VERSION,
        dataset_fingerprint=dataset_fingerprint, preprocessing_checksum=preprocessing_state.checksum,
        model_spec_id=model_spec_id_value, training_spec_id=training_spec_id_value,
        class_mapping=preprocessing_state.class_mapping, centroids=tuple(centroids),
        train_class_counts=tuple(class_counts), checksum=checksum,
    )


def _squared_distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def predict_validation(
    validation_samples: tuple[TrainingInputSample, ...], model: BaselineModelArtifact,
) -> tuple[ValidationPrediction, ...]:
    """Nearest-centroid classification for VALIDATION samples against an
    already-fit model -- never touches `train_batches` or refits anything.
    Distances are computed in the fixed pixel-vector dimension order every
    sample already has (row-major R,G,B from `apply_preprocessing`), and
    the argmin loop breaks ties toward the smaller class index, so the same
    inputs always produce the same predictions and scores.
    """
    predictions = []
    for sample in validation_samples:
        distances = tuple(
            _squared_distance(sample.normalized_pixels, centroid) for centroid in model.centroids
        )
        predicted_index = 0
        best_distance = distances[0]
        for index in range(1, len(distances)):
            if distances[index] < best_distance:
                best_distance = distances[index]
                predicted_index = index
        score = 1.0 / (1.0 + best_distance)
        predictions.append(
            ValidationPrediction(
                sample_id=sample.sample_id, true_class_index=sample.class_index,
                predicted_class_index=predicted_index, distances=distances, score=score,
            )
        )
    return tuple(predictions)


def compute_validation_metrics(predictions: tuple[ValidationPrediction, ...]) -> ValidationMetrics:
    if not predictions:
        return ValidationMetrics(
            sample_count=0, correct_count=0, accuracy=0.0, mean_score=0.0, predicted_class_counts=(),
        )
    correct_count = sum(
        1 for prediction in predictions if prediction.predicted_class_index == prediction.true_class_index
    )
    mean_score = sum(prediction.score for prediction in predictions) / len(predictions)
    counts: dict[int, int] = {}
    for prediction in predictions:
        counts[prediction.predicted_class_index] = counts.get(prediction.predicted_class_index, 0) + 1
    return ValidationMetrics(
        sample_count=len(predictions), correct_count=correct_count,
        accuracy=correct_count / len(predictions), mean_score=mean_score,
        predicted_class_counts=tuple(sorted(counts.items())),
    )


def _log_payload(
    *,
    operation: str,
    architecture_id: str,
    version: str,
    train_sample_count: int,
    validation_sample_count: int,
    duration_seconds: float,
    validation_metrics: ValidationMetrics,
) -> dict:
    return {
        "architecture_id": architecture_id,
        "duration_seconds": duration_seconds,
        "operation": operation,
        "train_sample_count": train_sample_count,
        "validation_metrics": {
            "accuracy": validation_metrics.accuracy,
            "correct_count": validation_metrics.correct_count,
            "mean_score": validation_metrics.mean_score,
            "predicted_class_counts": [list(item) for item in validation_metrics.predicted_class_counts],
            "sample_count": validation_metrics.sample_count,
        },
        "validation_sample_count": validation_sample_count,
        "version": version,
    }


def training_log_artifact_bytes(log: TrainingLogArtifact) -> bytes:
    payload = _log_payload(
        operation=log.operation, architecture_id=log.architecture_id, version=log.version,
        train_sample_count=log.train_sample_count, validation_sample_count=log.validation_sample_count,
        duration_seconds=log.duration_seconds, validation_metrics=log.validation_metrics,
    )
    return _canonical_json(payload)


def build_training_log(
    *,
    model: BaselineModelArtifact,
    validation_metrics: ValidationMetrics,
    train_sample_count: int,
    validation_sample_count: int,
    duration_seconds: float,
) -> TrainingLogArtifact:
    """Records the single-pass baseline fit+score operation, resource usage
    (wall-clock duration, sample counts), and validation metrics -- there is
    no epoch loop to log, this architecture fits in one pass. Unlike the
    model artifact, this log's own checksum is NOT expected to be identical
    across runs (`duration_seconds` genuinely varies run to run); only the
    model artifact and the validation predictions/metrics it is built from
    are required to be reproducible.
    """
    payload = _log_payload(
        operation=SINGLE_PASS_CENTROID_FIT, architecture_id=model.architecture_id, version=model.version,
        train_sample_count=train_sample_count, validation_sample_count=validation_sample_count,
        duration_seconds=duration_seconds, validation_metrics=validation_metrics,
    )
    checksum = f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"
    return TrainingLogArtifact(
        operation=SINGLE_PASS_CENTROID_FIT, architecture_id=model.architecture_id, version=model.version,
        train_sample_count=train_sample_count, validation_sample_count=validation_sample_count,
        duration_seconds=duration_seconds, validation_metrics=validation_metrics, checksum=checksum,
    )
