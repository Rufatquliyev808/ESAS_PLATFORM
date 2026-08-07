"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";
// This endpoint recomputes historical backtest statistics across four
// timeframes on every call; it is not meant for 5s polling like the live
// indicator consensus panel, so this refreshes far less often.
const REFRESH_INTERVAL_MS = 90_000;

type Trend = "bullish" | "bearish" | "neutral" | "insufficient_data";
type Outcome = "reversed" | "continued" | "ambiguous";

type LiquidityLevel = { side: string; level: number; touch_count: number; distance_bps: number };

type ReactionEvent = {
  pool_side: string;
  pool_level: number;
  touched_at: string;
  outcome: Outcome;
  excursion_bps: number | null;
};

type ReactionStatistics = {
  pool_side: string;
  status: "completed" | "insufficient_data";
  n_total: number;
  n_reversed: number;
  n_continued: number;
  n_ambiguous: number;
  reversed_percent: number | null;
  confidence_interval_low_percent: number | null;
  confidence_interval_high_percent: number | null;
};

type ReactionPayload = {
  events: ReactionEvent[];
  buy_side_statistics: ReactionStatistics;
  sell_side_statistics: ReactionStatistics;
};

type IndicatorSegment = {
  condition_id: string;
  status: "completed" | "insufficient_data";
  n_total: number;
  reversed_percent: number | null;
  confidence_interval_low_percent: number | null;
  baseline_reversed_percent: number | null;
  exceeds_baseline: boolean | null;
};

type SegmentPayload = { baseline: ReactionStatistics; segments: IndicatorSegment[] };

type TimeframeOverview = {
  timeframe: string;
  status: "completed" | "insufficient_data";
  bar_count: number;
  latest_close: number | null;
  trend: Trend;
  nearest_resistance: LiquidityLevel | null;
  nearest_support: LiquidityLevel | null;
  reaction: ReactionPayload;
  segments: { buy_side: SegmentPayload; sell_side: SegmentPayload };
};

type LiquidityOverview = {
  symbol: string;
  generated_at: string;
  timeframes: TimeframeOverview[];
};

const TREND_LABELS: Record<Trend, string> = {
  bullish: "Yuxarı trend",
  bearish: "Aşağı trend",
  neutral: "Neytral",
  insufficient_data: "Kifayət qədər məlumat yoxdur",
};

const TREND_TONE: Record<Trend, string> = {
  bullish: "good",
  bearish: "danger",
  neutral: "neutral",
  insufficient_data: "info",
};

const OUTCOME_LABELS: Record<Outcome, string> = {
  reversed: "Geri qayıtdı",
  continued: "Keçdi",
  ambiguous: "Qeyri-müəyyən",
};

const SIDE_LABELS: Record<string, string> = {
  buy_side: "Müqavimət (yuxarıdan yaxınlaşma)",
  sell_side: "Dəstək (aşağıdan yaxınlaşma)",
};

const CONDITION_LABELS: Record<string, string> = {
  rsi_oversold: "RSI aşırı-satılmış",
  rsi_overbought: "RSI aşırı-alınmış",
  stochastic_oversold: "Stochastic aşırı-satılmış",
  stochastic_overbought: "Stochastic aşırı-alınmış",
  adx_trending: "ADX güclü trend göstərir",
};

