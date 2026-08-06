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
