# DEEPscope — Spherical Dynamo Viewer

DEEPscope is a browser-based Three.js viewer for three-dimensional spherical-dynamo
and convection simulations. It includes converters for:

- the Leeds Spherical Dynamo code;
- XSHELLS through `pyxshells`;
- MagIC `G_#.TAG` and `G_ave.TAG` graphic files through MagIC's `MagicGraph`
  reader;
- Calypso merged ASCII/binary spectral restarts (`*.fst` / `*.fsb`, also
  native gzip) with their matching grid controls;
- QuICC/EPMDynamoCode spherical HDF5 spectral states: full-sphere `WLFl`/`WLFm`
  and spherical-shell `SLFl`/`SLFm` ordering;
- Rayleigh `Spherical_3D` outputs and single-domain version-2 Chebyshev checkpoints
  (see [Rayleigh converter and public example](RAYLEIGH_CONVERTER.md)).

Open the hosted viewer at
[the DEEPscope viewer](https://ludhovik.github.io/DEEP/), or run it locally
with Vite. Local datasets are read in the browser and are not uploaded.

## What the viewer can display

- CMB and ICB fields;
- a spherical surface at any radius;
- two equatorial and two meridional slices;
- positive and negative isosurfaces with colour/value legends;
- magnetic slices and isosurfaces inside a resolved inner core;
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

The progress box shows the current file or calculation and includes **Cancel**.
Reads show received bytes; a percentage appears when the decoded file size is
known. Unknown or compressed download sizes use an indeterminate indicator.
The box remains accessible with the title collapsed or the opening screen visible.
Cancelling a primary dataset switch restores the preceding dataset and view;
cancelling a geometry replacement leaves the preceding geometry displayed.

Tube simplification, tube mesh construction and isosurface generation run in a
browser Web Worker. This uses the visitor's computer and needs no Cloudflare
deployment. Cancellation terminates active calculations and clears queued work;
a later request starts a fresh worker. Source arrays stay available in the
viewer cache, and geometry buffers transfer back without another full copy.
Parsing large JSON files, copying inputs and uploading meshes to the graphics
device still take time; the tube budget is not a total browser-memory cap.

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
article API. Record responses bypass browser and Cloudflare caches so published
file replacements can be discovered. See [proxy deployment](GITHUB_PAGES.md#figshare-proxy)
when updating the Worker; pushing to GitHub Pages does not deploy it.

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

Each meridional plane displays the same field, scale, colour map and opacity on
both halves by default. Enable **Independent sides** to expose separate controls
for **Right (+s, longitude phi)** and **Left (-s, longitude phi + 180°)**,
including separate colourbars. Longitude and visibility remain common to the
plane. Old `DTV2` view codes containing only one meridional setting stay linked;
codes that already contain different half settings retain the independent view.

The CMB can be clipped by one or two meridional planes or by an explicit
eight-quarter mask. In **Between meridional planes** mode, **CMB side** switches
between the complementary front and rear sectors. Open **Planet / moon surface**, enable **Show**, choose
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
do not change the tube diameter. Tube appearance options are included in DTV2 codes.

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

**Tube simplification → Auto fit budget** is optional and off by default. With
**Simplify tubes** enabled, it increases the shape and B² error tolerances until
the estimated combined mesh fits the selected tube budget. Each trial starts
from the saved polylines and retains every selected line, its endpoints, pairing
identifiers, magnetic extrema and missing-data breaks.

- **Auto max shape / ro**, default `0.005`, bounds the permitted shape error
  (`0.5%` of the outer radius).
- **Auto max B² error %**, default `5`, bounds the permitted B² interpolation error.

Automatic fitting never exceeds these bounds, even if the manual tolerances are
larger. If fitting is impossible within them, it preserves the previous display
and asks for a different stride, side count, memory budget or error bounds. It
does not silently drop additional lines. The title reports the tolerances used.
Turning off **Auto fit budget** restores the manual tolerances; turning off
**Simplify tubes** uses every saved sample.

DTV2 saves the automatic mode and error bounds. The result also depends on the
session's memory budget. For a repeatable publication mesh across computers,
turn off automatic fitting and enter the reported tolerances manually, or turn
off simplification entirely.

In **Magnetic field lines → Tube memory**, **Custom limit** is off by default,
using a **192 MiB** geometry budget. Turn it on to set **Limit (MiB)** between
**32 and 2048 MiB**, for example `512`. Turning it off restores the default
without forgetting the custom value. This is a session preference: opening a
dataset or applying a DTV2 code leaves it unchanged; refreshing the page restores
the default. View codes do not contain this memory preference.

The budget checks the estimated combined shell and exterior tube geometry for
the requested view, **after stride and simplification**, before allocation.
It also applies to reused geometry and requests still loading. Raising the limit
does not rebuild an otherwise matching mesh. The title reports retained/original
point counts and the mesh estimate against the selected limit; an oversized
request leaves the previous display intact, including when lowering the limit.

This is not a cap on total browser RAM or graphics memory: source arrays,
temporary work, graphics copies, volumes and other cached views use additional
memory. The sequence/data cache has its own limit. Higher tube limits allow
larger meshes and can consume substantially more total memory. Alternatively,
increase the simplification error limits modestly, increase **Line stride**, or
reduce **Tube sides**. Reducing diameter or opacity does not reduce vertex count.

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

All six converters trace a line in Cartesian coordinates with arclength-like
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
poloidal coefficients, while XSHELLS, MagIC, Calypso, QuICC and Rayleigh analyse the physical CMB `Br`.
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

Opening a primary dataset, including **Load primary path** on the same dataset,
starts with the default camera, colours, visibility, scales, lines and panel
layout, then applies that dataset's saved view. Deleting the published view file
therefore restores the default appearance when the dataset is reopened. Partial
dataset view files also start from defaults, without inheriting the preceding
dataset's settings. To transfer your current setup deliberately, copy its view
code before opening another dataset and load that code afterwards.

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
see the new file. After updating a remote record, publish the changes and reopen
the dataset. Each saved-view read refreshes the Figshare/Zenodo file list and
downloads the view without using cached contents, so a replaced file ID is
discovered without refreshing the page. Ordinary data reads still reuse their
caches. Keep the exact filename `view.DTV2`, including its capitalization.
On Figshare, saving an edit as a draft is not enough: the base DOI exposes the
latest **published** version ([Figshare versioning](https://info.figshare.com/user-guide/how-versioning-works/)).
Writing through a selected folder depends on the browser's
[File System Access permission support](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemHandle/requestPermission).

For a sequence, put the shared view at the root beside `sequence.json`; **Save
view.DTV2** writes there even when a later frame is selected. If the root has no
usable view file, the initial frame's `view.DTV2` is tried. The view is applied
once when opening the sequence, not at each playback frame. Secondary datasets
do not replace the primary view.

A missing view file uses the default appearance, reported as **default view
applied** in the title. Invalid/unreadable view files are reported without
blocking the dataset; optional network lookups have a five-second timeout. If
saved settings fail to render, the viewer retries the new dataset with its
default view. A failed dataset replacement restores the previous dataset and
view. Compatible saved settings are applied, unavailable
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
├── T_volume.f32              # temperature or codensity
├── C_volume.f32              # composition, when present
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
    "T": "T_volume.f32",
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
python -m pip install -r requirements-calypso.txt     # Calypso (NumPy/SciPy)
python -m pip install -r requirements-quicc.txt       # QuICC/EPM (NumPy/SciPy/h5py)
python -m pip install -r requirements-rayleigh.txt    # Rayleigh (NumPy/SciPy)
```

Run any converter with `--help` for the complete and current option list.

### Angular spectral truncation

All six converters accept `--spectral-lmax L`. **The default is 0: keep all
available source degrees.** Omitting the option is equivalent to setting it to
0. This changes the Leeds converter's previous default of 128; specify 128
explicitly to retain that cutoff.

For example, add this to a Leeds, XSHELLS, MagIC, Calypso, QuICC or Rayleigh conversion command:

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

Leeds, XSHELLS, Calypso and QuICC truncate their native scalar and poloidal/toroidal
coefficients before physical-space synthesis. Rayleigh checkpoints do the same. XSHELLS retains radial ghost
coefficients and each field's radial domain. Omit explicit `--nlat`/`--nphi`
when you want XSHELLS to choose its smaller grid automatically.

MagIC graphic files and Rayleigh Spherical_3D files contain physical samples. The converter first reads the
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
and MagIC/Calypso/QuICC/Rayleigh's `--external-lmax` (default 32) remain separate controls.

## Leeds converter

Convert one state file:

```bash
python tools/convert_leeds_to_viewer.py \
  --state /path/to/state00001.cdf.dat \
  --out public/data_leeds
```

Convert a numbered sequence:

```bash
python tools/convert_leeds_to_viewer.py \
  --folder /path/to/leeds_run \
  --sequence-first 1000 \
  --sequence-last 2000 \
  --sequence-step 50 \
  --sequence-clear \
  --out public/data_leeds_sequence
```

The bundled `modules.py` contains the Leeds shell and regular full-sphere
spectral transforms. Geometry can be detected or set explicitly. Optional
outputs include spherical and cylindrical scalar gradients, azimuthal means and fluctuations, magnetic
field continuation, internal/exterior field lines, motional EMF, and induction.

Converter version 3.3 corrects the Leeds longitude coordinates to match SHTns:
`phi[j] = 2*pi*j/nphi`, with no duplicate endpoint. Regenerate older Leeds
bundles to apply this correction; updating the viewer alone cannot repair
coordinates and field-line geometry already exported into a bundle.

### Dimensionless parameters (all converters)

The Leeds command is now `python tools/convert_leeds_to_viewer.py` (npm:
`npm run convert-leeds -- ...`). Update scripts using the old filename.

Parameters come from native simulation metadata, **never folder or file names**.
Explicit `--Ek`/`--E`, `--Pr`, `--Sc`, `--RaT`/`--Ra`, `--RaC`/`--Ra_comp`,
and `--Pm` overrides take precedence. Missing Ek, Pr, Sc, RaT, RaC and Pm are
requested individually when running interactively. Blank answers leave values
unknown (`null` in metadata); prompts appear on separate lines. Use
`--no-parameter-prompt` for batch jobs; missing values are reported.

An explicit `--RaC 0` selects a thermal-only conversion. All six converters
skip composition synthesis where their input format permits it and omit `C`,
`C_nom0`, `C_phiavg`, every composition gradient, and composition profiles.
`N2` retains its thermal contribution. This policy applies only to the explicit
CLI option; a zero stored in native metadata does not silently discard a field.
Combining `--RaC 0` with a composition name in `--output` is an error. With
`--incremental`, the new staged bundle also removes previously managed
composition `.f32` files while preserving `view.DTV2`.

Leeds reads NetCDF global attributes: `E → Ek`, `Ra → RaT`, `Ra_comp → RaC`,
and `Pr`, `Sc`, `Pm` directly. Optional `Ro`, `q` and `riro` (saved as
`radius_ratio`) are retained when present, without prompting for these
code-specific extras. Both NetCDF4 and older NetCDF3 files are supported.
MagIC reads its graphic/header and associated log metadata; QuICC reads its
HDF5 physical parameters; Calypso reads its native dimensionless controls;
Rayleigh reads `main_input`. XSHELLS uses exposed native field-header parameters;
standard field files may lack them, in which case supply overrides or answer
the prompts. No directory-name values are substituted.

Native N2 conventions remain source-specific. Calypso's native momentum
coefficients remain authoritative unless explicitly overridden; a modified
Rayleigh number is not silently treated as conventional Ra. Leeds omits N2
when its required inputs remain unknown, while exporting the other fields.

Each sequence frame reads its own native parameters. Answers to missing-value
prompts are reused only where later frames also lack that value. Explicit CLI
overrides apply to every frame. Existing numerical caches remain usable through
the Leeds rename; metadata/output validation is refreshed on the first update.
Unchanged incremental conversions still skip; use an explicit parameter override
when changing a previously entered value.

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
`MagicGraph` class, with a DEEPscope compatibility reader for complete Version 9
fluid shells whose declared inner-core records are absent. The MagIC Python
installation needs no modifications. Make the package importable, for example:

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

Archived names such as `G_a60.run_tag` work directly with `--graph`; no rename
or symbolic link is required. The `a60` token is kept as a file identifier and
does not imply time averaging. Numeric folder/sequence selection continues to
select `G_<number>` files only.

Some Version 9 archives declare an inner radial grid but end immediately after
the complete fluid shell. DEEPscope validates the exact shell size, record
markers and grid coverage, then reads the seven available fields (entropy,
three velocity and three magnetic components). It warns about the absent IC
records and records this in `metadata.json` under `source_reader` and
`inner_core.available=false`. The header's conductivity ratio `sigma` and
conducting-boundary classification are preserved. There are no invented
inner-core samples. Omission during export cannot be distinguished from a
download truncated exactly at the shell boundary; compare the archive checksum
if available. Partial shell/IC records are not silently accepted by this path.
Normal files, including those with IC records, still use `MagicGraph`.
Input precision must match the file (`--precision float64` for double precision).

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

## Calypso converter

The Calypso converter reads merged ASCII/binary spectral restarts with their original
`control_MHD` and linked spherical-grid controls. No Calypso installation or
SHTns is required. Keep the extracted archive's directory structure intact.

```bash
python3 tools/convert_calypso_to_viewer.py \
  --folder /path/to/shell/dynamobench_case_1 \
  --out public/data_calypso \
  --incremental --emf --induction \
  --cmb-br-ltrunc 13 --field-line-mode both \
  --line-seeds 360 --external-rmax 40 --external-nr 192 \
  --line-max-steps 4000
```

The latest restart is selected; `--state-number 0` selects the initial state.
All source degrees are retained by default. For the supplied L=63 benchmark,
`--spectral-lmax 32` reduces the angular output grid from 96 × 192 to 34 × 66.
Add `--sequence-first 0 --sequence-last 1 --sequence-step 1` to convert both
supplied restarts. Temperature/codensity is `T`; composition, when present, is `C`.

Full-sphere `half_Chebyshev` grids and native `merged_bin_gz` restarts are
supported, including the separately stored centre node. For the supplied
full-sphere run, use `--folder /path/to/full_sphere/sph_shell_842`; the same
export options apply. Restart file indices and solver timestep numbers are
stored separately: `rst.99.fsb.gz` contains simulation step 990000.
The shell run is checked against its analytic initial field and independent
physical snapshot; the real full-sphere restart is checked for binary layout,
grid/centre consistency and a complete export. Analytic fixtures check the
full-sphere vector reconstruction.
See [CALYPSO_CONVERTER.md](CALYPSO_CONVERTER.md) for native format requirements,
N2 normalization, equations and supported control layouts.

## QuICC / EPMDynamoCode converter

```bash
python3 tools/convert_quicc_to_viewer.py \
  --state /path/to/state0000.hdf5 \
  --out public/data_quicc \
  --incremental --cache-dir "$HOME/.cache/deepscope" \
  --emf --induction --cmb-br-ltrunc 13 \
  --field-line-mode both --line-seeds 360 \
  --external-rmax 40 --external-nr 192 --line-max-steps 4000
```

Use `--folder` to select the latest numbered state, `--state-number` for a
specific index, or `--sequence-first/--sequence-last/--sequence-step` for a
sequence. Default spectral truncation is off; `--spectral-lmax 128` filters
coefficients before reconstruction. Incremental conversion reuses each native
field synthesis when you add diagnostics or change field-line settings.

This reader supports legacy EPM and modern QuICC **full-sphere Worland** states
(`WLFl`/`WLFm`), with analytic regular limits at the centre, and **spherical-shell
Chebyshev** states (`SLFl`/`SLFm`). Shell boundaries come from native
`physical/lower1d` and `physical/upper1d` values. The same command selects the
correct radial reconstruction automatically. Extract archives first and pass
the `.hdf5` state to `--state`. Cartesian/cylindrical schemes and separate
imposed/background files need their own readers; these formats provide no
separately resolved inner-core fields for `--inner-core-only`. Source scalar coefficients are exported
as stored, without adding an assumed conductive background.

Standard builds are detected by file layout: EPM uses its Schmidt normalization;
modern QuICC uses SHUnity. Custom solver builds must select the matching
`--angular-normalization`, `--worland-family` and `--worland-normalization`.
N² requires an explicit `--n2-convention` because the state format does not
identify the model’s Rayleigh normalization; gradients are exported by default.
See [QUICC_CONVERTER.md](QUICC_CONVERTER.md) for equations, normalization limits,
a verified downloadable dynamo benchmark and the validation command.

## Rayleigh converter

Rayleigh full `Spherical_3D` snapshots and supported version-2, single-domain
Chebyshev checkpoints can be converted without installing Rayleigh:

```bash
python3 tools/convert_rayleigh_to_viewer.py \
  --checkpoint /path/to/run/Checkpoints/00040000 \
  --out public/data_rayleigh \
  --incremental --cache-dir "$HOME/.cache/deepscope"
```

For physical outputs, use `--snapshot /path/to/Spherical_3D/00040000_grid`.
The shared diagnostics and magnetic field-line options apply when the source
contains the required fields. N2 is omitted unless a matching convention is
explicitly selected. See [RAYLEIGH_CONVERTER.md](RAYLEIGH_CONVERTER.md) for
supported layouts, equations, sequences and a tested public convection dataset.

## Vorticity and magnetic polarity

All six converters export `vort_r`, `vort_theta`, `vort_phi`, `vort_s`, `vort_z`
and `vort_abs` when velocity is available. These are components and magnitude
of **curl(u)** in the input velocity's reference frame; no planetary `2 Omega`
term is added. They can be selected for slices and isosurfaces.

For yellow/blue magnetic lines or B² tubes, choose **Colour by → Local radial
polarity**: yellow for local outward `Br > 0`, blue for inward `Br < 0`.
Colour can change along a line. **CMB starting polarity** retains the older
single-colour footpoint convention. Grey local-polarity samples have zero or
unavailable Br; older bundles need reconversion to supply local values.

Rerun the same converter command with `--incremental` and its existing cache
to add these outputs. Cached compatible line paths are sampled, not retraced.
See [VORTICITY_POLARITY.md](VORTICITY_POLARITY.md) for equations, units, centre
handling, update instructions and validation.

## Useful converter options

The six converters intentionally share common controls where possible:

```text
--spectral-lmax L
--output ur Br C vort_r
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

### Selecting specific volume fields

All six converters accept `--output` followed by case-sensitive field names:

```bash
python3 tools/convert_leeds_to_viewer.py \
  --state /path/to/state00001.cdf.dat \
  --out public/data_selected \
  --incremental \
  --output ur Br T vort_r
```

This writes only `ur_volume.f32`, `Br_volume.f32`, `T_volume.f32` and
`vort_r_volume.f32`, together with the metadata and coordinates needed by the
viewer. Other volume diagnostics, surface maps and field lines are skipped,
even if map or field-line options appear in the command. Native input readers
may still read a whole snapshot; vector transforms and curls calculate coupled
components when required. Those dependencies remain internal and are not
exported. For example, `vort_r` needs the velocity vector but does not request
helicity, scalar gradients or magnetic diagnostics.

**Omit `--output` to retain the normal full export.** The existing `--emf` and
`--induction` switches remain opt-in. With explicit selection they enable the
calculation but export only the named components, for example:

```text
--output ur Br EMFr --emf
--output vort_r vort_z Ir Iz --induction
--output grad_sT grad_zT grad_sC_nom0 grad_zC_nom0
```

Here `s = r sin(theta)` is cylindrical radius. Across every converter, `T`
means temperature or codensity and `C` means composition. An unsuffixed field
contains the complete scalar, including `m=0`; `_nom0` means that the
axisymmetric component has been removed. Thus `grad_sT` is the full thermal
gradient and `grad_sT_nom0` is its non-axisymmetric part. They are projections
of the physical spherical gradient:

```text
grad_s f = sin(theta) grad_r f + cos(theta) grad_theta f
grad_z f = cos(theta) grad_r f - sin(theta) grad_theta f
```

The implementation differentiates the full scalar and then removes its
azimuthal mean for `_nom0`. Because differentiation and the cylindrical basis
projection are linear and their coefficients do not depend on longitude, this
is mathematically equivalent to removing `m=0` before taking the gradient (up
to floating-point roundoff). A regression test checks both routes directly.

The stored thermal variable is named `C` consistently across converters;
`T` remains a compatibility alias where it already existed.

Induction calculates its required EMF internally; you need not export EMF or
add `--emf` just to select induction. Field availability depends on the input;
unknown names, unavailable fields, missing required N2 parameters/conventions,
and conflicting options produce an error without replacing a valid existing
bundle. Mean/fluctuation selections conflict with `--no-m0-fields`; gradient
and N2 selections conflict with `--no-gradients`. `--inner-core-only` is a
separate update mode and cannot be combined with `--output`. Selected magnetic
fields still include available conducting inner-core data.

Use the same `--output` list with sequence conversion to select every frame.
With `--incremental`, extending/changing the list reuses compatible cached
calculations and publishes exactly the new selection. Fields removed from the
list are removed from the new bundle. Removing `--output` restores the normal
export on the next conversion.

### Incremental conversion

All six converters accept **`--incremental`**. Add it to the same conversion
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
populate it, except for the dedicated inner-core-only update below. Native precision and working grids are retained: downsampled
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
Without `--incremental`, conversion runs normally. Leeds, MagIC, Calypso, QuICC and Rayleigh sequence
extensions reuse unchanged frames and preserve root and per-frame `view.DTV2`
files. XSHELLS keeps its existing single-snapshot interface. Previous output
backups and validation before publication also apply to incremental runs.

### Field-line runtime and progress

All six converters use the shared serial CPU tracer. They now report the
internal, exterior and return-branch stages, completed seed counts, current
integration step and elapsed time approximately every five seconds. Writing
large line files, saving completed line calculations and final validation
are also announced.
Line JSON is encoded in memory before writing, so peak memory includes the
largest encoded line file.

`--line-seeds 360` selects a 13 × 28 grid (364 seeds). Internal lines are traced
in both directions; `--line-max-steps 4000` is a limit per branch, not a total
for the dataset. Lines that wind inside the fluid can use the full budget.
The seed counter can therefore advance unevenly. Exterior lines and return
branches run afterwards. `--external-rmax` controls the exterior domain and
does not explain time spent tracing inside the shell.

A prepared interpolator reuses the fixed longitude spacing and one set of
cell weights for all three magnetic components. It preserves the existing
trilinear interpolation, RK4 steps, boundary rules and sampled strengths.

With `--incremental`, calculations already saved to cache survive Ctrl+C.
An interrupted field-line stage is not checkpointed per seed: that stage starts
again, while cached native fields and diagnostics are reused. Keep the cache
and rerun the same command. Publication occurs only after bundle validation,
so interruption leaves the preceding published dataset intact.

For a quick volume-only preview, append `--skip-field-lines`. Remove that flag
on a later incremental run to add field lines without repeating matching
cached transforms. An existing complete output with lines will be replaced
by the requested volume-only bundle if this preview flag is used.

### Magnetic fields inside the inner core

The same `Br`, `Bt`, `Bp`, `Babs`, magnetic azimuthal means and fluctuations
can cover both the fluid outer core and the solid inner core. Only stored
magnetic data are used:

- **Leeds:** separate `icr`, `icBP` and `icBT` arrays in classic NetCDF or HDF5
  states are detected automatically. Padded IC arrays are read using the length
  of `icr`. Older unmarked potentials are conventional coefficients; marked
  `regular_r_power_g_x` potentials use their saved radial power offsets.
- **XSHELLS:** the native `fieldB` radial domain must extend below the fluid ICB.
- **MagIC:** the graphic file must contain `radius_ic`, `Br_ic`, `Btheta_ic` and
  `Bphi_ic`. Incomplete core vectors or radii outside the ICB are rejected.
- **Calypso:** native spectral magnetic data must extend below the fluid ICB,
  with matching radial and boundary controls.

In the viewer, choose **Magnetic volume region → Inner core only** to restrict
magnetic radial spheres, equatorial/meridional slices and isosurfaces to that
region. **Whole core** displays both domains; **Fluid outer core** excludes the
solid interior. Choose a magnetic field on the desired slice and hide the
**ICB surface** (and CMB surface if necessary) to expose the interior. The
region choice is saved in DTV2. On datasets without resolved inner-core data,
it falls back to the available radial domain.

Fluid-only scalar, velocity and derived fields remain restricted to their
native domain. Their zero padding is excluded from slices and isosurface
interpolation. This avoids artificial isosurfaces at the solid/fluid boundary.
The output keeps one shared radial grid, without duplicate ICB coordinates;
the shared ICB sample comes from the existing outer-core output. Field lines
remain the existing fluid-shell/exterior traces. No unmeasured central region
is extrapolated: an `icr` grid starting above zero retains that smallest radius.

#### Add the core to an existing conversion

Append this option to the **same source/output command**:

```text
--inner-core-only
```

It works with or without `--incremental` and needs no calculation cache. It
requires the existing `conversion_manifest.json` to match the simulation
inputs, and verifies the existing converted files before making changes.
For example, from the repository root:

```bash
python tools/convert_leeds_to_viewer.py \
  --state simulation/state00001.cdf.dat \
  --modules-dir . \
  --out public/my_data \
  --inner-core-only
```

Use your existing paths in this example. Keep the existing sequence range for
a Leeds or MagIC sequence; each saved frame is checked and updated, including
the first-frame copy at the sequence root. XSHELLS retains its single-snapshot
interface.

This mode **uses the existing bundle's angular truncation and sampling**.
Other calculation options are not applied; `--force` is incompatible. Leeds
synthesizes only the separate inner-core magnetic data and prepends their
samples. Existing outer-core `.f32` samples are copied byte for byte; profiles,
surface fields, field-line files and saved views are retained. Binaries become
larger because the common grid gains radial rows. Reading checksums, copying
files and retaining the preceding output backup still require time and disk
space. A repeated core update does not synthesize the core again.

XSHELLS and MagIC normally already export the available inner-core data. Their
core-only update adds the explicit domain metadata to an older bundle without
running native transforms or diagnostics. If an old bundle has no core data
and the format requires reconversion, the update reports that instead of
inventing an internal field; use a normal `--incremental` conversion with the
native magnetic input. Changed simulation files or incomplete outputs require
a normal conversion as well.

The Leeds conventional reconstruction uses direct SHTns coefficients
`Q = l(l+1) P/r`, `S = P/r + dP/dr`, `T = T`, with a local physical-radius
polynomial derivative (KL=3). Marked regular potentials use the nonsingular
powers in `r` and derivatives in `x=r²`. The native layout and derivative
convention can be checked in the Leeds
[state writer](https://github.com/Leeds-Spherical-Dynamo/leeds-code/blob/main/program/io.F90),
[radial operators](https://github.com/Leeds-Spherical-Dynamo/leeds-code/blob/main/modules/meshs.F90)
and [magnetic QST conversion](https://github.com/Leeds-Spherical-Dynamo/leeds-code/blob/main/modules/variables.F90).

### Isosurface legends

When an isosurface has visible geometry, the movable legend panel shows its
colour swatch, field name and threshold (for example, `ur = 0.1` and
`ur = -0.1`). Only enabled, displayed surfaces appear. Colour edits update the
swatches; a pending or failed rebuild keeps the values of the preceding mesh.
PNG/PDF exports include the same swatches and values when legends are visible
and expanded. Collapsing or hiding the legend follows the existing export
behaviour.

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

Scalar naming version 2 uses one unambiguous contract: temperature/codensity
is `T`, composition is `C`, unsuffixed diagnostics retain `m=0`, and `_nom0`
removes it. Consequently the full buoyancy diagnostic is `N2` and its
non-axisymmetric part is `N2_nom0`. The viewer migrates old saved-view field
choices when they are applied to a version-2 bundle. Rerunning a normal
conversion with `--incremental` publishes canonical `.f32` filenames and
removes obsolete managed volume files while preserving `view.DTV2`.

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
│   ├── convert_leeds_to_viewer.py
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

Field-line polarity colours are customizable under **Magnetic field lines**:
**Br > 0 colour** and **Br < 0 colour**. Choose **Local Br (along line)** for
local outward/inward direction, or **Starting CMB Br (whole line)** to identify
the starting footpoint. Both colours are saved in DTV2 and included in legends
and exports. See [polarity conventions](VORTICITY_POLARITY.md#comparing-line-colours-with-the-cmb)
when comparing lines with a truncated CMB map.
