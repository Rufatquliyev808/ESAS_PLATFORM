import hashlib

from backend.app.analysis.visual_baseline_trainer import BaselineModelArtifact, ValidationPrediction
from backend.app.analysis.visual_evaluation import (
    EVALUATED,
    INSUFFICIENT_EVIDENCE,
    MINIMUM_HOLDOUT_SAMPLES,
    OUT_OF_DISTRIBUTION,
    build_evaluation_artifact,
    compute_majority_baseline_accuracy,
    detect_out_of_distribution,
    evaluation_artifact_bytes,
)
from backend.app.analysis.visual_training_input import TrainingInputSample


def _model(*, class_mapping, train_class_counts) -> BaselineModelArtifact:
    return BaselineModelArtifact(
        architecture_id="pixel_centroid_baseline_v1", version="1.0.0",
        dataset_fingerprint="sha256:dataset-a", preprocessing_checksum="sha256:preprocessing-a",
        model_spec_id="sha256:model-spec-a", training_spec_id="sha256:training-spec-a",
        class_mapping=class_mapping, centroids=((0.0,), (1.0,)),
        train_class_counts=train_class_counts, checksum="sha256:model-a",
    )


DEFAULT_MODEL = _model(
    class_mapping=(("down", 0), ("up", 1)), train_class_counts=(("down", 3), ("up", 7)),
)


def _sample(sample_id: str, *, class_index: int) -> TrainingInputSample:
    return TrainingInputSample(sample_id=sample_id, normalized_pixels=(0.0,), class_index=class_index)


def _prediction(sample_id: str, *, true_index: int, predicted_index: int, distances: tuple[float, ...]) -> ValidationPrediction:
    return ValidationPrediction(
        sample_id=sample_id, true_class_index=true_index, predicted_class_index=predicted_index,
        distances=distances, score=1.0 / (1.0 + min(distances)),
    )


def test_compute_majority_baseline_accuracy_predicts_majority_class() -> None:
    holdout_samples = (
        _sample("h1", class_index=1),  # up (majority)
        _sample("h2", class_index=1),  # up
        _sample("h3", class_index=0),  # down
    )
    accuracy = compute_majority_baseline_accuracy(DEFAULT_MODEL, holdout_samples)
    assert accuracy == 2 / 3  # majority class is "up" (7 > 3), correct for h1/h2


def test_compute_majority_baseline_accuracy_handles_empty_holdout() -> None:
    assert compute_majority_baseline_accuracy(DEFAULT_MODEL, ()) == 0.0


def test_compute_majority_baseline_accuracy_breaks_ties_toward_smaller_index() -> None:
    tied_model = _model(class_mapping=(("down", 0), ("up", 1)), train_class_counts=(("down", 5), ("up", 5)))
    holdout_samples = (_sample("h1", class_index=0),)
    # Tie -> smaller index (0, "down") wins -> majority baseline predicts "down" -> correct.
    assert compute_majority_baseline_accuracy(tied_model, holdout_samples) == 1.0


def test_detect_out_of_distribution_flags_when_holdout_much_farther() -> None:
    validation_predictions = (
        _prediction("v1", true_index=0, predicted_index=0, distances=(0.01, 0.5)),
        _prediction("v2", true_index=1, predicted_index=1, distances=(0.5, 0.02)),
    )
    holdout_predictions = (
        _prediction("h1", true_index=0, predicted_index=1, distances=(5.0, 5.0)),
    )
    is_ood, validation_mean, holdout_mean = detect_out_of_distribution(validation_predictions, holdout_predictions)
    assert is_ood is True
    assert validation_mean == (0.01 + 0.02) / 2
    assert holdout_mean == 5.0


def test_detect_out_of_distribution_does_not_flag_similar_distances() -> None:
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.1, 0.5)),)
    holdout_predictions = (_prediction("h1", true_index=0, predicted_index=0, distances=(0.12, 0.5)),)
    is_ood, _, _ = detect_out_of_distribution(validation_predictions, holdout_predictions)
    assert is_ood is False


