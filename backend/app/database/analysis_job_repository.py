from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
import random
import secrets

from backend.app.database.connection import get_connection


JOB_TYPES = frozenset({
    "pattern_candidate_backtest", "statistical_analysis", "visual_experiment_rendering",
    "visual_experiment_training", "visual_experiment_acceptance",
})
TERMINAL_STATES = frozenset({"completed", "cancelled", "failed"})
DEFAULT_LEASE_SECONDS = 30
LEASE_RECOVERY_SECONDS = 60
MAX_JITTER_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 60.0
MAX_ACTIVE_JOBS_PER_USER = 3

# Each job type owns its own (jobs table, audit table, job_id prefix). This
# exists because `analysis_jobs`' job_type CHECK constraint was already
# applied to the real production database restricted to just
# 'pattern_candidate_backtest', and this migration system's safety validator
# forbids DROP/DELETE/UPDATE statements -- so the usual SQLite "rebuild the
# table" technique for widening a CHECK constraint is not available. A new
# job type gets a new table (see migration 0011 for 'statistical_analysis'),
# not a wider CHECK on the old one. The job_id prefix lets every job-id-only
# lookup (get_job, send_heartbeat, complete_job, fail_job, request_cancel)
# route to the right table without an extra query or a job_type parameter
# the caller may not have on hand.
_JOB_TABLES: dict[str, tuple[str, str, str]] = {
    "pattern_candidate_backtest": ("analysis_jobs", "analysis_job_audit", "job"),
    "statistical_analysis": ("statistical_analysis_jobs", "statistical_analysis_job_audit", "saj"),
    "visual_experiment_rendering": (
        "visual_experiment_rendering_jobs", "visual_experiment_rendering_job_audit", "vrj",
    ),
    "visual_experiment_training": (
        "visual_experiment_training_jobs", "visual_experiment_training_job_audit", "vtj",
    ),
    "visual_experiment_acceptance": (
        "visual_experiment_acceptance_jobs", "visual_experiment_acceptance_job_audit", "vaj",
    ),
}
_PREFIX_TO_JOB_TYPE = {prefix: job_type for job_type, (_, _, prefix) in _JOB_TABLES.items()}


class AnalysisJobNotFoundError(LookupError):
    pass


class AnalysisJobOwnershipError(PermissionError):
    pass


class AnalysisJobConflictError(RuntimeError):
    pass


class AnalysisJobFencingError(RuntimeError):
    """A worker tried to write with a stale fencing token -- its lease already expired
    and another worker (or nobody) now owns the job. This is the core claim-safety
    guarantee: only the current fencing token holder may progress a job."""
    pass


class AnalysisJobQueueFullError(RuntimeError):
    """A user already has too many active jobs; enqueue is rejected, not silently
    dropped or unbounded-queued -- callers should surface this as 429/503."""
    pass


@dataclass(frozen=True)
class AnalysisJob:
    job_id: str
    job_type: str
    created_by: str
    created_at: str
    priority: int
    payload: dict[str, object]
    related_resource_id: str
    correlation_id: str
    state: str
    state_version: int
    attempt_count: int
    max_attempts: int
    next_attempt_at: str | None
    lease_owner: str | None
    lease_expires_at: str | None
    fencing_token: int
    started_at: str | None
    last_heartbeat_at: str | None
    completed_at: str | None
    error_code: str | None
    result: dict[str, object] | None
    cancel_requested: bool
    updated_at: str


def _required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _tables_for_job_type(job_type: str) -> tuple[str, str]:
    table, audit_table, _ = _JOB_TABLES[job_type]
    return table, audit_table


def _tables_for_job_id(job_id: str) -> tuple[str, str]:
    prefix = job_id.split("_", 1)[0]
    job_type = _PREFIX_TO_JOB_TYPE.get(prefix)
    if job_type is None:
        raise AnalysisJobNotFoundError("analysis job was not found")
    return _tables_for_job_type(job_type)


def _new_job_id(job_type: str) -> str:
    _, _, prefix = _JOB_TABLES[job_type]
    return f"{prefix}_{secrets.token_urlsafe(18)}"


def _row_to_job(row: object) -> AnalysisJob:
    return AnalysisJob(
        job_id=row["job_id"], job_type=row["job_type"], created_by=row["created_by"],
        created_at=row["created_at"], priority=row["priority"],
        payload=json.loads(row["payload_json"]), related_resource_id=row["related_resource_id"],
        correlation_id=row["correlation_id"], state=row["state"], state_version=row["state_version"],
        attempt_count=row["attempt_count"], max_attempts=row["max_attempts"],
        next_attempt_at=row["next_attempt_at"], lease_owner=row["lease_owner"],
        lease_expires_at=row["lease_expires_at"], fencing_token=row["fencing_token"],
        started_at=row["started_at"], last_heartbeat_at=row["last_heartbeat_at"],
        completed_at=row["completed_at"], error_code=row["error_code"],
        result=json.loads(row["result_json"]) if row["result_json"] is not None else None,
        cancel_requested=bool(row["cancel_requested"]), updated_at=row["updated_at"],
    )


