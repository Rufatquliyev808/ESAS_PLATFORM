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
  };
  bars: AnalysisBar[];
  indicators: { ema: IndicatorSeries; rsi: IndicatorSeries; atr: IndicatorSeries };
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

function Fingerprint({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd title={value}>{value.slice(0, 12)}…{value.slice(-8)}</dd></div>;
}

export function TechnicalAnalysisPanel({ sessionId, symbol, token, onUnauthorized }: { sessionId: string; symbol: string; token: string; onUnauthorized: () => void }) {
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
        <PriceChart bars={result.bars} ema={result.indicators.ema} />
        <div className="indicator-grid"><RsiChart series={result.indicators.rsi} /><AtrChart series={result.indicators.atr} /></div>
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
          </dl>
        </details>
        <p className="analysis-disclaimer"><strong>Qeyd:</strong> Bu göstəricilər araşdırma üçündür. Platforma bu mərhələdə alış/satış siqnalı vermir və əməliyyat açmır.</p>
      </>}
    </section>
  );
}
