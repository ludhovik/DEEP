// One isotropic length conversion per dataset. Never warp a shell or its fields.
export function datasetPlacement(primary, secondary, settings = {}) {
  const positive = (value, label) => {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) throw new Error(`${label} must be a finite positive radius.`);
    return number;
  };
  const radius = (meta, role) => {
    const reference = Number(settings[`${role}NativeRadius`] ?? 0);
    if (!Number.isFinite(reference) || reference < 0) throw new Error(`${role} native reference radius must be zero (automatic) or positive.`);
    const native = positive(reference || meta.r_outer, `${role} native radius`);
    const physical = positive(settings[`${role}PhysicalRadius`] ?? 1, `${role} physical radius`);
    const factor = positive(physical / native, `${role} radius conversion`);
    return { native, physical, factor, inner: meta.r_inner * factor, outer: meta.r_outer * factor };
  };
  const p = radius(primary, "primary");
  const s = secondary ? radius(secondary, "secondary") : null;
  return { primary: p, secondary: s, secondaryScale: s ? positive(s.factor / p.factor, "Relative radius conversion") : 1 };
}

export function placementSummary(primary, secondary, settings = {}) {
  const placement = datasetPlacement(primary, secondary, settings);
  const unit = String(settings.placementUnit || "common units");
  const number = value => Number(value.toPrecision(7));
  const range = item => `${number(item.inner)}–${number(item.outer)} ${unit}`;
  const result = { primary: range(placement.primary), secondary: "Not loaded", interface: "" };
  if (!placement.secondary) return result;
  const p = placement.primary, s = placement.secondary;
  result.secondary = range(s);
  const tolerance = 1e-6 * Math.max(p.outer, s.outer);
  if (Math.abs(p.outer - s.outer) < tolerance && Math.abs(p.inner - s.inner) < tolerance) {
    result.interface = "Same sampled shell/sphere";
  } else {
    const [core, mantle] = p.outer < s.outer ? [p, s] : [s, p];
    const gap = mantle.inner - core.outer;
    result.interface = Math.abs(gap) < tolerance ? "Sampled boundaries meet"
      : `${gap > 0 ? "Gap" : "Overlap"}: ${number(Math.abs(gap))} ${unit} between inner-domain outer / outer-domain inner radii`;
  }
  return result;
}