def _insert_audit(
    connection, audit_table: str, *, job_id: str, actor: str, actor_kind: str, action: str,
    previous_state: str | None, next_state: str, fencing_token: int | None,
    details: dict[str, object] | None, now: str,
) -> None:
    connection.execute(
        f"""
        INSERT INTO {audit_table}
        (job_id, actor, actor_kind, action, previous_state, next_state, fencing_token, details_json, occurred_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            job_id, actor, actor_kind, action, previous_state, next_state, fencing_token,
            json.dumps(details, sort_keys=True, separators=(",", ":")) if details is not None else None,
            now,
        ),
    )


def enqueue_job(
    *,
    job_type: str,
    created_by: str,
    payload: dict[str, object],
    related_resource_id: str,
    idempotency_key: str,
    priority: int = 3,
    max_attempts: int = 5,
) -> AnalysisJob:
    """Queue a job, or return the existing job for a repeated idempotency key.

    Enforces a hard per-user cap on active (non-terminal) jobs: a user cannot
    monopolize the queue, and a full queue is rejected outright rather than
    silently dropped, per the worker/scheduler contract's fairness rules.
    """
    normalized_type = _required_text(job_type, "job_type")
    if normalized_type not in JOB_TYPES:
        raise ValueError(f"unsupported job_type: {normalized_type}")
    normalized_creator = _required_text(created_by, "created_by")
    normalized_resource = _required_text(related_resource_id, "related_resource_id")
    normalized_key = _required_text(idempotency_key, "idempotency_key")
    if not 1 <= priority <= 5:
        raise ValueError("priority must be between 1 and 5")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    table, audit_table = _tables_for_job_type(normalized_type)
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = _hash(payload_json)
    # Deliberately NOT scoped by creator: the key namespace is shared per job_type so a
    # key reused by a different user is detected below and rejected, rather than silently
    # creating an independent per-user namespace that would defeat that protection.
    key_hash = _hash(f"{normalized_type}:{normalized_key}")
    now = _now()
    job_id = _new_job_id(normalized_type)
    correlation_id = f"corr_{secrets.token_urlsafe(12)}"

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        existing = connection.execute(
            f"SELECT * FROM {table} WHERE job_type = ? AND idempotency_key_hash = ?;",
            (normalized_type, key_hash),
        ).fetchone()
        if existing is not None:
            if existing["created_by"] != normalized_creator:
                raise AnalysisJobOwnershipError("job idempotency key belongs to another user")
            return _row_to_job(existing)

        active_count = connection.execute(
            f"""
            SELECT COUNT(*) FROM {table}
            WHERE created_by = ? AND state NOT IN ('completed', 'cancelled', 'failed');
            """,
            (normalized_creator,),
        ).fetchone()[0]
        if active_count >= MAX_ACTIVE_JOBS_PER_USER:
            raise AnalysisJobQueueFullError(
                f"user already has {active_count} active jobs (max {MAX_ACTIVE_JOBS_PER_USER})"
            )

        connection.execute(
            f"""
            INSERT INTO {table}
            (
                job_id, job_type, created_by, created_at, priority, payload_json, payload_hash,
                idempotency_key_hash, related_resource_id, correlation_id, state, state_version,
                attempt_count, max_attempts, next_attempt_at, lease_owner, lease_expires_at,
                fencing_token, started_at, last_heartbeat_at, completed_at, error_code,
                result_json, cancel_requested, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, 0, ?, NULL, NULL, NULL, 0,
                    NULL, NULL, NULL, NULL, NULL, 0, ?);
            """,
            (
                job_id, normalized_type, normalized_creator, now, priority, payload_json,
                payload_hash, key_hash, normalized_resource, correlation_id, max_attempts, now,
            ),
        )
        _insert_audit(
            connection, audit_table, job_id=job_id, actor=normalized_creator, actor_kind="user",
            action="enqueue", previous_state=None, next_state="queued", fencing_token=None,
            details={"priority": priority, "related_resource_id": normalized_resource}, now=now,
        )
        row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (job_id,)).fetchone()
    return _row_to_job(row)


def _reclaim_expired_leases(connection, *, job_type: str, now: str, now_dt: datetime) -> None:
    """Treat claimed/running jobs whose lease has expired as interrupted -- the
    worker that held them is presumed dead. Retryable ones go back to queued
    (with a fresh attempt slot check happening at claim time); exhausted ones
    fail. This is what makes restart/crash recovery safe without a live
    heartbeat process watching workers."""
    table, audit_table = _tables_for_job_type(job_type)
    stale_cutoff = (now_dt - timedelta(seconds=LEASE_RECOVERY_SECONDS)).isoformat(timespec="microseconds")
    stale_rows = connection.execute(
        f"""
        SELECT * FROM {table}
        WHERE job_type = ? AND state IN ('claimed', 'running')
          AND (lease_expires_at IS NULL OR lease_expires_at < ?);
        """,
        (job_type, stale_cutoff),
    ).fetchall()
    for row in stale_rows:
        can_retry = row["attempt_count"] < row["max_attempts"]
        next_state = "queued" if can_retry else "failed"
        updated = connection.execute(
            f"""
            UPDATE {table}
            SET state = ?, state_version = state_version + 1, lease_owner = NULL,
                lease_expires_at = NULL, error_code = CASE WHEN ? = 'failed' THEN 'lease_expired_max_attempts' ELSE error_code END,
                completed_at = CASE WHEN ? = 'failed' THEN ? ELSE completed_at END,
                updated_at = ?
            WHERE job_id = ? AND state_version = ?;
            """,
            (next_state, next_state, next_state, now, now, row["job_id"], row["state_version"]),
        )
        if updated.rowcount == 1:
            _insert_audit(
                connection, audit_table, job_id=row["job_id"], actor="scheduler", actor_kind="worker",
                action="interrupted", previous_state=row["state"], next_state=next_state,
                fencing_token=row["fencing_token"],
                details={"reason": "lease_expired"}, now=now,
            )


def claim_next_job(*, worker_id: str, job_type: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> AnalysisJob | None:
    """Atomically claim the oldest eligible job, reclaiming any job whose lease
    has expired (crashed worker) first. Bumps a monotonic fencing token so a
    worker that later wakes up from the dead cannot write with a stale claim."""
    normalized_type = _required_text(job_type, "job_type")
    normalized_worker = _required_text(worker_id, "worker_id")
    if normalized_type not in JOB_TYPES:
        raise ValueError(f"unsupported job_type: {normalized_type}")

    table, audit_table = _tables_for_job_type(normalized_type)
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        _reclaim_expired_leases(connection, job_type=normalized_type, now=now, now_dt=now_dt)

        candidate = connection.execute(
            f"""
            SELECT * FROM {table}
            WHERE job_type = ?
              AND (
                  state = 'queued'
                  OR (state = 'retry_wait' AND (next_attempt_at IS NULL OR next_attempt_at <= ?))
              )
            ORDER BY priority ASC, created_at ASC, job_id ASC
            LIMIT 1;
            """,
            (normalized_type, now),
        ).fetchone()
        if candidate is None:
            return None

        lease_expires = (now_dt + timedelta(seconds=lease_seconds)).isoformat(timespec="microseconds")
        next_fencing_token = candidate["fencing_token"] + 1
        updated = connection.execute(
            f"""
            UPDATE {table}
            SET state = 'claimed', state_version = state_version + 1, lease_owner = ?,
                lease_expires_at = ?, fencing_token = ?, attempt_count = attempt_count + 1,
                updated_at = ?
            WHERE job_id = ? AND state_version = ?;
            """,
            (normalized_worker, lease_expires, next_fencing_token, now, candidate["job_id"], candidate["state_version"]),
        )
        if updated.rowcount != 1:
            # Another worker claimed it between our SELECT and UPDATE; caller can retry.
            return None
        _insert_audit(
            connection, audit_table, job_id=candidate["job_id"], actor=normalized_worker, actor_kind="worker",
            action="claim", previous_state=candidate["state"], next_state="claimed",
            fencing_token=next_fencing_token, details={"lease_seconds": lease_seconds}, now=now,
        )
        row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (candidate["job_id"],)).fetchone()
    return _row_to_job(row)


def _load_for_write(connection, job_id: str, table: str) -> object:
    row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (job_id,)).fetchone()
    if row is None:
        raise AnalysisJobNotFoundError("analysis job was not found")
    return row


def _check_fencing(row: object, worker_id: str, fencing_token: int) -> None:
    if row["lease_owner"] != worker_id or row["fencing_token"] != fencing_token:
        raise AnalysisJobFencingError(
            "stale fencing token or lease no longer owned by this worker"
        )


def send_heartbeat(*, job_id: str, worker_id: str, fencing_token: int, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> AnalysisJob:
    """Extend the lease and, on the first heartbeat after claim, move claimed -> running."""
    normalized_job_id = _required_text(job_id, "job_id")
    normalized_worker = _required_text(worker_id, "worker_id")
    table, audit_table = _tables_for_job_id(normalized_job_id)
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = _load_for_write(connection, normalized_job_id, table)
        _check_fencing(row, normalized_worker, fencing_token)
        if row["state"] not in ("claimed", "running"):
            raise AnalysisJobConflictError(f"cannot heartbeat from state {row['state']}")
        next_state = "running"
        started_at = row["started_at"] or now
        lease_expires = (now_dt + timedelta(seconds=lease_seconds)).isoformat(timespec="microseconds")
        connection.execute(
            f"""
            UPDATE {table}
            SET state = ?, state_version = state_version + 1, lease_expires_at = ?,
                started_at = ?, last_heartbeat_at = ?, updated_at = ?
            WHERE job_id = ? AND state_version = ?;
            """,
            (next_state, lease_expires, started_at, now, now, normalized_job_id, row["state_version"]),
        )
        if row["state"] != next_state:
            _insert_audit(
                connection, audit_table, job_id=normalized_job_id, actor=normalized_worker, actor_kind="worker",
                action="heartbeat_start", previous_state=row["state"], next_state=next_state,
                fencing_token=fencing_token, details=None, now=now,
            )
        result_row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (normalized_job_id,)).fetchone()
    return _row_to_job(result_row)


def complete_job(*, job_id: str, worker_id: str, fencing_token: int, result: dict[str, object]) -> AnalysisJob:
    """Mark a running job completed, unless a cancel was requested -- cancellation
    is honored at this single batch boundary (this job type has no internal
    checkpoints to interrupt mid-computation)."""
    normalized_job_id = _required_text(job_id, "job_id")
    normalized_worker = _required_text(worker_id, "worker_id")
    table, audit_table = _tables_for_job_id(normalized_job_id)
    now = _now()

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = _load_for_write(connection, normalized_job_id, table)
        _check_fencing(row, normalized_worker, fencing_token)
        if row["state"] != "running":
            raise AnalysisJobConflictError(f"cannot complete from state {row['state']}")
        next_state = "cancelled" if row["cancel_requested"] else "completed"
        result_json = json.dumps(result, sort_keys=True, separators=(",", ":")) if next_state == "completed" else None
        connection.execute(
            f"""
            UPDATE {table}
            SET state = ?, state_version = state_version + 1, result_json = ?,
                completed_at = ?, updated_at = ?
            WHERE job_id = ? AND state_version = ?;
            """,
            (next_state, result_json, now, now, normalized_job_id, row["state_version"]),
        )
        _insert_audit(
            connection, audit_table, job_id=normalized_job_id, actor=normalized_worker, actor_kind="worker",
            action="complete" if next_state == "completed" else "cancel_honored",
            previous_state="running", next_state=next_state, fencing_token=fencing_token,
            details=None, now=now,
        )
        result_row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (normalized_job_id,)).fetchone()
    return _row_to_job(result_row)


def _backoff_seconds(attempt_count: int) -> float:
    base = min(MAX_BACKOFF_SECONDS, float(2 ** max(0, attempt_count - 1)))
    return base + random.uniform(0, MAX_JITTER_SECONDS)


def fail_job(*, job_id: str, worker_id: str, fencing_token: int, error_code: str, retryable: bool) -> AnalysisJob:
    """Fail a running job. Only transient, retryable failures get another
    attempt (exponential backoff with jitter, capped, up to max_attempts);
    validation/permission/fingerprint-type errors must be called with
    retryable=False so a broken job doesn't retry forever."""
    normalized_job_id = _required_text(job_id, "job_id")
    normalized_worker = _required_text(worker_id, "worker_id")
    normalized_error = _required_text(error_code, "error_code")
    table, audit_table = _tables_for_job_id(normalized_job_id)
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat(timespec="microseconds")

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = _load_for_write(connection, normalized_job_id, table)
        _check_fencing(row, normalized_worker, fencing_token)
        if row["state"] != "running":
            raise AnalysisJobConflictError(f"cannot fail from state {row['state']}")
        can_retry = retryable and row["attempt_count"] < row["max_attempts"]
        if can_retry:
            next_state = "retry_wait"
            delay = _backoff_seconds(row["attempt_count"])
            next_attempt_at = (now_dt + timedelta(seconds=delay)).isoformat(timespec="microseconds")
            completed_at = None
        else:
            next_state = "failed"
            next_attempt_at = None
            completed_at = now
        connection.execute(
            f"""
            UPDATE {table}
            SET state = ?, state_version = state_version + 1, error_code = ?,
                next_attempt_at = ?, completed_at = ?, lease_owner = NULL,
                lease_expires_at = NULL, updated_at = ?
            WHERE job_id = ? AND state_version = ?;
            """,
            (next_state, normalized_error, next_attempt_at, completed_at, now, normalized_job_id, row["state_version"]),
        )
        _insert_audit(
            connection, audit_table, job_id=normalized_job_id, actor=normalized_worker, actor_kind="worker",
            action="fail", previous_state="running", next_state=next_state, fencing_token=fencing_token,
            details={"error_code": normalized_error, "retryable": retryable}, now=now,
        )
        result_row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (normalized_job_id,)).fetchone()
    return _row_to_job(result_row)


