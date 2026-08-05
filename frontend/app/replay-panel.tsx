"use client";

import { useCallback, useEffect, useState } from "react";
import { TechnicalAnalysisPanel } from "./technical-analysis-panel";
import { StrategyComparisonPanel } from "./strategy-comparison-panel";
import type { DashboardSection } from "./dashboard-navigation";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";

type ReplaySession = {
  session_id: string;
  created_by: string;
  symbol: string;
  start_at: string;
  end_at: string;
  mode: "step" | "max_speed";
  state: string;
  state_version: number;
  dataset_tick_count: number;
  processed_ticks: number;
  created_at: string;
  completed_at: string | null;
};

type ReplayEvent = { event_id: string; timestamp: string; bid: number; ask: number };
type QualityReport = {
  report_id: string;
  content_fingerprint: string;
  summary: { status: string; tick_count: number; finding_count: number };
};

type Envelope<T> = { data: T };
type Page<T> = Envelope<T[]> & { page: { next_cursor: string | null; has_more: boolean } };

function localInput(date: Date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function azTime(value: string | null) {
  return value ? new Intl.DateTimeFormat("az-AZ", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
}

type ReplayView = Exclude<DashboardSection, "results" | "live" | "hypotheses">;

export function ReplayPanel({ token, onUnauthorized, view, onOpenReplay }: { token: string; onUnauthorized: () => void; view: ReplayView; onOpenReplay: () => void }) {
  const now = new Date();
  const [symbol, setSymbol] = useState("GOLD");
  const [startAt, setStartAt] = useState(localInput(new Date(now.getTime() - 3600000)));
  const [endAt, setEndAt] = useState(localInput(now));
  const [mode, setMode] = useState<"step" | "max_speed">("step");
  const [stepSize, setStepSize] = useState(100);
  const [sessions, setSessions] = useState<ReplaySession[]>([]);
  const [selected, setSelected] = useState<ReplaySession | null>(null);
  const [events, setEvents] = useState<ReplayEvent[]>([]);
  const [eventCursor, setEventCursor] = useState<string | null>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const request = useCallback(async <T,>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...init?.headers },
    });
    if (response.status === 401) {
      onUnauthorized();
      throw new Error("Sessiyanın vaxtı bitib.");
    }
    if (response.status === 409) throw new Error("Vəziyyət dəyişib. Məlumat yeniləndi; əmri təkrar yoxlayın.");
    if (!response.ok) throw new Error(`Sorğu yerinə yetirilmədi (HTTP ${response.status}).`);
    return response.json() as Promise<T>;
  }, [onUnauthorized, token]);

  const loadSessions = useCallback(async (preferredId?: string) => {
    setLoading(true);
    try {
      const result = await request<Page<ReplaySession>>("/api/v2/replay-sessions?page_size=50");
      setSessions(result.data);
      setSelected((current) => {
        const id = preferredId ?? current?.session_id;
        return result.data.find((item) => item.session_id === id)
          ?? (view === "replay" ? result.data[0] : result.data.find((item) => item.state === "completed"))
          ?? result.data[0]
          ?? null;
      });
      setError(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Replay məlumatı alınmadı.");
    } finally {
      setLoading(false);
    }
  }, [request, view]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadSessions(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [loadSessions]);

  async function createSession(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const result = await request<Envelope<ReplaySession>>("/api/v2/replay-sessions", {
        method: "POST",
        body: JSON.stringify({ symbol: symbol.trim().toUpperCase(), start_at: new Date(startAt).toISOString(), end_at: new Date(endAt).toISOString(), mode }),
      });
      await loadSessions(result.data.session_id);
      setError(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Replay yaradıla bilmədi.");
    } finally { setBusy(false); }
  }

  async function command(name: "start" | "step" | "pause" | "resume" | "cancel") {
    if (!selected) return;
    setBusy(true);
    try {
      await request(`/api/v2/replay-sessions/${selected.session_id}/commands`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ command: name, expected_state_version: selected.state_version, requested_ticks: name === "step" ? stepSize : null }),
      });
      await loadSessions(selected.session_id);
      setError(null);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Əmr icra edilmədi.");
      await loadSessions(selected.session_id);
    } finally { setBusy(false); }
  }

  async function loadEvents(cursor?: string | null) {
    if (!selected) return;
    setBusy(true);
    try {
      const query = new URLSearchParams({ page_size: "25" });
      if (cursor) query.set("cursor", cursor);
      const result = await request<Page<ReplayEvent>>(`/api/v2/replay-sessions/${selected.session_id}/events?${query}`);
      setEvents(cursor ? (current) => [...current, ...result.data] : result.data);
      setEventCursor(result.page.next_cursor);
      setError(null);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Eventlər alınmadı."); }
    finally { setBusy(false); }
  }

  async function loadQuality() {
    if (!selected) return;
    setBusy(true);
    try {
      const result = await request<Envelope<QualityReport>>(`/api/v2/replay-sessions/${selected.session_id}/quality-report`);
      setQuality(result.data);
      setError(null);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Keyfiyyət hesabatı alınmadı."); }
    finally { setBusy(false); }
  }

  function choose(session: ReplaySession) {
    setSelected(session);
    setEvents([]);
    setEventCursor(null);
    setQuality(null);
    setError(null);
  }

  const progress = selected?.dataset_tick_count ? Math.min(100, selected.processed_ticks / selected.dataset_tick_count * 100) : 0;
  const canStart = selected?.state === "created";
  const canPause = selected?.state === "running";
  const canResume = selected && ["paused", "interrupted"].includes(selected.state);
  const canStep = selected?.mode === "step" && selected?.state === "running";
  const canCancel = selected && !["completed", "cancelled", "failed"].includes(selected.state);

  if (view !== "replay") {
    return (
      <>
        <section className="panel analysis-context-panel" aria-labelledby="analysis-context-title">
          <div className="section-heading">
            <div><p className="eyebrow">Araşdırma konteksti</p><h2 id="analysis-context-title">Seçilmiş replay məlumatı</h2></div>
            <button className="secondary-button" type="button" onClick={onOpenReplay}>Sessiyanı dəyiş</button>
          </div>
          <p className="replay-notice">Aşağıdakı analiz yalnız tamamlanmış tarixi sessiyaya əsaslanır. Ticarət əməliyyatı aparılmır.</p>
          {error && <p className="replay-error" role="alert">{error}</p>}
          {loading ? <p className="empty-state">Məlumat konteksti yüklənir...</p> : !selected ? <p className="empty-state">Analiz üçün əvvəlcə replay sessiyası yaradın.</p> : <>
            <div className="analysis-context-grid">
              <div><span>Simvol</span><strong>{selected.symbol}</strong></div>
              <div><span>İnterval</span><strong>{azTime(selected.start_at)} — {azTime(selected.end_at)}</strong></div>
              <div><span>Vəziyyət</span><strong>{selected.state}</strong></div>
              <div><span>Rejim</span><strong>{selected.mode}</strong></div>
              <div><span>İrəliləyiş</span><strong>{selected.processed_ticks} / {selected.dataset_tick_count}</strong></div>
            </div>
            {selected.state !== "completed" && <p className="replay-error">Bu analiz üçün tamamlanmış sessiya seçilməlidir. “Sessiyanı dəyiş” düyməsindən istifadə edin.</p>}
          </>}
        </section>
        {selected?.state === "completed" && view === "strategies" &&
          <StrategyComparisonPanel key={`strategy-${selected.session_id}`} sessionId={selected.session_id} symbol={selected.symbol} token={token} onUnauthorized={onUnauthorized} />}
        {selected?.state === "completed" && ["technical", "structure", "liquidity", "bos-choch", "retest"].includes(view) &&
          <TechnicalAnalysisPanel key={`technical-${selected.session_id}`} view={view as Exclude<ReplayView, "replay" | "strategies">} sessionId={selected.session_id} symbol={selected.symbol} token={token} onUnauthorized={onUnauthorized} />}
      </>
    );
  }

  return (
    <section className="panel replay-panel" aria-labelledby="replay-title">
      <div className="section-heading">
        <div><p className="eyebrow">Araşdırma məlumatı</p><h2 id="replay-title">Tarixi məlumatın replay idarəetməsi</h2></div>
        <button className="secondary-button" type="button" onClick={() => void loadSessions()} disabled={loading || busy}>Yenilə</button>
      </div>
      <p className="replay-notice">Bu bölmə yalnız məlumatı yenidən oynadır və analiz üçün hazırlayır. Ticarət əməliyyatı aparılmır.</p>
      {error && <p className="replay-error" role="alert">{error}</p>}

      <form className="replay-form" onSubmit={createSession}>
        <label>Simvol<input value={symbol} onChange={(e) => setSymbol(e.target.value)} required maxLength={32} /></label>
        <label>Başlanğıc<input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} required /></label>
        <label>Son<input type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} required /></label>
        <label>Rejim<select value={mode} onChange={(e) => setMode(e.target.value as "step" | "max_speed")}><option value="step">Addım-addım</option><option value="max_speed">Maksimum sürət</option></select></label>
        <button type="submit" disabled={busy}>Replay yarat</button>
      </form>

      <div className="replay-layout">
        <div>
          <h3>Sessiyalar</h3>
          {loading ? <p className="empty-state">Sessiyalar yüklənir...</p> : sessions.length === 0 ? <p className="empty-state">Hələ replay sessiyası yoxdur.</p> : (
            <div className="replay-list">{sessions.map((session) => <button type="button" className={selected?.session_id === session.session_id ? "selected" : ""} key={session.session_id} onClick={() => choose(session)}><strong>{session.symbol}</strong><span>{session.state} · {session.mode}</span><small>{azTime(session.created_at)}</small></button>)}</div>
          )}
        </div>
        <div className="replay-detail">
          <h3>Sessiya detalı</h3>
          {!selected ? <p className="empty-state">Detalları görmək üçün sessiya seçin.</p> : <>
            <dl><div><dt>Vəziyyət</dt><dd>{selected.state}</dd></div><div><dt>Simvol</dt><dd>{selected.symbol}</dd></div><div><dt>İnterval</dt><dd>{azTime(selected.start_at)} — {azTime(selected.end_at)}</dd></div><div><dt>İrəliləyiş</dt><dd>{selected.processed_ticks} / {selected.dataset_tick_count}</dd></div></dl>
            <div className="replay-progress"><span style={{ width: `${progress}%` }} /></div>
            <div className="replay-actions">
              {canStart && <button disabled={busy} onClick={() => void command("start")}>Başlat</button>}
              {canStep && <><label>Addım<input type="number" min="1" max="10000" value={stepSize} onChange={(e) => setStepSize(Number(e.target.value))} /></label><button disabled={busy} onClick={() => void command("step")}>İrəlilə</button></>}
              {canPause && <button disabled={busy} onClick={() => void command("pause")}>Dayandır</button>}
              {canResume && <button disabled={busy} onClick={() => void command("resume")}>Davam etdir</button>}
              {canCancel && <button className="danger-button" disabled={busy} onClick={() => void command("cancel")}>Ləğv et</button>}
              <button className="secondary-button" disabled={busy} onClick={() => void loadEvents(null)}>Eventləri göstər</button>
              {selected.state === "completed" && <button className="secondary-button" disabled={busy} onClick={() => void loadQuality()}>Keyfiyyət hesabatı</button>}
            </div>
            {events.length > 0 && <div className="replay-results"><h4>Event nümunələri</h4><div className="table-wrap"><table><thead><tr><th>Event</th><th>Vaxt</th><th>Bid</th><th>Ask</th></tr></thead><tbody>{events.map((item) => <tr key={item.event_id}><td>{item.event_id}</td><td>{azTime(item.timestamp)}</td><td>{item.bid}</td><td>{item.ask}</td></tr>)}</tbody></table></div>{eventCursor && <button className="secondary-button" disabled={busy} onClick={() => void loadEvents(eventCursor)}>Daha çox göstər</button>}</div>}
            {quality && <div className="quality-summary"><h4>Keyfiyyət nəticəsi</h4><strong>{quality.summary.status}</strong><p>{quality.summary.tick_count} tick · {quality.summary.finding_count} tapıntı</p><small>{quality.report_id}</small></div>}
          </>}
        </div>
      </div>
    </section>
  );
}
