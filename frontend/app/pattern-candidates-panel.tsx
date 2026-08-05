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
type PersistedPatternCandidate = {
  candidate_id: string;
  created_by: string;
  replay_session_id: string;
  hypothesis_id: string;
  hypothesis_version: string;
  family: string;
  direction: string;
  condition_state: string;
  observed_at: string | null;
  evidence: Record<string, unknown>;
  pattern_candidate_version: string;
  hypothesis_registry_version: string;
  source_fingerprint: string;
  timeframe: string;
  parameters: Record<string, unknown>;
  lifecycle_state: "registered" | "evaluated" | "archived";
  state_version: number;
  created_at: string;
  updated_at: string;
};
type BacktestScenario = {
  scenario: string;
  total_cost_bps: number;
  effective_sample_size: number;
  net_mean_return_percent: number | null;
  hit_rate_percent: number | null;
  confidence_interval_low_percent: number | null;
  confidence_interval_high_percent: number | null;
  status: "supportive_evidence" | "insufficient_evidence";
  reason: string;
};
type PersistedPatternCandidateBacktest = {
  backtest_id: string;
  candidate_id: string;
  horizon_bars: number;
  result: {
    total_events: number;
    matured_events: number;
    immature_events: number;
    scenarios: BacktestScenario[];
  };
  fingerprint: string;
  created_at: string;
};
type Envelope<T> = { data: T };
type Page<T> = Envelope<T[]>;

const BACKTESTABLE_HYPOTHESES = new Set([
  "structure_break_long", "structure_break_short",
  "liquidity_sweep_reclaim_long", "liquidity_sweep_reclaim_short",
]);
const BACKTEST_STATUS_LABELS: Record<string, string> = {
  supportive_evidence: "Sübut yetərlidir",
  insufficient_evidence: "Sübut yetərli deyil",
};

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

