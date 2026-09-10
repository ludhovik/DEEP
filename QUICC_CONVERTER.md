# QuICC and EPMDynamoCode conversion

`tools/convert_quicc_to_viewer.py` reads spherical **spectral state files**
directly with h5py, NumPy and SciPy. Neither an installed QuICC executable nor
its Python package is required. Source files and upstream code are read-only.

## Supported inputs

- Legacy [EPMDynamoCode](https://github.com/QuICC/EPMDynamoCode):
  `Truncation/{N,L,M,Mp}`, `Velocity/{VelocityPol,VelocityTor}`,
  `Magnetic/{MagneticPol,MagneticTor}`, `Codensity/Codensity`.
- Modern [QuICC](https://github.com/QuICC/QuICC-Solver): `WLFl` (degree-major)
  and `WLFm` (order-major) full-sphere Worland states, with
  `truncation/spectral/dim{1,2,3}D` and `velocity`, `magnetic`, `temperature`,
  `composition` groups. A scalar is optional; absent fields are never invented.
- Complex HDF5 arrays and real/imaginary pairs, including EPM's HDF5 array
  datatype. Dimensions, finite values, paired potentials and real m=0 modes
  are checked before export.

- Modern QuICC spherical-shell states `SLFl` and `SLFm` use the same field
  groups as modern full spheres, with a mapped Chebyshev radial expansion.
  `physical/lower1d` and `physical/upper1d` must specify valid native boundaries;
  `rratio`/`r_ratio`, if present, must agree. A ratio alone is insufficient to
  establish the physical length normalization and is rejected.

Cartesian, cylindrical, physical visualization and custom restart layouts are
not supported. Native geometry is detected automatically; `--geometry` and
`--fluid-inner-radius` validate it rather than reinterpret it. These inputs
provide no separately resolved inner-core arrays, so `--inner-core-only` and
`--geometry conducting-inner-core` remain unsupported. No data are invented
inside the shell's inner boundary.

Pass an **extracted HDF5 state** to `--state`, never its `.tar.gz` archive.
Invalid signatures now produce an explicit extraction instruction.

## Install and convert

```bash
python3 -m pip install -r requirements-quicc.txt
python3 tools/convert_quicc_to_viewer.py \
  --state /path/to/state0000.hdf5 \
  --out public/data_quicc \
  --incremental --cache-dir "$HOME/.cache/deepscope" \
  --emf --induction --cmb-br-ltrunc 13 \
  --field-line-mode both --line-seeds 360 \
  --external-rmax 40 --external-nr 192 --line-max-steps 4000
```

`--folder /path/to/run` chooses the latest `stateNNNN.hdf5` or
`state_NNNN.h5`; `--state-number N` selects one. For a differently named file,
use `--state`. Sequences use the same first/last/step options as the other
converters; every requested index must exist. Output publication is staged
and validated; a failed conversion keeps the previously published bundle.

The output includes `.f32` fields, explicit coordinates, amplitudes,
cylindrical velocity components, azimuthal means and fluctuations, helicity,
scalar gradients, optional motional EMF and induction, CMB/surface maps and
paired internal/exterior lines with return branches. View files, viewer line
stride pairing and B² tubes use the ordinary DEEPscope bundle format.

`--spectral-lmax 0` (default) retains every native mode. A positive cutoff
removes higher degrees before vector/scalar synthesis and reduces the grid.
Sampling factors apply afterward. Full-sphere radius includes both 0 and 1; shell radius includes both native
boundaries and no points below the ICB. The angular
grid uses Gauss colatitudes and a full uniform longitude period, without a
duplicate seam. No arbitrary centre extrapolation is used.

`--incremental` caches HDF5 reads and each vector/scalar synthesis separately,
as well as shared diagnostics and line calculations. Changing line options or
adding EMF reuses the native transforms. Missing/damaged outputs are rebuilt
from checked caches. `--force` requests recomputation. Keep `--cache-dir`
outside the output bundle and outside every `public/` directory.

## Normalization and mathematical reconstruction

For a standard build the radial basis is

\[
W_n^\ell(r)=\frac{r^\ell P_n^{(-1/2,\ell-1/2)}(2r^2-1)}{N_{n\ell}},
\quad
\int_0^1 W_n^\ell W_k^\ell\frac{dr}{\sqrt{1-r^2}}=\delta_{nk}.
\]

For \(\ell>0\),

\[
N_{n\ell}^2=\frac{\Gamma(n+1/2)\Gamma(n+\ell+1/2)}
 {2(2n+\ell)\Gamma(n+1)\Gamma(n+\ell)}.
\]

The \(n=\ell=0\) limit is \(N_{00}^2=\pi/2\). The remaining
\(\ell=0\) modes are handled analytically as well.

Using the conventional associated Legendre functions including the
Condon–Shortley phase, the angular factors are:

| Setting | Angular factor multiplying \(P_\ell^m(\cos\theta)\) |
|---|---|
| `unity` (modern QuICC default) | \(\sqrt{(2\ell+1)(\ell-m)!/[4\pi(\ell+m)!]}\) |
| `schmidt` (custom modern build) | \(\sqrt{(\ell-m)!/(\ell+m)!}\) |
| `epm` (legacy EPM default) | \(\sqrt{(2-\delta_{m0})(\ell-m)!/(\ell+m)!}\) |

Each positive-m contribution is \(2\Re[a_{\ell m}Y_{\ell m}]\);
the m=0 contribution is real and counted once. EPM `Mp` symmetry is unfolded
to a full longitude period. Normalized recurrences avoid large-m factorial
overflow. `--angular-normalization auto` selects the standard upstream
convention **from the file layout**, not from a normalization attribute.

The files do not record all solver build options. Custom builds must explicitly
supply matching `--angular-normalization unity|schmidt|epm`,
`--worland-family chebyshev|legendre` and
`--worland-normalization unity|natural`. Legendre here means Jacobi
\(\alpha=0,\beta=\ell-1/2\); other Worland families require an extension.
A wrong convention changes amplitudes even if the resulting picture looks plausible.

### Shell radial basis

For SLFl/SLFm, with \(a=(r_o-r_i)/2\), \(b=(r_o+r_i)/2\) and
\(x=(r-b)/a\), the native expansion is

\[
f_{\ell m}(r)=c_{0,\ell m}+2\sum_{n=1}^{N}c_{n,\ell m}T_n(x).
\]

The factor two applies only to n>0, matching QuICC's inverse FCT convention.
Derivatives are evaluated analytically with \(d/dr=a^{-1}d/dx\). The same
vector formulas below apply with this radial basis. Worland settings do not
change the shell basis; nondefault Worland options are rejected for shells.
The shell grid uses Chebyshev–Lobatto points including both boundaries.
Native length units are preserved (the benchmark has a unit shell gap).

[QuICC shell projection operators](https://github.com/QuICC/QuICC-Solver/blob/main/Components/PyQuICC/Python/quicc/projection/shell.py)
define the basis and its derivative normalization.

Both vector potentials obey

\[
\mathbf B=\nabla\times(T\mathbf r)+\nabla\times\nabla\times(P\mathbf r).
\]

For each harmonic, defining \(S=P'+P/r\), the reconstructed components are

\[
B_r=\frac{\ell(\ell+1)}r P Y,\quad
B_\theta=S\partial_\theta Y+T\frac{im}{\sin\theta}Y,\quad
B_\phi=S\frac{im}{\sin\theta}Y-T\partial_\theta Y.
\]

Velocity uses the same formulas. Derivatives are evaluated analytically in
the radial polynomial basis. At the centre, scalar l=0 and vector poloidal
l=1 regular limits survive; vector l=0 is a null potential. The spherical
components of a uniform centre vector naturally depend on theta/phi, but
transform to the same Cartesian vector from every direction.

Scalar fields are reconstructed **as stored**. Imposed fields, reference
profiles and background/source files are not implicitly added. In particular,
`C_phiavg` includes only the stored axisymmetric scalar, and `Cnom0` removes
that mean. The name `N2_full` means m=0 is retained; it does not imply that an
absent conductive reference profile has been reconstructed.

### N2 and physical units

HDF5 records a spatial scheme, not a unique model's nondimensional equations.
QuICC models can use different Rayleigh and time scales. To avoid silently
applying the wrong scale, **N2 is off by default** for this converter; scalar
gradients are still exported. Select the convention appropriate to the model:

- `--n2-convention deepscope`: \(N^2=rE^2(Ra_T C_r/Pr+Ra_C Comp_r/Sc)\).
- `--n2-convention quicc-rotating`: for full spheres,
  \(N^2=rE(Ra_T C_r/Pr+Ra_C Comp_r/Sc)\). For shells,
  \(N^2=(r/r_o)E(Ra_T C_r+Ra_C Comp_r)\), matching the standard unit-gap
  QuICC shell dynamo's modified Rayleigh number and gravity. Its thermal
  buoyancy coefficient contains no Pr factor. Composition uses the analogous
  convention when selected by the user. This shell convention is rejected for
  non-unit-gap coordinates; choose `none` unless the model scaling is known.
  These are rotation-unit diagnostics of the stored scalar, without adding an
  absent conductive background.
- `--n2-convention none`: omit N2 (default).

CLI parameter overrides apply to these calculations. Missing factors leave the
corresponding contribution absent; metadata records native parameters and the
chosen convention. Other quantities retain native simulation units. Conversion
alone does not make amplitudes from different nondimensional models comparable.

## Verified online dynamo example

The QuICC project's own **BoussinesqSphereDynamo / Explicit** reference archive
contains twelve numbered snapshots plus `state_initial.hdf5`, native energy
series and `parameters.cfg`. This is a small numerical benchmark rather than a
planet-specific production run. It includes velocity, magnetic field and
thermal scalar, with N=15, L=M=31, E=0.0005, Pr=1, Pm=7 and modified Ra=200.

- [Official benchmark configuration](https://github.com/QuICC/Model-BoussinesqSphereDynamo/blob/main/TestSuite/CMakeLists.txt)
- [Official reference-download configuration](https://github.com/QuICC/QuICC-Solver/blob/main/cmake.d/FetchBenchmarkReference.cmake)
- [Download the verified archive](https://gitlab.ethz.ch/quicc/test-benchmarks/-/raw/v0.8.0/ref/BoussinesqSphereDynamo/Explicit.tar.gz)

```bash
mkdir -p "$HOME/Downloads/quicc-benchmark"
curl -4 -fL \
  'https://gitlab.ethz.ch/quicc/test-benchmarks/-/raw/v0.8.0/ref/BoussinesqSphereDynamo/Explicit.tar.gz' \
  -o "$HOME/Downloads/quicc-benchmark/Explicit.tar.gz"
tar --no-same-owner -xzf "$HOME/Downloads/quicc-benchmark/Explicit.tar.gz" \
  -C "$HOME/Downloads/quicc-benchmark"

python3 tools/convert_quicc_to_viewer.py \
  --state "$HOME/Downloads/quicc-benchmark/Explicit/state0011.hdf5" \
  --out public/data_quicc \
  --incremental --cache-dir "$HOME/.cache/deepscope" \
  --emf --induction --n2-convention quicc-rotating \
  --cmb-br-ltrunc 13 --field-line-mode both --line-seeds 360 \
  --external-rmax 40 --external-nr 192 --line-max-steps 4000
```

Use the DEEPscope folder picker on the resulting `public/data_quicc` folder.
To convert a sequence instead, replace `--state ...` with
`--folder "$HOME/Downloads/quicc-benchmark/Explicit" --sequence-first 0 --sequence-last 11 --sequence-step 1`.

Archive size: 8,901,643 bytes. SHA-256:
`25b2f9b363d643c0c6f6b52292ff7d5ac68f1f79782422f0f01c4d575ced965e`.

## Verified spherical-shell example

The user's [BoussinesqShellDynamo Explicit v0.8.0 archive](https://gitlab.ethz.ch/quicc/test-benchmarks/-/raw/v0.8.0/ref/BoussinesqShellDynamo/Explicit.tar.gz)
is supported. Extract it, then use the same conversion options:

```bash
tar --no-same-owner -xzf "$HOME/Downloads/quicc-benchmark2/Explicit.tar.gz" \
  -C "$HOME/Downloads/quicc-benchmark2"
python3 tools/convert_quicc_to_viewer.py \
  --state "$HOME/Downloads/quicc-benchmark2/Explicit/state0011.hdf5" \
  --out public/data_quicc_shell \
  --incremental --cache-dir "$HOME/.cache/deepscope" \
  --emf --induction --n2-convention quicc-rotating \
  --cmb-br-ltrunc 13 --field-line-mode both --line-seeds 360 \
  --external-rmax 40 --external-nr 192 --line-max-steps 4000
```

This state is SLFl, N=23, L=M=47, \(r_i=0.5384615384615384\),
\(r_o=1.5384615384615383\), E=0.0005, Pm=5, Pr=1, Ra=50.
A complete export with 36 tracing seeds produced 46 volumes and 36 exterior
arcs with all return branches connected. Native `state0000` energy comparison:

| Quantity | Native reference | Reconstructed |
|---|---:|---:|
| Mean kinetic energy | 769.404712588804 | 769.404712588798 |
| Mean magnetic energy | 1.5670242214564 | 1.5670242214563932 |
| Mean temperature squared | 0.00603865921329396 | 0.006038659213293904 |

```bash
python3 tests/test_quicc_shell.py
QUICC_SHELL_BENCHMARK_DIR="$HOME/Downloads/quicc-benchmark2/Explicit" \
  python3 tests/test_quicc_shell.py
```

The [shell model equations](https://github.com/QuICC/Model-BoussinesqShellDynamo/blob/main/Readme.md)
and [effective buoyancy coefficient](https://github.com/QuICC/Model-BoussinesqShellDynamo/blob/main/Model/Boussinesq/Shell/Dynamo/IDynamoBackend.cpp)
determine the shell-specific N2 factor.

## Validation

```bash
python3 tests/test_quicc_converter.py
QUICC_BENCHMARK_DIR="$HOME/Downloads/quicc-benchmark/Explicit" \
  python3 tests/test_quicc_converter.py
```

The optional real-data check independently integrates reconstructed fields and
compares the results to the archive's native energy tables. For `state0000`:

| Quantity | Native reference | Reconstructed |
|---|---:|---:|
| Mean kinetic energy | 8815.65290275401 | 8815.652902753971 |
| Mean magnetic energy | 0.0145280479619922 | 0.014528047961992294 |
| Mean temperature squared | 0.00127579456176312 | 0.001275794561763118 |

Analytic tests cover orthonormal radial bases, radial derivatives, uniform
Cartesian magnetic fields along x/y/z including the centre, solid-body
rotation, a radial scalar polynomial, Fourier symmetry, both harmonic orders,
cutoff filtering and legacy EPM normalization. Integration tests cover complete
bundles, sequence publication, diagnostic additions, cache reuse, deleted output
recovery and preserving the last bundle when new input is invalid.

Legacy EPM is validated with independently specified analytic fixtures, not a
production EPM state. The downloaded production-format benchmark is modern
QuICC WLFl. This distinction matters for custom or modified solver builds.

### Source conventions checked

- [EPM HDF5 writer](https://github.com/QuICC/EPMDynamoCode/blob/main/src/IO/HDF5/State/StateFileWriterBase.cpp)
- [EPM radial projection operators](https://github.com/QuICC/EPMDynamoCode/blob/main/include/Polynomials/TorPolRadialOperator.hpp)
- [EPM angular polynomials](https://github.com/QuICC/EPMDynamoCode/blob/main/src/Polynomials/AssociatedLegendrePolynomial.cpp)
- [QuICC Worland normalization](https://github.com/QuICC/QuICC-Solver/blob/main/Components/PyQuICC/Python/quicc/geometry/worland/chebyshev.py)
- [QuICC full-sphere model equations](https://github.com/QuICC/Model-BoussinesqSphereDynamo/blob/main/Readme.md)
