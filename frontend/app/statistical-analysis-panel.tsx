"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";

type Timeframe = "S1" | "S10" | "M1" | "M5" | "M15" | "M30" | "H1" | "H4" | "D1";
type Status = "completed" | "insufficient_data";

type WindowReturn = { start_at: string; end_at: string; tick_count: number; open_mid: number; close_mid: number; log_return: number };
type ReturnSeries = {
  status: Status; n_total: number; n_valid: number; n_excluded: number;
  count: number | null; mean: number | null; median: number | null; std_dev: number | null;
  minimum: number | null; maximum: number | null; p05: number | null; p95: number | null;
  windows: WindowReturn[];
};

type VolatilityDistribution = {
  status: Status; n_total: number; n_valid: number; count: number | null;
  mean: number | null; median: number | null; std_dev: number | null;
  minimum: number | null; maximum: number | null; p05: number | null; p95: number | null;
};
type Volatility = {
  window_range_absolute: VolatilityDistribution;
  window_range_relative: VolatilityDistribution;
  window_log_return_abs: VolatilityDistribution;
  tick_return: VolatilityDistribution;
  robust_mad_status: Status;
  robust_mad: number | null;
};

type SpreadDistribution = {
  status: Status; n_total: number; n_valid: number; count: number | null;
  mean: number | null; median: number | null; std_dev: number | null;
  minimum: number | null; maximum: number | null;
  p05: number | null; p25: number | null; p75: number | null; p95: number | null; p99: number | null;
};
type Spread = { window_spread_absolute: SpreadDistribution; window_spread_relative_bps: SpreadDistribution };

type RateDistribution = {
  status: Status; n_total: number; n_valid: number;
  mean: number | null; median: number | null; std_dev: number | null;
  minimum: number | null; maximum: number | null; p95: number | null; p99: number | null;
};
type TickRate = {
  total_window_count: number; populated_window_count: number; empty_window_count: number;
  window_tick_count: RateDistribution; window_ticks_per_second: RateDistribution;
  interval_seconds: RateDistribution; same_timestamp_tick_count: number;
};

type FlagCombination = { flags: number; count: number };
type VersionSegment = { module_version: string; event_version: string; count: number };
type TickVolume = {
  n_total: number; n_zero_volume: number; n_positive_volume: number;
  tick_volume: RateDistribution; window_volume_sum: RateDistribution;
  flag_combinations: FlagCombination[]; version_segments: VersionSegment[];
};

type RegimeSummary = {
  regime: string; volatility_tier: string; spread_tier: string; tick_speed_tier: string;
  return_direction: string; observation_count: number; confidence: number;
  first_observed_at: string; last_observed_at: string;
};
type Regimes = {
  status: Status; n_total_windows: number; n_classified_windows: number;
  data_quality_status: string; regimes: RegimeSummary[];
};

type UtcHourBucket = {
  utc_hour: number; status: Status; n_total_windows: number; n_return_windows: number;
  mean_return: number | null; median_return: number | null; return_std_dev: number | null;
  return_confidence_interval_low: number | null; return_confidence_interval_high: number | null;
  mean_range_relative: number | null;
};
type Sessions = { calendar_unavailable: boolean; limitations: string[]; buckets: UtcHourBucket[] };

type StatisticalAnalysis = {
  session_id: string; symbol: string; timeframe: Timeframe;
  lineage: Record<string, string | number>;
  return_series: ReturnSeries;
  volatility: Volatility;
  spread: Spread;
  tick_rate: TickRate;
  tick_volume: TickVolume;
  regimes: Regimes;
  sessions: Sessions;
  interpretation: string;
  api_version: string;
};
type Envelope<T> = { data: T };

const TIER_LABELS: Record<string, string> = { low: "aşağı", high: "yuxarı" };
const DIRECTION_LABELS: Record<string, string> = { up: "yuxarı", down: "aşağı", flat: "dəyişməz", unknown: "naməlum" };
const QUALITY_LABELS: Record<string, string> = { pass: "keçdi", review: "nəzərdən keçirilməli", fail: "uğursuz" };

