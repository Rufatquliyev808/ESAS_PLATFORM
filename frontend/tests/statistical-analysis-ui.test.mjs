import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/statistical-analysis-panel.tsx", import.meta.url);

test("statistical analysis panel stays research-only and covers SA-001-SA-007", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /replay-sessions\/\$\{sessionId\}\/statistical-analysis/);
  assert.match(source, /TƏDQİQAT MÜŞAHİDƏSİDİR — TİCARƏT TÖVSİYƏSİ DEYİL/);
  const lowered = source.toLowerCase();
  assert.doesNotMatch(lowered, /placeorder|sendorder|positionsize|"buy"|'buy'|"sell"|'sell'|gözlənilir/);
  // Regime labels must be documented as arbitrary/non-comparable across runs.
  assert.match(source, /ixtiyaridir/);
  // SA-006 must stay explicitly framed as raw UTC hours, not named sessions.
  assert.match(source, /adlandırılmış bazar sessiyası/);
  // All seven SA sections should be represented.
  for (const marker of ["SA-001", "SA-002", "SA-003", "SA-004", "SA-005", "SA-006", "SA-007"]) {
    assert.match(source, new RegExp(marker));
  }
});
