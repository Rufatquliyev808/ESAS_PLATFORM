"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";

const SHADOW_EVENT_TYPES = [
  "SHADOW_RUN_STARTED", "SHADOW_DECISION_RECORDED", "SHADOW_RISK_BLOCKED",
  "SHADOW_THEORETICAL_POSITION_OPENED", "SHADOW_THEORETICAL_POSITION_CLOSED",
  "SHADOW_DATA_GAP_RECORDED", "SHADOW_RUN_COMPLETED",
  "SHADOW_PROMOTION_RECOMMENDED", "SHADOW_PROMOTION_REJECTED",
];

type Participant = { participant_id: string; role: "champion" | "challenger"; module_id: string; module_version: string };
type ShadowRun = {
  shadow_run_id: string; created_by: string; created_at: string; planned_end_at: string;
  primary_metric: string; primary_metric_threshold: number; approved_by: string;
  execution_allowed: boolean; state: "registered" | "started" | "completed" | "halted";
  state_version: number; halt_reason: string | null; participants: Participant[];
};
type ShadowEvent = { event_id: string; event_type: string; correlation_id: string; actor: string; payload: Record<string, unknown>; occurred_at: string };
type ShadowPosition = {
  position_id: string; participant_id: string; symbol: string; direction: "long" | "short";
  theoretical_size: number; reserved_risk_amount: number; opened_at: string; state: "open" | "closed";
  state_version: number; closed_at: string | null; theoretical_pnl_percent: number | null;
};
type PortfolioSummary = {
  open_position_count: number; total_reserved_risk_amount: number;
  closed_position_count: number; net_realized_theoretical_pnl_percent: number | null;
};

const STATE_LABELS: Record<string, string> = {
  registered: "Qeydə alınıb", started: "Başladılıb", completed: "Tamamlanıb", halted: "Dayandırılıb",
};

