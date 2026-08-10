from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.analysis.bars import build_closed_mid_bars
from backend.app.analysis.visual_baseline_trainer import BASELINE_ARCHITECTURE_ID
from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
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
from backend.app.database.visual_baseline_model_repository import (
    VisualBaselineModelConflictError,
    get_baseline_model,
)
from backend.app.database.visual_experiment_repository import (
    VisualExperimentOwnershipError,
    get_visual_experiment,
    register_visual_experiment,
)
from backend.app.storage.artifact_store import has_artifact
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_experiment_training import start_visual_experiment_training
from backend.app.strategies.visual_baseline_training import (
    VisualBaselineTrainingError,
    train_visual_baseline_model,
)


BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
SMALL_SPEC = RenderSpec(width=20, height=16, padding_top=2, padding_bottom=2, padding_left=2, padding_right=2)

BASELINE_MODEL_SPEC = ModelSpec(
    architecture_id=BASELINE_ARCHITECTURE_ID, preprocessing_policy="normalize_0_1",
    class_weight_policy="balanced",
)
DEFAULT_TRAINING_SPEC = TrainingSpec(
    seed=42, optimizer="adam", loss="cross_entropy", batch_size=4, max_epochs=10, compute_requirement="cpu",
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
            f"GOLD:btrain:{index:05d}", "TICK_RECEIVED",
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


def _prepare_trainable_experiment(database_path: Path, *, owner: str = "TEST-USER"):
    """Same split-boundary arithmetic as the prior increments' fixtures
    (train=11, purged=2, validation=3, holdout=3, pending_horizon=1),
    additionally forcing train/validation/holdout labels into a 2-class
    up/down mix so the baseline trainer's centroid math is meaningfully
    exercised regardless of what the natural price pattern would have
    produced (which can end up all "flat").
    """
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_time = BASE_TIME + timedelta(minutes=40)
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
    session = get_replay_session(running.session_id)
    fingerprint = _real_bar_fingerprint(session, end_time=end_time)

    experiment = register_visual_experiment(
        created_by=owner, actor_role="operator", replay_session_id=session.session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=fingerprint,
        render_spec=SMALL_SPEC, label_spec=LabelSpec(1, 15.0, -15.0),
        observation_window_bars=2, train_end_at=(BASE_TIME + timedelta(minutes=24)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(minutes=32)).isoformat(),
    )
    render_visual_experiment(experiment.experiment_id, actor=owner, actor_role="operator")

    with get_connection() as connection:
        train_sample_ids = [
            row["sample_id"]
            for row in connection.execute(
                "SELECT sample_id FROM visual_dataset_samples "
                "WHERE experiment_id = ? AND split_id = 'train' ORDER BY sample_id;",
                (experiment.experiment_id,),
            ).fetchall()
        ]
        for index, sample_id in enumerate(train_sample_ids):
            connection.execute(
                "UPDATE visual_dataset_samples SET label_value = ? WHERE experiment_id = ? AND sample_id = ?;",
                ("up" if index % 2 == 0 else "down", experiment.experiment_id, sample_id),
            )
        connection.execute(
            "UPDATE visual_dataset_samples SET label_value = 'up' "
            "WHERE experiment_id = ? AND split_id IN ('validation', 'holdout');",
            (experiment.experiment_id,),
        )

    trained = start_visual_experiment_training(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert trained.experiment.lifecycle_state == "training"
    return experiment


def test_train_visual_baseline_model_succeeds_and_keeps_lifecycle_state(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    result = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert result.model.architecture_id == BASELINE_ARCHITECTURE_ID
    assert len(result.model.centroids) == len(result.model.class_mapping)
    assert result.persisted.model_checksum == result.model.checksum
    assert has_artifact(result.model.checksum, extension="json")
    assert has_artifact(result.log.checksum, extension="json")

    stored_experiment = get_visual_experiment(experiment.experiment_id)
    assert stored_experiment.lifecycle_state == "training"  # unchanged by this step

    stored_model = get_baseline_model(experiment.experiment_id)
    assert stored_model is not None
    assert stored_model.model_checksum == result.model.checksum


def test_train_visual_baseline_model_is_deterministic(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    first = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    second = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert first.model == second.model
    assert first.model.checksum == second.model.checksum
    assert first.log.validation_metrics == second.log.validation_metrics


def test_validation_mutation_does_not_change_model_weights(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    before = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    with get_connection() as connection:
        connection.execute(
            "UPDATE visual_dataset_samples SET label_value = 'down' "
            "WHERE experiment_id = ? AND split_id = 'validation';",
            (experiment.experiment_id,),
        )

    after = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert after.model.checksum == before.model.checksum
    assert after.model.centroids == before.model.centroids


def test_holdout_mutation_does_not_change_model_weights(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    before = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    with get_connection() as connection:
        connection.execute(
            "UPDATE visual_dataset_samples SET label_value = 'down' "
            "WHERE experiment_id = ? AND split_id = 'holdout';",
            (experiment.experiment_id,),
        )

    after = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert after.model.checksum == before.model.checksum
    assert after.model.centroids == before.model.centroids


def test_train_visual_baseline_model_rejects_other_users_experiment(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database, owner="OWNER-USER")
    with pytest.raises(VisualExperimentOwnershipError):
        train_visual_baseline_model(
            experiment.experiment_id, actor="OTHER-USER",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_train_visual_baseline_model_rejects_experiment_not_in_training_state(
    isolated_database: Path,
) -> None:
    end_time = BASE_TIME + timedelta(minutes=30)
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    _seed_ticks(end_time)
    created = create_replay_session(
        created_by="TEST-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=end_time, mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor="TEST-USER", actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=500)
    session = get_replay_session(running.session_id)
    fingerprint = _real_bar_fingerprint(session, end_time=end_time)
    experiment = register_visual_experiment(
        created_by="TEST-USER", actor_role="operator", replay_session_id=session.session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=fingerprint,
        render_spec=SMALL_SPEC, label_spec=LabelSpec(3, 15.0, -15.0),
        observation_window_bars=5, train_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(days=2)).isoformat(),
    )
    # Still "registered" -- never rendered or gated into "training".
    with pytest.raises(VisualBaselineTrainingError):
        train_visual_baseline_model(
            experiment.experiment_id, actor="TEST-USER",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_train_visual_baseline_model_conflicts_on_different_spec_after_first_success(
    isolated_database: Path,
) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    other_training_spec = TrainingSpec(
        seed=99, optimizer="sgd", loss="cross_entropy", batch_size=2, max_epochs=1, compute_requirement="cpu",
    )
    with pytest.raises(VisualBaselineModelConflictError):
        train_visual_baseline_model(
            experiment.experiment_id, actor="TEST-USER",
            model_spec=BASELINE_MODEL_SPEC, training_spec=other_training_spec,
        )
