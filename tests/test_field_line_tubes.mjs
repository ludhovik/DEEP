import assert from "node:assert/strict";
import test from "node:test";
import * as THREE from "three";
import { makeMagneticTubeGeometry, magneticTubeDiameter, peakLineStrength, estimateTubeBytes, simplifyMagneticLine } from "../src/field-line-tubes.js";

const options = { reference: 1, diameter: 0.1, minimum: 0, maximum: 1, sides: 8, lengthScale: 1 };
const colours = count => Array(count).fill([1, 0.2, 0.1]).flat();
const near = (a, b, tolerance = 2e-7) => assert.ok(Math.abs(a - b) < tolerance, `${a} ≈ ${b}`);

test("tube diameter follows B squared with explicit reference and display limits", () => {
  near(magneticTubeDiameter(1, options), 0.1);
  near(magneticTubeDiameter(2, options), 0.4);
  near(magneticTubeDiameter(2, { ...options, reference: 2 }), 0.1);
  near(magneticTubeDiameter(0, options), 0);
  near(magneticTubeDiameter(1e300, options), 1);
  near(magneticTubeDiameter(0, { ...options, minimum: 0.01 }), 0.01);
  for (const value of [null, undefined, NaN, Infinity, -1, "2"]) {
    assert.equal(magneticTubeDiameter(value, options), null);
  }
  assert.throws(() => magneticTubeDiameter(1, { ...options, maximum: 0.01, minimum: 0.1 }));
});

test("real Three.js tube rings have the requested radii at each field sample", () => {
  const points = [[0, 0, 0], [0, 0, 1], [0, 0, 2]];
  const strength = [1, 2, 0.5];
  const geometry = makeMagneticTubeGeometry(points, strength, colours(3), options);
  const position = geometry.attributes.position;
  for (let i = 0; i < 3; i++) for (let k = 0; k < 8; k++) {
    const vertex = new THREE.Vector3().fromBufferAttribute(position, 8 * i + k);
    near(vertex.distanceTo(new THREE.Vector3(...points[i])), 0.05 * strength[i] ** 2);
  }
  assert.ok(geometry.attributes.normal.array.every(Number.isFinite));
  assert.ok(geometry.attributes.color.array.every(Number.isFinite));
  geometry.dispose();
});

test("uniform tube faces point outwards and its caps are hit by rays", () => {
  const geometry = makeMagneticTubeGeometry([[0, 0, 0], [0, 0, 1]], [1, 1], colours(2), options);
  const p = geometry.attributes.position, indices = geometry.index.array;
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (let i = 0; i < indices.length; i += 3) {
    a.fromBufferAttribute(p, indices[i]); b.fromBufferAttribute(p, indices[i + 1]); c.fromBufferAttribute(p, indices[i + 2]);
    const centre = a.clone().add(b).add(c).multiplyScalar(1 / 3);
    const normal = b.clone().sub(a).cross(c.clone().sub(a));
    assert.ok(normal.lengthSq() > 1e-16);
    const outward = centre.z === 0 ? new THREE.Vector3(0, 0, -1)
      : centre.z === 1 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(centre.x, centre.y, 0);
    assert.ok(normal.dot(outward) > 0);
  }
  const material = new THREE.MeshBasicMaterial();
  const mesh = new THREE.Mesh(geometry, material); mesh.updateMatrixWorld();
  for (const [origin, direction] of [ [[0, 0, -1], [0, 0, 1]], [[0, 0, 2], [0, 0, -1]], [[1, 0, 0.5], [-1, 0, 0]] ]) {
    assert.ok(new THREE.Raycaster(new THREE.Vector3(...origin), new THREE.Vector3(...direction)).intersectObject(mesh).length > 0);
  }
  geometry.dispose(); material.dispose();
});

test("duplicates, null samples, zero field and sharp turns produce finite geometry without bridging gaps", () => {
  const points = [[0, 0, 0], [0, 0, 0], [0, 0, 1], [0, 0, 2], [5, 0, 0], [5, 0, 1], [5, 0, 0.5]];
  const geometry = makeMagneticTubeGeometry(points, [1, 1, 0, null, 1, 1, 1], colours(points.length), options);
  assert.equal(geometry.userData.tube.chains, 2);
  assert.ok(geometry.attributes.position.array.every(Number.isFinite));
  assert.ok(geometry.attributes.normal.array.every(Number.isFinite));
  const p = geometry.attributes.position, indices = geometry.index.array;
  for (let i = 0; i < indices.length; i += 3) {
    const xs = [p.getX(indices[i]), p.getX(indices[i + 1]), p.getX(indices[i + 2])];
    assert.ok(Math.max(...xs) - Math.min(...xs) < 1, "unknown span is not connected");
  }
  assert.equal(makeMagneticTubeGeometry([[0, 0, 0], [0, 0, 1]], [0, 0], colours(2), options), null);
  const actualBytes = Object.values(geometry.attributes).reduce((sum, a) => sum + a.array.byteLength, geometry.index.array.byteLength);
  assert.ok(estimateTubeBytes([{ points }], 8) >= actualBytes);
  geometry.dispose();
});

