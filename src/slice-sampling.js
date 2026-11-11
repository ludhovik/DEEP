// Interpolation in the stored spherical coordinates, not in grid index space.
// Supports nonuniform radial/Gauss grids and the periodic longitude seam.
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

export function stencilValue(entries, valueAt) {
  if (!entries.length) return NaN;
  let result = 0;
  for (const [index, weight] of entries) result += weight * valueAt(index);
  return result;
}

// Cache the interpolation stencil so sequence frames/field changes use exactly
// the same samples as the first render (including compact longitude averages).
export function appendSliceStencil(indices, weights, entries) {
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