function formatPercent(value: number | null): string {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

function formatPoints(distanceBps: number, price: number): string {
  const points = (Math.abs(distanceBps) / 10_000) * price;
  return `${points.toFixed(2)} (${Math.abs(distanceBps).toFixed(0)} bps)`;
}

function ReactionSummary({ side, stats }: { side: string; stats: ReactionStatistics }) {
  if (stats.status === "insufficient_data") {
    return (
      <p className="card-detail">
        {SIDE_LABELS[side] ?? side}: kifayət qədər tarixi toxunma yoxdur (n={stats.n_total}).
      </p>
    );
  }
  return (
    <p className="card-detail">
      {SIDE_LABELS[side] ?? side}: tarixən <strong>{formatPercent(stats.reversed_percent)}</strong> geri
      qayıdıb (95% etibar intervalı: {formatPercent(stats.confidence_interval_low_percent)}–
      {formatPercent(stats.confidence_interval_high_percent)}, n={stats.n_reversed + stats.n_continued}).
    </p>
  );
}

function SegmentList({ segments }: { segments: IndicatorSegment[] }) {
  const notable = segments.filter((item) => item.status === "completed" && item.exceeds_baseline);
  if (notable.length === 0) return null;
  return (
    <ul className="liquidity-segment-list">
      {notable.map((item) => (
        <li key={item.condition_id}>
          {CONDITION_LABELS[item.condition_id] ?? item.condition_id} zamanı tarixi geri-qayıtma faizi{" "}
          <strong>{formatPercent(item.reversed_percent)}</strong>-ə çatır (baza: {formatPercent(item.baseline_reversed_percent)}, n={item.n_total}).
        </li>
      ))}
    </ul>
  );
}

function JournalList({ events, price }: { events: ReactionEvent[]; price: number }) {
  const [expanded, setExpanded] = useState(false);
  const recent = events.slice(-30).reverse();
  if (recent.length === 0) return null;
  return (
    <details className="liquidity-journal" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary>Jurnal — son {recent.length} tarixi toxunma</summary>
      <ul>
        {recent.map((event, index) => (
          <li key={`${event.touched_at}-${index}`}>
            <span>{new Date(event.touched_at).toLocaleString("az-AZ")}</span>
            <span>{event.pool_level.toFixed(2)}</span>
            <span>{OUTCOME_LABELS[event.outcome]}</span>
            <span>{event.excursion_bps == null ? "—" : formatPoints(event.excursion_bps, price)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function TimeframeCard({ overview }: { overview: TimeframeOverview }) {
  if (overview.status === "insufficient_data" || overview.latest_close == null) {
    return (
      <article className="liquidity-timeframe-card">
        <p className="eyebrow">{overview.timeframe}</p>
        <p className="card-detail">Hazırda kifayət qədər tarixi bar məlumatı yoxdur.</p>
      </article>
    );
  }
  const price = overview.latest_close;
  return (
    <article className="liquidity-timeframe-card">
      <div className="card-topline">
        <p className="eyebrow">{overview.timeframe}</p>
        <span className={`status-pill tone-${TREND_TONE[overview.trend]}`}>
          <span className="status-dot" aria-hidden="true" />
          {TREND_LABELS[overview.trend]}
        </span>
      </div>
      <p className="card-value">{price.toFixed(2)}</p>
      <p className="card-detail">
        {overview.nearest_resistance
          ? `Ən yaxın müqavimət: ${overview.nearest_resistance.level.toFixed(2)} (${formatPoints(overview.nearest_resistance.distance_bps, price)} uzaqda)`
          : "Müqavimət səviyyəsi tapılmadı."}
      </p>
      <p className="card-detail">
        {overview.nearest_support
          ? `Ən yaxın dəstək: ${overview.nearest_support.level.toFixed(2)} (${formatPoints(overview.nearest_support.distance_bps, price)} uzaqda)`
          : "Dəstək səviyyəsi tapılmadı."}
      </p>
      <ReactionSummary side="buy_side" stats={overview.reaction.buy_side_statistics} />
      <ReactionSummary side="sell_side" stats={overview.reaction.sell_side_statistics} />
      <SegmentList segments={overview.segments.buy_side.segments} />
      <SegmentList segments={overview.segments.sell_side.segments} />
      <JournalList events={overview.reaction.events} price={price} />
    </article>
  );
}

export function LiquidityOverviewPanel({
  token,
  onUnauthorized,
}: {
  token: string;
  onUnauthorized: () => void;
}) {
  const [overview, setOverview] = useState<LiquidityOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const running = useRef(false);

  const refresh = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    try {
      const response = await fetch(
        `${API_BASE}/api/v2/liquidity-overview?symbol=GOLD`,
        { cache: "no-store", headers: { Authorization: `Bearer ${token}` } },
      );
      if (response.status === 401) {
        onUnauthorized();
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = (await response.json()).data as LiquidityOverview;
      setOverview(payload);
      setError(null);
    } catch {
      setError("Likvidlik icmalı alına bilmədi. Son uğurlu nəticə göstərilir.");
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
    <section className="panel liquidity-overview" aria-labelledby="liquidity-overview-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Çox-taymfreym likvidlik icmalı</p>
          <h2 id="liquidity-overview-title">Likvidlik səviyyələri</h2>
        </div>
        <div className="liquidity-overview-actions">
          <span className="research-pill">TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL</span>
          <button type="button" onClick={() => void refresh()}>Yenilə</button>
        </div>
      </div>
      {error && <p className="replay-error" role="alert">{error}</p>}
      {!overview ? (
        <p className="card-detail">Yüklənir…</p>
      ) : (
        <>
          <div className="liquidity-timeframe-grid">
            {overview.timeframes.map((item) => (
              <TimeframeCard key={item.timeframe} overview={item} />
            ))}
          </div>
          <p className="card-detail">
            {overview.symbol} · son yenilənmə {new Date(overview.generated_at).toLocaleTimeString("az-AZ")}
          </p>
        </>
      )}
    </section>
  );
}
