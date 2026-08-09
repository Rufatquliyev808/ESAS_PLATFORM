from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json

from backend.app.analysis.bars import TIMEFRAME_SECONDS
from backend.app.analysis.visual_label import LabelSpec, label_spec_id as compute_label_spec_id
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.analysis.visual_render import RenderSpec, render_spec_id as compute_render_spec_id
from backend.app.database.connection import get_connection
from backend.app.database.visual_training_repository import (
    PersistedVisualTrainingConfig,
    VisualTrainingConfigConflictError,
)


class VisualExperimentNotFoundError(LookupError):
    pass


class VisualExperimentOwnershipError(PermissionError):
    pass


class VisualExperimentConflictError(RuntimeError):
    pass


ARCHIVABLE_STATES = frozenset({"registered"})
RENDERABLE_FROM_STATES = frozenset({"registered"})
FAILABLE_FROM_STATES = frozenset({"rendering"})
TRAINABLE_FROM_STATES = frozenset({"rendering"})


@dataclass(frozen=True)
class PersistedVisualExperiment:
    experiment_id: str
    created_by: str
    replay_session_id: str
    symbol: str
    timeframe: str
    source_bar_fingerprint: str
    render_spec_id: str
    render_spec: dict[str, object]
    label_spec_id: str
    label_spec: dict[str, object]
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
        render_spec=json.loads(row["render_spec_json"]),
        label_spec_id=row["label_spec_id"],
        label_spec=json.loads(row["label_spec_json"]),
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
    render_spec: RenderSpec,
    label_spec: LabelSpec,
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

    `render_spec`/`label_spec` are the actual reconstructable spec values
    (not just an opaque caller-supplied id) -- `render_spec_id`/
    `label_spec_id` are derived here via the same `visual_render.py`/
    `visual_label.py` functions the renderer/labeller themselves use, so a
    later materialization step can recover the exact spec used, not just a
    hash of it.

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

    render_spec_json = json.dumps(asdict(render_spec), sort_keys=True, separators=(",", ":"))
    label_spec_json = json.dumps(asdict(label_spec), sort_keys=True, separators=(",", ":"))
    computed_render_spec_id = compute_render_spec_id(render_spec)
    computed_label_spec_id = compute_label_spec_id(label_spec)

    experiment_id = _experiment_id(
        symbol=normalized_symbol, timeframe=timeframe,
        source_bar_fingerprint=normalized_fingerprint, render_spec_id=computed_render_spec_id,
        label_spec_id=computed_label_spec_id, observation_window_bars=observation_window_bars,
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
                source_bar_fingerprint, render_spec_id, render_spec_json,
                label_spec_id, label_spec_json,
                observation_window_bars, train_end_at, validation_end_at,
                lifecycle_state, state_version, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'registered', 0, ?, ?);
            """,
            (
                experiment_id, normalized_creator, normalized_session_id, normalized_symbol,
                timeframe, normalized_fingerprint, computed_render_spec_id, render_spec_json,
                computed_label_spec_id, label_spec_json,
                observation_window_bars, normalized_train_end_at,
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


def _transition(
    *,
    experiment_id: str, actor: str, actor_role: str, expected_state_version: int,
    allowed_from_states: frozenset[str], next_state: str, action: str,
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
        if row["lifecycle_state"] not in allowed_from_states:
            raise VisualExperimentConflictError(
                f"cannot transition to {next_state} from state {row['lifecycle_state']}"
            )
        previous_state = row["lifecycle_state"]

        now = datetime.now(UTC).isoformat(timespec="microseconds")
        updated = connection.execute(
            """
            UPDATE visual_experiments
            SET lifecycle_state = ?, state_version = state_version + 1, updated_at = ?
            WHERE experiment_id = ? AND state_version = ?;
            """,
            (next_state, now, normalized_experiment_id, expected_state_version),
        )
        if updated.rowcount != 1:
            raise VisualExperimentConflictError("visual experiment changed during transition")

        connection.execute(
            """
            INSERT INTO visual_experiment_audit
            (experiment_id, actor, actor_role, action, previous_state, next_state, occurred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (normalized_experiment_id, normalized_actor, normalized_role, action, previous_state, next_state, now),
        )
        result_row = connection.execute(
            "SELECT * FROM visual_experiments WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
    return _row_to_experiment(result_row)


def start_rendering(
    *, experiment_id: str, actor: str, actor_role: str, expected_state_version: int,
) -> PersistedVisualExperiment:
    """registered -> rendering. Marks that materialization has begun; does
    not itself render anything -- callers run the materializer separately
    and then call `mark_rendering_failed` on error. There is no
    `mark_rendering_complete`: the experiment simply stays in `rendering`
    once materialization succeeds, since the Phase 5 contract's next named
    state (`training`) requires model-training infrastructure this
    increment deliberately does not build.
    """
    return _transition(
        experiment_id=experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=expected_state_version,
        allowed_from_states=RENDERABLE_FROM_STATES, next_state="rendering", action="start_rendering",
    )


def mark_rendering_failed(
    *, experiment_id: str, actor: str, actor_role: str, expected_state_version: int,
) -> PersistedVisualExperiment:
    """rendering -> failed. The specific failure reason (bar-fingerprint
    mismatch, dataset drift, etc.) is not re-stored here -- it is already
    the caller's raised exception; the audit action name itself is the
    persisted signal that a rendering attempt failed, matching how
    `block_pattern_candidate_for_data_quality` documents the same
    "the transition itself is the record" convention.
    """
    return _transition(
        experiment_id=experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=expected_state_version,
        allowed_from_states=FAILABLE_FROM_STATES, next_state="failed", action="mark_rendering_failed",
    )


def start_training(
    *, experiment_id: str, actor: str, actor_role: str, expected_state_version: int,
) -> PersistedVisualExperiment:
    """rendering -> training. Callers (`strategies/visual_experiment_training.py`)
    must have already verified every training-readiness gate passes BEFORE
    calling this -- this function itself does not re-check dataset
    completeness, it only performs the lifecycle transition + audit once the
    caller has decided it is safe.
    """
    return _transition(
        experiment_id=experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=expected_state_version,
        allowed_from_states=TRAINABLE_FROM_STATES, next_state="training", action="start_training",
    )


def block_experiment_for_data_quality(
    *, experiment_id: str, actor: str, actor_role: str, expected_state_version: int,
) -> PersistedVisualExperiment:
    """rendering -> blocked_by_data_quality. The fail-closed outcome when a
    training-readiness gate check fails -- an incomplete or corrupted
    dataset (missing manifest, drifted fingerprint, missing/invalid
    artifact, missing split, or too few train samples) must never reach
    `training`. The specific reason(s) are the caller's raised
    `TrainingReadinessError`, not re-stored here -- the audit action name
    itself is the persisted signal, matching `mark_rendering_failed`'s "the
    transition itself is the record" convention.
    """
    return _transition(
        experiment_id=experiment_id, actor=actor, actor_role=actor_role,
        expected_state_version=expected_state_version,
        allowed_from_states=TRAINABLE_FROM_STATES, next_state="blocked_by_data_quality",
        action="block_for_data_quality",
    )


def begin_training_atomically(
    *,
    experiment_id: str,
    actor: str,
    actor_role: str,
    expected_state_version: int,
    model_spec: ModelSpec,
    training_spec: TrainingSpec,
    model_spec_id: str,
    training_spec_id: str,
    training_configuration_checksum: str,
    dataset_fingerprint: str,
) -> tuple[PersistedVisualExperiment, PersistedVisualTrainingConfig]:
    """Atomically performs the entire `rendering -> training` step: the
    lifecycle transition, its audit row, and the `visual_training_configs`
    row, all in ONE SQLite transaction. Replaces what used to be two
    separate calls from the orchestration layer (`start_training()` then
    `persist_training_configuration()`) -- if a process crashed between
    those two calls, an experiment could be left in `training` with no
    recorded configuration, an unrecoverable in-between state. Here, either
    every write commits together or none of them do (the `with
    get_connection()` block rolls back the whole transaction on any
    exception, exactly like every other transition in this module).

    Idempotent: if a training configuration already exists for this
    experiment with a MATCHING checksum, this is a no-op that returns the
    current experiment + that configuration -- safe to retry after a caller
    is unsure whether a previous attempt committed. A training
    configuration that already exists with a DIFFERENT checksum is refused
    (`VisualTrainingConfigConflictError`) -- checked BEFORE the lifecycle
    state is even inspected, since a configuration mismatch is the more
    specific, more informative error regardless of what state the
    experiment happens to be in by then.
    """
    normalized_experiment_id = _required_text(experiment_id, "experiment_id")
    normalized_actor = _required_text(actor, "actor")
    normalized_role = _required_text(actor_role, "actor_role")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")

        existing_config = connection.execute(
            "SELECT * FROM visual_training_configs WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        if existing_config is not None:
            if existing_config["training_configuration_checksum"] != training_configuration_checksum:
                raise VisualTrainingConfigConflictError(
                    "experiment already has a training configuration with a different checksum"
                )
            experiment_row = connection.execute(
                "SELECT * FROM visual_experiments WHERE experiment_id = ?;",
                (normalized_experiment_id,),
            ).fetchone()
            if experiment_row is None:
                raise VisualExperimentNotFoundError("visual experiment was not found")
            return _row_to_experiment(experiment_row), _row_to_training_config(existing_config)

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
        if row["lifecycle_state"] not in TRAINABLE_FROM_STATES:
            raise VisualExperimentConflictError(
                f"cannot transition to training from state {row['lifecycle_state']}"
            )
        previous_state = row["lifecycle_state"]

        now = datetime.now(UTC).isoformat(timespec="microseconds")
        updated = connection.execute(
            """
            UPDATE visual_experiments
            SET lifecycle_state = 'training', state_version = state_version + 1, updated_at = ?
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
            VALUES (?, ?, ?, 'start_training', ?, 'training', ?);
            """,
            (normalized_experiment_id, normalized_actor, normalized_role, previous_state, now),
        )

        model_spec_json = json.dumps(asdict(model_spec), sort_keys=True, separators=(",", ":"))
        training_spec_json = json.dumps(asdict(training_spec), sort_keys=True, separators=(",", ":"))
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

        experiment_row = connection.execute(
            "SELECT * FROM visual_experiments WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()
        config_row = connection.execute(
            "SELECT * FROM visual_training_configs WHERE experiment_id = ?;",
            (normalized_experiment_id,),
        ).fetchone()

    return _row_to_experiment(experiment_row), _row_to_training_config(config_row)


def _row_to_training_config(row: object) -> PersistedVisualTrainingConfig:
    return PersistedVisualTrainingConfig(
        experiment_id=row["experiment_id"], model_spec_id=row["model_spec_id"],
        training_spec_id=row["training_spec_id"],
        training_configuration_checksum=row["training_configuration_checksum"],
        dataset_fingerprint=row["dataset_fingerprint"], created_at=row["created_at"],
    )
