import * as THREE from "three";

// Diameter encodes magnetic energy. Display limits are applied afterwards.
export function magneticTubeDiameter(strength, options) {
  if (typeof strength !== "number" || !Number.isFinite(strength) || strength < 0) return null;
  const { reference, diameter, minimum = 0, maximum } = options;
  if (!(reference > 0) || !Number.isFinite(reference) || !(diameter > 0)
      || !Number.isFinite(diameter) || !(minimum >= 0) || !Number.isFinite(minimum)
      || !(maximum >= minimum) || !Number.isFinite(maximum)) {
    throw new Error("Invalid B² tube diameter or reference strength.");
  }
  const ratio = strength / reference;
  return Math.max(minimum, Math.min(maximum, diameter * ratio * ratio));
}

export function peakLineStrength(lines) {
  let peak = 0;
  for (const line of lines) {
    if (!Array.isArray(line.strength)) continue;
    for (const value of line.strength) {
      if (typeof value === "number" && Number.isFinite(value) && value > peak) peak = value;
    }
  }
  return peak;
}

export function estimateTubeBytes(lines, sides) {
  // Includes normals, colours, 32-bit indices and end caps, before allocation.
  return lines.reduce((sum, line) => sum + (line.points?.length || 0) * (112 * sides + 96), 0);
}

// Approximate the saved polyline and its B² profile, never retracing the field.
// Both errors are checked at every source sample using cumulative arclength.
export function simplifyMagneticLine(line, options = {}) {
  if (!options.enabled || !Array.isArray(line.points) || !Array.isArray(line.strength)
      || line.points.length < 3) return line;
  const positionTolerance = Number(options.positionTolerance);
  const energyTolerance = Number(options.energyTolerance);
  if (!(positionTolerance > 0) || !Number.isFinite(positionTolerance)
      || !(energyTolerance > 0 && energyTolerance <= 1)) {
    throw new Error("Tube simplification tolerances must be positive and finite.");
  }
  const points = line.points, strength = line.strength, count = points.length;
  const keep = new Uint8Array(count);
  const distance = new Float64Array(count);
  const energy = new Float64Array(count);
  const valid = i => Array.isArray(points[i]) && points[i].length >= 3
    && Number.isFinite(points[i][0]) && Number.isFinite(points[i][1]) && Number.isFinite(points[i][2])
    && typeof strength[i] === "number" && Number.isFinite(strength[i]) && strength[i] >= 0;

  const simplifyChain = (first, last) => {
    keep[first] = keep[last] = 1;
    if (last - first < 2) return;
    let peak = 0, peakIndex = first, minimumIndex = first;
    distance[first] = 0;
    for (let i = first; i <= last; i++) {
      if (strength[i] > peak) { peak = strength[i]; peakIndex = i; }
      if (strength[i] < strength[minimumIndex]) minimumIndex = i;
      if (i > first) distance[i] = distance[i - 1] + Math.hypot(
        points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1], points[i][2] - points[i - 1][2]);
    }
    if (!Number.isFinite(distance[last])) {
      keep.fill(1, first, last + 1);
      return;
    }
    // Normalization avoids overflow when squaring large magnetic strengths.
    for (let i = first; i <= last; i++) energy[i] = peak > 0 ? (strength[i] / peak) ** 2 : 0;
    const anchors = [...new Set([first, minimumIndex, peakIndex, last])].sort((a, b) => a - b);
    const stack = [];
    for (let i = 1; i < anchors.length; i++) {
      keep[anchors[i - 1]] = keep[anchors[i]] = 1;
      stack.push([anchors[i - 1], anchors[i]]);
    }
    while (stack.length) {
      const [a, b] = stack.pop();
      if (b - a < 2) continue;
      const length = distance[b] - distance[a];
      let worst = 1, split = -1;
      for (let i = a + 1; i < b; i++) {
        const t = length > 0 ? (distance[i] - distance[a]) / length : (i - a) / (b - a);
        const spatialError = Math.hypot(
          points[i][0] - ((1 - t) * points[a][0] + t * points[b][0]),
          points[i][1] - ((1 - t) * points[a][1] + t * points[b][1]),
          points[i][2] - ((1 - t) * points[a][2] + t * points[b][2]));
        const interpolatedEnergy = (1 - t) * energy[a] + t * energy[b];
        const energyError = Math.abs(energy[i] - interpolatedEnergy)
          / (energyTolerance * Math.max(energy[i], interpolatedEnergy, 1e-12));
        const error = Math.max(spatialError / positionTolerance, energyError);
        if (error > worst) { worst = error; split = i; }
      }
      if (split >= 0) {
        // Balanced splits bound work by O(n log n), even for very noisy input.
        const margin = Math.max(1, Math.floor((b - a) / 4));
        split = Math.max(a + margin, Math.min(b - margin, split));
        keep[split] = 1;
        stack.push([a, split], [split, b]);
      }
    }
  };

  let first = 0;
  for (let i = 0; i <= count; i++) {
    if (i < count && valid(i)) continue;
    if (i > first) simplifyChain(first, i - 1);
    if (i < count) keep[i] = 1; // Retain missing-data separators: never bridge gaps.
    first = i + 1;
  }
  const indices = [];
  for (let i = 0; i < count; i++) if (keep[i]) indices.push(i);
  if (indices.length === count) return line;
  return { ...line, points: indices.map(i => points[i]), strength: indices.map(i => strength[i]) };
}

export function makeMagneticTubeGeometry(points, strengths, vertexColors, options) {
  const sides = Math.round(options.sides ?? 8);
  if (!Number.isInteger(sides) || sides < 3 || sides > 16) throw new Error("Tube sides must be between 3 and 16.");
  const chains = [];
  let chain = [];
  const flush = () => {
    if (chain.length > 1 && chain.some(p => p.radius > 0)) chains.push(chain);
    chain = [];
  };
  const epsilon2 = (1e-10 * (options.lengthScale || 1)) ** 2;
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    const diameter = magneticTubeDiameter(strengths?.[i], options);
    if (!Array.isArray(p) || p.length < 3 || !p.slice(0, 3).every(Number.isFinite) || diameter === null) {
      // Do not bridge unknown geometry or interpret missing strengths as B=0.
      flush();
      continue;
    }
    const point = new THREE.Vector3(p[0], p[1], p[2]);
    if (chain.length && point.distanceToSquared(chain.at(-1).point) <= epsilon2) continue;
    chain.push({ point, radius: diameter / 2, color: vertexColors.slice(3 * i, 3 * i + 3) });
  }
  flush();
  if (!chains.length) return null;

  const vertices = chains.reduce((sum, c) => sum + c.length * sides + 2 * (sides + 1), 0);
  const indexCount = chains.reduce((sum, c) => sum + (c.length - 1) * sides * 6 + sides * 6, 0);
  const position = new Float32Array(vertices * 3);
  const color = new Float32Array(vertices * 3);
  const indices = new Uint32Array(indexCount);
  let vertex = 0, index = 0;
  const writeVertex = (point, rgb) => {
    position.set([point.x, point.y, point.z], vertex * 3);
    color.set(rgb, vertex * 3);
    return vertex++;
  };
  const triangle = (a, b, c) => { indices.set([a, b, c], index); index += 3; };

  for (const c of chains) {
    const start = vertex;
    let previousTangent = null, normal = null;
    const binormal = new THREE.Vector3();
    const rotation = new THREE.Quaternion();
    const offset = new THREE.Vector3();
    const ringPoint = new THREE.Vector3();
    for (let i = 0; i < c.length; i++) {
      const tangent = c[Math.min(i + 1, c.length - 1)].point.clone()
        .sub(c[Math.max(i - 1, 0)].point);
      if (tangent.lengthSq() <= epsilon2) tangent.copy(c[Math.min(i + 1, c.length - 1)].point).sub(c[i].point);
      tangent.normalize();
      if (previousTangent) {
        rotation.setFromUnitVectors(previousTangent, tangent);
        normal.applyQuaternion(rotation);
        normal.addScaledVector(tangent, -normal.dot(tangent)).normalize();
      } else {
        normal = new THREE.Vector3(...(Math.abs(tangent.z) < 0.9 ? [0, 0, 1] : [0, 1, 0]))
          .cross(tangent).normalize();
      }
      binormal.crossVectors(tangent, normal).normalize();
      for (let k = 0; k < sides; k++) {
        const angle = 2 * Math.PI * k / sides;
        offset.copy(normal).multiplyScalar(Math.cos(angle) * c[i].radius)
          .addScaledVector(binormal, Math.sin(angle) * c[i].radius);
        writeVertex(ringPoint.copy(c[i].point).add(offset), c[i].color);
      }
      previousTangent = tangent;
    }
    for (let i = 0; i < c.length - 1; i++) {
      for (let k = 0; k < sides; k++) {
        const a = start + i * sides + k, b = start + i * sides + (k + 1) % sides;
        const d = b + sides, e = a + sides;
        if (c[i].radius > 0) triangle(a, b, e);
        if (c[i + 1].radius > 0) triangle(b, d, e);
      }
    }
    for (const end of [0, c.length - 1]) {
      const centre = writeVertex(c[end].point, c[end].color);
      const ring = vertex;
      for (let k = 0; k < sides; k++) {
        const at = (start + end * sides + k) * 3;
        writeVertex(ringPoint.fromArray(position, at), c[end].color);
      }
      if (c[end].radius > 0) for (let k = 0; k < sides; k++) {
        const a = ring + k, b = ring + (k + 1) % sides;
        if (end === 0) triangle(centre, b, a);
        else triangle(centre, a, b);
      }
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(color, 3));
  geometry.setIndex(new THREE.BufferAttribute(indices.subarray(0, index), 1));
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  geometry.userData.tube = { sides, chains: chains.length, reference: options.reference };
  return geometry;
}
