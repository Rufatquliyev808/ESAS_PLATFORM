from dataclasses import dataclass
from hashlib import sha256
import json
import random


VISUAL_TRAINING_INPUT_VERSION = "1.0.0"
VALID_CLASS_WEIGHT_POLICIES = frozenset({"none", "balanced", "inverse_frequency"})


class PreprocessingFitError(ValueError):
    pass


@dataclass(frozen=True)
class LabeledImage:
    """A sample's identity, its decoded raw RGB8 pixel buffer, and its
    label -- decoupled from persistence (DB rows) and from the artifact
    store (PNG bytes), so this module stays a pure, directly testable
    function of already-materialized values with no I/O of its own.
    """

    sample_id: str
    pixels: bytes
    label_value: str


@dataclass(frozen=True)
class PreprocessingState:
    """Everything a later step needs to reproduce this exact transform:
    the fitted normalization bounds, the class-index mapping, and enough
    identity (train_fingerprint, checksum) to prove which train data it was
    fit from and detect any drift. Deliberately does not carry a reference
    to validation/holdout data -- there is no field here that could have
    come from anywhere but train.
    """

    version: str
    width: int
    height: int
    channels: int
    train_fingerprint: str
    class_mapping: tuple[tuple[str, int], ...]
    channel_min: tuple[int, ...]
    channel_max: tuple[int, ...]
    class_weight_policy: str
    class_weights: tuple[tuple[str, float], ...]
    checksum: str


@dataclass(frozen=True)
class TrainingInputSample:
    sample_id: str
    normalized_pixels: tuple[float, ...]
    class_index: int


@dataclass(frozen=True)
class TrainingInputBatch:
    batch_index: int
    samples: tuple[TrainingInputSample, ...]


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _train_fingerprint(train_images: tuple[LabeledImage, ...]) -> str:
    identities = sorted(
        f"{image.sample_id}:{sha256(image.pixels).hexdigest()}:{image.label_value}"
        for image in train_images
    )
    payload = {"sample_identities": identities, "version": VISUAL_TRAINING_INPUT_VERSION}
    return f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"


def _compute_class_weights(class_counts: dict[str, int], *, policy: str) -> tuple[tuple[str, float], ...]:
    if policy not in VALID_CLASS_WEIGHT_POLICIES:
        raise PreprocessingFitError(
            f"class_weight_policy must be one of: {', '.join(sorted(VALID_CLASS_WEIGHT_POLICIES))}"
        )
    sorted_classes = sorted(class_counts)
    total = sum(class_counts.values())
    num_classes = len(sorted_classes)
    if policy == "none":
        weights = {label: 1.0 for label in sorted_classes}
    elif policy == "balanced":
        weights = {label: total / (num_classes * class_counts[label]) for label in sorted_classes}
    else:  # inverse_frequency
        weights = {label: total / class_counts[label] for label in sorted_classes}
    return tuple((label, weights[label]) for label in sorted_classes)


def _preprocessing_state_payload(
    *,
    width: int,
    height: int,
    channels: int,
    train_fingerprint: str,
    class_mapping: tuple[tuple[str, int], ...],
    channel_min: tuple[int, ...],
    channel_max: tuple[int, ...],
    class_weight_policy: str,
    class_weights: tuple[tuple[str, float], ...],
) -> dict:
    return {
        "channel_max": list(channel_max),
        "channel_min": list(channel_min),
        "channels": channels,
        "class_mapping": [list(item) for item in class_mapping],
        "class_weight_policy": class_weight_policy,
        "class_weights": [list(item) for item in class_weights],
        "height": height,
        "train_fingerprint": train_fingerprint,
        "version": VISUAL_TRAINING_INPUT_VERSION,
        "width": width,
    }


def preprocessing_state_artifact_bytes(state: PreprocessingState) -> bytes:
    """The exact bytes `state.checksum` is a sha256 over -- what gets
    written to the content-addressed artifact store for this preprocessing
    state. Rebuilding the payload from the state's own fields (rather than
    caching the original bytes) guarantees the artifact content and the
    checksum can never drift apart.
    """
    payload = _preprocessing_state_payload(
        width=state.width, height=state.height, channels=state.channels,
        train_fingerprint=state.train_fingerprint, class_mapping=state.class_mapping,
        channel_min=state.channel_min, channel_max=state.channel_max,
        class_weight_policy=state.class_weight_policy, class_weights=state.class_weights,
    )
    return _canonical_json(payload)


