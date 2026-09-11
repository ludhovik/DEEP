# Rayleigh converter

Convert Rayleigh snapshots into DEEPscope `metadata.json`, coordinates and
little-endian float32 volumes, with the same shared diagnostics, magnetic
field-line export and incremental cache used by the other converters.
The Rayleigh solver and its Python post-processing package are not required.

```bash
python3 -m pip install -r requirements-rayleigh.txt
python3 tools/convert_rayleigh_to_viewer.py --help
```

## A public example that has been converted and checked

The official [Rayleigh Sample Outputs](https://zenodo.org/records/13376792)
archive is about 9 MB. It contains the Christensen et al. (2001) case-0
**hydrodynamic convection** benchmark, including complete spectral checkpoints.
This example has velocity, a thermal scalar and pressure; it has no magnetic
field. Do not expect magnetic field lines or magnetic diagnostics from it.

From the DEEPscope repository:

```bash
mkdir -p "$HOME/Downloads/rayleigh-example"
curl -fL \
  "https://zenodo.org/api/records/13376792/files/benchmark_outputs.zip/content" \
  -o "$HOME/Downloads/rayleigh-example/benchmark_outputs.zip"
unzip "$HOME/Downloads/rayleigh-example/benchmark_outputs.zip" \
  -d "$HOME/Downloads/rayleigh-example"

python3 tools/convert_rayleigh_to_viewer.py \
  --checkpoint "$HOME/Downloads/rayleigh-example/benchmark_outputs/Checkpoints/00040000" \
  --out public/data_rayleigh_benchmark \
  --incremental \
  --cache-dir "$HOME/.cache/deepscope" \
  --skip-field-lines \
  --no-earth-br
```

Open `public/data_rayleigh_benchmark` with the viewer's folder picker. The
converter exports 29 volume fields from this checkpoint, including velocity,
thermal fields, pressure, helicity, vorticity and scalar gradients. N2 is omitted by
default because its nondimensionalization is model-dependent.

The reconstructed volume-averaged kinetic energy is **58.3478351**, within
0.0003% of the published benchmark value **58.348**. An independent comparison
with the archive's native Shell_Slices velocities gives relative L2 differences
below 0.012%; the slices precede the checkpoint by one timestep, so they are
not an exact same-time reference.

The optional downloaded-data regression test runs with:

```bash
RAYLEIGH_BENCHMARK_DIR="$HOME/Downloads/rayleigh-example/benchmark_outputs" \
  python3 tests/test_rayleigh_converter.py
```

## Supported input formats

### Full spectral checkpoints

Pass a checkpoint directory or its `grid_etc` file to `--checkpoint`/`--state`.
Keep the accompanying files together:

| Native file | Meaning | Viewer fields |
| --- | --- | --- |
| `W`, `Z` | Velocity mass-flux poloidal/toroidal potentials | `ur`, `ut`, `up` and derived fields |
| `C`, `A` | Magnetic poloidal/toroidal potentials | `Br`, `Bt`, `Bp` and derived fields |
| `T` | Stored thermal scalar | `T` |
| `P` | Stored pressure | `P` |
| Explicit `--composition-field Xa001` (or another scalar filename) | Selected composition scalar | `C` |
| `equation_coefficients` | Reference functions, including density | Used to reconstruct velocity |
| `main_input` | Model parameters and angular resolution | Metadata and model checks |

Native magnetic potential `C` is **not** the viewer's composition scalar `C`.
Only the selected composition scalar is converted; names are not guessed.
`--main-input FILE` overrides the automatically discovered control file.

This reader supports **stream checkpoint version 2, grid_type 2, single-domain
Chebyshev grids**, for Boussinesq and ordinary anelastic velocity potentials.
It checks the actual radial nodes before differentiating. Other checkpoint
layouts, multidomain grids, and compressible/pseudo-incompressible checkpoint
conventions are rejected with an instruction to export `Spherical_3D` instead.
It does not invent a conducting inner-core field where the source has none.
Full-fluid-sphere radial grids are supported when the stored potentials satisfy
the required regular centre limits; the public benchmark validates a shell.

Reference density must be present in `equation_coefficients`. If it is absent,
`--constant-density 1` is available **only when a unit reference density is
physically correct for the simulation**. It is never assumed silently. The
reader accepts ordinary version-1 (10 constants) and version-2 reference files;
unrecognized layouts fail rather than guessing a density.

### Spherical_3D physical snapshots

```bash
python3 tools/convert_rayleigh_to_viewer.py \
  --snapshot /path/to/run/Spherical_3D/00010000_grid \
  --out public/data_rayleigh \
  --incremental --cache-dir "$HOME/.cache/deepscope" \
  --spectral-lmax 128 \
  --emf --induction \
  --cmb-br-ltrunc 13 \
  --field-line-mode both --line-seeds 360 \
  --external-rmax 40 --external-nr 192 --line-max-steps 4000
```

Keep the matching `00010000_00001`, etc. beside `00010000_grid`. These are full
3-D fields; Shell_Slices, Equatorial_Slices, averages, spectra and archives
cannot substitute for a full snapshot. The grid and quantities must come from
the same output step. Each stored quantity is a headerless float64 array in
Fortran `(phi, theta, r)` order. Both byte orders are supported.

| Quantity code | Viewer field |
| --- | --- |
| 1, 2, 3 | `ur`, `ut`, `up` |
| 801, 802, 803 | `Br`, `Bt`, `Bp` |
| 501 | Thermal `T` (override with `--thermal-quantity`) |
| 502 | Pressure `P` |
| Explicit `--composition-quantity CODE` | Composition `C` |

Request the needed quantities using Rayleigh's `full3d_values` and an appropriate
`full3d_frequency`. Check the quantity lookup for your Rayleigh version/model.
An incomplete vector triplet is an error; a wholly absent vector or scalar is
omitted. EMF and induction require both velocity and magnetism.

Spherical_3D headers contain the iteration number but **no physical time**.
The converter records unknown time as JSON `null`, or accepts `--time VALUE`
for a single snapshot. It never treats an iteration number as a physical time.

## Shared options and incremental additions

The converter uses the existing export pipeline for:

- radial/angular downsampling and `--spectral-lmax` (default 0 keeps all);
- vector magnitudes, cylindrical velocity, azimuthal means/fluctuations,
  helicity and scalar gradients;
- `--emf` and `--induction`, with the same definitions as the other converters;
- low-degree CMB/Earth maps, internal/external magnetic field lines and connected
  return branches, line strength for B² tubes, and pairing identifiers for stride;
- geometry selection, physical-parameter overrides and optional N2;
- sequences, validated atomic bundle publication, preservation of `view.DTV2`,
  and `--incremental` with optional `--cache-dir`.

For checkpoints, angular modes above the requested cutoff are omitted before
synthesis. For Spherical_3D, the full physical snapshot must first be read;
scalar/vector harmonic projection then produces the reduced angular grid.
Native Gauss colatitudes are required for this projection. Radial samples remain
unchanged unless explicitly downsampled. Derived nonlinear fields are computed
from the retained source fields; compare cutoffs when assessing convergence.

Rerun the same command with `--incremental` to skip a validated unchanged bundle.
Adding `--emf --induction`, changing line settings or enabling another scalar
reuses eligible completed calculations. An interrupted calculation restarts;
completed cached calculations remain available. Changing source files or code
invalidates affected work. Keep the cache outside the output bundle and `public/`.

Use `--folder` for automatic latest-step discovery or a sequence:

```bash
python3 tools/convert_rayleigh_to_viewer.py \
  --folder /path/to/run/Checkpoints --input-format checkpoint \
  --sequence-first 10000 --sequence-last 40000 --sequence-step 10000 \
  --out public/data_rayleigh_sequence \
  --incremental --cache-dir "$HOME/.cache/deepscope"
```

Those example indices must actually exist. The step is the **saved output
cadence**, not necessarily one iteration. Use `--state-number` to select one
numbered snapshot. If a run contains both checkpoints and Spherical_3D files,
choose `--input-format checkpoint` or `--input-format spherical3d` explicitly.

`--external-rmax` uses the source radius units. The default Earth scaling and
an insulating potential exterior are visualization/model assumptions: choose
settings appropriate to the planetary or stellar simulation. A photospheric
magnetic field need not have a current-free exterior.

## Reconstruction and physical meaning

Let `Y_lm` be orthonormal complex spherical harmonics, with the Condon–Shortley
phase. Native checkpoints store one coefficient per `m >= 0`, ordered first by
`m`, then by `l`. Reconstruct the real field as

```math
f(r,\theta,\phi)=\Re\sum_{m\ge0}\sum_{\ell\ge m}f_{\ell m}(r)Y_{\ell m}(\theta,\phi).
```

There is **no additional factor of two for nonzero m** in Rayleigh checkpoint
coefficients. On the mapped native Chebyshev roots, each radial coefficient is
`c0/2 + sum(n>=1, cn Tn(x))`; the mapping reproduces the stored first/last radii.
Radial derivatives are taken analytically in this basis.

For velocity potentials `W,Z`,

```math
\rho_0\mathbf u=\nabla\times\nabla\times(W\mathbf e_r)
                   +\nabla\times(Z\mathbf e_r).
```

Thus each harmonic contributes

```math
\begin{aligned}
\rho_0u_r&=\ell(\ell+1)W_{\ell m}Y_{\ell m}/r^2,\\
\rho_0u_\theta&=[W'_{\ell m}\partial_\theta Y_{\ell m}
                 +Z_{\ell m}(im/\sin\theta)Y_{\ell m}]/r,\\
\rho_0u_\phi&=[W'_{\ell m}(im/\sin\theta)Y_{\ell m}
               -Z_{\ell m}\partial_\theta Y_{\ell m}]/r.
\end{aligned}
```

Magnetic reconstruction uses the same expressions with `W→C`, `Z→A`, and no
density division. All quantities remain in the source simulation's units;
background thermal/compositional profiles are not added. Helicity is
`u · curl(u)`, EMF is `u × B`, and the exported induction diagnostic is
`curl(u × B)`; it is not the complete magnetic time derivative including diffusion.

N2 is **off by default**. `--n2-convention deepscope` explicitly selects the
existing `r Ek² [(RaT/Pr) ∂r T + (RaC/Sc) ∂r C]` convention and requires finite
parameters for the available scalars. This is not a universal Rayleigh N2 formula:
anelastic gravity, entropy units and reference profiles may require another
normalization. Omit it unless that convention matches your model.

## Validation and sources

`python3 tests/test_rayleigh_converter.py` checks both byte orders, native
array layout, scalar normalization, uniform Cartesian magnetic fields along
all three axes, solid-body rotation, density division, centre limits, spectral
truncation, incremental additions, sequences and the shared magnetic line export.
The optional downloaded benchmark independently checks the kinetic energy by
radial quadrature and harmonic orthogonality. The full official checkpoint was
also converted and passed DEEPscope bundle validation.

- [Official Rayleigh repository](https://github.com/geodynamics/Rayleigh)
- [Rayleigh diagnostic plotting tutorial and benchmark values](https://rayleigh-documentation.readthedocs.io/en/latest/post_processing/Diagnostic_Plotting.html)
- [Official sample-output dataset](https://zenodo.org/records/13376792)

The reader follows `Checkpointing.F90`, `Sphere_Hybrid_Space.F90`,
`rayleigh_diagnostics.py`, `reference_tools.py` and `spectral_utils.py` in the
upstream source. It is implemented in DEEPscope and does not patch upstream Rayleigh.
