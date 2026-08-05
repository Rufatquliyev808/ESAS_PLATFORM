from dataclasses import dataclass
from datetime import UTC, datetime
import json

from backend.app.database.connection import get_connection


class PatternCandidateNotFoundError(LookupError):
    pass


class PatternCandidateOwnershipError(PermissionError):
    pass


class PatternCandidateConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PersistedPatternCandidate:
    candidate_id: str
    created_by: str
    replay_session_id: str
    hypothesis_id: str
    hypothesis_version: str
    family: str
    direction: str
    condition_state: str
    observed_at: str | None
    evidence: dict[str, object]
    pattern_candidate_version: str
    hypothesis_registry_version: str
    source_fingerprint: str
    timeframe: str
    parameters: dict[str, object]
    lifecycle_state: str
    state_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PatternCandidateListPosition:
    created_at: str
    candidate_id: str


@dataclass(frozen=True)
class PatternCandidatePage:
    items: tuple[PersistedPatternCandidate, ...]
    next_position: PatternCandidateListPosition | None


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _row_to_candidate(row: object) -> PersistedPatternCandidate:
    return PersistedPatternCandidate(
        candidate_id=row["candidate_id"],
        created_by=row["created_by"],
        replay_session_id=row["replay_session_id"],
        hypothesis_id=row["hypothesis_id"],
        hypothesis_version=row["hypothesis_version"],
        family=row["family"],
        direction=row["direction"],
        condition_state=row["condition_state"],
        observed_at=row["observed_at"],
        evidence=json.loads(row["evidence_json"]),
        pattern_candidate_version=row["pattern_candidate_version"],
        hypothesis_registry_version=row["hypothesis_registry_version"],
        source_fingerprint=row["source_fingerprint"],
        timeframe=row["timeframe"],
        parameters=json.loads(row["parameters_json"]),
        lifecycle_state=row["lifecycle_state"],
        state_version=row["state_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def register_pattern_candidate(
    *,
    created_by: str,
    actor_role: str,
    replay_session_id: str,
    candidate_id: str,
    hypothesis_id: str,
    hypothesis_version: str,
    family: str,
    direction: str,
    condition_state: str,
    observed_at: str | None,
    evidence: dict[str, object],
    pattern_candidate_version: str,
    hypothesis_registry_version: str,
    source_fingerprint: str,
    timeframe: str,
    parameters: dict[str, object],
) -> PersistedPatternCandidate:
    """Persist a draft candidate slot as an immutable "registered" record.

    Registration is idempotent by candidate_id: retrying with the exact same
    deterministic candidate returns the existing record instead of inserting
    a duplicate. Only already-confirmed slots can be registered.
    """
    normalized_creator = _required_text(created_by, "created_by")
    normalized_role = _required_text(actor_role, "actor_role")
    normalized_session_id = _required_text(replay_session_id, "replay_session_id")
    normalized_candidate_id = _required_text(candidate_id, "candidate_id")
    if condition_state != "candidate_confirmed":
        raise ValueError("only candidate_confirmed slots can be registered")

    evidence_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    parameters_json = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    now = datetime.now(UTC).isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM pattern_candidates WHERE candidate_id = ?;",
            (normalized_candidate_id,),
        ).fetchone()
        if existing is not None:
            if existing["created_by"] != normalized_creator:
                raise PatternCandidateOwnershipError(
                    "candidate is already registered by another user"
                )
            return _row_to_candidate(existing)

        connection.execute(
            """
            INSERT INTO pattern_candidates
            (
                candidate_id, created_by, replay_session_id, hypothesis_id,
                hypothesis_version, family, direction, condition_state,
                observed_at, evidence_json, pattern_candidate_version,
                hypothesis_registry_version, source_fingerprint, timeframe,
                parameters_json, lifecycle_state, state_version,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'registered', 0, ?, ?);
            """,
            (
                normalized_candidate_id, normalized_creator, normalized_session_id,
                hypothesis_id, hypothesis_version, family, direction, condition_state,
                observed_at, evidence_json, pattern_candidate_version,
                hypothesis_registry_version, source_fingerprint, timeframe,
                parameters_json, now, now,
            ),
        )
        connection.execute(
            """
            INSERT INTO pattern_candidate_audit
            (candidate_id, actor, actor_role, action, previous_state, next_state, occurred_at)
            VALUES (?, ?, ?, 'register', NULL, 'registered', ?);
            """,
            (normalized_candidate_id, normalized_creator, normalized_role, now),
        )
        row = connection.execute(
            "SELECT * FROM pattern_candidates WHERE candidate_id = ?;",
            (normalized_candidate_id,),
        ).fetchone()
    return _row_to_candidate(row)


