from dataclasses import dataclass
from datetime import UTC, datetime
import json
import secrets

from backend.app.database.connection import get_connection


PARTICIPANT_ROLES = frozenset({"champion", "challenger"})
NON_TERMINAL_STATES = frozenset({"registered", "started"})


class ShadowRunNotFoundError(LookupError):
    pass


class ShadowRunOwnershipError(PermissionError):
    pass


class ShadowRunConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class ShadowRunParticipant:
    participant_id: str
    role: str
    module_id: str
    module_version: str


@dataclass(frozen=True)
class PersistedShadowRun:
    shadow_run_id: str
    created_by: str
    created_at: str
    planned_end_at: str
    code_commit: str
    config_hash: str
    feature_claim_versions: tuple[str, ...]
    symbols: tuple[str, ...]
    timeframes: tuple[str, ...]
    sessions: tuple[str, ...]
    accepted_market_regimes: tuple[str, ...]
    minimum_market_open_duration_seconds: int
    minimum_eligible_decision_count: int
    primary_metric: str
    primary_metric_threshold: float
    secondary_metrics: dict[str, object]
    failure_rules: dict[str, object]
    theoretical_fill_model: dict[str, object]
    risk_budget: dict[str, object]
    data_quality_policy: dict[str, object]
    approved_by: str
    rollback_plan: str
    execution_allowed: bool
    state: str
    state_version: int
    halt_reason: str | None
    updated_at: str
    participants: tuple[ShadowRunParticipant, ...]


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _required_sequence(value: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return tuple(value)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(18)}"


def _row_to_participant(row: object) -> ShadowRunParticipant:
    return ShadowRunParticipant(
        participant_id=row["participant_id"], role=row["role"],
        module_id=row["module_id"], module_version=row["module_version"],
    )


def _row_to_run(row: object, participant_rows: tuple[object, ...]) -> PersistedShadowRun:
    return PersistedShadowRun(
        shadow_run_id=row["shadow_run_id"], created_by=row["created_by"], created_at=row["created_at"],
        planned_end_at=row["planned_end_at"], code_commit=row["code_commit"], config_hash=row["config_hash"],
        feature_claim_versions=tuple(json.loads(row["feature_claim_versions_json"])),
        symbols=tuple(json.loads(row["symbols_json"])), timeframes=tuple(json.loads(row["timeframes_json"])),
        sessions=tuple(json.loads(row["sessions_json"])),
        accepted_market_regimes=tuple(json.loads(row["accepted_market_regimes_json"])),
        minimum_market_open_duration_seconds=row["minimum_market_open_duration_seconds"],
        minimum_eligible_decision_count=row["minimum_eligible_decision_count"],
        primary_metric=row["primary_metric"], primary_metric_threshold=row["primary_metric_threshold"],
        secondary_metrics=json.loads(row["secondary_metrics_json"]),
        failure_rules=json.loads(row["failure_rules_json"]),
        theoretical_fill_model=json.loads(row["theoretical_fill_model_json"]),
        risk_budget=json.loads(row["risk_budget_json"]),
        data_quality_policy=json.loads(row["data_quality_policy_json"]),
        approved_by=row["approved_by"], rollback_plan=row["rollback_plan"],
        execution_allowed=bool(row["execution_allowed"]), state=row["state"],
        state_version=row["state_version"], halt_reason=row["halt_reason"], updated_at=row["updated_at"],
        participants=tuple(_row_to_participant(item) for item in participant_rows),
    )


def _load_run(connection, shadow_run_id: str) -> object:
    row = connection.execute(
        "SELECT * FROM shadow_runs WHERE shadow_run_id = ?;", (shadow_run_id,),
    ).fetchone()
    if row is None:
        raise ShadowRunNotFoundError("shadow run was not found")
    return row


def _load_participants(connection, shadow_run_id: str) -> tuple[object, ...]:
    return tuple(connection.execute(
        "SELECT * FROM shadow_run_participants WHERE shadow_run_id = ? ORDER BY participant_id;",
        (shadow_run_id,),
    ).fetchall())


