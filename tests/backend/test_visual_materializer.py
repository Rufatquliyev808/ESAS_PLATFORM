from datetime import UTC, datetime, timedelta

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.visual_dataset import (
    HOLDOUT,
    PENDING_HORIZON,
    PURGED_BOUNDARY_OVERLAP,
    TRAIN,
    VALIDATION,
)
from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_materializer import (
    BarFingerprintMismatchError,
    materialize_visual_dataset,
)
from backend.app.analysis.visual_render import RenderSpec, render_canonical_chart


BASE_TIME = datetime(2026, 8, 9, 0, 0, tzinfo=UTC)
SPEC = RenderSpec(width=20, height=10, padding_top=1, padding_bottom=1, padding_left=1, padding_right=1)
SOURCE_FINGERPRINT = "sha256:source-bars"


def bar(index: int, price: float = 100.0) -> MarketBar:
    start = BASE_TIME + timedelta(minutes=index)
    return MarketBar(
        symbol="GOLD", timeframe="M1",
        start_at=start.isoformat(timespec="microseconds"),
        end_at=(start + timedelta(minutes=1)).isoformat(timespec="microseconds"),
        open=price, high=price, low=price, close=price,
        tick_count=2, tick_volume=2,
        spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"event:{index}:0", last_event_id=f"event:{index}:1",
    )


def bars(count: int) -> tuple[MarketBar, ...]:
    return tuple(bar(i) for i in range(count))


def materialize(
    bar_count: int = 12, *, observation_window_bars: int = 2,
    horizon_bars: int = 2, train_end_at: str = (BASE_TIME + timedelta(days=1)).isoformat(),
    validation_end_at: str = (BASE_TIME + timedelta(days=2)).isoformat(),
):
    return materialize_visual_dataset(
        bars(bar_count), bar_fingerprint=SOURCE_FINGERPRINT,
        source_bar_fingerprint=SOURCE_FINGERPRINT, render_spec=SPEC,
        label_spec=LabelSpec(horizon_bars, 10.0, -10.0),
        observation_window_bars=observation_window_bars,
        train_end_at=train_end_at, validation_end_at=validation_end_at,
    )


def test_rejects_empty_bars() -> None:
    with pytest.raises(ValueError):
        materialize_visual_dataset(
            (), bar_fingerprint=SOURCE_FINGERPRINT, source_bar_fingerprint=SOURCE_FINGERPRINT,
            render_spec=SPEC, label_spec=LabelSpec(2, 10.0, -10.0), observation_window_bars=2,
            train_end_at=BASE_TIME.isoformat(), validation_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        )


def test_rejects_non_positive_observation_window_bars() -> None:
    with pytest.raises(ValueError):
        materialize(observation_window_bars=0)


def test_rejects_insufficient_bars_for_one_window() -> None:
    with pytest.raises(ValueError):
        materialize(bar_count=1, observation_window_bars=2)


def test_fails_closed_on_bar_fingerprint_mismatch() -> None:
    with pytest.raises(BarFingerprintMismatchError):
        materialize_visual_dataset(
            bars(12), bar_fingerprint="sha256:actual", source_bar_fingerprint="sha256:frozen-at-registration",
            render_spec=SPEC, label_spec=LabelSpec(2, 10.0, -10.0), observation_window_bars=2,
            train_end_at=BASE_TIME.isoformat(), validation_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        )


def test_produces_non_overlapping_windows_and_drops_trailing_partial() -> None:
    result = materialize(bar_count=13, observation_window_bars=2)
    assert len(result.samples) == 6  # floor(13/2), trailing 1 bar dropped
    assert result.observation_window_bars == 2


def test_each_sample_matches_direct_render_and_carries_png() -> None:
    result = materialize(bar_count=12, observation_window_bars=2)
    all_bars = bars(12)
    first_window = all_bars[0:2]
    expected_image = render_canonical_chart(first_window, bar_fingerprint=SOURCE_FINGERPRINT, spec=SPEC)

    first = result.samples[0]
    assert first.sample.image_checksum == expected_image.image_checksum
    assert first.image.png_bytes == expected_image.png_bytes
    assert first.image.png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert first.sample.source_bar_fingerprint == SOURCE_FINGERPRINT
    assert first.image.window_first_event_id == first_window[0].first_event_id


