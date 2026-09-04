# Validation report

## Completed checks

### Syntax and CLI

- Python compilation succeeded for both converters, `modules.py`, and the test suite.
- `--help` was exercised for both converters using import-only `shtns`/`pyxshells` stubs.
- Both CLIs expose `--emf`, `--induction`, `--geometry`, and `--fluid-inner-radius`.

### Regression tests

`tests/test_converter_package.py` completed with 9/9 tests passing:

- full-fluid-sphere geometry;
- conducting-inner-core geometry;
- ordinary shell geometry;
- protection against misclassifying regular centre decay as a solid core;
- EMF cross-product component signs;
- analytic vector-curl test for solid rotation;
- direct comparison of `modules.curl_spat` with an independent spherical-curl implementation;
- common viewer-field contract;
- common CLI options and metadata contract.

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

## Environment limitation

Real `shtns` and `pyxshells` libraries were not installed in the packaging environment. Therefore, the final package was validated with:

- mathematical and numerical real-space tests;
- the supplied state file plus a lightweight SHTns test backend;
- a synthetic XSHELLS backend;
- syntax and CLI checks.

The spectral transforms themselves retain the previously validated Leeds implementation in the supplied `modules.py`; no full production conversion against the real SHTns or pyxshells libraries was possible in this environment.
