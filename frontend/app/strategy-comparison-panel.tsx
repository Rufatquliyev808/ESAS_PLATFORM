"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";
type Timeframe = "M1" | "M5" | "M15" | "H1";
type StrategyResult = {
  definition: { strategy_id: string; version: string; lifecycle: string; description: string; required_features: string[]; interpretation: string };
  summary: { ready: number; insufficient_data: number; above: number; below: number; equal: number };
  parameters: Array<[string, number | string]>;
  fingerprint: string;
  dataset_fingerprint: string;
  bar_fingerprint: string;
  indicator_fingerprint: string;
  outcome_evaluation: {
    definition: { evaluator_id: string; version: string; lifecycle: string; interpretation: string };
    horizon_bars: number;
    summary: {
      matured: number; immature: number; not_applicable: number;
      up: number; down: number; flat: number; mean_return_percent: number | null;
      by_relation: Array<{ relation: string; count: number; up: number; down: number; flat: number; mean_return_percent: number }>;
    };
    fingerprint: string;
    interpretation: string;
  };
};
type StrategyAnalysis = { symbol: string; timeframe: Timeframe; strategies: StrategyResult[]; interpretation: string; api_version: string };

function percent(value: number, total: number) { return total ? value / total * 100 : 0; }
function CountBar({ label, value, total, tone }: { label: string; value: number; total: number; tone: string }) {
  const share = percent(value, total);
  return <div className="strategy-count"><div><span>{label}</span><strong>{value} · {share.toFixed(1)}%</strong></div><div className="strategy-meter"><span className={tone} style={{ width: `${share}%` }} /></div></div>;
}

