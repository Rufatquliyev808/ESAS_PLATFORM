"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";

type Timeframe = "M1" | "M5" | "M15" | "H1";
type IndicatorPoint = { bar_end_at: string; status: "ready" | "insufficient_data"; value: number | null };
type IndicatorSeries = { feature_id: string; version: string; period: number; unit: string; points: IndicatorPoint[] };
type AnalysisBar = {
  start_at: string;
  end_at: string;
  open: number;
  high: number;
  low: number;
  close: number;
  tick_count: number;
  tick_volume: number;
};
type StructurePivot = { kind: "high" | "low"; classification: string; value: number; pivot_bar_end_at: string; confirmed_at: string };
type StructureSide = { side: "long" | "short"; state: string; latest_high: string | null; latest_low: string | null; observed_at: string | null };
type MarketStructure = { version: string; pivot_left: number; pivot_right: number; equality_tolerance_bps: number; warmup_bars: number; pivots: StructurePivot[]; long_observation: StructureSide; short_observation: StructureSide; fingerprint: string };
type LiquidityPool = { side: "buy_side" | "sell_side"; level: number; touch_count: number; available_at: string };
type LiquidityObservation = { direction: "bullish" | "bearish"; state: string; pool_side: string; pool_level: number | null; pool_touch_count: number; observed_at: string | null; excursion_bps: number | null; close_back_confirmed: boolean };
type LiquiditySweep = { version: string; pool_tolerance_bps: number; minimum_touches: number; minimum_sweep_bps: number; maximum_pool_age_bars: number; pools: LiquidityPool[]; bullish_observation: LiquidityObservation; bearish_observation: LiquidityObservation; fingerprint: string };
type StructureBreakObservation = { direction: "bullish" | "bearish"; state: string; break_type: string | null; broken_pivot_kind: string | null; broken_pivot_classification: string | null; level: number | null; pivot_confirmed_at: string | null; observed_at: string | null; close_distance_bps: number | null };
type BosChoch = { version: string; minimum_close_break_bps: number; maximum_pivot_age_bars: number; observations: StructureBreakObservation[]; bullish_observation: StructureBreakObservation; bearish_observation: StructureBreakObservation; fingerprint: string };
type RetestObservation = { direction: "bullish" | "bearish"; state: string; break_type: string | null; level: number | null; break_observed_at: string | null; touched_at: string | null; observed_at: string | null; close_distance_bps: number | null };
type Retest = { version: string; touch_tolerance_bps: number; confirmation_close_bps: number; invalidation_close_bps: number; maximum_retest_age_bars: number; observations: RetestObservation[]; bullish_observation: RetestObservation; bearish_observation: RetestObservation; fingerprint: string };
type FvgObservation = { direction: "bullish" | "bearish"; state: string; lower_bound: number | null; upper_bound: number | null; gap_bps: number | null; formed_at: string | null; first_touched_at: string | null; observed_at: string | null; fill_percent: number };
type FairValueGap = { version: string; minimum_gap_bps: number; observations: FvgObservation[]; bullish_observation: FvgObservation; bearish_observation: FvgObservation; fingerprint: string };
type AnalysisResult = {
  session_id: string;
  symbol: string;
  timeframe: Timeframe;
  parameters: { ema_period: number; rsi_period: number; atr_period: number; bar_limit: number };
  lineage: {
    replay_contract_version: string;
    dataset_tick_count: number;
    dataset_fingerprint: string;
    dataset_fingerprint_version: string;
    bar_count: number;
    bar_builder_version: string;
    bar_fingerprint: string;
    indicator_package_version: string;
    indicator_fingerprint: string;
    liquidity_sweep_version?: string;
    liquidity_sweep_fingerprint?: string;
    bos_choch_version?: string;
    bos_choch_fingerprint?: string;
    retest_version?: string;
    retest_fingerprint?: string;
    fair_value_gap_version?: string;
    fair_value_gap_fingerprint?: string;
  };
  bars: AnalysisBar[];
  indicators: { ema: IndicatorSeries; rsi: IndicatorSeries; atr: IndicatorSeries };
  market_structure?: MarketStructure;
  liquidity_sweep?: LiquiditySweep;
  bos_choch?: BosChoch;
  retest?: Retest;
  fair_value_gap?: FairValueGap;
  interpretation: string;
  api_version: string;
};
type Envelope<T> = { data: T };

