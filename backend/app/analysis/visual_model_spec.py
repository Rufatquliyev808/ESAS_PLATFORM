from dataclasses import asdict, dataclass
from hashlib import sha256
import json


MODEL_SPEC_VERSION = "1.0.0"
TRAINING_SPEC_VERSION = "1.0.0"

VALID_COMPUTE_REQUIREMENTS = frozenset({"cpu", "gpu"})
VALID_CLASS_WEIGHT_POLICIES = frozenset({"none", "balanced", "inverse_frequency"})


@dataclass(frozen=True)
class ModelSpec:
    """What the model IS: architecture identity plus how raw samples are
    turned into model inputs and how class imbalance is handled. Deliberately
    excludes anything about how a training RUN behaves (seed, optimizer,
    batch/epoch limits, compute) -- that is `TrainingSpec`'s concern. Must be
    frozen by the caller before training starts, same "register the config
    before you look at results" discipline `RenderSpec`/`LabelSpec` already
    enforce elsewhere in Phase 5.
    """

    architecture_id: str
    preprocessing_policy: str
    class_weight_policy: str
    version: str = MODEL_SPEC_VERSION


@dataclass(frozen=True)
class TrainingSpec:
    """How a training RUN behaves: seed (for reproducibility), optimizer/
    loss, batch size and epoch ceiling, and whether the run requires a GPU.
    """

    seed: int
    optimizer: str
    loss: str
    batch_size: int
    max_epochs: int
    compute_requirement: str
    version: str = TRAINING_SPEC_VERSION


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def model_spec_id(spec: ModelSpec) -> str:
    return f"sha256:{sha256(_canonical_json(asdict(spec))).hexdigest()}"


def training_spec_id(spec: TrainingSpec) -> str:
    return f"sha256:{sha256(_canonical_json(asdict(spec))).hexdigest()}"


def _required_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def validate_model_spec(spec: ModelSpec) -> None:
    _required_text(spec.architecture_id, "architecture_id")
    _required_text(spec.preprocessing_policy, "preprocessing_policy")
    if spec.class_weight_policy not in VALID_CLASS_WEIGHT_POLICIES:
        raise ValueError(
            f"class_weight_policy must be one of: {', '.join(sorted(VALID_CLASS_WEIGHT_POLICIES))}"
        )


def _positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def validate_training_spec(spec: TrainingSpec) -> None:
    if isinstance(spec.seed, bool) or not isinstance(spec.seed, int):
        raise ValueError("seed must be an integer")
    _required_text(spec.optimizer, "optimizer")
    _required_text(spec.loss, "loss")
    _positive_int(spec.batch_size, "batch_size")
    _positive_int(spec.max_epochs, "max_epochs")
    if spec.compute_requirement not in VALID_COMPUTE_REQUIREMENTS:
        raise ValueError(
            f"compute_requirement must be one of: {', '.join(sorted(VALID_COMPUTE_REQUIREMENTS))}"
        )


def training_configuration_checksum(
    *, dataset_fingerprint: str, model_spec_id: str, training_spec_id: str,
) -> str:
    """Identity of "this exact dataset trained with this exact model/training
    spec". Deterministic: the same three inputs always produce the same
    checksum, and any change to any one of them (a different dataset
    materialization, a different architecture, a different seed) produces a
    different one -- the property the Phase 5 `rendering -> training`
    contract's acceptance criterion requires.
    """
    payload = {
        "dataset_fingerprint": dataset_fingerprint,
        "model_spec_id": model_spec_id,
        "training_spec_id": training_spec_id,
        "version": f"{MODEL_SPEC_VERSION}+{TRAINING_SPEC_VERSION}",
    }
    return f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"
