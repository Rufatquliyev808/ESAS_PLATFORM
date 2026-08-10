"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { JobStatusBadge, isJobCancellable, useAsyncJob } from "./async-job-panel";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";
const RENDERING_JOB_STORAGE_PREFIX = "esas.visual-experiment-rendering-job.";
const TRAINING_JOB_STORAGE_PREFIX = "esas.visual-experiment-training-job.";

// Phase 5's only supported architecture so far (pixel_centroid_baseline_v1)
// -- not user-configurable yet, matching how render_spec geometry/colour
// also stay at fixed defaults in this panel. A future increment can expose
// these once more than one architecture exists.
const DEFAULT_TRAINING_JOB_BODY = {
  architecture_id: "pixel_centroid_baseline_v1",
  preprocessing_policy: "normalize_0_1",
  class_weight_policy: "balanced",
  seed: 42,
  optimizer: "adam",
  loss: "cross_entropy",
  batch_size: 32,
  max_epochs: 10,
  compute_requirement: "cpu",
};

type Timeframe = "S1" | "S10" | "M1" | "M5" | "M15" | "M30" | "H1" | "H4" | "D1";
type VisualExperiment = {
  experiment_id: string;
  created_by: string;
  replay_session_id: string;
  symbol: string;
  timeframe: string;
  source_bar_fingerprint: string;
  render_spec_id: string;
  render_spec: { width: number; height: number };
  label_spec_id: string;
  label_spec: { horizon_bars: number; up_threshold_bps: number; down_threshold_bps: number };
  observation_window_bars: number;
  train_end_at: string;
  validation_end_at: string;
  lifecycle_state: string;
  state_version: number;
  created_at: string;
  updated_at: string;
};
type Envelope<T> = { data: T };
type Page<T> = Envelope<T[]>;

const LIFECYCLE_LABELS: Record<string, string> = {
  registered: "Qeydə alınıb (konfiqurasiya dondurulub)",
  rendering: "Render edilir",
  training: "Təlim edilir",
  evaluated: "Qiymətləndirilib",
  accepted_for_shadow: "SHADOW namizədi",
  rejected: "Rədd edilib",
  archived: "Arxivləşdirilib",
  blocked_by_data_quality: "Bloklanıb — məlumat keyfiyyəti",
  invalid_leakage: "Etibarsız — sızma aşkarlandı",
  non_reproducible: "Təkrarlana bilmir",
  out_of_distribution: "Paylanmadan kənar",
  insufficient_evidence: "Sübut yetərsizdir",
  failed: "Uğursuz oldu",
  cancelled: "Ləğv edilib",
};

const ARCHIVABLE_STATES = new Set(["registered"]);

