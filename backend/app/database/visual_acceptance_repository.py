from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.database.connection import get_connection


class VisualAcceptanceConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedVisualAcceptanceDecision:
    experiment_id: str
    evaluation_checksum: str
    decision: str
    holdout_accuracy: float
    majority_baseline_accuracy: float
    improvement_over_baseline: float
    decision_checksum: str
    created_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _row_to_decision(row: object) -> PersistedVisualAcceptanceDecision:
    return PersistedVisualAcceptanceDecision(
        experiment_id=row["experiment_id"], evaluation_checksum=row["evaluation_checksum"],
        decision=row["decision"], holdout_accuracy=row["holdout_accuracy"],
        majority_baseline_accuracy=row["majority_baseline_accuracy"],
        improvement_over_baseline=row["improvement_over_baseline"],
        decision_checksum=row["decision_checksum"], created_at=row["created_at"],
    )


def persist_acceptance_decision(
    *,
    experiment_id: str,
    evaluation_checksum: str,
    decision: str,
    holdout_accuracy: float,
    majority_baseline_accuracy: float,
    improvement_over_baseline: float,
    decision_checksum: str,
) -> PersistedVisualAcceptanceDecision:
    """Idempotent by experiment_id: re-attempting the decision with an
    IDENTICAL result (same `decision_checksum`) returns the existing
    record. A DIFFERENT checksum for an experiment that already has one is
    refused -- mirrors `visual_evaluation_repository.persist_evaluation`'s
    conflict rule.
    """
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    now = datetime.now(UTC).isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM visual_acceptance_decisions WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        if existing is not None:
            if existing["decision_checksum"] != decision_checksum:
                raise VisualAcceptanceConflictError(
                    "experiment already has an acceptance decision with a different checksum"
                )
            return _row_to_decision(existing)

        connection.execute(
            """
            INSERT INTO visual_acceptance_decisions
            (
                experiment_id, evaluation_checksum, decision, holdout_accuracy,
                majority_baseline_accuracy, improvement_over_baseline, decision_checksum, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                normalized_experiment_id, evaluation_checksum, decision, holdout_accuracy,
                majority_baseline_accuracy, improvement_over_baseline, decision_checksum, now,
            ),
        )

    return PersistedVisualAcceptanceDecision(
        experiment_id=normalized_experiment_id, evaluation_checksum=evaluation_checksum, decision=decision,
        holdout_accuracy=holdout_accuracy, majority_baseline_accuracy=majority_baseline_accuracy,
        improvement_over_baseline=improvement_over_baseline, decision_checksum=decision_checksum,
        created_at=now,
    )


def get_acceptance_decision(experiment_id: str) -> PersistedVisualAcceptanceDecision | None:
    normalized = _required_text(experiment_id, "experiment_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM visual_acceptance_decisions WHERE experiment_id = ?;", (normalized,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_decision(row)
