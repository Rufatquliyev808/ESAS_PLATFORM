import hashlib

import pytest

from backend.app.analysis.visual_baseline_trainer import (
    BASELINE_ARCHITECTURE_ID,
    BaselineTrainerError,
    baseline_model_artifact_bytes,
    build_training_log,
    compute_validation_metrics,
    fit_baseline_model,
    predict_validation,
    training_log_artifact_bytes,
)
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.analysis.visual_training_input import (
    LabeledImage,
    TrainingInputBatch,
    apply_preprocessing,
    fit_preprocessing_state,
)


WIDTH, HEIGHT, CHANNELS = 1, 1, 3

BASELINE_MODEL_SPEC = ModelSpec(
    architecture_id=BASELINE_ARCHITECTURE_ID, preprocessing_policy="normalize_0_1",
    class_weight_policy="none",
)
WRONG_ARCHITECTURE_MODEL_SPEC = ModelSpec(
    architecture_id="some_other_architecture", preprocessing_policy="normalize_0_1",
    class_weight_policy="none",
)
DEFAULT_TRAINING_SPEC = TrainingSpec(
    seed=1, optimizer="adam", loss="cross_entropy", batch_size=2, max_epochs=1, compute_requirement="cpu",
)
DATASET_FINGERPRINT = "sha256:dataset-a"


def _image(sample_id: str, *, fill: int, label: str) -> LabeledImage:
    return LabeledImage(sample_id=sample_id, pixels=bytes([fill, fill, fill]), label_value=label)


TRAIN_IMAGES = (
    _image("up1", fill=0, label="up"),
    _image("up2", fill=10, label="up"),
    _image("down1", fill=245, label="down"),
    _image("down2", fill=255, label="down"),
    _image("flat1", fill=120, label="flat"),
    _image("flat2", fill=130, label="flat"),
)


def _batches_from_images(images) -> tuple[TrainingInputBatch, ...]:
    state = fit_preprocessing_state(
        images, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    samples = tuple(apply_preprocessing(image, state) for image in images)
    return state, (TrainingInputBatch(batch_index=0, samples=samples),)


def test_fit_baseline_model_rejects_wrong_architecture() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    with pytest.raises(BaselineTrainerError):
        fit_baseline_model(
            batches, preprocessing_state=state, model_spec=WRONG_ARCHITECTURE_MODEL_SPEC,
            training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
        )


def test_fit_baseline_model_rejects_labels_outside_frozen_scheme() -> None:
    images = TRAIN_IMAGES + (_image("sideways1", fill=50, label="sideways"),)
    state, batches = _batches_from_images(images)
    with pytest.raises(BaselineTrainerError):
        fit_baseline_model(
            batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
            training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
        )


def test_fit_baseline_model_computes_correct_centroids() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    label_by_index = dict((index, label) for label, index in state.class_mapping)
    centroid_by_label = {
        label_by_index[index]: model.centroids[index] for index in range(len(model.centroids))
    }
    # channel_min=0 (from "up1"), channel_max=255 (from "down2") -> normalized = value/255
    assert centroid_by_label["up"] == pytest.approx((5 / 255,) * 3)
    assert centroid_by_label["down"] == pytest.approx((250 / 255,) * 3)
    assert centroid_by_label["flat"] == pytest.approx((125 / 255,) * 3)


def test_fit_baseline_model_records_correct_train_class_counts() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    counts = dict(model.train_class_counts)
    assert counts == {"up": 2, "down": 2, "flat": 2}


def test_fit_baseline_model_is_deterministic_regardless_of_batch_layout() -> None:
    state, batches_a = _batches_from_images(TRAIN_IMAGES)
    # Same samples, different batching/order.
    all_samples = batches_a[0].samples
    reordered = tuple(reversed(all_samples))
    batches_b = (
        TrainingInputBatch(batch_index=0, samples=reordered[:3]),
        TrainingInputBatch(batch_index=1, samples=reordered[3:]),
    )
    model_a = fit_baseline_model(
        batches_a, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    model_b = fit_baseline_model(
        batches_b, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    assert model_a == model_b
    assert model_a.checksum == model_b.checksum


def test_fit_baseline_model_rejects_zero_train_samples() -> None:
    state, _ = _batches_from_images(TRAIN_IMAGES)
    with pytest.raises(BaselineTrainerError):
        fit_baseline_model(
            (), preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
            training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
        )


def test_baseline_model_artifact_bytes_hash_matches_checksum() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    artifact_bytes = baseline_model_artifact_bytes(model)
    assert f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}" == model.checksum


def test_predict_validation_classifies_toward_nearest_centroid() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    validation_image = _image("val_near_up", fill=5, label="up")
    validation_sample = apply_preprocessing(validation_image, state)
    predictions = predict_validation((validation_sample,), model)

    label_by_index = dict((index, label) for label, index in state.class_mapping)
    assert len(predictions) == 1
    predicted_label = label_by_index[predictions[0].predicted_class_index]
    assert predicted_label == "up"
    assert predictions[0].true_class_index == predictions[0].predicted_class_index
    assert 0.0 < predictions[0].score <= 1.0
    assert len(predictions[0].distances) == len(model.centroids)


def test_predict_validation_never_mutates_model() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    before_checksum = model.checksum
    validation_image = _image("val1", fill=200, label="down")
    validation_sample = apply_preprocessing(validation_image, state)
    predict_validation((validation_sample,), model)
    assert model.checksum == before_checksum


def test_compute_validation_metrics_accuracy() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    validation_samples = tuple(
        apply_preprocessing(image, state)
        for image in (
            _image("val_up", fill=5, label="up"),
            _image("val_down", fill=250, label="down"),
            _image("val_mislabeled", fill=5, label="down"),  # near "up" pixels but labeled "down"
        )
    )
    predictions = predict_validation(validation_samples, model)
    metrics = compute_validation_metrics(predictions)
    assert metrics.sample_count == 3
    assert metrics.correct_count == 2
    assert metrics.accuracy == pytest.approx(2 / 3)
    assert 0.0 < metrics.mean_score <= 1.0


def test_compute_validation_metrics_handles_empty_predictions() -> None:
    metrics = compute_validation_metrics(())
    assert metrics.sample_count == 0
    assert metrics.accuracy == 0.0


def test_build_training_log_checksum_matches_artifact_bytes() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    validation_sample = apply_preprocessing(_image("val1", fill=5, label="up"), state)
    predictions = predict_validation((validation_sample,), model)
    metrics = compute_validation_metrics(predictions)
    log = build_training_log(
        model=model, validation_metrics=metrics, train_sample_count=6,
        validation_sample_count=1, duration_seconds=0.001234,
    )
    artifact_bytes = training_log_artifact_bytes(log)
    assert f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}" == log.checksum
    assert log.operation == "single_pass_centroid_fit"


def test_build_training_log_checksum_differs_for_different_duration() -> None:
    state, batches = _batches_from_images(TRAIN_IMAGES)
    model = fit_baseline_model(
        batches, preprocessing_state=state, model_spec=BASELINE_MODEL_SPEC,
        training_spec=DEFAULT_TRAINING_SPEC, dataset_fingerprint=DATASET_FINGERPRINT,
    )
    metrics = compute_validation_metrics(())
    log_a = build_training_log(
        model=model, validation_metrics=metrics, train_sample_count=6,
        validation_sample_count=0, duration_seconds=0.1,
    )
    log_b = build_training_log(
        model=model, validation_metrics=metrics, train_sample_count=6,
        validation_sample_count=0, duration_seconds=0.2,
    )
    assert log_a.checksum != log_b.checksum
