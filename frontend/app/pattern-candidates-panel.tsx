"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";

type Timeframe = "M1" | "M5" | "M15" | "H1";
type PatternCandidateSlot = {
  candidate_id: string;
  hypothesis_id: string;
  hypothesis_version: string;
  family: string;
  direction: string;
  lifecycle_state: string;
  condition_state: "candidate_confirmed" | "no_candidate" | "insufficient_data";
  observed_at: string | null;
  evidence: Record<string, unknown>;
};
type PatternCandidates = {
  version: string;
  hypothesis_registry_version: string;
  slots: PatternCandidateSlot[];
  fingerprint: string;
  interpretation: string;
};
type ReplayPatternCandidates = {
  session_id: string;
  symbol: string;
  timeframe: Timeframe;
  parameters: Record<string, number>;
  lineage: Record<string, unknown>;
  pattern_candidates: PatternCandidates;
  interpretation: string;
  api_version: string;
};
type Envelope<T> = { data: T };

const HYPOTHESIS_TITLES: Record<string, string> = {
  market_structure_long: "Yüksələn bazar strukturu",
  market_structure_short: "Enən bazar strukturu",
  liquidity_sweep_reclaim_long: "Aşağı səviyyə süpürülməsi və geri alınma",
  liquidity_sweep_reclaim_short: "Yuxarı səviyyə süpürülməsi və geri alınma",
  structure_break_long: "Yuxarı struktur qırılması və retest",
  structure_break_short: "Aşağı struktur qırılması və retest",
};

const CONDITION_LABELS: Record<string, string> = {
  candidate_confirmed: "Şərt təsdiqləndi (draft)",
  no_candidate: "Şərt ödənmir",
  insufficient_data: "Məlumat azdır",
};

function formatTime(value: string | null) {
  return value ? new Intl.DateTimeFormat("az-AZ", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "—";
}

function evidenceEntries(evidence: Record<string, unknown>) {
  return Object.entries(evidence).filter(([, value]) => value !== null && value !== undefined);
}

function PatternSlotCard({ slot }: { slot: PatternCandidateSlot }) {
  const tone = slot.condition_state === "candidate_confirmed" ? "confirmed" : slot.condition_state === "insufficient_data" ? "warmup" : "empty";
  return (
    <article className={`pattern-candidate-slot ${tone}`}>
      <header>
        <div>
          <p className="eyebrow">{slot.family} · {slot.direction}</p>
          <h5>{HYPOTHESIS_TITLES[slot.hypothesis_id] ?? slot.hypothesis_id}</h5>
        </div>
        <span className={`analysis-badge ${slot.condition_state === "candidate_confirmed" ? "ready" : "warmup"}`}>
          {CONDITION_LABELS[slot.condition_state] ?? slot.condition_state}
        </span>
      </header>
      <p className="pattern-candidate-time">{slot.observed_at ? `Müşahidə vaxtı: ${formatTime(slot.observed_at)}` : "Hələ müşahidə yoxdur"}</p>
      {evidenceEntries(slot.evidence).length > 0 && (
        <dl className="pattern-candidate-evidence">
          {evidenceEntries(slot.evidence).map(([key, value]) => (
            <div key={key}><dt>{key}</dt><dd>{String(value)}</dd></div>
          ))}
        </dl>
      )}
    </article>
  );
}

export function PatternCandidatesPanel({ sessionId, symbol, token, onUnauthorized }: { sessionId: string; symbol: string; token: string; onUnauthorized: () => void }) {
  const [timeframe, setTimeframe] = useState<Timeframe>("M5");
  const [barLimit, setBarLimit] = useState(500);
  const [query, setQuery] = useState({ timeframe: "M5" as Timeframe, barLimit: 500 });
  const [result, setResult] = useState<ReplayPatternCandidates | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ timeframe: query.timeframe, bar_limit: String(query.barLimit) });
    try {
      const response = await fetch(`${API_BASE}/api/v2/replay-sessions/${sessionId}/pattern-candidates?${params}`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Replay məlumatı dəyişib və ya sessiya tamamlanmayıb.");
      if (!response.ok) throw new Error(`Pattern namizədləri alına bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Envelope<ReplayPatternCandidates>;
      setResult(payload.data);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Pattern namizədləri alına bilmədi.");
    } finally { setLoading(false); }
  }, [onUnauthorized, query, sessionId, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <section className="pattern-candidates" aria-labelledby="pattern-candidates-title">
      <div className="analysis-heading">
        <div>
          <p className="eyebrow">Draft tədqiqat namizədi · siqnal, giriş və ya order deyil</p>
          <h3 id="pattern-candidates-title">{symbol} pattern namizədləri</h3>
          <p>Struktur, likvidlik və struktur qırılması/retest detektorlarının hazır olan nəticələrini birləşdirir. Backtest, label, qəbul/rədd qərarı bu mərhələyə daxil deyil.</p>
        </div>
      </div>

      <form className="analysis-controls" onSubmit={(event) => {
        event.preventDefault();
        const next = { timeframe, barLimit };
        if (JSON.stringify(next) === JSON.stringify(query)) void load();
        else setQuery(next);
      }}>
        <label>Vaxt çərçivəsi<select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}><option>M1</option><option>M5</option><option>M15</option><option>H1</option></select></label>
        <label>Görünən bar<select value={barLimit} onChange={(event) => setBarLimit(Number(event.target.value))}><option value="100">100</option><option value="250">250</option><option value="500">500</option><option value="1000">1 000</option></select></label>
        <button type="submit" disabled={loading}>{loading ? "Hesablanır…" : "Namizədləri hesabla"}</button>
      </form>

      {error && <div className="analysis-error" role="alert"><strong>Pattern namizədləri göstərilə bilmədi</strong><span>{error}</span><button type="button" onClick={() => void load()}>Yenidən yoxla</button></div>}
      {loading && !result ? <div className="analysis-loading"><span className="loading-ring" /><div><strong>Mövcud detektorlar birləşdirilir</strong><p>Yalnız bağlanmış barlardan alınan causal nəticələr istifadə olunur.</p></div></div> : result && <>
        <div className="pattern-candidate-grid">
          {result.pattern_candidates.slots.map((slot) => <PatternSlotCard key={slot.candidate_id} slot={slot} />)}
        </div>
        <details className="analysis-lineage">
          <summary>Məlumat mənbəyi və hesablamanın izi</summary>
          <dl>
            <div><dt>Namizəd modulu versiyası</dt><dd>{result.pattern_candidates.version}</dd></div>
            <div><dt>Hipotez reyestri versiyası</dt><dd>{result.pattern_candidates.hypothesis_registry_version}</dd></div>
            <div><dt>Nəticə izi</dt><dd title={result.pattern_candidates.fingerprint}>{result.pattern_candidates.fingerprint.slice(0, 20)}…</dd></div>
          </dl>
        </details>
        <p className="analysis-disclaimer"><strong>Qeyd:</strong> Bütün namizədlər `draft` vəziyyətindədir. Backtest, label/horizon ölçümü, qəbul/rədd qərarı və SHADOW hazırlığı ayrıca, sonrakı mərhələlərdir. Platforma bu bölmədə alış/satış siqnalı vermir və order yaratmır.</p>
      </>}
    </section>
  );
}