def register_shadow_run(
    *,
    created_by: str,
    planned_end_at: str,
    code_commit: str,
    config_hash: str,
    feature_claim_versions: tuple[str, ...],
    symbols: tuple[str, ...],
    timeframes: tuple[str, ...],
    sessions: tuple[str, ...],
    accepted_market_regimes: tuple[str, ...],
    minimum_market_open_duration_seconds: int,
    minimum_eligible_decision_count: int,
    primary_metric: str,
    primary_metric_threshold: float,
    secondary_metrics: dict[str, object],
    failure_rules: dict[str, object],
    theoretical_fill_model: dict[str, object],
    risk_budget: dict[str, object],
    data_quality_policy: dict[str, object],
    approved_by: str,
    rollback_plan: str,
    participants: tuple[tuple[str, str, str], ...],
) -> PersistedShadowRun:
    """Pre-register an immutable SHADOW run manifest (contract section 3).

    This only persists the manifest, participants (exactly one champion plus
    zero or more challengers) and gives callers a place to append events --
    it does not run anything. No live decision feed exists yet (Phase 5-8
    are design-only), so nothing calls this in production yet.

    Every field here becomes frozen the instant the row is inserted (enforced
    by a DB trigger, not just this function): "Run başladıqdan sonra hədəf,
    metrik və hədlər dəyişdirilmir." Only state may change afterward, via
    start_shadow_run/complete_shadow_run/halt_shadow_run.
    """
    normalized_creator = _required_text(created_by, "created_by")
    normalized_planned_end = _required_text(planned_end_at, "planned_end_at")
    normalized_commit = _required_text(code_commit, "code_commit")
    normalized_config_hash = _required_text(config_hash, "config_hash")
    normalized_claims = _required_sequence(feature_claim_versions, "feature_claim_versions")
    normalized_symbols = _required_sequence(symbols, "symbols")
    normalized_timeframes = _required_sequence(timeframes, "timeframes")
    normalized_sessions = _required_sequence(sessions, "sessions")
    normalized_regimes = _required_sequence(accepted_market_regimes, "accepted_market_regimes")
    normalized_primary_metric = _required_text(primary_metric, "primary_metric")
    normalized_approved_by = _required_text(approved_by, "approved_by")
    normalized_rollback_plan = _required_text(rollback_plan, "rollback_plan")
    if minimum_market_open_duration_seconds < 0:
        raise ValueError("minimum_market_open_duration_seconds must not be negative")
    if minimum_eligible_decision_count < 1:
        raise ValueError("minimum_eligible_decision_count must be at least 1")
    if not participants:
        raise ValueError("at least one participant is required")
    champion_count = 0
    for role, module_id, module_version in participants:
        if role not in PARTICIPANT_ROLES:
            raise ValueError(f"unsupported participant role: {role}")
        _required_text(module_id, "module_id")
        _required_text(module_version, "module_version")
        if role == "champion":
            champion_count += 1
    if champion_count != 1:
        raise ValueError("a shadow run must have exactly one champion participant")

    now = _now()
    shadow_run_id = _new_id("shadow_run")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        connection.execute(
            """
            INSERT INTO shadow_runs
            (
                shadow_run_id, created_by, created_at, planned_end_at, code_commit, config_hash,
                feature_claim_versions_json, symbols_json, timeframes_json, sessions_json,
                accepted_market_regimes_json, minimum_market_open_duration_seconds,
                minimum_eligible_decision_count, primary_metric, primary_metric_threshold,
                secondary_metrics_json, failure_rules_json, theoretical_fill_model_json,
                risk_budget_json, data_quality_policy_json, approved_by, rollback_plan,
                execution_allowed, state, state_version, halt_reason, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'registered', 0, NULL, ?);
            """,
            (
                shadow_run_id, normalized_creator, now, normalized_planned_end, normalized_commit,
                normalized_config_hash, json.dumps(normalized_claims), json.dumps(normalized_symbols),
                json.dumps(normalized_timeframes), json.dumps(normalized_sessions),
                json.dumps(normalized_regimes), minimum_market_open_duration_seconds,
                minimum_eligible_decision_count, normalized_primary_metric, primary_metric_threshold,
                json.dumps(secondary_metrics, sort_keys=True), json.dumps(failure_rules, sort_keys=True),
                json.dumps(theoretical_fill_model, sort_keys=True), json.dumps(risk_budget, sort_keys=True),
                json.dumps(data_quality_policy, sort_keys=True), normalized_approved_by,
                normalized_rollback_plan, now,
            ),
        )
        for role, module_id, module_version in participants:
            connection.execute(
                """
                INSERT INTO shadow_run_participants (participant_id, shadow_run_id, role, module_id, module_version)
                VALUES (?, ?, ?, ?, ?);
                """,
                (_new_id("participant"), shadow_run_id, role, module_id, module_version),
            )
        row = _load_run(connection, shadow_run_id)
        participant_rows = _load_participants(connection, shadow_run_id)
    return _row_to_run(row, participant_rows)


