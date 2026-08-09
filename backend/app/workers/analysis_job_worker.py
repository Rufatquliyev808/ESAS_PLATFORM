from dataclasses import asdict
import sqlite3

from backend.app.database.analysis_job_repository import (
    AnalysisJob,
    claim_next_job,
    complete_job,
    fail_job,
    send_heartbeat,
)
from backend.app.database.pattern_candidate_backtest_repository import (
    PatternCandidateBacktestNotFoundError,
)
from backend.app.database.pattern_candidate_repository import (
    PatternCandidateConflictError,
    PatternCandidateNotFoundError,
    PatternCandidateOwnershipError,
)
from backend.app.analysis.replay_analysis import ReplayDatasetChangedError
from backend.app.analysis.statistical_analysis import create_replay_statistical_analysis
from backend.app.database.replay_session_repository import (
    ReplaySessionNotFoundError,
    ReplayTransitionConflictError,
    get_replay_session,
)
from backend.app.strategies.pattern_candidate_backtest import (
    PatternCandidateBacktestUnsupportedError,
)
from backend.app.strategies.replay_pattern_candidates import (
    evaluate_replay_pattern_candidate_backtest,
)


# Errors that mean "this exact request can never succeed" -- retrying would
# just waste an attempt slot and delay a failure the caller already knows
# about. Anything not in this list falls through to the broad except below,
# which also treats it as non-retryable by default (only genuinely transient
# infrastructure errors, e.g. sqlite3.OperationalError, are retried).
_NON_RETRYABLE_ERRORS = (
    PatternCandidateNotFoundError,
    PatternCandidateOwnershipError,
    PatternCandidateBacktestUnsupportedError,
    PatternCandidateConflictError,
    PatternCandidateBacktestNotFoundError,
    ReplaySessionNotFoundError,
    ReplayTransitionConflictError,
    ReplayDatasetChangedError,
    ValueError,
)


def _run_pattern_candidate_backtest_job(job: AnalysisJob) -> dict[str, object]:
    payload = job.payload
    backtest = evaluate_replay_pattern_candidate_backtest(
        candidate_id=str(payload["candidate_id"]), actor=job.created_by, actor_role="operator",
        horizon_bars=int(payload.get("horizon_bars", 3)),
        spread_bps=float(payload.get("spread_bps", 2.0)),
        commission_bps=float(payload.get("commission_bps", 1.0)),
        slippage_bps=float(payload.get("slippage_bps", 1.0)),
        latency_bps=float(payload.get("latency_bps", 0.5)),
        adverse_multiplier=float(payload.get("adverse_multiplier", 1.5)),
        stress_multiplier=float(payload.get("stress_multiplier", 2.5)),
    )
    return asdict(backtest)


def _run_statistical_analysis_job(job: AnalysisJob) -> dict[str, object]:
    payload = job.payload
    session = get_replay_session(str(payload["session_id"]))
    analysis = create_replay_statistical_analysis(
        session=session,
        timeframe=str(payload.get("timeframe", "M1")),
        minimum_sample_size=int(payload.get("minimum_sample_size", 30)),
    )
    return asdict(analysis)


_DISPATCH = {
    "pattern_candidate_backtest": _run_pattern_candidate_backtest_job,
    "statistical_analysis": _run_statistical_analysis_job,
}


def run_worker_once(*, worker_id: str, job_type: str = "pattern_candidate_backtest") -> bool:
    """Claim and fully process at most one job. Returns True if a job was claimed
    (regardless of whether it ultimately succeeded, retried, or failed).

    This function is the single-worker execution unit the contract describes.
    It is safe to call from a real standalone worker process loop, or (as this
    codebase currently does) from a FastAPI BackgroundTask right after enqueue
    -- the claim/lease/fencing mechanics make both callers equally safe against
    double-processing.
    """
    handler = _DISPATCH.get(job_type)
    if handler is None:
        raise ValueError(f"no worker registered for job_type: {job_type}")

    job = claim_next_job(worker_id=worker_id, job_type=job_type)
    if job is None:
        return False

    job = send_heartbeat(job_id=job.job_id, worker_id=worker_id, fencing_token=job.fencing_token)

    try:
        result = handler(job)
    except _NON_RETRYABLE_ERRORS as error:
        fail_job(
            job_id=job.job_id, worker_id=worker_id, fencing_token=job.fencing_token,
            error_code=f"{type(error).__name__}: {error}", retryable=False,
        )
        return True
    except sqlite3.OperationalError as error:
        fail_job(
            job_id=job.job_id, worker_id=worker_id, fencing_token=job.fencing_token,
            error_code=f"sqlite_operational_error: {error}", retryable=True,
        )
        return True
    except Exception as error:  # noqa: BLE001 -- worker boundary: one bad job must not crash the queue
        fail_job(
            job_id=job.job_id, worker_id=worker_id, fencing_token=job.fencing_token,
            error_code=f"unexpected_error: {type(error).__name__}: {error}", retryable=False,
        )
        return True

    complete_job(job_id=job.job_id, worker_id=worker_id, fencing_token=job.fencing_token, result=result)
    return True


def drain_queue(*, worker_id: str, job_type: str = "pattern_candidate_backtest", max_jobs: int = 50) -> int:
    """Process jobs one at a time until the queue is empty or max_jobs is reached.

    Bounded by max_jobs so a single caller (e.g. a BackgroundTask) cannot loop
    forever if jobs keep arriving faster than they can be processed.
    """
    processed = 0
    while processed < max_jobs:
        if not run_worker_once(worker_id=worker_id, job_type=job_type):
            break
        processed += 1
    return processed