def test_detect_out_of_distribution_uses_floor_when_validation_distance_near_zero() -> None:
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.0, 1.0)),)
    # Small holdout distance should NOT be flagged just because validation was ~0.
    holdout_predictions = (_prediction("h1", true_index=0, predicted_index=0, distances=(0.02, 1.0)),)
    is_ood, _, _ = detect_out_of_distribution(validation_predictions, holdout_predictions)
    assert is_ood is False


def _predictions_for(samples: tuple[TrainingInputSample, ...], *, distance: float) -> tuple[ValidationPrediction, ...]:
    return tuple(
        _prediction(sample.sample_id, true_index=sample.class_index, predicted_index=sample.class_index, distances=(distance, distance))
        for sample in samples
    )


def test_build_evaluation_artifact_outcome_evaluated_on_normal_holdout() -> None:
    holdout_samples = (
        _sample("h1", class_index=1), _sample("h2", class_index=0), _sample("h3", class_index=1),
    )
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.1, 0.5)),)
    holdout_predictions = _predictions_for(holdout_samples, distance=0.1)
    evaluation = build_evaluation_artifact(
        model=DEFAULT_MODEL, holdout_samples=holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    assert evaluation.outcome == EVALUATED
    assert evaluation.holdout_sample_count == 3


def test_build_evaluation_artifact_outcome_insufficient_evidence_below_minimum() -> None:
    assert MINIMUM_HOLDOUT_SAMPLES >= 1
    holdout_samples = tuple(
        _sample(f"h{i}", class_index=0) for i in range(MINIMUM_HOLDOUT_SAMPLES - 1)
    )
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.1, 0.5)),)
    holdout_predictions = _predictions_for(holdout_samples, distance=0.1)
    evaluation = build_evaluation_artifact(
        model=DEFAULT_MODEL, holdout_samples=holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    assert evaluation.outcome == INSUFFICIENT_EVIDENCE


def test_build_evaluation_artifact_outcome_out_of_distribution() -> None:
    holdout_samples = tuple(_sample(f"h{i}", class_index=0) for i in range(MINIMUM_HOLDOUT_SAMPLES))
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.01, 0.5)),)
    holdout_predictions = _predictions_for(holdout_samples, distance=50.0)
    evaluation = build_evaluation_artifact(
        model=DEFAULT_MODEL, holdout_samples=holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    assert evaluation.outcome == OUT_OF_DISTRIBUTION
    assert evaluation.is_out_of_distribution is True


def test_build_evaluation_artifact_prioritizes_insufficient_evidence_over_ood() -> None:
    # Fewer than the minimum AND far-away distances -- insufficient_evidence wins.
    holdout_samples = tuple(_sample(f"h{i}", class_index=0) for i in range(MINIMUM_HOLDOUT_SAMPLES - 1))
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.01, 0.5)),)
    holdout_predictions = _predictions_for(holdout_samples, distance=50.0)
    evaluation = build_evaluation_artifact(
        model=DEFAULT_MODEL, holdout_samples=holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    assert evaluation.outcome == INSUFFICIENT_EVIDENCE


def test_evaluation_artifact_bytes_hash_matches_checksum() -> None:
    holdout_samples = tuple(_sample(f"h{i}", class_index=1) for i in range(MINIMUM_HOLDOUT_SAMPLES))
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.1, 0.5)),)
    holdout_predictions = _predictions_for(holdout_samples, distance=0.1)
    evaluation = build_evaluation_artifact(
        model=DEFAULT_MODEL, holdout_samples=holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    artifact_bytes = evaluation_artifact_bytes(evaluation)
    assert f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}" == evaluation.checksum


def test_build_evaluation_artifact_is_deterministic_for_same_inputs() -> None:
    holdout_samples = tuple(_sample(f"h{i}", class_index=1) for i in range(MINIMUM_HOLDOUT_SAMPLES))
    validation_predictions = (_prediction("v1", true_index=0, predicted_index=0, distances=(0.1, 0.5)),)
    holdout_predictions = _predictions_for(holdout_samples, distance=0.1)
    first = build_evaluation_artifact(
        model=DEFAULT_MODEL, holdout_samples=holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    second = build_evaluation_artifact(
        model=DEFAULT_MODEL, holdout_samples=holdout_samples,
        validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
    )
    assert first == second
    assert first.checksum == second.checksum
