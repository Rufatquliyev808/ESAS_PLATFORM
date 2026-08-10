from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from backend.app.analysis.bars import MarketBar, build_closed_mid_bars
from backend.app.analysis.visual_acceptance import ACCEPTED_FOR_SHADOW, REJECTED
from backend.app.analysis.visual_baseline_trainer import BASELINE_ARCHITECTURE_ID
from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_model_spec import ModelSpec, TrainingSpec
from backend.app.analysis.visual_render import RenderSpec, render_canonical_chart
from backend.app.analysis.visual_statistical_acceptance import decide_statistical_acceptance
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    create_replay_session,
    get_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.database.visual_acceptance_repository import get_acceptance_decision
from backend.app.database.visual_experiment_repository import (
    VisualExperimentOwnershipError,
    get_visual_experiment,
    mark_evaluated,
    register_visual_experiment,
)
from backend.app.database.visual_testing_trial_repository import count_family_trials
from backend.app.storage.artifact_store import has_artifact, put_artifact
from backend.app.strategies.visual_experiment_acceptance import (
    VisualAcceptanceError,
    decide_visual_experiment_acceptance,
)
from backend.app.strategies.visual_experiment_evaluation import evaluate_visual_experiment
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_experiment_training import start_visual_experiment_training


BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
SMALL_SPEC = RenderSpec(width=20, height=16, padding_top=2, padding_bottom=2, padding_left=2, padding_right=2)

BASELINE_MODEL_SPEC = ModelSpec(
    architecture_id=BASELINE_ARCHITECTURE_ID, preprocessing_policy="normalize_0_1",
    class_weight_policy="balanced",
)
DEFAULT_TRAINING_SPEC = TrainingSpec(
    seed=42, optimizer="adam", loss="cross_entropy", batch_size=4, max_epochs=10, compute_requirement="cpu",
)


