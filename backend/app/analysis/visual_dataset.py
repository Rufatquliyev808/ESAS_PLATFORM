from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
import json

from backend.app.analysis.visual_render import CanonicalImage


VISUAL_DATASET_VERSION = "1.0.0"
LABELED = "labeled"
PENDING_HORIZON = "pending_horizon"
TRAIN = "train"
VALIDATION = "validation"
HOLDOUT = "holdout"
PURGED_BOUNDARY_OVERLAP = "purged_boundary_overlap"


@dataclass(frozen=True)
class VisualSample:
    """One dataset unit, carrying the Phase 5 contract's immutable lineage
    chain: sample_id -> source_bar_fingerprint -> render_spec_id ->
    image_checksum -> observation_end_at -> label_spec_id ->
    label_available_at -> split_id. Label VALUE computation itself is
    intentionally out of scope here (the contract requires it be computed
    "ayrıca" -- separately -- per Phase 4 rules, without influencing image
    rendering); this layer only records whatever label a caller supplies
    and enforces that it cannot be dated before the observation window it
    describes actually closes.
    """

    version: str
    sample_id: str
    symbol: str
    timeframe: str
    source_bar_fingerprint: str
    render_spec_id: str
    image_checksum: str
    observation_window_start_at: str
    observation_end_at: str
    label_spec_id: str
    label_available_at: str | None
    label_value: str | None
    label_status: str
    quality_flags: tuple[str, ...]
    split_id: str = "unassigned"
    interpretation: str = "research_observation_not_trading_signal"


@dataclass(frozen=True)
class DatasetManifestEntry:
    symbol: str
    timeframe: str
    split_id: str
    label_status: str
    has_quality_flags: bool
    count: int


@dataclass(frozen=True)
class DatasetManifest:
    version: str
    total_samples: int
    entries: tuple[DatasetManifestEntry, ...]
    fingerprint: str


def _parse_utc(value: str, field_name: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC)


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _fingerprint(payload: dict) -> str:
    return f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"


def build_visual_sample(
    image: CanonicalImage,
    *,
    label_spec_id: str,
    label_available_at: str | None = None,
    label_value: str | None = None,
) -> VisualSample:
    normalized_label_spec_id = label_spec_id.strip()
    if not normalized_label_spec_id:
        raise ValueError("label_spec_id must not be empty")
    if label_value is not None and label_available_at is None:
        raise ValueError("label_value requires label_available_at")

    if label_available_at is not None:
        known_at = _parse_utc(image.known_at, "image.known_at")
        available_at = _parse_utc(label_available_at, "label_available_at")
        if available_at < known_at:
            raise ValueError(
                "label_available_at must not be before the observation window closes"
            )
        label_status = LABELED
    else:
        label_status = PENDING_HORIZON

    sample_id = _fingerprint(
        {
            "image_checksum": image.image_checksum,
            "label_available_at": label_available_at,
            "label_spec_id": normalized_label_spec_id,
            "observation_end_at": image.known_at,
            "render_spec_id": image.render_spec_id,
            "source_bar_fingerprint": image.bar_fingerprint,
        }
    )

    return VisualSample(
        version=VISUAL_DATASET_VERSION,
        sample_id=sample_id,
        symbol=image.symbol,
        timeframe=image.timeframe,
        source_bar_fingerprint=image.bar_fingerprint,
        render_spec_id=image.render_spec_id,
        image_checksum=image.image_checksum,
        observation_window_start_at=image.first_bar_start_at,
        observation_end_at=image.known_at,
        label_spec_id=normalized_label_spec_id,
        label_available_at=label_available_at,
        label_value=label_value,
        label_status=label_status,
        quality_flags=image.quality_flags,
    )


def assign_time_based_splits(
    samples: tuple[VisualSample, ...], *, train_end_at: str, validation_end_at: str,
) -> tuple[VisualSample, ...]:
    """Time-based (never random) train/validation/holdout split, per the
    contract's "Random image split qadağandır; zaman əsaslı bölgü
    məcburidir" rule. A labeled sample whose [observation_window_start_at,
    label_available_at) interval crosses a split boundary is purged (kept
    in the output with split_id=PURGED_BOUNDARY_OVERLAP, never silently
    dropped) rather than assigned to either side, since it would otherwise
    let the same historical event leak across two splits. Samples without a
    label yet (label_status=PENDING_HORIZON) are not split at all -- their
    horizon has not completed.
    """
    train_boundary = _parse_utc(train_end_at, "train_end_at")
    validation_boundary = _parse_utc(validation_end_at, "validation_end_at")
    if validation_boundary <= train_boundary:
        raise ValueError("validation_end_at must be after train_end_at")

    assigned: list[VisualSample] = []
    for sample in samples:
        if sample.label_status != LABELED:
            assigned.append(replace(sample, split_id=PENDING_HORIZON))
            continue

        window_start = _parse_utc(
            sample.observation_window_start_at, "observation_window_start_at"
        )
        window_end = _parse_utc(sample.label_available_at, "label_available_at")

        if window_end <= train_boundary:
            split_id = TRAIN
        elif window_start < train_boundary:
            split_id = PURGED_BOUNDARY_OVERLAP
        elif window_end <= validation_boundary:
            split_id = VALIDATION
        elif window_start < validation_boundary:
            split_id = PURGED_BOUNDARY_OVERLAP
        else:
            split_id = HOLDOUT
        assigned.append(replace(sample, split_id=split_id))
    return tuple(assigned)


def build_dataset_manifest(samples: tuple[VisualSample, ...]) -> DatasetManifest:
    """Counts samples by symbol/timeframe/split/label-status/quality, never
    dropping any of them (failed, neutral and pending-horizon samples all get
    their own manifest row). Session and regime breakdowns from Phase 3's
    SA-006/SA-007 are deliberately not joined in here yet -- that requires
    tying a visual sample back to a specific statistical-analysis window,
    which is a separate future increment.
    """
    counter: dict[tuple[str, str, str, str, bool], int] = {}
    for sample in samples:
        key = (
            sample.symbol, sample.timeframe, sample.split_id, sample.label_status,
            bool(sample.quality_flags),
        )
        counter[key] = counter.get(key, 0) + 1

    entries = tuple(
        DatasetManifestEntry(symbol, timeframe, split_id, label_status, has_quality_flags, count)
        for (symbol, timeframe, split_id, label_status, has_quality_flags), count
        in sorted(counter.items())
    )

    return DatasetManifest(
        version=VISUAL_DATASET_VERSION,
        total_samples=len(samples),
        entries=entries,
        fingerprint=_fingerprint(
            {
                "entries": [asdict(entry) for entry in entries],
                "total_samples": len(samples),
                "version": VISUAL_DATASET_VERSION,
            }
        ),
    )
