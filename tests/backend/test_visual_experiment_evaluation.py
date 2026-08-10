from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from backend.app.analysis.bars import MarketBar, build_closed_mid_bars
from backend.app.analysis.visual_baseline_trainer import BASELINE_ARCHITECTURE_ID, predict_validation
from backend.app.analysis.visual_evaluation import (
    EVALUATED,
    INSUFFICIENT_EVIDENCE,
    OUT_OF_DISTRIBUTION,
    build_evaluation_artifact,
)
from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.analysis.visual_render import RenderSpec, render_canonical_chart
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    create_replay_session,
    get_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.database.visual_evaluation_repository import get_evaluation
from backend.app.database.visual_experiment_repository import (
    VisualExperimentOwnershipError,
    get_visual_experiment,
    register_visual_experiment,
)
from backend.app.storage.artifact_store import artifact_path, has_artifact, put_artifact
from backend.app.strategies.visual_baseline_training import VisualBaselineTrainingError
from backend.app.strategies.visual_experiment_evaluation import evaluate_visual_experiment
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_experiment_training import start_visual_experiment_training
from backend.app.strategies.visual_training_input_pipeline import build_visual_training_input


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
            f"GOLD:eval:{index:05d}", "TICK_RECEIVED",
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

    start_visual_experiment_training(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    return experiment


def test_evaluate_visual_experiment_reaches_evaluated(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    result = evaluate_visual_experiment(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert result.evaluation.outcome == EVALUATED
    assert result.experiment.lifecycle_state == "evaluated"
    assert result.evaluation.holdout_sample_count == 3
    assert has_artifact(result.evaluation.checksum, extension="json")

    stored_experiment = get_visual_experiment(experiment.experiment_id)
    assert stored_experiment.lifecycle_state == "evaluated"
    stored_evaluation = get_evaluation(experiment.experiment_id)
    assert stored_evaluation is not None
    assert stored_evaluation.outcome == EVALUATED
    assert stored_evaluation.evaluation_checksum == result.evaluation.checksum


def test_evaluate_visual_experiment_holdout_computation_is_deterministic(isolated_database: Path) -> None:
    """Exercises the same holdout evaluation logic the orchestrator uses,
    computed twice from the real pipeline (not just the pure unit test),
    without going through the state-changing orchestrator itself (which
    cannot be re-run after the first success moves the experiment past
    `training`).
    """
    experiment = _prepare_trainable_experiment(isolated_database)

    from backend.app.strategies.visual_baseline_training import train_visual_baseline_model

    training_result = train_visual_baseline_model(
        experiment.experiment_id, actor="TEST-USER",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    model = training_result.model

    def _build_evaluation():
        training_input = build_visual_training_input(
            experiment.experiment_id, actor="TEST-USER",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
        validation_predictions = predict_validation(training_input.validation_samples, model)
        holdout_predictions = predict_validation(training_input.holdout_samples, model)
        return build_evaluation_artifact(
            model=model, holdout_samples=training_input.holdout_samples,
            validation_predictions=validation_predictions, holdout_predictions=holdout_predictions,
        )

    first = _build_evaluation()
    second = _build_evaluation()
    assert first == second
    assert first.checksum == second.checksum


def test_evaluate_visual_experiment_reaches_insufficient_evidence_with_too_few_holdout_samples(
    isolated_database: Path,
) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    with get_connection() as connection:
        holdout_sample_ids = [
            row["sample_id"]
            for row in connection.execute(
                "SELECT sample_id FROM visual_dataset_samples WHERE experiment_id = ? AND split_id = 'holdout';",
                (experiment.experiment_id,),
            ).fetchall()
        ]
        # Leave only 2 holdout samples -- below MINIMUM_HOLDOUT_SAMPLES (3).
        connection.execute(
            "DELETE FROM visual_dataset_samples WHERE experiment_id = ? AND sample_id = ?;",
            (experiment.experiment_id, holdout_sample_ids[0]),
        )

    result = evaluate_visual_experiment(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert result.evaluation.outcome == INSUFFICIENT_EVIDENCE
    assert result.experiment.lifecycle_state == "insufficient_evidence"


def test_evaluate_visual_experiment_reaches_out_of_distribution_for_far_holdout_sample(
    isolated_database: Path,
) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)

    # Build a wildly different-colored image (same dimensions) and swap it
    # in for every holdout sample's artifact/image checksum, so their pixel
    # content sits far from every train centroid.
    far_spec = RenderSpec(
        width=SMALL_SPEC.width, height=SMALL_SPEC.height,
        padding_top=SMALL_SPEC.padding_top, padding_bottom=SMALL_SPEC.padding_bottom,
        padding_left=SMALL_SPEC.padding_left, padding_right=SMALL_SPEC.padding_right,
        background_rgb=(0, 255, 255), bullish_rgb=(255, 0, 255), bearish_rgb=(255, 255, 0),
        wick_rgb=(0, 0, 0),
    )
    far_bar = MarketBar(
        symbol="GOLD", timeframe="M1", start_at="2026-08-01T08:00:00.000000+00:00",
        end_at="2026-08-01T08:01:00.000000+00:00", open=1.0, high=1.5, low=0.5, close=1.2,
        tick_count=1, tick_volume=1, spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id="far:0", last_event_id="far:1",
    )
    far_image = render_canonical_chart((far_bar,), bar_fingerprint="sha256:far", spec=far_spec)
    far_artifact_checksum = f"sha256:{sha256(far_image.png_bytes).hexdigest()}"
    put_artifact(far_artifact_checksum, far_image.png_bytes, extension="png")
    assert artifact_path(far_artifact_checksum, extension="png").is_file()

    with get_connection() as connection:
        connection.execute(
            "UPDATE visual_dataset_samples SET image_checksum = ?, artifact_checksum = ? "
            "WHERE experiment_id = ? AND split_id = 'holdout';",
            (far_image.image_checksum, far_artifact_checksum, experiment.experiment_id),
        )

    result = evaluate_visual_experiment(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert result.evaluation.outcome == OUT_OF_DISTRIBUTION
    assert result.evaluation.is_out_of_distribution is True
    assert result.experiment.lifecycle_state == "out_of_distribution"


def test_evaluate_visual_experiment_rejects_other_users_experiment(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database, owner="OWNER-USER")
    with pytest.raises(VisualExperimentOwnershipError):
        evaluate_visual_experiment(
            experiment.experiment_id, actor="OTHER-USER", actor_role="operator",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_evaluate_visual_experiment_cannot_be_rerun_once_evaluated(isolated_database: Path) -> None:
    experiment = _prepare_trainable_experiment(isolated_database)
    evaluate_visual_experiment(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    # The experiment is no longer `training`, so the re-attempt fails at
    # train_visual_baseline_model()'s own precondition check before the
    # evaluation transition is ever reached.
    with pytest.raises(VisualBaselineTrainingError):
        evaluate_visual_experiment(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )
