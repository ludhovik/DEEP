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
