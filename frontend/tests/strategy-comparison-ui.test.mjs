import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/strategy-comparison-panel.tsx", import.meta.url);

test("strategy comparison stays modular, traceable and research-only", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /strategy-analysis\?/);
  assert.match(source, /strategiya müqayisə laboratoriyası/);
  assert.match(source, /Qiymətin EMA ilə münasibəti/);
  assert.match(source, /RSI momentum rejimi/);
  assert.match(source, /rsi_regime_observation/);
  assert.match(source, /outcome_horizon/);
  assert.match(source, /outcome_evaluation\.summary\.matured/);
  assert.match(source, /outcome_evaluation\.summary\.immature/);
  assert.match(source, /strategy-outcomes/);
  assert.match(source, /development_ratio/);
  assert.match(source, /walk_forward_windows/);
  assert.match(source, /walk_forward_evaluation/);
  assert.match(source, /multi_window_evaluation/);
  assert.match(source, /stability-overview/);
  assert.match(source, /stability-windows/);
  assert.match(source, /cost_scenario_evaluation/);
  assert.match(source, /cost_spread_bps/);
  assert.match(source, /cost-scenario-grid/);
  assert.match(source, /Xam və xərc çıxılmış tarixi dəyişiklik/);
  assert.match(source, /brokerdən təsdiqlənmiş real tarif deyil/);
  assert.match(source, /Siqnal, risk icazəsi və order yaratmır/);
  assert.match(source, /İnkişaf və toxunulmamış yoxlama/);
  assert.match(source, /sərhədi keçən gələcək nəticələr inkişaf hesabından çıxarılır/);
  assert.match(source, /mənfəət vəd etmir/);
  assert.match(source, /RSI aşağı hədd/);
  assert.match(source, /definition\.version/);
  assert.match(source, /Nəticə izi/);
  assert.match(source, /alış\/satış qərarı vermir/);
  assert.match(source, /ticarət əməliyyatı açmır/);
});
