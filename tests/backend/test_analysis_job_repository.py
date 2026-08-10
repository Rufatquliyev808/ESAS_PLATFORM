from pathlib import Path

import pytest

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.analysis_job_repository import (
    AnalysisJobConflictError,
    AnalysisJobFencingError,
    AnalysisJobNotFoundError,
    AnalysisJobOwnershipError,
    AnalysisJobQueueFullError,
    claim_next_job,
    complete_job,
    enqueue_job,
    fail_job,
    get_job,
    queue_metrics,
    request_cancel,
    send_heartbeat,
)


def _prepare(database_path: Path) -> None:
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")


def _enqueue(created_by: str = "TEST-USER", key: str = "k1", priority: int = 3, resource: str = "candidate-1"):
    return enqueue_job(
        job_type="pattern_candidate_backtest", created_by=created_by,
        payload={"candidate_id": resource, "horizon_bars": 3}, related_resource_id=resource,
        idempotency_key=key, priority=priority,
    )


def test_enqueue_is_idempotent_for_same_key(isolated_database: Path) -> None:
    _prepare(isolated_database)
    first = _enqueue()
    second = _enqueue()
    assert first == second
    with get_connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM analysis_jobs;").fetchone()[0]
    assert count == 1


def test_enqueue_rejects_key_reused_by_another_user(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue(created_by="TEST-USER", key="shared")
    with pytest.raises(AnalysisJobOwnershipError):
        _enqueue(created_by="OTHER-USER", key="shared")


def test_enqueue_enforces_per_user_active_job_cap(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue(key="k1")
    _enqueue(key="k2")
    _enqueue(key="k3")
    with pytest.raises(AnalysisJobQueueFullError):
        _enqueue(key="k4")


def test_claim_returns_none_when_queue_empty(isolated_database: Path) -> None:
    _prepare(isolated_database)
    assert claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest") is None


def test_claim_is_exclusive_between_two_workers(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue(key="only")
    first = claim_next_job(worker_id="worker-a", job_type="pattern_candidate_backtest")
    second = claim_next_job(worker_id="worker-b", job_type="pattern_candidate_backtest")
    assert first is not None
    assert second is None
    assert first.lease_owner == "worker-a"
    assert first.state == "claimed"
    assert first.fencing_token == 1


def test_claim_orders_by_priority_then_creation_time(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue(key="low", priority=5)
    _enqueue(key="high", priority=1)
    _enqueue(key="mid", priority=3)
    first = claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    second = claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    third = claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    assert [job.priority for job in (first, second, third)] == [1, 3, 5]


def test_stale_fencing_token_is_rejected_after_reclaim(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue()
    claimed = claim_next_job(worker_id="worker-a", job_type="pattern_candidate_backtest")
    assert claimed is not None
    # Simulate worker-a's lease having already expired (e.g. it crashed).
    with get_connection() as connection:
        connection.execute(
            "UPDATE analysis_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?;",
            (claimed.job_id,),
        )
    reclaimed = claim_next_job(worker_id="worker-b", job_type="pattern_candidate_backtest")
    assert reclaimed is not None
    assert reclaimed.job_id == claimed.job_id
    assert reclaimed.lease_owner == "worker-b"
    assert reclaimed.fencing_token == claimed.fencing_token + 1
    with pytest.raises(AnalysisJobFencingError):
        send_heartbeat(job_id=claimed.job_id, worker_id="worker-a", fencing_token=claimed.fencing_token)
    with pytest.raises(AnalysisJobFencingError):
        complete_job(job_id=claimed.job_id, worker_id="worker-a", fencing_token=claimed.fencing_token, result={})
    # The rightful (new) owner can still write.
    heartbeat = send_heartbeat(job_id=reclaimed.job_id, worker_id="worker-b", fencing_token=reclaimed.fencing_token)
    assert heartbeat.state == "running"


def test_expired_lease_reclaim_records_interrupted_audit_and_bumps_attempts(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue()
    claimed = claim_next_job(worker_id="worker-a", job_type="pattern_candidate_backtest")
    with get_connection() as connection:
        connection.execute(
            "UPDATE analysis_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?;",
            (claimed.job_id,),
        )
    claim_next_job(worker_id="worker-b", job_type="pattern_candidate_backtest")
    with get_connection() as connection:
        audit = connection.execute(
            "SELECT action, previous_state, next_state FROM analysis_job_audit WHERE job_id = ? ORDER BY audit_id;",
            (claimed.job_id,),
        ).fetchall()
    actions = [tuple(row) for row in audit]
    assert ("interrupted", "claimed", "queued") in actions
    reloaded = get_job(claimed.job_id)
    assert reloaded.attempt_count == 2  # first claim + reclaim


def test_expired_lease_reclaim_fails_job_once_attempts_exhausted(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = enqueue_job(
        job_type="pattern_candidate_backtest", created_by="TEST-USER",
        payload={"candidate_id": "c"}, related_resource_id="c", idempotency_key="k", max_attempts=1,
    )
    claimed = claim_next_job(worker_id="worker-a", job_type="pattern_candidate_backtest")
    assert claimed.attempt_count == 1
    with get_connection() as connection:
        connection.execute(
            "UPDATE analysis_jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?;",
            (claimed.job_id,),
        )
    none_left = claim_next_job(worker_id="worker-b", job_type="pattern_candidate_backtest")
    assert none_left is None
    reloaded = get_job(claimed.job_id)
    assert reloaded.state == "failed"
    assert reloaded.error_code == "lease_expired_max_attempts"


def test_retry_only_happens_for_retryable_failures_within_max_attempts(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = enqueue_job(
        job_type="pattern_candidate_backtest", created_by="TEST-USER",
        payload={"candidate_id": "c"}, related_resource_id="c", idempotency_key="k", max_attempts=2,
    )
    claimed = claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    send_heartbeat(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token)
    retried = fail_job(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token, error_code="transient", retryable=True)
    assert retried.state == "retry_wait"
    assert retried.next_attempt_at is not None
    # Force it due now and reclaim for a second (final) attempt.
    with get_connection() as connection:
        connection.execute(
            "UPDATE analysis_jobs SET next_attempt_at = '2000-01-01T00:00:00+00:00' WHERE job_id = ?;",
            (claimed.job_id,),
        )
    second = claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    assert second is not None
    assert second.attempt_count == 2
    send_heartbeat(job_id=second.job_id, worker_id="w1", fencing_token=second.fencing_token)
    final = fail_job(job_id=second.job_id, worker_id="w1", fencing_token=second.fencing_token, error_code="transient", retryable=True)
    assert final.state == "failed"


def test_non_retryable_failure_goes_straight_to_failed(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue()
    claimed = claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    send_heartbeat(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token)
    failed = fail_job(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token, error_code="validation_error", retryable=False)
    assert failed.state == "failed"
    assert failed.error_code == "validation_error"


def test_complete_honors_a_cancel_requested_while_running(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue()
    claimed = claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    send_heartbeat(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token)
    request_cancel(job_id=claimed.job_id, actor="TEST-USER")
    finished = complete_job(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token, result={"ok": True})
    assert finished.state == "cancelled"
    assert finished.result is None


def test_cancel_from_queued_is_immediate(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue()
    cancelled = request_cancel(job_id=job.job_id, actor="TEST-USER")
    assert cancelled.state == "cancelled"


def test_cancel_rejects_terminal_state_and_wrong_owner(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue()
    request_cancel(job_id=job.job_id, actor="TEST-USER")
    with pytest.raises(AnalysisJobConflictError):
        request_cancel(job_id=job.job_id, actor="TEST-USER")
    job2 = _enqueue(key="k2")
    with pytest.raises(AnalysisJobOwnershipError):
        request_cancel(job_id=job2.job_id, actor="OTHER-USER")


def test_missing_job_raises_not_found(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(AnalysisJobNotFoundError):
        get_job("missing")


def test_queue_metrics_reports_depth_by_state(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue(key="k1")
    _enqueue(key="k2")
    claim_next_job(worker_id="w1", job_type="pattern_candidate_backtest")
    metrics = queue_metrics("pattern_candidate_backtest")
    assert metrics["depth_by_state"]["queued"] == 1
    assert metrics["depth_by_state"]["claimed"] == 1
    assert metrics["oldest_queued_age_seconds"] is not None
    assert metrics["oldest_queued_age_seconds"] >= 0


def test_payload_carries_no_secret_looking_fields(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue()
    forbidden = {"password", "token", "secret", "api_key", "access_token"}
    assert not (set(job.payload.keys()) & forbidden)


def _enqueue_statistical_analysis(created_by: str = "TEST-USER", key: str = "sa1", session_id: str = "session-1"):
    return enqueue_job(
        job_type="statistical_analysis", created_by=created_by,
        payload={"session_id": session_id, "timeframe": "M1", "minimum_sample_size": 30},
        related_resource_id=session_id, idempotency_key=key,
    )


def test_statistical_analysis_jobs_use_a_separate_table(isolated_database: Path) -> None:
    # analysis_jobs' job_type CHECK constraint (already applied to real
    # production) only allows 'pattern_candidate_backtest' -- statistical
    # analysis jobs must land in their own table, never that one.
    _prepare(isolated_database)
    job = _enqueue_statistical_analysis()
    assert job.job_id.startswith("saj_")
    with get_connection() as connection:
        own_table_count = connection.execute(
            "SELECT COUNT(*) FROM statistical_analysis_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
        other_table_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
    assert own_table_count == 1
    assert other_table_count == 0


def test_statistical_analysis_job_full_lifecycle_routes_to_its_own_table(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue_statistical_analysis()
    claimed = claim_next_job(worker_id="w1", job_type="statistical_analysis")
    assert claimed is not None
    assert claimed.job_id.startswith("saj_")
    running = send_heartbeat(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token)
    assert running.state == "running"
    finished = complete_job(job_id=claimed.job_id, worker_id="w1", fencing_token=claimed.fencing_token, result={"ok": True})
    assert finished.state == "completed"
    assert finished.result == {"ok": True}
    reloaded = get_job(claimed.job_id)
    assert reloaded.state == "completed"
    with get_connection() as connection:
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM statistical_analysis_job_audit WHERE job_id = ?;", (claimed.job_id,)
        ).fetchone()[0]
    assert audit_count >= 3  # enqueue, claim, complete


def test_pattern_candidate_and_statistical_analysis_job_ids_do_not_collide(isolated_database: Path) -> None:
    _prepare(isolated_database)
    pattern_job = _enqueue()
    stats_job = _enqueue_statistical_analysis()
    assert pattern_job.job_id.startswith("job_")
    assert stats_job.job_id.startswith("saj_")
    assert get_job(pattern_job.job_id).job_type == "pattern_candidate_backtest"
    assert get_job(stats_job.job_id).job_type == "statistical_analysis"
    # A per-user active-job cap is enforced independently per job type: three
    # pattern-candidate jobs plus one statistical-analysis job should not
    # trip the pattern-candidate queue's cap.
    _enqueue(key="k2")
    _enqueue(key="k3")
    metrics = queue_metrics("statistical_analysis")
    assert metrics["depth_by_state"]["queued"] == 1


def test_statistical_analysis_queue_metrics_are_independent_of_pattern_candidate_queue(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue_statistical_analysis(key="sa1")
    _enqueue_statistical_analysis(key="sa2", session_id="session-2")
    claim_next_job(worker_id="w1", job_type="statistical_analysis")
    metrics = queue_metrics("statistical_analysis")
    assert metrics["depth_by_state"]["queued"] == 1
    assert metrics["depth_by_state"]["claimed"] == 1
    pattern_metrics = queue_metrics("pattern_candidate_backtest")
    assert pattern_metrics["depth_by_state"] == {}


def test_queue_metrics_rejects_unsupported_job_type(isolated_database: Path) -> None:
    _prepare(isolated_database)
    with pytest.raises(ValueError, match="job_type"):
        queue_metrics("not_a_real_job_type")


def _enqueue_visual_experiment_rendering(created_by: str = "TEST-USER", key: str = "vrj1", experiment_id: str = "experiment-1"):
    return enqueue_job(
        job_type="visual_experiment_rendering", created_by=created_by,
        payload={"experiment_id": experiment_id}, related_resource_id=experiment_id,
        idempotency_key=key,
    )


def test_visual_experiment_rendering_jobs_use_a_separate_table(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue_visual_experiment_rendering()
    assert job.job_id.startswith("vrj_")
    with get_connection() as connection:
        own_table_count = connection.execute(
            "SELECT COUNT(*) FROM visual_experiment_rendering_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
        other_table_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
    assert own_table_count == 1
    assert other_table_count == 0


def test_visual_experiment_rendering_queue_metrics_are_independent(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue_visual_experiment_rendering(key="vrj1", experiment_id="experiment-1")
    _enqueue_visual_experiment_rendering(key="vrj2", experiment_id="experiment-2")
    claim_next_job(worker_id="w1", job_type="visual_experiment_rendering")
    metrics = queue_metrics("visual_experiment_rendering")
    assert metrics["depth_by_state"]["queued"] == 1
    assert metrics["depth_by_state"]["claimed"] == 1
    pattern_metrics = queue_metrics("pattern_candidate_backtest")
    assert pattern_metrics["depth_by_state"] == {}


def _enqueue_visual_experiment_training(created_by: str = "TEST-USER", key: str = "vtj1", experiment_id: str = "experiment-1"):
    return enqueue_job(
        job_type="visual_experiment_training", created_by=created_by,
        payload={
            "experiment_id": experiment_id,
            "model_spec": {
                "architecture_id": "pixel_centroid_baseline_v1", "preprocessing_policy": "normalize_0_1",
                "class_weight_policy": "balanced", "version": "1.0.0",
            },
            "training_spec": {
                "seed": 42, "optimizer": "adam", "loss": "cross_entropy", "batch_size": 4,
                "max_epochs": 10, "compute_requirement": "cpu", "version": "1.0.0",
            },
        },
        related_resource_id=experiment_id, idempotency_key=key,
    )


def test_visual_experiment_training_jobs_use_a_separate_table(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue_visual_experiment_training()
    assert job.job_id.startswith("vtj_")
    with get_connection() as connection:
        own_table_count = connection.execute(
            "SELECT COUNT(*) FROM visual_experiment_training_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
        other_table_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
    assert own_table_count == 1
    assert other_table_count == 0


def test_visual_experiment_training_queue_metrics_are_independent(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue_visual_experiment_training(key="vtj1", experiment_id="experiment-1")
    _enqueue_visual_experiment_training(key="vtj2", experiment_id="experiment-2")
    claim_next_job(worker_id="w1", job_type="visual_experiment_training")
    metrics = queue_metrics("visual_experiment_training")
    assert metrics["depth_by_state"]["queued"] == 1
    assert metrics["depth_by_state"]["claimed"] == 1
    pattern_metrics = queue_metrics("pattern_candidate_backtest")
    assert pattern_metrics["depth_by_state"] == {}


def _enqueue_visual_experiment_acceptance(created_by: str = "TEST-USER", key: str = "vaj1", experiment_id: str = "experiment-1"):
    return enqueue_job(
        job_type="visual_experiment_acceptance", created_by=created_by,
        payload={
            "experiment_id": experiment_id,
            "model_spec": {
                "architecture_id": "pixel_centroid_baseline_v1", "preprocessing_policy": "normalize_0_1",
                "class_weight_policy": "balanced", "version": "1.0.0",
            },
            "training_spec": {
                "seed": 42, "optimizer": "adam", "loss": "cross_entropy", "batch_size": 4,
                "max_epochs": 10, "compute_requirement": "cpu", "version": "1.0.0",
            },
        },
        related_resource_id=experiment_id, idempotency_key=key,
    )


def test_visual_experiment_acceptance_jobs_use_a_separate_table(isolated_database: Path) -> None:
    _prepare(isolated_database)
    job = _enqueue_visual_experiment_acceptance()
    assert job.job_id.startswith("vaj_")
    with get_connection() as connection:
        own_table_count = connection.execute(
            "SELECT COUNT(*) FROM visual_experiment_acceptance_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
        other_table_count = connection.execute(
            "SELECT COUNT(*) FROM analysis_jobs WHERE job_id = ?;", (job.job_id,)
        ).fetchone()[0]
    assert own_table_count == 1
    assert other_table_count == 0


def test_all_five_job_type_ids_do_not_collide(isolated_database: Path) -> None:
    _prepare(isolated_database)
    pattern_job = _enqueue()
    stats_job = _enqueue_statistical_analysis()
    rendering_job = _enqueue_visual_experiment_rendering()
    training_job = _enqueue_visual_experiment_training()
    acceptance_job = _enqueue_visual_experiment_acceptance()
    assert pattern_job.job_id.startswith("job_")
    assert stats_job.job_id.startswith("saj_")
    assert rendering_job.job_id.startswith("vrj_")
    assert training_job.job_id.startswith("vtj_")
    assert acceptance_job.job_id.startswith("vaj_")
    assert get_job(pattern_job.job_id).job_type == "pattern_candidate_backtest"
    assert get_job(stats_job.job_id).job_type == "statistical_analysis"
    assert get_job(rendering_job.job_id).job_type == "visual_experiment_rendering"
    assert get_job(training_job.job_id).job_type == "visual_experiment_training"
    assert get_job(acceptance_job.job_id).job_type == "visual_experiment_acceptance"


def test_visual_experiment_acceptance_queue_metrics_are_independent(isolated_database: Path) -> None:
    _prepare(isolated_database)
    _enqueue_visual_experiment_acceptance(key="vaj1", experiment_id="experiment-1")
    _enqueue_visual_experiment_acceptance(key="vaj2", experiment_id="experiment-2")
    claim_next_job(worker_id="w1", job_type="visual_experiment_acceptance")
    metrics = queue_metrics("visual_experiment_acceptance")
    assert metrics["depth_by_state"]["queued"] == 1
    assert metrics["depth_by_state"]["claimed"] == 1
    pattern_metrics = queue_metrics("pattern_candidate_backtest")
    assert pattern_metrics["depth_by_state"] == {}
