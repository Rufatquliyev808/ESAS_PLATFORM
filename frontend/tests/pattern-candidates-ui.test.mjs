import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/pattern-candidates-panel.tsx", import.meta.url);

test("pattern candidates UI stays draft-only, research-only and covers all six hypotheses", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /pattern-candidates\?/);
  assert.match(source, /PatternSlotCard/);
  assert.match(source, /market_structure_long: "Yüksələn bazar strukturu"/);
  assert.match(source, /market_structure_short: "Enən bazar strukturu"/);
  assert.match(source, /liquidity_sweep_reclaim_long:/);
  assert.match(source, /liquidity_sweep_reclaim_short:/);
  assert.match(source, /structure_break_long:/);
  assert.match(source, /structure_break_short:/);
  assert.match(source, /candidate_confirmed/);
  assert.match(source, /insufficient_data/);
  assert.match(source, /no_candidate/);
  assert.match(source, /Draft tədqiqat namizədi · siqnal, giriş və ya order deyil/);
  assert.match(source, /Backtest, label, qəbul\/rədd qərarı bu mərhələyə daxil deyil/);
  assert.match(source, /Bütün namizədlər `draft` vəziyyətindədir/);
  assert.match(source, /Platforma bu bölmədə alış\/satış siqnalı vermir və order yaratmır/);
  assert.match(source, /Məlumat mənbəyi və hesablamanın izi/);
});
