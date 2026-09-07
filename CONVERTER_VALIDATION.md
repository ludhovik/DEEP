# Validation report

## Incremental calculation reuse (3.5.0, 2026-09-07)

The complete converter suite passes 63 tests, including eleven new incremental
tests. These verify lossless float64 storage and copy-on-write cache reads,
SHA256-based source/output/entry checks, code revisions, explicit force,
corruption repair, and retention of published output and saved views on failure.

Leeds, XSHELLS and MagIC each run an initial conversion, add EMF and induction
with incremental reuse, then run a fresh comparison. All exported `.f32` files
match byte for byte, while native reader/transform calls are reused. The test
uses analytical input and native-backend fixtures with the actual diagnostics,
sampling, cache and bundle-validation code. It caught and corrected an XSHELLS
memory-layout-dependent rounding difference between fresh and cached arrays.

Dipole tests repeat actual internal/exterior tracing and return-footpoint
connection calculations through the cache, preserving geometry, status counts,
pairing identifiers and mutated exterior metadata. A MagIC sequence-extension
test converts only the added frame and preserves both root and per-frame views.
Leeds forwards the same incremental/cache/force options to its frame processes.

Compiled native backends and production snapshots were not available for these
new checks; this is not a production-simulation benchmark. Cache validation
still reads source and output bytes, and changed conversions still perform
uncached arithmetic, output assembly and I/O. Existing uncached bundles need an
initial conversion; native data are never reconstructed from viewer `.f32` files.

## Spectral truncation and return branches (3.4.0, 2026-09-06)

`bash run_converter_tests.sh` passes 52 tests: 37 package tests, nine exterior
tracing tests and six spectral projection tests.

- All three CLIs default to `--spectral-lmax 0`, accept positive cutoffs and
  reject negative degrees. Disabled cutoffs preserve the native data.
- Leeds tests verify exact retained coefficient remapping. XSHELLS tests cover
  maximum orders with symmetry factors 1 and 3, distinct fluid/magnetic radial
  domains, ghost rows, boundary flags, time and curl state.
- MagIC scalar tests retain the mean and low degrees while removing higher
  degrees. Vector tests verify coupled radial/spheroidal/toroidal projection,
  including non-axisymmetric modes and azimuthal symmetry. The normalized
  harmonic recurrence agrees with SciPy through degree/order 128 without
  high-order overflow.
- An end-to-end synthetic MagIC conversion with EMF and induction writes 60
  valid volume fields. A cutoff of 4 reduces its angular grid from 32 by 64
  to 6 by 10 while keeping all five radial samples. Every volume is smaller;
  this particular size ratio is a test case, not a promise for other inputs.
- Analytic dipole tests trace an inward branch from the exact returning
  exterior endpoint to the ICB. Its direction matches the exterior arc and
  variation in the dipole invariant `r/sin(theta)^2` is below `2e-5`.
  Reversing the simulation field triggers a reported polarity mismatch and
  produces no fabricated branch.
- The synthetic MagIC `both` export connects all eight closed exterior arcs
  to eight new internal return branches with exact matching JSON endpoints.

