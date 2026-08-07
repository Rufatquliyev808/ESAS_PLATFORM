import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/liquidity-overview-panel.tsx", import.meta.url);

test("liquidity overview panel stays a research-only backtest summary, not a trading signal", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /api\/v2\/liquidity-overview/);
  assert.match(source, /TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL/);
  // "buy_side"/"sell_side" are pre-existing liquidity-pool-side labels
  // (structural, not action language), so a bare buy/sell check would
  // false-positive here; check for the actual prohibited action language.
  const lowered = source.toLowerCase();
  assert.doesNotMatch(lowered, /placeorder|sendorder|positionsize|"buy"|'buy'|"sell"|'sell'|gözlənilir/);
});