def test_last_window_without_full_horizon_is_pending() -> None:
    result = materialize(bar_count=12, observation_window_bars=2, horizon_bars=2)
    assert result.samples[-1].sample.label_status == PENDING_HORIZON
    assert result.samples[-1].sample.label_available_at is None
    for item in result.samples[:-1]:
        assert item.sample.label_status == "labeled"


def test_split_assignment_covers_train_purged_and_validation() -> None:
    train_end_at = (BASE_TIME + timedelta(minutes=5)).isoformat()
    validation_end_at = (BASE_TIME + timedelta(minutes=11)).isoformat()
    result = materialize(
        bar_count=12, observation_window_bars=2, horizon_bars=2,
        train_end_at=train_end_at, validation_end_at=validation_end_at,
    )
    split_ids = [item.sample.split_id for item in result.samples]
    assert split_ids == [TRAIN, PURGED_BOUNDARY_OVERLAP, PURGED_BOUNDARY_OVERLAP, VALIDATION, PURGED_BOUNDARY_OVERLAP, PENDING_HORIZON]


def test_all_labeled_samples_are_holdout_when_boundaries_precede_all_bars() -> None:
    train_end_at = (BASE_TIME - timedelta(minutes=10)).isoformat()
    validation_end_at = (BASE_TIME - timedelta(minutes=5)).isoformat()
    result = materialize(
        bar_count=12, observation_window_bars=2, horizon_bars=2,
        train_end_at=train_end_at, validation_end_at=validation_end_at,
    )
    labeled = [item for item in result.samples if item.sample.label_status == "labeled"]
    assert labeled
    assert all(item.sample.split_id == HOLDOUT for item in labeled)


def test_all_labeled_samples_are_train_when_boundaries_follow_all_bars() -> None:
    result = materialize(bar_count=12, observation_window_bars=2, horizon_bars=2)
    labeled = [item for item in result.samples if item.sample.label_status == "labeled"]
    assert labeled
    assert all(item.sample.split_id == TRAIN for item in labeled)


def test_manifest_and_dataset_fingerprint_are_produced() -> None:
    result = materialize(bar_count=12, observation_window_bars=2)
    assert result.manifest.total_samples == len(result.samples)
    assert result.dataset_fingerprint.startswith("sha256:")
    assert result.manifest.fingerprint.startswith("sha256:")


def test_deterministic_for_identical_input() -> None:
    first = materialize(bar_count=12, observation_window_bars=2)
    second = materialize(bar_count=12, observation_window_bars=2)
    assert first.dataset_fingerprint == second.dataset_fingerprint
    assert first.manifest.fingerprint == second.manifest.fingerprint
    first_identities = [(s.sample.sample_id, s.sample.image_checksum, s.sample.split_id) for s in first.samples]
    second_identities = [(s.sample.sample_id, s.sample.image_checksum, s.sample.split_id) for s in second.samples]
    assert first_identities == second_identities


def test_different_render_spec_changes_dataset_fingerprint() -> None:
    baseline = materialize(bar_count=12, observation_window_bars=2)
    different = materialize_visual_dataset(
        bars(12), bar_fingerprint=SOURCE_FINGERPRINT, source_bar_fingerprint=SOURCE_FINGERPRINT,
        render_spec=RenderSpec(width=40, height=20, padding_top=1, padding_bottom=1, padding_left=1, padding_right=1),
        label_spec=LabelSpec(2, 10.0, -10.0), observation_window_bars=2,
        train_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(days=2)).isoformat(),
    )
    assert baseline.dataset_fingerprint != different.dataset_fingerprint
    assert baseline.render_spec_id != different.render_spec_id