A separate integration check uses the actual classes from the official
[pyxshells 2.8 release](https://pypi.org/project/pyxshells/2.8/), with only the
SHTns coefficient layout substituted. It verifies exact scalar/poloidal/
toroidal coefficient retention, including radial ghost rows, for symmetry
factors 1 and 3. This caught the upstream `copy_data_from` NumPy 2 failure;
the converter instead copies by explicit degree/order indices.

Native production snapshots and a compiled SHTns backend were unavailable
for this change. These analytic, interface and synthetic checks do not replace
a complete native Leeds/XSHELLS/MagIC run. Convert one frame into a new output
folder, inspect `spectral_truncation` and `return_connection_counts`, and check
the resulting figure before starting a long sequence. A return branch is one
finite internal trace; later CMB crossings are not recursively extended.

## Exterior tracing correction (3.3.1, 2026-09-06)

All three converters use the corrected common exterior grid and tracer.
`bash run_converter_tests.sh` runs 33 package tests and eight dedicated
exterior-tracing tests. `npm run test-converters` discovers both suites.

The new tests exercise the numerical interpolation and RK4 implementation on
analytic arrays, without replacing the integrator or interpolator:

- `rmax=40`, 96 radial points and degree 128: the automatic CMB step is the
  same as for `rmax=2.5`, with monotonically increasing radial samples clustered
  near the CMB. Doubling radial resolution reduces the tested degree-128
  near-surface radial interpolation error by more than a factor of three.
- Dipole arcs from colatitudes 10, 60, 70, 89.5 and 120 degrees return to the
  CMB. The 10-degree arc extends beyond 33 CMB radii. The 89.5-degree loop rises
  only about `7.6e-5` CMB radii, and is retained even with an explicitly coarse
  requested step after short-arc refinement. Relative variation in
  `r/sin(theta)^2` is below `2e-5` for the tested arcs.
- A paired seed whose norm rounds just below the CMB is accepted, with its
  original Cartesian coordinates preserved exactly in the exported first
  point. Real boundary crossings remain rejected by the interpolator.
- For the mixed potential `V=cos(theta)/r^2 + 0.4*P2(cos(theta))/r^3`, the
  analytic flux function `sin(theta)^2*(1/r + 0.6*cos(theta)/r^2)` varies by
  less than 0.2% along the tested trace. Increasing exterior radial samples
  from 96 to 192 reduces this error by more than a factor of two.
- Outer-radius termination, step-budget exhaustion, successful closure, and
  skipped seeds are distinguished. Input seed counts reconcile with actual
  traced and skipped counts.
- An end-to-end synthetic MagIC conversion with `both` mode and `rmax=40`
  writes a validated bundle with paired shell/exterior coordinates and
  consistent diagnostics in its JSON files.

These checks establish regression and analytic consistency, not accuracy for
every simulation spectrum. The reported Leeds `state04086.cdf.dat` was not
available for this correction, so its new retained-line count has not been
measured. Use the native converter on one frame, inspect termination counts,
and compare radial/step refinement before reconverting a complete sequence.

## Completed checks

### Syntax and CLI

- Python compilation succeeded for all three converters, `modules.py`, and the test suite.
- `--help` was exercised using import-only dependency stubs where needed.
- The Leeds and XSHELLS CLIs expose the common `--emf`, `--induction`,
  `--geometry`, and `--fluid-inner-radius` options; MagIC exposes the equivalent
  field-line and geometry controls appropriate to native `G_*.tag` files.

### Regression tests

`tests/test_converter_package.py` completed with 31/31 tests passing for the
3.3 converter fixes. This suite uses synthetic/import-only backends where a
native simulation reader or SHTns is unavailable:

- full-fluid-sphere geometry;
- conducting-inner-core geometry;
- ordinary shell geometry;
- protection against misclassifying regular centre decay as a solid core;
- EMF cross-product component signs;
- analytic vector-curl test for solid rotation;
- direct comparison of `modules.curl_spat` with an independent spherical-curl implementation;
- common viewer-field contract;
- common CLI options and metadata contract.

The added regressions cover:

- SHTns-compatible Leeds longitudes;
- a non-axisymmetric MagIC `l=m=8` exterior harmonic, with relative component
  errors below `1e-11`, and analytic `m=1` pole limits;
- exact graphic-file number matching;
- retained CMB/ICB/radial endpoints, colatitude low-pass, and longitude
  anti-aliasing even for a stride that does not divide the sample count;
- a downsampled synthetic MagIC bundle with volume, CMB and Earth maps;
- absence of `Cnol0` and `Compnol0` from all new converter exports;
- rejecting NaN, infinity and float32 overflow without overwriting a file;
- CLI staging for all three converters, validation failures, a late sequence
  failure, and rollback after a failed publish rename;
- retained prior output/unrelated files and backups outside `public/` in a
  Git checkout.

### Magnetic field-line validation

The common field-line integrator and all three exterior reconstructions were
tested against the analytic axial dipole

```text
Br     = 2 M cos(theta) / r^3
Btheta = M sin(theta) / r^3
Bphi   = 0
```

For this field, `div(B)=0`, `curl(B)=0`, and each line obeys
`r/sin(theta)^2 = constant`. The tests verify:

- Leeds, XSHELLS, and MagIC reproduce the analytic exterior components;
- the SHTns spheroidal coefficient uses the required negative sign;
- positive/negative polarity is respectively outward/inward `Br` at the CMB;
- integration starts exactly at the requested CMB point;
- the first exterior integration step moves outward from the CMB;
- closed exterior traces return exactly to the CMB;
- the return footpoint has the opposite radial polarity for the test dipole;
- the dipole line invariant has relative spread below `2e-5`;
- paired internal/exterior JSON records use the same CMB coordinate exactly.

### Curl comparison

For a smooth three-component field on a spherical shell, excluding derivative-boundary planes, the maximum absolute component differences between:

- the requested `modules.curl_spat` formulation; and
- the independent explicit spherical-curl implementation retained in the Leeds converter

were:

```text
curl_r      8.88e-15
curl_theta  6.80e-15
curl_phi    5.77e-15
```

The full-sphere interior comparison also agreed at approximately `8e-15`, and the `r=0` output from `modules.curl_spat` remained finite.

### Leeds smoke conversions

A supplied full-sphere Leeds state was converted end to end with a lightweight SHTns test backend.

A magnetic variant verified that all optional fields were written:

```text
EMFr EMFt EMFp EMFabs
EMFr_fluct EMFt_fluct EMFp_fluct
Ir It Ip Iz Iabs
```

A synthetic conducting-inner-core variant verified:

- `physical_geometry = spherical_shell_conducting_inner_core`;
- nonzero magnetic field inside the ICB;
- derivative-stencil leakage confined to the configured validation buffer;
- velocity output exactly zero below the output ICB index;
- optional EMF and induction export completed.

### XSHELLS smoke conversion

A synthetic `pyxshells` backend with:

- magnetic grid `0 <= r <= 1`;
- fluid grid `0.4 <= r <= 1`;
- nonzero B below `r=0.4`

verified:

```text
physical_geometry = spherical_shell_conducting_inner_core
r_icb = 0.4
has_conducting_inner_core = true
```

The complete common velocity, magnetic, scalar, gradient, N2, EMF, and induction outputs were written on the magnetic master grid, with fluid-only fields zero below the ICB.

### MagIC smoke conversion

A synthetic MagIC `MagicGraph` backend verified native descending-radius and
azimuthal-symmetry layout adaptation, low-degree surface reconstruction, and an
end-to-end binary/metadata output contract compatible with the viewer.

## Environment limitation

Real `shtns` and `pyxshells` libraries were not installed in the packaging environment. Therefore, the final package was validated with:

- mathematical and numerical real-space tests;
- the supplied state file plus a lightweight SHTns test backend;
- a synthetic XSHELLS backend;
- syntax and CLI checks.

The spectral transforms retain the previously validated Leeds coefficient
conventions in `modules.py`, with the longitude-coordinate correction described
above. No full production conversion against real SHTns or pyxshells libraries
was rerun for the 3.3 fixes. Earlier smoke-conversion notes record previous
validation and do not substitute for rerunning a user's native snapshots.
