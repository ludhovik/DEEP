import * as THREE from "three";
import { buildSphericalIsosurface } from "./isosurface-geometry.js";
import { simplifyMagneticLine, estimateTubeBytes, makeMagneticTubeGeometry } from "./field-line-tubes.js";

export function packGeometry(geometry) {
  if (!geometry) return null;
  return { attributes: Object.fromEntries(Object.entries(geometry.attributes).map(([key, attribute]) =>
    [key, { array: attribute.array, itemSize: attribute.itemSize }])),
    index: geometry.index?.array || null, userData: geometry.userData,
    boundingSphere: geometry.boundingSphere ? {
      center: geometry.boundingSphere.center.toArray(), radius: geometry.boundingSphere.radius,
    } : null };
}

export function unpackGeometry(data) {
  if (!data) return null;
  const geometry = new THREE.BufferGeometry();
  for (const [key, attribute] of Object.entries(data.attributes)) {
    geometry.setAttribute(key, new THREE.BufferAttribute(attribute.array, attribute.itemSize));
  }
  if (data.index) geometry.setIndex(new THREE.BufferAttribute(data.index, 1));
  geometry.userData = data.userData || {};
  if (data.boundingSphere) geometry.boundingSphere = new THREE.Sphere(
    new THREE.Vector3().fromArray(data.boundingSphere.center), data.boundingSphere.radius);
  return geometry;
}

export function geometryTransferList(result) {
  const buffers = new Set();
  for (const data of Array.isArray(result) ? result : [result]) {
    if (!data?.attributes) continue;
    for (const attribute of Object.values(data.attributes)) buffers.add(attribute.array.buffer);
    if (data.index) buffers.add(data.index.buffer);
  }
  return [...buffers];
}

export function prepareTubeLines({ selected, settings, radius, limitBytes }, report = () => {}) {
  const automatic = settings.lineTubeSimplify && settings.lineTubeAutoDetail;
  const maxShape = settings.lineTubeAutoMaxShapeError;
  const maxEnergy = settings.lineTubeAutoMaxEnergyErrorPercent;
  if (automatic && (!(maxShape > 0 && maxShape <= 0.05) || !(maxEnergy > 0 && maxEnergy <= 20))) {
    throw new Error("Automatic tube error bounds must be positive: shape ≤ 0.05 ro, B² ≤ 20%.");
  }
  let shape = automatic ? Math.min(settings.lineTubeShapeError, maxShape) : settings.lineTubeShapeError;
  let energy = automatic ? Math.min(settings.lineTubeEnergyErrorPercent, maxEnergy) : settings.lineTubeEnergyErrorPercent;
  for (let attempt = 0; ; attempt++) {
    report({ label: automatic ? `Fitting tubes: trial ${attempt + 1}` : "Simplifying tubes" });
    const reduced = Object.fromEntries(Object.entries(selected).map(([mode, lines]) => [mode,
      lines.map(line => simplifyMagneticLine(line, { enabled: settings.lineTubeSimplify,
        positionTolerance: shape * radius, energyTolerance: energy / 100 }))]));
    const bytes = estimateTubeBytes(Object.values(reduced).flat(), settings.lineTubeSides);
    const result = { selected: reduced, bytes, shapeError: shape, energyErrorPercent: energy,
      automatic: Boolean(automatic) };
    if (!automatic || bytes <= limitBytes) return result;
    if ((shape >= maxShape && energy >= maxEnergy) || attempt >= 24) {
      throw new Error(`Automatic tube detail cannot fit ${(bytes / 1024 ** 2).toFixed(1)} MiB into ${(limitBytes / 1024 ** 2).toFixed(0)} MiB within the allowed errors. `
        + "Increase Line stride, reduce Tube sides, raise Tube memory, or increase the automatic error bounds.");
    }
    // Always simplify the original polylines, never a previous approximation.
    shape = Math.min(maxShape, shape * 2);
    energy = Math.min(maxEnergy, energy * 2);
  }
}

export function executeGeometryJob(type, payload, report = () => {}) {
  if (type === "isosurface") return packGeometry(buildSphericalIsosurface(payload, report));
  if (type === "prepare-tubes") return prepareTubeLines(payload, report);
  if (type === "tubes") return payload.lines.map((line, i) => {
    report({ label: "Building tubes", fraction: i / Math.max(1, payload.lines.length) });
    return line ? packGeometry(makeMagneticTubeGeometry(line.points, line.strength, line.colors, payload.options)) : null;
  });
  throw new Error(`Unknown geometry task: ${type}`);
}