function fmt(value: number | null | undefined, digits = 5): string {
  return value == null || !Number.isFinite(value) ? "—" : new Intl.NumberFormat("az-AZ", { maximumFractionDigits: digits }).format(value);
}

function StatusBadge({ status }: { status: Status }) {
  return <span className={`analysis-badge ${status === "completed" ? "ready" : "warmup"}`}>{status === "completed" ? "Hazırdır" : "Məlumat azdır"}</span>;
}

function DistributionLine({ label, distribution, digits = 5 }: { label: string; distribution: { status: Status; n_valid: number; n_total: number; mean: number | null; median: number | null; std_dev: number | null; minimum: number | null; maximum: number | null }; digits?: number }) {
  return (
    <p className="card-detail">
      <strong>{label}:</strong>{" "}
      {distribution.status === "insufficient_data"
        ? `kifayət qədər nümunə yoxdur (${distribution.n_valid}/${distribution.n_total})`
        : `orta ${fmt(distribution.mean, digits)} · median ${fmt(distribution.median, digits)} · std ${fmt(distribution.std_dev, digits)} · aralıq ${fmt(distribution.minimum, digits)}–${fmt(distribution.maximum, digits)} (n=${distribution.n_valid})`}
    </p>
  );
}

export function StatisticalAnalysisPanel({ sessionId, symbol, token, onUnauthorized }: { sessionId: string; symbol: string; token: string; onUnauthorized: () => void }) {
  const [timeframe, setTimeframe] = useState<Timeframe>("M5");
  const [minimumSampleSize, setMinimumSampleSize] = useState(30);
  const [queryConfig, setQueryConfig] = useState({ timeframe: "M5" as Timeframe, minimumSampleSize: 30 });
  const [result, setResult] = useState<StatisticalAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    const query = new URLSearchParams({
      timeframe: queryConfig.timeframe,
      minimum_sample_size: String(queryConfig.minimumSampleSize),
    });
    try {
      const response = await fetch(`${API_BASE}/api/v2/replay-sessions/${sessionId}/statistical-analysis?${query}`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.status === 401) { onUnauthorized(); throw new Error("Sessiyanın vaxtı bitib. Yenidən daxil olun."); }
      if (response.status === 409) throw new Error("Replay məlumatı dəyişib. Sessiyanı yeniləyib analizi yenidən hesablayın.");
      if (!response.ok) throw new Error(`Statistik analiz alına bilmədi (HTTP ${response.status}).`);
      const payload = await response.json() as Envelope<StatisticalAnalysis>;
      setResult(payload.data);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Statistik analiz alına bilmədi.");
    } finally { setLoading(false); }
  }, [onUnauthorized, queryConfig, sessionId, token]);

  useEffect(() => {
    const initialLoad = window.setTimeout(() => void loadAnalysis(), 0);
    return () => window.clearTimeout(initialLoad);
  }, [loadAnalysis]);

  return (
    <section className="technical-analysis" aria-labelledby="statistical-analysis-title">
      <div className="analysis-heading">
        <div>
          <p className="eyebrow">Araşdırma görünüşü · siqnal deyil</p>
          <h3 id="statistical-analysis-title">{symbol} statistik analiz (Phase 3, SA-001–SA-007)</h3>
          <p>Yalnız tamamlanmış replay sessiyasının bağlanmış barları və xam tick-ləri üzərində hesablanır.</p>
        </div>
        <span className="research-pill">TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL</span>
      </div>

      <form className="analysis-controls" onSubmit={(event) => {
        event.preventDefault();
        const next = { timeframe, minimumSampleSize };
        if (JSON.stringify(next) === JSON.stringify(queryConfig)) void loadAnalysis();
        else setQueryConfig(next);
      }}>
        <label>Vaxt çərçivəsi
          <select value={timeframe} onChange={(event) => setTimeframe(event.target.value as Timeframe)}>
            <option>S1</option><option>S10</option><option>M1</option><option>M5</option><option>M15</option><option>M30</option><option>H1</option><option>H4</option><option>D1</option>
          </select>
        </label>
        <label>Minimum nümunə<input type="number" min="1" max="10000" value={minimumSampleSize} onChange={(event) => setMinimumSampleSize(Number(event.target.value))} /></label>
        <button type="submit" disabled={loading}>{loading ? "Hesablanır…" : "Analizi hesabla"}</button>
      </form>

      {error && <div className="analysis-error" role="alert"><strong>Analiz göstərilə bilmədi</strong><span>{error}</span><button type="button" onClick={() => void loadAnalysis()}>Yenidən yoxla</button></div>}

      {loading && !result ? (
        <div className="analysis-loading"><span className="loading-ring" /><div><strong>Statistik göstəricilər hesablanır</strong><p>Gəlir seriyası, volatilite, spread, tick sürəti, tick-volume, rejim və sessiya müqayisəsi eyni pəncərələrdən hazırlanır.</p></div></div>
      ) : result && <>

        <article className="analysis-card">
          <header><div><p className="eyebrow">SA-001 · Gəlir seriyası</p><h4>Pəncərə log-return-u</h4></div><StatusBadge status={result.return_series.status} /></header>
          <DistributionLine label="Log-return" distribution={result.return_series} digits={6} />
          {result.return_series.status === "completed" && <p className="card-detail">p05–p95 aralığı: {fmt(result.return_series.p05, 6)} — {fmt(result.return_series.p95, 6)}</p>}
        </article>

        <article className="analysis-card">
          <header><div><p className="eyebrow">SA-002 · Volatilite</p><h4>Pəncərə range-i və return dəyişkənliyi</h4></div></header>
          <DistributionLine label="Pəncərə range-i (mütləq)" distribution={result.volatility.window_range_absolute} digits={4} />
          <DistributionLine label="Pəncərə range-i (nisbi)" distribution={result.volatility.window_range_relative} digits={6} />
          <DistributionLine label="|Log-return| (pəncərə)" distribution={result.volatility.window_log_return_abs} digits={6} />
          <DistributionLine label="Tick-to-tick log-return (pəncərəsiz)" distribution={result.volatility.tick_return} digits={6} />
          <p className="card-detail"><strong>Robust MAD:</strong> {result.volatility.robust_mad_status === "completed" ? fmt(result.volatility.robust_mad, 6) : "kifayət qədər nümunə yoxdur"}</p>
        </article>

        <article className="analysis-card">
          <header><div><p className="eyebrow">SA-003 · Spread davranışı</p><h4>Pəncərə orta spread-i</h4></div></header>
          <DistributionLine label="Spread (mütləq)" distribution={result.spread.window_spread_absolute} digits={4} />
          <DistributionLine label="Spread (nisbi, bps)" distribution={result.spread.window_spread_relative_bps} digits={2} />
        </article>

        <article className="analysis-card">
          <header><div><p className="eyebrow">SA-004 · Tick sürəti</p><h4>Pəncərə tick sayı və interval</h4></div></header>
          <p className="card-detail">Pəncərə sayı: {result.tick_rate.populated_window_count} dolu / {result.tick_rate.empty_window_count} boş / {result.tick_rate.total_window_count} cəmi</p>
          <DistributionLine label="Pəncərə tick sayı" distribution={result.tick_rate.window_tick_count} digits={1} />
          <DistributionLine label="Ardıcıl tick intervalı (san)" distribution={result.tick_rate.interval_seconds} digits={3} />
          <p className="card-detail">Eyni-timestamp tick sayı: {result.tick_rate.same_timestamp_tick_count}</p>
        </article>

        <article className="analysis-card">
          <header><div><p className="eyebrow">SA-005 · Tick-volume və flags</p><h4>MT5 tick-volume (real birja həcmi deyil)</h4></div></header>
          <p className="card-detail">Sıfır volume: {result.tick_volume.n_zero_volume} · Müsbət volume: {result.tick_volume.n_positive_volume} (cəmi {result.tick_volume.n_total})</p>
          <DistributionLine label="Volume (tick üzrə)" distribution={result.tick_volume.tick_volume} digits={0} />
          <DistributionLine label="Pəncərə üzrə cəm" distribution={result.tick_volume.window_volume_sum} digits={0} />
          {result.tick_volume.flag_combinations.length > 0 && (
            <div className="table-wrap"><table><thead><tr><th>Flags (xam)</th><th>Say</th></tr></thead>
              <tbody>{result.tick_volume.flag_combinations.map((item) => <tr key={item.flags}><td>{item.flags}</td><td>{item.count}</td></tr>)}</tbody>
            </table></div>
          )}
        </article>

        <article className="analysis-card">
          <header><div><p className="eyebrow">SA-007 · Bazar rejimi namizədləri</p><h4>Neytral, dataset-daxili rejim qrupları</h4></div><StatusBadge status={result.regimes.status} /></header>
          <p className="card-detail">Keyfiyyət statusu: {QUALITY_LABELS[result.regimes.data_quality_status] ?? result.regimes.data_quality_status} · Pəncərə: {result.regimes.n_classified_windows}/{result.regimes.n_total_windows}</p>
          {result.regimes.status === "completed" && (
            <div className="table-wrap"><table>
              <thead><tr><th>Rejim</th><th>Volatilite</th><th>Spread</th><th>Tick sürəti</th><th>İstiqamət</th><th>Say</th><th>Nisbət</th></tr></thead>
              <tbody>{result.regimes.regimes.map((item) => (
                <tr key={item.regime}>
                  <td>{item.regime}</td>
                  <td>{TIER_LABELS[item.volatility_tier] ?? item.volatility_tier}</td>
                  <td>{TIER_LABELS[item.spread_tier] ?? item.spread_tier}</td>
                  <td>{TIER_LABELS[item.tick_speed_tier] ?? item.tick_speed_tier}</td>
                  <td>{DIRECTION_LABELS[item.return_direction] ?? item.return_direction}</td>
                  <td>{item.observation_count}</td>
                  <td>{(item.confidence * 100).toFixed(1)}%</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
          <p className="liquidity-boundary">Rejim adları (&quot;regime_1&quot; və s.) ixtiyaridir, iqtisadi məna daşımır və fərqli analizlər arasında müqayisə edilə bilməz — yalnız bu icra üçün nisbi qruplaşdırmadır.</p>
        </article>

        <article className="analysis-card">
          <header><div><p className="eyebrow">SA-006 · Sessiya müqayisəsi</p><h4>UTC saat qrupları (təqvim-yoxdur rejim)</h4></div></header>
          {result.sessions.limitations.map((limitation) => <p key={limitation} className="card-detail">{limitation}</p>)}
          <div className="table-wrap"><table>
            <thead><tr><th>UTC saat</th><th>Pəncərə</th><th>Orta return</th><th>95% CI</th><th>Orta range (nisbi)</th></tr></thead>
            <tbody>{result.sessions.buckets.map((bucket) => (
              <tr key={bucket.utc_hour}>
                <td>{String(bucket.utc_hour).padStart(2, "0")}:00</td>
                <td>{bucket.n_return_windows}/{bucket.n_total_windows}</td>
                <td>{bucket.status === "completed" ? fmt(bucket.mean_return, 6) : "—"}</td>
                <td>{bucket.status === "completed" ? `${fmt(bucket.return_confidence_interval_low, 6)} — ${fmt(bucket.return_confidence_interval_high, 6)}` : "—"}</td>
                <td>{fmt(bucket.mean_range_relative, 6)}</td>
              </tr>
            ))}</tbody>
          </table></div>
          <p className="liquidity-boundary">Bu, adlandırılmış bazar sessiyası (London/New York və s.) deyil, yalnız xam UTC saatı üzrə qruplaşdırmadır. Qruplar arası fərq avtomatik olaraq ticarət üstünlüyü sayılmır.</p>
        </article>

        <details className="analysis-lineage">
          <summary>Məlumat mənbəyi və hesablamanın izi</summary>
          <dl>
            {Object.entries(result.lineage).filter(([key]) => key.endsWith("_fingerprint")).map(([key, value]) => (
              <div key={key}><dt>{key}</dt><dd title={String(value)}>{String(value).slice(0, 12)}…{String(value).slice(-8)}</dd></div>
            ))}
          </dl>
        </details>
        <p className="analysis-disclaimer"><strong>Qeyd:</strong> Bu göstəricilər araşdırma üçündür. Platforma bu mərhələdə alış/satış siqnalı vermir və əməliyyat açmır.</p>
      </>}
    </section>
  );
}
