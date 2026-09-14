import assert from "node:assert/strict";
import test from "node:test";
import { computeLongitudeAverage, longitudeWeights, LongitudeAverageCache,
  longitudeDisplayField, volumeDisplayValue } from "../src/longitude-average.js";

test("uniform longitude reduction isolates m=0 for every radius and latitude", () => {
  const metadata = { nr: 3, ntheta: 4, nphi: 16 };
  const phi = Array.from({ length: 16 }, (_, i) => .17 + 2 * Math.PI * i / 16);
  const field = Float32Array.from({ length: 192 }, (_, i) =>
    2 + Math.floor(i / 16) / 4 + 3 * Math.cos(2 * phi[i % 16]) - Math.sin(phi[i % 16]));
  const original = field.slice();
  const mean = computeLongitudeAverage({ field, metadata, phi });
  assert.equal(mean.length, 12);
  field.viewerDomain = { r_min: .5, magnetic: true };
  const average = longitudeDisplayField(field, mean, "mean", 16);
  const fluctuation = longitudeDisplayField(field, mean, "fluctuation", 16);
  assert.equal(longitudeDisplayField(field, null, "slice", 16), field);
  assert.equal(average.viewerDomain, field.viewerDomain);
  for (let row = 0; row < 12; row++) {
    assert.ok(Math.abs(mean[row] - (2 + row / 4)) < 2e-7);
    let residual = 0;
    for (let ip = 0; ip < 16; ip++) {
      const index = row * 16 + ip;
      assert.equal(volumeDisplayValue(average, index), mean[row]);
      assert.equal(volumeDisplayValue(average, index) + volumeDisplayValue(fluctuation, index), field[index]);
      residual += volumeDisplayValue(fluctuation, index);
    }
    assert.ok(Math.abs(residual) < 1e-12);
  }
  assert.deepEqual(field.slice(), original);
});

test("nonuniform periodic quadrature includes the closing longitude interval", () => {
  const phi = [0, Math.PI / 4, Math.PI, 3 * Math.PI / 2];
  assert.deepEqual(Array.from(longitudeWeights(phi, 4)), [3 / 16, 1 / 4, 5 / 16, 1 / 4]);
  const mean = computeLongitudeAverage({ field: new Float32Array([0, 4, 8, 12]),
    metadata: { nr: 1, ntheta: 1, nphi: 4 }, phi });
  assert.equal(mean[0], 6.5);
  assert.deepEqual(longitudeWeights(phi.map(x => x - 4), 4), longitudeWeights(phi, 4));
});

test("compensated float64 reduction preserves a small mean across cancelling f32 values", () => {
  const mean = computeLongitudeAverage({ field: new Float32Array([2 ** 80, 1, -(2 ** 80), 1]),
    metadata: { nr: 1, ntheta: 1, nphi: 4 } });
  assert.equal(mean[0], .5);
});

test("invalid dimensions, coordinates and nonfinite samples fail explicitly", () => {
  const payload = { field: new Float32Array([1, 2, 3, 4]), metadata: { nr: 1, ntheta: 1, nphi: 4 } };
  for (const phi of [[0, 1, 2], [0, 1, 1, 2], [0, 1, 2, 2 * Math.PI], [0, 1, NaN, 3]]) {
    assert.throws(() => computeLongitudeAverage({ ...payload, phi }));
  }
  assert.throws(() => computeLongitudeAverage({ ...payload, field: new Float32Array(3) }), /dimensions/);
  assert.throws(() => computeLongitudeAverage({ ...payload, field: new Float32Array([1, 2, NaN, 4]) }), /non-finite/);
});

test("mean cache shares pending work, distinguishes frames and retries cancelled computations", async () => {
  const cache = new LongitudeAverageCache(), field = new Float32Array(8);
  const metadata = { nr: 1, ntheta: 2, nphi: 4 }, phi = [0, 1, 2, 3];
  let calls = 0;
  const compute = async () => { calls++; return new Float64Array([calls, calls]); };
  const a = cache.get(field, metadata, phi, compute), b = cache.get(field, metadata, phi, compute);
  assert.equal(a, b);
  assert.equal(await a, await b);
  assert.equal(calls, 1);
  await cache.get(field.slice(), metadata, phi, compute);
  assert.equal(calls, 2, "a new frame has a separate reduction");
  await cache.get(field, metadata, phi.slice(), compute);
  assert.equal(calls, 3, "a changed coordinate object invalidates the reduction");
  cache.clear();
  await assert.rejects(cache.get(field, metadata, phi, () => { throw new DOMException("Cancelled", "AbortError"); }), { name: "AbortError" });
  await cache.get(field, metadata, phi, compute);
  assert.equal(calls, 4);
});
