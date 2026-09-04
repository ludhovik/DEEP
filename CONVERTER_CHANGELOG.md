# Changelog

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
