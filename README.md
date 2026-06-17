# Dynamo Three.js Viewer

Local browser visualiser for spherical-dynamo state data.

The viewer displays independently selectable scalar fields on:

- the CMB surface,
- the ICB surface, if present,
- an equatorial slice,
- a two-sided meridional slice with a longitude slider,
- magnetic field lines seeded from the CMB, with shell, exterior, or both modes.

It is designed to run locally at `http://127.0.0.1:5173`.

---

## 1. Requirements

You need Python and Node.js/npm.

```bash
python --version
node --version
npm --version
```

Python 3.11 is fine. For Vite, use a recent Node.js version. If `node` and `npm` are missing, install Node locally with `nvm`:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.5/install.sh | bash
source ~/.bashrc
nvm install --lts
nvm use --lts
```

Then check:

```bash
node --version
npm --version
```

For real state conversion, your Python environment must also be able to import your `modules.py` dependencies, including `numpy`, `h5py`, `scipy`, `shtns`, `matplotlib`, and `cartopy`, because those are imported by `modules.py` at top level.

---

## 2. Install the viewer

From inside this folder:

```bash
npm install
```

---

## 3. Run with the included demo data

The zip includes demo data already. Run:

```bash
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

To regenerate the synthetic demo data:

```bash
npm run make-data
npm run dev
```

---

## 4. Convert a real Leeds spherical-dynamo state file

The real converter is:

```text
tools/convert_state_to_viewer.py
```

It uses your existing `modules.py` routines:

```python
load_state
PolTor_to_spat
SH_to_spat
SH_to_spat_nom0
gradient_spat
lsd_to_shtns
shtns
```

### Option A: run from the directory containing `modules.py`

```bash
cd /path/where/modules.py/is
python /path/to/dynamo-three-viewer/tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --out /path/to/dynamo-three-viewer/public/data
```

Then run the viewer:

```bash
cd /path/to/dynamo-three-viewer
npm run dev
```

### Option B: pass the directory containing `modules.py`

```bash
cd /path/to/dynamo-three-viewer
python tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --modules-dir /path/where/modules.py/is \
  --out public/data

npm run dev
```

To add a CMB map of `B_r` truncated to a chosen spherical-harmonic degree, append for example:

```bash
--cmb-br-ltrunc 10
```

### Option C: convert the latest state file in a folder

```bash
python tools/convert_state_to_viewer.py \
  --folder "/nfs/b0251/Data/FLAYER/DYN_false_VBC=1_CompBC=4_CBC=4_Ek=2e-5_Pm=1_Pr=1_Sc=10_Ra=120e6_RaC=1e9_rs=0.83_q=-100/1" \
  --modules-dir /path/where/modules.py/is \
  --out public/data

npm run dev
```

The converter picks the largest `state<number>.cdf.dat` file.

---

## 5. Quantities exported to the viewer

The converter writes the following 3-D fields when possible:

```text
Br, Bt, Bp, Babs
ur, ut, up, Uabs
C, Comp
Cnom0, Compnom0
Cnol0, Compnol0
N2
grad_rC, grad_rComp
```

Magnetic quantities are written only when `BP` is not zero everywhere. The converter checks:

```text
max(abs(BP)) > magnetic_tol
```

If `BP` is zero everywhere, the state is classified as `non_magnetic`, the magnetic fields are not exported, and magnetic field-line tracing is skipped. If `BP` is non-zero, the state is classified as `dynamo`.

Here:

- `Bt` means the theta component of the magnetic field.
- `Bp` means the phi component of the magnetic field.
- `ut` means the theta component of velocity.
- `up` means the phi component of velocity.
- `N2` is written as a radial-profile field broadcast into a 3-D volume, so the current viewer can display it on surfaces and slices.
- The true radial profiles are also written to `public/data/profiles.json`.

You can optionally export a CMB-only low-degree magnetic map, for example `Br_CMB_lmax10`, using:

```bash
python tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --modules-dir /path/where/modules.py/is \
  --out public/data \
  --cmb-br-ltrunc 10
```

This synthesizes `B_r` at the CMB after setting all magnetic poloidal coefficients with spherical-harmonic degree `l > 10` to zero. The resulting field is a **CMB-only** field and appears only in the CMB field selector.

The Brunt-Vaisala frequency profile follows the expression from your script:

```python
N2 = r * E**2 * (grad_rComp_mean_r * RaC / Sc + grad_rC_mean_r * RaT / Pr)
```

The display title and metadata intentionally omit `rs` and `rm`.

---

## 6. Viewer controls

The viewer now has separate field selectors for:

```text
CMB field
ICB field
Equator field
Meridian field
```

This means, for example, you can show:

