from dataclasses import dataclass
from hashlib import sha256
import json

from backend.app.analysis.visual_baseline_trainer import (
    BaselineModelArtifact,
    ValidationMetrics,
    ValidationPrediction,
    compute_validation_metrics,
)
from backend.app.analysis.visual_training_input import TrainingInputSample


EVALUATION_VERSION = "1.0.0"

EVALUATED = "evaluated"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
OUT_OF_DISTRIBUTION = "out_of_distribution"
VALID_OUTCOMES = frozenset({EVALUATED, INSUFFICIENT_EVIDENCE, OUT_OF_DISTRIBUTION})

# v1 sanity thresholds -- like MINIMUM_TRAIN_SAMPLES in visual_experiment_training.py,
# these are engineering floors to catch degenerate cases fail-closed, not
# statistically tuned values. Revisiting them is a separate, later decision.
MINIMUM_HOLDOUT_SAMPLES = 3
OOD_DISTANCE_MULTIPLIER = 3.0
OOD_DISTANCE_FLOOR = 0.01


@dataclass(frozen=True)
class EvaluationArtifact:
    """The Phase 5 `training -> evaluated` step's record of what was
    measured: which model this evaluates, HOLDOUT performance (the first
    and only place holdout data is used -- deliberately deferred from the
    baseline trainer), a naive majority-class comparator to sanity-check
    the model actually learned something, and an out-of-distribution check
    comparing holdout's nearest-centroid distances against validation's.
    `outcome` records which of the three possible lifecycle destinations
    this evaluation led to; it is NOT itself an accept/reject verdict on
    model quality -- that is a separate, later step.
    """

    model_checksum: str
    version: str
    holdout_sample_count: int
    holdout_metrics: ValidationMetrics
    majority_baseline_accuracy: float
    improvement_over_baseline: float
    validation_mean_min_distance: float
    holdout_mean_min_distance: float
    is_out_of_distribution: bool
    outcome: str
    checksum: str


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def compute_majority_baseline_accuracy(
    model: BaselineModelArtifact, holdout_samples: tuple[TrainingInputSample, ...],
) -> float:
    """A naive "always predict the most common TRAIN class" comparator --
    the sanity floor a real model should beat. Ties in `train_class_counts`
    break toward the smaller class index, since that tuple is already built
    in class-index order by `fit_baseline_model`, making `max()`'s
    first-occurrence tie-break deterministic.
    """
    if not holdout_samples:
        return 0.0
    index_by_label = {label: index for label, index in model.class_mapping}
    majority_label = max(model.train_class_counts, key=lambda item: item[1])[0]
    majority_index = index_by_label[majority_label]
    correct = sum(1 for sample in holdout_samples if sample.class_index == majority_index)
    return correct / len(holdout_samples)


def _mean_min_distance(predictions: tuple[ValidationPrediction, ...]) -> float:
    if not predictions:
        return 0.0
    return sum(min(prediction.distances) for prediction in predictions) / len(predictions)


def detect_out_of_distribution(
    validation_predictions: tuple[ValidationPrediction, ...],
    holdout_predictions: tuple[ValidationPrediction, ...],
    *,
    distance_multiplier: float = OOD_DISTANCE_MULTIPLIER,
    distance_floor: float = OOD_DISTANCE_FLOOR,
) -> tuple[bool, float, float]:
    """Flags holdout as out-of-distribution when its samples sit, on
    average, much farther from their nearest centroid than validation
    samples did. `distance_floor` keeps a near-zero validation distance
    (e.g. every validation sample landing exactly on a centroid) from
    making an OOD threshold of effectively zero.
    """
    validation_mean = _mean_min_distance(validation_predictions)
    holdout_mean = _mean_min_distance(holdout_predictions)
    threshold = distance_multiplier * max(validation_mean, distance_floor)
    return holdout_mean > threshold, validation_mean, holdout_mean


