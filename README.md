# DEEPscope — Spherical Dynamo Viewer

DEEPscope is a browser-based Three.js viewer for three-dimensional spherical-dynamo
and convection simulations. It includes converters for:

- the Leeds Spherical Dynamo code;
- XSHELLS through `pyxshells`;
- MagIC `G_#.TAG` and `G_ave.TAG` graphic files through MagIC's `MagicGraph`
  reader.

Open the hosted viewer at
[the DEEPscope viewer](https://ludhovik.github.io/DEEP/), or run it locally
with Vite. Local datasets are read in the browser and are not uploaded.

## What the viewer can display

- CMB and ICB fields;
- a spherical surface at any radius;
- two equatorial and two meridional slices;
- positive and negative isosurfaces;
- internal and exterior magnetic field lines, including tubes with diameter proportional to magnetic energy;
- Earth, Mars, Ganymede, Mercury, Venus, Enceladus and Moon surface images, or
  an available extrapolated radial magnetic field;
- two compatible datasets on the same grid;
- time sequences with playback, preloading, and bounded memory caching;
- PNG, PDF, WebM, and PNG-sequence output;
- transferable view-state codes.

Each display has independent field, range, colour map, and opacity controls.
The appearance panel also provides a selectable background colour and a
two-endpoint custom colour map. The title, legend, and quick-export boxes can
each be hidden, collapsed, placed at a preset location, dragged, or resized in
the viewport.

## Quick start

### Use the hosted viewer

1. Open [DEEPscope](https://ludhovik.github.io/DEEP/).
2. Select **Open local dataset folder**, **Open bundled demonstration**, or
   enter a supported public repository URL.
3. Open **Controls** in the upper-right corner.

The local-folder option grants the page read access only to the folder selected
by the user. The simulation data remain on the computer.

### Run locally

Requirements:

- Node.js 22.12 or newer;
- npm;
- Python 3.10 or newer for conversion.

```bash
git clone https://github.com/ludhovik/DEEP.git
cd DEEP
npm ci --no-audit --no-fund
npm run dev
```

Open the URL printed by Vite. For a production check:

```bash
npm run build
npm run preview
```

`npm ci` uses the exact versions in `package-lock.json`. Use `npm install` only
when intentionally updating dependencies.

## Loading data

### Local folder

Select a converted single-frame folder containing `metadata.json`, or a
sequence root containing `sequence.json` and `frames/`.

To replace the displayed dataset, use **Controls → Dataset → Select primary
folder**. Each selection reads the chosen folder afresh, including when files
have the same names as those in the previous folder. No page refresh is needed.
For a path or URL, edit **Primary path / URL**, then click **Load primary path**.
Replacing a secondary folder also redraws any displayed comparison fields.
If loading fails, the previous dataset and its folder access remain available.

This is the preferred way to inspect large private datasets. The browser reads
the selected files directly without publishing them.

During local Vite development, an absolute path can also be entered in the
dataset control, for example:

```text
/path/to/viewer_data
```

Browser folder selection is more portable and also works on the hosted site.

### Figshare

Paste any of these forms into the URL box:

```text
https://figshare.com/articles/dataset/RECORD_TITLE/ARTICLE_ID
https://api.figshare.com/v2/articles/ARTICLE_ID
https://doi.org/10.6084/m9.figshare.ARTICLE_ID
figshare:ARTICLE_ID
```

The public record must contain the converted files individually, including
their folder paths. Uploading only a ZIP file does not expose the files needed
for random access in the viewer.

Figshare metadata is read through the small Cloudflare Worker in
`cloudflare/figshare-proxy.js`; the actual data files are downloaded from
Figshare. The proxy accepts read-only `GET` and CORS preflight requests,
does not use a Figshare token, and restricts upstream requests to the Figshare
API and file-download hosts.

### Zenodo

Paste one of these forms:

```text
https://zenodo.org/records/RECORD_ID
https://zenodo.org/api/records/RECORD_ID
https://doi.org/10.5281/zenodo.RECORD_ID
zenodo:RECORD_ID
```

As with Figshare, the converted files must be present individually in the
record. Preserve paths such as `frames/state00001/metadata.json` when uploading
a sequence.

### Other public web storage

A direct URL to a converted dataset root works when the server:

- exposes the real files rather than an HTML sharing page;
- preserves the folder layout;
- permits cross-origin `GET` requests from the viewer;
- supports sufficiently large downloads.

Ordinary Google Drive, Dropbox, and OneDrive folder-sharing pages do not expose
a CORS-readable directory tree and therefore cannot be used as dataset roots.
Use local folder selection, Figshare, Zenodo, or a static web/object-storage
service configured for CORS.

## Viewer controls

### Camera and keyboard

Mouse controls:

- left drag: rotate;
- wheel: zoom;
- right drag: pan.

Keyboard shortcuts:

| Key | Action |
| --- | --- |
| Left / Right | Rotate azimuth by 5° |
| Up / Down | Rotate elevation by 5° |
| `I` / `O` | Zoom in / out |
| `+` / `-` | Next / previous sequence frame |

The **Point of view** panel stores distance, azimuth, elevation, target, and
field of view. **Use current mouse view** copies the current interactive camera
into those controls.

### Surfaces and slices

Every CMB, ICB, radial, equatorial, and meridional display has:

- a field selector;
- symmetric, min/max, or manual scaling;
- a colour-map selector;
- manual minimum and maximum values;
- opacity.

The CMB can be clipped by one or two meridional planes or by an explicit
eight-quarter mask. Open **Planet / moon surface**, enable **Show**, choose
**Display → Surface image**, then select **Image body**: Earth, Mars, Ganymede,
Mercury, Venus (radar surface), Enceladus or Moon. **Texture longitude**, **Image
radius / outer**, and **Opacity** adjust its placement and appearance. Images
use the same closed sphere, polar caps and meridian clipping as the Earth image.

Changing the body changes the reference image only. It preserves your simulation
fields, camera, clipping and radius settings. The radius is a multiple of the
dataset's outer radius; choose the ratio appropriate to your figure. This is a
visual reference, not a physical model of that body's interior or magnetic field.
**Display → Magnetic B_r**, when available, continues to show the dataset's
extrapolated field at the radius recorded in its metadata.

The selected body is saved in copied `DTV2` codes and dataset `view.DTV2` files.
Older full view codes without a body selection use Earth. Images are bundled
with the viewer and downloaded only when selected, from the same origin as the
app. They do not use Figshare, Zenodo or the Cloudflare proxy. Source credits
follow the displayed image; a failed load leaves the previous image in place.

Venus uses a radar-derived surface image. Some maps use enhanced colours or
filled coverage gaps and are intended for illustration. Source mosaics can
retain lighting differences or limited polar detail even though the sphere
geometry has no missing seam or cap. See the
[surface-image sources, licences and limitations](public/assets/surfaces/CREDITS.txt).

The bundled Earth image is a complete 2:1 latitude-longitude map from
[NASA's Blue Marble](https://svs.gsfc.nasa.gov/2915/). The longitude seam is
closed and both poles are capped. North is +z; with **Texture longitude = 0**,
Greenwich lies along +x and 90 degrees east along +y. Older versions placed
Greenwich half a turn away, so adjust a previously saved texture longitude by
180 degrees if you need its former continent orientation. Texture longitude
changes the image only; the dataset coordinates and clipping planes stay fixed.
For a sharper replacement image, use a complete equirectangular PNG such as
4096 x 2048, including both poles. See
[Earth texture requirements and credits](public/assets/README_EARTH_TEXTURE.txt).

### Custom appearance

Open **Appearance and legends** to set:

- the canvas background colour;
- the low and high endpoints of `custom-two-colour`;
- title-box visibility, collapse state, position, width, and height;
- legend visibility;
- collapsed or expanded legend state;
- legend position, width, and height;
- quick-export visibility, collapse state, position, width, and height.

Choose `custom-two-colour` in any surface, slice, Earth-field, or field-line
colour-map selector. The two custom endpoint colours are shared by all displays
using that map.

Drag the **DEEPscope**, **Legends**, or **Quick export** header to move that box.
Drag its lower-right corner grip to resize it, and click `−`/`+` to collapse or
expand it. A height of `0` in the controls restores automatic height. Positions,
dimensions, visibility, and collapse states are included in view-state codes.
Legend width and position also carry into PNG/PDF legend layout.

Dataset summaries, progress and error messages appear in the **DEEPscope title
box**. Quick export keeps its buttons and short download hint. An error or
warning adds a **⚠** button beside the title, including when the box is
collapsed; click it to expand the box and read the message. **Dismiss warning**
clears it. Unrelated progress does not hide an error; a successful retry of a
failed control task clears that task's notice. Loading a new dataset clears
previous notices. Warnings are temporary feedback and are not saved in DTV2.

### Isosurfaces and field lines

Isosurfaces support positive and negative levels, independent colours,
opacity, resolution, optional meridional clipping, and two transparency modes.
**Stable (dithered)** uses depth-aware alpha hashing so transparent components
do not disappear when the camera moves. **Smooth (may reorder)** retains
conventional alpha blending for users who prefer a grain-free image and do not
have overlapping transparent geometry.

When the converter wrote magnetic field lines, the viewer can display internal
shell lines, exterior potential/poloidal lines, or both. Lines can be coloured
by strength or CMB seed polarity, with configurable width, opacity, stride, and
range.

Choose **Magnetic field lines → Render as → B² tubes** to give each line a
three-dimensional tube whose diameter varies along its path:

```math
d(s)=\operatorname{clip}\!\left[d_{\mathrm{ref}}
\left(\frac{|\mathbf B(\mathbf x(s))|}{B_{\mathrm{ref}}}\right)^2,
d_{\min},d_{\max}\right].
```

In **B² tube diameter**, diameter values are fractions of the outer radius
`ro`. **Ref |B| (0 = auto)** sets the reference in the dataset's magnetic-field
units; zero selects the maximum available line strength across the displayed
domains, before stride selection. Set a positive reference to compare figures
or frames on the same scale. The colour map and its linear/logarithmic scale
do not change the tube diameter. All tube options are included in DTV2 codes.

**Minimum / ro** can keep weak-field sections visible; **Maximum / ro** limits
very wide sections. These are display limits. With no clipping, doubling
`|B|` quadruples the diameter. **Tube sides** controls mesh detail. Increase
**Line stride** or reduce tube sides if a requested mesh exceeds the geometry
budget. Tube opacity uses stable dithered transparency, as for isosurfaces.

**Tube simplification → Simplify tubes** is on by default and can be switched
off to use every saved sample. It reduces points along each retained line,
keeping the original endpoints, pairing identifiers, strongest/weakest samples
within each continuous section, and missing-data breaks. It does not retrace
the magnetic field or change the stored dataset. Ordinary lines are unaffected.

| Simplification control | Default | Meaning |
| --- | --- | --- |
| **Shape error / ro** | `0.0005` | Maximum centreline deviation from the saved polyline, as a fraction of outer radius (`0.05%` by default). |
| **B² error (%)** | `1` | Maximum relative change in the interpolated B² profile at source samples. |

Both bounds are checked using the original cumulative arclength. The energy
comparison uses a small floor (`10⁻¹²` of the section's peak B²) near zero.
Larger error limits permit fewer points; smaller limits retain more detail.
The colour range and automatic strength reference still use the full selected
domains before thinning. All simplification options are included in DTV2.

The fixed **192 MiB geometry budget** is checked after simplification. The
title reports retained/original point counts and the estimated mesh size;
an oversized request leaves the previous display intact. If needed, increase
the error limits modestly, increase **Line stride**, or reduce **Tube sides**.
Reducing diameter or opacity does not reduce the number of mesh vertices.

Recent converter bundles already contain `strength = |B|` at each traced
point and need no reconversion for tubes. For legacy internal lines, including
the bundled demonstration, the viewer can sample an available `Babs` volume
on the viewer grid; the status message identifies this approximation. Lines
with no usable strength array retain constant width, and tube geometry never
bridges missing-strength sections or extrapolates a volume into the exterior.

This thickness encoding follows [Aubert, Aurnou & Wicht (2008), section 2.2](https://www.ipgp.fr/~aubert/DMFIPaper.pdf).
It represents magnetic energy visually. Time-dependent DMFI anchor tracking
is not implemented; each frame retains its converter-generated line paths.

With **Line type → Both**, **Line stride** selects linked internal/exterior
lines together using their identifiers. A stride of 3 retains every third
shell line group and all of its available exterior partners, even when exterior
arcs are missing or stored in a different order. A stride of 1 shows all lines.
Older bundles without line identifiers retain independent stride selection;
new converter output already contains the pairing information. Shell lines
without an exported exterior partner remain available for display.

All three converters trace a line in Cartesian coordinates with arclength-like
parameter `s`:

```text
dx/ds = +/- B(x) / |B(x)|
```

Spherical field components are trilinearly interpolated (periodically in
longitude), transformed to Cartesian components, and integrated with
boundary-aware fourth-order Runge–Kutta steps. Boundary events are projected
exactly onto the ICB or CMB.

Inside the fluid, `B` is the field reconstructed from the simulation output.
Outside the CMB there are no imposed currents, so the converter solves
`B = -grad(V)` and `laplacian(V) = 0`. If
`Br(R,theta,phi) = sum(q_lm Y_lm)` at CMB radius `R`, then

```text
Br_lm(r)     = q_lm (R/r)^(l+2) Y_lm
Btheta_lm(r) = -q_lm (R/r)^(l+2)/(l+1) dY_lm/dtheta
Bphi_lm(r)   = -q_lm (R/r)^(l+2)/(l+1)/sin(theta) dY_lm/dphi
```

This field is divergence-free and curl-free. Leeds obtains `q_lm` from its CMB
poloidal coefficients, while XSHELLS and MagIC analyse the physical CMB `Br`.
The SHTns spheroidal coefficient is fixed analytically to
`S_lm = -Q_lm/(l+1)`; it is no longer selected from line appearance.

In `--field-line-mode both`, every exterior line begins at the exact traced CMB
intersection stored for its corresponding internal line. Their JSON records
share a `line_id`; the exterior record also contains `paired_shell_line_id`.

From converter version 3.4, a closed exterior arc also seeds an **additional
internal branch at its returning CMB footpoint**. A regular internal seed grid
rarely includes that second point, which explains why older bundles showed
an apparently unconnected return end. The new branch integrates the actual
simulation field from the exact endpoint, in the same oriented `+B` or `-B`
direction as the exterior arc. It adds at most one internal branch per arc;
it does not recursively follow every later boundary crossing or guarantee a
complete closed loop. The internal trace can stop at the ICB, another CMB
intersection, a field null, or its step limit.

The exterior record identifies this branch with `paired_shell_return_line_id`.
A shared `line_group_id` makes **Line stride** retain or omit the original
internal line, exterior arc and return branch together. Reconversion is needed
to add return branches to existing bundles. The console and metadata report
`return_connection_counts`; an incompatible radial polarity or an unresolved
inward trace is reported without drawing an artificial connection. Using a
different harmonic cutoff for the exterior reconstruction can cause such a
boundary mismatch, particularly near a neutral line.

Positive polarity means `Br > 0` (field directed outward) at that starting CMB
footpoint, and negative means `Br < 0` (field directed inward). An exterior arc
connects one positive and one negative footpoint, so its colour describes only
the selected starting footpoint. The return branch uses the polarity of its
own CMB footpoint, so polarity colouring can change at a connected endpoint.

Exterior tracing clusters radial samples near the CMB, where higher spherical
harmonic degrees decay most rapidly. The automatic CMB step depends on the CMB
radius and retained degree; it grows with radius and shrinks again on return.
Short loops are retried with smaller steps instead of requiring an excursion
of two integration steps above the CMB. Boundary checks tolerate floating-point
roundoff while retaining the exact paired shell starting point.

`--external-rmax` is an **absolute radius in the input file's length units**.
Omitting it uses `2.5 * r_cmb`. Keep a larger value such as `40` when long arcs
are wanted: the automatic CMB step no longer grows with this outer limit.
The default `--external-closed-only` exports only arcs returning to the CMB
within that domain and the step budget. Reducing the outer limit can therefore
exclude valid long loops; a line reaching that limit is not proof of a
physically open field line. `--no-external-closed-only` also exports incomplete
traces with their termination status.

For high-degree fields or a large exterior domain, compare
`--external-nr 192` with `--external-nr 256` to check radial convergence.
This changes exterior interpolation resolution, not the volume-field grid.
If many traces report `max_steps`, increase `--line-max-steps`; the automatic
step is deliberately smaller near the CMB than in older converters.
`--line-step-size` supplies a fixed requested step for both shell and exterior
traces, subject to boundary and short-arc refinement.

The console and `metadata.json` report exterior sampling, termination counts,
and input/traced/retained/skipped seed counts. In `both` mode, shell segments
without an actual CMB intersection cannot seed a paired exterior arc, so the
two exported line counts need not match. Remaining `immediate_cmb`,
`short_arc`, or `interpolation_stop` results warrant inspection; increasing the
seed count alone does not establish convergence. Test one frame into a
separate output folder before regenerating a long sequence. Existing bundles
need reconversion to receive the corrected line coordinates.

### Two datasets

Use **Dataset → Secondary path / URL** to load a second converted dataset. Its
`nr`, `ntheta`, and `nphi` dimensions must match the primary dataset. Secondary
fields are prefixed with the selected secondary label and can be assigned to
the same surfaces and slices as primary fields.

## Portable view-state codes

The **View state** folder can copy, show, load, or save a compact `DTV2:` code.
A view state records the complete visual setup, including:

- selected fields and visibility switches;
- colour maps, custom colours, ranges, and opacities;
- slice positions, clipping, quarter masks, and isosurfaces;
- field-line style;
- Earth and lighting settings;
- camera position, target, scale, and field of view;
- background plus title/legend/quick-export visibility, collapse state,
  position, and size;
- export and video presentation settings.

It deliberately does **not** contain the primary or secondary dataset path,
secondary dataset identity, current sequence frame, or dataset-specific frame
ranges/cache state. Load a dataset first, then paste a view code to reproduce
the same figure setup without changing that dataset. Field names unavailable in
the current dataset are skipped and reported; all compatible settings are still
applied.

Older `DTV1:` codes remain readable, but any dataset path embedded in them is
ignored.

### Default view stored with a dataset

Put a plain UTF-8 file named **`view.DTV2`** beside `metadata.json`. Its contents
are the complete `DTV2:...` code produced by **View state → Copy code**, with
an optional final newline. No change to `metadata.json` is needed. DEEPscope
automatically applies that view when opening the primary dataset, before the
first render. The convention works with local folders, local-server paths,
HTTP datasets, Figshare and Zenodo records that include the file.

To save the current setup, use **View state → Save view.DTV2**:

1. For a folder opened with **Select primary folder**, a supporting browser asks
   for write permission and creates or replaces `view.DTV2` in that folder.
   Reading a dataset never requests write access.
2. If the source is remote, was opened by a server path, or the browser only
   supports read-only folder selection, the viewer offers a `view.DTV2` file to
   save/download. Place it beside `metadata.json`, or upload it with the remote
   dataset. A web page cannot directly write into a Figshare/Zenodo record.

**Download view.DTV2** always offers a separate copy. After adding a file through
a download, reselect a folder opened with read-only file input so the viewer can
see the new file. After updating a remote record, refresh the page and reopen
the dataset. Keep the exact filename `view.DTV2`, including its capitalization.
Writing through a selected folder depends on the browser's
[File System Access permission support](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemHandle/requestPermission).

For a sequence, put the shared view at the root beside `sequence.json`; **Save
view.DTV2** writes there even when a later frame is selected. If the root has no
usable view file, the initial frame's `view.DTV2` is tried. The view is applied
once when opening the sequence, not at each playback frame. Secondary datasets
do not replace the primary view.

A missing view file leaves normal loading unchanged. Invalid/unreadable view
files are reported without blocking the dataset; optional network lookups have
a five-second timeout. If saved settings fail to render, the viewer retries the
new dataset with its normal view. Compatible settings are applied, unavailable
fields are skipped, and dataset paths/frame numbers embedded in a code are
ignored. Re-running a converter preserves a `view.DTV2` at the output root.

## Sequences

A sequence root has this shape:

```text
viewer_sequence/
├── sequence.json
└── frames/
    ├── state00001/
    │   ├── metadata.json
    │   └── ...
    └── state00002/
        ├── metadata.json
        └── ...
```

Playback controls select the first and last frame, frame rate, preload count,
and cache limit. Isosurfaces and field lines can be deferred during playback to
keep interaction responsive.

Loading is transactional: metadata, coordinates, and a complete field are
validated before a new dataset replaces the current scene. Requests time out,
binary lengths must match the declared grid, a broken sequence frame stops
playback cleanly, and the viewer attempts to restore the last working dataset
or frame after a rendering failure.

Only the latest asynchronous request may replace a surface or field-line set.
A failed replacement leaves the preceding mesh displayed. Isosurface geometry
is cached independently of its colour, opacity, and transparency mode.

Frames and secondary datasets are checked against the actual `r`, `theta`, and
`phi` arrays, not just their dimensions. If metadata declares a coordinates
file, that file is required. Uniform-grid fallback is only for legacy bundles
that do not declare one. A transferred view code validates field availability
(including the isosurface field) and restores numeric options such as the Earth
radius scale without loading a dataset or changing the selected frame.

## Export

The export panel and **Export** folder provide:

- PNG with visible colour-bar legends;
- PDF with visible colour-bar legends;
- WebM camera rotation;
- an offline sequence of PNG frames, written to a selected folder or an
  uncompressed ZIP fallback.

PNG and PDF use the selected viewer background colour. Hidden or collapsed
legends are omitted, and visible legends follow their selected or dragged
position.

Video motion modes include a fixed current view, 360° azimuth, combined
azimuth/elevation motion, and personalized staged motion. A custom specification
such as:

```text
-180p,45t;180p
```

rotates azimuth (`p`) and elevation (`t`) in degrees. Comma-separated commands
run together within a stage; semicolon-separated stages run in order.

## Common converted-data contract

A single-frame dataset normally contains:

```text
viewer_data/
├── metadata.json
├── coordinates.json          # optional for uniform grids
├── profiles.json             # optional
├── Br_volume.f32
├── Bt_volume.f32
├── Bp_volume.f32
├── C_volume.f32
└── ...
```

Volume arrays are raw little-endian float32 values in C-order
`(radius, theta, phi)`. Their exact element count must be:

```text
nr × ntheta × nphi
```

`metadata.json` maps display names to files:

```json
{
  "nr": 64,
  "ntheta": 128,
  "nphi": 256,
  "fields": {
    "Br": "Br_volume.f32",
    "C": "C_volume.f32"
  },
  "coordinates": "coordinates.json"
}
```

Surface fields, field-line files, radii, parameters, geometry, and provenance
are described by additional metadata keys written by the converters. Use an
existing converted dataset as the schema reference rather than editing binary
files by hand.

## Converter setup

Create an isolated Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install only the requirements needed for the selected converter:

```bash
python -m pip install -r requirements-converters.txt  # Leeds
python -m pip install -r requirements-xshells.txt     # XSHELLS
python -m pip install -r requirements-magic.txt       # MagIC bridge
```

Run any converter with `--help` for the complete and current option list.

### Angular spectral truncation

All three converters accept `--spectral-lmax L`. **The default is 0: keep all
available source degrees.** Omitting the option is equivalent to setting it to
0. This changes the Leeds converter's previous default of 128; specify 128
explicitly to retain that cutoff.

For example, add this to a Leeds, XSHELLS or MagIC conversion command:

```bash
--spectral-lmax 128
```

When the input contains degrees above 128, this removes those modes and
constructs a smaller angular grid. Radial samples are unchanged. A float32
volume occupies `4 * nr * ntheta * nphi` bytes, so reducing the angular
dimensions reduces every exported volume's size. A requested cutoff at or
above the available degree leaves the original grid and fields unchanged.
`metadata.json` records the requested and effective cutoff under
`spectral_truncation`.

Leeds and XSHELLS truncate their native scalar and poloidal/toroidal
coefficients before physical-space synthesis. XSHELLS retains radial ghost
coefficients and each field's radial domain. Omit explicit `--nlat`/`--nphi`
when you want XSHELLS to choose its smaller grid automatically.

MagIC graphic files contain physical samples. The converter first reads the
native data, projects it onto scalar/vector spherical harmonics, and
synthesizes the retained degrees on a smaller grid. Scalars keep their
degree-zero mean; velocity and magnetic fields use the coupled vector
components of the [Q/S/T formulation](https://nschaeff.bitbucket.io/shtns/vsh.html).
This needs the native Gauss colatitude grid but adds no runtime dependency.
It reduces output size, while the initial native-file read still needs its
original memory allocation.

Gradients, EMF, induction and field lines are then calculated from the
truncated source fields. Nonlinear products can contain higher degrees than
the input cutoff; reduced output grids do not preserve all native nonlinear
detail. Check convergence for the quantities you use. CMB/Earth map cutoffs
and MagIC's `--external-lmax` (default 32) remain separate controls.

## Leeds converter

Convert one state file:

```bash
python tools/convert_state_to_viewer.py \
  --state /path/to/state00001.cdf.dat \
  --out public/data_leeds
```

Convert a numbered sequence:

```bash
python tools/convert_state_to_viewer.py \
  --folder /path/to/leeds_run \
  --sequence-first 1000 \
  --sequence-last 2000 \
  --sequence-step 50 \
  --sequence-clear \
  --out public/data_leeds_sequence
```

The bundled `modules.py` contains the Leeds shell and regular full-sphere
spectral transforms. Geometry can be detected or set explicitly. Optional
outputs include scalar gradients, azimuthal means and fluctuations, magnetic
field continuation, internal/exterior field lines, motional EMF, and induction.

Converter version 3.3 corrects the Leeds longitude coordinates to match SHTns:
`phi[j] = 2*pi*j/nphi`, with no duplicate endpoint. Regenerate older Leeds
bundles to apply this correction; updating the viewer alone cannot repair
coordinates and field-line geometry already exported into a bundle.

## XSHELLS converter

Discover conventional files from a run folder and tag:

```bash
python tools/convert_xshells_to_viewer.py \
  --folder /path/to/xshells_run \
  --tag run_tag \
  --out public/data_xshells
```

Or provide explicit files:

```bash
python tools/convert_xshells_to_viewer.py \
  --velocity /path/to/fieldU.run_tag \
  --magnetic /path/to/fieldB.run_tag \
  --temperature /path/to/fieldT.run_tag \
  --composition /path/to/fieldC.run_tag \
  --out public/data_xshells
```

The converter supports shell and conducting-inner-core geometry, selectable
SHTns output grids, downsampling, gradients, `N2`, magnetic continuation,
field lines, EMF, and induction when the source quantities are available.
Direct script invocation resolves the bundled `modules.py` automatically;
XSHELLS does not need the Leeds-only `--modules-dir` option.

## MagIC converter

The MagIC converter reads genuine 3-D graphic snapshots through the official
`MagicGraph` class. Make the MagIC Python package importable, for example:

```bash
git clone https://github.com/magic-sph/magic.git ../magic
python -c 'import sys; sys.path.insert(0, "../magic/python"); from magic import MagicGraph; print("MagicGraph OK")'
```

Convert one snapshot:

```bash
python tools/convert_magic_to_viewer.py \
  --graph /path/to/G_17.run_tag \
  --magic-python-dir ../magic/python \
  --out public/data_magic
```

Convert a sequence:

```bash
python tools/convert_magic_to_viewer.py \
  --folder /path/to/magic_run \
  --tag run_tag \
  --sequence-first 1 \
  --sequence-last 20 \
  --sequence-step 1 \
  --sequence-clear \
  --magic-python-dir ../magic/python \
  --out public/data_magic_sequence
```

Depending on the source file, the converter can write velocity, magnetic,
entropy/temperature, composition, pressure, phase, mean/fluctuating fields,
gradients, `N2`, EMF, induction, CMB/Earth magnetic maps, and field lines. It
unfolds MagIC `minc` symmetry and converts arrays to increasing-radius
`(radius, theta, phi)` order.

An open validation source is Yifan Wu's MagIC dataset on
[Zenodo record 8036223](https://zenodo.org/records/8036223). See
[`MAGIC_CONVERTER.md`](MAGIC_CONVERTER.md) for the tested archive member,
extraction command, physical parameters, and detailed caveats.

## Useful converter options

The three converters intentionally share common controls where possible:

```text
--spectral-lmax L
--downsample-r N --downsample-theta N --downsample-phi N
--geometry auto|full-sphere|shell|conducting-inner-core
--skip-field-lines
--field-line-mode shell|exterior|both
--line-seeds N
--cmb-br-ltrunc L
--earth-br-ltrunc L
--emf
--induction
--incremental
--cache-dir /path/to/conversion-cache
--force
--Ek VALUE --Pr VALUE --Sc VALUE --RaT VALUE --RaC VALUE
```

Not every option applies to every source format. A converter writes only fields
supported by its input and does not invent absent magnetic or compositional
quantities.

### Incremental conversion

All three converters accept **`--incremental`**. Add it to the same conversion
command, keeping its source and output paths:

```text
--incremental
```

The first incremental run calculates the requested bundle and saves a
lossless cache of selected expensive operations, including native transforms,
gradients, magnetic diagnostics, surface synthesis and field-line tracing.
Later runs check source contents, options, calculation code, backend versions,
and cached-file checksums before reusing results. An unchanged complete bundle
is skipped. Changed conversions reuse matching calculations and publish a
new validated bundle; simple arithmetic, output assembly and file I/O can
still run. Adding a diagnostic does not require repeating cached transforms.

Existing bundles without a calculation cache need an initial conversion to
populate it. Native precision and working grids are retained: downsampled
viewer `.f32` files are not used to reconstruct missing native calculations.
Changing inputs, truncation, grids, or the relevant calculation invalidates
affected results. A damaged cache entry is recomputed. Source and output checks
still read files, so checking a large bundle takes time even when no calculation
is needed.

By default the cache is `.deepscope-cache/` at the Git project root (or beside
the output when outside a checkout), outside the published `public/` tree.
The cache requires additional disk space and is ignored by Git. Use
`--cache-dir /path/to/conversion-cache` to place it elsewhere, outside the
output and `public/`. Deleting this disposable cache leaves converted data
intact; missing calculations will be rebuilt when needed.

Combine **`--incremental --force`** to recompute and refresh cached calculations.
Without `--incremental`, conversion runs normally. Leeds and MagIC sequence
extensions reuse unchanged frames and preserve root and per-frame `view.DTV2`
files. XSHELLS keeps its existing single-snapshot interface. Previous output
backups and validation before publication also apply to incremental runs.

### Sampling and output safety

Radial downsampling retains both radial endpoints and the CMB/ICB. Angular
downsampling applies a Gaussian low-pass in physical colatitude and Fourier
resampling in longitude. Longitudes remain uniformly spaced around the full
period even when the requested stride does not divide the native sample count.
Surface maps use the same angular sampling as volumes. These filters reduce
aliasing; they are not a replacement for checking resolution convergence.
Diagnostics and field lines use the working grid before these output strides
are applied. That is the native grid when spectral truncation is disabled,
or the grid synthesized at the retained degree when `--spectral-lmax` reduces
the source. Leave the strides at 1 when no further viewer-grid filtering is
wanted.

`Cnol0` and `Compnol0` are no longer exported. The `m=0`-removed diagnostics
(`Cnom0`, `Compnom0`) are unchanged. From converter 3.4.2, the duplicate names
`C_nom0` and `Comp_nom0` and their separate files are no longer exported.
The viewer removes these duplicate choices from older bundles too, and maps
old saved-view selections to `Cnom0`/`Compnom0`. If an old bundle contains only
an underscored name, its existing file is exposed under the canonical name.
Updating the viewer fixes the field menus without reconverting old datasets;
it does not delete files from existing local or remote bundles.

All three converter CLIs build into a staging directory and validate the
complete bundle before replacing `--out`. A failed conversion or sequence frame
leaves the previous output intact. The old output is retained at the printed
backup path: `.deepscope-backups/` at the Git checkout root when on the same
filesystem, otherwise a sibling `.deepscope-backup-*` directory. Backups consume
disk space; keep them out of published datasets and remove them manually only
after checking the new output. Unrelated files in the output are preserved.
Use a dedicated output subdirectory, not the current directory or repository
root. `--sequence-clear` remains accepted for compatibility; a new sequence is
always staged in full and published only after every selected frame succeeds.

NaN, infinity, and float32 overflow now stop conversion instead of becoming
zeros or invalid binary values. The explicitly reported XSHELLS singular
`r=0` spherical-component regularization is retained. A failed second publish
rename is rolled back; an abrupt process interruption between the two renames
may require restoring the printed backup manually.

## Validation

Run the converter test suite:

```bash
npm run test-converters
```

Run viewer logic regressions, then validate syntax and the production bundle:

```bash
node --test tests/test_viewer_regressions.mjs
node --check src/main.js
npm run build
```

The viewer regressions use test doubles for rendering and networking. They do
not replace a browser/GPU check of the demo, remote loading, and exports.

Additional scientific and release checks are documented in:

- [`CONVERTER_VALIDATION.md`](CONVERTER_VALIDATION.md);
- [`BUILD_VALIDATION.md`](BUILD_VALIDATION.md);
- [`LEEDS_XSHELLS_OUTPUT_PARITY_NOTES.md`](LEEDS_XSHELLS_OUTPUT_PARITY_NOTES.md);
- [`MAGIC_CONVERTER.md`](MAGIC_CONVERTER.md).

## GitHub Pages deployment

The workflow in `.github/workflows/deploy-pages.yml` installs dependencies,
builds `dist/`, and deploys it to GitHub Pages.

Repository setup:

1. Open **Settings → Pages**.
2. Under **Build and deployment**, select **GitHub Actions**.
3. Push to `main`, or run the workflow manually from **Actions**.
4. Open the URL reported by the deploy job.

For a public repository whose code should remain owner-controlled, enable a
`main` branch ruleset under **Settings → Rules → Rulesets**. Require pull
requests, prevent force pushes and deletion, require successful Actions checks,
and restrict updates to the repository owner or an approved team. Public users
can read or fork the code, but cannot push to the repository unless explicitly
granted write access.

See [`GITHUB_PAGES.md`](GITHUB_PAGES.md) for the deployment and privacy model.

## Troubleshooting

### A remote dataset does not load

- Confirm the record is public.
- Confirm `metadata.json` or `sequence.json` is present as an individual file.
- Confirm every file name in the metadata matches exactly, including case.
- Confirm each `.f32` size is `nr × ntheta × nphi × 4` bytes.
- For a generic web host, inspect its CORS response headers.
- Do not paste an ordinary cloud-drive folder sharing page.

The viewer reports timeouts, missing files, invalid JSON, coordinate-size
mismatches, and truncated arrays rather than silently continuing.

### The viewer becomes slow on a sequence

- Reduce the preload frame count.
- Lower the cache limit.
- Enable deferred isosurfaces and field lines.
- Downsample during conversion.
- Pause playback before changing expensive isosurface or field-line options.

### The site still shows an older build

Check the latest GitHub Actions run, then perform a hard refresh. GitHub Pages
may take a short time to publish after the workflow completes.

### MagIC cannot import `MagicGraph`

Pass the directory containing MagIC's `magic` Python package:

```bash
python tools/convert_magic_to_viewer.py \
  --graph /path/to/G_1.run_tag \
  --magic-python-dir /path/to/magic/python \
  --out public/data_magic
```

## Project layout

```text
DEEP/
├── .github/workflows/deploy-pages.yml
├── cloudflare/figshare-proxy.js
├── index.html
├── src/
│   ├── main.js
│   └── style.css
├── public/
│   ├── assets/
│   └── data/
├── tools/
│   ├── convert_state_to_viewer.py
│   ├── convert_xshells_to_viewer.py
│   ├── convert_magic_to_viewer.py
│   └── make_demo_data.py
├── tests/test_converter_package.py
├── modules.py
├── package.json
└── package-lock.json
```

## License

See [`LICENSE`](LICENSE).
