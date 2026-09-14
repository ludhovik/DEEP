// Periodic longitude quadrature at fixed (r, theta). No latitude/volume weight.
export function longitudeWeights(phi, nphi) {
  if (!Number.isInteger(nphi) || nphi < 2) throw new Error("Need at least two longitudes.");
  if (phi == null) return new Float64Array(nphi).fill(1 / nphi);
  if (phi.length !== nphi) throw new Error("Longitude coordinate count does not match the volume.");
  const gaps = new Float64Array(nphi), period = 2 * Math.PI;
  for (let i = 0; i < nphi; i++) {
    if (!Number.isFinite(phi[i])) throw new Error("Longitude coordinates must be finite.");
    gaps[i] = i + 1 < nphi ? phi[i + 1] - phi[i] : phi[0] + period - phi[i];
    if (!(gaps[i] > 1e-10)) throw new Error("Longitudes must increase without a duplicate periodic seam.");
  }
  // Uniform grids use an arithmetic mean (allow coordinate roundoff in f32).
  const uniform = gaps.every(gap => Math.abs(gap - period / nphi) < 1e-6 * period / nphi + 1e-7);
  if (uniform) return new Float64Array(nphi).fill(1 / nphi);
  return Float64Array.from(gaps, (gap, i) => (gap + gaps[(i + nphi - 1) % nphi]) / (2 * period));
}

export function computeLongitudeAverage({ field, metadata, phi }, report = () => {}) {
  const { nr, ntheta, nphi } = metadata;
  if (![nr, ntheta, nphi].every(n => Number.isInteger(n) && n > 0)
      || field.length !== nr * ntheta * nphi) throw new Error("Volume dimensions do not match the field.");
  const weights = longitudeWeights(phi, nphi);
  // Keep the reduction in float64 to avoid discarding a small mean or fluctuation.
  const mean = new Float64Array(nr * ntheta);
  for (let row = 0; row < mean.length; row++) {
    let sum = 0, correction = 0;
    for (let ip = 0; ip < nphi; ip++) {
      const value = field[row * nphi + ip];
      if (!Number.isFinite(value)) throw new Error("Cannot average a volume with non-finite values.");
      const term = value * weights[ip];
      const next = sum + term;
      correction += Math.abs(sum) >= Math.abs(term) ? (sum - next) + term : (term - next) + sum;
      sum = next;
    }
    mean[row] = sum + correction;
    if (row % ntheta === 0) report({ label: "Averaging longitude", fraction: row / mean.length });
  }
  report({ label: "Averaging longitude", fraction: 1 });
  return mean;
}

// Array identity distinguishes fields, sources and sequence frames. Weak keys
// release reductions with evicted source volumes; concurrent requests share work.
export class LongitudeAverageCache {
  constructor() { this.clear(); }
  clear() { this.entries = new WeakMap(); }
  get(field, metadata, phi, compute) {
    const dimensions = `${metadata.nr}/${metadata.ntheta}/${metadata.nphi}`;
    const cached = this.entries.get(field);
    if (cached?.phi === phi && cached.dimensions === dimensions) return cached.promise;
    const entries = this.entries;
    const entry = { phi, dimensions };
    entry.promise = Promise.resolve().then(compute).catch(error => {
      if (entries.get(field) === entry) entries.delete(field);
      throw error;
    });
    entries.set(field, entry);
    return entry.promise;
  }
}

export function longitudeDisplayField(field, mean, mode, nphi) {
  if (mode === "slice") return field;
  if (!["mean", "fluctuation"].includes(mode)) throw new Error(`Unknown meridian mode: ${mode}`);
  return { source: field, mean, mode, nphi, viewerDomain: field.viewerDomain };
}

export function volumeDisplayValue(field, index) {
  if (!field.mode) return field[index];
  const average = field.mean[Math.floor(index / field.nphi)];
  return field.mode === "mean" ? average : field.source[index] - average;
}

export function longitudeFieldLabel(fieldName, mode) {
  if (mode === "mean") return `⟨${fieldName}⟩φ`;
  if (mode === "fluctuation") return `${fieldName} − ⟨${fieldName}⟩φ`;
  return fieldName;
}
