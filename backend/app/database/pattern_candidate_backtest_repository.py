from dataclasses import dataclass
from datetime import UTC, datetime
import json
import secrets

from backend.app.database.connection import get_connection
from backend.app.database.pattern_candidate_repository import (
    PatternCandidateConflictError,
    PatternCandidateNotFoundError,
    PatternCandidateOwnershipError,
)


class PatternCandidateBacktestNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class PersistedPatternCandidateBacktest:
    backtest_id: str
    candidate_id: str
    created_by: str
    horizon_bars: int
    cost_parameters: dict[str, object]
    result: dict[str, object]
    fingerprint: str
    created_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _new_backtest_id() -> str:
    return f"pcb_{secrets.token_urlsafe(18)}"


def _row_to_backtest(row: object) -> PersistedPatternCandidateBacktest:
    return PersistedPatternCandidateBacktest(
        backtest_id=row["backtest_id"],
        candidate_id=row["candidate_id"],
        created_by=row["created_by"],
        horizon_bars=row["horizon_bars"],
        cost_parameters=json.loads(row["cost_parameters_json"]),
        result=json.loads(row["result_json"]),
        fingerprint=row["fingerprint"],
        created_at=row["created_at"],
    )


def store_pattern_candidate_backtest(
    *,
    candidate_id: str,
    actor: str,
    actor_role: str,
    horizon_bars: int,
    cost_parameters: dict[str, object],
    result: dict[str, object],
    fingerprint: str,
) -> PersistedPatternCandidateBacktest:
    """Append an immutable backtest run and move a fresh candidate to "evaluated".

    Only "registered" or already-"evaluated" candidates can be backtested.
    The lifecycle transitions registered -> evaluated on the first run;
    later re-runs stay in "evaluated" but still append a new backtest row
    and audit entry, so no historical result is ever silently replaced.
    """
    normalized_candidate_id = _required_text(candidate_id, "candidate_id")
    normalized_actor = _required_text(actor, "actor")
    normalized_role = _required_text(actor_role, "actor_role")
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be at least 1")

    now = datetime.now(UTC).isoformat(timespec="microseconds")
    backtest_id = _new_backtest_id()
    cost_json = json.dumps(cost_parameters, sort_keys=True, separators=(",", ":"))
    result_json = json.dumps(result, sort_keys=True, separators=(",", ":"))

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = connection.execute(
            "SELECT * FROM pattern_candidates WHERE candidate_id = ?;",
            (normalized_candidate_id,),
        ).fetchone()
        if row is None:
            raise PatternCandidateNotFoundError("pattern candidate was not found")
        if row["created_by"] != normalized_actor:
            raise PatternCandidateOwnershipError(
                "pattern candidate belongs to another user"
            )
        if row["lifecycle_state"] not in ("registered", "evaluated"):
            raise PatternCandidateConflictError(
                f"cannot backtest from state {row['lifecycle_state']}"
            )

        connection.execute(
            """
            INSERT INTO pattern_candidate_backtests
            (
                backtest_id, candidate_id, created_by, horizon_bars,
                cost_parameters_json, result_json, fingerprint, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                backtest_id, normalized_candidate_id, normalized_actor, horizon_bars,
                cost_json, result_json, fingerprint, now,
            ),
        )

        previous_state = row["lifecycle_state"]
        if previous_state == "registered":
            updated = connection.execute(
                """
                UPDATE pattern_candidates
                SET lifecycle_state = 'evaluated',
                    state_version = state_version + 1,
                    updated_at = ?
                WHERE candidate_id = ? AND state_version = ?;
                """,
                (now, normalized_candidate_id, row["state_version"]),
            )
            if updated.rowcount != 1:
                raise PatternCandidateConflictError(
                    "pattern candidate changed during transition"
                )
            action = "evaluate"
        else:
            action = "re_evaluate"

        connection.execute(
            """
            INSERT INTO pattern_candidate_audit
            (candidate_id, actor, actor_role, action, previous_state, next_state, occurred_at)
            VALUES (?, ?, ?, ?, ?, 'evaluated', ?);
            """,
            (normalized_candidate_id, normalized_actor, normalized_role, action, previous_state, now),
        )
        result_row = connection.execute(
            "SELECT * FROM pattern_candidate_backtests WHERE backtest_id = ?;",
            (backtest_id,),
        ).fetchone()
    return _row_to_backtest(result_row)


def get_latest_pattern_candidate_backtest(candidate_id: str) -> PersistedPatternCandidateBacktest:
    normalized = _required_text(candidate_id, "candidate_id")
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM pattern_candidate_backtests
            WHERE candidate_id = ?
            ORDER BY created_at DESC, backtest_id DESC
            LIMIT 1;
            """,
            (normalized,),
        ).fetchone()
    if row is None:
        raise PatternCandidateBacktestNotFoundError("pattern candidate has no backtest yet")
    return _row_to_backtest(row)
