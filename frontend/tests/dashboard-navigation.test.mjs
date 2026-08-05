import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const page = await readFile(new URL("../app/page.tsx", import.meta.url), "utf8");
const navigation = await readFile(
  new URL("../app/dashboard-navigation.tsx", import.meta.url),
  "utf8",
);
const replay = await readFile(
  new URL("../app/replay-panel.tsx", import.meta.url),
  "utf8",
);
const analysis = await readFile(
  new URL("../app/technical-analysis-panel.tsx", import.meta.url),
  "utf8",
);
const styles = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

test("dashboard opens the results section by default", () => {
  assert.match(page, /useState<DashboardSection>\("results"\)/);
  assert.match(page, /<DashboardSidebar/);
  assert.match(page, /activeSection === "results"/);
});

test("sidebar exposes educational section guidance", () => {
  assert.match(navigation, /Nəticələr/);
  assert.match(navigation, /Texniki göstəricilər/);
  assert.match(navigation, /Strategiya müqayisəsi/);
  assert.match(navigation, /GOLD-a mümkün təsiri/);
  assert.match(navigation, /<summary>Nəyə əsaslanır\?<\/summary>/);
});

test("large analysis areas render independently", () => {
  assert.match(replay, /view === "replay"/);
  assert.match(replay, /view === "strategies"/);
  assert.match(analysis, /view === "technical"/);
  assert.match(analysis, /view === "structure"/);
  assert.match(analysis, /view === "liquidity"/);
  assert.match(analysis, /view === "bos-choch"/);
  assert.match(analysis, /view === "retest"/);
});

test("dashboard layout has desktop and responsive navigation styles", () => {
  assert.match(styles, /\.dashboard-shell/);
  assert.match(styles, /\.dashboard-sidebar/);
  assert.match(styles, /\.dashboard-workspace/);
  assert.match(styles, /@media \(max-width: 980px\)/);
});
