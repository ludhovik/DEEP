# Dynamo Three.js Viewer

Local Three.js/Vite viewer for spherical-dynamo output from:

- the Leeds Spherical Dynamo code;
- XSHELLS through `pyxshells`.

The package contains:

- `tools/convert_state_to_viewer.py` — Leeds state-file converter;
- `tools/convert_xshells_to_viewer.py` — XSHELLS field converter;
- `src/main.js` — browser viewer;
- `public/data/` — default browser-readable dataset folder;
- sample data that can be used to test the viewer immediately.

The viewer supports CMB and ICB surfaces, arbitrary-radius spherical surfaces,
equatorial and meridional slices, isosurfaces, magnetic field lines, Earth
texture or Earth-surface magnetic field, two simultaneous datasets, sequence
playback, PNG/PDF/video export, and saved view-state codes.

---

## Contents

1. [System requirements and version checks](#1-system-requirements-and-version-checks)
2. [Install NVM, Node.js and npm](#2-install-nvm-nodejs-and-npm)
3. [Download and unpack the viewer](#3-download-and-unpack-the-viewer)
4. [Install the viewer and verify the build](#4-install-the-viewer-and-verify-the-build)
5. [Start the viewer](#5-start-the-viewer)
6. [Prepare the Python converter environment](#6-prepare-the-python-converter-environment)
7. [Leeds converter examples](#7-leeds-converter-examples)
8. [XSHELLS converter examples](#8-xshells-converter-examples)
9. [Keyboard shortcuts](#9-keyboard-shortcuts)
10. [Load datasets in the viewer](#10-load-datasets-in-the-viewer)
11. [Main viewer displays](#11-main-viewer-displays)
12. [Sequence playback and preloading](#12-sequence-playback-and-preloading)
13. [Export PNG, PDF and video](#13-export-png-pdf-and-video)
14. [Converted fields and custom fields](#14-converted-fields-and-custom-fields)
15. [Magnetic field continuation to Earth](#15-magnetic-field-continuation-to-earth)
16. [Detailed Leeds converter reference](#16-detailed-leeds-converter-reference)
17. [Detailed XSHELLS converter reference](#17-detailed-xshells-converter-reference)
18. [Performance and memory](#18-performance-and-memory)
19. [Troubleshooting](#19-troubleshooting)
20. [Project layout and development commands](#20-project-layout-and-development-commands)

---

# 1. System requirements and version checks

Use a Linux, macOS, or WSL terminal. The commands below are written for Bash.

On Debian, Ubuntu, or WSL, install the basic command-line tools if needed:

```bash
sudo apt update
sudo apt install -y curl unzip python3 python3-venv python3-pip
```

On an HPC system without `sudo`, use the available Python module, Conda
environment, or local software stack instead.

The project currently uses Vite 8.0.16. Its Node.js requirement is:

```text
Node.js 20.19 or newer within Node 20,
or Node.js 22.12 or newer.
```

Using the current Node.js LTS release through NVM is recommended.

The Python converters require:

```text
Python 3.10 or newer
```

because they use Python 3.10 type syntax.

Check what is already installed:

```bash
python3 --version
node --version
npm --version
nvm --version
```

A suitable result looks similar to:

```text
Python 3.10+
Node v22.12+ or a newer LTS release
npm supplied with that Node release
```

Run explicit compatibility checks:

```bash
python3 -c 'import sys; print(sys.version); assert sys.version_info >= (3, 10)'
node -e 'console.log(process.version); const [M,m]=process.versions.node.split(".").map(Number); if (!((M===20 && m>=19) || (M===22 && m>=12) || M>22)) process.exit(1)'
```

If `node`, `npm`, or `nvm` is missing, install NVM as described next.

---

# 2. Install NVM, Node.js and npm

NVM manages Node.js versions without requiring administrator access. The
following command installs NVM 0.40.6 from the official `nvm-sh/nvm`
repository:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.6/install.sh | bash
```

Reload the shell configuration:

```bash
source ~/.bashrc
```

For Zsh use:

```bash
source ~/.zshrc
```

If `nvm` is still not found, load it directly:

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
```

Check NVM:

```bash
nvm --version
```

Install and activate the current Node.js LTS release:

```bash
nvm install --lts
nvm use --lts
nvm alias default 'lts/*'
```

Check the installed tools:

```bash
node --version
npm --version
which node
which npm
```

Both `which` commands should normally point inside:

```text
~/.nvm/
```

## WSL note

Run these commands inside WSL, not in Windows PowerShell, when the project is
used from a WSL filesystem. Keep the project under the Linux home directory for
better npm performance, for example:

```text
~/dynamo-three-viewer/
```

rather than under:

```text
/mnt/c/...
```

---

# 3. Download and unpack the viewer

Download the latest viewer ZIP from the ChatGPT conversation or the location
where it was shared.

Assuming it was downloaded into `~/Downloads`:

```bash
cd ~/Downloads
ls dynamo-three-viewer-*.zip
```

Unpack it into the home directory:

```bash
unzip dynamo-three-viewer-*.zip -d ~/
```

Then enter the project folder:

```bash
cd ~/dynamo-three-viewer
```

If several matching ZIP files exist, specify the exact filename instead of the
wildcard:

```bash
unzip dynamo-three-viewer-readme-installation-guide.zip -d ~/
cd ~/dynamo-three-viewer
```

Check that the expected files are present:

```bash
ls
ls tools
ls src
ls public/data
```

You should see at least:

```text
README.md
index.html
package.json
package-lock.json
src/main.js
tools/convert_state_to_viewer.py
tools/convert_xshells_to_viewer.py
```

---

# 4. Install the viewer and verify the build

Activate the Node version first if this is a new terminal:

```bash
nvm use --lts
```

Install the exact JavaScript dependency versions recorded in
`package-lock.json`:

```bash
npm ci --no-audit --no-fund
```

Use `npm install` instead only when intentionally updating dependencies:

```bash
npm install --no-audit --no-fund
```

Check the JavaScript syntax and production build:

```bash
node --check src/main.js
npm run build
```

A successful build creates:

```text
dist/
```

---

# 5. Start the viewer

Start the Vite development server:

```bash
npm run dev
```

Open the address printed by Vite, normally:

```text
http://127.0.0.1:5173
```

The ZIP contains a small sample dataset under:

```text
public/data/
```

Enter this dataset path when prompted:

```text
/data
```

If the browser keeps an older JavaScript version after replacing the viewer,
perform a hard refresh:

```text
Ctrl + F5
```

## Running the viewer on a remote machine

Vite binds to `127.0.0.1`. Forward the port over SSH:

```bash
ssh -L 5173:127.0.0.1:5173 username@remote-machine
```

Then run `npm run dev` on the remote machine and open locally:

```text
http://127.0.0.1:5173
```

---

# 6. Prepare the Python converter environment

Create a Python virtual environment in the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python --version
```

Every new terminal should reactivate it with:

```bash
cd ~/dynamo-three-viewer
source .venv/bin/activate
```

## 6.1 Leeds converter requirements

Install NumPy:

```bash
python -m pip install numpy
```

The Leeds converter also requires your own Leeds post-processing `modules.py`.
That file is **not bundled** with this viewer.

It must provide functions including:

```python
load_state
PolTor_to_spat
SH_to_spat
SH_to_spat_nom0
gradient_spat
```

Copy `modules.py` into a known directory, for example:

```text
~/leeds-postprocessing/modules.py
```

Check that it imports:

```bash
PYTHONPATH="$HOME/leeds-postprocessing:$PYTHONPATH" \
python -c 'import modules; print(modules.__file__)'
```

Pass its **containing directory** to the converter:

```bash
--modules-dir "$HOME/leeds-postprocessing"
```

Do not use:

```text
--modules-dir /path/to/modules.py
```

because `--modules-dir` expects a directory.

If `modules.py` is copied into the project root, use:

```bash
--modules-dir .
```

Your `modules.py` may itself require additional packages such as SciPy or
NetCDF. Install those dependencies in the same Python environment.

## 6.2 XSHELLS converter requirements

Install the pinned XSHELLS Python requirements:

```bash
python -m pip install -r requirements-xshells.txt
```

The XSHELLS path requires:

```text
numpy
pyxshells 2.8
shtns
```

Check the imports:

```bash
python -c 'import numpy, pyxshells, shtns; print("NumPy/pyxshells/SHTns OK")'
```

SHTns may need to be installed separately according to the Python/HPC
environment in use.

---

# 7. Leeds converter examples

The converter is:

```text
tools/convert_state_to_viewer.py
```

All browser-readable outputs must be written under `public/`.

The default output folder is:

```text
public/data/
```

The corresponding viewer URL path is:

```text
/data
```

## 7.1 Convert one state file without field lines

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/STATEFILES/state03125.cdf.dat" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --earth-br-ltrunc 13 \
  --skip-field-lines
```

`--state` and `--file` are aliases, so this is equivalent:

```bash
python tools/convert_state_to_viewer.py \
  --state "/path/to/STATEFILES/state03125.cdf.dat" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

## 7.2 Convert one state file with magnetic field lines

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/STATEFILES/state03125.cdf.dat" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --earth-br-ltrunc 13 \
  --field-line-mode both \
  --external-rmax 40 \
  --line-seeds 360
```

## 7.3 Convert the latest state in a folder

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

The converter selects the largest state number matching:

```text
state*.cdf.dat
```

## 7.4 Convert a numbered sequence

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --earth-br-ltrunc 13 \
  --sequence-first 3100 \
  --sequence-last 3125 \
  --sequence-step 5 \
  --sequence-clear \
  --skip-field-lines
```

This selects:

```text
state03100.cdf.dat
state03105.cdf.dat
state03110.cdf.dat
...
state03125.cdf.dat
```

and writes:

```text
public/data/sequence.json
public/data/frames/state03100/
public/data/frames/state03105/
...
```

## 7.5 Sequence with field lines

```bash
python tools/convert_state_to_viewer.py \
  --folder "/path/to/STATEFILES" \
  --modules-dir "$HOME/leeds-postprocessing" \
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

Field-line generation is expensive. Start with `--skip-field-lines` for large
sequences unless field lines are needed in every frame.

## 7.6 FLAYER example

```bash
python tools/convert_state_to_viewer.py \
  --folder "/uolstore/Research/b/b0251/Data/FLAYER/DYN_C_VBC=1_CompBC=4_CBC=4_Ek=2e-5_Pm=5_Pr=1_Sc=10_Ra=120e6_RaC=1e9_rs=0.83_q=-100/STATEFILES" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data \
  --spectral-lmax 128 \
  --cmb-br-ltrunc 13 \
  --skip-field-lines
```

## 7.7 Full-sphere state without an inner core

For a Leeds state whose radial grid includes the centre, use:

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/state0026.cdf.dat" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data_full_sphere \
  --no-inner-core \
  --spectral-lmax 128 \
  --skip-field-lines
```

`--full-sphere` is an alias for `--no-inner-core`. The converter also detects a
full sphere automatically when the first radial coordinate is `r=0`.

Current Leeds full-sphere states do **not** store the conventional potentials
that the shell `PolTor_to_spat` routine expects. Stage 5/6 stores the bounded
regular coefficients directly:

```text
radial_representation = "regular_r_power_g_x"
radial_power_offset   = 0
```

with

```text
f_lm(r) = r^(l+p0) G_lm(x),    x = r^2.
```

The converter reads these attributes separately for `uP`, `uT`, `BP`, `BT`,
`C`, and `Comp`. It then uses the same direct regular reconstruction as
`var_coll_TorPol2qst_fullsphere` in the Leeds code. For
`P=r^(l+pP)G(x)` and `T=r^(l+pT)H(x)`, the SHTns coefficients are

```text
Q = l(l+1) r^(l+pP-1) G,
S = +r^(l+pP-1) [(l+pP+1)G + 2x dG/dx],
T = r^(l+pT) H.
```

No quantity is divided by `r`. The positive `S` sign follows the actual Leeds
full-sphere chain: `var_coll_TorPol2qst_fullsphere` forms positive `s`, and
`tra_qst2rtp_shtns` applies a positive `shtns_norm_st`. The shell helper in
`modules.py` uses a negative conventional-potential `S` expression (and marks
that line `#check the sign`); that shell convention is not used for regular
full-sphere velocity or magnetic fields. The derivative `dG/dx` uses the same
local, factorial-scaled finite-difference operator as Leeds `D%dx(1)`, with the
standard `i_KL=3` seven-point stencil.

This is important because passing stored `G` directly to the shell transform
would incorrectly evaluate terms such as `l(l+1)G/r`, producing very large
velocity close to the centre.

At `r=0`, only the regular `l=1` vector limit can remain finite. The converter
synthesizes that limit directly, converts it to a single Cartesian centre
vector, and projects the same vector back onto every spherical basis direction.
It does not force velocity to zero unless the physical `l=1` centre limit is
zero. Regular scalar coefficients are first converted to their physical form
`r^(l+p0)G`, so only the `l=0` scalar remains at the exact centre.

For an older full-sphere state marked
`conventional_r_coefficient` (or lacking the representation attribute), the
converter first applies the bounded Leeds stage-5 projection from
`f=r^pG` to `G`. This uses `K=2*i_KL+1=7` and the same `1e-6` resolvability
threshold as `var_fullsphere_projection_precompute`; it never divides a mode
pointwise by a small `r^l`.

The detected representations, projection path, derivative method, and centre
Cartesian diagnostics are written to:

```text
state_radial_representations
full_sphere_transform
center_regularization
```

The default centre-detection tolerance is:

```bash
--center-tolerance 1e-12
```

For a full-sphere sequence, include `--no-inner-core` in the sequence command;
it is propagated to every converted frame.

## 7.8 Explicit physical parameters

The converter attempts to read parameters from the input path. They can also be
set explicitly:

```bash
python tools/convert_state_to_viewer.py \
  --file "/path/to/state_last.cdf.dat" \
  --modules-dir "$HOME/leeds-postprocessing" \
  --out public/data_SN_fig2 \
  --Ek 1e-5 \
  --Pr 1 \
  --Sc 10 \
  --RaT 90 \
  --RaC 30000 \
  --skip-field-lines
```

Accepted aliases are:

```text
Ek:   --Ek, --E
Pr:   --Pr, --PrT, --Pr_T
Sc:   --Sc, --PrC, --Pr_C
RaT:  --RaT, --Ra, --Ra_T
RaC:  --RaC, --Ra_C
```

Disable interactive parameter prompts in batch jobs with:

```bash
--no-parameter-prompt
```

---

# 8. XSHELLS converter examples

The converter is:

```text
tools/convert_xshells_to_viewer.py
```

XSHELLS commonly stores a snapshot as:

```text
fieldU.<tag>   velocity
fieldB.<tag>   magnetic field
fieldT.<tag>   temperature
fieldC.<tag>   composition
```

Any subset can be converted.

## 8.1 Discover fields from a folder and tag

```bash
python tools/convert_xshells_to_viewer.py \
  --folder "/path/to/xshells/run" \
  --tag bench \
  --out public/data_xshells \
  --Ek 1e-5 \
  --Pr 1 \
  --Sc 10 \
  --RaT 90 \
  --RaC 30000 \
  --cmb-br-ltrunc 13 \
  --earth-br-ltrunc 13 \
  --skip-field-lines
```

Without `--tag`, the converter selects the newest matching files in the folder.

## 8.2 Explicit XSHELLS field paths

```bash
python tools/convert_xshells_to_viewer.py \
  --velocity "/path/to/fieldU.snapshot" \
  --magnetic "/path/to/fieldB.snapshot" \
  --temperature "/path/to/fieldT.snapshot" \
  --composition "/path/to/fieldC.snapshot" \
  --out public/data_xshells \
  --cmb-br-ltrunc 13 \
  --earth-br-ltrunc 13
```

For a non-magnetic run, omit `--magnetic`.

## 8.3 XSHELLS field lines

```bash
python tools/convert_xshells_to_viewer.py \
  --folder "/path/to/xshells/run" \
  --tag bench \
  --out public/data_xshells \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --external-rmax 40 \
  --line-seeds 360
```

## 8.4 Control the SHTns output grid

Both options must be supplied together:

```bash
--nlat 256 --nphi 512
```

Optional output downsampling is separate:

```bash
--downsample-r 2 \
--downsample-theta 2 \
--downsample-phi 2
```

## 8.5 Load the XSHELLS dataset

Start the viewer and enter:

```text
/data_xshells
```

The current XSHELLS converter processes one snapshot per command. To compare or
retain several snapshots, write each one to a different folder under `public/`.

---

# 9. Keyboard shortcuts

Keyboard shortcuts are active when focus is not inside a GUI input, selector,
button, or editable text field.

```text
+ / Numpad +    next sequence frame
- / Numpad -    previous sequence frame

Left arrow      phi -5 degrees
Right arrow     phi +5 degrees
Up arrow        theta -5 degrees
Down arrow      theta +5 degrees

i               zoom in by 10%
o               zoom out by 10%
```

Sequence stepping wraps cyclically:

```text
last frame +  -> first frame
first frame - -> last frame
```

If normal sequence playback is already running, the timer is paused for the
manual step and then resumed without creating competing frame-load requests.

Shortcuts are ignored during video recording and offline PNG-sequence export.

---

# 10. Load datasets in the viewer

The viewer accepts three dataset-source types.

## 10.1 Select any folder with the browser

This is the recommended method for data outside the project. Use:

```text
Dataset
  Select primary folder
```

Then select the converted dataset directory itself, for example:

```text
C:\Users\wgdh881\Downloads\data_FLAYER_C19
```

The selected folder may contain either:

```text
metadata.json
```

or a sequence root containing:

```text
sequence.json
frames/...
```

The viewer reads `metadata.json`, coordinates, `.f32` arrays, field-line JSON,
and sequence subdirectories directly through the browser filesystem API. The
folder does not need to be copied under `public/`.

Chrome and Edge use the native directory picker. Browsers without
`showDirectoryPicker` use a directory-upload fallback. A selected-folder handle
is temporary and must normally be selected again after reloading the page.

## 10.2 Enter an absolute path in the text box

When running the development server with:

```bash
npm run dev
```

enter an absolute Windows path directly:

```text
C:\Users\wgdh881\Downloads\data_FLAYER_C19
```

The viewer converts it internally to Vite's `/@fs/` filesystem route.

For a POSIX path, use the explicit `file:` prefix:

```text
file:/work/n03/n03/wgdh881/data_FLAYER_C19
file:/uolstore/Research/a/a88/earcd/DYNAMOS/data_FLAYER_C19
```

Then press:

```text
Dataset
  Load primary path
```

Absolute text paths are supported by `npm run dev`. They are not portable to a
static production server because `/@fs/` is a Vite development-server feature.
The server remains bound to `127.0.0.1`; do not expose it to an untrusted network.

## 10.3 Load from `public/`

The original browser paths remain supported:

```text
public/data/             -> /data
public/data_run2/        -> /data_run2
public/datasets/run_A/   -> /datasets/run_A
public/data_xshells/     -> /data_xshells
```

Use:

```text
Dataset
  Primary path / URL
  Load primary path
```

A public dataset can also be selected through the URL:

```text
http://127.0.0.1:5173/?dataset=/datasets/run_A
```

## 10.4 Load two datasets simultaneously

The viewer supports one primary and one secondary dataset. The secondary source
can also be selected with a folder picker or entered as a path/URL.

The primary dataset controls the spherical grid. The secondary dataset is
accepted only when these dimensions match:

```text
nr
ntheta
nphi
```

Use:

```text
Dataset
  Secondary path / URL
  Select secondary folder
  Secondary label
  Load secondary path
```

Secondary fields receive a prefix, for example:

```text
D2:Br
D2:Comp
D2:N2_full
```

A secondary sequence is loaded as a static comparison using its first frame. It
is not animated by the primary sequence controls.

---

# 11. Main viewer displays

The main `Controls` panel and its folders start collapsed. The separate
`Point of view` panel is fixed at the bottom-left and also starts collapsed.

Trackball controls allow free mouse rotation. When enabled, the orientation axes
are shown in the top-right corner.

## 11.1 CMB and ICB surfaces

Each surface has independent field, scale, colour-map, manual range and opacity
controls.

The CMB can use either:

- the outer radial layer of a volume field;
- a field registered under `surface_fields` with `"surface": "cmb"`.

The ICB radius is obtained from `metadata.json`, including XSHELLS conducting
inner-core datasets where the magnetic grid extends below the fluid shell.

## 11.2 Equatorial and meridional slices

Two equatorial and two meridional slices are available. Each has independent
field, scaling, colour map and opacity controls.

The two meridional planes also control optional clipping of CMB, Earth and
isosurface displays.

## 11.3 Radial spherical surface

The `Radial spherical surface` panel displays any volume field on a sphere at a
selected normalized radius:

```text
0 <= r / r_o <= 1
```

Values are linearly interpolated between adjacent radial grid levels. If the
requested radius is outside a field's stored radial domain, the closest
available radius is used.

Controls include:

```text
Show
Field
Radius r / r_o
Scale
Colour map
Manual min/max
Opacity
```

The surface supports primary or secondary fields, sequence playback, view-state
saving, and PNG/PDF/video export.

## 11.4 Earth surface: image or magnetic field

Open:

```text
Earth surface
```

Select one of:

```text
Display = Earth image
Display = Magnetic Br
```

### Earth image

The Earth texture is optional and is **not bundled** with this package. Add a
2:1 equirectangular image at exactly:

```text
public/assets/earth_blue_marble.jpg
```

For example:

```bash
mkdir -p public/assets
cp /path/to/earth_blue_marble.jpg public/assets/earth_blue_marble.jpg
```

Image controls include longitude, radius/core and opacity.

The Earth panel also contains the slice-gap filler controls:

```text
Slice gap filler
Filler opacity
```

These fill visual gaps created where slice planes intersect clipped spherical
surfaces.

### Earth magnetic field

Both converters generate an Earth-surface radial magnetic field by default when
magnetic data are available:

```text
Br_Earth_lmax13_earth.f32
```

Magnetic controls include:

```text
Magnetic field
Scale
Colour map
Manual min/max
Opacity
```

The magnetic sphere radius is read from field metadata and is independent of
the image-radius control.

## 11.5 Eight-quarter surface selection

The CMB and Earth surfaces can be divided into eight selectable regions by two
meridional planes and the equator:

```text
North Q1 ... North Q4
South Q1 ... South Q4
```

If only one meridional slice is active, the viewer adds a perpendicular plane
to define four longitudinal sectors. The equator divides them into north and
south.

## 11.6 Isosurfaces

The `Isosurfaces` folder provides:

```text
Show
Field
Resolution
Clip with meridians
Clip offset M1/M2
Positive and negative values/colours
Opacity
```

The field selector includes all registered volume fields. The extraction is
performed on the spherical numerical grid and remains confined to its radial
domain.

Start with:

```text
Resolution = 24 or 32
```

and increase only when necessary.

## 11.7 Magnetic field lines

Field-line controls include:

```text
Show
Line type = shell / exterior / both
Line stride
Colour by = strength / polarity
Value transform
Range
Thickness
Opacity
```

Converter options include:

```text
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

An exact seed grid can be requested with:

```bash
--line-seed-theta 10 --line-seed-phi 36
```

which gives 360 seeds.

---

# 12. Sequence playback and preloading

A Leeds sequence has the structure:

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

Paths inside `sequence.json` must be relative to the dataset root:

```json
{
  "path": "frames/state03100",
  "metadata": "frames/state03100/metadata.json"
}
```

Do not include `public/data/` in those internal paths.

## 12.1 Playback controls

```text
Sequence playback
  Reload sequence.json
  Frame
  FPS
  Preload frames
  Cache limit MB
  Defer isosurfaces
  Defer field lines
  Preload N frames
  Preload full sequence
  Clear cache
  Play
  Pause
```

Recommended workflow:

```text
1. Select the visible fields and objects.
2. Set Preload frames to any value from 1 to the full sequence length.
3. Set Cache limit MB according to available RAM and GPU memory.
4. Click Preload N frames, or Preload full sequence.
5. Click Play.
```

The `Preload frames` upper bound is the number of snapshots in `sequence.json`.
There is no separate hard frame-count limit. Setting it equal to the sequence
length requests that the complete sequence be cached for both interactive
playback and playback-enabled video export.

The viewer loads only arrays used by visible objects.

Persistent GPU geometry is retained for CMB, ICB, radial surface, equatorial
slices and meridional slices when successive frames have the same grid.
Only their colour buffers are updated.

## 12.2 Heavy-object preloading

When defer is disabled, preloading also includes:

- complete isosurface geometry;
- field-line JSON and GPU line geometry.

The two controls are independent:

```text
Defer isosurfaces = on
  Hide isosurfaces during playback and refresh on pause.

Defer isosurfaces = off
  Preload and display frame-specific isosurfaces.

Defer field lines = on
  Hide lines during playback and refresh on pause.

Defer field lines = off
  Preload and display frame-specific line geometry.
```

Scalar arrays, field-line JSON, isosurface meshes and field-line GPU geometry
share the same `Cache limit MB`. The viewer uses least-recently-used eviction of
inactive entries only when this combined memory limit is exceeded. Therefore,
all requested frames remain preloaded when the configured memory cache is large
enough.

---

# 13. Export PNG, PDF and video

The `Export` folder includes:

```text
Save PNG + colourbars
Save PDF + colourbars
Record video
PNG snapshot sequence
```

Visible colourbars are included in PNG/PDF output.

## 13.1 Video rotation modes

Available modes are:

```text
360 degrees in phi
360 degrees phi + 180 degrees theta
Personalized motion
```

The motion starts from the current camera viewpoint.

### Personalized syntax

```text
p = relative phi/azimuth rotation in degrees
t = relative theta/polar rotation in degrees
, = motions performed simultaneously
; = next motion stage
```

Examples:

```text
90p
-180p
45t
-180p,45t;180p
90p,-30t;90p
```

For:

```text
180p,45t;180p
```

stage 1 performs 180 degrees in phi and 45 degrees in theta simultaneously;
stage 2 then performs another 180 degrees in phi.

Video time is divided between semicolon-separated stages in proportion to the
largest absolute angular motion in each stage.

## 13.2 Video with sequence playback

Enable:

```text
Export > Activate playback
```

before recording.

The video timeline controls the sequence frame rather than using the normal
real-time playback timer. The same `Preload frames` value used by interactive
playback is used before recording. Set it to the complete sequence length to
request a fully cached movie sequence. Isosurfaces and field-line geometry are
included when their defer controls are off.

If a remaining frame swap is necessary, the recorder is paused until the new
field reaches the canvas, preventing loading intervals from being encoded as
frozen video frames.

## 13.3 Offline PNG sequence

Open:

```text
Export > PNG snapshot sequence
```

Set first frame, last frame, step, output width and whether heavy objects should
be refreshed.

On Chromium browsers with the File System Access API, select an output folder.
Other browsers package the PNG files in a ZIP.

Output names are:

```text
frame_00000.png
frame_00001.png
...
```

Create an MP4 with FFmpeg:

```bash
ffmpeg -framerate 24 -i 'frame_%05d.png' \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p movie.mp4
```

---

# 14. Converted fields and custom fields

## 14.1 Typical Leeds volume fields

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

Definitions:

- `N2` has its azimuthal `m=0` component removed;
- `N2_full` retains `m=0`;
- `grad_*` fields have `m=0` removed;
- `grad_*_full` fields retain `m=0`;
- `*_phiavg` fields are azimuthal averages broadcast back to 3-D.

The implemented buoyancy-frequency scaling is:

```text
N^2 = r Ek^2 [RaT/Pr dT/dr + RaC/Sc dComp/dr]
```

## 14.2 Typical XSHELLS fields

```text
ur, ut, up, Uabs
Br, Bt, Bp, Babs
T, Comp
```

Axisymmetric and non-axisymmetric variants include:

```text
*_phiavg
*_nom0
```

Scalar gradients are exported as full and `m=0`-removed variants.

## 14.3 Add a custom 3-D field

The viewer does not discover an `.f32` file by filename alone. Register it in
`metadata.json`:

```json
{
  "fields": {
    "x": "x.f32"
  }
}
```

The file must contain little-endian 32-bit floats with shape:

```text
(nr, ntheta, nphi)
```

flattened in C order, with `iphi` varying fastest:

```python
import numpy as np

x = np.asarray(x, dtype="<f4")
assert x.shape == (nr, ntheta, nphi)
x.tofile("public/data/x.f32")
```

The expected byte count is:

```text
nr * ntheta * nphi * 4
```

For a sequence, add the field and metadata entry to every frame.

## 14.4 Add a CMB-only field

A CMB field has shape:

```text
(ntheta, nphi)
```

Register it as:

```json
{
  "surface_fields": {
    "x_CMB": {
      "surface": "cmb",
      "file": "x_CMB.f32"
    }
  }
}
```

## 14.5 Add an Earth-only field

Register a two-dimensional Earth surface field with:

```json
{
  "surface_fields": {
    "x_Earth": {
      "surface": "earth",
      "file": "x_Earth.f32",
      "radius_scale": 1.8307471264
    }
  }
}
```

---

# 15. Magnetic field continuation to Earth

Both converters generate a low-degree Earth-surface radial magnetic field by
default when magnetic data are present.

Write the CMB radial field as:

```text
Br(r_o, theta, phi) = sum_lm b_lm(r_o) Y_lm(theta, phi)
```

In a current-free insulating mantle, each radial-field harmonic continues as:

```text
b_lm(r) = b_lm(r_o) (r_o / r)^(l + 2)
```

The default Earth radius is:

```text
r_E / r_CMB = 6371 / 3480 = 1.830747126...
```

and only degrees:

```text
1 <= l <= 13
```

are retained. Therefore:

```text
Br(r_E, theta, phi)
  = sum_(l=1)^13 sum_m
    b_lm(r_CMB)
    (r_CMB/r_E)^(l+2)
    Y_lm(theta, phi)
```

The dipole decays as `r^-3`, the quadrupole as `r^-4`, and so on.

Default output:

```text
Br_Earth_lmax13_earth.f32
```

Metadata records:

- Earth radius scale;
- effective truncation;
- radial decay law;
- `surface = earth`.

Options available in both converters:

```bash
--earth-br-ltrunc 13
--earth-radius-scale 1.8307471264
--no-earth-br
```

The low-degree CMB map is controlled independently with:

```bash
--cmb-br-ltrunc 13
```

---

# 16. Detailed Leeds converter reference

## 16.1 Angular spectral truncation

The default is:

```bash
--spectral-lmax 128
```

This truncates the spherical-harmonic coefficients before physical-space
synthesis. It is preferable to post-transform theta/phi subsampling because it
removes unresolved high-degree content before generating the grid.

Disable spectral truncation with:

```bash
--spectral-lmax 0
```

Alternative cutoffs include:

```bash
--spectral-lmax 96
--spectral-lmax 160
```

The effective values are written under the `spectral` key in `metadata.json`.

Radial and angular post-downsampling remain available:

```bash
--downsample-r 2
--downsample-theta 2
--downsample-phi 2
```

Normally leave theta and phi downsampling at 1 when using spectral truncation.

## 16.2 Parameter extraction

The converter reads these values from the path when possible:

```text
Ek, Pr, Sc, RaT, RaC
```

Accepted path aliases are:

```text
Ek/E
Pr/PrT/Pr_T
Sc/PrC/Pr_C
RaT/Ra_T/Ra
RaC/Ra_C
```

For example:

```text
Pm=0/Pr_T=1/Pr_C=10/q=0.0/E=1e-5/Ra_T=90/Ra_C=30000/
```

is interpreted as:

```text
Ek  = 1e-5
Pr  = 1
Sc  = 10
RaT = 90
RaC = 30000
```

When converting a sequence, missing parameters are resolved once from the first
selected frame and forwarded to subsequent frame conversions.

## 16.3 Sequence output structure

The converter copies the first sequence frame into the dataset root so the
viewer can start even before playback is activated.

Expected output:

```text
public/data/
  metadata.json
  coordinates.json
  sequence.json
  frames/
    state03100/
    state03105/
```

## 16.4 Full-sphere regular-coefficient conversion

The converter supports Leeds states with `riro=0` and `r[0]=0`. Enable the mode
explicitly with either:

```bash
--no-inner-core
--full-sphere
```

The mode is also activated automatically when the radial grid contains one
centre point at index zero. An explicit request fails if the state does not
contain `r=0`.

The converter follows the regular formulation in the Leeds full-sphere source:

- stored fields are identified using `radial_representation` and
  `radial_power_offset`;
- regular velocity and magnetic potentials are reconstructed directly in
  `x=r^2` using the Leeds QST identities;
- `d/dx` uses the local `i_KL=3` seven-point Leeds finite-difference stencil;
- legacy conventional full-sphere modes are converted with the bounded `K=7`
  Leeds projection rather than division by `r^l`;
- scalar regular coefficients are multiplied by `r^(l+p0)` before angular
  synthesis;
- the exact-centre vector is represented by its unique Cartesian regular limit.

Metadata records:

```text
full_sphere
has_inner_core
state_radial_representations
full_sphere_transform.enabled
full_sphere_transform.method
full_sphere_transform.fields
center_regularization.enabled
center_regularization.requested_explicitly
center_regularization.detected_from_radius_grid
center_regularization.method
center_regularization.vector_center_policy
center_regularization.scalar_center_policy
center_regularization.vector_center_diagnostics
```

## 16.5 Field-line modes

```text
shell     field lines inside the fluid shell
exterior  potential/poloidal lines reconstructed from CMB Br
both      both sets
```

Useful controls:

```bash
--external-rmax 40
--line-seeds 360
--line-max-steps 1000
--line-step-size 0.01
```

---

# 17. Detailed XSHELLS converter reference

## 17.1 Conducting inner core and radial domains

XSHELLS may store the magnetic field over a larger radial domain than velocity
or scalar fields. For example, `fieldB` may extend from the centre to the CMB
while `fieldU` and `fieldT` begin at the ICB.

When magnetic data are present, the converter:

- uses the magnetic radial grid as the viewer master grid;
- retains `Br`, `Bt` and `Bp` throughout the conducting inner core for `r > 0`;
- sets the singular spherical-component layer at exactly `r = 0` to zero;
- embeds shell-only velocity and scalar fields as zero outside their native
  radial domains;
- writes `r_icb`, `icb_radius`, `icb_index`, `radial_domains` and
  `field_domains` to `metadata.json`.

The viewer uses `icb_index`, not radial index zero, to locate the ICB.

## 17.2 Scalar gradients and N2

By default, full and `m=0`-removed gradient fields are generated.

Disable gradients with:

```bash
--no-gradients
```

Disable `m=0`-removed and phi-average variants with:

```bash
--no-m0-fields
```

When the required parameters are available, the converter generates `N2` and
`N2_full` using the same scaling as the Leeds converter.

## 17.3 Magnetic outputs

The XSHELLS converter analyses the physical CMB radial field using the native
SHTns transform. It can produce:

```text
Br_CMB_lmax13_cmb.f32
Br_Earth_lmax13_earth.f32
B_lines_shell.json
B_lines_exterior_poloidal.json
B_lines.json
```

For a conducting inner core, shell lines are deliberately restricted to the
fluid shell. Exterior lines are reconstructed from CMB `Br` as a current-free
field.

`Cps` is not requested or written by either converter. The viewer removes that
legacy key when opening older metadata files.

---

# 18. Performance and memory

A 3-D field is stored as a browser `Float32Array`.

Memory per field is approximately:

```text
nr * ntheta * nphi * 4 bytes
```

For:

```text
nr = 180
ntheta = 384
nphi = 384
```

one field is approximately:

```text
106 MB
```

Recommendations:

```text
Use --skip-field-lines for large sequences.
Choose any preload count up to the complete sequence length.
Use a cache limit of 1500-3000 MB initially and increase it only if system and GPU memory permit.
Keep isosurfaces deferred during interactive playback unless required.
Start isosurface resolution at 24-32.
Use --spectral-lmax before angular post-downsampling.
Reduce radial resolution when necessary.
```

For video with non-deferred isosurfaces or lines, cached geometry contributes to
the same memory limit as scalar arrays and field-line data. Increase `Cache limit
MB` to retain more frames, or reduce the preload count or isosurface resolution
if memory becomes limiting.

---

# 19. Troubleshooting

## 19.1 `nvm: command not found`

Reload the shell:

```bash
source ~/.bashrc
```

or load NVM explicitly:

```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
```

## 19.2 Vite reports an unsupported Node version

```bash
nvm install --lts
nvm use --lts
node --version
npm ci --no-audit --no-fund
```

## 19.3 `npm run dev` says `vite: Permission denied`

Remove and reinstall dependencies on the current machine:

```bash
rm -rf node_modules
npm ci --no-audit --no-fund
```

Do not copy `node_modules` between machines or operating systems.

## 19.4 Converter cannot import `modules`

Check the containing directory:

```bash
ls /path/to/leeds-postprocessing/modules.py
```

Then use:

```bash
--modules-dir /path/to/leeds-postprocessing
```

Test it directly:

```bash
PYTHONPATH="/path/to/leeds-postprocessing:$PYTHONPATH" \
python -c 'import modules; print(modules.__file__)'
```

## 19.5 Dataset selector cannot load a folder

For a folder outside the project, prefer:

```text
Dataset > Select primary folder
```

For a typed Windows path, run `npm run dev` and enter:

```text
C:\Users\wgdh881\Downloads\data_FLAYER_C19
```

For a typed POSIX path, use:

```text
file:/absolute/path/to/data_FLAYER_C19
```

When using `npm run preview` or another static server, absolute text paths are
not available; use the folder picker or a path under `public/` instead.

## 19.6 `Unexpected token '<'` while reading JSON

Vite returned `index.html` because the requested JSON path does not exist.
Check:

```bash
ls public/data/metadata.json
ls public/data/sequence.json
ls public/data/frames/state03100/metadata.json
```

## 19.7 Sequence playback is laggy

Use:

```text
Preload frames = as many snapshots as memory permits
Cache limit MB = increase according to available RAM/GPU memory
Preload N frames
```

To request the complete sequence, set `Preload frames` to the sequence length or
click `Preload full sequence`. The only cache constraint is `Cache limit MB`.

Also consider:

```text
Defer isosurfaces = on
Defer field lines = on
hide unused slices
reduce isosurface resolution
```

When defer is off, ensure enough frames are preloaded so the heavy geometry is
ready before playback reaches it.

## 19.8 Video freezes when fields change

Use the current viewer version. Playback-enabled video export uses a dedicated
frame-synchronised driver and pauses recording during any remaining frame swap.

Preload the required number of frames, ideally the complete sequence when memory
permits, and reduce heavy geometry if the browser still cannot maintain the
requested rate.

## 19.9 Earth texture cannot be loaded

The image is optional and not included. Add:

```text
public/assets/earth_blue_marble.jpg
```

or select:

```text
Earth surface > Display = Magnetic Br
```

## 19.10 Browser still shows an old error

Hard-refresh:

```text
Ctrl + F5
```

or restart Vite:

```bash
npm run dev
```

## 19.11 Phi averages contain extreme values

Reconvert using the current converter. Non-finite and extreme outliers are
excluded from phi-average calculations.

## 19.12 Sequence root metadata is missing

The current sequence converter copies the first frame to the dataset root. For
an older sequence, copy it manually:

```bash
cp -a public/data/frames/state03100/* public/data/
```

---

# 20. Project layout and development commands

Typical project layout:

```text
dynamo-three-viewer/
  index.html
  package.json
  package-lock.json
  README.md
  requirements-xshells.txt
  public/
    assets/
      README_EARTH_TEXTURE.txt
      earth_blue_marble.jpg       optional, user-supplied
    data/
      metadata.json
      coordinates.json
      *_volume.f32
      *_cmb.f32
      *_earth.f32
      sequence.json
      frames/
  src/
    main.js
    style.css
  tools/
    convert_state_to_viewer.py
    convert_xshells_to_viewer.py
    make_demo_data.py
```

`modules.py` is external Leeds post-processing code and is not part of this
layout unless you copy it into the project yourself.

Useful commands:

```bash
npm run dev       # development server
npm run build     # production build
npm run preview   # preview production build
npm run make-data # regenerate demonstration data
node --check src/main.js
```

The viewer can load files under `public/`, through the folder picker, or through Vite `/@fs/` absolute paths. Do not place converted
data under `src/`.

## View-state code

The `View state` folder can:

```text
Copy code
Show code
Load code
Save code to file
```

A view state includes selected fields, colour maps, ranges, opacity, camera,
lighting, surfaces, slices, field lines, isosurfaces, Earth settings and
sequence settings. It is useful for reproducing a figure across datasets.

### Fixed-view video and background PNG sequences

Video export now has a `No motion (current view)` rotation mode. This records the
current camera view without any camera motion; if `Activate playback` is enabled,
the video records only the sequence evolution.

PNG-sequence rendering now ignores browser `resize` events until the export is
finished, so the exported image size stays fixed even if the browser window size
changes during rendering. The viewer size is synchronised back to the browser
window when the export completes.

### Background export for video and PNG sequences

Video export and PNG-sequence export include a `Background export` option. When enabled, the main viewer canvas and corner axes are hidden while the export runs, so sequence/video updates are not displayed interactively. This is useful on remote desktop or HPC graphical sessions where live viewport updates are slow. The export still uses the current viewer scene and settings, and the viewport is restored automatically when the export completes or is cancelled.

### Hidden-tab and minimized-window exports

Browser tabs normally suspend `requestAnimationFrame` and canvas `captureStream`
when they are hidden or minimized. The background export paths therefore use
explicit rendering instead of the interactive animation loop.

- Background PNG sequences render each frame explicitly and do not wait for
  `requestAnimationFrame`.
- Background video uses WebCodecs with deterministic frame timestamps and muxes
  VP8 frames directly into a standard `.webm` file. It continues when the
  browser tab is hidden or the window is minimized, provided the page remains
  open.
- Foreground video keeps the normal browser `MediaRecorder` WebM workflow.

Background video requires a recent Chromium-based browser and a secure context
(`localhost`, an SSH-forwarded localhost URL, or HTTPS). The resulting WebM file
can be opened directly; no IVF conversion is required.

### Hidden-tab WebM video

Hidden-tab video export uses WebCodecs for deterministic frame-by-frame VP8 encoding, then muxes the encoded frames directly into a standard WebM container in the browser. The saved `.webm` file can be opened directly in browsers, VLC, mpv, and other WebM-compatible players; no IVF conversion step is required.

### Playback and video frame range

`Sequence playback` now includes `First played frame` and `Last played frame`.
Normal playback, keyboard frame stepping, preloading, foreground video, and
hidden-tab WebM export all loop only within this inclusive range. Video export
starts from the selected first frame and restores the frame that was displayed
before recording after export completes. `Preload selected range` prepares all
frames in the selected interval, subject only to `Cache limit MB`.

### Windows absolute paths

Enter a Windows dataset folder directly, for example:

```text
C:\Users\wgdh881\Desktop\public\data_FLAYER_C19
```

The viewer converts it to an internal `localfs:` source and reads files through
a localhost-only Vite endpoint. This works with both `npm run dev` and
`npm run preview`. With a generic static server, use `Select primary folder`
instead, because browsers cannot read arbitrary local paths directly.

### Windows OneDrive paths

Absolute Windows paths containing spaces, such as:

```text
C:\Users\wgdh881\OneDrive - University of Leeds\DEEP\public\data_FLAYER_C19
```

are sent to the Vite server using a base64url-encoded local-filesystem endpoint,
so spaces and punctuation are preserved exactly. Restart `npm run dev` or
`npm run preview` after updating because `vite.config.js` implements this route.
If the Vite server runs inside WSL rather than Windows, use the corresponding
`/mnt/c/Users/...` path or the folder-selection button.

