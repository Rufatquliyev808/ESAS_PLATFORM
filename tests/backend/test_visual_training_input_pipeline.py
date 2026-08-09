from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.analysis.bars import build_closed_mid_bars
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
from backend.app.database.visual_dataset_repository import count_dataset_samples
from backend.app.database.visual_experiment_repository import VisualExperimentOwnershipError, register_visual_experiment
from backend.app.storage.artifact_store import has_artifact
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_training_input_pipeline import (
    PREPROCESSING_ARTIFACT_EXTENSION,
    VisualTrainingInputError,
    build_visual_training_input,
)


BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
SMALL_SPEC = RenderSpec(width=20, height=16, padding_top=2, padding_bottom=2, padding_left=2, padding_right=2)

DEFAULT_MODEL_SPEC = ModelSpec(
    architecture_id="cnn-small-v1", preprocessing_policy="normalize_0_1", class_weight_policy="balanced",
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
            f"GOLD:tipipe:{index:05d}", "TICK_RECEIVED",
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


def _prepare_ready_experiment(database_path: Path, *, owner: str = "TEST-USER"):
    """Same split-boundary arithmetic as
    test_visual_experiment_training.py's fixture: a 40-minute session,
    2-bar windows, 1-bar horizon, split boundaries at +24min/+32min ->
    train=11, purged=2, validation=3, holdout=3, pending_horizon=1.
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
    return experiment


def test_build_visual_training_input_succeeds_with_expected_split_sizes(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    result = build_visual_training_input(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    train_sample_count = sum(len(batch.samples) for batch in result.train_batches)
    assert train_sample_count == 11
    assert len(result.validation_samples) == 3
    assert len(result.holdout_samples) == 3
    assert has_artifact(result.preprocessing_state.checksum, extension=PREPROCESSING_ARTIFACT_EXTENSION)


def test_pending_horizon_and_purged_samples_stay_out_of_training_input_but_remain_in_manifest(
    isolated_database: Path,
) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    result = build_visual_training_input(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    train_sample_count = sum(len(batch.samples) for batch in result.train_batches)
    used_in_training_input = train_sample_count + len(result.validation_samples) + len(result.holdout_samples)

    # 11 train + 2 purged + 3 validation + 3 holdout + 1 pending_horizon = 20 total (see fixture docstring)
    assert count_dataset_samples(experiment.experiment_id) == 20
    assert used_in_training_input == 17  # 11 train + 3 validation + 3 holdout, excludes 2 purged + 1 pending


def test_build_visual_training_input_is_byte_for_byte_deterministic(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)
    first = build_visual_training_input(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    second = build_visual_training_input(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert first.preprocessing_state == second.preprocessing_state
    assert first.preprocessing_state.checksum == second.preprocessing_state.checksum
    assert first.train_batches == second.train_batches
    assert first.validation_samples == second.validation_samples
    assert first.holdout_samples == second.holdout_samples


def test_validation_mutation_does_not_change_train_preprocessing_checksum(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database)

    # Force at least two distinct, known train-split classes up front (the
    # natural price pattern in this fixture can end up producing a single
    # "flat" label for every sample) and pin one validation sample to one of
    # those classes too, so the validation sample can be flipped to the
    # OTHER known class below without ever hitting an "unseen label" error.
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
        # Every validation/holdout sample must also carry a label the train
        # class_mapping knows about, or apply_preprocessing rejects it as
        # unseen -- pin them all to "up" up front.
        connection.execute(
            "UPDATE visual_dataset_samples SET label_value = 'up' "
            "WHERE experiment_id = ? AND split_id IN ('validation', 'holdout');",
            (experiment.experiment_id,),
        )
        validation_sample_id = connection.execute(
            "SELECT sample_id FROM visual_dataset_samples "
            "WHERE experiment_id = ? AND split_id = 'validation' ORDER BY sample_id LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()["sample_id"]

    before = build_visual_training_input(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    with get_connection() as connection:
        connection.execute(
            "UPDATE visual_dataset_samples SET label_value = 'down' WHERE experiment_id = ? AND sample_id = ?;",
            (experiment.experiment_id, validation_sample_id),
        )

    after = build_visual_training_input(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert after.preprocessing_state.checksum == before.preprocessing_state.checksum
    assert after.train_batches == before.train_batches
    assert after.validation_samples != before.validation_samples


def test_build_visual_training_input_rejects_other_users_experiment(isolated_database: Path) -> None:
    experiment = _prepare_ready_experiment(isolated_database, owner="OWNER-USER")
    with pytest.raises(VisualExperimentOwnershipError):
        build_visual_training_input(
            experiment.experiment_id, actor="OTHER-USER",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_build_visual_training_input_fails_closed_on_missing_artifact(isolated_database: Path) -> None:
    from backend.app.storage.artifact_store import artifact_path

    experiment = _prepare_ready_experiment(isolated_database)
    with get_connection() as connection:
        checksum = connection.execute(
            "SELECT artifact_checksum FROM visual_dataset_samples "
            "WHERE experiment_id = ? AND split_id = 'train' LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()["artifact_checksum"]
    artifact_path(checksum, extension="png").unlink()

    with pytest.raises(VisualTrainingInputError):
        build_visual_training_input(
            experiment.experiment_id, actor="TEST-USER",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_build_visual_training_input_fails_closed_on_corrupted_artifact(isolated_database: Path) -> None:
    from backend.app.storage.artifact_store import artifact_path

    experiment = _prepare_ready_experiment(isolated_database)
    with get_connection() as connection:
        checksum = connection.execute(
            "SELECT artifact_checksum FROM visual_dataset_samples "
            "WHERE experiment_id = ? AND split_id = 'train' LIMIT 1;",
            (experiment.experiment_id,),
        ).fetchone()["artifact_checksum"]
    artifact_path(checksum, extension="png").write_bytes(b"corrupted, not a real png")

    with pytest.raises(VisualTrainingInputError):
        build_visual_training_input(
            experiment.experiment_id, actor="TEST-USER",
            model_spec=DEFAULT_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
