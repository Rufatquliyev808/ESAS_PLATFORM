"use client";

import { useCallback, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";
const POLL_INTERVAL_MS = 2_000;

export type JobState =
  | "queued" | "claimed" | "running" | "pausing" | "paused" | "retry_wait"
  | "completed" | "cancelled" | "interrupted" | "failed";

export type AsyncJob<TResult = unknown> = {
  job_id: string;
  job_type: string;
  state: JobState;
  state_version: number;
  priority: number;
  attempt_count: number;
  max_attempts: number;
  error_code: string | null;
  result: TResult | null;
  cancel_requested: boolean;
  created_at: string;
  completed_at: string | null;
};

type Envelope<T> = { data: T };

const TERMINAL_STATES = new Set<JobState>(["completed", "cancelled", "failed"]);

const STATE_LABELS: Record<JobState, string> = {
  queued: "Növbədədir",
  claimed: "Götürülüb",
  running: "İcra olunur",
  pausing: "Dayandırılır",
  paused: "Dayandırılıb",
  retry_wait: "Təkrar cəhd planlaşdırılıb",
  completed: "Tamamlandı",
  cancelled: "Ləğv edildi",
  interrupted: "Kəsildi",
  failed: "Uğursuz oldu",
};

const STATE_TONE: Record<JobState, string> = {
  queued: "info", claimed: "info", running: "info",
  pausing: "warning", paused: "warning", retry_wait: "warning",
  completed: "good", cancelled: "warning", interrupted: "warning", failed: "danger",
};

export function JobStatusBadge({ state }: { state: JobState }) {
  return (
    <span className={`status-pill tone-${STATE_TONE[state] ?? "info"}`}>
      <span className="status-dot" aria-hidden="true" />
      {STATE_LABELS[state] ?? state}
    </span>
  );
}

export function useAsyncJob<TResult = unknown>({
  createUrl, detailUrlFor, cancelUrlFor, token, onUnauthorized, onCompleted,
}: {
  createUrl: string;
  detailUrlFor: (jobId: string) => string;
  cancelUrlFor: (jobId: string) => string;
  token: string;
  onUnauthorized: () => void;
  /** Called once, right when a job reaches `completed` with a result -- from
   * inside the poll tick / create response handler, never from a React
   * effect, so callers can safely call setState here without triggering the
   * "no setState in an effect body" lint rule. */
  onCompleted?: (result: TResult) => void;
}) {
  const [job, setJob] = useState<AsyncJob<TResult> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pollTimer = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current !== null) {
      window.clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const applyJob = useCallback((next: AsyncJob<TResult>) => {
    setJob(next);
    if (next.state === "completed" && next.result) onCompleted?.(next.result);
  }, [onCompleted]);

  const pollDetail = useCallback((jobId: string) => {
    stopPolling();
    const tick = async () => {
      try {
        const response = await fetch(`${API_BASE}${detailUrlFor(jobId)}`, {
          cache: "no-store",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (response.status === 401) { onUnauthorized(); return; }
        if (!response.ok) throw new Error(`Job statusu alına bilmədi (HTTP ${response.status}).`);
        const payload = await response.json() as Envelope<AsyncJob<TResult>>;
        applyJob(payload.data);
        if (!TERMINAL_STATES.has(payload.data.state)) {
          pollTimer.current = window.setTimeout(() => void tick(), POLL_INTERVAL_MS);
        }
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : "Job statusu alına bilmədi.");
      }
    };
    void tick();
  }, [applyJob, detailUrlFor, onUnauthorized, stopPolling, token]);

  const create = useCallback(async (body: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}${createUrl}`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ idempotency_key: crypto.randomUUID(), ...body }),
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 429) throw new Error("Növbə doludur (maksimum 3 aktiv job). Bir azdan yenidən cəhd edin.");
      if (response.status === 403) throw new Error("Bu resurs sizə aid deyil.");
      if (!response.ok) throw new Error(`Job yaradıla bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Envelope<AsyncJob<TResult>>;
      applyJob(payload.data);
      if (!TERMINAL_STATES.has(payload.data.state)) pollDetail(payload.data.job_id);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Job yaradıla bilmədi.");
    } finally {
      setBusy(false);
    }
  }, [applyJob, createUrl, onUnauthorized, pollDetail, token]);

  const cancel = useCallback(async () => {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}${cancelUrlFor(job.job_id)}`, {
        method: "POST",
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Job artıq son vəziyyətdədir, ləğv edilə bilmir.");
      if (!response.ok) throw new Error(`Job ləğv edilə bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Envelope<AsyncJob<TResult>>;
      setJob(payload.data);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Job ləğv edilə bilmədi.");
    } finally {
      setBusy(false);
    }
  }, [cancelUrlFor, job, onUnauthorized, token]);

  const reset = useCallback(() => {
    stopPolling();
    setJob(null);
    setError(null);
  }, [stopPolling]);

  return { job, error, busy, create, cancel, reset };
}

export function isJobCancellable(job: AsyncJob): boolean {
  return !TERMINAL_STATES.has(job.state) && !job.cancel_requested;
}
