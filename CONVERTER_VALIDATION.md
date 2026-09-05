# Validation report

## Completed checks

### Syntax and CLI

- Python compilation succeeded for all three converters, `modules.py`, and the test suite.
- `--help` was exercised using import-only dependency stubs where needed.
- The Leeds and XSHELLS CLIs expose the common `--emf`, `--induction`,
  `--geometry`, and `--fluid-inner-radius` options; MagIC exposes the equivalent
  field-line and geometry controls appropriate to native `G_*.tag` files.

### Regression tests

`tests/test_converter_package.py` completed with 15/15 tests passing:

- full-fluid-sphere geometry;
- conducting-inner-core geometry;
- ordinary shell geometry;
- protection against misclassifying regular centre decay as a solid core;
- EMF cross-product component signs;
- analytic vector-curl test for solid rotation;
- direct comparison of `modules.curl_spat` with an independent spherical-curl implementation;
- common viewer-field contract;
- common CLI options and metadata contract.

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

The spectral transforms themselves retain the previously validated Leeds implementation in the supplied `modules.py`; no full production conversion against the real SHTns or pyxshells libraries was possible in this environment.
