import assert from "node:assert/strict";
import test from "node:test";
import { Worker } from "node:worker_threads";
import { GeometryClient } from "../src/geometry-client.js";
import { executeGeometryJob, unpackGeometry, prepareTubeLines } from "../src/geometry-jobs.js";
import { estimateTubeBytes } from "../src/field-line-tubes.js";

function workerClient() {
  return new GeometryClient(() => {
    const worker = new Worker(new URL("./helpers/geometry-node-worker.mjs", import.meta.url));
    const adapter = { postMessage: data => worker.postMessage(data), terminate: () => worker.terminate() };
    worker.on("message", data => adapter.onmessage?.({ data }));
    worker.on("error", error => adapter.onerror?.({ message: error.message }));
    return adapter;
  });
}

function sphere(n = 24) {
  const metadata = { nr: n, ntheta: n, nphi: 2 * n, r_inner: 0, r_outer: 1 };
  const coords = {
    r: Array.from({ length: n }, (_, i) => i / (n - 1)),
    theta: Array.from({ length: n }, (_, i) => Math.PI * i / (n - 1)),
    phi: Array.from({ length: 2 * n }, (_, i) => Math.PI * i / n),
  };
  const field = Float32Array.from({ length: n * n * 2 * n }, (_, i) => coords.r[Math.floor(i / (2 * n * n))]);
  return { metadata, coords, field, isoValue: 0.7, requestedResolution: n };
}

test("actual worker isosurfaces match synchronous geometry and the analytical radius", async () => {
  const client = workerClient(), payload = sphere(), progress = [];
  try {
    const original = payload.field.slice();
    let ticks = 0;
    const timer = setInterval(() => ticks++, 5);
    let result;
    try { result = await client.run("isosurface", payload, { onProgress: p => progress.push(p) }); }
    finally { clearInterval(timer); }
    assert.ok(ticks > 0, "the calling event loop runs while geometry is computed");
    assert.deepEqual(payload.field, original, "cached source buffers are not detached or modified");
    const reference = executeGeometryJob("isosurface", payload);
    assert.deepEqual(result.attributes.position.array, reference.attributes.position.array);
    assert.deepEqual(result.attributes.normal.array, reference.attributes.normal.array);
    assert.ok(progress.some(p => p.fraction === 1));
    const geometry = unpackGeometry(result), vertices = geometry.attributes.position;
    assert.ok(vertices.count > 0);
    for (let i = 0; i < vertices.count; i++) {
      const radius = Math.hypot(vertices.getX(i), vertices.getY(i), vertices.getZ(i));
      assert.ok(Math.abs(radius - 0.7) < 0.02, `radius ${radius}`);
    }
    geometry.dispose();
  } finally { client.cancelAll(); }
});

test("worker clipping and nonuniform radial grids retain the existing isosurface convention", () => {
  const payload = sphere(12);
  payload.coords.r = payload.coords.r.map(r => r * r);
  payload.field = Float32Array.from(payload.field, (_, i) => payload.coords.r[Math.floor(i / 288)]);
  payload.clipOptions = { enabled: true, mode: "rear-half", phi0: 0, side: "positive", offset: 0.1 };
  const result = executeGeometryJob("isosurface", payload);
  const p = result.attributes.position.array;
  assert.ok(p.length > 0);
  for (let i = 0; i < p.length; i += 9) assert.ok((p[i + 1] + p[i + 4] + p[i + 7]) / 3 > 0.1 - 1e-7);
});

test("actual worker tubes preserve vertices, colours, normals and indices", async () => {
  const client = workerClient();
  const payload = { lines: [{ points: [[0, 0, 0], [0, 0, 1], [0.2, 0, 2]], strength: [1, 2, 1],
    colors: new Float32Array([1, 0, 0, 0, 1, 0, 0, 0, 1]) }, null],
    options: { reference: 2, diameter: 0.1, minimum: 0, maximum: 0.5, sides: 8, lengthScale: 1 } };
  try {
    const result = await client.run("tubes", payload), expected = executeGeometryJob("tubes", payload);
    assert.deepEqual(result, expected);
    assert.equal(result[1], null);
    assert.equal(payload.lines[0].colors.byteLength, 36);
  } finally { client.cancelAll(); }
});

test("cancelling active and queued worker jobs rejects both and permits a clean retry", async () => {
  const client = workerClient(), payload = sphere(36), controller = new AbortController();
  try {
    const first = client.run("isosurface", payload, { signal: controller.signal });
    const second = client.run("isosurface", payload);
    const checks = [assert.rejects(first, { name: "AbortError" }), assert.rejects(second, { name: "AbortError" })];
    client.cancelAll();
    await Promise.all(checks);
    const retried = await client.run("isosurface", sphere(8));
    assert.ok(retried.attributes.position.array.length > 0);
  } finally { client.cancelAll(); }
});

test("abort interrupts a running worker and queued cancellation does not stop unrelated work", async () => {
  const client = workerClient(), active = new AbortController(), queued = new AbortController();
  try {
    const first = client.run("isosurface", sphere(40), { signal: active.signal });
    const second = client.run("isosurface", sphere(8), { signal: queued.signal });
    const checkFirst = assert.rejects(first, { name: "AbortError" });
    const checkSecond = assert.rejects(second, { name: "AbortError" });
    queued.abort(); active.abort();
    await Promise.all([checkFirst, checkSecond]);
    assert.ok((await client.run("isosurface", sphere(8))).attributes.position.array.length);
    await assert.rejects(client.run("unknown", {}), /Unknown geometry task/);
    assert.ok((await client.run("isosurface", sphere(8))).attributes.position.array.length);
  } finally { client.cancelAll(); }
});

