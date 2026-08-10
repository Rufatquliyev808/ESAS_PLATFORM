from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.analysis.bars import MarketBar, build_closed_mid_bars
from backend.app.analysis.visual_acceptance import ACCEPTED_FOR_SHADOW
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
from backend.app.database.tick_replay_repository import iter_tick_batches
from backend.app.database.visual_experiment_repository import register_visual_experiment
from backend.app.main import app
from backend.app.strategies.visual_experiment_acceptance import decide_visual_experiment_acceptance
from backend.app.strategies.visual_experiment_evaluation import evaluate_visual_experiment
from backend.app.strategies.visual_experiment_materialization import render_visual_experiment
from backend.app.strategies.visual_experiment_training import start_visual_experiment_training


def _prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def _headers(client: TestClient, user_code: str = "TEST-USER") -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"user_code": user_code, "password": "test-password-123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_payload(risk_budget: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "planned_end_at": "2026-09-01T00:00:00+00:00",
        "code_commit": "abc123",
        "config_hash": "sha256:config",
        "feature_claim_versions": ["market_structure:1.0.0"],
        "symbols": ["GOLD"],
        "timeframes": ["M5"],
        "sessions": ["london"],
        "accepted_market_regimes": ["trending"],
        "minimum_market_open_duration_seconds": 3600,
        "minimum_eligible_decision_count": 30,
        "primary_metric": "net_return_percent",
        "primary_metric_threshold": 0.5,
        "secondary_metrics": {},
        "failure_rules": {},
        "theoretical_fill_model": {},
        "risk_budget": risk_budget or {},
        "data_quality_policy": {},
        "approved_by": "RISK-OFFICER",
        "rollback_plan": "halt and archive run",
        "participants": [{"role": "champion", "module_id": "structure_break_long", "module_version": "1.0.0"}],
    }


VISUAL_BASE_TIME = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
VISUAL_SMALL_SPEC = RenderSpec(width=20, height=16, padding_top=2, padding_bottom=2, padding_left=2, padding_right=2)
VISUAL_MODEL_SPEC = ModelSpec(
    architecture_id=BASELINE_ARCHITECTURE_ID, preprocessing_policy="normalize_0_1",
    class_weight_policy="balanced",
)
VISUAL_TRAINING_SPEC = TrainingSpec(
    seed=42, optimizer="adam", loss="cross_entropy", batch_size=4, max_epochs=10, compute_requirement="cpu",
)


def _seed_visual_ticks(end_time: datetime, *, tag: str) -> None:
    rows = []
    t = VISUAL_BASE_TIME
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


def _prepare_accepted_visual_experiment(database_path: Path, *, owner: str = "TEST-USER", tag: str = "shadow-api-learn") -> str:
    """Reaches a real `accepted_for_shadow` Visual AI experiment -- same
    learnable-signal technique as test_visual_experiment_acceptance.py."""
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    end_time = VISUAL_BASE_TIME + timedelta(minutes=70)
    _seed_visual_ticks(end_time, tag=tag)
    created = create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=VISUAL_BASE_TIME, end_at=end_time, mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor=owner, actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=500)
    session = get_replay_session(running.session_id)
    ticks = (
        tick
        for batch in iter_tick_batches(symbol=session.symbol, start_at=VISUAL_BASE_TIME, end_at=end_time)
        for tick in batch
    )
    bar_result = build_closed_mid_bars(
        ticks, timeframe="M1", end_at=end_time, source_fingerprint=session.dataset_fingerprint,
    )

    experiment = register_visual_experiment(
        created_by=owner, actor_role="operator", replay_session_id=session.session_id,
        symbol="GOLD", timeframe="M1", source_bar_fingerprint=bar_result.fingerprint,
        render_spec=VISUAL_SMALL_SPEC, label_spec=LabelSpec(1, 15.0, -15.0),
        observation_window_bars=2, train_end_at=(VISUAL_BASE_TIME + timedelta(minutes=25)).isoformat(),
        validation_end_at=(VISUAL_BASE_TIME + timedelta(minutes=45)).isoformat(),
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
        model_spec=VISUAL_MODEL_SPEC, training_spec=VISUAL_TRAINING_SPEC,
    )

    far_bar = MarketBar(
        symbol="GOLD", timeframe="M1", start_at="2026-08-01T08:00:00.000000+00:00",
        end_at="2026-08-01T08:01:00.000000+00:00", open=1.0, high=1.5, low=0.5, close=1.2,
        tick_count=1, tick_volume=1, spread_min=0.1, spread_max=0.1, spread_mean=0.1,
        first_event_id=f"{tag}:0", last_event_id=f"{tag}:1",
    )
    up_spec = RenderSpec(
        width=VISUAL_SMALL_SPEC.width, height=VISUAL_SMALL_SPEC.height, padding_top=VISUAL_SMALL_SPEC.padding_top,
        padding_bottom=VISUAL_SMALL_SPEC.padding_bottom, padding_left=VISUAL_SMALL_SPEC.padding_left,
        padding_right=VISUAL_SMALL_SPEC.padding_right, background_rgb=(0, 0, 0), bullish_rgb=(0, 0, 0),
        bearish_rgb=(0, 0, 0), wick_rgb=(0, 0, 0),
    )
    down_spec = RenderSpec(
        width=VISUAL_SMALL_SPEC.width, height=VISUAL_SMALL_SPEC.height, padding_top=VISUAL_SMALL_SPEC.padding_top,
        padding_bottom=VISUAL_SMALL_SPEC.padding_bottom, padding_left=VISUAL_SMALL_SPEC.padding_left,
        padding_right=VISUAL_SMALL_SPEC.padding_right, background_rgb=(255, 255, 255), bullish_rgb=(255, 255, 255),
        bearish_rgb=(255, 255, 255), wick_rgb=(255, 255, 255),
    )
    up_image = render_canonical_chart((far_bar,), bar_fingerprint=f"sha256:{tag}-up", spec=up_spec)
    down_image = render_canonical_chart((far_bar,), bar_fingerprint=f"sha256:{tag}-down", spec=down_spec)
    up_artifact_checksum = f"sha256:{sha256(up_image.png_bytes).hexdigest()}"
    down_artifact_checksum = f"sha256:{sha256(down_image.png_bytes).hexdigest()}"
    from backend.app.storage.artifact_store import put_artifact

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
        model_spec=VISUAL_MODEL_SPEC, training_spec=VISUAL_TRAINING_SPEC,
    )
    result = decide_visual_experiment_acceptance(
        experiment.experiment_id, actor=owner, actor_role="operator",
        model_spec=VISUAL_MODEL_SPEC, training_spec=VISUAL_TRAINING_SPEC,
    )
    assert result.decision.decision == ACCEPTED_FOR_SHADOW
    return experiment.experiment_id


