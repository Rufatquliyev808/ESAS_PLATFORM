import pytest

from backend.app.analysis.visual_training_input import (
    LabeledImage,
    PreprocessingFitError,
    apply_preprocessing,
    build_deterministic_batches,
    fit_preprocessing_state,
    preprocessing_state_artifact_bytes,
)


WIDTH, HEIGHT, CHANNELS = 2, 2, 3


def _pixels(fill: int) -> bytes:
    return bytes([fill]) * (WIDTH * HEIGHT * CHANNELS)


def _image(sample_id: str, *, fill: int, label: str) -> LabeledImage:
    return LabeledImage(sample_id=sample_id, pixels=_pixels(fill), label_value=label)


TRAIN_IMAGES = (
    _image("s1", fill=0, label="up"),
    _image("s2", fill=255, label="down"),
    _image("s3", fill=64, label="up"),
    _image("s4", fill=192, label="down"),
)


def test_fit_preprocessing_state_is_deterministic_regardless_of_input_order() -> None:
    reversed_images = tuple(reversed(TRAIN_IMAGES))
    state_a = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    state_b = fit_preprocessing_state(
        reversed_images, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    assert state_a == state_b
    assert state_a.checksum == state_b.checksum


def test_fit_preprocessing_state_computes_correct_channel_bounds() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    assert state.channel_min == (0, 0, 0)
    assert state.channel_max == (255, 255, 255)


def test_fit_preprocessing_state_class_mapping_is_sorted() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    assert state.class_mapping == (("down", 0), ("up", 1))


def test_fit_preprocessing_state_rejects_empty_train_images() -> None:
    with pytest.raises(PreprocessingFitError):
        fit_preprocessing_state((), width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none")


def test_fit_preprocessing_state_rejects_wrong_pixel_length() -> None:
    bad_image = LabeledImage(sample_id="bad", pixels=bytes([1, 2, 3]), label_value="up")
    with pytest.raises(PreprocessingFitError):
        fit_preprocessing_state(
            (bad_image,), width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
        )


def test_fit_preprocessing_state_rejects_unknown_class_weight_policy() -> None:
    with pytest.raises(PreprocessingFitError):
        fit_preprocessing_state(
            TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="made_up",
        )


def test_class_weights_balanced_policy_weighs_rarer_classes_higher() -> None:
    images = (
        _image("s1", fill=0, label="up"),
        _image("s2", fill=1, label="up"),
        _image("s3", fill=2, label="up"),
        _image("s4", fill=3, label="down"),
    )
    state = fit_preprocessing_state(
        images, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="balanced",
    )
    weights = dict(state.class_weights)
    assert weights["down"] > weights["up"]


def test_class_weights_none_policy_is_uniform() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    weights = dict(state.class_weights)
    assert all(weight == 1.0 for weight in weights.values())


def test_apply_preprocessing_normalizes_into_zero_one_range() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    sample = apply_preprocessing(TRAIN_IMAGES[0], state)
    assert all(0.0 <= value <= 1.0 for value in sample.normalized_pixels)
    assert sample.normalized_pixels == (0.0,) * (WIDTH * HEIGHT * CHANNELS)


def test_apply_preprocessing_never_refits_state() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    out_of_range_image = _image("val1", fill=255, label="up")
    apply_preprocessing(out_of_range_image, state)  # must not raise or mutate state
    assert state.channel_min == (0, 0, 0)
    assert state.channel_max == (255, 255, 255)


def test_apply_preprocessing_rejects_unseen_label() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    unseen_label_image = _image("val1", fill=0, label="flat")
    with pytest.raises(PreprocessingFitError):
        apply_preprocessing(unseen_label_image, state)


def test_apply_preprocessing_rejects_wrong_dimensions() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    wrong_size_image = LabeledImage(sample_id="bad", pixels=bytes([1, 2, 3]), label_value="up")
    with pytest.raises(PreprocessingFitError):
        apply_preprocessing(wrong_size_image, state)


def test_preprocessing_state_artifact_bytes_hash_matches_checksum() -> None:
    import hashlib

    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    artifact_bytes = preprocessing_state_artifact_bytes(state)
    assert f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}" == state.checksum


def test_build_deterministic_batches_is_reproducible_for_same_seed() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    samples = tuple(apply_preprocessing(image, state) for image in TRAIN_IMAGES)
    batches_a = build_deterministic_batches(samples, batch_size=2, seed=7)
    batches_b = build_deterministic_batches(samples, batch_size=2, seed=7)
    assert batches_a == batches_b


def test_build_deterministic_batches_differs_for_different_seed() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    samples = tuple(apply_preprocessing(image, state) for image in TRAIN_IMAGES)
    batches_a = build_deterministic_batches(samples, batch_size=2, seed=1)
    batches_b = build_deterministic_batches(samples, batch_size=2, seed=2)
    order_a = [sample.sample_id for batch in batches_a for sample in batch.samples]
    order_b = [sample.sample_id for batch in batches_b for sample in batch.samples]
    assert order_a != order_b


def test_build_deterministic_batches_covers_every_sample_exactly_once() -> None:
    state = fit_preprocessing_state(
        TRAIN_IMAGES, width=WIDTH, height=HEIGHT, channels=CHANNELS, class_weight_policy="none",
    )
    samples = tuple(apply_preprocessing(image, state) for image in TRAIN_IMAGES)
    batches = build_deterministic_batches(samples, batch_size=3, seed=42)
    all_ids = [sample.sample_id for batch in batches for sample in batch.samples]
    assert sorted(all_ids) == sorted(image.sample_id for image in TRAIN_IMAGES)
    assert len(batches) == 2  # 4 samples, batch_size=3 -> batches of 3 and 1
    assert len(batches[0].samples) == 3
    assert len(batches[1].samples) == 1


def test_build_deterministic_batches_rejects_non_positive_batch_size() -> None:
    with pytest.raises(ValueError):
        build_deterministic_batches((), batch_size=0, seed=1)
