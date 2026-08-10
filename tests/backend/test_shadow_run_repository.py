from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
import sqlite3

import pytest

from backend.app.analysis.bars import MarketBar
from backend.app.analysis.visual_acceptance import ACCEPTED_FOR_SHADOW, REJECTED
from backend.app.analysis.visual_baseline_trainer import BASELINE_ARCHITECTURE_ID
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
from backend.app.database.shadow_run_repository import (
    ShadowRunConflictError,
    ShadowRunNotFoundError,
    ShadowRunOwnershipError,
    complete_shadow_run,
    get_shadow_run,
    halt_shadow_run,
    register_shadow_run,
    start_shadow_run,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.database.visual_experiment_repository import register_visual_experiment
from backend.app.storage.artifact_store import put_artifact
from backend.app.strategies.visual_experiment_acceptance import decide_visual_experiment_acceptance
from backend.app.strategies.visual_experiment_evaluation import evaluate_visual_experiment
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_experiment_training import start_visual_experiment_training


def _prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def _register(**overrides):
    defaults = dict(
        created_by="TEST-USER", planned_end_at="2026-09-01T00:00:00+00:00",
        code_commit="abc123", config_hash="sha256:config",
        feature_claim_versions=("market_structure:1.0.0", "liquidity_sweep:1.0.0"),
        symbols=("GOLD",), timeframes=("M5",), sessions=("london",),
        accepted_market_regimes=("trending", "ranging"),
        minimum_market_open_duration_seconds=3600, minimum_eligible_decision_count=30,
        primary_metric="net_return_percent", primary_metric_threshold=0.5,
        secondary_metrics={"max_drawdown_percent": 5.0}, failure_rules={"max_tail_loss_percent": 10.0},
        theoretical_fill_model={"spread_bps": 2.0, "latency_ms": 50},
        risk_budget={"max_concurrent_positions": 3}, data_quality_policy={"max_gap_seconds": 5},
        approved_by="RISK-OFFICER", rollback_plan="halt and archive run",
        participants=(("champion", "structure_break_long", "1.0.0"), ("challenger", "market_structure_long", "1.0.0")),
    )
    defaults.update(overrides)
    return register_shadow_run(**defaults)


def test_register_shadow_run_persists_full_manifest_and_participants(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    assert run.state == "registered"
    assert run.execution_allowed is False
    assert run.state_version == 0
    assert len(run.participants) == 2
    champion = next(p for p in run.participants if p.role == "champion")
    assert champion.module_id == "structure_break_long"


def test_register_requires_exactly_one_champion(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        _register(participants=(("challenger", "a", "1.0.0"),))
    with pytest.raises(ValueError):
        _register(participants=(("champion", "a", "1.0.0"), ("champion", "b", "1.0.0")))


def test_register_rejects_invalid_thresholds(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError):
        _register(minimum_market_open_duration_seconds=-1)
    with pytest.raises(ValueError):
        _register(minimum_eligible_decision_count=0)


def test_get_shadow_run_round_trips(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    reloaded = get_shadow_run(run.shadow_run_id)
    assert reloaded == run


def test_get_missing_shadow_run_raises(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ShadowRunNotFoundError):
        get_shadow_run("missing")


def test_lifecycle_registered_to_started_to_completed(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    started = start_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version)
    assert started.state == "started"
    completed = complete_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=started.state_version)
    assert completed.state == "completed"


def test_cannot_complete_before_starting(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with pytest.raises(ShadowRunConflictError):
        complete_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version)


def test_halt_is_reachable_from_registered_or_started(isolated_database: Path) -> None:
    _prepare(isolated_database)
    registered_run = _register()
    halted_from_registered = halt_shadow_run(
        shadow_run_id=registered_run.shadow_run_id, actor="TEST-USER",
        expected_state_version=registered_run.state_version, reason="order adapter call attempted",
    )
    assert halted_from_registered.state == "halted"
    assert halted_from_registered.halt_reason == "order adapter call attempted"

    started_run = _register()
    started = start_shadow_run(shadow_run_id=started_run.shadow_run_id, actor="TEST-USER", expected_state_version=started_run.state_version)
    halted_from_started = halt_shadow_run(
        shadow_run_id=started.shadow_run_id, actor="TEST-USER",
        expected_state_version=started.state_version, reason="critical safety event",
    )
    assert halted_from_started.state == "halted"


def test_cannot_transition_terminal_run(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    halted = halt_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version, reason="x")
    with pytest.raises(ShadowRunConflictError):
        start_shadow_run(shadow_run_id=halted.shadow_run_id, actor="TEST-USER", expected_state_version=halted.state_version)


def test_transition_enforces_ownership_and_optimistic_lock(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with pytest.raises(ShadowRunOwnershipError):
        start_shadow_run(shadow_run_id=run.shadow_run_id, actor="OTHER-USER", expected_state_version=run.state_version)
    with pytest.raises(ShadowRunConflictError):
        start_shadow_run(shadow_run_id=run.shadow_run_id, actor="TEST-USER", expected_state_version=run.state_version + 1)


def test_execution_allowed_cannot_be_forced_true_at_the_database_level(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE shadow_runs SET execution_allowed = 1 WHERE shadow_run_id = ?;",
                (run.shadow_run_id,),
            )


def test_manifest_fields_are_immutable_once_registered(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE shadow_runs SET primary_metric_threshold = 99.0 WHERE shadow_run_id = ?;",
                (run.shadow_run_id,),
            )


def test_shadow_run_participants_are_append_only(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    participant_id = run.participants[0].participant_id
    with get_connection() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE shadow_run_participants SET module_version = '2.0.0' WHERE participant_id = ?;",
                (participant_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "DELETE FROM shadow_run_participants WHERE participant_id = ?;",
                (participant_id,),
            )


# Phase 5 -> Phase 9 lineage-only connection: a SHADOW run challenger may
# reference the specific `accepted_for_shadow` Visual AI experiment it
# stands for. These fixtures reuse the exact "learnable signal" and
# "natural/unlearnable signal" techniques from
# test_visual_experiment_acceptance.py to reach real accepted_for_shadow /
# rejected experiments -- see that file's docstrings for why the mutation
# must happen AFTER the training-readiness gate.
BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
SMALL_SPEC = RenderSpec(width=20, height=16, padding_top=2, padding_bottom=2, padding_left=2, padding_right=2)
BASELINE_MODEL_SPEC = ModelSpec(
    architecture_id=BASELINE_ARCHITECTURE_ID, preprocessing_policy="normalize_0_1",
    class_weight_policy="balanced",
)
DEFAULT_TRAINING_SPEC = TrainingSpec(
    seed=42, optimizer="adam", loss="cross_entropy", batch_size=4, max_epochs=10, compute_requirement="cpu",
)


def _seed_visual_ticks(end_time: datetime, *, tag: str) -> None:
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
    from backend.app.analysis.bars import build_closed_mid_bars

    ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=BASE_TIME, end_at=end_time)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe="M1", end_at=end_time, source_fingerprint=session.dataset_fingerprint,
    )
    return bar_result.fingerprint


def _prepare_accepted_visual_experiment(database_path: Path, *, owner: str = "TEST-USER", tag: str = "shadow-learn") -> str:
    """Reaches a real `accepted_for_shadow` Visual AI experiment (70-minute
    session, learnable signal injected after the readiness gate)."""
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_time = BASE_TIME + timedelta(minutes=70)
    _seed_visual_ticks(end_time, tag=tag)
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
    result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert result.decision.decision == ACCEPTED_FOR_SHADOW
    return experiment.experiment_id


def _prepare_rejected_visual_experiment(database_path: Path, *, owner: str = "TEST-USER", tag: str = "shadow-reject") -> str:
    """Reaches a real, naturally-rejected Visual AI experiment (unlearnable
    alternating-label signal -- the model cannot beat chance)."""
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_time = BASE_TIME + timedelta(minutes=40)
    _seed_visual_ticks(end_time, tag=tag)
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
    result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=BASELINE_MODEL_SPEC, training_spec=DEFAULT_TRAINING_SPEC,
    )
    assert result.decision.decision == REJECTED
    return experiment.experiment_id


def test_register_shadow_run_persists_visual_lineage_for_accepted_experiment(isolated_database: Path) -> None:
    from backend.app.database.visual_acceptance_repository import get_acceptance_decision
    from backend.app.database.visual_baseline_model_repository import get_baseline_model

    experiment_id = _prepare_accepted_visual_experiment(isolated_database)
    run = _register(
        participants=(
            ("champion", "structure_break_long", "1.0.0"),
            ("challenger", "visual_ai_baseline", "1.0.0", experiment_id),
        ),
    )
    challenger = next(p for p in run.participants if p.role == "challenger")
    champion = next(p for p in run.participants if p.role == "champion")
    assert champion.visual_experiment_id is None

    model = get_baseline_model(experiment_id)
    decision = get_acceptance_decision(experiment_id)
    assert challenger.visual_experiment_id == experiment_id
    assert challenger.visual_model_checksum == model.model_checksum
    assert challenger.visual_acceptance_decision_checksum == decision.decision_checksum

    reloaded = get_shadow_run(run.shadow_run_id)
    reloaded_challenger = next(p for p in reloaded.participants if p.role == "challenger")
    assert reloaded_challenger.visual_experiment_id == experiment_id


def test_register_shadow_run_rejects_visual_lineage_on_champion(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError, match="challenger"):
        _register(
            participants=(
                ("champion", "structure_break_long", "1.0.0", "some-experiment-id"),
                ("challenger", "b", "1.0.0"),
            ),
        )


def test_register_shadow_run_rejects_missing_visual_experiment(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError, match="not found"):
        _register(
            participants=(
                ("champion", "structure_break_long", "1.0.0"),
                ("challenger", "visual_ai_baseline", "1.0.0", "does-not-exist"),
            ),
        )


def test_register_shadow_run_rejects_experiment_not_accepted_for_shadow(isolated_database: Path) -> None:
    experiment_id = _prepare_rejected_visual_experiment(isolated_database)
    with pytest.raises(ValueError, match="not accepted_for_shadow"):
        _register(
            participants=(
                ("champion", "structure_break_long", "1.0.0"),
                ("challenger", "visual_ai_baseline", "1.0.0", experiment_id),
            ),
        )


def test_register_shadow_run_without_visual_lineage_leaves_fields_none(isolated_database: Path) -> None:
    _prepare(isolated_database)
    run = _register()
    for participant in run.participants:
        assert participant.visual_experiment_id is None
        assert participant.visual_model_checksum is None
        assert participant.visual_acceptance_decision_checksum is None