def _evaluation_payload(
    *,
    model_checksum: str,
    version: str,
    holdout_sample_count: int,
    holdout_metrics: ValidationMetrics,
    majority_baseline_accuracy: float,
    improvement_over_baseline: float,
    validation_mean_min_distance: float,
    holdout_mean_min_distance: float,
    is_out_of_distribution: bool,
    outcome: str,
) -> dict:
    return {
        "holdout_mean_min_distance": holdout_mean_min_distance,
        "holdout_metrics": {
            "accuracy": holdout_metrics.accuracy,
            "correct_count": holdout_metrics.correct_count,
            "mean_score": holdout_metrics.mean_score,
            "predicted_class_counts": [list(item) for item in holdout_metrics.predicted_class_counts],
            "sample_count": holdout_metrics.sample_count,
        },
        "holdout_sample_count": holdout_sample_count,
        "improvement_over_baseline": improvement_over_baseline,
        "is_out_of_distribution": is_out_of_distribution,
        "majority_baseline_accuracy": majority_baseline_accuracy,
        "model_checksum": model_checksum,
        "outcome": outcome,
        "validation_mean_min_distance": validation_mean_min_distance,
        "version": version,
    }


def evaluation_artifact_bytes(evaluation: EvaluationArtifact) -> bytes:
    payload = _evaluation_payload(
        model_checksum=evaluation.model_checksum, version=evaluation.version,
        holdout_sample_count=evaluation.holdout_sample_count, holdout_metrics=evaluation.holdout_metrics,
        majority_baseline_accuracy=evaluation.majority_baseline_accuracy,
        improvement_over_baseline=evaluation.improvement_over_baseline,
        validation_mean_min_distance=evaluation.validation_mean_min_distance,
        holdout_mean_min_distance=evaluation.holdout_mean_min_distance,
        is_out_of_distribution=evaluation.is_out_of_distribution, outcome=evaluation.outcome,
    )
    return _canonical_json(payload)


def build_evaluation_artifact(
    *,
    model: BaselineModelArtifact,
    holdout_samples: tuple[TrainingInputSample, ...],
    validation_predictions: tuple[ValidationPrediction, ...],
    holdout_predictions: tuple[ValidationPrediction, ...],
) -> EvaluationArtifact:
    """Evaluates a trained baseline model against HOLDOUT -- the first and
    only place in the Phase 5 pipeline holdout data is actually used,
    deliberately deferred from the trainer step. Always computes every
    metric (even when about to abstain) so the artifact is fully
    informative regardless of outcome; `outcome` records which gate fired:

    - too few holdout samples -> `insufficient_evidence` (abstain -- not
      enough evidence to trust ANY conclusion, checked first even if the
      OOD check would also have fired);
    - holdout sits far outside the distribution validation showed ->
      `out_of_distribution` (the evaluation itself is not trustworthy);
    - otherwise -> `evaluated`. This does NOT judge whether the model is
      good enough to use -- that accept/reject verdict is a separate,
      later step; `evaluated` here just means "the evaluation completed
      validly".
    """
    holdout_metrics = compute_validation_metrics(holdout_predictions)
    majority_baseline_accuracy = compute_majority_baseline_accuracy(model, holdout_samples)
    is_out_of_distribution, validation_mean_min_distance, holdout_mean_min_distance = (
        detect_out_of_distribution(validation_predictions, holdout_predictions)
    )

    if len(holdout_samples) < MINIMUM_HOLDOUT_SAMPLES:
        outcome = INSUFFICIENT_EVIDENCE
    elif is_out_of_distribution:
        outcome = OUT_OF_DISTRIBUTION
    else:
        outcome = EVALUATED

    payload = _evaluation_payload(
        model_checksum=model.checksum, version=EVALUATION_VERSION,
        holdout_sample_count=len(holdout_samples), holdout_metrics=holdout_metrics,
        majority_baseline_accuracy=majority_baseline_accuracy,
        improvement_over_baseline=holdout_metrics.accuracy - majority_baseline_accuracy,
        validation_mean_min_distance=validation_mean_min_distance,
        holdout_mean_min_distance=holdout_mean_min_distance,
        is_out_of_distribution=is_out_of_distribution, outcome=outcome,
    )
    checksum = f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"

    return EvaluationArtifact(
        model_checksum=model.checksum, version=EVALUATION_VERSION,
        holdout_sample_count=len(holdout_samples), holdout_metrics=holdout_metrics,
        majority_baseline_accuracy=majority_baseline_accuracy,
        improvement_over_baseline=holdout_metrics.accuracy - majority_baseline_accuracy,
        validation_mean_min_distance=validation_mean_min_distance,
        holdout_mean_min_distance=holdout_mean_min_distance,
        is_out_of_distribution=is_out_of_distribution, outcome=outcome, checksum=checksum,
    )