function azTime(value: string) {
  return new Intl.DateTimeFormat("az-AZ", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function splitList(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function newCorrelationId(): string {
  return `corr_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

export function ShadowRunsPanel({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [runs, setRuns] = useState<ShadowRun[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [events, setEvents] = useState<ShadowEvent[]>([]);
  const [positions, setPositions] = useState<ShadowPosition[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  const loadRuns = useCallback(async () => {
    setListError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v2/shadow-runs`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setRuns((await response.json()).data as ShadowRun[]);
    } catch { setListError("SHADOW run siyahısı alına bilmədi."); }
  }, [onUnauthorized, token]);

  const loadDetail = useCallback(async (shadowRunId: string) => {
    setDetailError(null);
    try {
      const [eventsResponse, positionsResponse, summaryResponse] = await Promise.all([
        fetch(`${API_BASE}/api/v2/shadow-runs/${shadowRunId}/events`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/api/v2/shadow-runs/${shadowRunId}/positions`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/api/v2/shadow-runs/${shadowRunId}/portfolio-summary`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (eventsResponse.status === 401) { onUnauthorized(); return; }
      if (!eventsResponse.ok || !positionsResponse.ok || !summaryResponse.ok) throw new Error("HTTP error");
      setEvents(((await eventsResponse.json()).data as ShadowEvent[]).slice().reverse());
      setPositions((await positionsResponse.json()).data as ShadowPosition[]);
      setSummary((await summaryResponse.json()).data as PortfolioSummary);
    } catch { setDetailError("Run təfərrüatı alına bilmədi."); }
  }, [onUnauthorized, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadRuns(), 0);
    return () => window.clearTimeout(timer);
  }, [loadRuns]);

  useEffect(() => {
    if (!selectedId) return;
    const timer = window.setTimeout(() => void loadDetail(selectedId), 0);
    return () => window.clearTimeout(timer);
  }, [selectedId, loadDetail]);

  const selected = runs?.find((item) => item.shadow_run_id === selectedId) ?? null;

  async function createRun(formData: FormData) {
    setFormError(null);
    setBusy("create");
    try {
      let riskBudget: Record<string, unknown> = {};
      const riskBudgetText = String(formData.get("risk_budget") ?? "").trim();
      if (riskBudgetText) {
        try { riskBudget = JSON.parse(riskBudgetText); } catch { throw new Error("Risk büdcəsi düzgün JSON deyil."); }
      }
      const body = {
        planned_end_at: new Date(String(formData.get("planned_end_at"))).toISOString(),
        code_commit: String(formData.get("code_commit")),
        config_hash: String(formData.get("config_hash")),
        feature_claim_versions: splitList(String(formData.get("feature_claim_versions") ?? "")),
        symbols: splitList(String(formData.get("symbols") ?? "")),
        timeframes: splitList(String(formData.get("timeframes") ?? "")),
        sessions: splitList(String(formData.get("sessions") ?? "")),
        accepted_market_regimes: splitList(String(formData.get("accepted_market_regimes") ?? "")),
        minimum_market_open_duration_seconds: Number(formData.get("minimum_market_open_duration_seconds")),
        minimum_eligible_decision_count: Number(formData.get("minimum_eligible_decision_count")),
        primary_metric: String(formData.get("primary_metric")),
        primary_metric_threshold: Number(formData.get("primary_metric_threshold")),
        secondary_metrics: {}, failure_rules: {}, theoretical_fill_model: {},
        risk_budget: riskBudget, data_quality_policy: {},
        approved_by: String(formData.get("approved_by")),
        rollback_plan: String(formData.get("rollback_plan")),
        participants: [{ role: "champion", module_id: String(formData.get("module_id")), module_version: String(formData.get("module_version")) }],
      };
      const response = await fetch(`${API_BASE}/api/v2/shadow-runs`, {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib."); }
      if (!response.ok) throw new Error(`Run yaradıla bilmədi (HTTP ${response.status}).`);
      const created = (await response.json()).data as ShadowRun;
      setShowCreateForm(false);
      await loadRuns();
      setSelectedId(created.shadow_run_id);
    } catch (failure) {
      setFormError(failure instanceof Error ? failure.message : "Run yaradıla bilmədi.");
    } finally { setBusy(null); }
  }

  async function transition(action: "start" | "complete" | "halt") {
    if (!selected) return;
    setBusy(action);
    try {
      const body: Record<string, unknown> = { expected_state_version: selected.state_version };
      if (action === "halt") {
        const reason = window.prompt("Dayandırma səbəbini yazın:");
        if (!reason) { setBusy(null); return; }
        body.reason = reason;
      }
      const response = await fetch(`${API_BASE}/api/v2/shadow-runs/${selected.shadow_run_id}/${action}`, {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await loadRuns();
      await loadDetail(selected.shadow_run_id);
    } catch { setDetailError("Vəziyyət dəyişdirilə bilmədi."); } finally { setBusy(null); }
  }

  async function recordEvent(formData: FormData) {
    if (!selected) return;
    setBusy("event");
    try {
      let payload: Record<string, unknown> = {};
      const payloadText = String(formData.get("payload") ?? "").trim();
      if (payloadText) { try { payload = JSON.parse(payloadText); } catch { throw new Error("Payload düzgün JSON deyil."); } }
      const response = await fetch(`${API_BASE}/api/v2/shadow-runs/${selected.shadow_run_id}/events`, {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ event_type: String(formData.get("event_type")), correlation_id: newCorrelationId(), payload }),
      });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await loadDetail(selected.shadow_run_id);
    } catch (failure) {
      setDetailError(failure instanceof Error ? failure.message : "Event qeydə alına bilmədi.");
    } finally { setBusy(null); }
  }

  async function openPosition(formData: FormData) {
    if (!selected) return;
    setBusy("open-position");
    try {
      const response = await fetch(`${API_BASE}/api/v2/shadow-runs/${selected.shadow_run_id}/positions`, {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          participant_id: String(formData.get("participant_id")),
          symbol: String(formData.get("symbol")),
          direction: String(formData.get("direction")),
          theoretical_size: Number(formData.get("theoretical_size")),
          reserved_risk_amount: Number(formData.get("reserved_risk_amount")),
          correlation_id: newCorrelationId(),
        }),
      });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = (await response.json()).data as { opened: boolean; reason?: string };
      await loadDetail(selected.shadow_run_id);
      if (!result.opened) setDetailError(`Mövqe açılmadı — risk limiti: ${result.reason}`);
    } catch { setDetailError("Mövqe açıla bilmədi."); } finally { setBusy(null); }
  }

  async function closePosition(position: ShadowPosition) {
    if (!selected) return;
    const pnlText = window.prompt("Nəzəri PnL (%) daxil edin:", "0");
    if (pnlText === null) return;
    const pnl = Number(pnlText);
    if (!Number.isFinite(pnl)) { setDetailError("PnL rəqəm olmalıdır."); return; }
    setBusy(`close-${position.position_id}`);
    try {
      const response = await fetch(`${API_BASE}/api/v2/shadow-runs/${selected.shadow_run_id}/positions/${position.position_id}/close`, {
        method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ theoretical_pnl_percent: pnl, expected_state_version: position.state_version, correlation_id: newCorrelationId() }),
      });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await loadDetail(selected.shadow_run_id);
    } catch { setDetailError("Mövqe bağlana bilmədi."); } finally { setBusy(null); }
  }

  return (
    <section className="shadow-runs" aria-labelledby="shadow-runs-title">
      <div className="shadow-runs-head">
        <div>
          <p className="eyebrow">Phase 9 · skelet</p>
          <h2 id="shadow-runs-title">SHADOW run-ları</h2>
          <p>Run manifesti, event reyestri və nəzəri portfolio/risk ledger-i — hələ real qərar generatoru (Phase 5-8) olmadığı üçün yalnız əl ilə (admin) yaradılıb izlənilə bilər.</p>
        </div>
        <span className="research-pill danger-pill">NƏZƏRİDİR — REAL ƏMƏLİYYAT YOXDUR</span>
      </div>
      <p className="shadow-runs-boundary">
        Order göndərilmir, mövqe MT5-də açılmır, real hesab balansına toxunulmur. <code>execution_allowed</code> həmişə <code>false</code>-dur.
      </p>

      {listError && <div className="replay-error" role="alert">{listError} <button type="button" onClick={() => void loadRuns()}>Yenidən yoxla</button></div>}

      <div className="shadow-runs-body">
        <div className="shadow-runs-list">
          <div className="shadow-runs-list-head">
            <h3>Run-lar {runs ? `(${runs.length})` : ""}</h3>
            <button type="button" className="secondary-button" onClick={() => setShowCreateForm((value) => !value)}>
              {showCreateForm ? "Bağla" : "Yeni run"}
            </button>
          </div>
          {!runs && !listError && <div className="analysis-loading"><span className="loading-ring" /><strong>Yüklənir</strong></div>}
          {runs && runs.length === 0 && !showCreateForm && <p className="pattern-candidate-time">Hələ SHADOW run yoxdur.</p>}
          <ul className="shadow-runs-items">
            {runs?.map((run) => (
              <li key={run.shadow_run_id}>
                <button type="button" className={selectedId === run.shadow_run_id ? "active" : ""} onClick={() => setSelectedId(run.shadow_run_id)}>
                  <strong>{run.primary_metric}</strong>
                  <span>{STATE_LABELS[run.state] ?? run.state} · {azTime(run.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>

          {showCreateForm && (
            <form
              className="shadow-run-create-form"
              onSubmit={(event) => { event.preventDefault(); void createRun(new FormData(event.currentTarget)); }}
            >
              {formError && <p className="replay-error" role="alert">{formError}</p>}
              <label>Planlaşdırılan bitmə vaxtı<input name="planned_end_at" type="datetime-local" required /></label>
              <label>Kod commit<input name="code_commit" required defaultValue="" /></label>
              <label>Konfiqurasiya hash<input name="config_hash" required defaultValue="" /></label>
              <label>Feature/claim versiyaları (vergüllə)<input name="feature_claim_versions" required placeholder="market_structure:1.0.0" /></label>
              <label>Simvollar (vergüllə)<input name="symbols" required defaultValue="GOLD" /></label>
              <label>Timeframe-lər (vergüllə)<input name="timeframes" required defaultValue="M5" /></label>
              <label>Sessiyalar (vergüllə)<input name="sessions" required placeholder="london" /></label>
              <label>Qəbul edilən bazar rejimləri (vergüllə)<input name="accepted_market_regimes" required placeholder="trending" /></label>
              <label>Min. bazar-açıq müddət (saniyə)<input name="minimum_market_open_duration_seconds" type="number" min={0} required defaultValue={3600} /></label>
              <label>Min. uyğun qərar sayı<input name="minimum_eligible_decision_count" type="number" min={1} required defaultValue={30} /></label>
              <label>Əsas metrik<input name="primary_metric" required placeholder="net_return_percent" /></label>
              <label>Əsas metrik həddi<input name="primary_metric_threshold" type="number" step="any" required defaultValue={0.5} /></label>
              <label>Champion modul ID<input name="module_id" required placeholder="structure_break_long" /></label>
              <label>Champion modul versiyası<input name="module_version" required defaultValue="1.0.0" /></label>
              <label>Risk büdcəsi (JSON)<textarea name="risk_budget" rows={3} placeholder='{"max_concurrent_positions": 3}' /></label>
              <label>Təsdiqləyən şəxs<input name="approved_by" required placeholder="RISK-OFFICER" /></label>
              <label>Rollback planı<textarea name="rollback_plan" rows={2} required placeholder="halt and archive run" /></label>
              <button type="submit" className="secondary-button" disabled={busy === "create"}>{busy === "create" ? "Yaradılır…" : "Run-ı qeydə al"}</button>
            </form>
          )}
        </div>

        {selected && (
          <div className="shadow-run-detail">
            {detailError && <div className="replay-error" role="alert">{detailError}</div>}
            <div className="shadow-run-detail-head">
              <h3>{selected.primary_metric} — {STATE_LABELS[selected.state] ?? selected.state}</h3>
              <div className="shadow-run-actions">
                {selected.state === "registered" && <button type="button" className="secondary-button" disabled={!!busy} onClick={() => void transition("start")}>{busy === "start" ? "…" : "Başlat"}</button>}
                {selected.state === "started" && <button type="button" className="secondary-button" disabled={!!busy} onClick={() => void transition("complete")}>{busy === "complete" ? "…" : "Tamamla"}</button>}
                {(selected.state === "registered" || selected.state === "started") && <button type="button" className="secondary-button" disabled={!!busy} onClick={() => void transition("halt")}>{busy === "halt" ? "…" : "Dayandır"}</button>}
              </div>
            </div>
            {selected.halt_reason && <p className="shadow-runs-boundary">Dayandırma səbəbi: {selected.halt_reason}</p>}
            <p className="pattern-candidate-time">
              Iştirakçılar: {selected.participants.map((item) => `${item.role}: ${item.module_id} v${item.module_version}`).join(" · ")}
            </p>

            {summary && (
              <div className="pattern-summary">
                <span>Açıq mövqe: {summary.open_position_count}</span>
                <span>Ehtiyat risk: {summary.total_reserved_risk_amount}</span>
                <span>Bağlanmış mövqe: {summary.closed_position_count}</span>
                <span>Xalis nəzəri PnL: {summary.net_realized_theoretical_pnl_percent ?? "—"}</span>
              </div>
            )}

            <details className="shadow-run-section" open>
              <summary>Nəzəri mövqe aç</summary>
              <form
                className="shadow-run-inline-form"
                onSubmit={(event) => { event.preventDefault(); void openPosition(new FormData(event.currentTarget)); }}
              >
                <label>İştirakçı
                  <select name="participant_id" required>
                    {selected.participants.map((item) => <option key={item.participant_id} value={item.participant_id}>{item.role}: {item.module_id}</option>)}
                  </select>
                </label>
                <label>Simvol<input name="symbol" required defaultValue="GOLD" /></label>
                <label>İstiqamət
                  <select name="direction" required>
                    <option value="long">long</option>
                    <option value="short">short</option>
                  </select>
                </label>
                <label>Nəzəri ölçü<input name="theoretical_size" type="number" step="any" min={0.0001} required defaultValue={1} /></label>
                <label>Ehtiyat risk<input name="reserved_risk_amount" type="number" step="any" min={0} required defaultValue={1} /></label>
                <button type="submit" className="secondary-button" disabled={busy === "open-position"}>{busy === "open-position" ? "Açılır…" : "Aç"}</button>
              </form>
            </details>

            <div className="shadow-run-section">
              <h4>Mövqelər ({positions.length})</h4>
              <ul className="shadow-positions-list">
                {positions.map((position) => (
                  <li key={position.position_id}>
                    <span>{position.symbol} · {position.direction} · ölçü {position.theoretical_size} · risk {position.reserved_risk_amount}</span>
                    <span>{position.state === "open" ? "açıq" : `bağlı (PnL ${position.theoretical_pnl_percent}%)`}</span>
                    {position.state === "open" && (
                      <button type="button" className="secondary-button" disabled={busy === `close-${position.position_id}`} onClick={() => void closePosition(position)}>
                        {busy === `close-${position.position_id}` ? "…" : "Bağla"}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            <details className="shadow-run-section">
              <summary>Event qeydə al</summary>
              <form
                className="shadow-run-inline-form"
                onSubmit={(event) => { event.preventDefault(); void recordEvent(new FormData(event.currentTarget)); }}
              >
                <label>Növ
                  <select name="event_type" required>
                    {SHADOW_EVENT_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
                <label>Payload (JSON)<textarea name="payload" rows={2} placeholder="{}" /></label>
                <button type="submit" className="secondary-button" disabled={busy === "event"}>{busy === "event" ? "Qeydə alınır…" : "Qeydə al"}</button>
              </form>
            </details>

            <div className="shadow-run-section">
              <h4>Event-lər ({events.length})</h4>
              <ul className="shadow-events-list">
                {events.map((event) => (
                  <li key={event.event_id}>
                    <strong>{event.event_type}</strong>
                    <span>{azTime(event.occurred_at)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
      <p className="pattern-boundary"><strong>Mərhələ sərhədi:</strong> Bu bölmə Phase 9 SHADOW müqaviləsinin persistence skeletidir. Real bazar müşahidəsi, qərar generasiyası və order icrası yoxdur.</p>
    </section>
  );
}