def fit_preprocessing_state(
    train_images: tuple[LabeledImage, ...],
    *,
    width: int,
    height: int,
    channels: int,
    class_weight_policy: str,
) -> PreprocessingState:
    """Fits per-channel min/max normalization bounds and class weights from
    TRAIN images ONLY -- there is no parameter here through which
    validation/holdout data could enter; that is the separation-by-
    construction the Phase 5 contract requires, not a runtime check.

    Deterministic and order-independent: min/max are associative, so
    whatever order `train_images` arrives in, the fitted bounds (and
    therefore the checksum) are identical -- the "byte-for-byte identical"
    acceptance criterion holds regardless of how a caller assembled the
    tuple.
    """
    if not train_images:
        raise PreprocessingFitError("cannot fit preprocessing state from zero train images")
    expected_length = width * height * channels
    for image in train_images:
        if len(image.pixels) != expected_length:
            raise PreprocessingFitError(
                f"sample {image.sample_id} pixel buffer length does not match width*height*channels"
            )

    channel_min = [255] * channels
    channel_max = [0] * channels
    for image in train_images:
        for offset in range(0, len(image.pixels), channels):
            for channel in range(channels):
                value = image.pixels[offset + channel]
                if value < channel_min[channel]:
                    channel_min[channel] = value
                if value > channel_max[channel]:
                    channel_max[channel] = value

    class_counts: dict[str, int] = {}
    for image in train_images:
        class_counts[image.label_value] = class_counts.get(image.label_value, 0) + 1
    sorted_classes = sorted(class_counts)
    class_mapping = tuple((label, index) for index, label in enumerate(sorted_classes))
    class_weights = _compute_class_weights(class_counts, policy=class_weight_policy)
    train_fingerprint = _train_fingerprint(train_images)

    payload = _preprocessing_state_payload(
        width=width, height=height, channels=channels, train_fingerprint=train_fingerprint,
        class_mapping=class_mapping, channel_min=tuple(channel_min), channel_max=tuple(channel_max),
        class_weight_policy=class_weight_policy, class_weights=class_weights,
    )
    checksum = f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"

    return PreprocessingState(
        version=VISUAL_TRAINING_INPUT_VERSION, width=width, height=height, channels=channels,
        train_fingerprint=train_fingerprint, class_mapping=class_mapping,
        channel_min=tuple(channel_min), channel_max=tuple(channel_max),
        class_weight_policy=class_weight_policy, class_weights=class_weights, checksum=checksum,
    )


def apply_preprocessing(image: LabeledImage, state: PreprocessingState) -> TrainingInputSample:
    """Applies an ALREADY-FIT `PreprocessingState` to one image. Never
    fits anything -- there is no code path here that could change
    `state`, so calling this on validation/holdout images can never feed
    back into (or leak information from) the frozen train-only state.
    """
    expected_length = state.width * state.height * state.channels
    if len(image.pixels) != expected_length:
        raise PreprocessingFitError(
            f"sample {image.sample_id} pixel buffer length does not match the fitted state's dimensions"
        )
    class_index_by_label = dict(state.class_mapping)
    if image.label_value not in class_index_by_label:
        raise PreprocessingFitError(
            f"sample {image.sample_id} has label {image.label_value!r}, which was never seen during fit"
        )

    normalized: list[float] = []
    for offset in range(0, len(image.pixels), state.channels):
        for channel in range(state.channels):
            value = image.pixels[offset + channel]
            channel_range = state.channel_max[channel] - state.channel_min[channel]
            normalized.append(
                0.0 if channel_range == 0 else (value - state.channel_min[channel]) / channel_range
            )

    return TrainingInputSample(
        sample_id=image.sample_id, normalized_pixels=tuple(normalized),
        class_index=class_index_by_label[image.label_value],
    )


def build_deterministic_batches(
    samples: tuple[TrainingInputSample, ...], *, batch_size: int, seed: int,
) -> tuple[TrainingInputBatch, ...]:
    """Deterministic batch order: sort by `sample_id` first (removes any
    incoming-order nondeterminism -- e.g. SQLite row order without an
    ORDER BY is not guaranteed), then shuffle with a seeded `random.Random`,
    then slice into fixed-size batches. The same seed applied to the same
    samples always produces the same batch order.
    """
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")

    ordered = sorted(samples, key=lambda sample: sample.sample_id)
    random.Random(seed).shuffle(ordered)
    return tuple(
        TrainingInputBatch(batch_index=batch_index, samples=tuple(ordered[start : start + batch_size]))
        for batch_index, start in enumerate(range(0, len(ordered), batch_size))
    )