def request_cancel(*, job_id: str, actor: str) -> AnalysisJob:
    """Cancel a job. queued/retry_wait/paused jobs are cancelled immediately.
    A running job cannot be interrupted mid-computation (no internal
    checkpoints), so cancellation is only recorded as a request the worker
    honors at its one batch boundary, right before it would otherwise mark
    the job completed."""
    normalized_job_id = _required_text(job_id, "job_id")
    normalized_actor = _required_text(actor, "actor")
    table, audit_table = _tables_for_job_id(normalized_job_id)
    now = _now()

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE;")
        row = _load_for_write(connection, normalized_job_id, table)
        if row["created_by"] != normalized_actor:
            raise AnalysisJobOwnershipError("analysis job belongs to another user")
        if row["state"] in TERMINAL_STATES:
            raise AnalysisJobConflictError(f"cannot cancel from terminal state {row['state']}")

        if row["state"] == "running":
            connection.execute(
                f"UPDATE {table} SET cancel_requested = 1, updated_at = ? WHERE job_id = ? AND state_version = ?;",
                (now, normalized_job_id, row["state_version"]),
            )
            _insert_audit(
                connection, audit_table, job_id=normalized_job_id, actor=normalized_actor, actor_kind="user",
                action="cancel_requested", previous_state="running", next_state="running",
                fencing_token=row["fencing_token"], details=None, now=now,
            )
        else:
            connection.execute(
                f"""
                UPDATE {table}
                SET state = 'cancelled', state_version = state_version + 1, completed_at = ?, updated_at = ?
                WHERE job_id = ? AND state_version = ?;
                """,
                (now, now, normalized_job_id, row["state_version"]),
            )
            _insert_audit(
                connection, audit_table, job_id=normalized_job_id, actor=normalized_actor, actor_kind="user",
                action="cancel", previous_state=row["state"], next_state="cancelled",
                fencing_token=None, details=None, now=now,
            )
        result_row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (normalized_job_id,)).fetchone()
    return _row_to_job(result_row)