function formatNumber(value: number | null | undefined, digits = 3) {
  return value == null ? "—" : new Intl.NumberFormat("az-AZ", { maximumFractionDigits: digits }).format(value);
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("az-AZ", { dateStyle: "short", timeStyle: "short" }).format(new Date(value));
}

function linePath(values: Array<number | null>, width: number, height: number, minValue?: number, maxValue?: number) {
  const finite = values.filter((value): value is number => value != null && Number.isFinite(value));
  if (!finite.length) return "";
  const minimum = minValue ?? Math.min(...finite);
  const maximum = maxValue ?? Math.max(...finite);
  const range = maximum - minimum || 1;
  let drawing = false;
  return values.map((value, index) => {
    if (value == null || !Number.isFinite(value)) { drawing = false; return ""; }
    const x = values.length === 1 ? width / 2 : index / (values.length - 1) * width;
    const y = height - ((value - minimum) / range) * height;
    const command = drawing ? "L" : "M";
    drawing = true;
    return `${command}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

function WarmupBadge({ series }: { series: IndicatorSeries }) {
  const count = series.points.filter((point) => point.status === "insufficient_data").length;
  return count ? <span className="analysis-badge warmup">{count} warm-up nöqtəsi</span> : <span className="analysis-badge ready">Tam hazırdır</span>;
}

function EmptyChart({ children }: { children: React.ReactNode }) {
  return <div className="analysis-empty">{children}</div>;
}

function PriceChart({ bars, ema }: { bars: AnalysisBar[]; ema: IndicatorSeries }) {
  const closes = bars.map((bar) => bar.close);
  const emaValues = ema.points.map((point) => point.value);
  const ready = emaValues.filter((value): value is number => value != null);
  const allValues = [...closes, ...ready];
  const minimum = Math.min(...allValues);
  const maximum = Math.max(...allValues);
  const closePath = linePath(closes, 760, 230, minimum, maximum);
  const emaPath = linePath(emaValues, 760, 230, minimum, maximum);
  return (
    <article className="analysis-card price-card">
      <header><div><p className="eyebrow">Qiymət qrafiki</p><h4>Bağlanış qiyməti və EMA {ema.period}</h4></div><WarmupBadge series={ema} /></header>
      {!bars.length ? <EmptyChart>Seçilmiş interval üçün bağlanmış bar yoxdur.</EmptyChart> : <>
        <div className="chart-legend"><span className="close-key">Bağlanış</span><span className="ema-key">EMA</span><strong>Son: {formatNumber(closes.at(-1), 5)}</strong></div>
        <svg className="analysis-chart" viewBox="-10 -10 780 250" role="img" aria-label="Bağlanış qiyməti və EMA xətti">
          <path className="chart-grid" d="M0 0H760 M0 57.5H760 M0 115H760 M0 172.5H760 M0 230H760" />
          <path className="close-line" d={closePath} />
          {emaPath && <path className="ema-line" d={emaPath} />}
        </svg>
        <div className="chart-range"><span>{formatTime(bars[0].end_at)}</span><span>{formatTime(bars.at(-1)!.end_at)}</span></div>
      </>}
    </article>
  );
}

function RsiChart({ series }: { series: IndicatorSeries }) {
  const values = series.points.map((point) => point.value);
  const last = [...values].reverse().find((value) => value != null);
  return (
    <article className="analysis-card">
      <header><div><p className="eyebrow">Momentum</p><h4>RSI {series.period}</h4></div><WarmupBadge series={series} /></header>
      {!values.some((value) => value != null) ? <EmptyChart>RSI üçün hələ kifayət qədər bağlanmış bar yoxdur.</EmptyChart> : <>
        <div className="indicator-value"><strong>{formatNumber(last, 2)}</strong><span>0–100 diapazonu · 30/70 istinad hədləri</span></div>
        <svg className="analysis-chart compact" viewBox="-10 -10 780 170" role="img" aria-label="RSI göstəricisi">
          <rect className="rsi-zone" x="0" y="45" width="760" height="60" />
          <path className="chart-grid dashed" d="M0 45H760 M0 105H760" />
          <path className="rsi-line" d={linePath(values, 760, 150, 0, 100)} />
        </svg>
        <div className="chart-range"><span>70 — yüksək zona</span><span>30 — aşağı zona</span></div>
      </>}
    </article>
  );
}

function AtrChart({ series }: { series: IndicatorSeries }) {
  const values = series.points.map((point) => point.value);
  const last = [...values].reverse().find((value) => value != null);
  return (
    <article className="analysis-card">
      <header><div><p className="eyebrow">Dəyişkənlik</p><h4>ATR {series.period}</h4></div><WarmupBadge series={series} /></header>
      {!values.some((value) => value != null) ? <EmptyChart>ATR üçün hələ kifayət qədər bağlanmış bar yoxdur.</EmptyChart> : <>
        <div className="indicator-value"><strong>{formatNumber(last, 5)}</strong><span>{series.unit || "qiymət vahidi"}</span></div>
        <svg className="analysis-chart compact" viewBox="-10 -10 780 170" role="img" aria-label="ATR göstəricisi">
          <path className="chart-grid" d="M0 0H760 M0 50H760 M0 100H760 M0 150H760" />
          <path className="atr-line" d={linePath(values, 760, 150)} />
        </svg>
      </>}
    </article>
  );
}

function Fingerprint({ label, value }: { label: string; value?: string }) {
  return <div><dt>{label}</dt><dd title={value}>{value ? `${value.slice(0, 12)}…${value.slice(-8)}` : "—"}</dd></div>;
}

function StructurePanel({ structure }: { structure: MarketStructure }) {
  const recent = (structure.pivots ?? []).slice(-8).reverse();
  const labels: Record<string, string> = { confirmed_structure: "Uyğun struktur", conflicting: "Zidd struktur", partial: "Qismən formalaşıb", neutral: "Neytral", insufficient_data: "Məlumat azdır" };
  return <article className="analysis-card structure-card">
    <header><div><p className="eyebrow">Bazar strukturu · araşdırma müşahidəsi</p><h4>HH/HL və LH/LL detektoru</h4></div><span className="analysis-badge ready">Versiya {structure.version}</span></header>
    <p>Dönüş yalnız sağdakı {structure.pivot_right} bar bağlandıqdan sonra təsdiqlənir; gələcək məlumat istifadə edilmir.</p>
    <div className="structure-sides">{[structure.long_observation, structure.short_observation].map((side) => <section key={side.side} className={`structure-side ${side.side}`}><span>{side.side === "long" ? "YÜKSƏLİŞ MÜŞAHİDƏSİ" : "ENİŞ MÜŞAHİDƏSİ"}</span><strong>{labels[side.state] ?? side.state}</strong><small>Son təpə: {side.latest_high ?? "—"} · Son dib: {side.latest_low ?? "—"}</small></section>)}</div>
    <div className="structure-meta">Qayda: {structure.pivot_left} sol / {structure.pivot_right} sağ bar · Bərabərlik həddi: {structure.equality_tolerance_bps} bps · Warm-up: {structure.warmup_bars} bar</div>
    {recent.length ? <div className="structure-pivots">{recent.map((pivot, index) => <div key={`${pivot.confirmed_at}-${pivot.kind}-${index}`}><b>{pivot.classification}</b><span>{formatNumber(pivot.value, 5)}</span><small>{formatTime(pivot.confirmed_at)} tarixində təsdiq</small></div>)}</div> : <EmptyChart>Hələ təsdiqlənmiş dönüş nöqtəsi yoxdur.</EmptyChart>}
  </article>;
}

function CompatibilityNotice({ layer }: { layer: string }) {
  return <article className="analysis-card analysis-error" role="status">
    <strong>{layer} hələ göstərilmir</strong>
    <p>Backend köhnə analiz formatı qaytarıb. Backend-i yenidən başladıb analizi yeniləyin.</p>
  </article>;
}

function LiquidityPanel({ liquidity }: { liquidity: LiquiditySweep }) {
  const labels: Record<string, string> = { confirmed_sweep: "Təsdiqlənmiş süpürmə", no_sweep: "Süpürmə yoxdur", insufficient_data: "Məlumat azdır", conflicting: "Zidd müşahidə" };
  const observations = [liquidity.bullish_observation, liquidity.bearish_observation];
  return <article className="analysis-card liquidity-card">
    <header><div><p className="eyebrow">Likvidlik · araşdırma müşahidəsi</p><h4>Bərabər təpə/dib və fitil süpürməsi</h4></div><span className="analysis-badge ready">Versiya {liquidity.version}</span></header>
    <p>Hovuz əvvəlcədən təsdiqlənmiş dönüşlərdən qurulur. Süpürmə yalnız bağlanmış bar səviyyənin o tərəfinə keçib geri bağlandıqda qeydə alınır.</p>
    <div className="liquidity-sides">{observations.map((item) => <section key={item.direction} className={`liquidity-side ${item.direction}`}>
      <span>{item.direction === "bullish" ? "YÜKSƏLİŞ MÜŞAHİDƏSİ" : "ENİŞ MÜŞAHİDƏSİ"}</span>
      <strong>{labels[item.state] ?? item.state}</strong>
      <small>Səviyyə: {formatNumber(item.pool_level, 5)} · Toxunuş: {item.pool_touch_count || "—"}</small>
      <small>Fitil məsafəsi: {formatNumber(item.excursion_bps, 2)} bps · {item.observed_at ? formatTime(item.observed_at) : "vaxt yoxdur"}</small>
    </section>)}</div>
    <div className="liquidity-meta">Hovuzlar: {liquidity.pools.length} · Dözümlülük: {liquidity.pool_tolerance_bps} bps · Minimum toxunuş: {liquidity.minimum_touches} · Minimum süpürmə: {liquidity.minimum_sweep_bps} bps</div>
    {liquidity.pools.length ? <div className="liquidity-pools">{liquidity.pools.slice(-6).reverse().map((pool, index) => <div key={`${pool.side}-${pool.available_at}-${index}`}><b>{pool.side === "buy_side" ? "Təpə hovuzu" : "Dib hovuzu"}</b><span>{formatNumber(pool.level, 5)}</span><small>{pool.touch_count} toxunuş · {formatTime(pool.available_at)} tarixindən məlumdur</small></div>)}</div> : <EmptyChart>Hələ minimum toxunuş sayına çatan likvidlik hovuzu yoxdur.</EmptyChart>}
    <p className="liquidity-boundary">Bu nəticə siqnal, giriş və ya əməliyyat əmri deyil.</p>
  </article>;
}

function BosChochPanel({ result }: { result: BosChoch }) {
  const labels: Record<string, string> = {
    confirmed_bos: "BOS təsdiqlənib",
    confirmed_choch: "CHoCH təsdiqlənib",
    unclassified_break: "Struktur rejimi qeyri-müəyyəndir",
    no_break: "Qırılma yoxdur",
    insufficient_data: "Məlumat azdır",
    conflicting: "Eyni barda zidd qırılma",
  };
  return <article className="analysis-card bos-choch-card">
    <header><div><p className="eyebrow">Struktur qırılması · araşdırma müşahidəsi</p><h4>BOS və CHoCH detektoru</h4></div><span className="analysis-badge ready">Versiya {result.version}</span></header>
    <p>BOS mövcud strukturun davamını, CHoCH isə mümkün istiqamət dəyişikliyini təsvir edir. Qırılma yalnız pivot təsdiqləndikdən sonra bağlanmış barın qiyməti ilə qeydə alınır.</p>
    <div className="bos-choch-sides">{[result.bullish_observation, result.bearish_observation].map((item) => <section key={item.direction} className={`bos-choch-side ${item.direction}`}>
      <span>{item.direction === "bullish" ? "YÜKSƏLİŞ QIRILMASI" : "ENİŞ QIRILMASI"}</span>
      <strong>{labels[item.state] ?? item.state}</strong>
      <small>Növ: {item.break_type ?? "—"} · Səviyyə: {formatNumber(item.level, 5)}</small>
      <small>Bağlanış məsafəsi: {formatNumber(item.close_distance_bps, 2)} bps · {item.observed_at ? formatTime(item.observed_at) : "vaxt yoxdur"}</small>
    </section>)}</div>
    <div className="bos-choch-meta">Təsdiqlənmiş müşahidələr: {result.observations.length} · Minimum bağlanış məsafəsi: {result.minimum_close_break_bps} bps · Pivot ömrü: {result.maximum_pivot_age_bars} bar</div>
    <p className="liquidity-boundary">Bu nəticə siqnal, giriş, risk qərarı və ya əməliyyat əmri deyil.</p>
  </article>;
}

function RetestPanel({ result }: { result: Retest }) {
  const labels: Record<string, string> = {
    confirmed_retest: "Retest təsdiqlənib",
    unconfirmed_retest: "Toxunuş var, bağlanış təsdiqi yoxdur",
    invalidated: "Səviyyə etibarsızlaşıb",
    no_retest: "Retest müşahidə edilməyib",
    insufficient_data: "Məlumat azdır",
    conflicting: "Zidd retest müşahidəsi",
  };
  const observations = [result.bullish_observation, result.bearish_observation];
  return <article className="analysis-card bos-choch-card">
    <header><div><p className="eyebrow">Səbəbli retest · araşdırma müşahidəsi</p><h4>Qırılmış səviyyəyə geri dönüş</h4></div><span className="analysis-badge ready">Versiya {result.version}</span></header>
    <p>Yalnız BOS/CHoCH qırılmasından sonra bağlanan barlar yoxlanılır. Gələcək məlumat hesablamaya daxil edilmir.</p>
    <div className="liquidity-sides">{observations.map((item) => <section key={item.direction} className={`liquidity-side ${item.direction}`}>
      <span>{item.direction === "bullish" ? "YÜKSƏLİŞ RETESTİ" : "ENİŞ RETESTİ"}</span>
      <strong>{labels[item.state] ?? item.state}</strong>
      <small>Səviyyə: {formatNumber(item.level, 5)} · Qırılma: {item.break_observed_at ? formatTime(item.break_observed_at) : "—"}</small>
      <small>Toxunuş: {item.touched_at ? formatTime(item.touched_at) : "—"} · Bağlanış məsafəsi: {formatNumber(item.close_distance_bps, 2)} bps</small>
    </section>)}</div>
    <div className="bos-choch-meta">Toxunuş dözümlülüyü: {result.touch_tolerance_bps} bps · Etibarsızlaşma: {result.invalidation_close_bps} bps · Maksimum yaş: {result.maximum_retest_age_bars} bar</div>
    <p className="liquidity-boundary">Bu nəticə strategiya, siqnal, giriş və ya əməliyyat əmri deyil.</p>
  </article>;
}

function FvgPanel({ result }: { result: FairValueGap }) {
  const labels: Record<string, string> = {
    open: "Boşluq açıqdır",
    partially_filled: "Qismən doldurulub",
    filled: "Tamamilə doldurulub",
    invalidated: "Boşluq etibarsızlaşıb",
    no_gap: "Boşluq müşahidə edilməyib",
    insufficient_data: "Məlumat azdır",
  };
  const observations = [result.bullish_observation, result.bearish_observation];
  return <article className="analysis-card bos-choch-card">
    <header><div><p className="eyebrow">Fair Value Gap · araşdırma müşahidəsi</p><h4>Qiymət boşluğu və doldurulması</h4></div><span className="analysis-badge ready">Versiya {result.version}</span></header>
    <p>Boşluq yalnız üç ardıcıl bağlanmış bar arasında yaranır. Doldurulma vəziyyəti yalnız sonrakı bağlanmış barlarla yenilənir; gələcək məlumat boşluğun yaranmasına təsir etmir.</p>
    <div className="liquidity-sides">{observations.map((item) => <section key={item.direction} className={`liquidity-side ${item.direction}`}>
      <span>{item.direction === "bullish" ? "YÜKSƏLİŞ BOŞLUĞU" : "ENİŞ BOŞLUĞU"}</span>
      <strong>{labels[item.state] ?? item.state}</strong>
      <small>Aralıq: {formatNumber(item.lower_bound, 5)} — {formatNumber(item.upper_bound, 5)} · {formatNumber(item.gap_bps, 2)} bps</small>
      <small>Doldurulma: {formatNumber(item.fill_percent, 1)}% · {item.observed_at ? formatTime(item.observed_at) : "vaxt yoxdur"}</small>
    </section>)}</div>
    <div className="bos-choch-meta">Təsdiqlənmiş müşahidələr: {result.observations.length} · Minimum boşluq: {result.minimum_gap_bps} bps</div>
    <p className="liquidity-boundary">Bu nəticə strategiya, siqnal, giriş və ya əməliyyat əmri deyil.</p>
  </article>;
}

type AnalysisView = "technical" | "structure" | "liquidity" | "bos-choch" | "retest" | "fvg";

export function TechnicalAnalysisPanel({ sessionId, symbol, token, onUnauthorized, view }: { sessionId: string; symbol: string; token: string; onUnauthorized: () => void; view: AnalysisView }) {
  const [timeframe, setTimeframe] = useState<Timeframe>("M5");
  const [emaPeriod, setEmaPeriod] = useState(20);
  const [rsiPeriod, setRsiPeriod] = useState(14);
  const [atrPeriod, setAtrPeriod] = useState(14);
  const [barLimit, setBarLimit] = useState(250);
  const [queryConfig, setQueryConfig] = useState({ timeframe: "M5" as Timeframe, emaPeriod: 20, rsiPeriod: 14, atrPeriod: 14, barLimit: 250 });
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    const query = new URLSearchParams({
      timeframe: queryConfig.timeframe,
      ema_period: String(queryConfig.emaPeriod),
      rsi_period: String(queryConfig.rsiPeriod),
      atr_period: String(queryConfig.atrPeriod),
      bar_limit: String(queryConfig.barLimit),
    });
    try {
      const response = await fetch(`${API_BASE}/api/v2/replay-sessions/${sessionId}/technical-analysis?${query}`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Replay məlumatı dəyişib. Sessiyanı yeniləyib analizi yenidən hesablayın.");
      if (!response.ok) throw new Error(`Texniki analiz alına bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Envelope<AnalysisResult>;
      setResult(payload.data);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Texniki analiz alına bilmədi.");
    } finally { setLoading(false); }
  }, [onUnauthorized, queryConfig, sessionId, token]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadAnalysis(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [loadAnalysis]);

  const readyBars = useMemo(() => result?.bars.length ?? 0, [result]);

  return (
    <section className="technical-analysis" aria-labelledby="technical-analysis-title">
      <div className="analysis-heading">
        <div><p className="eyebrow">Araşdırma görünüşü · siqnal deyil</p><h3 id="technical-analysis-title">{symbol} texniki analiz laboratoriyası</h3><p>Yalnız tamamlanmış replay sessiyasının bağlanmış barları hesablanır.</p></div>
        {result && <span className="analysis-badge ready">{readyBars} bar göstərilir</span>}
      </div>

      <form className="analysis-controls" onSubmit={(event) => {
        event.preventDefault();
        const next = { timeframe, emaPeriod, rsiPeriod, atrPeriod, barLimit };
        if (JSON.stringify(next) === JSON.stringify(queryConfig)) void loadAnalysis();
        else setQueryConfig(next);
      }}>
        <label>Vaxt çərçivəsi<select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}><option>M1</option><option>M5</option><option>M15</option><option>H1</option></select></label>
        <label>EMA dövrü<input type="number" min="2" max="500" value={emaPeriod} onChange={(event) => setEmaPeriod(Number(event.target.value))} /></label>
        <label>RSI dövrü<input type="number" min="2" max="500" value={rsiPeriod} onChange={(event) => setRsiPeriod(Number(event.target.value))} /></label>
        <label>ATR dövrü<input type="number" min="2" max="500" value={atrPeriod} onChange={(event) => setAtrPeriod(Number(event.target.value))} /></label>
        <label>Görünən bar<select value={barLimit} onChange={(event) => setBarLimit(Number(event.target.value))}><option value="100">100</option><option value="250">250</option><option value="500">500</option><option value="1000">1 000</option></select></label>
        <button type="submit" disabled={loading}>{loading ? "Hesablanır…" : "Analizi hesabla"}</button>
      </form>

      {error && <div className="analysis-error" role="alert"><strong>Analiz göstərilə bilmədi</strong><span>{error}</span><button type="button" onClick={() => void loadAnalysis()}>Yenidən yoxla</button></div>}
      {loading && !result ? <div className="analysis-loading"><span className="loading-ring" /><div><strong>Bağlanmış barlar hesablanır</strong><p>EMA, RSI və ATR eyni replay məlumatından hazırlanır.</p></div></div> : result && <>
        {view === "technical" && <><PriceChart bars={result.bars} ema={result.indicators.ema} /><div className="indicator-grid"><RsiChart series={result.indicators.rsi} /><AtrChart series={result.indicators.atr} /></div></>}
        {view === "structure" && (result.market_structure ? <StructurePanel structure={result.market_structure} /> : <CompatibilityNotice layer="Bazar strukturu" />)}
        {view === "bos-choch" && (result.bos_choch ? <BosChochPanel result={result.bos_choch} /> : <CompatibilityNotice layer="BOS/CHoCH" />)}
        {view === "retest" && (result.retest ? <RetestPanel result={result.retest} /> : <CompatibilityNotice layer="Retest analizi" />)}
        {view === "fvg" && (result.fair_value_gap ? <FvgPanel result={result.fair_value_gap} /> : <CompatibilityNotice layer="Fair Value Gap analizi" />)}
        {view === "liquidity" && (result.liquidity_sweep ? <LiquidityPanel liquidity={result.liquidity_sweep} /> : <CompatibilityNotice layer="Likvidlik analizi" />)}
        <details className="analysis-lineage">
          <summary>Məlumat mənbəyi və hesablamanın izi</summary>
          <dl>
            <div><dt>Replay müqaviləsi</dt><dd>{result.lineage.replay_contract_version}</dd></div>
            <div><dt>Dataset tick sayı</dt><dd>{formatNumber(result.lineage.dataset_tick_count, 0)}</dd></div>
            <div><dt>Bar sayı / qurucu</dt><dd>{result.lineage.bar_count} / {result.lineage.bar_builder_version}</dd></div>
            <div><dt>İndikator paketi</dt><dd>{result.lineage.indicator_package_version}</dd></div>
            <Fingerprint label="Dataset izi" value={result.lineage.dataset_fingerprint} />
            <Fingerprint label="Bar izi" value={result.lineage.bar_fingerprint} />
            <Fingerprint label="İndikator izi" value={result.lineage.indicator_fingerprint} />
            <Fingerprint label="Likvidlik izi" value={result.lineage.liquidity_sweep_fingerprint} />
            <Fingerprint label="BOS/CHoCH izi" value={result.lineage.bos_choch_fingerprint} />
            <Fingerprint label="Retest izi" value={result.lineage.retest_fingerprint} />
            <Fingerprint label="Fair Value Gap izi" value={result.lineage.fair_value_gap_fingerprint} />
          </dl>
        </details>
        <p className="analysis-disclaimer"><strong>Qeyd:</strong> Bu göstəricilər araşdırma üçündür. Platforma bu mərhələdə alış/satış siqnalı vermir və əməliyyat açmır.</p>
      </>}
    </section>
  );
}