def test_create_shadow_run_persists_visual_lineage_via_api(isolated_database: Path) -> None:
    experiment_id = _prepare_accepted_visual_experiment(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        payload = _create_payload()
        payload["participants"] = [
            {"role": "champion", "module_id": "structure_break_long", "module_version": "1.0.0"},
            {
                "role": "challenger", "module_id": "visual_ai_baseline", "module_version": "1.0.0",
                "visual_experiment_id": experiment_id,
            },
        ]
        response = client.post("/api/v2/shadow-runs", json=payload, headers=headers)
    assert response.status_code == 200
    challenger = next(p for p in response.json()["data"]["participants"] if p["role"] == "challenger")
    assert challenger["visual_experiment_id"] == experiment_id
    assert challenger["visual_model_checksum"] is not None
    assert challenger["visual_acceptance_decision_checksum"] is not None


def test_create_shadow_run_rejects_visual_experiment_that_is_not_accepted_for_shadow(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        payload = _create_payload()
        payload["participants"] = [
            {"role": "champion", "module_id": "structure_break_long", "module_version": "1.0.0"},
            {
                "role": "challenger", "module_id": "visual_ai_baseline", "module_version": "1.0.0",
                "visual_experiment_id": "does-not-exist",
            },
        ]
        response = client.post("/api/v2/shadow-runs", json=payload, headers=headers)
    assert response.status_code == 422


def test_create_and_get_shadow_run(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers)
        assert created.status_code == 200
        run_id = created.json()["data"]["shadow_run_id"]
        assert created.json()["data"]["execution_allowed"] is False
        assert created.json()["data"]["state"] == "registered"

        detail = client.get(f"/api/v2/shadow-runs/{run_id}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["data"]["shadow_run_id"] == run_id


def test_create_rejects_invalid_participants(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        payload = _create_payload()
        payload["participants"] = [
            {"role": "challenger", "module_id": "a", "module_version": "1.0.0"},
        ]
        response = client.post("/api/v2/shadow-runs", json=payload, headers=headers)
        assert response.status_code == 422


def test_unauthenticated_request_is_rejected(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        response = client.post("/api/v2/shadow-runs", json=_create_payload())
    assert response.status_code == 401


def test_list_shadow_runs_returns_created_run(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers)
        run_id = created.json()["data"]["shadow_run_id"]
        listed = client.get("/api/v2/shadow-runs", headers=headers)
    assert listed.status_code == 200
    assert any(item["shadow_run_id"] == run_id for item in listed.json()["data"])


def test_missing_shadow_run_returns_404(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.get("/api/v2/shadow-runs/missing", headers=headers)
    assert response.status_code == 404


def test_lifecycle_start_then_complete(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        started = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/start",
            json={"expected_state_version": created["state_version"]}, headers=headers,
        ).json()["data"]
        assert started["state"] == "started"
        completed = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/complete",
            json={"expected_state_version": started["state_version"]}, headers=headers,
        )
    assert completed.status_code == 200
    assert completed.json()["data"]["state"] == "completed"


def test_halt_from_registered_records_reason(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        halted = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/halt",
            json={"expected_state_version": created["state_version"], "reason": "order adapter call attempted"},
            headers=headers,
        )
    assert halted.status_code == 200
    assert halted.json()["data"]["state"] == "halted"
    assert halted.json()["data"]["halt_reason"] == "order adapter call attempted"


def test_stale_state_version_returns_409(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        response = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/start",
            json={"expected_state_version": created["state_version"] + 1}, headers=headers,
        )
    assert response.status_code == 409


def test_record_and_list_events(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        run_id = created["shadow_run_id"]
        recorded = client.post(
            f"/api/v2/shadow-runs/{run_id}/events",
            json={"event_type": "SHADOW_RUN_STARTED", "correlation_id": "corr-1", "payload": {"note": "manual"}},
            headers=headers,
        )
        assert recorded.status_code == 200
        listed = client.get(f"/api/v2/shadow-runs/{run_id}/events", headers=headers)
    assert listed.status_code == 200
    assert any(item["event_id"] == recorded.json()["data"]["event_id"] for item in listed.json()["data"])


def test_record_event_rejects_unsupported_type(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        response = client.post(
            f"/api/v2/shadow-runs/{created['shadow_run_id']}/events",
            json={"event_type": "ORDER_PLACED", "correlation_id": "corr-1", "payload": {}}, headers=headers,
        )
    assert response.status_code == 422


def test_open_list_close_position_and_summary_updates(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        run_id = created["shadow_run_id"]
        participant_id = created["participants"][0]["participant_id"]

        opened = client.post(
            f"/api/v2/shadow-runs/{run_id}/positions",
            json={
                "participant_id": participant_id, "symbol": "GOLD", "direction": "long",
                "theoretical_size": 1.0, "reserved_risk_amount": 2.0, "correlation_id": "corr-1",
            },
            headers=headers,
        )
        assert opened.status_code == 200
        assert opened.json()["data"]["opened"] is True
        position_id = opened.json()["data"]["position"]["position_id"]

        listed = client.get(f"/api/v2/shadow-runs/{run_id}/positions", headers=headers)
        assert any(item["position_id"] == position_id for item in listed.json()["data"])

        summary_before = client.get(f"/api/v2/shadow-runs/{run_id}/portfolio-summary", headers=headers).json()["data"]
        assert summary_before["open_position_count"] == 1
        assert summary_before["total_reserved_risk_amount"] == 2.0

        closed = client.post(
            f"/api/v2/shadow-runs/{run_id}/positions/{position_id}/close",
            json={"theoretical_pnl_percent": 1.5, "expected_state_version": 0, "correlation_id": "corr-2"},
            headers=headers,
        )
        assert closed.status_code == 200
        assert closed.json()["data"]["state"] == "closed"

        summary_after = client.get(f"/api/v2/shadow-runs/{run_id}/portfolio-summary", headers=headers).json()["data"]
        assert summary_after["open_position_count"] == 0
        assert summary_after["net_realized_theoretical_pnl_percent"] == 1.5


def test_position_open_blocked_by_risk_budget(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        created = client.post(
            "/api/v2/shadow-runs", json=_create_payload(risk_budget={"max_concurrent_positions": 1}), headers=headers,
        ).json()["data"]
        run_id = created["shadow_run_id"]
        participant_id = created["participants"][0]["participant_id"]
        body = {
            "participant_id": participant_id, "symbol": "GOLD", "direction": "long",
            "theoretical_size": 1.0, "reserved_risk_amount": 1.0, "correlation_id": "corr-1",
        }
        first = client.post(f"/api/v2/shadow-runs/{run_id}/positions", json=body, headers=headers)
        assert first.json()["data"]["opened"] is True
        second = client.post(f"/api/v2/shadow-runs/{run_id}/positions", json=body, headers=headers)
    assert second.status_code == 200
    assert second.json()["data"]["opened"] is False
    assert second.json()["data"]["reason"] == "max_concurrent_positions_exceeded"


def test_close_position_from_wrong_run_returns_404(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with TestClient(app) as client:
        headers = _headers(client)
        first_run = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        second_run = client.post("/api/v2/shadow-runs", json=_create_payload(), headers=headers).json()["data"]
        opened = client.post(
            f"/api/v2/shadow-runs/{first_run['shadow_run_id']}/positions",
            json={
                "participant_id": first_run["participants"][0]["participant_id"], "symbol": "GOLD",
                "direction": "long", "theoretical_size": 1.0, "reserved_risk_amount": 1.0,
                "correlation_id": "corr-1",
            },
            headers=headers,
        ).json()["data"]["position"]
        response = client.post(
            f"/api/v2/shadow-runs/{second_run['shadow_run_id']}/positions/{opened['position_id']}/close",
            json={"theoretical_pnl_percent": 1.0, "expected_state_version": 0, "correlation_id": "corr-2"},
            headers=headers,
        )
    assert response.status_code == 404
