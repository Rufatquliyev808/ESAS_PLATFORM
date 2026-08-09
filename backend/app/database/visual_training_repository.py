from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json

from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.database.connection import get_connection


class VisualTrainingConfigConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedVisualTrainingConfig:
    experiment_id: str
    model_spec_id: str
    training_spec_id: str
    training_configuration_checksum: str
    dataset_fingerprint: str
    created_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def persist_training_configuration(
    *,
    experiment_id: str,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
    model_spec_id: str,
    training_spec_id: str,
    training_configuration_checksum: str,
    dataset_fingerprint: str,
) -> PersistedVisualTrainingConfig:
    """Idempotent by experiment_id: re-attempting training with an IDENTICAL
    configuration (same `training_configuration_checksum`) returns the
    existing record. A DIFFERENT checksum for an experiment that already has
    one is refused -- once an experiment has been frozen for training, its
    configuration cannot silently change, mirroring
    `visual_dataset_repository.persist_dataset_manifest`'s conflict rule.
    """
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    now = datetime.now(UTC).isoformat(timespec="microseconds")
    model_spec_json = json.dumps(asdict(model_spec), sort_keys=True, separators=(",", ":"))
    training_spec_json = json.dumps(asdict(training_spec), sort_keys=True, separators=(",", ":"))

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM visual_training_configs WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        if existing is not None:
            if existing["training_configuration_checksum"] != training_configuration_checksum:
                raise VisualTrainingConfigConflictError(
                    "experiment already has a training configuration with a different checksum"
                )
            return PersistedVisualTrainingConfig(
                experiment_id=existing["experiment_id"],
                model_spec_id=existing["model_spec_id"],
                training_spec_id=existing["training_spec_id"],
                training_configuration_checksum=existing["training_configuration_checksum"],
                dataset_fingerprint=existing["dataset_fingerprint"],
                created_at=existing["created_at"],
            )

        connection.execute(
            """
            INSERT INTO visual_training_configs
            (
                experiment_id, model_spec_id, model_spec_json, training_spec_id,
                training_spec_json, training_configuration_checksum, dataset_fingerprint, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_experiment_id, model_spec_id, model_spec_json, training_spec_id,
                training_spec_json, training_configuration_checksum, dataset_fingerprint, now,
            ),
        )

    return PersistedVisualTrainingConfig(
        experiment_id=normalized_experiment_id, model_spec_id=model_spec_id,
        training_spec_id=training_spec_id,
        training_configuration_checksum=training_configuration_checksum,
        dataset_fingerprint=dataset_fingerprint, created_at=now,
    )


def get_training_configuration(experiment_id: str) -> PersistedVisualTrainingConfig | None:
    normalized = _required_text(experiment_id, "experiment_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM visual_training_configs WHERE experiment_id = ?;", (normalized,),
        ).fetchone()
    if row is None:
        return None
    return PersistedVisualTrainingConfig(
        experiment_id=row["experiment_id"], model_spec_id=row["model_spec_id"],
        training_spec_id=row["training_spec_id"],
        training_configuration_checksum=row["training_configuration_checksum"],
        dataset_fingerprint=row["dataset_fingerprint"], created_at=row["created_at"],
    )
