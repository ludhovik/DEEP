# Calypso converter

Convert native Calypso spectral restarts to the same DEEPscope bundle used by
Leeds, XSHELLS and MagIC. The converter reads merged ASCII `*.fst` and binary
`*.fsb` files, including native `*.fst.gz` / `*.fsb.gz`, with their original controls.
It reconstructs physical fields directly from the spectral coefficients.

## Quick start with the supplied shell archive

Extract `shell-20260909T101138Z-1-001.zip` first. Keep `control_MHD`,
`sph_lm63r72c_6/control_resolution`, and `rst_6/` in their original relative
locations inside `shell/dynamobench_case_1`.

```bash
python3 -m pip install -r requirements-calypso.txt

python3 tools/convert_calypso_to_viewer.py \
  --folder shell/dynamobench_case_1 \
  --out public/data_calypso \
  --incremental \
  --emf --induction \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --line-seeds 360 \
  --external-rmax 40 --external-nr 192 \
  --line-max-steps 4000
```

Adjust only the input folder if the archive was extracted elsewhere. Open
`public/data_calypso` in the viewer. The latest available restart is selected
by default: step 1 in this archive. Add `--state-number 0` for the initial
benchmark, or give an explicit `--state /path/to/rst.1.fst --control
/path/to/control_MHD`.

The default retains all source degrees and the native angular resolution.
For this L=63 example, `--spectral-lmax 32` reduces the angular grid from
96 × 192 to 34 × 66. A cutoff of 128 would not reduce this dataset.

To export both supplied steps as a sequence, use the same command with:

```text
--sequence-first 0 --sequence-last 1 --sequence-step 1
```

Every requested step must exist. The converter does not invent missing
timesteps. Root and per-frame `view.DTV2` files survive incremental updates.

## Full-sphere binary restart

For the supplied `full_sphere/sph_shell_842` run, use that folder with the
same export options. The reader discovers `rst_48/rst.99.fsb.gz` through
`control_MHD`. No manual decompression or control-file edits are needed.

The native `half_Chebyshev` grid has positive radii
`r_k = r_CMB sin(pi k / (2 N))`, `k=1..N`, where `N=num_fluid_grid_ctl`.
The origin is stored separately on the MPI rank owning the l=m=0 mode.
Thus 192 spectral radial nodes become 193 exported radial coordinates,
including one centre. This grid type is automatically classified full-sphere.
Keep the native `half_Chebyshev` label; substituting ordinary `Chebyshev`
would assign different radii to the spectral coefficients.

The restart filename counts saved outputs, not solver timesteps. Use index
99 with `--state-number` or sequence controls for this file. Its metadata
records `state_number=99`, `calypso.simulation_step=990000`, and time≈2.475.

Binary input follows native `field_block_MPI_IO_b` and
`gz_field_block_MPI_IO_b`: four-byte UNIX byte-order marker, 64-bit integers
and reals, 255-byte field labels, and rank-local Fortran `(node, component)`
blocks. Native gzip files contain separate members for header blocks and MPI
rank data, plus compressed-byte offsets. The reader validates those offsets,
block sizes, CRCs, node counts and finite values. Both byte orders are supported.
Wrapping an ordinary `.fsb` file in a single gzip stream is a different layout
from native `merged_bin_gz` and is not supported.

## Options and output

The Calypso and MagIC entry points share the same argument definitions and
physical-field export pipeline. Run `--help` for the complete list.

- Native spectral truncation, with `--spectral-lmax 0` retaining everything;
  radial/colatitude/longitude downsampling preserves physical boundaries.
- Velocity `ur`, `ut`, `up`, cylindrical `us`, `uz`, speed and helicity.
- Magnetic `Br`, `Bt`, `Bp`, strength, azimuthal means and fluctuations.
- Temperature as canonical `C`, composition as `Comp`, and pressure as `P`
  when present; scalar means/fluctuations, full and fluctuating gradients.
  `Cnom0`/`Compnom0` are the canonical fluctuation names, without duplicate
  `C_nom0`/`Comp_nom0` files.
- `N2` and `N2_full` when buoyancy and rotation coefficients can be resolved.
- Optional `--emf` and `--induction`, CMB/Earth magnetic maps, internal and
  exterior field lines with connected return branches, pairing identifiers
  and field strengths usable by the viewer's B² tubes.
