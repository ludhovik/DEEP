# DEEP — Dynamo Three.js Viewer

DEEP is a browser-based Three.js viewer for three-dimensional spherical-dynamo
and convection simulations. It includes converters for:

- the Leeds Spherical Dynamo code;
- XSHELLS through `pyxshells`;
- MagIC `G_#.TAG` and `G_ave.TAG` graphic files through MagIC's `MagicGraph`
  reader.

Open the hosted viewer at
[ludhovik.github.io/DEEP](https://ludhovik.github.io/DEEP/), or run it locally
with Vite. Local datasets are read in the browser and are not uploaded.

## What the viewer can display

- CMB and ICB fields;
- a spherical surface at any radius;
- two equatorial and two meridional slices;
- positive and negative isosurfaces;
- internal and exterior magnetic field lines;
- an Earth texture or an extrapolated Earth-surface radial magnetic field;
- two compatible datasets on the same grid;
- time sequences with playback, preloading, and bounded memory caching;
- PNG, PDF, WebM, and PNG-sequence output;
- transferable view-state codes.

Each display has independent field, range, colour map, and opacity controls.
The appearance panel also provides a selectable background colour and a
two-endpoint custom colour map. Legends can be hidden, collapsed, placed at a
preset corner or side, or dragged anywhere in the viewport.

## Quick start

### Use the hosted viewer

1. Open [the DEEP viewer](https://ludhovik.github.io/DEEP/).
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
eight-quarter mask. The Earth surface can show a texture or an available
extrapolated magnetic field.

### Custom appearance

Open **Appearance and legends** to set:

- the canvas background colour;
- the low and high endpoints of `custom-two-colour`;
- legend visibility;
- collapsed or expanded legend state;
- a preset legend position.

Choose `custom-two-colour` in any surface, slice, Earth-field, or field-line
colour-map selector. The two custom endpoint colours are shared by all displays
using that map.

Drag the **Legends** header to place the legend manually. Click the `−`/`+`
button to collapse or expand it. Both preset and dragged positions are included
in view-state codes and in PNG/PDF layout.

### Isosurfaces and field lines

Isosurfaces support positive and negative levels, independent colours,
opacity, resolution, and optional meridional clipping.

When the converter wrote magnetic field lines, the viewer can display internal
shell lines, exterior potential/poloidal lines, or both. Lines can be coloured
by strength or CMB seed polarity, with configurable width, opacity, stride, and
range.

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
- background and legend visibility, collapse state, and position;
- export and video presentation settings.

It deliberately does **not** contain the primary or secondary dataset path,
secondary dataset identity, current sequence frame, or dataset-specific frame
ranges/cache state. Load a dataset first, then paste a view code to reproduce
the same figure setup without changing that dataset. Field names unavailable in
the current dataset are skipped and reported; all compatible settings are still
applied.

Older `DTV1:` codes remain readable, but any dataset path embedded in them is
ignored.

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
--downsample-r N --downsample-theta N --downsample-phi N
--geometry auto|full-sphere|shell|conducting-inner-core
--skip-field-lines
--field-line-mode shell|exterior|both
--line-seeds N
--cmb-br-ltrunc L
--earth-br-ltrunc L
--emf
--induction
--Ek VALUE --Pr VALUE --Sc VALUE --RaT VALUE --RaC VALUE
```

Not every option applies to every source format. A converter writes only fields
supported by its input and does not invent absent magnetic or compositional
quantities.

## Validation

Run the converter test suite:

```bash
npm run test-converters
```

Validate JavaScript syntax and the production bundle:

```bash
node --check src/main.js
npm run build
```

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
