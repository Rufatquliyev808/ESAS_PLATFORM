import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/live-technical-summary-panel.tsx", import.meta.url);

test("live technical summary panel stays a research-only indicator consensus, not a trading signal", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /api\/v2\/live-technical-summary/);
  assert.match(source, /TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL/);
  assert.doesNotMatch(source.toLowerCase(), /\bbuy\b|\bsell\b|placeorder|sendorder|positionsize/);
});
