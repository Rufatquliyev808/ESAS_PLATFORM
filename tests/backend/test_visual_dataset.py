from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.visual_dataset import (
    HOLDOUT,
    LABELED,
    PENDING_HORIZON,
    PURGED_BOUNDARY_OVERLAP,
    TRAIN,
    VALIDATION,
    assign_time_based_splits,
    build_dataset_manifest,
    build_visual_sample,
)
from backend.app.analysis.visual_render import RenderSpec, render_canonical_chart


BASE_TIME = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
SPEC = RenderSpec(width=20, height=10, padding_top=1, padding_bottom=1, padding_left=1, padding_right=1)


def bar(start: datetime, index: int) -> MarketBar:
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=1.0, high=1.2, low=0.8, close=1.1,
        tick_count=2, tick_volume=2,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:1",
    )


def image_at(day_offset: int, *, n_bars: int = 3):
    start = BASE_TIME + timedelta(days=day_offset)
    bars = tuple(bar(start + timedelta(minutes=i), i) for i in range(n_bars))
    return render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SPEC)


TRAIN_END = (BASE_TIME + timedelta(days=1)).isoformat()
VALIDATION_END = (BASE_TIME + timedelta(days=2)).isoformat()


def test_pending_horizon_when_no_label_available_at() -> None:
    sample = build_visual_sample(image_at(0), label_spec_id="horizon_10bar_up")
    assert sample.label_status == PENDING_HORIZON
    assert sample.label_available_at is None
    assert sample.label_value is None


def test_labeled_when_label_available_at_given() -> None:
    image = image_at(0)
    available_at = (BASE_TIME + timedelta(minutes=10)).isoformat()
    sample = build_visual_sample(
        image, label_spec_id="horizon_10bar_up", label_available_at=available_at, label_value="up",
    )
    assert sample.label_status == LABELED
    assert sample.label_value == "up"


def test_sample_id_is_deterministic_for_identical_inputs() -> None:
    image = image_at(0)
    a = build_visual_sample(image, label_spec_id="spec_a")
    b = build_visual_sample(image, label_spec_id="spec_a")
    assert a.sample_id == b.sample_id


def test_sample_id_differs_by_label_spec_id() -> None:
    image = image_at(0)
    a = build_visual_sample(image, label_spec_id="spec_a")
    b = build_visual_sample(image, label_spec_id="spec_b")
    assert a.sample_id != b.sample_id


def test_rejects_empty_label_spec_id() -> None:
    with pytest.raises(ValueError):
        build_visual_sample(image_at(0), label_spec_id="   ")


def test_rejects_label_value_without_label_available_at() -> None:
    with pytest.raises(ValueError):
        build_visual_sample(image_at(0), label_spec_id="spec_a", label_value="up")


def test_rejects_label_available_at_before_observation_window_closes() -> None:
    image = image_at(0)
    too_early = (BASE_TIME - timedelta(minutes=1)).isoformat()
    with pytest.raises(ValueError):
        build_visual_sample(image, label_spec_id="spec_a", label_available_at=too_early)


def _labeled_sample(day_offset: int, *, horizon_minutes: int = 5):
    image = image_at(day_offset)
    known_at = datetime.fromisoformat(image.known_at)
    available_at = (known_at + timedelta(minutes=horizon_minutes)).isoformat()
    return build_visual_sample(
        image, label_spec_id="spec_a", label_available_at=available_at, label_value="up",
    )


def test_sample_fully_before_train_boundary_is_train() -> None:
    sample = _labeled_sample(0)
    [assigned] = assign_time_based_splits((sample,), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END)
    assert assigned.split_id == TRAIN


def test_sample_fully_within_validation_range_is_validation() -> None:
    sample = _labeled_sample(1)
    [assigned] = assign_time_based_splits((sample,), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END)
    assert assigned.split_id == VALIDATION


def test_sample_fully_after_validation_boundary_is_holdout() -> None:
    sample = _labeled_sample(3)
    [assigned] = assign_time_based_splits((sample,), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END)
    assert assigned.split_id == HOLDOUT


