from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.database.connection import get_connection


class VisualBaselineModelConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedVisualBaselineModel:
    experiment_id: str
    architecture_id: str
    version: str
    dataset_fingerprint: str
    preprocessing_checksum: str
    model_spec_id: str
    training_spec_id: str
    model_checksum: str
    log_checksum: str
    created_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _row_to_model(row: object) -> PersistedVisualBaselineModel:
    return PersistedVisualBaselineModel(
        experiment_id=row["experiment_id"], architecture_id=row["architecture_id"],
        version=row["version"], dataset_fingerprint=row["dataset_fingerprint"],
        preprocessing_checksum=row["preprocessing_checksum"], model_spec_id=row["model_spec_id"],
        training_spec_id=row["training_spec_id"], model_checksum=row["model_checksum"],
        log_checksum=row["log_checksum"], created_at=row["created_at"],
    )


def persist_baseline_model(
    *,
    experiment_id: str,
    architecture_id: str,
    version: str,
    dataset_fingerprint: str,
    preprocessing_checksum: str,
    model_spec_id: str,
    training_spec_id: str,
    model_checksum: str,
    log_checksum: str,
) -> PersistedVisualBaselineModel:
    """Idempotent by experiment_id: re-attempting training with an
    IDENTICAL resulting model (same `model_checksum`) returns the existing
    record. A DIFFERENT checksum for an experiment that already has one is
    refused -- once a baseline model has been recorded for an experiment,
    it cannot silently change, mirroring
    `visual_training_repository.persist_training_configuration`'s
    conflict rule.
    """
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    now = datetime.now(UTC).isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM visual_baseline_models WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        if existing is not None:
            if existing["model_checksum"] != model_checksum:
                raise VisualBaselineModelConflictError(
                    "experiment already has a baseline model with a different checksum"
                )
            return _row_to_model(existing)

        connection.execute(
            """
            INSERT INTO visual_baseline_models
            (
                experiment_id, architecture_id, version, dataset_fingerprint, preprocessing_checksum,
                model_spec_id, training_spec_id, model_checksum, log_checksum, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_experiment_id, architecture_id, version, dataset_fingerprint,
                preprocessing_checksum, model_spec_id, training_spec_id, model_checksum,
                log_checksum, now,
            ),
        )

    return PersistedVisualBaselineModel(
        experiment_id=normalized_experiment_id, architecture_id=architecture_id, version=version,
        dataset_fingerprint=dataset_fingerprint, preprocessing_checksum=preprocessing_checksum,
        model_spec_id=model_spec_id, training_spec_id=training_spec_id,
        model_checksum=model_checksum, log_checksum=log_checksum, created_at=now,
    )


def get_baseline_model(experiment_id: str) -> PersistedVisualBaselineModel | None:
    normalized = _required_text(experiment_id, "experiment_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM visual_baseline_models WHERE experiment_id = ?;", (normalized,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_model(row)
