from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json

from backend.app.analysis.bars import TIMEFRAME_SECONDS
from backend.app.database.connection import get_connection


class VisualExperimentNotFoundError(LookupError):
    pass


class VisualExperimentOwnershipError(PermissionError):
    pass


class VisualExperimentConflictError(RuntimeError):
    pass


ARCHIVABLE_STATES = frozenset({"registered"})


@dataclass(frozen=True)
class PersistedVisualExperiment:
    experiment_id: str
    created_by: str
    replay_session_id: str
    symbol: str
    timeframe: str
    source_bar_fingerprint: str
    render_spec_id: str
    label_spec_id: str
    observation_window_bars: int
    train_end_at: str
    validation_end_at: str
    lifecycle_state: str
    state_version: int
    created_at: str
    updated_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _required_utc(value: str, field_name: str) -> str:
    normalized = _required_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field_name} must include a timezone")
    return normalized


def _experiment_id(
    *,
    symbol: str, timeframe: str, source_bar_fingerprint: str, render_spec_id: str,
    label_spec_id: str, observation_window_bars: int, train_end_at: str, validation_end_at: str,
) -> str:
    payload = {
        "label_spec_id": label_spec_id,
        "observation_window_bars": observation_window_bars,
        "render_spec_id": render_spec_id,
        "source_bar_fingerprint": source_bar_fingerprint,
        "symbol": symbol,
        "timeframe": timeframe,
        "train_end_at": train_end_at,
        "validation_end_at": validation_end_at,
    }
    encoded = json.dumps(
        payload, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _row_to_experiment(row: object) -> PersistedVisualExperiment:
    return PersistedVisualExperiment(
        experiment_id=row["experiment_id"],
        created_by=row["created_by"],
        replay_session_id=row["replay_session_id"],
        symbol=row["symbol"],
        timeframe=row["timeframe"],
        source_bar_fingerprint=row["source_bar_fingerprint"],
        render_spec_id=row["render_spec_id"],
        label_spec_id=row["label_spec_id"],
        observation_window_bars=row["observation_window_bars"],
        train_end_at=row["train_end_at"],
        validation_end_at=row["validation_end_at"],
        lifecycle_state=row["lifecycle_state"],
        state_version=row["state_version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def register_visual_experiment(
    *,
    created_by: str,
    actor_role: str,
    replay_session_id: str,
    symbol: str,
    timeframe: str,
    source_bar_fingerprint: str,
    render_spec_id: str,
    label_spec_id: str,
    observation_window_bars: int,
    train_end_at: str,
    validation_end_at: str,
) -> PersistedVisualExperiment:
    """Register a Phase 5 experiment's frozen configuration -- the render
    spec, label spec, source bar lineage, and time-based split boundaries
    that must all be fixed before any rendering or training begins, per the
    contract's "Eksperiment qeydiyyatı" section. Registration only persists
    this configuration; it does not itself render images, build the
    dataset, or train anything -- those are separate, later lifecycle
    transitions.

    `experiment_id` is derived deterministically from the configuration
    (same fields -> same id), matching the hash-based id scheme already
    used throughout Phase 5 for render_spec_id/sample_id/label_spec_id.
    Re-registering identical configuration is therefore naturally
    idempotent -- it returns the existing record.
    """
    normalized_creator = _required_text(created_by, "created_by")
    normalized_role = _required_text(actor_role, "actor_role")
    normalized_session_id = _required_text(replay_session_id, "replay_session_id")
    normalized_symbol = _required_text(symbol, "symbol")
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"timeframe must be one of: {', '.join(TIMEFRAME_SECONDS)}")
    normalized_fingerprint = _required_text(source_bar_fingerprint, "source_bar_fingerprint")
    normalized_render_spec_id = _required_text(render_spec_id, "render_spec_id")
    normalized_label_spec_id = _required_text(label_spec_id, "label_spec_id")
    if (
        isinstance(observation_window_bars, bool)
        or not isinstance(observation_window_bars, int)
        or observation_window_bars < 1
    ):
        raise ValueError("observation_window_bars must be a positive integer")
    normalized_train_end_at = _required_utc(train_end_at, "train_end_at")
    normalized_validation_end_at = _required_utc(validation_end_at, "validation_end_at")
    if normalized_validation_end_at <= normalized_train_end_at:
        raise ValueError("validation_end_at must be after train_end_at")

    experiment_id = _experiment_id(
        symbol=normalized_symbol, timeframe=timeframe,
        source_bar_fingerprint=normalized_fingerprint, render_spec_id=normalized_render_spec_id,
        label_spec_id=normalized_label_spec_id, observation_window_bars=observation_window_bars,
        train_end_at=normalized_train_end_at, validation_end_at=normalized_validation_end_at,
    )
    now = datetime.now(UTC).isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            "SELECT * FROM visual_experiments WHERE experiment_id = ?;", (experiment_id,),
        ).fetchone()
        if existing is not None:
            if existing["created_by"] != normalized_creator:
                raise VisualExperimentOwnershipError(
                    "experiment is already registered by another user"
                )
            return _row_to_experiment(existing)

        connection.execute(
            """
            INSERT INTO visual_experiments
            (
                experiment_id, created_by, replay_session_id, symbol, timeframe,
                source_bar_fingerprint, render_spec_id, label_spec_id,
                observation_window_bars, train_end_at, validation_end_at,
                lifecycle_state, state_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'registered', 0, ?, ?);
            """,
            (
                experiment_id, normalized_creator, normalized_session_id, normalized_symbol,
                timeframe, normalized_fingerprint, normalized_render_spec_id,
                normalized_label_spec_id, observation_window_bars, normalized_train_end_at,
                normalized_validation_end_at, now, now,
            ),
        )
        connection.execute(
            """
            INSERT INTO visual_experiment_audit
            (experiment_id, actor, actor_role, action, previous_state, next_state, occurred_at)
            VALUES (?, ?, ?, 'register', NULL, 'registered', ?);
            """,
            (experiment_id, normalized_creator, normalized_role, now),
        )
        row = connection.execute(
            "SELECT * FROM visual_experiments WHERE experiment_id = ?;", (experiment_id,),
        ).fetchone()
    return _row_to_experiment(row)


