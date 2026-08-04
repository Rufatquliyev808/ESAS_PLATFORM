"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ESAS_API_URL ?? "http://127.0.0.1:8000";

type Hypothesis = {
  hypothesis_id: string; version: string; title: string; family: string;
  direction: "long" | "short" | "neutral"; lifecycle: string; readiness: string;
  question: string; required_observations: string[]; invalidation_observations: string[];
  required_timeframes: string[]; evidence_status: string;
};
type Registry = { registry_version: string; interpretation: string; fingerprint: string; hypotheses: Hypothesis[] };

const labels: Record<string, string> = {
  market_structure: "Bazar strukturu", liquidity_sweep: "Likvidlik müşahidəsi",
  bos_choch_retest: "Struktur qırılması / retest", zone_model: "Zona modeli",
  definition_ready: "Tərif hazırdır", needs_precise_detector: "Detektor dəqiqləşməlidir",
  definition_incomplete: "Tərif tamamlanmalıdır", long: "LONG hipotezi",
  short: "SHORT hipotezi", neutral: "Neytral hipotez",
};

export function PatternHypothesisRegistry({ token, onUnauthorized }: { token: string; onUnauthorized: () => void }) {
  const [registry, setRegistry] = useState<Registry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/v2/research/pattern-hypotheses`, { cache: "no-store", headers: { Authorization: `Bearer ${token}` } });
      if (response.status === 401) { onUnauthorized(); return; }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setRegistry((await response.json()).data as Registry);
    } catch { setError("Hipotez reyestri hazırda alına bilmədi."); }
  }, [onUnauthorized, token]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return <section className="pattern-registry" aria-labelledby="pattern-registry-title">
    <div className="pattern-registry-head"><div><p className="eyebrow">Phase 4 · əvvəlcədən qeydiyyat</p><h2 id="pattern-registry-title">Bazar strukturu hipotez reyestri</h2><p>Nümunə şəkillər yalnız araşdırma ideyasıdır. Hər ailə ayrıca versiyalanacaq və ayrıca sınaqdan keçəcək.</p></div><span className="research-pill">Siqnal deyil · əməliyyat açmır</span></div>
    {error && <div className="replay-error" role="alert">{error} <button type="button" onClick={() => void load()}>Yenidən yoxla</button></div>}
    {!registry && !error && <div className="analysis-loading"><span className="loading-ring" /><strong>Hipotezlər yüklənir</strong></div>}
    {registry && <>
      <div className="pattern-summary"><span>Reyestr v{registry.registry_version}</span><span>{registry.hypotheses.length} ayrı hipotez</span><span>Dəyişməz iz: {registry.fingerprint.slice(7, 19)}…</span></div>
      <div className="pattern-grid">{registry.hypotheses.map((item) => <article className={`pattern-card ${item.direction}`} key={item.hypothesis_id}>
        <header><div><p className="eyebrow">{labels[item.family] ?? item.family}</p><h3>{item.title}</h3></div><span className={`pattern-direction ${item.direction}`}>{labels[item.direction]}</span></header>
        <p>{item.question}</p>
        <div className="pattern-meta"><span>v{item.version}</span><span>{labels[item.readiness] ?? item.readiness}</span><span>{item.required_timeframes.join(" · ")}</span></div>
        <details><summary>Ölçüləcək şərtlər</summary><ul>{item.required_observations.map((value) => <li key={value}>{value}</li>)}</ul></details>
        <details><summary>Hipotezi etibarsız edən hallar</summary><ul>{item.invalidation_observations.map((value) => <li key={value}>{value}</li>)}</ul></details>
      </article>)}</div>
      <p className="pattern-boundary"><strong>Mərhələ sərhədi:</strong> Bunlar yalnız maşınla oxunan tədqiqat suallarıdır. Hələ strategiya, giriş nöqtəsi, risk hesabı və ya alqı-satqı icazəsi deyil.</p>
    </>}
  </section>;
}