function formatTime(value: string | null) {
  return value ? new Intl.DateTimeFormat("az-AZ", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "—";
}

function localInput(date: Date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

type RenderingJobResult = {
  experiment: { lifecycle_state: string };
  manifest: { dataset_fingerprint: string; manifest_fingerprint: string; total_samples: number };
  sample_count: number;
};

function RenderingJobCell({ experiment, token, onUnauthorized, onCompleted }: {
  experiment: VisualExperiment;
  token: string;
  onUnauthorized: () => void;
  onCompleted: () => void;
}) {
  const storageKey = `${RENDERING_JOB_STORAGE_PREFIX}${experiment.experiment_id}`;
  const restoreAttempted = useRef(false);

  const asyncJob = useAsyncJob<RenderingJobResult>({
    createUrl: `/api/v2/visual-experiments/${experiment.experiment_id}/rendering-jobs`,
    detailUrlFor: (jobId) => `/api/v2/visual-experiments/${experiment.experiment_id}/rendering-jobs/${jobId}`,
    cancelUrlFor: (jobId) => `/api/v2/visual-experiments/${experiment.experiment_id}/rendering-jobs/${jobId}/cancel`,
    token, onUnauthorized, onCompleted,
  });

  useEffect(() => {
    if (restoreAttempted.current) return;
    restoreAttempted.current = true;
    const rememberedJobId = window.localStorage.getItem(storageKey);
    if (rememberedJobId) asyncJob.restore(rememberedJobId);
    // Runs once per mounted row (one row per experiment_id); asyncJob.restore
    // is stable across renders (useCallback), storageKey is derived from a
    // prop that does not change for a given row.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (asyncJob.job?.state === "cancelled") {
      window.localStorage.removeItem(storageKey);
      return;
    }
    if (asyncJob.job?.job_id) window.localStorage.setItem(storageKey, asyncJob.job.job_id);
  }, [asyncJob.job?.job_id, asyncJob.job?.state, storageKey]);

  if (experiment.lifecycle_state !== "registered" && !asyncJob.job) {
    return <span className="pattern-candidate-time">—</span>;
  }

  return (
    <div className="pattern-candidate-backtest-cell">
      {!asyncJob.job && (
        <button type="button" className="secondary-button" disabled={asyncJob.busy} onClick={() => void asyncJob.create({})}>
          {asyncJob.busy ? "Növbəyə əlavə olunur…" : "Dataset yarat"}
        </button>
      )}
      {asyncJob.job && (
        <div className="async-job-meta">
          <JobStatusBadge state={asyncJob.job.state} />
          {isJobCancellable(asyncJob.job) && (
            <button type="button" className="secondary-button" disabled={asyncJob.busy} onClick={() => void asyncJob.cancel()}>Ləğv et</button>
          )}
          {asyncJob.job.error_code && <span className="card-detail danger-text">{asyncJob.job.error_code}</span>}
          {asyncJob.job.state === "completed" && asyncJob.job.result && (
            <dl className="pattern-candidate-evidence">
              <div><dt>Nümunə sayı</dt><dd>{asyncJob.job.result.sample_count}</dd></div>
              <div><dt>Dataset fingerprint</dt><dd title={asyncJob.job.result.manifest.dataset_fingerprint}>{asyncJob.job.result.manifest.dataset_fingerprint.slice(0, 20)}…</dd></div>
            </dl>
          )}
        </div>
      )}
      {asyncJob.error && <span className="card-detail danger-text">{asyncJob.error}</span>}
    </div>
  );
}

const EVALUATION_OUTCOME_LABELS: Record<string, string> = {
  evaluated: "Qiymətləndirildi",
  out_of_distribution: "Paylanmadan kənar",
  insufficient_evidence: "Sübut yetərsizdir",
};

type TrainingJobResult = {
  experiment: { lifecycle_state: string };
  evaluation: {
    outcome: string;
    holdout_sample_count: number;
    holdout_metrics: { accuracy: number; correct_count: number; sample_count: number };
    majority_baseline_accuracy: number;
    improvement_over_baseline: number;
    is_out_of_distribution: boolean;
  };
};

function TrainingJobCell({ experiment, token, onUnauthorized, onCompleted }: {
  experiment: VisualExperiment;
  token: string;
  onUnauthorized: () => void;
  onCompleted: () => void;
}) {
  const storageKey = `${TRAINING_JOB_STORAGE_PREFIX}${experiment.experiment_id}`;
  const restoreAttempted = useRef(false);

  const asyncJob = useAsyncJob<TrainingJobResult>({
    createUrl: `/api/v2/visual-experiments/${experiment.experiment_id}/training-jobs`,
    detailUrlFor: (jobId) => `/api/v2/visual-experiments/${experiment.experiment_id}/training-jobs/${jobId}`,
    cancelUrlFor: (jobId) => `/api/v2/visual-experiments/${experiment.experiment_id}/training-jobs/${jobId}/cancel`,
    token, onUnauthorized, onCompleted,
  });

  useEffect(() => {
    if (restoreAttempted.current) return;
    restoreAttempted.current = true;
    const rememberedJobId = window.localStorage.getItem(storageKey);
    if (rememberedJobId) asyncJob.restore(rememberedJobId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (asyncJob.job?.state === "cancelled") {
      window.localStorage.removeItem(storageKey);
      return;
    }
    if (asyncJob.job?.job_id) window.localStorage.setItem(storageKey, asyncJob.job.job_id);
  }, [asyncJob.job?.job_id, asyncJob.job?.state, storageKey]);

  if (experiment.lifecycle_state !== "training" && !asyncJob.job) {
    return <span className="pattern-candidate-time">—</span>;
  }

  return (
    <div className="pattern-candidate-backtest-cell">
      {!asyncJob.job && (
        <button
          type="button" className="secondary-button" disabled={asyncJob.busy}
          onClick={() => void asyncJob.create(DEFAULT_TRAINING_JOB_BODY)}
        >
          {asyncJob.busy ? "Növbəyə əlavə olunur…" : "Modeli öyrət və qiymətləndir"}
        </button>
      )}
      {asyncJob.job && (
        <div className="async-job-meta">
          <JobStatusBadge state={asyncJob.job.state} />
          {isJobCancellable(asyncJob.job) && (
            <button type="button" className="secondary-button" disabled={asyncJob.busy} onClick={() => void asyncJob.cancel()}>Ləğv et</button>
          )}
          {asyncJob.job.error_code && <span className="card-detail danger-text">{asyncJob.job.error_code}</span>}
          {asyncJob.job.state === "completed" && asyncJob.job.result && (
            <dl className="pattern-candidate-evidence">
              <div><dt>Nəticə</dt><dd>{EVALUATION_OUTCOME_LABELS[asyncJob.job.result.evaluation.outcome] ?? asyncJob.job.result.evaluation.outcome}</dd></div>
              <div><dt>Holdout accuracy</dt><dd>{(asyncJob.job.result.evaluation.holdout_metrics.accuracy * 100).toFixed(1)}%</dd></div>
              <div><dt>Baseline (majority)</dt><dd>{(asyncJob.job.result.evaluation.majority_baseline_accuracy * 100).toFixed(1)}%</dd></div>
              <div><dt>Holdout nümunə</dt><dd>{asyncJob.job.result.evaluation.holdout_sample_count}</dd></div>
            </dl>
          )}
        </div>
      )}
      {asyncJob.error && <span className="card-detail danger-text">{asyncJob.error}</span>}
    </div>
  );
}

export function VisualExperimentsPanel({ sessionId, symbol, token, onUnauthorized }: { sessionId: string; symbol: string; token: string; onUnauthorized: () => void }) {
  const now = new Date();
  const [timeframe, setTimeframe] = useState<Timeframe>("M1");
  const [sourceBarFingerprint, setSourceBarFingerprint] = useState("");
  const [horizonBars, setHorizonBars] = useState(10);
  const [upThresholdBps, setUpThresholdBps] = useState(10);
  const [downThresholdBps, setDownThresholdBps] = useState(-10);
  const [observationWindowBars, setObservationWindowBars] = useState(64);
  const [trainEndAt, setTrainEndAt] = useState(localInput(new Date(now.getTime() + 24 * 60 * 60 * 1000)));
  const [validationEndAt, setValidationEndAt] = useState(localInput(new Date(now.getTime() + 48 * 60 * 60 * 1000)));

  const [experiments, setExperiments] = useState<VisualExperiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [archivingId, setArchivingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v2/visual-experiments?page_size=100`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`Eksperimentlər alına bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Page<VisualExperiment>;
      setExperiments(payload.data);
      setError(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Eksperimentlər alına bilmədi.");
    } finally { setLoading(false); }
  }, [onUnauthorized, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const register = useCallback(async () => {
    setRegistering(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v2/visual-experiments`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          session_id: sessionId,
          symbol,
          timeframe,
          source_bar_fingerprint: sourceBarFingerprint,
          label_spec: {
            horizon_bars: horizonBars,
            up_threshold_bps: upThresholdBps,
            down_threshold_bps: downThresholdBps,
          },
          observation_window_bars: observationWindowBars,
          train_end_at: new Date(trainEndAt).toISOString(),
          validation_end_at: new Date(validationEndAt).toISOString(),
        }),
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 422) throw new Error("Konfiqurasiya etibarsızdır — sahələri yoxlayın.");
      if (response.status === 403) throw new Error("Bu replay sessiyası başqa istifadəçiyə məxsusdur.");
      if (response.status === 404) throw new Error("Replay sessiyası tapılmadı.");
      if (!response.ok) throw new Error(`Eksperiment qeydə alına bilmədi (HTTP ${response.status}).`);
      await load();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Eksperiment qeydə alına bilmədi.");
    } finally { setRegistering(false); }
  }, [downThresholdBps, horizonBars, load, observationWindowBars, onUnauthorized, sessionId, sourceBarFingerprint, symbol, timeframe, token, trainEndAt, upThresholdBps, validationEndAt]);

  const archive = useCallback(async (experiment: VisualExperiment) => {
    setArchivingId(experiment.experiment_id);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v2/visual-experiments/${experiment.experiment_id}/archive`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ expected_state_version: experiment.state_version }),
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Eksperiment vəziyyəti dəyişib; siyahını yeniləyin.");
      if (!response.ok) throw new Error(`Eksperiment arxivləşdirilə bilmədi (HTTP ${response.status}).`);
      await load();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Eksperiment arxivləşdirilə bilmədi.");
    } finally { setArchivingId(null); }
  }, [load, onUnauthorized, token]);

  return (
    <section className="visual-experiments" aria-labelledby="visual-experiments-title">
      <div className="analysis-heading">
        <div>
          <p className="eyebrow">Phase 5 — tədqiqat konfiqurasiyası · ticarət siqnalı deyil</p>
          <h3 id="visual-experiments-title">{symbol} Visual AI eksperimentləri</h3>
          <p>
            Əvvəlcə eksperimentin DONDURULMUŞ konfiqurasiyasını qeydə alın. Sonra &ldquo;Dataset yarat&rdquo;
            düyməsi real render→dataset→label icrasını job kimi başladır (şəkillər PNG kimi, checksum və tam
            lineage ilə saxlanılır) — model təlim etmir. Dataset hazır olduqda &ldquo;Modeli öyrət və
            qiymətləndir&rdquo; düyməsi (`pixel_centroid_baseline_v1`) deterministik baseline modeli
            job kimi öyrədir və holdout üzərində qiymətləndirir — accept/reject qərarı hələ ayrı addımdır.
            Render spesifikasiyası (ölçü, rəng) standart dəyərlərlə qeydə alınır; horizon və label hədləri
            aşağıda seçilir. `source_bar_fingerprint` hələ ayrıca hesablama endpoint-i olmadığı üçün əl ilə
            (statistik/texniki analiz nəticəsindən götürülərək) daxil edilir.
          </p>
        </div>
      </div>

      <form className="analysis-controls" onSubmit={(event) => { event.preventDefault(); void register(); }}>
        <label>
          Vaxt çərçivəsi
          <select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}>
            <option>S1</option><option>S10</option><option>M1</option><option>M5</option><option>M15</option>
            <option>M30</option><option>H1</option><option>H4</option><option>D1</option>
          </select>
        </label>
        <label>Pəncərə uzunluğu (bar)<input type="number" min={1} max={5000} value={observationWindowBars} onChange={(event) => setObservationWindowBars(Number(event.target.value))} /></label>
        <label>Bar fingerprint<input type="text" required placeholder="sha256:…" value={sourceBarFingerprint} onChange={(event) => setSourceBarFingerprint(event.target.value)} /></label>
        <label>Horizon (bar)<input type="number" min={1} max={5000} value={horizonBars} onChange={(event) => setHorizonBars(Number(event.target.value))} /></label>
        <label>Yuxarı hədd (bps)<input type="number" step="0.1" value={upThresholdBps} onChange={(event) => setUpThresholdBps(Number(event.target.value))} /></label>
        <label>Aşağı hədd (bps)<input type="number" step="0.1" value={downThresholdBps} onChange={(event) => setDownThresholdBps(Number(event.target.value))} /></label>
        <label>Train sərhədi<input type="datetime-local" required value={trainEndAt} onChange={(event) => setTrainEndAt(event.target.value)} /></label>
        <label>Validation sərhədi<input type="datetime-local" required value={validationEndAt} onChange={(event) => setValidationEndAt(event.target.value)} /></label>
        <button type="submit" disabled={registering}>{registering ? "Qeydə alınır…" : "Eksperimenti qeydə al"}</button>
      </form>

      {error && <div className="analysis-error" role="alert"><strong>Xəta</strong><span>{error}</span><button type="button" onClick={() => void load()}>Yenidən yoxla</button></div>}

      <section className="visual-experiments-list" aria-labelledby="visual-experiments-registered-title">
        <h4 id="visual-experiments-registered-title">Qeydə alınmış eksperimentlər</h4>
        {loading && experiments.length === 0 ? (
          <p className="empty-state">Yüklənir…</p>
        ) : experiments.length === 0 ? (
          <p className="empty-state">Hələ qeydə alınmış eksperiment yoxdur.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Vaxt çərçivəsi</th><th>Pəncərə</th><th>Horizon / hədlər (bps)</th><th>Vəziyyət</th><th>Qeydə alınma</th><th>Dataset</th><th>Model</th><th /></tr></thead>
              <tbody>
                {experiments.map((experiment) => (
                  <tr key={experiment.experiment_id}>
                    <td>{experiment.timeframe}</td>
                    <td>{experiment.observation_window_bars} bar</td>
                    <td>{experiment.label_spec.horizon_bars} bar · {experiment.label_spec.up_threshold_bps >= 0 ? "+" : ""}{experiment.label_spec.up_threshold_bps} / {experiment.label_spec.down_threshold_bps}</td>
                    <td>{LIFECYCLE_LABELS[experiment.lifecycle_state] ?? experiment.lifecycle_state}</td>
                    <td>{formatTime(experiment.created_at)}</td>
                    <td>
                      <RenderingJobCell experiment={experiment} token={token} onUnauthorized={onUnauthorized} onCompleted={() => void load()} />
                    </td>
                    <td>
                      <TrainingJobCell experiment={experiment} token={token} onUnauthorized={onUnauthorized} onCompleted={() => void load()} />
                    </td>
                    <td>
                      {ARCHIVABLE_STATES.has(experiment.lifecycle_state) && (
                        <button type="button" className="secondary-button" disabled={archivingId === experiment.experiment_id} onClick={() => void archive(experiment)}>
                          {archivingId === experiment.experiment_id ? "Arxivləşdirilir…" : "Arxivləşdir"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="analysis-disclaimer"><strong>Qeyd:</strong> &ldquo;Dataset yarat&rdquo; real render→dataset→label icrasını işə salır (PNG artefaktları + manifest saxlanılır). &ldquo;Modeli öyrət və qiymətləndir&rdquo; real (deterministik, sadə) baseline modeli öyrədir və holdout üzərində qiymətləndirir. Statistik/reyestr-əsaslı accept/reject qərarı (`evaluated → accepted_for_shadow | rejected`) hələ frontend-ə bağlanmayıb. Heç bir vəziyyət real ticarət icazəsi vermir.</p>
      </section>
    </section>
  );
}