def _seed_ticks(end_time: datetime, *, tag: str) -> None:
    rows = []
    t = BASE_TIME
    index = 0
    while t < end_time:
        price = 4100.0 + (index % 20) * 0.5
        bid = round(price, 2)
        ask = round(price + 0.4, 2)
        rows.append((
            f"GOLD:{tag}:{index:05d}", "TICK_RECEIVED",
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


def _prepare_evaluated_experiment(database_path: Path, *, owner: str = "TEST-USER"):
    """Reaches `evaluated` with the natural (unlearnable, randomly-relative-
    to-content) label assignment from earlier increments' fixtures -- the
    model cannot do better than chance here, so this is used for the
    natural-rejection test.
    """
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_time = BASE_TIME + timedelta(minutes=40)
    _seed_ticks(end_time, tag="accept")
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
    evaluate_visual_experiment(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    return experiment


def _prepare_learnable_evaluated_experiment(database_path: Path, *, owner: str = "TEST-USER", tag: str = "learn"):
    """A larger (70-minute) session tuned to give train=12/validation=9/
    holdout=11, with a genuinely learnable signal injected AFTER the
    training-readiness gate has already passed (mutating samples earlier
    would change the recomputed dataset fingerprint and trip that gate):
    every "up"-labeled train/holdout sample's PNG artifact is swapped for a
    solid-black image, every "down"-labeled one for a solid-white image, so
    the centroid classifier can genuinely learn to separate them.
    """
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_time = BASE_TIME + timedelta(minutes=70)
    _seed_ticks(end_time, tag=tag)
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
        observation_window_bars=2, train_end_at=(BASE_TIME + timedelta(minutes=25)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(minutes=45)).isoformat(),
    )
    render_visual_experiment(experiment.experiment_id, actor=owner, actor_role="operator")

    with get_connection() as connection:
        for split in ("train", "holdout"):
            sample_ids = [
                row["sample_id"]
                for row in connection.execute(
                    "SELECT sample_id FROM visual_dataset_samples "
                    "WHERE experiment_id = ? AND split_id = ? ORDER BY sample_id;",
                    (experiment.experiment_id, split),
                ).fetchall()
            ]
            for index, sample_id in enumerate(sample_ids):
                connection.execute(
                    "UPDATE visual_dataset_samples SET label_value = ? WHERE experiment_id = ? AND sample_id = ?;",
                    ("up" if index % 2 == 0 else "down", experiment.experiment_id, sample_id),
                )
        connection.execute(
            "UPDATE visual_dataset_samples SET label_value = 'up' WHERE experiment_id = ? AND split_id = 'validation';",
            (experiment.experiment_id,),
        )

    start_visual_experiment_training(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    far_bar = MarketBar(
        symbol="GOLD", timeframe="M1", start_at="2026-08-01T08:00:00.000000+00:00",
        end_at="2026-08-01T08:01:00.000000+00:00", open=1.0, high=1.5, low=0.5, close=1.2,
        tick_count=1, tick_volume=1, spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"{tag}:0", last_event_id=f"{tag}:1",
    )
    up_spec = RenderSpec(
        width=SMALL_SPEC.width, height=SMALL_SPEC.height, padding_top=SMALL_SPEC.padding_top,
        padding_bottom=SMALL_SPEC.padding_bottom, padding_left=SMALL_SPEC.padding_left,
        padding_right=SMALL_SPEC.padding_right, background_rgb=(0, 0, 0), bullish_rgb=(0, 0, 0),
        bearish_rgb=(0, 0, 0), wick_rgb=(0, 0, 0),
    )
    down_spec = RenderSpec(
        width=SMALL_SPEC.width, height=SMALL_SPEC.height, padding_top=SMALL_SPEC.padding_top,
        padding_bottom=SMALL_SPEC.padding_bottom, padding_left=SMALL_SPEC.padding_left,
        padding_right=SMALL_SPEC.padding_right, background_rgb=(255, 255, 255), bullish_rgb=(255, 255, 255),
        bearish_rgb=(255, 255, 255), wick_rgb=(255, 255, 255),
    )
    up_image = render_canonical_chart((far_bar,), bar_fingerprint=f"sha256:{tag}-up", spec=up_spec)
    down_image = render_canonical_chart((far_bar,), bar_fingerprint=f"sha256:{tag}-down", spec=down_spec)
    up_artifact_checksum = f"sha256:{sha256(up_image.png_bytes).hexdigest()}"
    down_artifact_checksum = f"sha256:{sha256(down_image.png_bytes).hexdigest()}"
    put_artifact(up_artifact_checksum, up_image.png_bytes, extension="png")
    put_artifact(down_artifact_checksum, down_image.png_bytes, extension="png")

    with get_connection() as connection:
        for split in ("train", "holdout"):
            rows = connection.execute(
                "SELECT sample_id, label_value FROM visual_dataset_samples "
                "WHERE experiment_id = ? AND split_id = ?;",
                (experiment.experiment_id, split),
            ).fetchall()
            for row in rows:
                if row["label_value"] == "up":
                    connection.execute(
                        "UPDATE visual_dataset_samples SET image_checksum = ?, artifact_checksum = ? "
                        "WHERE experiment_id = ? AND sample_id = ?;",
                        (up_image.image_checksum, up_artifact_checksum, experiment.experiment_id, row["sample_id"]),
                    )
                else:
                    connection.execute(
                        "UPDATE visual_dataset_samples SET image_checksum = ?, artifact_checksum = ? "
                        "WHERE experiment_id = ? AND sample_id = ?;",
                        (down_image.image_checksum, down_artifact_checksum, experiment.experiment_id, row["sample_id"]),
                    )

    evaluate_visual_experiment(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    return experiment


def test_decide_visual_experiment_acceptance_rejects_when_model_underperforms(
    isolated_database: Path,
) -> None:
    experiment = _prepare_evaluated_experiment(isolated_database)
    result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert result.decision.decision == REJECTED
    assert result.experiment.lifecycle_state == "rejected"
    assert has_artifact(result.decision.checksum, extension="json")

    stored_experiment = get_visual_experiment(experiment.experiment_id)
    assert stored_experiment.lifecycle_state == "rejected"
    stored_decision = get_acceptance_decision(experiment.experiment_id)
    assert stored_decision is not None
    assert stored_decision.decision == REJECTED


def test_decide_visual_experiment_acceptance_reaches_accepted_for_shadow_with_single_trial(
    isolated_database: Path,
) -> None:
    experiment = _prepare_learnable_evaluated_experiment(isolated_database)
    result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )

    assert result.decision.decision == ACCEPTED_FOR_SHADOW
    assert result.decision.reasons == ()
    assert result.decision.family_trial_count == 1
    assert result.decision.corrected_alpha == pytest.approx(0.05)
    assert result.decision.trial_registered is True
    assert result.decision.reproduction_verified is True
    assert result.experiment.lifecycle_state == "accepted_for_shadow"
    assert has_artifact(result.decision.checksum, extension="json")

    stored_decision = get_acceptance_decision(experiment.experiment_id)
    assert stored_decision is not None
    assert stored_decision.decision == ACCEPTED_FOR_SHADOW


def test_family_trial_count_records_the_single_registered_trial(isolated_database: Path) -> None:
    experiment = _prepare_learnable_evaluated_experiment(isolated_database)
    result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert count_family_trials(result.decision.testing_family_id) == 1


def test_same_evidence_is_rejected_once_family_has_accumulated_many_trials(
    isolated_database: Path,
) -> None:
    """The core multiple-testing acceptance criterion, demonstrated with
    REAL pipeline-derived numbers: the exact same holdout evidence that
    reached `accepted_for_shadow` for a single-trial family is `rejected`
    once Bonferroni correction is applied for a much larger family --
    re-run as a pure re-decision (not a second orchestrator pass, since the
    experiment has already moved past `evaluated`) with the real p_value/
    counts the first decision computed.
    """
    experiment = _prepare_learnable_evaluated_experiment(isolated_database)
    single_trial_result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    d = single_trial_result.decision
    assert d.decision == ACCEPTED_FOR_SHADOW

    large_family_decision = decide_statistical_acceptance(
        testing_family_id=d.testing_family_id, family_trial_count=1000,
        trial_registered=d.trial_registered, reproduction_verified=d.reproduction_verified,
        evaluation_outcome=d.evaluation_outcome, holdout_sample_count=d.holdout_sample_count,
        holdout_correct_count=d.holdout_correct_count,
        majority_baseline_accuracy=d.majority_baseline_accuracy,
        evaluation_checksum=d.evaluation_checksum, model_checksum=d.model_checksum,
    )
    assert large_family_decision.decision == REJECTED
    assert large_family_decision.corrected_alpha < d.corrected_alpha
    assert large_family_decision.p_value == pytest.approx(d.p_value)


def test_decide_visual_experiment_acceptance_rejects_other_users_experiment(
    isolated_database: Path,
) -> None:
    experiment = _prepare_evaluated_experiment(isolated_database, owner="OWNER-USER")
    with pytest.raises(VisualExperimentOwnershipError):
        decide_visual_experiment_acceptance(
            experiment.experiment_id, actor="OTHER-USER", actor_role="operator",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_decide_visual_experiment_acceptance_rejects_experiment_not_evaluated(
    isolated_database: Path,
) -> None:
    end_time = BASE_TIME + timedelta(minutes=30)
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    _seed_ticks(end_time, tag="notevald")
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
    # Still "registered" -- never rendered, trained, or evaluated.
    with pytest.raises(VisualAcceptanceError):
        decide_visual_experiment_acceptance(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_decide_visual_experiment_acceptance_requires_a_persisted_evaluation(
    isolated_database: Path,
) -> None:
    end_time = BASE_TIME + timedelta(minutes=30)
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    _seed_ticks(end_time, tag="noeval")
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
    render_visual_experiment(experiment.experiment_id, actor="TEST-USER", actor_role="operator")
    rendered = get_visual_experiment(experiment.experiment_id)
    # Directly force `training -> evaluated` bypassing the real evaluation
    # orchestrator entirely, simulating a corrupted/incomplete lifecycle
    # where no evaluation was ever actually persisted.
    from backend.app.database.visual_experiment_repository import start_training

    trained = start_training(
        experiment_id=rendered.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=rendered.state_version,
    )
    mark_evaluated(
        experiment_id=trained.experiment_id, actor="TEST-USER", actor_role="operator",
        expected_state_version=trained.state_version,
    )

    with pytest.raises(VisualAcceptanceError):
        decide_visual_experiment_acceptance(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_decide_visual_experiment_acceptance_cannot_be_rerun_once_decided(
    isolated_database: Path,
) -> None:
    experiment = _prepare_evaluated_experiment(isolated_database)
    decide_visual_experiment_acceptance(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    with pytest.raises(VisualAcceptanceError):
        decide_visual_experiment_acceptance(
            experiment.experiment_id, actor="TEST-USER", actor_role="operator",
            model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
        )


def test_decide_visual_experiment_acceptance_rejects_on_reproduction_mismatch(
    isolated_database: Path,
) -> None:
    """If the persisted `visual_baseline_models.model_checksum` no longer
    matches what a fresh recomputation from the same persisted samples
    produces (e.g. historical tampering, or a record from a different run),
    `reproduction_verified` is False and the decision is rejected, never
    `accepted_for_shadow`, regardless of how good the holdout evidence is.
    """
    experiment = _prepare_learnable_evaluated_experiment(isolated_database)
    with get_connection() as connection:
        connection.execute(
            "UPDATE visual_baseline_models SET model_checksum = ? WHERE experiment_id = ?;",
            ("sha256:" + "0" * 64, experiment.experiment_id),
        )

    result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor="TEST-USER", actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert result.decision.reproduction_verified is False
    assert result.decision.decision == REJECTED
    assert "model_reproduction_checksum_mismatch" in result.decision.reasons
