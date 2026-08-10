from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json

from backend.app.database.connection import get_connection


TRIAL_ID_VERSION = "1.0.0"


class VisualTestingTrialConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegisteredTrial:
    trial_id: str
    testing_family_id: str
    experiment_id: str
    model_spec_id: str
    training_spec_id: str
    registered_at: str


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def compute_trial_id(*, testing_family_id: str, model_spec_id: str, training_spec_id: str) -> str:
    """Deterministic: the same family + model spec + training spec always
    identifies the same trial, so re-registering an already-known trial
    (e.g. an idempotent retry of training) is a no-op rather than a new row.
    """
    payload = {
        "model_spec_id": model_spec_id, "testing_family_id": testing_family_id,
        "training_spec_id": training_spec_id, "version": TRIAL_ID_VERSION,
    }
    return f"sha256:{sha256(_canonical_json(payload)).hexdigest()}"


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _row_to_trial(row: object) -> RegisteredTrial:
    return RegisteredTrial(
        trial_id=row["trial_id"], testing_family_id=row["testing_family_id"],
        experiment_id=row["experiment_id"], model_spec_id=row["model_spec_id"],
        training_spec_id=row["training_spec_id"], registered_at=row["registered_at"],
    )


def register_trial(
    *, testing_family_id: str, experiment_id: str, model_spec_id: str, training_spec_id: str,
) -> RegisteredTrial:
    """Registers a trial BEFORE its result is known -- callers must call
    this ahead of fitting/evaluating a model, never after. Idempotent for
    an identical (family, model_spec_id, training_spec_id): returns the
    existing row rather than inflating the family's trial count. A
    DIFFERENT `experiment_id` attempting to reuse the same trial identity
    is refused -- since `experiment_id` is itself deterministic from
    dataset configuration, this should be unreachable in practice and
    signals a genuine data-integrity problem if it ever happens.
    """
    normalized_family_id = _required_text(testing_family_id, "testing_family_id")
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    normalized_model_spec_id = _required_text(model_spec_id, "model_spec_id")
    normalized_training_spec_id = _required_text(training_spec_id, "training_spec_id")
    trial_id = compute_trial_id(
        testing_family_id=normalized_family_id, model_spec_id=normalized_model_spec_id,
        training_spec_id=normalized_training_spec_id,
    )
    now = datetime.now(UTC).isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM visual_testing_trials WHERE trial_id = ?;", (trial_id,),
        ).fetchone()
        if existing is not None:
            if existing["experiment_id"] != normalized_experiment_id:
                raise VisualTestingTrialConflictError(
                    "trial already registered for a different experiment_id"
                )
            return _row_to_trial(existing)

        connection.execute(
            """
            INSERT INTO visual_testing_trials
            (trial_id, testing_family_id, experiment_id, model_spec_id, training_spec_id, registered_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (trial_id, normalized_family_id, normalized_experiment_id, normalized_model_spec_id,
             normalized_training_spec_id, now),
        )

    return RegisteredTrial(
        trial_id=trial_id, testing_family_id=normalized_family_id, experiment_id=normalized_experiment_id,
        model_spec_id=normalized_model_spec_id, training_spec_id=normalized_training_spec_id,
        registered_at=now,
    )


def get_trial(trial_id: str) -> RegisteredTrial | None:
    normalized = _required_text(trial_id, "trial_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM visual_testing_trials WHERE trial_id = ?;", (normalized,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_trial(row)


def trial_is_registered(*, testing_family_id: str, model_spec_id: str, training_spec_id: str) -> bool:
    trial_id = compute_trial_id(
        testing_family_id=testing_family_id, model_spec_id=model_spec_id, training_spec_id=training_spec_id,
    )
    return get_trial(trial_id) is not None


def count_family_trials(testing_family_id: str) -> int:
    normalized = _required_text(testing_family_id, "testing_family_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM visual_testing_trials WHERE testing_family_id = ?;",
            (normalized,),
        ).fetchone()
    return row["n"]
