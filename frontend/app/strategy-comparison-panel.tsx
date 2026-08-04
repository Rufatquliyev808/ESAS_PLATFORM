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
  walk_forward_evaluation: {
    definition: { evaluator_id: string; version: string; lifecycle: string; interpretation: string };
    status: "ready" | "insufficient_data";
    manifest: { development_ratio: number; split_index: number; total_bars: number; parameter_source: string; split_policy: string; fingerprint?: string };
    development: WalkForwardWindow;
    validation: WalkForwardWindow;
    fingerprint: string;
    interpretation: string;
  };
  multi_window_evaluation: {
    definition: { evaluator_id: string; version: string; lifecycle: string; interpretation: string };
    status: "ready" | "insufficient_data";
    summary: {
      requested_windows: number; completed_windows: number; windows_with_matured_observations: number;
      positive_windows: number; negative_windows: number; flat_windows: number;
      total_validation_observations: number; matured_validation_observations: number;
      immature_validation_observations: number; not_applicable_validation_observations: number;
      weighted_mean_return_percent: number | null; minimum_window_mean_return_percent: number | null;
      maximum_window_mean_return_percent: number | null; return_range_percentage_points: number | null;
    };
    windows: Array<{
      window_number: number; development: WalkForwardWindow; validation: WalkForwardWindow;
      manifest: {
        development_end_index_exclusive: number; validation_start_index: number;
        validation_end_index_exclusive: number; development_bar_fingerprint: string;
        validation_bar_fingerprint: string;
      };
      fingerprint: string;
    }>;
    manifest: { requested_windows: number; initial_development_bars: number; split_policy: string };
    fingerprint: string;
    interpretation: string;
  };
  cost_scenario_evaluation: {
    definition: { evaluator_id: string; version: string; lifecycle: string; interpretation: string };
    scenarios: Array<{
      assumption: { scenario: "normal" | "adverse" | "stress"; spread_bps: number; commission_bps: number; slippage_bps: number; latency_bps: number; multiplier: number; total_cost_bps: number; total_cost_percent: number; unit: string; source: string };
      summary: { matured_observations: number; total_validation_observations: number; coverage_percent: number; raw_weighted_mean_return_percent: number | null; net_weighted_mean_return_percent: number | null; cost_per_observation_percent: number; aggregate_modeled_cost_percentage_points: number; positive_net_windows: number; negative_net_windows: number; flat_net_windows: number };
      windows: Array<{ window_number: number; matured_observations: number; raw_mean_return_percent: number | null; net_mean_return_percent: number | null }>;
    }>;
    manifest: { upstream_multi_window_fingerprint: string; scenario_policy: string; source: string; raw_result_policy: string };
    fingerprint: string;
    interpretation: string;
  };
  statistical_reliability_evaluation: {
    definition: { evaluator_id: string; version: string; lifecycle: string; interpretation: string };
    overall_status: "supportive_evidence" | "insufficient_evidence";
    scenarios: Array<{
      scenario: "normal" | "adverse" | "stress"; status: "supportive_evidence" | "insufficient_evidence";
      effective_sample_size: number; observed_mean_percent: number | null; baseline_mean_percent: number;
      raw_effect_percentage_points: number | null; standardized_effect_size: number | null;
      sample_standard_deviation: number | null; confidence_level_percent: number;
      confidence_interval_low_percent: number | null; confidence_interval_high_percent: number | null; reason: string;
    }>;
    manifest: { primary_metric: string; baseline: string; acceptance_rule: string; sampling_policy: string; minimum_effective_sample_size: number };
    fingerprint: string; interpretation: string;
  };
};
type WalkForwardWindow = {
  window: string; start_bar_end_at: string | null; end_bar_end_at: string | null;
  total_observations: number; matured: number; immature: number;
  not_applicable: number; boundary_excluded: number;
  up: number; down: number; flat: number; mean_return_percent: number | null;
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
  const [developmentRatio, setDevelopmentRatio] = useState(0.7);
  const [walkForwardWindows, setWalkForwardWindows] = useState(3);
  const [costSpreadBps, setCostSpreadBps] = useState(2);
  const [costCommissionBps, setCostCommissionBps] = useState(1);
  const [costSlippageBps, setCostSlippageBps] = useState(1);
  const [costLatencyBps, setCostLatencyBps] = useState(0.5);
  const [adverseCostMultiplier, setAdverseCostMultiplier] = useState(1.5);
  const [stressCostMultiplier, setStressCostMultiplier] = useState(2.5);
  const [query, setQuery] = useState({ timeframe: "M5" as Timeframe, emaPeriod: 20, rsiPeriod: 14, rsiLow: 30, rsiHigh: 70, barLimit: 500, outcomeHorizon: 3, developmentRatio: 0.7, walkForwardWindows: 3, costSpreadBps: 2, costCommissionBps: 1, costSlippageBps: 1, costLatencyBps: 0.5, adverseCostMultiplier: 1.5, stressCostMultiplier: 2.5 });
  const [result, setResult] = useState<StrategyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    const params = new URLSearchParams({ timeframe: query.timeframe, ema_period: String(query.emaPeriod), rsi_period: String(query.rsiPeriod), rsi_low: String(query.rsiLow), rsi_high: String(query.rsiHigh), bar_limit: String(query.barLimit), outcome_horizon: String(query.outcomeHorizon), development_ratio: String(query.developmentRatio), walk_forward_windows: String(query.walkForwardWindows), cost_spread_bps: String(query.costSpreadBps), cost_commission_bps: String(query.costCommissionBps), cost_slippage_bps: String(query.costSlippageBps), cost_latency_bps: String(query.costLatencyBps), adverse_cost_multiplier: String(query.adverseCostMultiplier), stress_cost_multiplier: String(query.stressCostMultiplier) });
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
      const next = { timeframe, emaPeriod, rsiPeriod, rsiLow, rsiHigh, barLimit, outcomeHorizon, developmentRatio, walkForwardWindows, costSpreadBps, costCommissionBps, costSlippageBps, costLatencyBps, adverseCostMultiplier, stressCostMultiplier };
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
      <label>İnkişaf / yoxlama<select value={developmentRatio} onChange={(event) => setDevelopmentRatio(Number(event.target.value))}><option value="0.6">60% / 40%</option><option value="0.7">70% / 30%</option><option value="0.8">80% / 20%</option></select></label>
      <label>Sabitlik pəncərəsi<select value={walkForwardWindows} onChange={(event) => setWalkForwardWindows(Number(event.target.value))}><option value="2">2 pəncərə</option><option value="3">3 pəncərə</option><option value="4">4 pəncərə</option><option value="5">5 pəncərə</option></select></label>
      <div className="cost-control-heading"><strong>Xərc fərziyyəsi</strong><span>Vahid: basis point (bps). Broker faktı deyil.</span></div>
      <label>Spread (bps)<input type="number" min="0" max="1000" step="0.1" value={costSpreadBps} onChange={(event) => setCostSpreadBps(Number(event.target.value))} /></label>
      <label>Komissiya (bps)<input type="number" min="0" max="1000" step="0.1" value={costCommissionBps} onChange={(event) => setCostCommissionBps(Number(event.target.value))} /></label>
      <label>Slippage (bps)<input type="number" min="0" max="1000" step="0.1" value={costSlippageBps} onChange={(event) => setCostSlippageBps(Number(event.target.value))} /></label>
      <label>Gecikmə təsiri (bps)<input type="number" min="0" max="1000" step="0.1" value={costLatencyBps} onChange={(event) => setCostLatencyBps(Number(event.target.value))} /></label>
      <label>Pis ssenari əmsalı<input type="number" min="1" max="10" step="0.1" value={adverseCostMultiplier} onChange={(event) => setAdverseCostMultiplier(Number(event.target.value))} /></label>
      <label>Stress ssenarisi əmsalı<input type="number" min="1" max="10" step="0.1" value={stressCostMultiplier} onChange={(event) => setStressCostMultiplier(Number(event.target.value))} /></label>
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
        <div className="walk-forward-block">
          <div className="walk-forward-heading"><div><p className="eyebrow">Xronoloji walk-forward · qarışdırma yoxdur</p><h5>İnkişaf və toxunulmamış yoxlama</h5></div><span className={strategy.walk_forward_evaluation.status === "ready" ? "analysis-badge ready" : "analysis-badge warmup"}>{strategy.walk_forward_evaluation.status === "ready" ? "Müqayisəyə hazır" : "Məlumat azdır"}</span></div>
          <p className="strategy-explanation">Parametrlər inkişaf konfiqurasiyasından gəlir. Yoxlama hissəsi onları seçmək üçün istifadə edilmir; sərhədi keçən gələcək nəticələr inkişaf hesabından çıxarılır.</p>
          <div className="walk-forward-grid">
            {([strategy.walk_forward_evaluation.development, strategy.walk_forward_evaluation.validation] as WalkForwardWindow[]).map((window) => <section key={window.window} className="walk-forward-window">
              <div className="walk-forward-window-title"><strong>{window.window === "development" ? `İnkişaf · ${(strategy.walk_forward_evaluation.manifest.development_ratio * 100).toFixed(0)}%` : `Yoxlama · ${((1 - strategy.walk_forward_evaluation.manifest.development_ratio) * 100).toFixed(0)}%`}</strong><span>{window.total_observations} müşahidə</span></div>
              <div className="strategy-summary"><div><span>Ölçülmüş</span><strong>{window.matured}</strong></div><div><span>Orta dəyişiklik</span><strong>{window.mean_return_percent === null ? "—" : `${window.mean_return_percent.toFixed(3)}%`}</strong></div><div><span>Yuxarı / aşağı</span><strong>{window.up} / {window.down}</strong></div></div>
              <p className="walk-forward-note">Yetkinləşməyən: {window.immature} · tətbiq olunmayan: {window.not_applicable}{window.boundary_excluded ? ` · sərhəddən çıxarılan: ${window.boundary_excluded}` : ""}</p>
            </section>)}
          </div>
          <p className="walk-forward-warning">Bu müqayisə komissiya, spread, slippage və risk daxil olmayan tarixi qiymət dəyişməsidir; mənfəət vəd etmir.</p>
        </div>
        <div className="stability-block">
          <div className="walk-forward-heading"><div><p className="eyebrow">Çoxpəncərəli sabitlik · gələcək məlumat yoxdur</p><h5>Ardıcıl yoxlama pəncərələri</h5></div><span className={strategy.multi_window_evaluation.status === "ready" ? "analysis-badge ready" : "analysis-badge warmup"}>{strategy.multi_window_evaluation.status === "ready" ? `${strategy.multi_window_evaluation.summary.completed_windows} pəncərə hazırdır` : "Məlumat azdır"}</span></div>
          <p className="strategy-explanation">Hər pəncərədə inkişaf məlumatı yalnız həmin tarixə qədər genişlənir. Sonrakı yoxlama hissələri üst-üstə düşmür və qarışdırılmır.</p>
          <div className="stability-overview">
            <div><span>Müsbət / mənfi / düz</span><strong>{strategy.multi_window_evaluation.summary.positive_windows} / {strategy.multi_window_evaluation.summary.negative_windows} / {strategy.multi_window_evaluation.summary.flat_windows}</strong></div>
            <div><span>Ölçülmüş yoxlama</span><strong>{strategy.multi_window_evaluation.summary.matured_validation_observations}</strong></div>
            <div><span>Çəkili orta dəyişiklik</span><strong>{strategy.multi_window_evaluation.summary.weighted_mean_return_percent === null ? "—" : `${strategy.multi_window_evaluation.summary.weighted_mean_return_percent.toFixed(3)}%`}</strong></div>
            <div><span>Pəncərələrarası aralıq</span><strong>{strategy.multi_window_evaluation.summary.return_range_percentage_points === null ? "—" : `${strategy.multi_window_evaluation.summary.return_range_percentage_points.toFixed(3)} bənd`}</strong></div>
          </div>
          <div className="stability-windows">
            {strategy.multi_window_evaluation.windows.map((window) => {
              const mean = window.validation.mean_return_percent;
              const tone = mean === null ? "neutral" : mean > 0 ? "positive" : mean < 0 ? "negative" : "neutral";
              return <section className={`stability-window ${tone}`} key={window.window_number}>
                <div className="stability-window-head"><span>Pəncərə {window.window_number}</span><strong>{mean === null ? "Nəticə yetişməyib" : `${mean >= 0 ? "+" : ""}${mean.toFixed(3)}%`}</strong></div>
                <p>{window.validation.start_bar_end_at ?? "—"}<br />{window.validation.end_bar_end_at ?? "—"}</p>
                <div className="stability-window-counts"><span>{window.validation.matured} ölçülüb</span><span>{window.validation.up} yuxarı · {window.validation.down} aşağı</span></div>
                <small>İnkişaf: {window.development.total_observations} bar · sərhəddən çıxarılan: {window.development.boundary_excluded}</small>
              </section>;
            })}
          </div>
          <p className="walk-forward-warning">Bu göstəricilər yalnız zaman üzrə tarixi sabitliyi təsvir edir. Komissiya, spread, slippage və risk nəzərə alınmır; nəticə siqnal və ya ticarət əmri deyil.</p>
        </div>
        <details><summary>Versiya və hesablama izi</summary><dl><div><dt>Modul</dt><dd>{strategy.definition.strategy_id}</dd></div><div><dt>Tələb olunan xüsusiyyət</dt><dd>{strategy.definition.required_features.join(", ")}</dd></div><div><dt>Nəticə izi</dt><dd title={strategy.fingerprint}>{strategy.fingerprint.slice(0, 22)}…</dd></div><div><dt>Bar izi</dt><dd title={strategy.bar_fingerprint}>{strategy.bar_fingerprint.slice(0, 22)}…</dd></div></dl></details>
        <div className="cost-scenario-block">
          <div className="walk-forward-heading"><div><p className="eyebrow">Xərc və stress ssenariləri · tədqiqat fərziyyəsi</p><h5>Xam və xərc çıxılmış tarixi dəyişiklik</h5></div><span className="analysis-badge warmup">v{strategy.cost_scenario_evaluation.definition.version}</span></div>
          <p className="strategy-explanation">Xam nəticə dəyişdirilmir. Rəqəmlər hər ölçülmüş müşahidədən seçdiyiniz xərc fərziyyəsini çıxır. Bunlar brokerdən təsdiqlənmiş real tarif deyil.</p>
          <div className="cost-scenario-grid">{strategy.cost_scenario_evaluation.scenarios.map((scenario) => {
            const labels = { normal: "Normal", adverse: "Pis", stress: "Stress" };
            const raw = scenario.summary.raw_weighted_mean_return_percent;
            const net = scenario.summary.net_weighted_mean_return_percent;
            return <section className={`cost-scenario-card ${scenario.assumption.scenario}`} key={scenario.assumption.scenario}>
              <div className="cost-scenario-title"><strong>{labels[scenario.assumption.scenario]} ssenarisi</strong><span>×{scenario.assumption.multiplier.toFixed(1)}</span></div>
              <div className="cost-result-pair"><div><span>Xam orta</span><strong>{raw === null ? "—" : `${raw >= 0 ? "+" : ""}${raw.toFixed(3)}%`}</strong></div><div><span>Xərcdən sonra</span><strong>{net === null ? "—" : `${net >= 0 ? "+" : ""}${net.toFixed(3)}%`}</strong></div></div>
              <p>Hər müşahidəyə xərc: <strong>{scenario.assumption.total_cost_bps.toFixed(2)} bps</strong> ({scenario.assumption.total_cost_percent.toFixed(3)}%)</p>
              <p>Əhatə: <strong>{scenario.summary.matured_observations} / {scenario.summary.total_validation_observations}</strong> · {scenario.summary.coverage_percent.toFixed(1)}%</p>
              <details><summary>Fərziyyənin tərkibi</summary><ul><li>Spread: {scenario.assumption.spread_bps.toFixed(2)} bps</li><li>Komissiya: {scenario.assumption.commission_bps.toFixed(2)} bps</li><li>Slippage: {scenario.assumption.slippage_bps.toFixed(2)} bps</li><li>Gecikmə: {scenario.assumption.latency_bps.toFixed(2)} bps</li></ul></details>
            </section>;
          })}</div>
          <p className="cost-warning"><strong>Vacib:</strong> “Xərcdən sonra” göstəricisi ticarət mənfəəti deyil; yalnız tarixi qiymət dəyişikliklərinə tətbiq olunan model fərziyyəsidir. Siqnal, risk icazəsi və order yaratmır.</p>
        </div>
        <div className="reliability-block">
          <div className="walk-forward-heading"><div><p className="eyebrow">Statistik etibarlılıq · sıfır baza ilə müqayisə</p><h5>Sübutun yetərlilik yoxlaması</h5></div><span className={`analysis-badge ${strategy.statistical_reliability_evaluation.overall_status === "supportive_evidence" ? "ready" : "warmup"}`}>{strategy.statistical_reliability_evaluation.overall_status === "supportive_evidence" ? "Sübut yetərlidir" : "Sübut yetərli deyil"}</span></div>
          <p className="strategy-explanation">Yalnız gələcək yoxlama hissəsi istifadə edilir. Üst-üstə düşən nəticələr ayrıca sübut sayılmır. Ən azı {strategy.statistical_reliability_evaluation.manifest.minimum_effective_sample_size} müşahidə və 95% etibar aralığının sıfırdan yuxarı olması tələb olunur.</p>
          <div className="reliability-grid">{strategy.statistical_reliability_evaluation.scenarios.map((scenario) => {
            const labels = { normal: "Normal", adverse: "Pis", stress: "Stress" };
            const enough = scenario.status === "supportive_evidence";
            return <section className={`reliability-card ${enough ? "supportive" : "insufficient"}`} key={scenario.scenario}>
              <div className="reliability-title"><strong>{labels[scenario.scenario]}</strong><span>{enough ? "Sübut yetərlidir" : "Sübut yetərli deyil"}</span></div>
              <div className="reliability-numbers"><div><span>Effektiv nümunə</span><strong>{scenario.effective_sample_size}</strong></div><div><span>Orta nəticə</span><strong>{scenario.observed_mean_percent === null ? "—" : `${scenario.observed_mean_percent >= 0 ? "+" : ""}${scenario.observed_mean_percent.toFixed(3)}%`}</strong></div></div>
              <p>95% etibar aralığı: <strong>{scenario.confidence_interval_low_percent === null || scenario.confidence_interval_high_percent === null ? "hesablamaq üçün məlumat azdır" : `${scenario.confidence_interval_low_percent.toFixed(3)}% — ${scenario.confidence_interval_high_percent.toFixed(3)}%`}</strong></p>
              <p>Təsir ölçüsü: <strong>{scenario.standardized_effect_size === null ? "—" : scenario.standardized_effect_size.toFixed(3)}</strong></p>
            </section>;
          })}</div>
          <p className="cost-warning"><strong>Şərh:</strong> “Sübut yetərlidir” yalnız seçilmiş tarixi məlumat və əvvəlcədən müəyyən edilmiş statistik qayda üçündür. Bu, gələcək gəlir zəmanəti, alqı-satqı siqnalı və ya əməliyyat icazəsi deyil.</p>
        </div>
      </article>;
    })}</div>}
    <p className="strategy-disclaimer"><strong>Təhlükəsizlik sərhədi:</strong> Bu laboratoriya alış/satış qərarı vermir, mövqe ölçüsü hesablamır və ticarət əməliyyatı açmır.</p>
  </section>;
}
