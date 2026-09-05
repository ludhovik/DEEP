# MagIC converter for DEEPscope

`tools/convert_magic_to_viewer.py` converts the standard three-dimensional
MagIC graphic files `G_<number>.TAG` and `G_ave.TAG` into the same DEEPscope data
contract used by the Leeds and XSHELLS converters.

## Supported inputs

The converter uses MagIC's official `MagicGraph` reader. It therefore supports
the graphic-file variants supported by that reader, including record-marker and
stream files, endian detection, thermal convection, composition/double
diffusion, magnetic dynamos, pressure, phase field, and inner-core magnetic
arrays when those quantities are present in the source file.

This converter does not read MagIC movie, checkpoint, `B_coeff`, or radial
profile files. Produce a `G_#.TAG` graphic snapshot from MagIC for a complete 3-D
viewer conversion.

## Install

From the DEEPscope repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-magic.txt
git clone https://github.com/magic-sph/magic.git ../magic
python -c 'import sys; sys.path.insert(0, "../magic/python"); from magic import MagicGraph; print("MagicGraph OK")'
```

The pure-Python reader is sufficient. You do not need to compile MagIC's
optional f2py reader libraries.

## Convert one snapshot

With an explicit file:

```bash
python tools/convert_magic_to_viewer.py \
  --graph "/path/to/run/G_17.my_tag" \
  --magic-python-dir "../magic/python" \
  --out public/data_magic
```

With the normal MagIC folder/tag convention:

```bash
python tools/convert_magic_to_viewer.py \
  --folder "/path/to/run" \
  --ivar 17 \
  --tag my_tag \
  --magic-python-dir "../magic/python" \
  --out public/data_magic
```

If `--ivar` is omitted, the highest numbered matching graphic is selected. Use
`--average` to select `G_ave.TAG`.

After conversion, start DEEPscope and load:

```text
/data_magic
```

## Convert a sequence

```bash
python tools/convert_magic_to_viewer.py \
  --folder "/path/to/run" \
  --tag my_tag \
  --sequence-first 1 \
  --sequence-last 20 \
  --sequence-step 1 \
  --sequence-clear \
  --magic-python-dir "../magic/python" \
  --out public/data_magic
```

This writes `sequence.json` and one viewer dataset per frame below
`public/data_magic/frames/`.

## Common converter capabilities

When their source quantities exist, the MagIC converter writes:

- velocity: `ur`, `ut`, `up`, `us`, `uz`, `Uabs`, and kinetic `helicity`;
- magnetic field: `Br`, `Bt`, `Bp`, and `Babs`;
- entropy/temperature: `C` plus the backward-compatible `T` alias;
- composition: `Comp` from MagIC `xi`;
- MagIC-only quantities: `P` (pressure) and `Phase`;
- azimuthal averages and `m=0`-removed variants;
- full and `m=0`-removed scalar gradients;
- `N2_full` and `N2` when the required control parameters and scalar fields
  exist;
- optional motional EMF and induction through `--emf` and `--induction`;
- CMB and Earth-surface radial magnetic maps;
- shell and reconstructed exterior magnetic field lines;
- explicit shell, full-sphere, and conducting-inner-core metadata;
- spatial downsampling and sequence playback metadata.

Fields absent from a MagIC run are skipped; the converter does not invent a
magnetic, compositional, pressure, or phase field.

Useful options include:

```bash
--downsample-r 2 --downsample-theta 2 --downsample-phi 2
--no-gradients
--no-m0-fields
--emf --induction
--cmb-br-ltrunc 13
--earth-br-ltrunc 13
--field-line-mode both
--line-seeds 360
--skip-field-lines
```

MagIC header values are used for `Ek`, `Pr`, `Sc`, `RaT`, and `RaC`. The common
CLI overrides (`--Ek`, `--Pr`, `--Sc`, `--RaT`, and `--RaC`) remain available.

## Coordinate and inner-core handling

`MagicGraph` exposes fields as `(phi_sector, theta, radius)`, with the radial
coordinate commonly running from the CMB toward the ICB. DEEPscope requires
little-endian C-order `(radius, theta, phi)` arrays on an increasing radial
grid. The converter performs this transformation and unfolds `minc` symmetry
without retaining a duplicate `phi=2*pi` plane.

When MagIC supplies inner-core magnetic arrays, those radii are merged into the
magnetic master grid. Fluid and scalar fields remain restricted to the fluid
shell and are zero outside their native radial domain. Conductivity metadata is
based on MagIC's `sigma` value; an insulating inner-core potential field may be
present without being mislabeled as a conducting inner core.

## Published validation dataset

The converter was tested with the open Zenodo dataset:

> Yifan Wu, *Dataset of "Parameter regimes of hemispherical dynamo waves in a
> spherical shell from 3D MHD simulations"*, Zenodo record 8036223, CC BY 4.0.

Record:

```text
https://zenodo.org/records/8036223
```

The 3.6 GB `pub_data.zip` contains several genuine MagIC graphic snapshots. The
specific validation member was:

```text
pub_data_Wu2023/cases/ek3e-5_pm05ra5e7/G_17.pm05ra5e7
```

Its matching MagIC log is in the same directory. After downloading the archive,
extract only that case with:

```bash
unzip -j pub_data.zip \
  'pub_data_Wu2023/cases/ek3e-5_pm05ra5e7/G_17.pm05ra5e7' \
  'pub_data_Wu2023/cases/ek3e-5_pm05ra5e7/log.pm05ra5e7' \
  -d magic_example
```

Then convert it:

```bash
python tools/convert_magic_to_viewer.py \
  --graph magic_example/G_17.pm05ra5e7 \
  --magic-python-dir ../magic/python \
  --out public/data_magic_example \
  --downsample-r 2 \
  --downsample-theta 2 \
  --downsample-phi 2 \
  --cmb-br-ltrunc 13 \
  --field-line-mode both
```

The validated snapshot contains velocity, entropy, pressure, and all three
magnetic components on an `81 x 200 x 400` fluid-shell grid. The MagIC reader
reports `Ek=3e-5`, `Pr=1`, `Pm=0.5`, `Ra=5e7`, and radius ratio `0.35`.

## Validation commands

Run the shared converter tests:

```bash
npm run test-converters
```

Check one converted dataset's binary sizes:

```bash
python - <<'PY'
import json
from pathlib import Path

root = Path("public/data_magic")
metadata = json.loads((root / "metadata.json").read_text())
expected = metadata["nr"] * metadata["ntheta"] * metadata["nphi"] * 4
for name, filename in metadata["fields"].items():
    actual = (root / filename).stat().st_size
    assert actual == expected, (name, actual, expected)
print("All volume files have the declared dimensions.")
PY
```
