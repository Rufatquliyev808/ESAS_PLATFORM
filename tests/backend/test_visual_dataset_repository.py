from pathlib import Path

import pytest

from backend.app.analysis.visual_dataset import DatasetManifestEntry, VisualSample
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.visual_dataset_repository import (
    VisualDatasetManifestConflictError,
    count_dataset_samples,
    get_dataset_manifest,
    persist_dataset_manifest,
    persist_materialized_samples,
)
from backend.app.database.visual_experiment_repository import register_visual_experiment
from backend.app.analysis.visual_render import RenderSpec
from backend.app.analysis.visual_label import LabelSpec


def _prepare(database_path: Path) -> str:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO replay_sessions
            (
                session_id, created_by, symbol, start_at, end_at, mode, state,
                replay_contract_version, quality_rule_version, dataset_tick_count,
                dataset_fingerprint, processed_ticks, created_at, updated_at, completed_at
            ) VALUES ('rps_test', 'TEST-USER', 'GOLD', '2026-08-05T00:00:00+00:00', '2026-08-05T01:00:00+00:00',
                      'max_speed', 'completed', '1.0', '1.0', 10, 'sha256:dataset', 10,
                      '2026-08-05T00:00:00+00:00', '2026-08-05T00:00:00+00:00', '2026-08-05T00:00:00+00:00');
            """
        )
    experiment = register_visual_experiment(
        created_by="TEST-USER", actor_role="operator", replay_session_id="rps_test",
        symbol="GOLD", timeframe="M1", source_bar_fingerprint="sha256:bars",
        render_spec=RenderSpec(), label_spec=LabelSpec(10, 10.0, -10.0),
        observation_window_bars=64, train_end_at="2026-08-06T00:00:00+00:00",
        validation_end_at="2026-08-07T00:00:00+00:00",
    )
    return experiment.experiment_id


def _sample(sample_id: str, split_id: str = "train") -> VisualSample:
    return VisualSample(
        version="1.0.0", sample_id=sample_id, symbol="GOLD", timeframe="M1",
        source_bar_fingerprint="sha256:bars", render_spec_id="sha256:render",
        image_checksum="sha256:image", observation_window_start_at="2026-08-05T00:00:00+00:00",
        observation_end_at="2026-08-05T00:10:00+00:00", label_spec_id="sha256:label",
        label_available_at="2026-08-05T00:20:00+00:00", label_value="up", label_status="labeled",
        quality_flags=(), split_id=split_id,
    )


def _manifest(fingerprint: str = "sha256:manifest-fingerprint"):
    from backend.app.analysis.visual_dataset import DatasetManifest
    entries = (DatasetManifestEntry("GOLD", "M1", "train", "labeled", False, 2),)
    return DatasetManifest(version="1.0.0", total_samples=2, entries=entries, fingerprint=fingerprint)


def test_persist_materialized_samples_inserts_rows(isolated_database: Path) -> None:
    experiment_id = _prepare(isolated_database)
    samples = (_sample("s1"), _sample("s2"))
    inserted = persist_materialized_samples(experiment_id, samples)
    assert inserted == 2
    assert count_dataset_samples(experiment_id) == 2


def test_persist_materialized_samples_is_idempotent(isolated_database: Path) -> None:
    experiment_id = _prepare(isolated_database)
    samples = (_sample("s1"), _sample("s2"))
    persist_materialized_samples(experiment_id, samples)
    second_inserted = persist_materialized_samples(experiment_id, samples)
    assert second_inserted == 0
    assert count_dataset_samples(experiment_id) == 2


def test_persist_dataset_manifest_stores_and_returns(isolated_database: Path) -> None:
    experiment_id = _prepare(isolated_database)
    manifest = _manifest()
    result = persist_dataset_manifest(experiment_id, manifest, dataset_fingerprint="sha256:dataset-fp")
    assert result.dataset_fingerprint == "sha256:dataset-fp"
    assert result.total_samples == 2

    fetched = get_dataset_manifest(experiment_id)
    assert fetched is not None
    assert fetched.dataset_fingerprint == "sha256:dataset-fp"


def test_persist_dataset_manifest_is_idempotent_for_same_fingerprint(isolated_database: Path) -> None:
    experiment_id = _prepare(isolated_database)
    manifest = _manifest()
    first = persist_dataset_manifest(experiment_id, manifest, dataset_fingerprint="sha256:dataset-fp")
    second = persist_dataset_manifest(experiment_id, manifest, dataset_fingerprint="sha256:dataset-fp")
    assert first == second


def test_persist_dataset_manifest_conflicts_on_different_fingerprint(isolated_database: Path) -> None:
    experiment_id = _prepare(isolated_database)
    manifest = _manifest()
    persist_dataset_manifest(experiment_id, manifest, dataset_fingerprint="sha256:dataset-fp-a")
    with pytest.raises(VisualDatasetManifestConflictError):
        persist_dataset_manifest(experiment_id, manifest, dataset_fingerprint="sha256:dataset-fp-b")


def test_get_dataset_manifest_returns_none_when_absent(isolated_database: Path) -> None:
    experiment_id = _prepare(isolated_database)
    assert get_dataset_manifest(experiment_id) is None


def test_count_dataset_samples_is_zero_when_none_persisted(isolated_database: Path) -> None:
    experiment_id = _prepare(isolated_database)
    assert count_dataset_samples(experiment_id) == 0
