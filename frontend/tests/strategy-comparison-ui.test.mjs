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
  assert.match(source, /RSI aşağı hədd/);
  assert.match(source, /definition\.version/);
  assert.match(source, /Nəticə izi/);
  assert.match(source, /alış\/satış qərarı vermir/);
  assert.match(source, /ticarət əməliyyatı açmır/);
});