function PatternSlotCard({ slot, registeredCandidateId, registering, onRegister }: {
  slot: PatternCandidateSlot;
  registeredCandidateId?: string;
  registering: boolean;
  onRegister: (slot: PatternCandidateSlot) => void;
}) {
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
      {slot.condition_state === "candidate_confirmed" && (
        registeredCandidateId ? (
          <p className="pattern-candidate-registered">Qeydə alınıb (draft) · {registeredCandidateId.slice(0, 24)}…</p>
        ) : (
          <button type="button" className="secondary-button" disabled={registering} onClick={() => onRegister(slot)}>
            {registering ? "Qeydə alınır…" : "Draft kimi qeydə al"}
          </button>
        )
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
  const [registered, setRegistered] = useState<PersistedPatternCandidate[]>([]);
  const [registeredError, setRegisteredError] = useState<string | null>(null);
  const [registeringHypothesis, setRegisteringHypothesis] = useState<string | null>(null);
  const [archivingCandidateId, setArchivingCandidateId] = useState<string | null>(null);
  const [backtests, setBacktests] = useState<Record<string, PersistedPatternCandidateBacktest>>({});
  const [backtestingId, setBacktestingId] = useState<string | null>(null);

  const loadRegistered = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v2/pattern-candidates?page_size=100`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`Qeydə alınmış namizədlər alına bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Page<PersistedPatternCandidate>;
      setRegistered(payload.data);
      setRegisteredError(null);
    } catch (failure) {
      setRegisteredError(failure instanceof Error ? failure.message : "Qeydə alınmış namizədlər alına bilmədi.");
    }
  }, [onUnauthorized, token]);

  const registerSlot = useCallback(async (slot: PatternCandidateSlot) => {
    setRegisteringHypothesis(slot.hypothesis_id);
    setRegisteredError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v2/pattern-candidates`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          session_id: sessionId, hypothesis_id: slot.hypothesis_id,
          timeframe: query.timeframe, bar_limit: query.barLimit,
        }),
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Namizəd artıq təsdiqlənmiş vəziyyətdə deyil; əvvəlcə yenidən hesablayın.");
      if (!response.ok) throw new Error(`Namizəd qeydə alına bilmədi (HTTP ${response.status}).`);
      await loadRegistered();
    } catch (failure) {
      setRegisteredError(failure instanceof Error ? failure.message : "Namizəd qeydə alına bilmədi.");
    } finally { setRegisteringHypothesis(null); }
  }, [loadRegistered, onUnauthorized, query, sessionId, token]);

  const archiveCandidate = useCallback(async (candidate: PersistedPatternCandidate) => {
    setArchivingCandidateId(candidate.candidate_id);
    setRegisteredError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v2/pattern-candidates/${candidate.candidate_id}/archive`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ expected_state_version: candidate.state_version }),
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Namizəd vəziyyəti dəyişib; siyahını yeniləyin.");
      if (!response.ok) throw new Error(`Namizəd arxivləşdirilə bilmədi (HTTP ${response.status}).`);
      await loadRegistered();
    } catch (failure) {
      setRegisteredError(failure instanceof Error ? failure.message : "Namizəd arxivləşdirilə bilmədi.");
    } finally { setArchivingCandidateId(null); }
  }, [loadRegistered, onUnauthorized, token]);

  const runBacktest = useCallback(async (candidate: PersistedPatternCandidate) => {
    setBacktestingId(candidate.candidate_id);
    setRegisteredError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v2/pattern-candidates/${candidate.candidate_id}/backtest`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({}),
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 422) throw new Error("Bu hipotez üçün backtest v1 hələ dəstəklənmir.");
      if (!response.ok) throw new Error(`Backtest icra edilə bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Envelope<PersistedPatternCandidateBacktest>;
      setBacktests((current) => ({ ...current, [candidate.candidate_id]: payload.data }));
      await loadRegistered();
    } catch (failure) {
      setRegisteredError(failure instanceof Error ? failure.message : "Backtest icra edilə bilmədi.");
    } finally { setBacktestingId(null); }
  }, [loadRegistered, onUnauthorized, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadRegistered(), 0);
    return () => window.clearTimeout(timer);
  }, [loadRegistered]);

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
          {result.pattern_candidates.slots.map((slot) => {
            const existing = registered.find((item) => item.replay_session_id === sessionId && item.hypothesis_id === slot.hypothesis_id && item.lifecycle_state === "registered");
            return (
              <PatternSlotCard
                key={slot.candidate_id}
                slot={slot}
                registeredCandidateId={existing?.candidate_id}
                registering={registeringHypothesis === slot.hypothesis_id}
                onRegister={(item) => void registerSlot(item)}
              />
            );
          })}
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

      <section className="pattern-candidate-registered-list" aria-labelledby="pattern-candidates-registered-title">
        <h4 id="pattern-candidates-registered-title">Qeydə alınmış namizədlər (bütün sessiyalar)</h4>
        <p>Yalnız sizin qeydə aldığınız draft namizədlər. Bu siyahı da backtest, label və ya qəbul qərarı deyil.</p>
        {registeredError && <div className="analysis-error" role="alert"><strong>Siyahı göstərilə bilmədi</strong><span>{registeredError}</span></div>}
        {registered.length === 0 ? <p className="empty-state">Hələ qeydə alınmış namizəd yoxdur.</p> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Hipotez</th><th>Sessiya</th><th>Vəziyyət</th><th>Qeydə alınma</th><th>Backtest (v1)</th><th /></tr></thead>
              <tbody>
                {registered.map((candidate) => {
                  const backtest = backtests[candidate.candidate_id];
                  const supported = BACKTESTABLE_HYPOTHESES.has(candidate.hypothesis_id);
                  return (
                    <tr key={candidate.candidate_id}>
                      <td>{HYPOTHESIS_TITLES[candidate.hypothesis_id] ?? candidate.hypothesis_id}</td>
                      <td>{candidate.replay_session_id.slice(0, 16)}…</td>
                      <td>{candidate.lifecycle_state === "archived" ? "Arxivləşdirilib" : candidate.lifecycle_state === "evaluated" ? "Backtest edilib" : "Qeydə alınıb (draft)"}</td>
                      <td>{formatTime(candidate.created_at)}</td>
                      <td>
                        {!supported ? <span className="pattern-candidate-time">v1-də dəstəklənmir</span> : candidate.lifecycle_state === "archived" ? "—" : (
                          <div className="pattern-candidate-backtest-cell">
                            <button type="button" className="secondary-button" disabled={backtestingId === candidate.candidate_id} onClick={() => void runBacktest(candidate)}>
                              {backtestingId === candidate.candidate_id ? "Hesablanır…" : backtest ? "Yenidən hesabla" : "Backtest et"}
                            </button>
                            {backtest && (
                              <ul className="pattern-candidate-backtest-scenarios">
                                {backtest.result.scenarios.map((scenario) => (
                                  <li key={scenario.scenario} className={scenario.status}>
                                    <strong>{scenario.scenario}</strong>
                                    <span>n={scenario.effective_sample_size} · net {scenario.net_mean_return_percent === null ? "—" : `${scenario.net_mean_return_percent >= 0 ? "+" : ""}${scenario.net_mean_return_percent.toFixed(3)}%`}</span>
                                    <span>{BACKTEST_STATUS_LABELS[scenario.status] ?? scenario.status}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                      </td>
                      <td>
                        {candidate.lifecycle_state !== "archived" && (
                          <button type="button" className="secondary-button" disabled={archivingCandidateId === candidate.candidate_id} onClick={() => void archiveCandidate(candidate)}>
                            {archivingCandidateId === candidate.candidate_id ? "Arxivləşdirilir…" : "Arxivləşdir"}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="pattern-candidate-backtest-disclaimer">Backtest v1 &ldquo;Struktur qırılması + retest&rdquo; və &ldquo;Likvidlik süpürməsi&rdquo; hipotezlərini dəstəkləyir. Bazar strukturu hələ dəstəklənmir — o hipotez hazırda yalnız son müşahidəni saxlayır, tarixi nümunə üçün kifayət etmir. Nəticə tarixi simulyasiyadır — sifariş, mövqe ölçüsü və ya gəlir zəmanəti deyil.</p>
      </section>
    </section>
  );
}