```text
CMB: Br
ICB: C
Equator: Comp
Meridian: N2
```

The meridional slice is two-sided: it shows the plane at longitude `phi` and the opposite side at `phi + pi`.

There is also a `Reset camera view` button in the GUI.

The viewer displays separate colour scale bars for the CMB, ICB, equatorial slice, and meridional slice, because each object can show a different field. Each display also has its own independent colour-scale controls:

```text
Scale: symmetric, minmax, or manual
Manual min
Manual max
Opacity
```

The colour range is computed from the displayed geometry, not the whole 3-D volume. For example, the CMB colour range is computed only from the selected CMB surface values; the equatorial range is computed only from the equatorial cut.

Use `symmetric` for signed fields such as `Br`, `ur`, `C`, or `Comp`. Use `minmax` for positive fields such as `Babs`, `Uabs`, or possibly `N2`. Use `manual` when you want to compare different surfaces/slices using the same fixed limits.

---

## 7. Magnetic field lines

The default is now **shell mode**:

```text
--field-line-mode shell
```

This traces the actual transformed simulation magnetic field `(Br, Bt, Bp)` inside the fluid shell, i.e. outside the inner core and below the CMB. Each line is integrated in both directions from a seed just below the CMB and then concatenated, so the displayed object is a complete field-line segment rather than a one-sided trace. These are the lines to use when you want the dynamo field to loop through the fluid shell.

The converter also keeps the older exterior mode:

```text
--field-line-mode exterior
```

Exterior mode does **not** plot the full simulation field. It reconstructs a potential/poloidal field outside the CMB from the surface poloidal magnetic coefficients `BP[:, -1]`:

```text
P_lm(r) = P_lm(r_cmb) * (r_cmb / r)^(l+1)
```

The exterior toroidal field is set to zero, as expected for the exterior potential-field approximation. The exterior tracer now keeps CMB-to-CMB arcs by default: it tries both integration directions from a seed just outside the CMB and keeps only traces that return to the CMB after moving outward.

You can also write both sets and choose between them in the viewer:

```text
--field-line-mode both
```

The converter writes separate files when possible:

```text
public/data/B_lines_shell.json
public/data/B_lines_exterior_poloidal.json
```

and also writes a backward-compatible combined file:

```text
public/data/B_lines.json
```

In the viewer, use **Other visualisation → Line type** to switch between `shell`, `exterior`, or `both`. If you turn **Magnetic field lines** off, the viewer removes all line groups from the scene rather than only hiding one group.

To skip field lines:

```bash
python tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --modules-dir /path/where/modules.py/is \
  --out public/data \
  --skip-field-lines
```

To control line density:

```bash
python tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --modules-dir /path/where/modules.py/is \
  --out public/data \
  --field-line-mode shell \
  --line-seed-theta 9 \
  --line-seed-phi 18 \
  --line-max-steps 1000
```

For exterior mode you can also control the exterior radial domain:

```bash
python tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --modules-dir /path/where/modules.py/is \
  --out public/data \
  --field-line-mode exterior \
  --external-rmax 2.5 \
  --external-nr 128
```

If `--external-rmax` is omitted, the exterior-mode default is `2.5 * r_outer`. For a dipole-dominated case, increase this value if high-latitude exterior arcs are being discarded before they return to the CMB.

Additional exterior-line options:

```text
--external-closed-only / --no-external-closed-only
--external-btheta-sign auto|plus|minus
```

The default `--external-closed-only` keeps only CMB-to-CMB arcs. The default `--external-btheta-sign auto` tests both possible SHTns sign conventions for the exterior poloidal theta component and keeps the one producing more CMB-returning arcs.

---

## 8. Downsampling for large states

For large simulations, do not load full resolution immediately. Use downsampling:

```bash
python tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --modules-dir /path/where/modules.py/is \
  --out public/data \
  --downsample-r 2 \
  --downsample-theta 2 \
  --downsample-phi 2
```

This keeps every second point in each direction. The viewer becomes much faster and the files are much smaller.

For a very large state, start with:

```bash
python tools/convert_state_to_viewer.py \
  --file /path/to/state000123.cdf.dat \
  --modules-dir /path/where/modules.py/is \
  --out public/data \
  --downsample-r 2 \
  --downsample-theta 4 \
  --downsample-phi 4 \
  --skip-field-lines
```

Then reduce the downsampling once the pipeline works.

---

## 9. Data format expected by the browser

Each scalar field is a raw little-endian float32 file:

```text
<field>_volume.f32
```

Flattening order:

```python
field[ir, itheta, iphi]
```

C-order index:

```python
index = (ir * ntheta + itheta) * nphi + iphi
```

The converter writes `metadata.json`, `coordinates.json`, and `profiles.json`.

---