@dataclass(frozen=True)
class VisualExperimentListPosition:
    created_at: str
    experiment_id: str


@dataclass(frozen=True)
class VisualExperimentPage:
    items: tuple[PersistedVisualExperiment, ...]
    next_position: VisualExperimentListPosition | None


def list_visual_experiments(
    *, owner: str, page_size: int = 50, after: VisualExperimentListPosition | None = None,
) -> VisualExperimentPage:
    normalized_owner = _required_text(owner, "owner")
    if not 1 <= page_size <= 200:
        raise ValueError("page_size must be between 1 and 200")

    conditions = ["created_by = ?"]
    parameters: list[object] = [normalized_owner]
    if after is not None:
        created_at = _required_text(after.created_at, "after.created_at")
        experiment_id = _required_text(after.experiment_id, "after.experiment_id")
        try:
            datetime.fromisoformat(created_at)
        except ValueError as error:
            raise ValueError("after.created_at must be an ISO timestamp") from error
        conditions.append("(created_at < ? OR (created_at = ? AND experiment_id < ?))")
        parameters.extend((created_at, created_at, experiment_id))

    where_sql = f"WHERE {' AND '.join(conditions)}"
    parameters.append(page_size + 1)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT * FROM visual_experiments
            {where_sql}
            ORDER BY created_at DESC, experiment_id DESC
            LIMIT ?;
            """,
            parameters,
        ).fetchall()

    has_more = len(rows) > page_size
    page_rows = rows[:page_size]
    next_position = None
    if has_more and page_rows:
        last_row = page_rows[-1]
        next_position = VisualExperimentListPosition(
            created_at=last_row["created_at"], experiment_id=last_row["experiment_id"],
        )
    return VisualExperimentPage(
        items=tuple(_row_to_experiment(row) for row in page_rows), next_position=next_position,
    )


def get_visual_experiment(experiment_id: str) -> PersistedVisualExperiment:
    normalized = _required_text(experiment_id, "experiment_id")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM visual_experiments WHERE experiment_id = ?;", (normalized,),
        ).fetchone()
    if row is None:
        raise VisualExperimentNotFoundError("visual experiment was not found")
    return _row_to_experiment(row)


def archive_visual_experiment(
    *, experiment_id: str, actor: str, actor_role: str, expected_state_version: int,
) -> PersistedVisualExperiment:
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    normalized_actor = _required_text(actor, "actor")
    normalized_role = _required_text(actor_role, "actor_role")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = connection.execute(
            "SELECT * FROM visual_experiments WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        if row is None:
            raise VisualExperimentNotFoundError("visual experiment was not found")
        if row["created_by"] != normalized_actor:
            raise VisualExperimentOwnershipError("visual experiment belongs to another user")
        if row["state_version"] != expected_state_version:
            raise VisualExperimentConflictError("visual experiment changed since it was loaded")
        if row["lifecycle_state"] not in ARCHIVABLE_STATES:
            raise VisualExperimentConflictError(
                f"cannot archive from state {row['lifecycle_state']}"
            )

        now = datetime.now(UTC).isoformat(timespec="microseconds")
        updated = connection.execute(
            """
            UPDATE visual_experiments
            SET lifecycle_state = 'archived', state_version = state_version + 1, updated_at = ?
            WHERE experiment_id = ? AND state_version = ?;
            """,
            (now, normalized_experiment_id, expected_state_version),
        )
        if updated.rowcount != 1:
            raise VisualExperimentConflictError("visual experiment changed during transition")

        connection.execute(
            """
            INSERT INTO visual_experiment_audit
            (experiment_id, actor, actor_role, action, previous_state, next_state, occurred_at)
            VALUES (?, ?, ?, 'archive', ?, 'archived', ?);
            """,
            (
                normalized_experiment_id, normalized_actor, normalized_role,
                row["lifecycle_state"], now,
            ),
        )
        result_row = connection.execute(
            "SELECT * FROM visual_experiments WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
    return _row_to_experiment(result_row)
