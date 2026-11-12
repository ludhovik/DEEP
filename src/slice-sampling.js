// Interpolation in the stored spherical coordinates, not in grid index space.
// Supports nonuniform radial/Gauss grids and the periodic longitude seam.
import { longitudeWeights } from "./longitude-average.js";

// Only recognised smooth scalars and radial components have a unique value
// at a pole. In particular ut/up and Bt/Bp have longitude-dependent bases.
export function regularPoleField(name = "") {
  const base = name.replace(/_(?:phiavg|nom0|m0)$/, "");
  return ["ur", "Br", "T", "C", "Comp", "Tanomaly", "Canomaly"].includes(base);
}

function bracket(axis, value, first = 0, last = axis.length - 1) {
  if (value <= axis[first]) return [first, first, 0];
  if (value >= axis[last]) return [last, last, 0];
  let lo = first, hi = last;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (axis[mid] <= value) lo = mid; else hi = mid;
  }
  return [lo, hi, (value - axis[lo]) / (axis[hi] - axis[lo])];
}

export function createSliceSampler(r, theta, phi, domain) {
  const nt = theta.length, np = phi.length, period = 2 * Math.PI;
  const tolerance = 1e-7 * Math.max(1, Math.abs(domain.rMax));
  return (radius, colatitude, longitude) => {
    if (domain.empty || radius < domain.rMin - tolerance || radius > domain.rMax + tolerance) return [];
    const radial = bracket(r, radius, domain.start, domain.end);
    const lat = bracket(theta, colatitude);
    const p = longitude >= phi[0] && longitude < phi[0] + period ? longitude
      : ((longitude - phi[0]) % period + period) % period + phi[0];
    const lon = p > phi[np - 1]
      ? [np - 1, 0, (p - phi[np - 1]) / (phi[0] + period - phi[np - 1])]
      : bracket(phi, p);
    const entries = [];
    for (let a = 0; a < 2; a++) for (let b = 0; b < 2; b++) for (let c = 0; c < 2; c++) {
      const weight = (a ? radial[2] : 1 - radial[2]) * (b ? lat[2] : 1 - lat[2]) * (c ? lon[2] : 1 - lon[2]);
      if (weight > 0) entries.push([(radial[a] * nt + lat[b]) * np + lon[c], weight]);
    }
    return entries;
  };
}

// Add virtual polar samples without changing the stored volume. Negative
// indices encode (radial index, north/south), leaving cached stencils compact.
// Pole values are estimated from longitude means of the nearest two rings,
// linearly extrapolated in cos(theta). This is exact for a + b*cos(theta)
// and approximate for higher degrees; it is not a spectral reconstruction.
export function createPolarSliceSampler(r, theta, phi, domain, valueAt, regular = false) {
  const native = createSliceSampler(r, theta, phi, domain);
  if (!regular) return Object.assign(native, { valueAt, polePolicy: "native" });
  const nt = theta.length, np = phi.length, weights = longitudeWeights(phi, np);
  const poles = new Map();
  const polarIndex = (ir, south) => -(2 * ir + Number(south) + 1);
  const read = index => {
    if (index >= 0) return valueAt(index);
    if (poles.has(index)) return poles.get(index);
    const code = -index - 1, ir = Math.floor(code / 2), south = code % 2;
    const first = south ? nt - 1 : 0, second = nt < 2 ? first : south ? nt - 2 : 1;
    const mean = it => {
      let sum = 0;
      for (let ip = 0; ip < np; ip++) sum += weights[ip] * valueAt((ir * nt + it) * np + ip);
      return sum;
    };
    const a = mean(first), mu = Math.cos(theta[first]), target = south ? -1 : 1;
    const gap = Math.cos(theta[second]) - mu;
    const result = Math.abs(target - mu) < 1e-14 || Math.abs(gap) < 1e-14
      ? a : a + (mean(second) - a) * (target - mu) / gap;
    poles.set(index, result);
    return result;
  };
  const sample = (radius, colatitude, longitude) => {
    const south = colatitude >= theta[nt - 1];
    const outside = colatitude <= theta[0] || south;
    const boundary = south ? theta[nt - 1] : theta[0];
    const distance = south ? Math.PI - colatitude : colatitude;
    const gap = south ? Math.PI - boundary : boundary;
    const entries = native(radius, colatitude, longitude);
    if (!entries.length) return entries;
    if (outside) {
      const t = gap < 1e-14 ? 0 : Math.min(1, Math.max(0, distance / gap));
      // Match the native ring and converge to the same pole from every phi.
      const result = entries.map(([index, weight]) => [index, weight * t]).filter(([, weight]) => weight > 0);
      const radial = bracket(r, radius, domain.start, domain.end);
      for (let a = 0; a < 2; a++) {
        const weight = (a ? radial[2] : 1 - radial[2]) * (1 - t);
        if (weight > 0) result.push([polarIndex(radial[a], south), weight]);
      }
      return result;
    }
    // Datasets with explicit polar nodes also share a single axis value.
    return entries.map(([index, weight]) => {
      const ir = Math.floor(index / (nt * np)), it = Math.floor(index / np) % nt;
      if (it === 0 && theta[0] < 1e-14) return [polarIndex(ir, false), weight];
      if (it === nt - 1 && Math.PI - theta[it] < 1e-14) return [polarIndex(ir, true), weight];
      return [index, weight];
    });
  };
  return Object.assign(sample, { valueAt: read, polePolicy: "scalar-axis-v1" });
}

export function stencilValue(entries, valueAt) {
  if (!entries.length) return NaN;
  let result = 0;
  for (const [index, weight] of entries) result += weight * valueAt(index);
  return result;
}

// Cache the interpolation stencil so sequence frames/field changes use exactly
// the same samples as the first render (including compact longitude averages).
export function appendSliceStencil(indices, weights, entries) {
  if (entries.length > 8) throw new Error("Slice interpolation stencil exceeds eight samples.");
  for (let k = 0; k < 8; k++) {
    indices.push(entries[k]?.[0] ?? -1);
    weights.push(entries[k]?.[1] ?? 0);
  }
}

export function cachedSliceValue(indices, weights, vertex, valueAt) {
  let result = 0, valid = false;
  for (let k = vertex * 8; k < vertex * 8 + 8; k++) {
    if (weights[k] > 0) { result += weights[k] * valueAt(indices[k]); valid = true; }
  }
  return valid ? result : NaN;
}
