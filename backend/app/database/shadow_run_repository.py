from dataclasses import dataclass
from datetime import UTC, datetime
import json
import secrets

from backend.app.analysis.visual_acceptance import ACCEPTED_FOR_SHADOW
from backend.app.database.connection import get_connection
from backend.app.database.visual_acceptance_repository import get_acceptance_decision
from backend.app.database.visual_baseline_model_repository import get_baseline_model
from backend.app.database.visual_experiment_repository import (
    VisualExperimentNotFoundError,
    get_visual_experiment,
)


PARTICIPANT_ROLES = frozenset({"champion", "challenger"})
NON_TERMINAL_STATES = frozenset({"registered", "started"})
# Visual AI lineage may only back a "challenger" -- a freshly
# accepted_for_shadow model has never been through any SHADOW validation
# itself, so it can never masquerade as the pre-selected "champion"
# baseline (contract section 7: "Baseline əvvəlcədən seçilir").
VISUAL_LINEAGE_ELIGIBLE_ROLES = frozenset({"challenger"})


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
    visual_experiment_id: str | None = None
    visual_model_checksum: str | None = None
    visual_acceptance_decision_checksum: str | None = None


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


def _row_to_participant(row: object, lineage_row: object | None) -> ShadowRunParticipant:
    return ShadowRunParticipant(
        participant_id=row["participant_id"], role=row["role"],
        module_id=row["module_id"], module_version=row["module_version"],
        visual_experiment_id=lineage_row["visual_experiment_id"] if lineage_row is not None else None,
        visual_model_checksum=lineage_row["visual_model_checksum"] if lineage_row is not None else None,
        visual_acceptance_decision_checksum=(
            lineage_row["visual_acceptance_decision_checksum"] if lineage_row is not None else None
        ),
    )


def _row_to_run(row: object, participant_rows: tuple[ShadowRunParticipant, ...]) -> PersistedShadowRun:
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
        participants=participant_rows,
    )


def _load_run(connection, shadow_run_id: str) -> object:
    row = connection.execute(
        "SELECT * FROM shadow_runs WHERE shadow_run_id = ?;", (shadow_run_id,),
    ).fetchone()
    if row is None:
        raise ShadowRunNotFoundError("shadow run was not found")
    return row


def _load_participants(connection, shadow_run_id: str) -> tuple[ShadowRunParticipant, ...]:
    rows = connection.execute(
        "SELECT * FROM shadow_run_participants WHERE shadow_run_id = ? ORDER BY participant_id;",
        (shadow_run_id,),
    ).fetchall()
    participants = []
    for row in rows:
        lineage_row = connection.execute(
            "SELECT * FROM shadow_run_participant_visual_lineage WHERE participant_id = ?;",
            (row["participant_id"],),
        ).fetchone()
        participants.append(_row_to_participant(row, lineage_row))
    return tuple(participants)


def _verify_visual_lineage(visual_experiment_id: str) -> tuple[str, str, str]:
    """Fail-closed lookup for a challenger's Visual AI backing: the
    experiment must exist and currently be `accepted_for_shadow`, and both
    its trained model and its acceptance decision must be persisted.
    Returns (visual_experiment_id, model_checksum, decision_checksum)
    derived fresh from those records -- never trusted from a caller.
    """
    normalized_experiment_id = _required_text(visual_experiment_id, "visual_experiment_id")
    try:
        experiment = get_visual_experiment(normalized_experiment_id)
    except VisualExperimentNotFoundError as error:
        raise ValueError(f"visual experiment not found: {normalized_experiment_id}") from error
    if experiment.lifecycle_state != ACCEPTED_FOR_SHADOW:
        raise ValueError(
            f"visual experiment {normalized_experiment_id} is not accepted_for_shadow "
            f"(currently {experiment.lifecycle_state!r})"
        )
    model = get_baseline_model(normalized_experiment_id)
    if model is None:
        raise ValueError(f"visual experiment {normalized_experiment_id} has no persisted baseline model")
    decision = get_acceptance_decision(normalized_experiment_id)
    if decision is None or decision.decision != ACCEPTED_FOR_SHADOW:
        raise ValueError(f"visual experiment {normalized_experiment_id} has no accepted_for_shadow decision")
    return normalized_experiment_id, model.model_checksum, decision.decision_checksum


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
    participants: tuple[tuple[str, str, str] | tuple[str, str, str, str | None], ...],
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

    Each participant tuple is (role, module_id, module_version) or, for a
    challenger backed by a specific Visual AI experiment, (role, module_id,
    module_version, visual_experiment_id) -- a lineage-only connection
    (contract section 7's champion/challenger model), not a live decision
    feed. When present, the referenced experiment must currently be
    `accepted_for_shadow`; its trained model's and acceptance decision's
    checksums are derived fresh from the persisted records (never trusted
    from the caller) and pinned as an immutable snapshot.
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
    visual_lineage_by_index: dict[int, tuple[str, str, str]] = {}
    for index, entry in enumerate(participants):
        role, module_id, module_version = entry[0], entry[1], entry[2]
        visual_experiment_id = entry[3] if len(entry) > 3 else None
        if role not in PARTICIPANT_ROLES:
            raise ValueError(f"unsupported participant role: {role}")
        _required_text(module_id, "module_id")
        _required_text(module_version, "module_version")
        if role == "champion":
            champion_count += 1
        if visual_experiment_id:
            if role not in VISUAL_LINEAGE_ELIGIBLE_ROLES:
                raise ValueError(
                    f"visual_experiment_id may only back a {sorted(VISUAL_LINEAGE_ELIGIBLE_ROLES)} participant, not {role!r}"
                )
            visual_lineage_by_index[index] = _verify_visual_lineage(visual_experiment_id)
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
        for index, entry in enumerate(participants):
            role, module_id, module_version = entry[0], entry[1], entry[2]
            participant_id = _new_id("participant")
            connection.execute(
                """
                INSERT INTO shadow_run_participants (participant_id, shadow_run_id, role, module_id, module_version)
                VALUES (?, ?, ?, ?, ?);
                """,
                (participant_id, shadow_run_id, role, module_id, module_version),
            )
            lineage = visual_lineage_by_index.get(index)
            if lineage is not None:
                lineage_experiment_id, model_checksum, decision_checksum = lineage
                connection.execute(
                    """
                    INSERT INTO shadow_run_participant_visual_lineage
                    (participant_id, shadow_run_id, visual_experiment_id, visual_model_checksum,
                     visual_acceptance_decision_checksum, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (participant_id, shadow_run_id, lineage_experiment_id, model_checksum, decision_checksum, now),
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
