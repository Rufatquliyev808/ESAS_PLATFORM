from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.analysis.bars import build_closed_mid_bars
from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_model_spec import (
    ModelSpec,
    TrainingSpec,
    model_spec_id,
    training_configuration_checksum,
    training_spec_id,
)
from backend.app.analysis.visual_render import RenderSpec
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    create_replay_session,
    get_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.database.visual_dataset_repository import get_dataset_manifest
from backend.app.database.visual_experiment_repository import (
    VisualExperimentConflictError,
    VisualExperimentOwnershipError,
    get_visual_experiment,
    register_visual_experiment,
    start_rendering,
)
from backend.app.database.visual_training_repository import get_training_configuration
from backend.app.storage.artifact_store import artifact_path, has_artifact
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_experiment_training import (
    MINIMUM_TRAIN_SAMPLES,
    TrainingReadinessError,
    start_visual_experiment_training,
)


BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)

DEFAULT_MODEL_SPEC = ModelSpec(
    architecture_id="cnn-small-v1", preprocessing_policy="normalize_0_1",
    class_weight_policy="balanced",
)
DEFAULT_TRAINING_SPEC = TrainingSpec(
    seed=42, optimizer="adam", loss="cross_entropy", batch_size=32, max_epochs=10,
    compute_requirement="cpu",
)


def _seed_ticks(end_time: datetime) -> None:
    rows = []
    t = BASE_TIME
    index = 0
    while t < end_time:
        price = 4100.0 + (index % 20) * 0.5
        bid = round(price, 2)
        ask = round(price + 0.4, 2)
        rows.append((
            f"GOLD:trtest:{index:05d}", "TICK_RECEIVED",
            t.isoformat(timespec="microseconds"), t.isoformat(timespec="microseconds"),
            "esas.mt5.bridge", "1.0", "GOLD", bid, ask, round((bid + ask) / 2, 2), 1, 6,
            int(t.timestamp() * 1000), "1.6.0", "{}",
        ))
        index += 1
        t += timedelta(seconds=3)
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO tick_events
            (event_id, event_type, event_timestamp, received_at, source, event_version,
             symbol, bid, ask, last, volume, flags, source_time_msc, module_version, raw_event_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            rows,
        )


def _prepare(database_path: Path, *, end_time: datetime, owner: str = "TEST-USER"):
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    _seed_ticks(end_time)
    created = create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=end_time, mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor=owner, actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=500)
    return get_replay_session(running.session_id)


def _real_bar_fingerprint(session, *, end_time: datetime) -> str:
    ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=BASE_TIME, end_at=end_time)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe="M1", end_at=end_time, source_fingerprint=session.dataset_fingerprint,
    )
    return bar_result.fingerprint


def _register(
    session, *, created_by: str = "TEST-USER", source_bar_fingerprint: str,
    observation_window_bars: int, horizon_bars: int, train_end_at: str, validation_end_at: str,
):
    return register_visual_experiment(
        created_by=created_by, actor_role="operator", replay_session_id=session.session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=source_bar_fingerprint,
        render_spec=RenderSpec(), label_spec=LabelSpec(horizon_bars, 15.0, -15.0),
        observation_window_bars=observation_window_bars, train_end_at=train_end_at,
        validation_end_at=validation_end_at,
    )


def _prepare_ready_experiment(database_path: Path, *, owner: str = "TEST-USER"):
    """40-minute session, 2-bar windows, 1-bar horizon, split boundaries at
    +24min/+32min -- tuned so every required split (train >= MINIMUM_TRAIN_SAMPLES,
    validation, holdout) is populated. See the task's design notes for the
    exact per-window split-boundary arithmetic this relies on.
    """
    end_time = BASE_TIME + timedelta(minutes=40)
    session = _prepare(database_path, end_time=end_time, owner=owner)
    fingerprint = _real_bar_fingerprint(session, end_time=end_time)
    experiment = _register(
        session, created_by=owner, source_bar_fingerprint=fingerprint,
        observation_window_bars=2, horizon_bars=1,
        train_end_at=(BASE_TIME + timedelta(minutes=24)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(minutes=32)).isoformat(),
    )
    render_visual_experiment(experiment.experiment_id, actor=owner, actor_role="operator")
    return get_visual_experiment(experiment.experiment_id)


