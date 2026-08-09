import pytest

from backend.app.analysis.visual_model_spec import (
    ModelSpec,
    TrainingSpec,
    model_spec_id,
    training_configuration_checksum,
    training_spec_id,
    validate_model_spec,
    validate_training_spec,
)


DEFAULT_MODEL_SPEC = ModelSpec(
    architecture_id="cnn-small-v1", preprocessing_policy="normalize_0_1",
    class_weight_policy="balanced",
)
DEFAULT_TRAINING_SPEC = TrainingSpec(
    seed=42, optimizer="adam", loss="cross_entropy", batch_size=32, max_epochs=10,
    compute_requirement="cpu",
)


def test_model_spec_id_is_deterministic() -> None:
    assert model_spec_id(DEFAULT_MODEL_SPEC) == model_spec_id(DEFAULT_MODEL_SPEC)


def test_model_spec_id_changes_with_architecture() -> None:
    other = ModelSpec(
        architecture_id="cnn-large-v1", preprocessing_policy="normalize_0_1",
        class_weight_policy="balanced",
    )
    assert model_spec_id(DEFAULT_MODEL_SPEC) != model_spec_id(other)


def test_training_spec_id_is_deterministic() -> None:
    assert training_spec_id(DEFAULT_TRAINING_SPEC) == training_spec_id(DEFAULT_TRAINING_SPEC)


def test_training_spec_id_changes_with_seed() -> None:
    other = TrainingSpec(
        seed=43, optimizer="adam", loss="cross_entropy", batch_size=32, max_epochs=10,
        compute_requirement="cpu",
    )
    assert training_spec_id(DEFAULT_TRAINING_SPEC) != training_spec_id(other)


def test_training_configuration_checksum_is_deterministic_for_same_dataset_and_spec() -> None:
    first = training_configuration_checksum(
        dataset_fingerprint="sha256:dataset-a",
        model_spec_id=model_spec_id(DEFAULT_MODEL_SPEC),
        training_spec_id=training_spec_id(DEFAULT_TRAINING_SPEC),
    )
    second = training_configuration_checksum(
        dataset_fingerprint="sha256:dataset-a",
        model_spec_id=model_spec_id(DEFAULT_MODEL_SPEC),
        training_spec_id=training_spec_id(DEFAULT_TRAINING_SPEC),
    )
    assert first == second


def test_training_configuration_checksum_changes_with_dataset_fingerprint() -> None:
    common = {
        "model_spec_id": model_spec_id(DEFAULT_MODEL_SPEC),
        "training_spec_id": training_spec_id(DEFAULT_TRAINING_SPEC),
    }
    checksum_a = training_configuration_checksum(dataset_fingerprint="sha256:dataset-a", **common)
    checksum_b = training_configuration_checksum(dataset_fingerprint="sha256:dataset-b", **common)
    assert checksum_a != checksum_b


def test_training_configuration_checksum_changes_with_training_spec() -> None:
    other_training_spec_id = training_spec_id(
        TrainingSpec(
            seed=1, optimizer="sgd", loss="cross_entropy", batch_size=32, max_epochs=10,
            compute_requirement="cpu",
        )
    )
    checksum_a = training_configuration_checksum(
        dataset_fingerprint="sha256:dataset-a", model_spec_id=model_spec_id(DEFAULT_MODEL_SPEC),
        training_spec_id=training_spec_id(DEFAULT_TRAINING_SPEC),
    )
    checksum_b = training_configuration_checksum(
        dataset_fingerprint="sha256:dataset-a", model_spec_id=model_spec_id(DEFAULT_MODEL_SPEC),
        training_spec_id=other_training_spec_id,
    )
    assert checksum_a != checksum_b


def test_validate_model_spec_accepts_default() -> None:
    validate_model_spec(DEFAULT_MODEL_SPEC)


@pytest.mark.parametrize("architecture_id", ["", "   "])
def test_validate_model_spec_rejects_empty_architecture_id(architecture_id: str) -> None:
    spec = ModelSpec(
        architecture_id=architecture_id, preprocessing_policy="normalize_0_1",
        class_weight_policy="none",
    )
    with pytest.raises(ValueError):
        validate_model_spec(spec)


def test_validate_model_spec_rejects_unknown_class_weight_policy() -> None:
    spec = ModelSpec(
        architecture_id="cnn-small-v1", preprocessing_policy="normalize_0_1",
        class_weight_policy="made_up_policy",
    )
    with pytest.raises(ValueError):
        validate_model_spec(spec)


def test_validate_training_spec_accepts_default() -> None:
    validate_training_spec(DEFAULT_TRAINING_SPEC)


def test_validate_training_spec_rejects_non_positive_batch_size() -> None:
    spec = TrainingSpec(
        seed=1, optimizer="adam", loss="cross_entropy", batch_size=0, max_epochs=10,
        compute_requirement="cpu",
    )
    with pytest.raises(ValueError):
        validate_training_spec(spec)


def test_validate_training_spec_rejects_non_positive_max_epochs() -> None:
    spec = TrainingSpec(
        seed=1, optimizer="adam", loss="cross_entropy", batch_size=32, max_epochs=0,
        compute_requirement="cpu",
    )
    with pytest.raises(ValueError):
        validate_training_spec(spec)


def test_validate_training_spec_rejects_unknown_compute_requirement() -> None:
    spec = TrainingSpec(
        seed=1, optimizer="adam", loss="cross_entropy", batch_size=32, max_epochs=10,
        compute_requirement="tpu",
    )
    with pytest.raises(ValueError):
        validate_training_spec(spec)


def test_validate_training_spec_rejects_boolean_seed() -> None:
    spec = TrainingSpec(
        seed=True, optimizer="adam", loss="cross_entropy", batch_size=32, max_epochs=10,
        compute_requirement="cpu",
    )
    with pytest.raises(ValueError):
        validate_training_spec(spec)