def get_pattern_candidate(candidate_id: str) -> PersistedPatternCandidate:
    normalized = _required_text(candidate_id, "candidate_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM pattern_candidates WHERE candidate_id = ?;",
            (normalized,),
        ).fetchone()
    if row is None:
        raise PatternCandidateNotFoundError("pattern candidate was not found")
    return _row_to_candidate(row)


def list_pattern_candidates(
    *,
    owner: str,
    page_size: int = 50,
    after: PatternCandidateListPosition | None = None,
) -> PatternCandidatePage:
    normalized_owner = _required_text(owner, "owner")
    if not 1 <= page_size <= 200:
        raise ValueError("page_size must be between 1 and 200")

    conditions = ["created_by = ?"]
    parameters: list[object] = [normalized_owner]
    if after is not None:
        created_at = _required_text(after.created_at, "after.created_at")
        candidate_id = _required_text(after.candidate_id, "after.candidate_id")
        try:
            datetime.fromisoformat(created_at)
        except ValueError as error:
            raise ValueError("after.created_at must be an ISO timestamp") from error
        conditions.append("(created_at < ? OR (created_at = ? AND candidate_id < ?))")
        parameters.extend((created_at, created_at, candidate_id))

    where_sql = f"WHERE {' AND '.join(conditions)}"
    parameters.append(page_size + 1)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM pattern_candidates
            {where_sql}
            ORDER BY created_at DESC, candidate_id DESC
            LIMIT ?;
            """,
            parameters,
        ).fetchall()

    has_more = len(rows) > page_size
    page_rows = rows[:page_size]
    next_position = None
    if has_more and page_rows:
        last_row = page_rows[-1]
        next_position = PatternCandidateListPosition(
            created_at=last_row["created_at"],
            candidate_id=last_row["candidate_id"],
        )
    return PatternCandidatePage(
        items=tuple(_row_to_candidate(row) for row in page_rows),
        next_position=next_position,
    )


def archive_pattern_candidate(
    *,
    candidate_id: str,
    actor: str,
    actor_role: str,
    expected_state_version: int,
) -> PersistedPatternCandidate:
    normalized_candidate_id = _required_text(candidate_id, "candidate_id")
    normalized_actor = _required_text(actor, "actor")
    normalized_role = _required_text(actor_role, "actor_role")

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
        if row["state_version"] != expected_state_version:
            raise PatternCandidateConflictError(
                "pattern candidate changed since it was loaded"
            )
        if row["lifecycle_state"] != "registered":
            raise PatternCandidateConflictError(
                f"cannot archive from state {row['lifecycle_state']}"
            )

        now = datetime.now(UTC).isoformat(timespec="microseconds")
        updated = connection.execute(
            """
            UPDATE pattern_candidates
            SET lifecycle_state = 'archived',
                state_version = state_version + 1,
                updated_at = ?
            WHERE candidate_id = ? AND state_version = ?;
            """,
            (now, normalized_candidate_id, expected_state_version),
        )
        if updated.rowcount != 1:
            raise PatternCandidateConflictError(
                "pattern candidate changed during transition"
            )

        connection.execute(
            """
            INSERT INTO pattern_candidate_audit
            (candidate_id, actor, actor_role, action, previous_state, next_state, occurred_at)
            VALUES (?, ?, ?, 'archive', 'registered', 'archived', ?);
            """,
            (normalized_candidate_id, normalized_actor, normalized_role, now),
        )
        result_row = connection.execute(
            "SELECT * FROM pattern_candidates WHERE candidate_id = ?;",
            (normalized_candidate_id,),
        ).fetchone()
    return _row_to_candidate(result_row)