- `--incremental`, `--cache-dir`, `--force`, sequences, validated atomic
  publication and previous-output backups.
- Full-sphere centre handling and resolved inner-core magnetic volumes.
  `--inner-core-only` refreshes core metadata of a source-verified existing
  Calypso bundle without recalculating outer-core data. The initial conversion
  already includes all stored magnetic radii below the ICB.

`--no-gradients`, `--no-m0-fields`, `--skip-field-lines`, geometry checks,
parameter overrides, exterior-grid and tracing controls work as in the
existing converters. As for MagIC, the potential-field tangential signs are
fixed by the analytic formula; `--external-btheta-sign` is accepted only for
command compatibility. `--modules-dir` is a compatibility option; this reader does not use `modules.py`.
Missing dimensionless parameters are prompted interactively, as in the other
converters; `--no-parameter-prompt` disables these prompts. Native momentum
coefficients retain their N2 convention; answers only fill absent factors, while
explicit Rayleigh CLI overrides retain their documented overriding behaviour.

Outputs include little-endian float32 volumes in `(r, theta, phi)` order,
`metadata.json`, `coordinates.json`, `profiles.json`, requested surface maps
and magnetic-line JSON files. Absent magnetic/compositional inputs are not
fabricated. A thermal convection restart without magnetic fields is usable.

### Incremental conversion

Use `--incremental` from the first run. Native reads, individual spectral
transforms and shared expensive diagnostics are cached losslessly outside
the published data folder. Adding `--emf`, `--induction` or changing line
settings reuses matching field transforms. An identical validated bundle is
skipped. Input, grid, truncation or algorithm changes invalidate affected
calculations. Output assembly, checksum reads and file writes can still run.
An older output without a calculation cache needs one initial cache-building
run. Never reconstruct new diagnostics from downsampled `.f32` files.

## Native format and mathematical conventions

