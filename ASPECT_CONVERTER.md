# ASPECT mantle convection → DEEPscope

`tools/convert_aspect_to_viewer.py` converts **complete 3-D spherical-shell**
VTK volumes: a serial `.vtu`, a parallel `.pvtu` plus all its pieces, or a
`solution.pvd` time collection. It needs neither ASPECT nor SHTns installed.
It does not convert ASPECT restart files, zipped archives, 2-D annuli, surface-only
outputs, rectangular boxes or regional chunks into global mantle volumes.

## Install

Run these commands from your DEEP checkout in WSL/Linux:

```bash
python3 -m pip install -r requirements-aspect.txt
```

Dependencies: NumPy, SciPy, VTK >= 9.3. Keep this environment separate from an
ASPECT solver build if their Python requirements differ.

## Small, tested example: a 3-D mantle-plume initial condition

The ASPECT repository contains a World Builder spherical-shell plume mesh,
including temperature, Cartesian velocity and three composition arrays. This is
an **initial-condition example, not an evolved ASPECT convection simulation**.
Its approximate radial range is 4371–6371 km; it is not a model extending down to
the Earth's actual CMB. The bottom boundary is the model's inner mantle boundary.

The following source is pinned to ASPECT commit
`30eb77ee5da186137d436dbad35c6cb3cab64b69`:
[3d_sphere_plume.vtu](https://github.com/geodynamics/aspect/blob/30eb77ee5da186137d436dbad35c6cb3cab64b69/contrib/world_builder/tests/gwb-grid/3d_sphere_plume.vtu).
The bundled World Builder directory includes an
[LGPL-2.1 license](https://github.com/geodynamics/aspect/blob/30eb77ee5da186137d436dbad35c6cb3cab64b69/contrib/world_builder/LICENSE).
The commands retain that license next to the downloaded mesh; the mesh itself
is not redistributed in DEEP.

```bash
ASPECT_INPUT="$HOME/Downloads/aspect-example"
mkdir -p "$ASPECT_INPUT"

curl -fL --retry 3 \
  'https://raw.githubusercontent.com/geodynamics/aspect/30eb77ee5da186137d436dbad35c6cb3cab64b69/contrib/world_builder/tests/gwb-grid/3d_sphere_plume.vtu' \
  -o "$ASPECT_INPUT/3d_sphere_plume.vtu"

curl -fL --retry 3 \
  'https://raw.githubusercontent.com/geodynamics/aspect/30eb77ee5da186137d436dbad35c6cb3cab64b69/contrib/world_builder/LICENSE' \
  -o "$ASPECT_INPUT/WORLD_BUILDER_LICENSE.txt"

(cd "$ASPECT_INPUT" && \
  echo 'cc3e0af4709d86c5cd118235eca6caff0db2971b4b0ea388ee070e81b587e29c  3d_sphere_plume.vtu' | sha256sum -c -)

python3 tools/convert_aspect_to_viewer.py \
  --input "$ASPECT_INPUT/3d_sphere_plume.vtu" --inspect

python3 tools/convert_aspect_to_viewer.py \
  --input "$ASPECT_INPUT/3d_sphere_plume.vtu" \
  --out public/data_aspect_plume \
  --nr 12 --ntheta 24 --nphi 48 \
  --r-inner 4371000 --r-outer 6371000 \
  --composition-field 'Composition 0' \
  --length-units m \
  --boundary-tolerance 0.02 \
  --title 'World Builder plume initial condition' \
  --inner-boundary-label 'Inner mantle boundary' \
  --source-url 'https://github.com/geodynamics/aspect/blob/30eb77ee5da186137d436dbad35c6cb3cab64b69/contrib/world_builder/tests/gwb-grid/3d_sphere_plume.vtu' \
  --incremental --cache-dir "$HOME/.cache/deepscope"
```

No decompression is needed for this file; VTK reads its encoding directly.
This deliberately small grid and explicit 2%-of-radius boundary projection
limit accommodate the coarse example mesh. They are demonstration settings,
not a resolution recommendation for a research calculation. Inspect the recorded
`interpolation` statistics in `metadata.json` before using derivatives.
Time is **unknown** because the example does not supply a physical timestep;
the converter does not invent one.

Open `public/data_aspect_plume` with **Select primary folder**, or use its URL
when it is hosted. Try `T`, `T_anomaly`, `C`, and `Composition_1`. The viewer
normalizes display length; output radii remain in metres.

## Published ASPECT convection simulations

Euen, Liu, Gassmöller, Heister and King (2023),
[Data associated with “A comparison of 3-D spherical shell thermal convection…”](https://doi.org/10.7294/22803335),
provides ASPECT and CitcomS model data for cases A1, A3, A7, C1, C2 and C3.
The dataset is **CC0 1.0**; its scripts have a separate MIT license.
The associated paper is
[Geoscientific Model Development 16, 3221–3239 (2023)](https://doi.org/10.5194/gmd-16-3221-2023).

Download just the ASPECT archive, rather than the separate CitcomS archive.
The public file index lists **7,501,159,424 bytes** and the MD5 below. Leave
additional disk space for extraction and converted volumes.

```bash
ASPECT_DATA="$HOME/Downloads/aspect-euen2023"
mkdir -p "$ASPECT_DATA"

curl -fL --retry 3 -C - \
  'https://ndownloader.figshare.com/files/40557500' \
  -o "$ASPECT_DATA/3Dsphericalshell_paper_ASPECT.tar.gz"

(cd "$ASPECT_DATA" && \
  echo '500b662ae60f9235722016a28a60232d  3Dsphericalshell_paper_ASPECT.tar.gz' | md5sum -c -) && \
  tar -xzf "$ASPECT_DATA/3Dsphericalshell_paper_ASPECT.tar.gz" -C "$ASPECT_DATA"

find "$ASPECT_DATA" -type f \( -name '*.pvd' -o -name '*.pvtu' -o -name '*.vtu' \)
```

Select a **volume** output from the desired case/resolution in that listing.
Do not choose a `surface` or `particles` file, and do not choose one numbered
VTU partition when its matching PVTU is available. PVTU discovers every piece
relative to its own directory, including when the archive has wrapper folders.

The download URL and expected checksum were read from the public file index.
This archive's internal file tree and a published-case conversion have **not**
been tested here: the
Figshare download endpoint returned HTTP 403 in the development environment.
Consequently no internal filename is assumed below. If the archive contains
only reduced plotting data rather than volume VTK, those files cannot reconstruct
a 3-D solution; use the authors' ASPECT setup to generate visualization output.

Replace the path below with the chosen entry from `find`:

```bash
ASPECT_VOLUME='/full/path/from/the/list/solution-00000.pvtu'

python3 tools/convert_aspect_to_viewer.py \
  --input "$ASPECT_VOLUME" --inspect

python3 tools/convert_aspect_to_viewer.py \
  --input "$ASPECT_VOLUME" \
  --out public/data_aspect_A1 \
  --nr 64 --ntheta 96 --nphi 192 \
  --title 'ASPECT — Euen et al. (2023), A1' \
  --source-url 'https://doi.org/10.7294/22803335' \
  --incremental --cache-dir "$HOME/.cache/deepscope"
```

Use a title matching the case you actually select. Check the case's `.prm` for
length/time units; this benchmark may be nondimensional. Do not label it in
metres or years merely because dimensional mantle models use those units.

## Time sequences and units

For ASPECT's standard PVD output:

```bash
python3 tools/convert_aspect_to_viewer.py \
  --input '/path/to/output/solution.pvd' \
  --all-frames --frame-step 1 \
  --out public/data_aspect_sequence \
  --nr 64 --ntheta 96 --nphi 192 \
  --time-units yr --length-units m --velocity-units 'm/yr' \
  --incremental --cache-dir "$HOME/.cache/deepscope"
```

Those unit flags describe the stored numbers; use them only when correct for
your run. They **do not rescale** values. ASPECT's “Use years instead of seconds”
setting affects its output conventions. See the official
[ASPECT visualization documentation](https://aspect-documentation.readthedocs.io/en/stable/user/run-aspect/visualizing-results/index.html).

PVD timesteps are saved in each frame's metadata and in `sequence.json`. A
single file uses VTK `TIME`/`TimeValue`/`Time`/`time` field data, or explicit
`--time NUMBER`. Missing time is JSON `null`, displayed as unknown.
`--frame 0` selects the first PVD frame; default `--frame -1` selects the last.
All frames share the first frame's sampling grid. An adaptive mesh may change,
but every frame must cover that grid and export the same chosen fields.
The normal viewer sequence preloader, phi-average calculator, time overlay,
Mollweide panel and image/video exports can use these bundles.

## Fields and numerical meaning

- `T` maps `T` or `Temperature`, or `--temperature-field NAME`.
- `C` maps an explicit `--composition-field NAME`; other scalar arrays retain
  safe names (`Composition 1` becomes `Composition_1`). No tracer is silently
  assumed to be active composition.
- Cartesian `velocity` becomes `ur`, `ut`, `up`, with `ut` positive toward
  increasing colatitude. Also exported: `Uabs`, `us`, `uz`.
- Pressure `p` maps to `P`. Available density, viscosity and other scalar arrays
  are retained. Non-velocity vector/tensor arrays are not exported.
- `T_anomaly` and `C_anomaly` subtract the spherical-surface mean at each radius.
  They are distinct from `_nom0`, which subtracts only the longitude mean.
- `_phiavg`, `_nom0`, physical scalar gradients, `dthetaT_phiavg`,
  `dthetaC_phiavg`, `dzup_phiavg`, `advT`, `advC` are included when inputs allow.
  Advection means **positive** `u dot grad(scalar)`; theta is colatitude, and
  `dzup_phiavg` is the axial derivative at fixed cylindrical radius.
- Example selection: `--output T T_anomaly ur viscosity advT`. Dependencies are
  sampled internally, but only selected volumes are written.
- `--no-gradients` disables gradients/advection/mean derivatives;
  `--no-m0-fields` disables longitude means/fluctuations and mean derivatives.
- No magnetic field, field lines, core dynamo Rayleigh numbers or dynamo `N2`
  formula is added. No reference temperature or background profile is guessed.

Sampling uses the original VTK cell connectivity. It does not interpolate
through the core cavity with a point-cloud triangulation. Colatitudes are
midpoints; longitude is periodic with no duplicate seam. Derivatives are finite
differences **after resampling**, not ASPECT's original finite-element derivatives.
Use grid-convergence checks before scientific interpretation.

Invalid interior samples fail conversion. Only the two radial endpoints may
project to nearby cells within `--boundary-tolerance * r_outer`; the number of
projected samples and largest displacement are recorded. Significant free-surface
topography or incomplete angular coverage needs a suitable inscribed sampling
shell, not a large tolerance that fills missing mantle. Cell-only arrays are
averaged to points and listed in metadata.

The viewer's outer/inner boundary names are Surface/CMB by default; override
`--inner-boundary-label` for a truncated mantle domain. The legacy JSON key
`has_inner_core` enables rendering the inner spherical boundary; it does **not**
claim the mantle dataset contains an inner core or magnetic core values.

Conversion is staged and validated before replacing an existing bundle. Failed
conversions preserve the previous output. `--incremental` fingerprints the input,
all referenced PVTU pieces, options and converter code, then skips a complete
unchanged output. It does not currently cache individual VTK interpolation jobs.