test("reference strength uses raw B magnitudes and ignores missing values", () => {
  assert.equal(peakLineStrength([{ strength: [null, 2, 4] }, { strength: [1, 3, NaN] }]), 4);
  assert.equal(peakLineStrength([{ points: [[0, 0, 0]] }]), 0);
});

const simplifyOptions = { enabled: true, positionTolerance: 0.0005, energyTolerance: 0.01 };

function assertApproximation(source, reduced, tolerance = simplifyOptions) {
  const indices = new Map(source.points.map((p, i) => [p, i]));
  const distances = [0];
  for (let i = 1; i < source.points.length; i++) {
    distances[i] = distances[i - 1] + Math.hypot(...source.points[i].map((v, axis) => v - source.points[i - 1][axis]));
  }
  const peak = Math.max(...source.strength);
  for (let j = 1; j < reduced.points.length; j++) {
    const a = indices.get(reduced.points[j - 1]), b = indices.get(reduced.points[j]);
    for (let i = a + 1; i < b; i++) {
      const t = (distances[i] - distances[a]) / (distances[b] - distances[a]);
      const error = Math.hypot(...[0, 1, 2].map(axis => source.points[i][axis]
        - ((1 - t) * source.points[a][axis] + t * source.points[b][axis])));
      assert.ok(error <= tolerance.positionTolerance + 1e-12, `shape error ${error}`);
      const actual = (source.strength[i] / peak) ** 2;
      const interpolated = (1 - t) * (source.strength[a] / peak) ** 2 + t * (source.strength[b] / peak) ** 2;
      assert.ok(Math.abs(actual - interpolated) <= tolerance.energyTolerance * Math.max(actual, interpolated, 1e-12) + 1e-14,
        `B² error at ${i}`);
    }
  }
}

test("simplification reduces straight tubes, preserves exact endpoints and metadata, and switches off losslessly", () => {
  const line = { line_id: 7, paired_shell_line_id: 7, polarity: -1, type: "exterior",
    points: Array.from({ length: 1001 }, (_, i) => [0, 0, i / 1000]),
    strength: Array.from({ length: 1001 }, (_, i) => Math.sqrt(1 + i / 1000)) };
  const before = JSON.stringify(line);
  assert.equal(simplifyMagneticLine(line, { enabled: false }), line);
  const reduced = simplifyMagneticLine(line, simplifyOptions);
  assert.equal(reduced.points.length, 2);
  assert.equal(reduced.points[0], line.points[0]);
  assert.equal(reduced.points.at(-1), line.points.at(-1));
  assert.equal(reduced.line_id, 7); assert.equal(reduced.paired_shell_line_id, 7);
  assert.equal(reduced.polarity, -1);
  assert.equal(JSON.stringify(line), before);
  assertApproximation(line, reduced);
  assert.ok(estimateTubeBytes([reduced], 8) < estimateTubeBytes([line], 8) / 100);
});

test("curved tubes obey both shape and local B² error bounds, including weak-field portions", () => {
  const line = { points: [], strength: [] };
  for (let i = 0; i <= 4000; i++) {
    const t = 2 * Math.PI * i / 4000;
    line.points.push([Math.cos(t), Math.sin(t), t / 5]);
    line.strength.push(0.005 + (1 + Math.sin(4 * t)) ** 2);
  }
  const reduced = simplifyMagneticLine(line, simplifyOptions);
  assert.ok(reduced.points.length < line.points.length / 4);
  assert.equal(Math.max(...reduced.strength), Math.max(...line.strength));
  assert.equal(Math.min(...reduced.strength), Math.min(...line.strength));
  assertApproximation(line, reduced);
});

test("simplification retains narrow magnetic peaks, zero fields, return bends and closed loops", () => {
  const spike = { points: Array.from({ length: 201 }, (_, i) => [0, 0, i / 200]),
    strength: Array.from({ length: 201 }, (_, i) => i === 99 ? 30 : i === 101 ? 0 : 1) };
  const reduced = simplifyMagneticLine(spike, simplifyOptions);
  assert.ok(reduced.points.includes(spike.points[99]));
  assert.ok(reduced.points.includes(spike.points[101]));
  assertApproximation(spike, reduced);
  const returning = { points: [[0, 0, 0], [0, 0, 2], [0, 0, 1], [0, 0, 3]], strength: [1, 1, 1, 1] };
  assert.equal(simplifyMagneticLine(returning, simplifyOptions), returning);
  const closed = { points: [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 0]], strength: [1, 1, 1, 1] };
  assert.equal(simplifyMagneticLine(closed, simplifyOptions), closed);
});

test("simplification preserves missing-strength separators and avoids overflow for large B", () => {
  const line = { points: Array.from({ length: 101 }, (_, i) => [0, 0, i]),
    strength: Array.from({ length: 101 }, (_, i) => i === 50 ? null : 1e300) };
  const reduced = simplifyMagneticLine(line, simplifyOptions);
  assert.deepEqual(reduced.points, [line.points[0], line.points[49], line.points[50], line.points[51], line.points[100]]);
  const geometry = makeMagneticTubeGeometry(reduced.points, reduced.strength, colours(reduced.points.length),
    { ...options, reference: 1e300 });
  assert.equal(geometry.userData.tube.chains, 2);
  assert.ok(geometry.attributes.position.array.every(Number.isFinite));
  geometry.dispose();
});
