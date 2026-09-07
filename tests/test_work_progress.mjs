import assert from "node:assert/strict";
import test from "node:test";
import { createWorkProgress, readResponseWithProgress } from "../src/work-progress.js";

test("progress remains visible independently of the title and cleans up overlapping work", () => {
  const panel = {}, label = {}, bar = { removeAttribute() { delete this.value; } }, cancel = { addEventListener(_, callback) { this.click = callback; } };
  const progress = createWorkProgress({ panel, label, bar, cancel });
  let cancelled = 0;
  const root = progress.begin("Opening dataset", () => cancelled++);
  const file = progress.begin("Br.f32", () => cancelled++);
  file.update({ label: "Br.f32: 4 / 8 MiB", fraction: 0.5 });
  assert.equal(panel.hidden, false); assert.equal(bar.value, 0.5);
  cancel.click(); assert.equal(cancelled, 2);
  file.finish();
  assert.equal(label.textContent, "Opening dataset"); assert.equal(bar.value, undefined);
  file.update({ label: "stale", fraction: 1 });
  assert.equal(label.textContent, "Opening dataset");
  root.finish(); assert.equal(panel.hidden, true);
});

test("streamed reads preserve binary bytes and report completion", async () => {
  const chunks = [new Uint8Array([1, 2]), new Uint8Array([3, 4, 5])], progress = [];
  const body = new ReadableStream({ start(controller) { chunks.forEach(c => controller.enqueue(c)); controller.close(); } });
  const result = await readResponseWithProgress(new Response(body, { headers: { "Content-Length": "5" } }), "arrayBuffer",
    { onProgress: p => progress.push(p) });
  assert.deepEqual(new Uint8Array(result), new Uint8Array([1, 2, 3, 4, 5]));
  assert.deepEqual(progress.at(-1), { received: 5, total: 5 });
});

test("streamed JSON handles split UTF-8 and unknown or compressed lengths", async () => {
  const bytes = new TextEncoder().encode('{"name":"B²"}');
  for (const headers of [{}, { "Content-Length": "4", "Content-Encoding": "gzip" }]) {
    const body = new ReadableStream({ start(c) { c.enqueue(bytes.slice(0, 11)); c.enqueue(bytes.slice(11)); c.close(); } });
    assert.deepEqual(await readResponseWithProgress(new Response(body, { headers }), "json"), { name: "B²" });
  }
});

test("cancelling an unfinished local or remote stream releases its reader", async () => {
  const controller = new AbortController();
  let cancelled = false;
  const body = new ReadableStream({ start(c) { c.enqueue(new Uint8Array([1, 2])); }, cancel() { cancelled = true; } });
  const response = new Response(body);
  const pending = readResponseWithProgress(response, "arrayBuffer", { signal: controller.signal });
  const rejected = assert.rejects(pending, { name: "AbortError" });
  controller.abort(); await rejected;
  assert.equal(cancelled, true); assert.equal(response.body.locked, false);
});

test("stream failures propagate and malformed JSON does not become a successful load", async () => {
  const response = new Response(new ReadableStream({ start(c) { c.error(new Error("interrupted")); } }));
  await assert.rejects(readResponseWithProgress(response, "arrayBuffer"), /interrupted/);
  assert.equal(response.body.locked, false);
  await assert.rejects(readResponseWithProgress(new Response("{broken"), "json"), SyntaxError);
});
