import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server renders the ESAS monitoring dashboard shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("pragma"), "no-cache");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("x-frame-options"), "DENY");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
  assert.equal(
    response.headers.get("permissions-policy"),
    "camera=(), microphone=(), geolocation=()",
  );
  const html = await response.text();
  assert.match(html, /<title>ESAS Platform — Monitorinq<\/title>/i);
  assert.match(html, /Monitorinq panelinə giriş/);
  assert.match(html, /İstifadəçi kodu/);
  assert.match(html, /Daxil ol/);
  assert.match(html, /lang="az"/);
  assert.doesNotMatch(html, /Your site is taking shape|SkeletonPreview/);
});