export function StrategyComparisonPanel({ sessionId, symbol, token, onUnauthorized }: { sessionId: string; symbol: string; token: string; onUnauthorized: () => void }) {
  const [timeframe, setTimeframe] = useState<Timeframe>("M5");
  const [emaPeriod, setEmaPeriod] = useState(20);
  const [rsiPeriod, setRsiPeriod] = useState(14);
  const [rsiLow, setRsiLow] = useState(30);
  const [rsiHigh, setRsiHigh] = useState(70);
  const [barLimit, setBarLimit] = useState(500);
  const [outcomeHorizon, setOutcomeHorizon] = useState(3);
  const [query, setQuery] = useState({ timeframe: "M5" as Timeframe, emaPeriod: 20, rsiPeriod: 14, rsiLow: 30, rsiHigh: 70, barLimit: 500, outcomeHorizon: 3 });
  const [result, setResult] = useState<StrategyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    const params = new URLSearchParams({ timeframe: query.timeframe, ema_period: String(query.emaPeriod), rsi_period: String(query.rsiPeriod), rsi_low: String(query.rsiLow), rsi_high: String(query.rsiHigh), bar_limit: String(query.barLimit), outcome_horizon: String(query.outcomeHorizon) });
    try {
      const response = await fetch(`${API_BASE}/api/v2/replay-sessions/${sessionId}/strategy-analysis?${params}`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Replay məlumatı dəyişib və ya sessiya tamamlanmayıb.");
      if (!response.ok) throw new Error(`Strategiya müşahidələri alına bilmədi (HTTP ${response.status}).`);
      setResult((await response.json()).data as StrategyAnalysis);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Strategiya müşahidələri alına bilmədi."); }
    finally { setLoading(false); }
  }, [onUnauthorized, query, sessionId, token]);

  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);

  return <section className="strategy-lab" aria-labelledby="strategy-lab-title">
    <div className="strategy-heading"><div><p className="eyebrow">Phase 4 · ayrıca versiyalanan modullar</p><h3 id="strategy-lab-title">{symbol} strategiya müqayisə laboratoriyası</h3><p>Hər metod ayrıca kartda hesablanır ki, sonrakı düzəlişlər bir-birindən asılı olmasın.</p></div><span className="research-pill">Araşdırma müşahidəsidir · siqnal deyil</span></div>
    <form className="strategy-controls" onSubmit={(event) => {
      event.preventDefault();
      const next = { timeframe, emaPeriod, rsiPeriod, rsiLow, rsiHigh, barLimit, outcomeHorizon };
      if (JSON.stringify(next) === JSON.stringify(query)) void load();
      else setQuery(next);
    }}>
      <label>Vaxt çərçivəsi<select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}><option>M1</option><option>M5</option><option>M15</option><option>H1</option></select></label>
      <label>EMA dövrü<input type="number" min="2" max="500" value={emaPeriod} onChange={(event) => setEmaPeriod(Number(event.target.value))} /></label>
      <label>RSI dövrü<input type="number" min="2" max="500" value={rsiPeriod} onChange={(event) => setRsiPeriod(Number(event.target.value))} /></label>
      <label>RSI aşağı hədd<input type="number" min="0" max="99" value={rsiLow} onChange={(event) => setRsiLow(Number(event.target.value))} /></label>
      <label>RSI yuxarı hədd<input type="number" min="1" max="100" value={rsiHigh} onChange={(event) => setRsiHigh(Number(event.target.value))} /></label>
      <label>Görünən bar<select value={barLimit} onChange={(event) => setBarLimit(Number(event.target.value))}><option value="100">100</option><option value="250">250</option><option value="500">500</option><option value="1000">1 000</option></select></label>
      <label>Nəticə üfüqü (bar)<input type="number" min="1" max="100" value={outcomeHorizon} onChange={(event) => setOutcomeHorizon(Number(event.target.value))} /></label>
      <button disabled={loading}>{loading ? "Hesablanır…" : "Müşahidələri hesabla"}</button>
    </form>
    {error && <div className="analysis-error" role="alert"><strong>Strategiya bölməsi göstərilə bilmədi</strong><span>{error}</span><button type="button" onClick={() => void load()}>Yenidən yoxla</button></div>}
    {loading && !result ? <div className="analysis-loading"><span className="loading-ring" /><div><strong>Modullar ayrıca hesablanır</strong><p>Nəticələr ticarət əmrinə çevrilmir.</p></div></div> : result && <div className="strategy-grid">{result.strategies.map((strategy) => {
      const total = strategy.summary.ready;
      const isRsi = strategy.definition.strategy_id === "rsi_regime_observation";
      return <article className="strategy-card" key={`${strategy.definition.strategy_id}:${strategy.definition.version}`}>
        <header><div><p className="eyebrow">{isRsi ? "Momentum / bazar rejimi" : "Bağlanış / trend istinadı"}</p><h4>{isRsi ? "RSI momentum rejimi" : "Qiymətin EMA ilə münasibəti"}</h4></div><div className="strategy-tags"><span>v{strategy.definition.version}</span><span>{strategy.definition.lifecycle}</span></div></header>
        <p className="strategy-explanation">{isRsi ? `RSI ${rsiLow}-dan aşağı, ${rsiHigh}-dan yuxarı və ya bu hədlərin arasında neytral rejim kimi təsnif edilir. Sərhədə bərabərlik aşağı/yuxarı rejimə daxildir.` : "Hər bağlanmış barın son qiyməti öz səbəbli EMA dəyərindən yuxarı, aşağı və ya bərabər kimi təsnif edilir. Bu, yalnız bazar vəziyyətinin təsviridir."}</p>
        <div className="strategy-counts"><CountBar label={isRsi ? "Yüksək RSI rejimi" : "EMA-dan yuxarı"} value={strategy.summary.above} total={total} tone="above" /><CountBar label={isRsi ? "Aşağı RSI rejimi" : "EMA-dan aşağı"} value={strategy.summary.below} total={total} tone="below" /><CountBar label={isRsi ? "Neytral RSI rejimi" : "EMA-ya bərabər"} value={strategy.summary.equal} total={total} tone="equal" /></div>
        <div className="strategy-summary"><div><span>Hazır müşahidə</span><strong>{strategy.summary.ready}</strong></div><div><span>Warm-up</span><strong>{strategy.summary.insufficient_data}</strong></div><div><span>Vaxt çərçivəsi</span><strong>{result.timeframe}</strong></div></div>
        <div className="strategy-outcomes">
          <div><p className="eyebrow">Tarixi nəticə ölçümü · siqnal deyil</p><h5>{strategy.outcome_evaluation.horizon_bars} qapalı bar sonrakı dəyişiklik</h5><p>Müşahidədən yalnız sonrakı qapalı barın qiyməti ilə ölçülür; gələcək qiymət müşahidənin yaradılmasına daxil edilmir.</p></div>
          <div className="strategy-summary"><div><span>Ölçülmüş</span><strong>{strategy.outcome_evaluation.summary.matured}</strong></div><div><span>Yetkinləşməyən</span><strong>{strategy.outcome_evaluation.summary.immature}</strong></div><div><span>Orta dəyişiklik</span><strong>{strategy.outcome_evaluation.summary.mean_return_percent === null ? "—" : `${strategy.outcome_evaluation.summary.mean_return_percent.toFixed(3)}%`}</strong></div></div>
          <div className="strategy-counts"><CountBar label="Yuxarı bağlanıb" value={strategy.outcome_evaluation.summary.up} total={strategy.outcome_evaluation.summary.matured} tone="above" /><CountBar label="Aşağı bağlanıb" value={strategy.outcome_evaluation.summary.down} total={strategy.outcome_evaluation.summary.matured} tone="below" /><CountBar label="Dəyişməyib" value={strategy.outcome_evaluation.summary.flat} total={strategy.outcome_evaluation.summary.matured} tone="equal" /></div>
          <details><summary>Rejimlər üzrə tarixi müqayisə</summary><dl>{strategy.outcome_evaluation.summary.by_relation.map((item) => <div key={item.relation}><dt>{item.relation}</dt><dd>{item.count} nəticə · orta {item.mean_return_percent.toFixed(3)}%</dd></div>)}</dl></details>
        </div>
        <details><summary>Versiya və hesablama izi</summary><dl><div><dt>Modul</dt><dd>{strategy.definition.strategy_id}</dd></div><div><dt>Tələb olunan xüsusiyyət</dt><dd>{strategy.definition.required_features.join(", ")}</dd></div><div><dt>Nəticə izi</dt><dd title={strategy.fingerprint}>{strategy.fingerprint.slice(0, 22)}…</dd></div><div><dt>Bar izi</dt><dd title={strategy.bar_fingerprint}>{strategy.bar_fingerprint.slice(0, 22)}…</dd></div></dl></details>
      </article>;
    })}</div>}
    <p className="strategy-disclaimer"><strong>Təhlükəsizlik sərhədi:</strong> Bu laboratoriya alış/satış qərarı vermir, mövqe ölçüsü hesablamır və ticarət əməliyyatı açmır.</p>
  </section>;
}
