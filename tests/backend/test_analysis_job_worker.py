from datetime import UTC, datetime, timedelta
from pathlib import Path

from backend.app.database.connection import get_connection, initialize_database
from backend.app.database.migration_runner import apply_migrations
from backend.app.database.analysis_job_repository import enqueue_job, get_job
from backend.app.database.pattern_candidate_repository import register_pattern_candidate
from backend.app.database.replay_session_repository import (
    create_replay_session,
    run_max_speed_replay,
    transition_replay_session,
)
from backend.app.workers.analysis_job_worker import drain_queue, run_worker_once


BASE_TIME = datetime(2026, 8, 4, 21, 0, tzinfo=UTC)


def _prepare(database_path: Path, *, owner: str = "TEST-USER"):
    initialize_database()
    apply_migrations(database_path, application_version="0.3.0")
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO tick_events
            (
                event_id, event_type, event_timestamp, received_at, source, event_version,
                symbol, bid, ask, last, volume, flags, source_time_msc,
                module_version, raw_event_json
            ) VALUES (?, 'TICK_RECEIVED', ?, ?, 'esas.mt5.bridge', '1.0',
                      'GOLD', ?, ?, ?, 1, 6, ?, '1.6.0', '{}');
            """,
            [
                (
                    f"GOLD:worker:{index:04d}",
                    (BASE_TIME + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
                    (BASE_TIME + timedelta(seconds=index * 5)).isoformat(timespec="microseconds"),
                    4100.0 + index,
                    4100.4 + index,
                    4100.2 + index,
                    int(BASE_TIME.timestamp() * 1000) + index * 5_000,
                )
                for index in range(1, 36)
            ],
        )
    created = create_replay_session(
        created_by=owner, actor_role="operator", symbol="GOLD",
        start_at=BASE_TIME, end_at=BASE_TIME + timedelta(minutes=3), mode="max_speed",
    )
    running = transition_replay_session(
        session_id=created.session_id, actor=owner, actor_role="operator",
        action="start", expected_state="created",
    )
    run_max_speed_replay(session_id=running.session_id, actor="WORKER", actor_role="worker", batch_size=10)
    return running


def _register_structure_break(session_id: str, created_by: str = "TEST-USER"):
    return register_pattern_candidate(
        created_by=created_by, actor_role="operator", replay_session_id=session_id,
        candidate_id="structure_break_long:worker", hypothesis_id="structure_break_long",
        hypothesis_version="1.0.0", family="bos_choch_retest", direction="long",
        condition_state="candidate_confirmed", observed_at="2026-08-04T21:00:10+00:00",
        evidence={}, pattern_candidate_version="1.0.0", hypothesis_registry_version="1.0.0",
        source_fingerprint="sha256:pattern", timeframe="M1",
        parameters={
            "bar_limit": 10, "pivot_left": 2, "pivot_right": 2, "equality_tolerance_bps": 0.0,
            "liquidity_pool_tolerance_bps": 10.0, "liquidity_minimum_touches": 2,
            "liquidity_minimum_sweep_bps": 1.0, "liquidity_maximum_pool_age_bars": 250,
            "bos_choch_minimum_close_break_bps": 1.0, "bos_choch_maximum_pivot_age_bars": 250,
            "retest_touch_tolerance_bps": 5.0, "retest_confirmation_close_bps": 0.0,
            "retest_invalidation_close_bps": 10.0, "retest_maximum_age_bars": 100,
        },
    )


def test_run_worker_once_returns_false_on_empty_queue(isolated_database: Path) -> None:
    _prepare(isolated_database)
    assert run_worker_once(worker_id="w1") is False


def test_run_worker_once_fails_job_when_candidate_missing(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    job = enqueue_job(
        job_type="pattern_candidate_backtest", created_by="TEST-USER",
        payload={"candidate_id": "does-not-exist"}, related_resource_id="does-not-exist",
        idempotency_key="k1",
    )
    processed = run_worker_once(worker_id="w1")
    assert processed is True
    reloaded = get_job(job.job_id)
    assert reloaded.state == "failed"
    assert "PatternCandidateNotFoundError" in reloaded.error_code


def test_run_worker_once_completes_a_real_backtest_job(isolated_database: Path) -> None:
    session = _prepare(isolated_database)
    candidate = _register_structure_break(session.session_id)
    job = enqueue_job(
        job_type="pattern_candidate_backtest", created_by="TEST-USER",
        payload={"candidate_id": candidate.candidate_id, "horizon_bars": 2},
        related_resource_id=candidate.candidate_id, idempotency_key="k1",
    )
    processed = run_worker_once(worker_id="w1")
    assert processed is True
    reloaded = get_job(job.job_id)
    assert reloaded.state == "completed"
    assert reloaded.result is not None
    assert reloaded.result["candidate_id"] == candidate.candidate_id
    assert reloaded.result["result"]["hypothesis_id"] == "structure_break_long"


def test_drain_queue_processes_multiple_jobs_up_to_limit(isolated_database: Path) -> None:
    _prepare(isolated_database)
    for index in range(2):
        enqueue_job(
            job_type="pattern_candidate_backtest", created_by="TEST-USER",
            payload={"candidate_id": "missing"}, related_resource_id="missing",
            idempotency_key=f"k{index}",
        )
    processed = drain_queue(worker_id="w1", max_jobs=1)
    assert processed == 1
    processed_rest = drain_queue(worker_id="w1", max_jobs=50)
    assert processed_rest == 1
