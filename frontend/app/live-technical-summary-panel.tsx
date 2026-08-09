"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";
const REFRESH_INTERVAL_MS = 5000;

type LeanStatus = "bullish_leaning" | "bearish_leaning" | "neutral" | "insufficient_data";
type IndicatorLean = { indicator_id: string; status: LeanStatus; value: number | null; reference: number | null };
type ConsensusSummary = {
  bullish_leaning_count: number;
  bearish_leaning_count: number;
  neutral_count: number;
  insufficient_data_count: number;
  overall_lean: LeanStatus;
};
type IndicatorConsensus = {
  version: string;
  oscillators: IndicatorLean[];
  moving_averages: IndicatorLean[];
  oscillator_summary: ConsensusSummary;
  moving_average_summary: ConsensusSummary;
  overall_summary: ConsensusSummary;
};
type LiveTechnicalSummary = {
  symbol: string;
  timeframe: string;
  generated_at: string;
  consensus: IndicatorConsensus | null;
  lineage: { bar_count: number; reproducible: boolean };
};

const LEAN_LABELS: Record<LeanStatus, string> = {
  bullish_leaning: "Yuxarı meyl",
  bearish_leaning: "Aşağı meyl",
  neutral: "Neytral",
  insufficient_data: "Kifayət qədər məlumat yoxdur",
};

const LEAN_TONE: Record<LeanStatus, string> = {
  bullish_leaning: "good",
  bearish_leaning: "danger",
  neutral: "neutral",
  insufficient_data: "info",
};

const INDICATOR_LABELS: Record<string, string> = {
  rsi: "RSI (14)",
  stochastic_k: "Stochastic %K (14,3)",
  cci: "CCI (20)",
  williams_r: "Williams %R (14)",
  macd: "MACD (12,26,9)",
  adx: "ADX (14)",
};

function indicatorLabel(id: string): string {
  if (id.startsWith("ema.close.")) return `EMA (${id.split(".").pop()})`;
  if (id.startsWith("sma.close.")) return `SMA (${id.split(".").pop()})`;
  return INDICATOR_LABELS[id] ?? id;
}

function GaugeCard({ title, summary }: { title: string; summary: ConsensusSummary }) {
  return (
    <article className="live-consensus-gauge">
      <p className="eyebrow">{title}</p>
      <strong className={`live-consensus-verdict tone-${LEAN_TONE[summary.overall_lean]}`}>
        {LEAN_LABELS[summary.overall_lean]}
      </strong>
      <div className="live-consensus-counts">
        <span>Aşağı meyl: {summary.bearish_leaning_count}</span>
        <span>Neytral: {summary.neutral_count}</span>
        <span>Yuxarı meyl: {summary.bullish_leaning_count}</span>
      </div>
    </article>
  );
}

function IndicatorTable({ title, items }: { title: string; items: IndicatorLean[] }) {
  return (
    <div className="live-consensus-table">
      <p className="eyebrow">{title}</p>
      <table>
        <thead>
          <tr>
            <th>Göstərici</th>
            <th>Dəyər</th>
            <th>Meyl</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.indicator_id}>
              <td>{indicatorLabel(item.indicator_id)}</td>
              <td>{item.value == null ? "—" : item.value.toFixed(2)}</td>
              <td>
                <span className={`status-pill tone-${LEAN_TONE[item.status]}`}>
                  <span className="status-dot" aria-hidden="true" />
                  {LEAN_LABELS[item.status]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LiveTechnicalSummaryPanel({
  token,
  onUnauthorized,
}: {
  token: string;
  onUnauthorized: () => void;
}) {
  const [summary, setSummary] = useState<LiveTechnicalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const running = useRef(false);

  const refresh = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    try {
      const response = await fetch(
        `${API_BASE}/api/v2/live-technical-summary?symbol=GOLD&timeframe=M1`,
        { cache: "no-store", headers: { Authorization: `Bearer ${token}` } },
      );
      if (response.status === 401) {
        onUnauthorized();
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = (await response.json()).data as LiveTechnicalSummary;
      setSummary(payload);
      setError(null);
    } catch {
      setError("Canlı texniki analiz alına bilmədi. Son uğurlu nəticə göstərilir.");
    } finally {
      running.current = false;
    }
  }, [onUnauthorized, token]);

  useEffect(() => {
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    const initial = window.setTimeout(refreshWhenVisible, 0);
    const interval = window.setInterval(refreshWhenVisible, REFRESH_INTERVAL_MS);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [refresh]);

  return (
    <section className="panel live-technical-summary" aria-labelledby="live-technical-summary-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Canlı indikator konsensusu</p>
          <h2 id="live-technical-summary-title">Texniki analiz</h2>
        </div>
        <span className="research-pill">TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL</span>
      </div>
      {error && <p className="replay-error" role="alert">{error}</p>}
      {!summary || !summary.consensus ? (
        <p className="card-detail">Hazırda kifayət qədər canlı bar məlumatı yoxdur.</p>
      ) : (
        <>
          <div className="live-consensus-grid">
            <GaugeCard title="Osilatorlar" summary={summary.consensus.oscillator_summary} />
            <GaugeCard title="Ümumi" summary={summary.consensus.overall_summary} />
            <GaugeCard title="Hərəkətli ortalamalar" summary={summary.consensus.moving_average_summary} />
          </div>
          <div className="live-consensus-tables">
            <IndicatorTable title="Osilatorlar" items={summary.consensus.oscillators} />
            <IndicatorTable title="Hərəkətli ortalamalar" items={summary.consensus.moving_averages} />
          </div>
          <p className="card-detail">
            {summary.symbol} · {summary.timeframe} · son yenilənmə{" "}
            {new Date(summary.generated_at).toLocaleTimeString("az-AZ")} ·{" "}
            {summary.consensus.oscillator_summary.insufficient_data_count +
              summary.consensus.moving_average_summary.insufficient_data_count >
            0
              ? "bəzi indikatorlar hələ kifayət qədər bar toplamayıb"
              : "bütün indikatorlar hazırdır"}
          </p>
        </>
      )}
    </section>
  );
}
