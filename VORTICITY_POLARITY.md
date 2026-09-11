# Vorticity and local magnetic polarity

## Vorticity in all six converters

Leeds, XSHELLS, MagIC, Calypso, QuICC and Rayleigh now export the following
float32 volumes whenever velocity is present:

| Field | Definition |
| --- | --- |
| `vort_r` | Radial vorticity, omega_r |
| `vort_theta` | Colatitudinal vorticity, omega_theta |
| `vort_phi` | Azimuthal vorticity, omega_phi |
| `vort_s` | Cylindrical radial vorticity, omega_r sin(theta) + omega_theta cos(theta) |
| `vort_z` | Axial vorticity, omega_r cos(theta) - omega_theta sin(theta) |
| `vort_abs` | Magnitude, sqrt(omega_r² + omega_theta² + omega_phi²) |

For example, `vort_z_volume.f32` is available for slices and isosurfaces after
loading the converted folder. The existing helicity field remains available.
These six new fields contain the full velocity curl, including axisymmetric
contributions. They are not fluctuation-only diagnostics.

The calculation is relative vorticity in the source velocity's reference frame:

```math
\boldsymbol\omega=\nabla\times\mathbf u.
```

With theta the colatitude and phi the longitude:

```math
\begin{aligned}
\omega_r &= \frac{\partial_\theta(\sin\theta\,u_\phi)-\partial_\phi u_\theta}
                  {r\sin\theta},\\
\omega_\theta &= \frac{(\partial_\phi u_r)/\sin\theta-\partial_r(ru_\phi)}{r},\\
\omega_\phi &= \frac{\partial_r(ru_\theta)-\partial_\theta u_r}{r}.
\end{aligned}
```

Units are source velocity divided by source length (usually nondimensional).
The converter does **not** add planetary `2 Omega`; absolute vorticity in a
rotating-frame calculation would require that additional vector.

All six converters use the same second-order physical-space curl with periodic
longitude differentiation. Derivatives are evaluated after requested spectral
truncation and before output downsampling. This is a finite-difference diagnostic,
not an exact native spectral derivative; assess grid/cutoff convergence for
quantitative studies.

Only fluid samples enter the derivatives. Zero padding in a solid inner core
does not generate a spurious boundary curl, and field metadata excludes that
padding from the viewer's valid vorticity domain. At a full-sphere centre, the
nearest nonzero shell supplies a single Cartesian-vector estimate, projected
back onto the spherical basis. This is a finite regular approximation, not a
forced zero. Existing helicity retains its documented zero-centre convention.

## Magnetic field-line polarity colours

Choose **Magnetic field lines → Colour by → Local Br (along line)**.
This works with ordinary lines and B² tubes; tube diameter remains proportional
to magnetic energy density while colour encodes direction.

| Colour | Local meaning |
| --- | --- |
| Yellow | Br > 0: magnetic field points radially outward here |
| Blue | Br < 0: magnetic field points radially inward here |
| Grey | Br = 0 or a local value is unavailable/undefined |

This follows the outward-yellow/inward-blue visual convention used in
[Glatzmaier's magnetic-field visualizations](https://www.nas.nasa.gov/SC10/PDF/Datasheets/Glatzmaier_SaturnDynamo_demo.pdf).
The implementation explicitly uses `Br = B dot e_r`. A vector B has no single
scalar sign, and its magnitude is always nonnegative.

A field line can change colour along its length. A closed exterior arc generally
has both outward and inward portions. This colour is independent of the ordering
of the saved polyline points and independent of the direction used to trace it.
The yellow/blue legend is included in image exports when the legend is visible
and expanded. The **Starting CMB Br (whole line)** option instead assigns one colour to the
whole line based on its starting footpoint. Old view codes selecting `polarity`
keep that original meaning. New local-polarity selections survive DTV2 round trips.

Converters sample signed Br at every saved point and write a `radial_field`
array alongside `points` and `strength` in each field-line JSON record. Shell
and return-branch values come from the simulation; exterior values come from
the reconstructed current-free field, with the requested exterior cutoff.
Consequently, strong exterior truncation can change polarity near weak-field
CMB regions. Colour is sampled at vertices and interpolated over rendering
segments; it does not imply an exactly resolved zero-crossing between samples.
At r=0 the radial direction is undefined and the stored value is `null`.

Tube simplification preserves both samples surrounding every sign, zero or
missing-value transition and keeps radial samples aligned with the retained
points. Pairing identifiers and CMB endpoints remain unchanged.

Old bundles without `radial_field` still work with strength and CMB-start colours.
In local-polarity mode their unavailable samples appear grey; the legend explains
that reconversion is needed. The viewer never guesses local Br from the starting
polarity or from an unoriented curve tangent.

## Update existing datasets incrementally

Rerun your existing converter command, retaining its source/output paths and
field-line settings, with `--incremental` and the same cache directory. Use the
normal conversion command, rather than `--inner-core-only`. Do not add `--force`
or clear the calculation cache.

Completed compatible transforms, helicity, EMF and traced lines can be reused.
The new vorticity fields and per-point Br samples are added, then the bundle is
validated and published atomically. Sampling Br does not retrace the lines.
The curl correction described below can invalidate an affected cached induction
calculation, as it should. A second unchanged run skips the complete conversion.
Upload the updated JSON and float32 files too if your dataset is hosted remotely,
then reopen the dataset in the viewer.

The shared curl's pole fallback now replaces only nonfinite samples. Previously,
a missing centre value could cause a valid near-pole angular column at other radii
to be overwritten. This correction applies to the shared physical-space induction
curl as well as the new vorticity output.

## Validation

- Analytic solid-body rotation around all three Cartesian axes: curl(u) = 2 Omega,
  including a nonzero regular centre; refinement and unit-scaling checks.
- Irrotational radial flow: zero vorticity; nonfinite velocities rejected.
- Dipole polarity along an arc: both signs, invariance under reversed point order,
  reversal under B → -B, undefined centre represented as null.
- Real Three.js line/tube vertex colours, worker-built tubes, simplification,
  legend meaning, geometry cache keys and DTV2 round trips.
- Incremental upgrade from the previous converter: spectral synthesis, internal
  lines, external lines and return branches reused; six vorticity fields and
  local radial samples added without changing the traced paths.
- The public Rayleigh convection example converts to a validated 29-field bundle.

Run `python3 tests/test_vorticity_polarity.py`, `bash run_converter_tests.sh`,
`npm run test-viewer` and `npm run build` from the repository.

## Comparing line colours with the CMB

Use **Local Br (along line)** to compare each endpoint's sign with the CMB.
**Starting CMB Br (whole line)** deliberately keeps its starting colour even
when an exterior arc returns to the opposite polarity; it does not describe
local Br at that return. Existing view codes keep their selected mode.

Select the primary **Br** CMB field and a symmetric colour scale when comparing
signs. A low-degree CMB map, an exterior potential field with a different cutoff,
or a secondary dataset can have different zero crossings. Colour does not
necessarily encode sign on a manually shifted or min/max colour scale. The
viewer does not flip the physical Br sign to force agreement between these maps.

**Br > 0 colour** and **Br < 0 colour** set the two colours in both polarity modes.
Defaults are yellow and blue. They apply to lines, B² tubes, on-screen swatches,
export swatches and DTV2 view codes. Zero or unavailable local Br stays grey.
The CMB's own colour map is independent. This viewer update needs no reconversion
if the bundle already contains per-point `radial_field` samples.
