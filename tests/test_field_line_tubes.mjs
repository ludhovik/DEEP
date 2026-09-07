import assert from "node:assert/strict";
import test from "node:test";
import * as THREE from "three";
import { makeMagneticTubeGeometry, magneticTubeDiameter, peakLineStrength, estimateTubeBytes } from "../src/field-line-tubes.js";

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
