import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/pattern-hypothesis-registry.tsx", import.meta.url);

test("pattern registry keeps hypotheses separate and research-only", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /pattern-hypotheses/);
  assert.match(source, /Bazar strukturu hipotez reyestri/);
  assert.match(source, /LONG hipotezi/);
  assert.match(source, /SHORT hipotezi/);
  assert.match(source, /Siqnal deyil · əməliyyat açmır/);
  assert.match(source, /Hələ strategiya, giriş nöqtəsi, risk hesabı/);
  assert.doesNotMatch(source, /placeOrder|sendOrder|positionSize/);
});
