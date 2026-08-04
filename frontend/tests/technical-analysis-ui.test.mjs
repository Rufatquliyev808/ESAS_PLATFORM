import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const sourceUrl = new URL("../app/technical-analysis-panel.tsx", import.meta.url);

test("technical analysis UI keeps indicators separate and research-only", async () => {
  const source = await readFile(sourceUrl, "utf8");
  assert.match(source, /technical-analysis\?/);
  assert.match(source, /Bağlanış qiyməti və EMA/);
  assert.match(source, /RSI göstəricisi/);
  assert.match(source, /ATR göstəricisi/);
  assert.match(source, /HH\/HL və LH\/LL detektoru/);
  assert.match(source, /YÜKSƏLİŞ MÜŞAHİDƏSİ/);
  assert.match(source, /ENİŞ MÜŞAHİDƏSİ/);
  assert.match(source, /yalnız sağdakı/);
  assert.match(source, /bar bağlandıqdan sonra təsdiqlənir/);
  assert.match(source, /StructurePanel/);
  assert.match(source, /LiquidityPanel/);
  assert.match(source, /Bərabər təpə\/dib və fitil süpürməsi/);
  assert.match(source, /Təsdiqlənmiş süpürmə/);
  assert.match(source, /Bu nəticə siqnal, giriş və ya əməliyyat əmri deyil/);
  assert.match(source, /warm-up nöqtəsi/);
  assert.match(source, /Məlumat mənbəyi və hesablamanın izi/);
  assert.match(source, /alış\/satış siqnalı vermir və əməliyyat açmır/);
});
