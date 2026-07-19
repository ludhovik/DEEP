# Dynamo Three.js Viewer

Local browser viewer for Leeds spherical-dynamo state files.

The package contains:

- a **Python converter**: `tools/convert_state_to_viewer.py`
- a **local Three.js/Vite viewer**: `src/main.js`
- output data read by the browser from: `public/data/`

The viewer can display:

- CMB and ICB surfaces
- equatorial and meridional slices
- magnetic field lines
- Earth surface texture
- velocity and scalar isosurfaces
- sequence playback for several converted state files
- exported PNG/PDF/video views
- saved/reloaded view-state codes

---

## 1. Folder layout

After unzipping, the project should look like:

```text
dynamo-three-viewer/
  index.html
  package.json
  README.md
  modules.py
  public/
    assets/
      earth_blue_marble.jpg
    data/
      metadata.json
      coordinates.json
      *_volume.f32
      sequence.json
      frames/
  src/
    main.js
  tools/
    convert_state_to_viewer.py
```

The browser reads data from:

```text
public/data/
```

Do **not** put data directly in `src/`.

### Multiple datasets in `public/`

You can keep several converted datasets under `public/` and switch between them inside the viewer.

Example layout:

```text
public/
  data/
    metadata.json
  data_run2/
    metadata.json
  datasets/
    run_A/
      metadata.json
    run_B/
      sequence.json
      frames/
        state03100/
```

The viewer path is the public URL path, not the filesystem path. For example:

```text
public/data/             -> /data
public/data_run2/        -> /data_run2
public/datasets/run_A/   -> /datasets/run_A
```

In the viewer use:

```text
Dataset
  Public folder
  Load dataset
```

Enter, for example:

```text
/data_run2
```

or:

```text
/datasets/run_A
```

then click:

```text
Load dataset
```

The browser cannot automatically list folders in `public/`, so the folder is entered manually.

---


---

## Multi-dataset startup

The viewer no longer requires one fixed dataset at:

```text
public/data/
```

You can keep several converted datasets under `public/`, for example:

```text
public/data_run1/
public/data_run2/
public/datasets/run_A/
public/datasets/run_B/
```

When the viewer starts, it asks which dataset folder to load.

Enter the browser/public path, not the filesystem path:

```text
/data_run1
/data_run2
/datasets/run_A
/datasets/run_B
```

For example, if the files are here:

```text
public/datasets/run_A/metadata.json
```

enter:

```text
/datasets/run_A
```

For a sequence dataset, the folder should contain:

```text
public/datasets/run_A/sequence.json
public/datasets/run_A/frames/state03100/metadata.json
```

and you should enter:

```text
/datasets/run_A
```

The viewer remembers the last dataset folder in browser storage.

You can also open a dataset directly using a URL query parameter:

```text
http://127.0.0.1:5173/?dataset=/datasets/run_A
```



---

## Loading two datasets at the same time

The viewer can load one **primary dataset** and one **secondary dataset**.

The primary dataset controls the geometry:

```text
r, theta, phi, nr, ntheta, nphi
```

The secondary dataset is added only if its grid matches the primary dataset:

```text
same nr
same ntheta
same nphi
```

This avoids silently plotting one dataset on the wrong spherical grid.

Example folder layout:

```text
public/datasets/run_A/
  metadata.json
  coordinates.json
  *_volume.f32

public/datasets/run_B/
  metadata.json
  coordinates.json
  *_volume.f32
```

In the viewer:

```text
Dataset
  Primary public folder      /datasets/run_A
  Load primary dataset

  Secondary public folder    /datasets/run_B
  Secondary label            D2
  Load secondary dataset
```

After loading the secondary dataset, its fields appear in all field selectors with the label prefix:

```text
D2:C
D2:Comp
D2:N2
D2:N2_full
D2:grad_rC_full
D2:Br
```

So, for example, you can show:

```text
CMB surface       Br
Equatorial slice  D2:N2_full
Meridional slice  C
Isosurface        D2:Comp
```

If the secondary dataset is a sequence folder, the viewer uses the first frame of that sequence as the secondary static dataset:

```text
public/datasets/run_B/sequence.json
public/datasets/run_B/frames/state03100/metadata.json
```

The secondary dataset is not animated by the primary sequence controls. It is loaded as a static comparison field source.



### 8-quarter surface selection

For the CMB surface and the Earth surface, you can now use a quarter-based visibility mode tied to the two meridional slices.

In the **Meridional slice 1** panel:

