import assert from "node:assert/strict";
import test from "node:test";
import worker from "../cloudflare/figshare-proxy.js";

const origin = "https://ludhovik.github.io";
const recordUrl = "https://deep-figshare-proxy.ludhovik-research.workers.dev/figshare/articles/33455986";

test("Figshare record replacements bypass edge caches and are not cached by the browser", async (t) => {
  let revision = 1;
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "https://api.figshare.com/v2/articles/33455986");
    assert.equal(options.cache, "no-store");
    assert.equal(options.cf?.cacheEverything, undefined);
    return Response.json({ version: revision }, { headers: { "Cache-Control": "public, max-age=3600" } });
  });
  for (revision = 1; revision <= 2; revision++) {
    const response = await worker.fetch(new Request(recordUrl, { headers: { Origin: origin } }));
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("Cache-Control"), "no-store");
    assert.equal(response.headers.get("Access-Control-Allow-Origin"), origin);
    assert.equal((await response.json()).version, revision);
  }
});

test("proxy refresh retains read-only routes, upstream status and CORS behaviour", async (t) => {
  let requests = 0;
  t.mock.method(globalThis, "fetch", async () => {
    requests++;
    return Response.json({ message: "Not found" }, { status: 404 });
  });
  const response = await worker.fetch(new Request(recordUrl, { headers: { Origin: origin } }));
  assert.equal(response.status, 404);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal(response.headers.get("Access-Control-Allow-Origin"), origin);
  assert.equal((await worker.fetch(new Request(recordUrl, { method: "POST" }))).status, 405);
  assert.equal((await worker.fetch(new Request(recordUrl.replace("33455986", "invalid")))).status, 404);
  const preflight = await worker.fetch(new Request(recordUrl, { method: "OPTIONS", headers: { Origin: origin } }));
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get("Access-Control-Allow-Methods"), "GET, OPTIONS");
  assert.equal(requests, 1);
  const otherOrigin = await worker.fetch(new Request(recordUrl, { headers: { Origin: "https://unrelated.example" } }));
  assert.equal(otherOrigin.headers.get("Access-Control-Allow-Origin"), null);
});
