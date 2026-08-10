import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/shadow-runs-panel.tsx", import.meta.url);

test("shadow runs panel stays a manual, theoretical Phase 9 skeleton", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /api\/v2\/shadow-runs/);
  assert.match(source, /NƏZƏRİDİR — REAL ƏMƏLİYYAT YOXDUR/);
  assert.match(source, /execution_allowed/);
  assert.match(source, /Order göndərilmir, mövqe MT5-də açılmır, real hesab balansına toxunulmur/);
  assert.match(source, /Real bazar müşahidəsi, qərar generasiyası və order icrası yoxdur/);
  assert.doesNotMatch(source, /placeOrder|sendOrder|positionSize/);
});

test("shadow runs panel offers a lineage-only connection to an accepted_for_shadow Visual AI experiment", async () => {
  const source = await readFile(sourceUrl, "utf8");
  // Challenger fieldset is optional (backward compatible with champion-only runs).
  assert.match(source, /challenger_module_id/);
  assert.match(source, /challenger_visual_experiment_id/);
  assert.match(source, /visual_experiment_id/);
  assert.match(source, /visual_model_checksum/);
  assert.match(source, /visual_acceptance_decision_checksum/);
  // Explicitly disclaims that this is lineage-only, not decision generation.
  assert.match(source, /YALNIZ audit-səviyyəli lineage-dir, modeldən heç bir qərar generasiya olunmur/);
  const lowered = source.toLowerCase();
  assert.doesNotMatch(lowered, /placeorder|sendorder|positionsize|"buy"|'buy'|"sell"|'sell'/);
});
