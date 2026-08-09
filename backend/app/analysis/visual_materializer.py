from dataclasses import dataclass
from hashlib import sha256
import json

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.visual_dataset import (
    DatasetManifest,
    VisualSample,
    assign_time_based_splits,
    build_dataset_manifest,
    build_visual_sample,
)
from backend.app.analysis.visual_label import LabelSpec, compute_label
from backend.app.analysis.visual_render import CanonicalImage, RenderSpec, render_canonical_chart


MATERIALIZER_VERSION = "1.0.0"


class BarFingerprintMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class MaterializedSample:
    """One rendered+labelled+lineage-tracked dataset unit. `image` carries the
    actual PNG bytes (`image.png_bytes`); `sample` carries the persistence-
    ready lineage record. Kept as two objects rather than merging them
    because `visual_dataset.py`'s `VisualSample` deliberately excludes raw
    image bytes -- this pairing is the materializer's own concern, not a
    change to that module.
    """

    sample: VisualSample
    image: CanonicalImage


@dataclass(frozen=True)
class VisualDatasetMaterialization:
    version: str
    bar_fingerprint: str
    render_spec_id: str
    label_spec_id: str
    observation_window_bars: int
    train_end_at: str
    validation_end_at: str
    samples: tuple[MaterializedSample, ...]
    manifest: DatasetManifest
    dataset_fingerprint: str


def _validate_bars(bars: tuple[MarketBar, ...]) -> None:
    if not bars:
        raise ValueError("bars must not be empty")
    symbol = bars[0].symbol
    timeframe = bars[0].timeframe
    previous_end: str | None = None
    for bar in bars:
        if bar.symbol != symbol or bar.timeframe != timeframe:
            raise ValueError("bars must share the same symbol and timeframe")
        if previous_end is not None and bar.start_at < previous_end:
            raise ValueError("bars must be sorted by start_at without overlap")
        previous_end = bar.end_at


def _windows(
    bars: tuple[MarketBar, ...], observation_window_bars: int
) -> list[tuple[MarketBar, ...]]:
    last_start = len(bars) - observation_window_bars
    return [
        bars[start : start + observation_window_bars]
        for start in range(0, last_start + 1, observation_window_bars)
    ]


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _dataset_fingerprint(
    *,
    bar_fingerprint: str,
    render_spec_id: str,
    label_spec_id: str,
    observation_window_bars: int,
    train_end_at: str,
    validation_end_at: str,
    samples: tuple[VisualSample, ...],
) -> str:
    payload = {
        "bar_fingerprint": bar_fingerprint,
        "label_spec_id": label_spec_id,
        "observation_window_bars": observation_window_bars,
        "render_spec_id": render_spec_id,
        "sample_identities": sorted(
            f"{sample.sample_id}:{sample.image_checksum}:{sample.split_id}"
            for sample in samples
        ),
        "train_end_at": train_end_at,
        "validation_end_at": validation_end_at,
        "version": MATERIALIZER_VERSION,
    }
    return f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"


def materialize_visual_dataset(
    bars: tuple[MarketBar, ...],
    *,
    bar_fingerprint: str,
    source_bar_fingerprint: str,
    render_spec: RenderSpec,
    label_spec: LabelSpec,
    observation_window_bars: int,
    train_end_at: str,
    validation_end_at: str,
) -> VisualDatasetMaterialization:
    """Deterministic Visual Dataset Materializer v1.

    Slices a completed replay session's closed bars into non-overlapping
    observation windows, renders and labels each one, and assigns a
    time-based train/validation/holdout split -- purely by composing the
    existing, already-tested `visual_render.py`/`visual_label.py`/
    `visual_dataset.py` functions. No rendering, labelling, splitting, or
    manifest logic is reimplemented here.

    Fail-closed: if `bar_fingerprint` (the fingerprint of the bars actually
    being materialized right now) does not match `source_bar_fingerprint`
    (the value frozen at experiment registration), this raises
    `BarFingerprintMismatchError` immediately rather than materializing
    from data that has drifted since registration.

    This function only ever produces in-memory objects -- it does not
    persist anything, does not touch any database, and does not transition
    any experiment's lifecycle state. That is a separate, later increment.
    """
    if bar_fingerprint != source_bar_fingerprint:
        raise BarFingerprintMismatchError(
            "bar_fingerprint does not match the experiment's frozen source_bar_fingerprint"
        )
    _validate_bars(bars)
    if (
        isinstance(observation_window_bars, bool)
        or not isinstance(observation_window_bars, int)
        or observation_window_bars < 1
    ):
        raise ValueError("observation_window_bars must be a positive integer")

    windows = _windows(bars, observation_window_bars)
    if not windows:
        raise ValueError("bars does not contain enough bars for a single observation window")

    materialized: list[MaterializedSample] = []
    for window in windows:
        image = render_canonical_chart(window, bar_fingerprint=bar_fingerprint, spec=render_spec)
        label_result = compute_label(bars, observation_end_at=image.known_at, spec=label_spec)
        sample = build_visual_sample(
            image,
            label_spec_id=label_result.label_spec_id,
            label_available_at=label_result.label_available_at,
            label_value=label_result.label_value,
        )
        materialized.append(MaterializedSample(sample=sample, image=image))

    split_samples = assign_time_based_splits(
        tuple(item.sample for item in materialized),
        train_end_at=train_end_at, validation_end_at=validation_end_at,
    )
    materialized = [
        MaterializedSample(sample=split_sample, image=item.image)
        for split_sample, item in zip(split_samples, materialized)
    ]

    manifest = build_dataset_manifest(split_samples)
    render_spec_id_value = materialized[0].image.render_spec_id
    label_spec_id_value = split_samples[0].label_spec_id

    dataset_fingerprint = _dataset_fingerprint(
        bar_fingerprint=bar_fingerprint, render_spec_id=render_spec_id_value,
        label_spec_id=label_spec_id_value, observation_window_bars=observation_window_bars,
        train_end_at=train_end_at, validation_end_at=validation_end_at, samples=split_samples,
    )

    return VisualDatasetMaterialization(
        version=MATERIALIZER_VERSION,
        bar_fingerprint=bar_fingerprint,
        render_spec_id=render_spec_id_value,
        label_spec_id=label_spec_id_value,
        observation_window_bars=observation_window_bars,
        train_end_at=train_end_at,
        validation_end_at=validation_end_at,
        samples=tuple(materialized),
        manifest=manifest,
        dataset_fingerprint=dataset_fingerprint,
    )
