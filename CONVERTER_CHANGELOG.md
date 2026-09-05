# Changelog

## 3.2.0

- Fixed the exterior SHTns spheroidal sign analytically to
  `S_lm = -Q_lm/(l+1)` for current-free potential continuation.
- Removed appearance-based automatic sign selection; `auto` now means the
  documented analytic minus sign.
- Launch exterior integration exactly on the CMB instead of adding a radial
  offset segment.
- In `--field-line-mode both`, pair exterior seeds with the actual traced CMB
  intersections of internal lines and record shared line identifiers.
- Define polarity as the sign of `Br` at the starting CMB footpoint: positive is
  outward and negative is inward.
- Add analytic axial-dipole tests for all three continuations, the RK4 field-line
  invariant, exact CMB endpoints, polarity, and internal/exterior seed pairing.

## 3.0.0

- Aligned Leeds and XSHELLS canonical viewer fields and metadata contract.
- Added optional `--emf` and `--induction` output to both converters.
- Corrected the EMF radial component to `u_theta B_phi - u_phi B_theta`.
- Both converters now use the requested vector `modules.curl_spat` implementation.
- Added common `EMFabs`, `Iabs`, `us`, `uz`, helicity, m=0-removed fields, and phi averages.
- Standardized scalar gradients as physical spherical components.
- Separated Leeds full-radius transform geometry from physical fluid geometry.
- Added automatic Leeds detection of a shell with a conducting inner core when velocity is zero in an inner interval and magnetic field is present there.
- Added spatial validation and a three-point ICB stencil buffer.
- Preserved magnetic fields inside conducting inner cores while masking fluid-only outputs there.
- Restricted shell field-line tracing to the fluid domain.
- Added XSHELLS verification that B is nonzero below the fluid ICB.
- Preserved XSHELLS CMB/Earth fields and shell/exterior field-line functionality.
- Added regression and smoke-test documentation.