The restart does not store its radial coordinates or harmonic index map.
The matching control files are therefore required. The reader follows the
active native routines in
[Calypso](https://github.com/geodynamics/calypso) and
[Kemorin](https://github.com/hirokemono/Kemorin_MHD):
`zonal_wavenumber_4_legendre.f90`, `set_sph_tranform_ordering.f90`,
`copy_rj_phys_data_4_IO.f90`, and the Schmidt/Legendre transforms.

The standard `cyclic_eq_mode` decomposition orders signed m from positive
to negative within each horizontal domain and l from |m| upward. Radial
subdomains partition those mode lists. The converter validates every MPI
node count and every field's byte offsets before reconstructing fields.
It uses Schmidt semi-normalized real harmonics without the Condon–Shortley
phase: positive m multiplies cosine; negative m multiplies sine.

Three-component spectral restart variables contain **P, T, dP/dr**, in that
order. They are not Cartesian or spherical vector samples. For either
velocity or magnetic field, with Y denoting each real harmonic:

```math
V_r=\sum_{\ell,m}\frac{\ell(\ell+1)}{r^2}P_{\ell m}Y_{\ell m},
```

```math
V_\theta=\frac1r\sum_{\ell,m}\left(P'_{\ell m}\partial_\theta Y_{\ell m}
+\frac{T_{\ell m}}{\sin\theta}\partial_\phi Y_{\ell m}\right),
\qquad
V_\phi=\frac1r\sum_{\ell,m}\left(\frac{P'_{\ell m}}{\sin\theta}\partial_\phi Y_{\ell m}
-T_{\ell m}\partial_\theta Y_{\ell m}\right).
```

The stored radial derivative is used directly. Scalars use
`f = sum(f_lm Y_lm)`. Cutoffs remove native modes before synthesis. Longitude
is uniformly sampled on `[0, 2π)`; colatitudes are the native Gauss nodes in
north-to-south order; radial coordinates increase outward.
The full-longitude grid has twice the meridional resolution, as in Calypso's
`set_global_sph_resolution`; the legacy `ngrid_zonal_ctl` entry is ignored by
the native code. A folded run uses a smaller sector FFT and is expanded to
the full longitude range for the viewer.

For a centre record, scalar values use the stored centre value. Vectors use
the regular l=1 limit estimated from `P_1m(r_first)/r_first²`, following the
native centre reconstruction. One Cartesian vector is projected onto each
spherical basis at r=0. Its accuracy depends on the nearest radial sample;
no singular division by zero is evaluated. The shared finite-difference
diagnostics retain the existing converters' centre approximations.

### Buoyancy normalization

Calypso permits products of named dimensionless numbers in its equations.
In particular `modified_Rayleigh` is not automatically the conventional
Rayleigh number used by the other converters. Native names and coefficients
are retained in `metadata.calypso`.

For the standard radial buoyancy terms in Calypso's momentum equation,
`c_v du/dt = ... + r(c_T T + c_C Comp) e_r - c_Omega e_z × u`, the converter
uses `Omega_* = c_Omega/(2 c_v)` and exports:

```math
\frac{N^2}{\Omega_*^2}
=\frac{r\left(c_T\,\partial_r T+c_C\,\partial_r\mathrm{Comp}\right)}
{c_v\,\Omega_*^2}.
```

`N2_full` includes the azimuthal mean; `N2` removes it. These are the signed
stratification diagnostics defined above, not a claim that every run uses
the same buoyancy units. If a coefficient cannot be resolved, its contribution
is omitted and availability is recorded. Explicit `--RaT`/`--RaC` overrides
instead use the other converters' `r Ek² RaT/Pr` or `r Ek² RaC/Sc` gradient
factor. The controls' thermal/compositional variables are used as stored;
an unstored conductive background is not invented.

## Supported inputs and current validation limits

- Merged ASCII and binary spectral restarts, including their native gzip
  variants. Rank-local files and physical `*.fld` files are not converter
  inputs. Preserve the matching original controls.
- Standard `num_radial_domain_ctl` / `num_horizontal_domain_ctl` decomposition,
  horizontal RJ inner loop, `cyclic_eq_mode`, `original` or `simple` mode
  distribution; folded longitude symmetry is supported. Custom decomposition
  arrays and unknown ordering are rejected instead of guessed.
- Generated Chebyshev or equally spaced radial grids, including native
  extensions, and explicit `r_layer` grids with ICB/CMB indices. An explicit
  full-sphere `ICB=0` means the separate origin and requires
  `sph_coef_type_ctl with_center`.
- Generated full-sphere `half_Chebyshev` grids with zero ICB/minimum radius,
  no stored exterior extension, and default `increment_cheby_ctl=1`.
  Extended or adjusted half-Chebyshev grids require explicit native radial
  controls. This restriction concerns the source grid; `--external-rmax`
  still controls the separately calculated exterior magnetic field.
- Full-sphere geometry must follow the source's centre grid/boundary controls.
  `--geometry full-sphere` cannot turn an ordinary positive-radius shell into
  a full sphere. Inner-core output requires stored magnetic coefficients at
  inner radii; no exterior potential model is substituted for them.

The supplied shell restarts have L=63 and a 73 × 96 × 192 grid. The initial
magnetic benchmark matches its analytic field to better than `4e-14` in all
components. At step 1, reconstruction matches the supplied independent
Cartesian physical snapshot on all owned MPI nodes within `5e-16` for
temperature, `9e-9` for velocity and `8e-8` for magnetic components. Tests
include non-axisymmetric phase, not only the axisymmetric dipole.

The supplied full-sphere `rst.99.fsb.gz` has L=31, 48 MPI ranks, 192 positive
radial nodes and a separate centre, with 108 × 216 angular nodes. Tests check
the native node stacks, binary layout and an independently addressed stored
centre temperature. A complete conversion exercises the real restart.
Analytic fixtures check full-sphere scalar/vector reconstruction, byte order,
multiple-rank layout, diagnostics and incremental reuse. This full-sphere
archive contains no independent physical snapshot, so it does not provide the
same point-by-point physical validation as the shell archive. Conducting-core
paths retain their analytic fixture coverage.

Run the ordinary tests with `npm run test-converters`. To repeat the optional
checks against this particular supplied archive:

```bash
CALYPSO_SAMPLE_DIR=/path/to/shell/dynamobench_case_1 \
  python3 tests/test_calypso_converter.py
```

```bash
CALYPSO_FULL_SPHERE_SAMPLE_DIR=/path/to/full_sphere/sph_shell_842 \
  python3 tests/test_calypso_binary.py
```
