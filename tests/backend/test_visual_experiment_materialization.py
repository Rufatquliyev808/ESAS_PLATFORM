from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.app.analysis.bars import build_closed_mid_bars
from backend.app.analysis.replay_analysis import ReplayDatasetChangedError
from backend.app.analysis.visual_label import LabelSpec
from backend.app.analysis.visual_materializer import BarFingerprintMismatchError
from backend.app.analysis.visual_render import RenderSpec
from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.replay_session_repository import (
    ReplayTransitionConflictError,
    create_replay_session,
    get_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.database.visual_dataset_repository import count_dataset_samples, get_dataset_manifest
from backend.app.database.visual_experiment_repository import (
    VisualExperimentConflictError,
    VisualExperimentOwnershipError,
    get_visual_experiment,
    register_visual_experiment,
)
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment


BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
END_TIME = BASE_TIME + timedelta(minutes=30)


def _seed_ticks() -> None:
    rows = []
    t = BASE_TIME
    index = 0
    while t < END_TIME:
        price = 4100.0 + (index % 20) * 0.5
        bid = round(price, 2)
        ask = round(price + 0.4, 2)
        rows.append((
            f"GOLD:matorch:{index:05d}", "TICK_RECEIVED",
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


def _prepare(database_path: Path, *, owner: str = "TEST-USER"):
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    _seed_ticks()
    created = create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=END_TIME, mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor=owner, actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=500)
    return get_replay_session(running.session_id)


def _real_bar_fingerprint(session) -> str:
    ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=BASE_TIME, end_at=END_TIME)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe="M1", end_at=END_TIME, source_fingerprint=session.dataset_fingerprint,
    )
    return bar_result.fingerprint


def _register(session, *, created_by: str = "TEST-USER", source_bar_fingerprint: str):
    return register_visual_experiment(
        created_by=created_by, actor_role="operator", replay_session_id=session.session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=source_bar_fingerprint,
        render_spec=RenderSpec(), label_spec=LabelSpec(3, 15.0, -15.0),
        observation_window_bars=5, train_end_at=(BASE_TIME + timedelta(days=1)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(days=2)).isoformat(),
    )


def test_render_visual_experiment_succeeds_and_persists(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    fingerprint = _real_bar_fingerprint(session)
    experiment = _register(session, source_bar_fingerprint=fingerprint)

    result = render_visual_experiment(experiment.experiment_id, actor="TEST-USER", actor_role="operator")

    assert result.experiment.lifecycle_state == "rendering"
    assert result.sample_count > 0
    assert result.manifest.total_samples == result.sample_count
    assert count_dataset_samples(experiment.experiment_id) == result.sample_count

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "rendering"
    manifest = get_dataset_manifest(experiment.experiment_id)
    assert manifest is not None
    assert manifest.dataset_fingerprint == result.manifest.dataset_fingerprint


def test_render_visual_experiment_fails_closed_on_bar_fingerprint_mismatch(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    experiment = _register(session, source_bar_fingerprint="sha256:deliberately-wrong")

    with pytest.raises(BarFingerprintMismatchError):
        render_visual_experiment(experiment.experiment_id, actor="TEST-USER", actor_role="operator")

    stored = get_visual_experiment(experiment.experiment_id)
    assert stored.lifecycle_state == "failed"
    assert count_dataset_samples(experiment.experiment_id) == 0


def test_render_visual_experiment_rejects_incomplete_replay_session(isolated_database: Path) -> None:
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    _seed_ticks()
    created = create_replay_session(
        created_by="TEST-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=END_TIME, mode="max_speed",
    )
    experiment = _register(created, source_bar_fingerprint="sha256:irrelevant")

    with pytest.raises(ReplayTransitionConflictError):
        render_visual_experiment(experiment.experiment_id, actor="TEST-USER", actor_role="operator")


def test_render_visual_experiment_rejects_other_users_experiment(isolated_database: Path) -> None:
    session = _prepare(isolated_database, owner="OWNER-USER")
    fingerprint = _real_bar_fingerprint(session)
    experiment = _register(session, created_by="OWNER-USER", source_bar_fingerprint=fingerprint)

    with pytest.raises(VisualExperimentOwnershipError):
        render_visual_experiment(experiment.experiment_id, actor="OTHER-USER", actor_role="operator")


def test_render_visual_experiment_cannot_be_rerun_once_rendering(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    fingerprint = _real_bar_fingerprint(session)
    experiment = _register(session, source_bar_fingerprint=fingerprint)

    render_visual_experiment(experiment.experiment_id, actor="TEST-USER", actor_role="operator")

    with pytest.raises(VisualExperimentConflictError):
        render_visual_experiment(experiment.experiment_id, actor="TEST-USER", actor_role="operator")