```text
Clip CMB with meridians
CMB clip mode = Selected 8 quarters
8-quarter selection
  North Q1 ... North Q4
  South Q1 ... South Q4
```

If **both meridional slices** are shown, their two planes define the 4 longitudinal sectors. If only one meridional slice is shown, the viewer uses that meridional plane plus an automatically generated perpendicular meridional plane to define the 4 sectors. The equator then splits each sector into north and south, giving 8 selectable regions in total.

The same selection is applied to both:

- the CMB surface
- the Earth surface layer

So you can show any combination of the 8 regions instead of only front/rear clipping.

`Q1..Q4` are ordered by the 4 azimuthal sectors created by the two meridional planes as you go around the sphere in longitude.


## 2. Install and start the viewer

From the project folder:

```bash
npm install --no-audit --no-fund
npm run dev
```

Open the URL printed by Vite, usually:

```text
http://127.0.0.1:5173
```

If the browser seems to keep old JavaScript, hard-refresh:

```text
Ctrl + F5
```

or clear the browser cache.

---

## 3. Python requirements

The converter uses your Leeds post-processing `modules.py`.

At minimum, `modules.py` must provide functions such as:

```python
load_state
PolTor_to_spat
SH_to_spat
SH_to_spat_nom0
gradient_spat
```

The converter command should point to the directory containing `modules.py`:

```bash
--modules-dir "modules.py"
```

or, if `modules.py` is in another folder:

```bash
--modules-dir "/path/to/folder/containing/modules_py/"
```

In the current project layout, if `modules.py` is in the project root, this is fine:

```bash
--modules-dir "modules.py"
```

---

## 4. Converter basics

The converter writes browser-readable files to:

```bash
--out public/data
```

To create a second dataset, choose another folder under `public/`:

```bash
--out public/data_run2
```

or:

```bash
--out public/datasets/run_A
```

Then select the matching viewer path:

```text
/data_run2
/datasets/run_A
```

Typical useful options:

```text
--spectral-lmax 128     angular spectral cutoff before physical-space synthesis; default is 128
--spectral-lmax 0       disable angular spectral truncation and use the full state-file lmax
--cmb-br-ltrunc 13      synthesize low-degree CMB Br, e.g. l <= 13
--skip-field-lines      skip magnetic field-line generation
--field-line-mode both  generate shell and exterior magnetic field lines
--external-rmax 40      maximum radius for exterior magnetic lines
--line-seeds 360        approximate total number of regular CMB line seeds
--downsample-r 2        optional radial downsampling
```

For angular reduction, prefer:

```bash
--spectral-lmax 128
```

over:

```bash
--downsample-theta 2 --downsample-phi 2
```

because `--spectral-lmax` removes high-degree spherical-harmonic content before the physical `theta/phi` grid is generated. The `--downsample-theta` and `--downsample-phi` options are still available, but they are a rough post-transform subsampling method.

For large sequences, it is often better to start with:

```bash
--skip-field-lines
```

because field-line generation can be expensive.

---


---

## Parameter extraction and prompts

The converter uses these parameters in `metadata.json` and in the computation of `N2`:

```text
Ek, Pr, Sc, RaT, RaC
```

It first tries to read them from the path. The following aliases are accepted:

```text
Ek:   Ek, E
Pr:   Pr, PrT, Pr_T
Sc:   Sc, PrC, Pr_C
RaT:  RaT, Ra_T, Ra
RaC:  RaC, Ra_C
```

For example, this path is now parsed correctly:

```text
Pm=0/Pr_T=1/Pr_C=10/q=0.0/E=1e-5/Ra_T=90/Ra_C=30000/
```

which gives:

```text
Ek  = 1e-5
Pr  = 1
Sc  = 10
RaT = 90
RaC = 30000
```

If one of the parameters is missing, the converter asks for it interactively:

```text
Enter Ek (Ekman number; aliases: Ek/E); blank = NaN:
```

Press Enter to keep a missing value as `NaN`.

You can also give the values explicitly on the command line:

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/state_last.cdf.dat" \
  --modules-dir "modules.py" \
  --out public/data_SN_fig2 \
  --Ek 1e-5 \
  --Pr 1 \
  --Sc 10 \
  --RaT 90 \
  --RaC 30000