def get_shadow_run(shadow_run_id: str) -> PersistedShadowRun:
    normalized = _required_text(shadow_run_id, "shadow_run_id")
    with get_connection() as connection:
        row = _load_run(connection, normalized)
        participant_rows = _load_participants(connection, normalized)
    return _row_to_run(row, participant_rows)


def list_shadow_runs(*, owner: str, limit: int = 100) -> tuple[PersistedShadowRun, ...]:
    """Owner-scoped run list, newest first.

    Unlike replay sessions or pattern candidates, SHADOW runs are rare,
    deliberate, long-lived experiments (weeks per the manifest's own
    planned_end_at) -- a simple bounded list is proportionate here, not
    signed keyset cursor pagination sized for a high-volume stream.
    """
    normalized_owner = _required_text(owner, "owner")
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM shadow_runs WHERE created_by = ? ORDER BY created_at DESC LIMIT ?;",
            (normalized_owner, limit),
        ).fetchall()
        runs = []
        for row in rows:
            participant_rows = _load_participants(connection, row["shadow_run_id"])
            runs.append(_row_to_run(row, participant_rows))
    return tuple(runs)


def _transition(
    *, shadow_run_id: str, actor: str, expected_state_version: int,
    allowed_from: frozenset[str], next_state: str, halt_reason: str | None = None,
) -> PersistedShadowRun:
    normalized_id = _required_text(shadow_run_id, "shadow_run_id")
    normalized_actor = _required_text(actor, "actor")
    now = _now()
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = _load_run(connection, normalized_id)
        if row["created_by"] != normalized_actor:
            raise ShadowRunOwnershipError("shadow run belongs to another user")
        if row["state_version"] != expected_state_version:
            raise ShadowRunConflictError("shadow run changed since it was loaded")
        if row["state"] not in allowed_from:
            raise ShadowRunConflictError(f"cannot transition to {next_state} from state {row['state']}")
        updated = connection.execute(
            """
            UPDATE shadow_runs
            SET state = ?, state_version = state_version + 1, halt_reason = ?, updated_at = ?
            WHERE shadow_run_id = ? AND state_version = ?;
            """,
            (next_state, halt_reason, now, normalized_id, expected_state_version),
        )
        if updated.rowcount != 1:
            raise ShadowRunConflictError("shadow run changed during transition")
        result_row = _load_run(connection, normalized_id)
        participant_rows = _load_participants(connection, normalized_id)
    return _row_to_run(result_row, participant_rows)


def start_shadow_run(*, shadow_run_id: str, actor: str, expected_state_version: int) -> PersistedShadowRun:
    return _transition(
        shadow_run_id=shadow_run_id, actor=actor, expected_state_version=expected_state_version,
        allowed_from=frozenset({"registered"}), next_state="started",
    )


def complete_shadow_run(*, shadow_run_id: str, actor: str, expected_state_version: int) -> PersistedShadowRun:
    return _transition(
        shadow_run_id=shadow_run_id, actor=actor, expected_state_version=expected_state_version,
        allowed_from=frozenset({"started"}), next_state="completed",
    )


def halt_shadow_run(*, shadow_run_id: str, actor: str, expected_state_version: int, reason: str) -> PersistedShadowRun:
    """Immediately stop a run, e.g. the critical-security response to any
    attempted order-adapter call (contract section 2). Reachable from any
    non-terminal state."""
    normalized_reason = _required_text(reason, "reason")
    return _transition(
        shadow_run_id=shadow_run_id, actor=actor, expected_state_version=expected_state_version,
        allowed_from=NON_TERMINAL_STATES, next_state="halted", halt_reason=normalized_reason,
    )