def test_sample_crossing_train_boundary_is_purged() -> None:
    start = BASE_TIME + timedelta(days=1) - timedelta(minutes=2)
    bars = tuple(bar(start + timedelta(minutes=i), i) for i in range(3))
    image = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SPEC)
    known_at = datetime.fromisoformat(image.known_at)
    available_at = (known_at + timedelta(minutes=10)).isoformat()
    sample = build_visual_sample(image, label_spec_id="spec_a", label_available_at=available_at, label_value="up")
    [assigned] = assign_time_based_splits((sample,), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END)
    assert assigned.split_id == PURGED_BOUNDARY_OVERLAP


def test_sample_crossing_validation_boundary_is_purged() -> None:
    start = BASE_TIME + timedelta(days=2) - timedelta(minutes=2)
    bars = tuple(bar(start + timedelta(minutes=i), i) for i in range(3))
    image = render_canonical_chart(bars, bar_fingerprint="sha256:source", spec=SPEC)
    known_at = datetime.fromisoformat(image.known_at)
    available_at = (known_at + timedelta(minutes=10)).isoformat()
    sample = build_visual_sample(image, label_spec_id="spec_a", label_available_at=available_at, label_value="up")
    [assigned] = assign_time_based_splits((sample,), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END)
    assert assigned.split_id == PURGED_BOUNDARY_OVERLAP


def test_pending_horizon_sample_is_never_split() -> None:
    sample = build_visual_sample(image_at(5), label_spec_id="spec_a")
    [assigned] = assign_time_based_splits((sample,), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END)
    assert assigned.split_id == PENDING_HORIZON


def test_rejects_validation_end_at_or_before_train_end_at() -> None:
    sample = _labeled_sample(0)
    with pytest.raises(ValueError):
        assign_time_based_splits((sample,), train_end_at=VALIDATION_END, validation_end_at=TRAIN_END)


def test_manifest_never_drops_any_sample() -> None:
    samples = assign_time_based_splits(
        (
            _labeled_sample(0),
            _labeled_sample(1),
            _labeled_sample(3),
            build_visual_sample(image_at(5), label_spec_id="spec_a"),
        ),
        train_end_at=TRAIN_END, validation_end_at=VALIDATION_END,
    )
    manifest = build_dataset_manifest(samples)
    assert manifest.total_samples == 4
    assert sum(entry.count for entry in manifest.entries) == 4
    split_ids = {entry.split_id for entry in manifest.entries}
    assert split_ids == {TRAIN, VALIDATION, HOLDOUT, PENDING_HORIZON}


def test_manifest_separates_rows_by_quality_flags() -> None:
    clean = _labeled_sample(0)
    gapped_bars = (
        bar(BASE_TIME, 0),
        bar(BASE_TIME + timedelta(minutes=10), 1),
    )
    gapped_image = render_canonical_chart(gapped_bars, bar_fingerprint="sha256:source", spec=SPEC)
    known_at = datetime.fromisoformat(gapped_image.known_at)
    available_at = (known_at + timedelta(minutes=5)).isoformat()
    gapped = build_visual_sample(
        gapped_image, label_spec_id="spec_a", label_available_at=available_at, label_value="up",
    )
    assert gapped.quality_flags != ()
    assert clean.quality_flags == ()

    manifest = build_dataset_manifest((clean, gapped))
    assert manifest.total_samples == 2
    assert len(manifest.entries) == 2


def test_manifest_fingerprint_is_deterministic() -> None:
    samples = (_labeled_sample(0),)
    first = build_dataset_manifest(samples)
    second = build_dataset_manifest(samples)
    assert first.fingerprint == second.fingerprint


def test_manifest_fingerprint_differs_for_different_split_composition() -> None:
    train_sample = assign_time_based_splits(
        (_labeled_sample(0),), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END,
    )
    validation_sample = assign_time_based_splits(
        (_labeled_sample(1),), train_end_at=TRAIN_END, validation_end_at=VALIDATION_END,
    )
    first = build_dataset_manifest(train_sample)
    second = build_dataset_manifest(validation_sample)
    assert first.fingerprint != second.fingerprint