```

Aliases also work:

```bash
--E 1e-5 --Pr_T 1 --Pr_C 10 --Ra_T 90 --Ra_C 30000
```

For non-interactive scripts, disable prompts with:

```bash
--no-parameter-prompt
```

For sequence conversion, the converter resolves missing parameters once from the first selected frame and forwards the resolved values to each frame, so it does not ask repeatedly for every state.


## 5. Convert one given statefile

Use `--state` or the alias `--file`.

Example with no field lines:

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/STATEFILES/state03125.cdf.dat" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

Example with magnetic field lines:

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/STATEFILES/state03125.cdf.dat" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --external-rmax 40 \
  --line-seeds 360
```

Equivalent command using `--state`:

```bash
python tools/convert_state_to_viewer.py \
  --state "/path/to/STATEFILES/state03125.cdf.dat" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

Output:

```text
public/data/metadata.json
public/data/coordinates.json
public/data/*_volume.f32
public/data/Br_CMB_lmax13_cmb.f32
```

---

## 6. Convert the last statefile in a folder

Use `--folder`. The converter will find the latest `state*.cdf.dat` in that folder.

Example with no field lines:

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

Example with field lines:

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --external-rmax 40 \
  --line-seeds 360
```

Example for the FLAYER case:

```bash
python tools/convert_state_to_viewer.py \
  --folder "/uolstore/Research/b/b0251/Data/FLAYER/DYN_C_VBC=1_CompBC=4_CBC=4_Ek=2e-5_Pm=5_Pr=1_Sc=10_Ra=120e6_RaC=1e9_rs=0.83_q=-100/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

---

## 7. Convert a sequence of statefiles

Use:

```text
--sequence-first FIRST
--sequence-last LAST
--sequence-step STEP
```

The converter selects files by state number:

```text
state03100.cdf.dat
state03105.cdf.dat
state03110.cdf.dat
...
```

Example sequence without field lines:

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --sequence-first 3100 \
  --sequence-last 3125 \
  --sequence-step 5 \
  --sequence-clear \
  --skip-field-lines
```

Example sequence with field lines:

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --external-rmax 40 \
  --line-seeds 360 \
  --sequence-first 3100 \
  --sequence-last 3125 \
  --sequence-step 5 \
  --sequence-clear
```

Example FLAYER sequence without field lines:

```bash
python tools/convert_state_to_viewer.py \
  --folder "/uolstore/Research/b/b0251/Data/FLAYER/DYN_C_VBC=1_CompBC=4_CBC=4_Ek=2e-5_Pm=5_Pr=1_Sc=10_Ra=120e6_RaC=1e9_rs=0.83_q=-100/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --sequence-first 3100 \
  --sequence-last 3125 \
  --sequence-step 5 \
  --sequence-clear \
  --skip-field-lines
```

This writes:

```text
public/data/sequence.json
public/data/frames/state03100/
public/data/frames/state03105/
public/data/frames/state03110/
...
```

The converter also copies the first frame to:

```text
public/data/
```

so the viewer can open normally.

Expected sequence structure:

```text
public/data/
  sequence.json
  frames/
    state03100/
      metadata.json
      coordinates.json
      *_volume.f32
    state03105/
      metadata.json
      coordinates.json
      *_volume.f32
```

The `sequence.json` should contain paths like:

```json
{
  "path": "frames/state03100",
  "metadata": "frames/state03100/metadata.json"
}
```

Do **not** use paths like:

```text
public/data/frames/state03100
/data/public/frames/state03100
```

inside `sequence.json`.

---

## 8. Sequence playback in the viewer

After converting a sequence, start the viewer:

```bash
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Use the GUI folder:

```text
Sequence playback
  Reload sequence.json
  Frame
  FPS
  Preload frames
  Cache limit MB
  Preload current view
  Clear cache
  Play
  Pause
```

Recommended workflow:

```text
1. Choose the fields and slices you want to animate.
2. Set Preload frames = 6 or 10.
3. Set Cache limit MB = 1500 or 3000.
4. Click Preload current view.
5. Click Play.
```

The viewer preloads only the fields used by the current view, not every field in every frame.

This avoids loading unnecessary arrays and keeps memory usage reasonable.

---

## 9. Magnetic field lines

Field-line generation is optional.

Skip field lines:

```bash
--skip-field-lines
```

Generate shell and exterior lines:

```bash
--field-line-mode both \
--external-rmax 40 \
--line-seeds 360
```

Use exact seed-grid dimensions:

```bash
--line-seed-theta 10 \
--line-seed-phi 36
```

This gives exactly:

```text
10 × 36 = 360 seeds
```

Use approximate total regular seeds:

```bash
--line-seeds 360
```

The converter chooses an approximately regular theta/phi grid.

In the viewer, field-line controls include:

```text
Magnetic field lines
  Show
  Line type
  Line stride
  Colour by = Strength / Polarity
  Value scale = Linear / log10(|B|)
  Range = minmax / manual
  Thickness
  Opacity
```

For large sequences, generate field lines only if really needed, because they can slow conversion and playback.

---

## 10. Angular spectral truncation

The converter supports angular spectral truncation before the physical-space transform:

```bash
--spectral-lmax 128
```

This is now the default.

If the original state has, for example:

```text
lmax = 191
mmax = 191
```

then the converter remaps the LSD coefficients onto a smaller `(l,m)` basis:

```text
lmax = 128
mmax = 128
```

before calling:

```python
PolTor_to_spat
SH_to_spat
SH_to_spat_nom0
```

This is preferable to downsampling in `theta` or `phi` because it removes unresolved high-degree content before synthesis rather than aliasing it onto a coarser grid.

Disable spectral truncation with:

```bash
--spectral-lmax 0
```

Use a different cutoff with:

```bash
--spectral-lmax 96
--spectral-lmax 160
```

The effective cutoff is written to `metadata.json` under:

```json
"spectral": {
  "enabled": true,
  "requested_lmax": 128,
  "lmax_original": 191,
  "mmax_original": 191,
  "lmax_effective": 128,
  "mmax_effective": 128
}
```

Radial downsampling is still separate:

```bash
--downsample-r 2
```

For most cases, leave angular post-downsampling off:

```bash
--downsample-theta 1
--downsample-phi 1
```

## 11. Converted fields

The converter writes the available fields into `metadata.json`.

Typical volume fields include:

```text
ur, ut, up, Uabs
Br, Bt, Bp, Babs
C, Comp
N2, N2_full
helicity
grad_rC, grad_thetaC, grad_phiC
grad_rComp, grad_thetaComp, grad_phiComp
grad_rC_full, grad_thetaC_full, grad_phiC_full
grad_rComp_full, grad_thetaComp_full, grad_phiComp_full
ur_phiavg, ut_phiavg, up_phiavg
Br_phiavg, Bt_phiavg, Bp_phiavg
```

Notes:

- `N2` is computed in 3-D and exported with the azimuthal `m=0` component removed.
- `N2_full` is the same quantity but with the azimuthal `m=0` component retained.
- scalar gradients named `grad_*` are exported with their azimuthal `m=0` component removed.
- scalar gradients named `grad_*_full` retain the azimuthal `m=0` component.
- `*_phiavg` fields are azimuthal averages broadcast back to 3-D so they can be shown with the same slice/surface tools.
- phi averages ignore non-finite or extreme outlier values.

---

## 12. Isosurfaces

The viewer has an `Isosurfaces` folder.

Controls:

```text
Isosurfaces
  Show
  Field
  Resolution
  Clip with meridians
  Clip offset M1
  Clip offset M2
  Show positive
  Positive value
  Positive color
  Show negative
  Negative value
  Negative color
  Opacity
```

The `Field` selector uses all available volume fields.

`Clip with meridians` uses the active meridional-slice clipping geometry, so you can open the isosurface on the front side and see inside the shell more clearly. It follows the current meridian positions and the current CMB clip mode / side settings.

`Clip offset M1` and `Clip offset M2` shift the isosurface clipping plane(s) perpendicular to meridional slice 1 and slice 2. The offsets are in the viewer's normalized length units (outer-core radius scale). Use positive or negative values to move the clipping plane sideways while keeping it parallel to the meridional plane. When only one meridional slice is active, the corresponding offset is used. When both meridional slices are active with `Between meridional planes (behind)`, both offsets are used.

Examples:

```text
ur
ut
up
Br
Bt
Bp
helicity
N2
C
Comp
```

The isosurface is extracted directly on the spherical dynamo grid, so it is confined to the fluid shell.

For performance, start with:

```text
Resolution = 24 or 32
```

then increase if needed.

---

## 13. Earth surface texture

The Earth surface uses a local texture:

```text
public/assets/earth_blue_marble.jpg
```

Put your texture there:

```bash
mkdir -p public/assets
cp /path/to/earth_blue_marble.jpg public/assets/earth_blue_marble.jpg
```

Recommended format:

```text
2:1 equirectangular / latitude-longitude projection
```

Then start or restart:

```bash
npm run dev
```

In the viewer:

```text
Earth surface
  Show
  Texture longitude
  Radius / core
  Opacity
  Slice gap filler
  Filler opacity
```

---

## 14. View-state code

The viewer can save and reload a complete visual setup.

GUI folder:

```text
View state
  Copy code
  Show code
  Load code
  Save code to file
```

The saved code includes:

```text
selected fields
colormaps
scale ranges
opacity values
camera position
lighting
slices
Earth surface settings
field-line settings
isosurface settings
sequence playback settings
```

This is useful for reproducing the same view on another converted state or sequence.

---

## 15. Export PNG/PDF/video

The viewer has export controls:

```text
Export
  Save PNG + colourbars
  Save PDF + colourbars
  Record video
```

Video controls include:

```text
Video width px
Video duration s
Video FPS
Rotation mode
```

Available rotation modes:

```text
360° in phi
360° phi + 180° theta
```

---

## 16. Troubleshooting

### Dataset selector cannot load a folder

Use the public URL path, not the filesystem path.

Correct examples:

```text
/data
/data_run2
/datasets/run_A
```

Incorrect examples:

```text
public/data_run2
/mnt/c/Users/.../public/data_run2
C:\Users\...\public\data_run2
```

For a dataset at:

```text
public/data_run2/metadata.json
```

enter this in the viewer:

```text
/data_run2
```

For a sequence dataset, check:

```bash
ls public/data_run2/sequence.json
ls public/data_run2/frames/state03100/metadata.json
```

### Error: `Unexpected token '<', "<!doctype "... is not valid JSON`

The viewer tried to read a JSON file, but Vite returned `index.html`.

Usually one of these files is missing or the path is wrong:

```text
public/data/metadata.json
public/data/sequence.json
public/data/frames/state03100/metadata.json
```

Check:

```bash
ls public/data/
ls public/data/sequence.json
ls public/data/frames/
ls public/data/frames/state03100/metadata.json
```

For a sequence, the correct structure is:

```text
public/data/sequence.json
public/data/frames/state03100/metadata.json
```

not:

```text
public/data/public/frames/
```

### Sequence exists but the viewer does not start

If `public/data/metadata.json` is missing but `sequence.json` exists, the viewer should start from the first frame. If it does not, copy the first frame to the root as a workaround:

```bash
cp -a public/data/frames/state03100/* public/data/
```

### Sequence playback is laggy

Use the preload controls:

```text
Sequence playback
  Preload frames = 6 or 10
  Cache limit MB = 1500 or 3000
  Preload current view
```

Also reduce what is visible:

```text
hide field lines
hide isosurfaces
use fewer slices
reduce isosurface resolution
```

### Converter says `NameError: shutil is not defined`

Use the latest converter. The sequence mode requires:

```python
import shutil
```

near the top of `tools/convert_state_to_viewer.py`.

### Phi-averaged fields show huge values such as `1e28`

Use the latest converter. Phi averages now ignore non-finite and extreme outlier values.

Reconvert the data after updating the converter.

### Earth texture does not show

Check that the file exists:

```bash
ls public/assets/earth_blue_marble.jpg
```

The viewer expects exactly:

```text
public/assets/earth_blue_marble.jpg
```

### Browser still shows an old bug

Hard-refresh:

```text
Ctrl + F5
```

or stop and restart Vite:

```bash
npm run dev
```

---

## 17. Useful complete commands

### One statefile, no field lines

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/state03125.cdf.dat" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

### Last state in folder, no field lines

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

### Sequence, no field lines

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --sequence-first 3100 \
  --sequence-last 3125 \
  --sequence-step 5 \
  --sequence-clear \
  --skip-field-lines
```

### Sequence, with field lines

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --external-rmax 40 \
  --line-seeds 360 \
  --sequence-first 3100 \
  --sequence-last 3125 \
  --sequence-step 5 \
  --sequence-clear
```

---

## 18. Notes on performance

Large 3-D fields are loaded as `Float32Array` objects in the browser.

Memory estimate per field:

```text
nr × ntheta × nphi × 4 bytes
```

For example, if:

```text
nr = 180
ntheta = 384
nphi = 384
```

one field is approximately:

```text
180 × 384 × 384 × 4 ≈ 106 MB
```

Therefore, do not preload every field for every frame. The viewer preloads only the currently visible fields, and the cache limit prevents unlimited memory growth.

For smoother playback:

```text
use --skip-field-lines for sequences
preload only 6 to 10 frames
set cache limit to 1500--3000 MB
hide expensive isosurfaces unless needed
reduce isosurface resolution
downsample if necessary
```

Optional downsampling example:

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES/" \
  --modules-dir "modules.py" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --sequence-first 3100 \
  --sequence-last 3125 \
  --sequence-step 5 \
  --sequence-clear \
  --skip-field-lines \
  --downsample-r 2 \
  --downsample-theta 2 \
  --downsample-phi 2
```

### Mouse rotation and corner axes

The viewer now uses **TrackballControls** instead of OrbitControls, which allows freer mouse rotation in all directions and avoids the blocked feeling near the poles.

When `Axes` is enabled in the GUI, the orientation axes are displayed in a small **top-right corner** overlay instead of in the middle of the model.


### GUI layout

The main `Controls` panel now opens collapsed, and its folders also start collapsed by default.

The `Point of view` controls are separated into their own GUI panel fixed at the bottom-left of the window. This panel also starts collapsed, so it is available without covering the main model view.



### GUI layout fix

The main GUI now uses a safe folder-collapse list and no longer references a missing `viewStateFolder` variable. This fixes the runtime `buildGui()` failure that could prevent datasets from loading.


---

## Convert XSHELLS fields with `pyxshells`

A separate converter is provided:

```text
tools/convert_xshells_to_viewer.py
```

XSHELLS stores a snapshot as separate field files, commonly:

```text
fieldU.<tag>   velocity
fieldB.<tag>   magnetic field
fieldT.<tag>   temperature
fieldC.<tag>   composition/concentration
```

Install the Python dependencies in the environment used for conversion:

```bash
python -m pip install numpy pyxshells
```

`pyxshells` uses the Python SHTns module, so SHTns must also be installed and importable:

```bash
python -c "import pyxshells, shtns; print('pyxshells/SHTns OK')"
```

### Automatic discovery from a folder and tag

For files such as `fieldU.bench`, `fieldB.bench`, `fieldT.bench`, and `fieldC.bench`:

```bash
python tools/convert_xshells_to_viewer.py \
  --folder "/path/to/xshells/run" \
  --tag bench \
  --out public/data_xshells \
  --Ek 1e-5 \
  --Pr 1 \
  --Sc 10 \
  --RaT 90 \
  --RaC 30000
```

Without `--tag`, the converter selects the newest matching `fieldU.*`, `fieldB.*`, `fieldT.*`, and `fieldC.*` files in the folder.

### Explicit field paths

```bash
python tools/convert_xshells_to_viewer.py \
  --velocity "/path/to/fieldU.snapshot" \
  --magnetic "/path/to/fieldB.snapshot" \
  --temperature "/path/to/fieldT.snapshot" \
  --composition "/path/to/fieldC.snapshot" \
  --out public/data_xshells
```

Any subset can be converted. For example, a non-magnetic thermal run can use only `--velocity` and `--temperature`.

### Output fields

Depending on the supplied files, the converter writes:

```text
ur, ut, up, Uabs
Br, Bt, Bp, Babs
T, Comp
```

Axisymmetric and non-axisymmetric variants include:

```text
ur_phiavg, ut_phiavg, up_phiavg
Br_phiavg, Bt_phiavg, Bp_phiavg
T_phiavg, Comp_phiavg

ur_nom0, ut_nom0, up_nom0
Br_nom0, Bt_nom0, Bp_nom0
T_nom0, Comp_nom0
```

Scalar gradients are exported as both full and m=0-removed fields:

```text
grad_rT_full, grad_thetaT_full, grad_phiT_full
grad_rComp_full, grad_thetaComp_full, grad_phiComp_full

grad_rT, grad_thetaT, grad_phiT
grad_rComp, grad_thetaComp, grad_phiComp
```

When the required parameters are available, it also writes:

```text
N2_full   full N² including m=0
N2        N² with m=0 removed
```

The implemented scaling is consistent with the Leeds converter:

```text
N² = r Ek² [ RaT/Pr dT/dr + RaC/Sc dComp/dr ]
```

### Control the SHTns physical grid

By default, `pyxshells`/SHTns chooses its physical grid. To specify it explicitly:

```bash
--nlat 256 --nphi 512
```

Both options must be supplied together. Viewer output can then be reduced further with:

```bash
--downsample-r 2 --downsample-theta 2 --downsample-phi 2
```

### Parameters and prompts

The converter accepts the same aliases used by the Leeds converter:

```text
--Ek or --E
--Pr, --PrT or --Pr_T
--Sc, --PrC or --Pr_C
--RaT, --Ra or --Ra_T
--RaC or --Ra_C
```

It first checks command-line values, then tries to parse values from the input paths. Missing values are requested interactively unless:

```bash
--no-parameter-prompt
```

### Load in the viewer

Start the viewer normally:

```bash
npm run dev
```

At the dataset prompt, enter:

```text
/data_xshells
```

The initial XSHELLS converter exports fields and surfaces usable by the CMB/ICB/slice/isosurface controls. It does not yet generate magnetic field-line JSON files.

### Conducting inner core and different radial domains

XSHELLS permits the magnetic field to extend beyond the velocity field into conducting solid layers. For example, `fieldB` may span from the centre to the CMB while `fieldU` and `fieldT` begin at the ICB.

The converter therefore:

- uses the magnetic radial grid as the viewer grid when `fieldB` is present;
- preserves `Br`, `Bt`, and `Bp` throughout the conducting inner core for every radius greater than zero;
- sets only the singular spherical-component layer at exactly `r=0` to zero;
- embeds shell-only velocity and scalar fields as zero outside their native radial domains;
- writes `r_icb`, `icb_radius`, `icb_index`, `radial_domains`, and `field_domains` to `metadata.json`.

The viewer uses `icb_index` to draw the ICB at the fluid-shell inner boundary, rather than assuming that the first radial point is the ICB.


### XSHELLS CMB truncation and magnetic field lines

The XSHELLS converter supports the same magnetic visualization outputs as the Leeds converter. It analyses the physical XSHELLS radial field at the fluid CMB using the field's own SHTns transform.

```bash
python tools/convert_xshells_to_viewer.py \
  --folder /path/to/run \
  --out public/data_xshells \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --line-seeds 360
```

Relevant options:

```text
--cmb-br-ltrunc L
--skip-field-lines
--field-line-mode shell|exterior|both
--external-rmax R
--external-nr N
--external-closed-only / --no-external-closed-only
--external-btheta-sign auto|plus|minus
--line-seeds N
--line-seed-theta N
--line-seed-phi N
--line-max-steps N
--line-step-size DS
```

For a conducting inner core, the volume magnetic field is retained below the ICB. The `shell` field-line mode is deliberately restricted to the fluid shell, while the exterior mode reconstructs a current-free field from `Br` at the CMB.

`Cps` is no longer requested or written by either converter. The viewer also removes that legacy key when opening older metadata files.

## Optimised sequence playback and PNG movie frames

The viewer sequence path is optimised for repeated snapshots on the same numerical grid.

### Interactive playback

During playback the viewer now:

- keeps the CMB, ICB, equatorial-slice and meridional-slice geometry on the GPU;
- updates the existing dynamic colour buffers instead of disposing and recreating meshes;
- loads only fields belonging to currently visible displays;
- leaves hidden slices unloaded until they are enabled;
- defers isosurface reconstruction and magnetic field-line loading by default;
- restores and updates deferred isosurfaces and field lines when playback is paused;
- advances to the next frame only after the current frame finishes loading, avoiding an interval backlog;
- avoids reconstructing the Earth surface and slice-gap fillers on every snapshot.

The **Sequence playback** panel contains:

- `Defer isosurfaces`;
- `Defer field lines`.

Both are enabled by default. Disable either option only when that object must be regenerated for every interactive frame.

Persistent geometry is used when consecutive snapshots have the same `nr`, `ntheta`, and `nphi`. If a sequence changes grid dimensions, the viewer safely rebuilds its geometry.

### Offline PNG snapshot sequence

Open:

```text
Export -> PNG snapshot sequence
```

Set:

- first and last sequence-frame indices;
- frame step;
- output width;
- whether isosurfaces and magnetic field lines should be refreshed for every exported frame.

Then select `Render PNG sequence`.

On browsers supporting the File System Access API, choose an output directory. The viewer writes:

```text
frame_00000.png
frame_00001.png
frame_00002.png
...
```

On browsers without directory writing, including Firefox, the viewer packages the PNGs into one uncompressed ZIP download. PNG data are already compressed, so ZIP deflation would provide little additional reduction. The fallback keeps the generated PNGs in browser memory until the ZIP is complete; use a moderate frame range or PNG width for very long sequences.

Use `Cancel PNG render` to stop after the current frame.

Create an MP4 with FFmpeg:

```bash
ffmpeg -framerate 24 -i 'frame_%05d.png' \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p movie.mp4
```

For a PNG ZIP, extract it before running FFmpeg.


### Sequence heavy-object behaviour

During playback, `Defer isosurfaces` and `Defer field lines` are independent:

- enabled: the object is hidden during playback and refreshed after pause;
- disabled: the object is rebuilt and displayed for every snapshot.


### Video export with sequence playback

Enable `Export > Activate playback` before `Record video` to advance the loaded
snapshot sequence while the camera rotation is recorded. The snapshot rate is
controlled by `Sequence playback > FPS`. Playback that was started by the video
export is stopped automatically when recording finishes; playback that was
already running before recording is left running.

### Personalized video motion

The two original camera paths remain available:

- `360° in phi`
- `360° phi + 180° theta`

A third mode, `Personalized motion`, starts from the current camera viewpoint and
accepts semicolon-separated relative rotations:

```text
-180p,45t;180p
```

Here `p` means azimuth/phi and `t` means polar angle/theta. Signed values control
the direction. Use `,` for motions happening at the same time within one stage,
and `;` for the next stage. Video time is divided between stages in proportion to
their largest absolute angular amplitude. Examples:

```text
90p
-180p
45t
-180p,45t;180p
90p,-30t;90p
```

### Preloading during sequence and video playback

Playback now automatically prepares the next number of snapshots specified by
`Sequence playback > Preload frames`.

The preload includes:

- binary arrays for currently visible scalar fields;
- isosurface mesh geometry when `Defer isosurfaces` is disabled;
- magnetic field-line JSON and GPU line geometry when `Defer field lines` is disabled.

The same preload runs before a video recording that has `Activate playback`
enabled. Heavy-object caches are bounded by `Preload frames`; old inactive
entries are disposed as new snapshots enter the rolling cache.

### Freeze-free video sequence synchronization

When `Export > Activate playback` is enabled, video export no longer runs the
normal real-time sequence timer. The video timeline drives the snapshot index.
Before recording, all unique snapshots required by the selected video duration
and sequence FPS are preloaded, including isosurfaces and field-line geometry
when their defer options are disabled.

During any remaining snapshot swap, `MediaRecorder` is paused. Recording resumes
only after the new fields and heavy objects have reached the canvas, and the
loading interval is removed from the camera-motion timeline. This prevents the
recorded movie from containing repeated frozen frames followed by camera jumps.

### Keyboard shortcuts

Keyboard shortcuts are active when focus is not inside a GUI input, selector,
button, or editable text field:

```text
+ / Numpad +    next sequence frame
- / Numpad -    previous sequence frame
Left / Right    rotate phi by -5° / +5°
Up / Down       rotate theta by -5° / +5°
i               zoom in by 10%
o               zoom out by 10%
```

Frame stepping wraps cyclically at the first and last snapshots. If sequence
playback is already running, the timer is paused for the manual step and then
resumed without creating a competing frame-load request.

### Radial spherical surface

The `Radial spherical surface` panel displays any volume field on a sphere at a
user-selected normalized radius `r / r_o` between 0 and 1. Values are linearly
interpolated between adjacent radial grid levels. If the requested radius lies
outside the radial domain stored by the dataset, the viewer uses the closest
available radius. The surface has independent visibility, field, colour scale,
colour map, manual limits, and opacity controls, and is supported during
sequence playback and image/video export.

### Earth surface latitude-cell fix

The Earth surface clipping mesh now defines the lower and upper colatitudes for
each latitude cell before evaluating its midpoint. This fixes the runtime error
`theta0 is not defined` when enabling the Earth texture.

### Earth-surface radial magnetic field

Both converters now export an Earth-surface radial magnetic field by default
when a magnetic field is available. The default truncation and radius are:

```text
lmax = 13
r_E / r_CMB = 6371 / 3480 = 1.830747126...
```

For a current-free mantle, each spherical-harmonic component of the radial
field is continued from the CMB according to

```text
Br_lm(r_E) = Br_lm(r_CMB) * (r_CMB / r_E)^(l + 2)
```

Only degrees `1 <= l <= 13` are retained. The output is:

```text
Br_Earth_lmax13_earth.f32
```

and `metadata.json` registers it under `surface_fields` with
`"surface": "earth"`, the radius ratio, effective truncation, and radial-decay
law.

The defaults can be changed with:

```bash
--earth-br-ltrunc 13
--earth-radius-scale 1.8307471264
```

or disabled with:

```bash
--no-earth-br
```

In the viewer, open `Earth surface` and select:

```text
Display = Earth image
```

or:

```text
Display = Magnetic Br
```

The magnetic mode provides a field selector, scale, colour map, manual range,
and opacity controls. Its radius is taken from the field metadata rather than
the texture-radius control.
