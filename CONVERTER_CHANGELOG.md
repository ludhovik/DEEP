# Changelog

## 3.5.0

- Add opt-in `--incremental` conversion to Leeds, XSHELLS and MagIC. Verify
  source, option, code, backend and output fingerprints before skipping a
  complete unchanged bundle.
- Cache selected native transforms/readers, gradients, diagnostics, surface
  synthesis and field-line calculations losslessly at their working precision.
  Changed conversions reuse matching calculations; viewer `.f32` files are
  never substituted for native data. Corrupt entries are recomputed.
- Store disposable caches outside published data, with `--cache-dir` for
  placement and `--incremental --force` for a full refresh. An existing bundle
  without a cache needs one initial calculation pass.
- Reuse unchanged Leeds and MagIC sequence frames while preserving root and
  frame views, validated staging and previous-output backups.
- Preserve tracing status counts and internal/exterior pairing metadata on
  cache hits. Normalize XSHELLS transform array layout so fresh and cached
  calculations give identical exported values.

## 3.4.2

- Remove the duplicate `C_nom0` and `Comp_nom0` fields and physical output
  files from all three converters; retain `Cnom0` and `Compnom0`.
- Remove the duplicate menu choices when loading older primary or secondary
  datasets, including aliases-only bundles. Translate old saved-view field
  selections to the canonical names without changing scientific values.

## 3.4.0

- Support `--spectral-lmax` in Leeds, XSHELLS and MagIC. Default 0 retains all
  source degrees; the Leeds default changes from 128 to 0.
- Reduce the angular synthesis grid with the retained degree. Preserve scalar
  means, radial samples and XSHELLS boundary/ghost coefficients. MagIC projects
  physical graphic samples using scalar and vector spherical harmonics.
- Resolve bundled `modules.py` for direct XSHELLS script invocation. Read and
  validate native angular layouts before sharing transforms; copy retained
  coefficients directly without pyxshells 2.8's NumPy 2-incompatible copy helper.
- In `both` mode, trace an additional internal branch from each closed exterior
  arc's return footpoint, using the actual simulation B in the same direction.
  Report boundary mismatches instead of fabricating connections.
- Group each original internal line, exterior arc and return branch for viewer
  stride selection. Existing bundles require reconversion for return branches.
- Add harmonic, coefficient-remapping, dipole-connection and synthetic export
  tests; record effective cutoffs and return-connection counts in metadata.

## 3.3.1

- Cluster exterior radial samples near the CMB and choose automatic tracing
  steps from the CMB radius and retained degree, across all three converters.
- Grow automatic steps farther from the CMB so long arcs remain practical.
- Refine short returning arcs instead of rejecting them for insufficient height.
- Tolerate roundoff at interpolation boundaries and preserve paired CMB seeds
  exactly, with termination and skipped-seed counts in export metadata.
- Add large-domain dipole, mixed-degree convergence and synthetic MagIC export
  regressions. Clarify absolute-radius units and the default `2.5*r_cmb` limit.

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