test("late messages from a terminated worker cannot replace a newer result", async () => {
  const workers = [];
  const client = new GeometryClient(() => {
    const worker = { terminate() {}, postMessage(message) { this.message = message; } };
    workers.push(worker); return worker;
  });
  const first = client.run("isosurface", {});
  const rejected = assert.rejects(first, { name: "AbortError" });
  client.cancelAll(); await rejected;
  const latest = client.run("isosurface", {});
  workers[0].onmessage({ data: { id: workers[1].message.id, result: "stale" } });
  workers[1].onmessage({ data: { id: workers[1].message.id, result: "current" } });
  assert.equal(await latest, "current");
  client.cancelAll();
});

test("worker startup failure rejects promptly and can be retried", async () => {
  let calls = 0;
  const client = new GeometryClient(() => { calls++; throw new Error("Worker disabled"); });
  await assert.rejects(client.run("isosurface", {}), /Worker disabled/);
  await assert.rejects(client.run("isosurface", {}), /Worker disabled/);
  assert.equal(calls, 2);
});

const settings = { lineTubeSimplify: true, lineTubeAutoDetail: true, lineTubeShapeError: 0.00001,
  lineTubeEnergyErrorPercent: 0.1, lineTubeAutoMaxShapeError: 0.005,
  lineTubeAutoMaxEnergyErrorPercent: 5, lineTubeSides: 8 };

test("automatic detail fits the budget and preserves every line and paired endpoint", () => {
  const points = Array.from({ length: 2001 }, (_, i) => [i / 2000, 0.01 * Math.sin(i / 2000 * 20 * Math.PI), 0]);
  const shell = { line_id: 11, points, strength: points.map(p => 1 + 0.2 * Math.sin(p[0] * 4 * Math.PI)) };
  const exterior = { ...shell, paired_shell_line_id: 11, points: [...points].reverse(), strength: [...shell.strength].reverse() };
  const selected = { shell: [shell], exterior: [exterior] };
  const manual = prepareTubeLines({ selected, settings: { ...settings, lineTubeAutoDetail: false }, radius: 1, limitBytes: 1 });
  const limitBytes = manual.bytes / 3;
  const fitted = prepareTubeLines({ selected, settings, radius: 1, limitBytes });
  assert.ok(fitted.bytes <= limitBytes);
  assert.ok(fitted.shapeError > settings.lineTubeShapeError);
  assert.ok(fitted.shapeError <= settings.lineTubeAutoMaxShapeError);
  assert.ok(fitted.energyErrorPercent <= settings.lineTubeAutoMaxEnergyErrorPercent);
  for (const mode of ["shell", "exterior"]) {
    const source = selected[mode][0], reduced = fitted.selected[mode][0];
    assert.equal(fitted.selected[mode].length, 1);
    assert.equal(reduced.points[0], source.points[0]);
    assert.equal(reduced.points.at(-1), source.points.at(-1));
    assert.equal(reduced.line_id, source.line_id);
    const originalIndices = new Map(source.points.map((p, i) => [p, i]));
    const arc = [0];
    for (let i = 1; i < source.points.length; i++) arc[i] = arc[i - 1]
      + Math.hypot(...source.points[i].map((value, axis) => value - source.points[i - 1][axis]));
    for (let k = 1; k < reduced.points.length; k++) {
      const a = originalIndices.get(reduced.points[k - 1]), b = originalIndices.get(reduced.points[k]);
      for (let i = a + 1; i < b; i++) {
        const q = (arc[i] - arc[a]) / (arc[b] - arc[a]);
        const error = Math.hypot(...source.points[i].map((value, axis) => value
          - ((1 - q) * source.points[a][axis] + q * source.points[b][axis])));
        assert.ok(error <= fitted.shapeError + 1e-12);
        const actual = source.strength[i] ** 2;
        const interpolated = (1 - q) * source.strength[a] ** 2 + q * source.strength[b] ** 2;
        assert.ok(Math.abs(actual - interpolated) <= fitted.energyErrorPercent / 100 * Math.max(actual, interpolated) + 1e-12);
      }
    }
  }
  assert.equal(fitted.selected.shell[0].points.at(-1), fitted.selected.exterior[0].points[0]);
  assert.equal(points.length, 2001);
  assert.equal(fitted.bytes, estimateTubeBytes(Object.values(fitted.selected).flat(), 8));
});

test("automatic detail cannot exceed error bounds or silently discard lines to fit", () => {
  const line = { points: [[0, 0, 0], [0, 0, 1]], strength: [1, 1], line_id: 7 };
  assert.throws(() => prepareTubeLines({ selected: { shell: [line] }, settings, radius: 1, limitBytes: 1 }), /cannot fit.*allowed errors/);
  const strict = prepareTubeLines({ selected: { shell: [line] }, radius: 1, limitBytes: 100000,
    settings: { ...settings, lineTubeShapeError: 0.02, lineTubeEnergyErrorPercent: 10 } });
  assert.equal(strict.shapeError, settings.lineTubeAutoMaxShapeError);
  assert.equal(strict.energyErrorPercent, settings.lineTubeAutoMaxEnergyErrorPercent);
  for (const overrides of [{ lineTubeAutoDetail: false }, { lineTubeSimplify: false }]) {
    const result = prepareTubeLines({ selected: { shell: [line] }, settings: { ...settings, ...overrides }, radius: 1, limitBytes: 1 });
    assert.equal(result.automatic, false);
    assert.equal(result.selected.shell[0], line);
  }
});
