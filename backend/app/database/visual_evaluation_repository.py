from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.database.connection import get_connection


class VisualEvaluationConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedVisualEvaluation:
    experiment_id: str
    model_checksum: str
    outcome: str
    holdout_sample_count: int
    holdout_accuracy: float
    majority_baseline_accuracy: float
    evaluation_checksum: str
    created_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _row_to_evaluation(row: object) -> PersistedVisualEvaluation:
    return PersistedVisualEvaluation(
        experiment_id=row["experiment_id"], model_checksum=row["model_checksum"],
        outcome=row["outcome"], holdout_sample_count=row["holdout_sample_count"],
        holdout_accuracy=row["holdout_accuracy"],
        majority_baseline_accuracy=row["majority_baseline_accuracy"],
        evaluation_checksum=row["evaluation_checksum"], created_at=row["created_at"],
    )


def persist_evaluation(
    *,
    experiment_id: str,
    model_checksum: str,
    outcome: str,
    holdout_sample_count: int,
    holdout_accuracy: float,
    majority_baseline_accuracy: float,
    evaluation_checksum: str,
) -> PersistedVisualEvaluation:
    """Idempotent by experiment_id: re-attempting evaluation with an
    IDENTICAL result (same `evaluation_checksum`) returns the existing
    record. A DIFFERENT checksum for an experiment that already has one is
    refused -- once an evaluation has been recorded, it cannot silently
    change, mirroring `visual_baseline_model_repository.persist_baseline_model`'s
    conflict rule.
    """
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    now = datetime.now(UTC).isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM visual_evaluations WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        if existing is not None:
            if existing["evaluation_checksum"] != evaluation_checksum:
                raise VisualEvaluationConflictError(
                    "experiment already has an evaluation with a different checksum"
                )
            return _row_to_evaluation(existing)

        connection.execute(
            """
            INSERT INTO visual_evaluations
            (
                experiment_id, model_checksum, outcome, holdout_sample_count, holdout_accuracy,
                majority_baseline_accuracy, evaluation_checksum, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_experiment_id, model_checksum, outcome, holdout_sample_count,
                holdout_accuracy, majority_baseline_accuracy, evaluation_checksum, now,
            ),
        )

    return PersistedVisualEvaluation(
        experiment_id=normalized_experiment_id, model_checksum=model_checksum, outcome=outcome,
        holdout_sample_count=holdout_sample_count, holdout_accuracy=holdout_accuracy,
        majority_baseline_accuracy=majority_baseline_accuracy, evaluation_checksum=evaluation_checksum,
        created_at=now,
    )


def get_evaluation(experiment_id: str) -> PersistedVisualEvaluation | None:
    normalized = _required_text(experiment_id, "experiment_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM visual_evaluations WHERE experiment_id = ?;", (normalized,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_evaluation(row)