def test_start_training_succeeds_when_all_gates_pass(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    manifest = get_dataset_manifest(experiment.experiment_id)
    assert manifest is not None

    result = start_visual_experiment_training(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert result.experiment.lifecycle_state == "training"
    expected_checksum = training_configuration_checksum(
        dataset_fingerprint=manifest.dataset_fingerprint,
        model_spec_id=model_spec_id(DEFAULT_MODEL_SPEC),
        training_spec_id=training_spec_id(DEFAULT_TRAINING_SPEC),
    )
    assert result.training_config.training_configuration_checksum == expected_checksum

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "training"
    persisted_config = get_training_configuration(experiment.experiment_id)
    assert persisted_config is not None
    assert persisted_config.training_configuration_checksum == expected_checksum


def test_start_training_cannot_be_rerun_once_training(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    start_visual_experiment_training(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    with pytest.raises(VisualExperimentConflictError):
        start_visual_experiment_training(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_start_training_rejects_other_users_experiment(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database, owner="OWNER-USER")
    with pytest.raises(VisualExperimentOwnershipError):
        start_visual_experiment_training(
            experiment.experiment_id, actor="OTHER-USER", actor_role="operator",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "rendering"


def test_start_training_rejects_invalid_model_spec_before_touching_lifecycle(
    isolated_database: Path,
) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    invalid_model_spec = ModelSpec(
        architecture_id="", preprocessing_policy="normalize_0_1", class_weight_policy="balanced",
    )
    with pytest.raises(ValueError):
        start_visual_experiment_training(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=invalid_model_spec, training_spec=DEFAULT_TRAINING_SPEC,
        )
    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "rendering"


def test_start_training_blocks_for_missing_manifest(isolated_database: Path) -> None:
    end_time = BASE_TIME + timedelta(minutes=30)
    session = _prepare(isolated_database, end_time=end_time)
    fingerprint = _real_bar_fingerprint(session, end_time=end_time)
    experiment = _register(
        session, source_bar_fingerprint=fingerprint, observation_window_bars=5, horizon_bars=3,
        train_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(days=2)).isoformat(),
    )
    # Simulate a corrupted lifecycle: rendering started but materialization
    # never actually persisted a manifest or any samples.
    start_rendering(
        experiment_id=experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=experiment.state_version,
    )

    with pytest.raises(TrainingReadinessError) as excinfo:
        start_visual_experiment_training(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
    assert "dataset_manifest_missing" in excinfo.value.reasons

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "blocked_by_data_quality"


def test_start_training_blocks_for_missing_splits_and_insufficient_samples(
    isolated_database: Path,
) -> None:
    end_time = BASE_TIME + timedelta(minutes=30)
    session = _prepare(isolated_database, end_time=end_time)
    fingerprint = _real_bar_fingerprint(session, end_time=end_time)
    # train_end_at/validation_end_at far in the future -> every labeled
    # sample lands in TRAIN, so validation/holdout are both empty, and this
    # short session does not produce enough windows to meet the minimum.
    experiment = _register(
        session, source_bar_fingerprint=fingerprint, observation_window_bars=5, horizon_bars=3,
        train_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(days=2)).isoformat(),
    )
    render_visual_experiment(experiment.experiment_id, actor="TEST-USER", actor_role="operator")

    with pytest.raises(TrainingReadinessError) as excinfo:
        start_visual_experiment_training(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
    reasons = excinfo.value.reasons
    assert "split_missing:validation" in reasons
    assert "split_missing:holdout" in reasons
    assert "insufficient_train_samples" in reasons

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "blocked_by_data_quality"


def test_start_training_blocks_for_dataset_fingerprint_drift(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT sample_id, split_id FROM visual_dataset_samples WHERE experiment_id = ? LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()
        # Guaranteed to actually change the value regardless of what it was.
        tampered_split_id = "holdout" if row["split_id"] != "holdout" else "train"
        connection.execute(
            "UPDATE visual_dataset_samples SET split_id = ? "
            "WHERE experiment_id = ? AND sample_id = ?;",
            (tampered_split_id, experiment.experiment_id, row["sample_id"]),
        )

    with pytest.raises(TrainingReadinessError) as excinfo:
        start_visual_experiment_training(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
    assert "dataset_fingerprint_changed" in excinfo.value.reasons

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "blocked_by_data_quality"


def test_start_training_blocks_for_missing_artifact(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    with get_connection() as connection:
        checksum = connection.execute(
            "SELECT artifact_checksum FROM visual_dataset_samples WHERE experiment_id = ? LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()["artifact_checksum"]
    assert has_artifact(checksum, extension="png")
    artifact_path(checksum, extension="png").unlink()

    with pytest.raises(TrainingReadinessError) as excinfo:
        start_visual_experiment_training(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
    assert any(reason.startswith("artifacts_missing:") for reason in excinfo.value.reasons)

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "blocked_by_data_quality"


def test_start_training_blocks_for_corrupted_artifact_checksum(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    with get_connection() as connection:
        checksum = connection.execute(
            "SELECT artifact_checksum FROM visual_dataset_samples WHERE experiment_id = ? LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()["artifact_checksum"]
    path = artifact_path(checksum, extension="png")
    path.write_bytes(b"not actually a png")

    with pytest.raises(TrainingReadinessError) as excinfo:
        start_visual_experiment_training(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
    assert any(reason.startswith("artifacts_checksum_invalid:") for reason in excinfo.value.reasons)

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "blocked_by_data_quality"


def test_minimum_train_samples_constant_is_positive() -> None:
    assert MINIMUM_TRAIN_SAMPLES > 0
