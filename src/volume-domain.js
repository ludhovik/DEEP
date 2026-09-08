// Valid radial support, including solid-core magnetism and fluid-only diagnostics.
export function fieldRadialDomain(metadata, coordinates, domain = {}, selection = "all") {
  const r = coordinates.r;
  let minimum = Number.isFinite(domain.r_min) ? domain.r_min : metadata.r_inner;
  let maximum = Number.isFinite(domain.r_max) ? domain.r_max : metadata.r_outer;
  const icb = Number(metadata.r_icb ?? metadata.r_fluid_inner);
  if (domain.magnetic && Number.isFinite(icb) && icb > minimum) {
    if (selection === "inner-core") maximum = Math.min(maximum, icb);
    if (selection === "fluid") minimum = Math.max(minimum, icb);
  }
  const tolerance = 1e-9 * Math.max(1, metadata.r_outer);
  const start = r.findIndex(value => value >= minimum - tolerance);
  let end = r.length - 1;
  while (end >= 0 && r[end] > maximum + tolerance) end--;
  return { start: Math.max(0, start), end,
    rMin: r[Math.max(0, start)], rMax: r[end],
    empty: start < 0 || end <= start };
}
