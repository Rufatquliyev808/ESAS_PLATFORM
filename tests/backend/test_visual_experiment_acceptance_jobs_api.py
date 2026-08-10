from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

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
from backend.app.database.visual_experiment_repository import register_visual_experiment
from backend.app.main import app
from backend.app.strategies.visual_experiment_evaluation import evaluate_visual_experiment
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_experiment_training import start_visual_experiment_training


BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
END_TIME = BASE_TIME + timedelta(minutes=40)
SMALL_SPEC = RenderSpec(width=20, height=16, padding_top=2, padding_bottom=2, padding_left=2, padding_right=2)

BASELINE_MODEL_SPEC = ModelSpec(
    architecture_id=BASELINE_ARCHITECTURE_ID, preprocessing_policy="normalize_0_1",
    class_weight_policy="balanced",
)
DEFAULT_TRAINING_SPEC = TrainingSpec(
    seed=42, optimizer="adam", loss="cross_entropy", batch_size=4, max_epochs=10, compute_requirement="cpu",
)
ACCEPTANCE_JOB_BODY = {
    "idempotency_key": "job-1",
    "architecture_id": BASELINE_ARCHITECTURE_ID,
    "preprocessing_policy": "normalize_0_1",
    "class_weight_policy": "balanced",
    "seed": 42,
    "optimizer": "adam",
    "loss": "cross_entropy",
    "batch_size": 4,
    "max_epochs": 10,
    "compute_requirement": "cpu",
}


def _seed_ticks(tag: str) -> None:
    rows = []
    t = BASE_TIME
    index = 0
    while t < END_TIME:
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


def _prepare(database_path: Path, *, owner: str = "TEST-USER", tag: str = "vaj-api"):
    """Registers, renders, gates into `training`, and evaluates an
    experiment -- the acceptance job wraps
    `decide_visual_experiment_acceptance()`, which requires `evaluated`.
    Deliberately uses the natural (unlearnable) alternating-label fixture,
    same as `test_visual_experiment_acceptance.py`'s
    `_prepare_evaluated_experiment` -- the model cannot beat chance here,
    so the decision deterministically lands on `rejected`, which is all
    these API-plumbing tests need.
    """
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    _seed_ticks(tag)
    created = create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=END_TIME, mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor=owner, actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=500)
    session = get_replay_session(running.session_id)

    ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=BASE_TIME, end_at=END_TIME)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe="M1", end_at=END_TIME, source_fingerprint=session.dataset_fingerprint,
    )
    experiment = register_visual_experiment(
        created_by=owner, actor_role="operator", replay_session_id=session.session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=bar_result.fingerprint,
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


def _headers(client: TestClient, user_code: str = "TEST-USER") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": user_code, "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_enqueue_acceptance_job_processes_via_background_task_and_completes(
    isolated_database: Path,
) -> None:
    experiment = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
        assert created.status_code == 202
        job_id = created.json()["data"]["job_id"]
        assert job_id.startswith("vaj_")
        detail = client.get(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs/{job_id}",
            headers=headers,
        )
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["state"] == "completed"
    assert body["result"]["experiment"]["lifecycle_state"] == "rejected"
    assert body["result"]["decision"]["decision"] == "rejected"


def test_enqueue_acceptance_job_is_idempotent_by_key(isolated_database: Path) -> None:
    experiment = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        first = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
        second = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
    assert first.json()["data"]["job_id"] == second.json()["data"]["job_id"]


def test_enqueue_acceptance_job_missing_experiment_returns_404(isolated_database: Path) -> None:
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post(
            "/api/v2/visual-experiments/does-not-exist/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
    assert response.status_code == 404


def test_acceptance_job_detail_rejects_wrong_experiment_path(isolated_database: Path) -> None:
    experiment = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
        job_id = created.json()["data"]["job_id"]
        mismatched = client.get(
            f"/api/v2/visual-experiments/some-other-experiment/acceptance-jobs/{job_id}",
            headers=headers,
        )
    assert mismatched.status_code == 404


def test_acceptance_job_detail_missing_returns_404(isolated_database: Path) -> None:
    experiment = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.get(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs/does-not-exist",
            headers=headers,
        )
    assert response.status_code == 404


def test_cancel_terminal_acceptance_job_returns_409(isolated_database: Path) -> None:
    experiment = _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
        job_id = created.json()["data"]["job_id"]
        cancel = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs/{job_id}/cancel",
            headers=headers,
        )
    assert cancel.status_code == 409


def test_acceptance_job_endpoints_require_ownership(isolated_database: Path) -> None:
    experiment = _prepare(isolated_database, owner="OTHER-OWNER", tag="vaj-owner")
    with TestClient(app) as client:
        headers = _headers(client, user_code="TEST-USER")
        forbidden_create = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
    assert forbidden_create.status_code == 403


def test_acceptance_job_fails_when_experiment_not_evaluated(isolated_database: Path) -> None:
    initialize_database()
    apply_migrations(isolated_database, application_version="0.3.0")
    _seed_ticks("vaj-notevald")
    created = create_replay_session(
        created_by="TEST-USER", actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=END_TIME, mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor="TEST-USER", actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=500)
    session = get_replay_session(running.session_id)
    ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=BASE_TIME, end_at=END_TIME)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe="M1", end_at=END_TIME, source_fingerprint=session.dataset_fingerprint,
    )
    experiment = register_visual_experiment(
        created_by="TEST-USER", actor_role="operator", replay_session_id=session.session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=bar_result.fingerprint,
        render_spec=SMALL_SPEC, label_spec=LabelSpec(1, 15.0, -15.0),
        observation_window_bars=2, train_end_at=(BASE_TIME + timedelta(minutes=24)).isoformat(),
        validation_end_at=(BASE_TIME + timedelta(minutes=32)).isoformat(),
    )
    # Still "registered" -- never rendered, trained, or evaluated.
    with TestClient(app) as client:
        headers = _headers(client)
        created_job = client.post(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs",
            json=ACCEPTANCE_JOB_BODY, headers=headers,
        )
        job_id = created_job.json()["data"]["job_id"]
        detail = client.get(
            f"/api/v2/visual-experiments/{experiment.experiment_id}/acceptance-jobs/{job_id}",
            headers=headers,
        )
    assert detail.json()["data"]["state"] == "failed"