def get_job(job_id: str) -> AnalysisJob:
    normalized = _required_text(job_id, "job_id")
    table, _ = _tables_for_job_id(normalized)
    with get_connection() as connection:
        row = connection.execute(f"SELECT * FROM {table} WHERE job_id = ?;", (normalized,)).fetchone()
    if row is None:
        raise AnalysisJobNotFoundError("analysis job was not found")
    return _row_to_job(row)


def queue_metrics(job_type: str) -> dict[str, object]:
    """Minimal observability: queue depth by state and the oldest queued job's age."""
    normalized_type = _required_text(job_type, "job_type")
    if normalized_type not in JOB_TYPES:
        raise ValueError(f"unsupported job_type: {normalized_type}")
    table, _ = _tables_for_job_type(normalized_type)
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT state, COUNT(*) AS count FROM {table} WHERE job_type = ? GROUP BY state;",
            (normalized_type,),
        ).fetchall()
        oldest = connection.execute(
            f"SELECT created_at FROM {table} WHERE job_type = ? AND state = 'queued' ORDER BY created_at ASC LIMIT 1;",
            (normalized_type,),
        ).fetchone()
    depth_by_state = {row["state"]: row["count"] for row in rows}
    oldest_queued_at = oldest["created_at"] if oldest is not None else None
    oldest_queued_age_seconds = None
    if oldest_queued_at is not None:
        oldest_queued_age_seconds = (
            datetime.now(UTC) - datetime.fromisoformat(oldest_queued_at)
        ).total_seconds()
    return {
        "job_type": normalized_type,
        "depth_by_state": depth_by_state,
        "oldest_queued_age_seconds": oldest_queued_age_seconds,
    }
