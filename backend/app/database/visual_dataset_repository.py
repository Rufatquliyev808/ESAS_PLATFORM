from dataclasses import dataclass
from datetime import UTC, datetime
import json

from backend.app.analysis.visual_dataset import DatasetManifest, VisualSample
from backend.app.database.connection import get_connection


class VisualDatasetManifestConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedVisualDatasetManifest:
    experiment_id: str
    dataset_fingerprint: str
    manifest_fingerprint: str
    total_samples: int
    materialized_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def persist_materialized_samples(
    experiment_id: str, samples: tuple[VisualSample, ...],
) -> int:
    """Idempotently persist per-sample lineage rows for a materialization.
    `sample_id` is a deterministic content hash (see `visual_dataset.py`),
    so re-materializing identical input re-derives the same ids -- `INSERT
    OR IGNORE` makes re-running materialization safe rather than failing on
    duplicate rows. Does not store raw PNG bytes -- image storage location
    (filesystem/blob) is a deliberately separate, not-yet-made decision;
    this table only carries the deterministic lineage/checksum record.
    """
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    now = datetime.now(UTC).isoformat(timespec="microseconds")
    inserted = 0
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        for sample in samples:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO visual_dataset_samples
                (
                    sample_id, experiment_id, symbol, timeframe, source_bar_fingerprint,
                    render_spec_id, image_checksum, observation_window_start_at,
                    observation_end_at, label_spec_id, label_available_at, label_value,
                    label_status, quality_flags_json, split_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    sample.sample_id, normalized_experiment_id, sample.symbol, sample.timeframe,
                    sample.source_bar_fingerprint, sample.render_spec_id, sample.image_checksum,
                    sample.observation_window_start_at, sample.observation_end_at,
                    sample.label_spec_id, sample.label_available_at, sample.label_value,
                    sample.label_status, json.dumps(list(sample.quality_flags)), sample.split_id, now,
                ),
            )
            inserted += cursor.rowcount
    return inserted


def persist_dataset_manifest(
    experiment_id: str, manifest: DatasetManifest, *, dataset_fingerprint: str,
) -> PersistedVisualDatasetManifest:
    """Idempotent by (experiment_id, dataset_fingerprint): re-materializing
    identical input returns the existing manifest record. A DIFFERENT
    dataset_fingerprint for an experiment that already has a manifest is a
    real integrity conflict (the frozen render/label spec and bar
    fingerprint should make this impossible) and is refused rather than
    silently overwritten.
    """
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    normalized_fingerprint = _required_text(dataset_fingerprint, "dataset_fingerprint")
    now = datetime.now(UTC).isoformat(timespec="microseconds")
    entries_json = json.dumps(
        [
            {
                "symbol": entry.symbol, "timeframe": entry.timeframe, "split_id": entry.split_id,
                "label_status": entry.label_status, "has_quality_flags": entry.has_quality_flags,
                "count": entry.count,
            }
            for entry in manifest.entries
        ]
    )

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM visual_dataset_manifests WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        if existing is not None:
            if existing["dataset_fingerprint"] != normalized_fingerprint:
                raise VisualDatasetManifestConflictError(
                    "experiment already has a manifest with a different dataset_fingerprint"
                )
            return PersistedVisualDatasetManifest(
                experiment_id=existing["experiment_id"],
                dataset_fingerprint=existing["dataset_fingerprint"],
                manifest_fingerprint=existing["manifest_fingerprint"],
                total_samples=existing["total_samples"],
                materialized_at=existing["materialized_at"],
            )

        connection.execute(
            """
            INSERT INTO visual_dataset_manifests
            (experiment_id, dataset_fingerprint, manifest_fingerprint, total_samples, entries_json, materialized_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_experiment_id, normalized_fingerprint, manifest.fingerprint,
                manifest.total_samples, entries_json, now,
            ),
        )

    return PersistedVisualDatasetManifest(
        experiment_id=normalized_experiment_id, dataset_fingerprint=normalized_fingerprint,
        manifest_fingerprint=manifest.fingerprint, total_samples=manifest.total_samples,
        materialized_at=now,
    )


def get_dataset_manifest(experiment_id: str) -> PersistedVisualDatasetManifest | None:
    normalized = _required_text(experiment_id, "experiment_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM visual_dataset_manifests WHERE experiment_id = ?;", (normalized,),
        ).fetchone()
    if row is None:
        return None
    return PersistedVisualDatasetManifest(
        experiment_id=row["experiment_id"], dataset_fingerprint=row["dataset_fingerprint"],
        manifest_fingerprint=row["manifest_fingerprint"], total_samples=row["total_samples"],
        materialized_at=row["materialized_at"],
    )


def count_dataset_samples(experiment_id: str) -> int:
    normalized = _required_text(experiment_id, "experiment_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM visual_dataset_samples WHERE experiment_id = ?;",
            (normalized,),
        ).fetchone()
    return row["n"]
