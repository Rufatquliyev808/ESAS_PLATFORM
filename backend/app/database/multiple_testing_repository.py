from dataclasses import dataclass
from datetime import UTC, datetime
import secrets

from backend.app.database.connection import get_connection


@dataclass(frozen=True)
class MultipleTestingTrial:
    trial_id: str
    family_key: str
    candidate_id: str
    backtest_id: str
    hypothesis_id: str
    actor: str
    family_sequence: int
    registered_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _new_trial_id() -> str:
    return f"trial_{secrets.token_urlsafe(18)}"


def _row_to_trial(row: object) -> MultipleTestingTrial:
    return MultipleTestingTrial(
        trial_id=row["trial_id"], family_key=row["family_key"], candidate_id=row["candidate_id"],
        backtest_id=row["backtest_id"], hypothesis_id=row["hypothesis_id"], actor=row["actor"],
        family_sequence=row["family_sequence"], registered_at=row["registered_at"],
    )


def register_trial(
    *, family_key: str, candidate_id: str, backtest_id: str, hypothesis_id: str, actor: str,
) -> MultipleTestingTrial:
    """Idempotently register one backtest run as a member of its family's multiple-testing budget.

    family_key scopes "same data" to the replay session the backtest ran
    against, per the Phase 3/Phase 4 contracts: every hypothesis/parameter
    variant tested against the same dataset must be counted here, whether
    or not it is ever classified -- otherwise the correction could be
    dodged by simply not classifying unfavorable runs. The caller
    (evaluate_replay_pattern_candidate_backtest) registers unconditionally
    on every backtest run for exactly this reason.
    """
    normalized_family = _required_text(family_key, "family_key")
    normalized_candidate = _required_text(candidate_id, "candidate_id")
    normalized_backtest = _required_text(backtest_id, "backtest_id")
    normalized_hypothesis = _required_text(hypothesis_id, "hypothesis_id")
    normalized_actor = _required_text(actor, "actor")
    now = datetime.now(UTC).isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM multiple_testing_trials WHERE backtest_id = ?;",
            (normalized_backtest,),
        ).fetchone()
        if existing is not None:
            return _row_to_trial(existing)
        next_sequence = connection.execute(
            "SELECT COALESCE(MAX(family_sequence), 0) + 1 FROM multiple_testing_trials WHERE family_key = ?;",
            (normalized_family,),
        ).fetchone()[0]
        trial_id = _new_trial_id()
        connection.execute(
            """
            INSERT INTO multiple_testing_trials
            (trial_id, family_key, candidate_id, backtest_id, hypothesis_id, actor, family_sequence, registered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                trial_id, normalized_family, normalized_candidate, normalized_backtest,
                normalized_hypothesis, normalized_actor, next_sequence, now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM multiple_testing_trials WHERE trial_id = ?;", (trial_id,),
        ).fetchone()
    return _row_to_trial(row)


def count_family_trials(family_key: str) -> int:
    normalized = _required_text(family_key, "family_key")
    with get_connection() as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM multiple_testing_trials WHERE family_key = ?;",
            (normalized,),
        ).fetchone()[0]


def list_family_trials(family_key: str) -> tuple[MultipleTestingTrial, ...]:
    normalized = _required_text(family_key, "family_key")
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM multiple_testing_trials WHERE family_key = ? ORDER BY family_sequence ASC;",
            (normalized,),
        ).fetchall()
    return tuple(_row_to_trial(row) for row in rows)
