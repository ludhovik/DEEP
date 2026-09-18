# DEEP: download and convert the six selected examples

Checked on 13 September 2026. Run these commands in **WSL/Bash**, starting in your
DEEP repository: the directory containing `tools/` and `requirements-rayleigh.txt`.

The Ganymede motional-induction example by **Cabanes, Gastine and Fournier** is
already your `Weber22_deep_T0` case. “Weber22” names the imposed magnetic-field
model, not the authors of the ocean simulation. The original and symlinked
Duarte commands also describe one example. There are therefore **six distinct
examples** in your list.

| Example | Published source | Download | Output folder under Desktop/public |
|---|---|---|---|
| Rayleigh solar tachocline MHD | [Matilsky et al., Zenodo 7117669](https://zenodo.org/records/7117669) | `MHD_Case.zip`, 1.25 GB | `data_rayleigh_tachocline` |
| Rayleigh hydrodynamic benchmark | [Rayleigh Sample Outputs, Zenodo 13376792](https://zenodo.org/records/13376792) | `benchmark_outputs.zip`, 9.02 MB | `data_rayleigh_benchmark` |
| Wu: `pm2ra10e7` | [Wu, Zenodo 8036223](https://zenodo.org/records/8036223) | `pub_data.zip`, 3.64 GB; shared with the next case | `data_magic_Wu24_2` |
| Wu: `pm2ra200e7` | [Wu, Zenodo 8036223](https://zenodo.org/records/8036223) | Same ZIP, downloaded once | `data_magic_Wu24` |
| Ganymede: `Flow_Rm1p77_Weber22_deep_T0` | [Cabanes, Gastine and Fournier, Zenodo 16612142](https://zenodo.org/records/16612142) | `MI_Gany.tgz`, 19.10 GB, containing another `.tgz` | `data_magic_Weber22` |
| Duarte18 Jupiter snapshot | [MagIC Jupiter, Edmond, DOI 10.17617/3.1Q](https://doi.org/10.17617/3.1Q) | Original `G_a60.vcondInteriorModelRa6e7a13sig02rat090Pm2Pr01ag` binary | `data_magic_Duarte18` |

Sizes above are decimal bytes rounded for display. Your Wu24 output labels are
preserved; the archive itself is named `pub_data_Wu2023`.

## 1. Common setup

Run this once in the terminal you will use for the following commands:

```bash
DEEP_ROOT="$PWD"
DEEP_PUBLIC="/mnt/c/Users/wgdh881/Desktop/public"
DEEP_INPUT="$DEEP_PUBLIC/input"
DEEP_CACHE="$HOME/.cache/deepscope"
MAGIC_ROOT="$DEEP_ROOT/../magic"
MAGIC_PYTHON="$MAGIC_ROOT/python"

mkdir -p "$DEEP_INPUT" "$DEEP_CACHE"

python3 -m pip install -r requirements-rayleigh.txt -r requirements-magic.txt

if [ ! -d "$MAGIC_PYTHON/magic" ]; then
    git clone https://github.com/magic-sph/magic.git "$MAGIC_ROOT"
fi
```

MagIC conversion uses its Python reader; you do not need to compile or run the
MagIC solver. Rayleigh conversion uses the reader included in DEEP.

### Check Rayleigh support

This repository includes the Rayleigh reader update needed for the solar
checkpoint's three radial domains. Check the converter options:

```bash
python3 tools/convert_rayleigh_to_viewer.py --help
```

The help should include `--radial-interface-tolerance`. The commands below use
this option explicitly for the solar case; the default remains strict for
other datasets. No separate patch is needed with this version of DEEP.

## 2. Rayleigh hydrodynamic benchmark

Source: [Rayleigh Sample Outputs](https://zenodo.org/records/13376792).
The case has velocity, a thermal scalar and pressure, with no magnetic field.

Download, verify and extract:

```bash
curl -fL --retry 5 --continue-at - \
  "https://zenodo.org/api/records/13376792/files/benchmark_outputs.zip/content" \
  -o "$DEEP_INPUT/rayleigh-benchmark_outputs.zip"

(
  cd "$DEEP_INPUT" &&
  printf '%s\n' \
    '2cd4096d4aeee2a95ee7ccc888fc571f  rayleigh-benchmark_outputs.zip' \
    | md5sum -c - &&
  unzip -n rayleigh-benchmark_outputs.zip
)
```

Convert checkpoint `00040000`:

```bash
python3 tools/convert_rayleigh_to_viewer.py \
  --checkpoint "$DEEP_INPUT/benchmark_outputs/Checkpoints/00040000" \
  --out "$DEEP_PUBLIC/data_rayleigh_benchmark" \
  --incremental \
  --cache-dir "$DEEP_CACHE" \
  --skip-field-lines \
  --no-earth-br
```

This exact conversion was run successfully with the updated reader: 33 volume
fields on a `48 × 64 × 128` grid. The official benchmark kinetic-energy test
also passed. No angular truncation is needed for this small example.

## 3. Rayleigh solar tachocline MHD

Source: [Confinement of the Solar Tachocline by Dynamo Action in the Radiative
Interior](https://zenodo.org/records/7117669).

**You already downloaded and extracted this case successfully.** Reuse it:

```bash
RAYLEIGH_MHD_CASE="$HOME/Downloads/rayleigh_7117669/Case_M"
```

For a fresh download in the common input folder instead, run this optional
block and then use its `RAYLEIGH_MHD_CASE` value:

```bash
mkdir -p "$DEEP_INPUT/rayleigh-tachocline"

curl -fL --retry 5 --continue-at - \
  "https://zenodo.org/api/records/7117669/files/MHD_Case.zip/content" \
  -o "$DEEP_INPUT/rayleigh-tachocline/MHD_Case.zip"

(
  cd "$DEEP_INPUT/rayleigh-tachocline" &&
  printf '%s\n' \
    '806e37071a904460848191d4e4b4dbb5  MHD_Case.zip' \
    | md5sum -c - &&
  unzip -n MHD_Case.zip
)

RAYLEIGH_MHD_CASE="$DEEP_INPUT/rayleigh-tachocline/Case_M"
```

Convert using the included reader:

```bash
python3 tools/convert_rayleigh_to_viewer.py \
  --checkpoint "$RAYLEIGH_MHD_CASE/Checkpoints/50200000" \
  --out "$DEEP_PUBLIC/data_rayleigh_tachocline" \
  --incremental \
  --cache-dir "$DEEP_CACHE" \
  --spectral-lmax 128 \
  --radial-interface-tolerance 0.01 \
  --emf --induction \
  --field-line-mode shell \
  --line-seeds 360 \
  --line-max-steps 4000 \
  --no-earth-br
```

The `W`, `Z`, `A`, `C`, `T`, `P`, `grid_etc`, `equation_coefficients` and
`main_input` files must remain together. The density is taken from the supplied
reference file; do not replace it with unit density. Native `C` is a magnetic
potential, not a composition field.

The three radial domains are reconstructed independently. This source has
small differences between reconstructed values on the two sides of an
interface: at degree 128, the largest is **0.743% of the maximum absolute Bp
field**. The explicit tolerance `0.01` permits differences up to 1% and averages
each duplicated interface pair for visualization. Every other radial sample is
preserved. The measured differences and tolerance are saved under
`rayleigh.radial_domains` in `metadata.json`. Gradients and curls near those
interfaces depend on this averaging and should not be treated as exact native
interface diagnostics.

This command was run successfully: **55 fields**, a `190 × 130 × 260` grid,
and **364 internal field lines**. The requested 360 seeds are adjusted to a
regular seed grid. The angular degree is reduced from 255 to 128. The archive
does not contain a same-time native physical snapshot for an independent
pointwise comparison; validation includes analytic multidomain fields and the
official separate benchmark.

## 4. Download and extract both Wu cases once

Source: [Yifan Wu's hemispherical dynamo-wave dataset](https://zenodo.org/records/8036223).
Both exact graphic filenames and their matching logs were verified in the ZIP
directory. Download the shared archive:

```bash
curl -fL --retry 5 --continue-at - \
  "https://zenodo.org/api/records/8036223/files/pub_data.zip/content" \
  -o "$DEEP_INPUT/Wu_pub_data.zip"

(
  cd "$DEEP_INPUT" &&
  printf '%s\n' \
    '1ab9a4fe60d4eb247c2c7d40eeaf95b2  Wu_pub_data.zip' \
    | md5sum -c - &&
  unzip -n Wu_pub_data.zip \
    'pub_data_Wu2023/cases/ek3e-5_pm2ra10e7/G_19.pm2ra10e7' \
    'pub_data_Wu2023/cases/ek3e-5_pm2ra10e7/log.pm2ra10e7' \
    'pub_data_Wu2023/cases/ek3e-5_pm2ra200e7/G_19.pm2ra200e7' \
    'pub_data_Wu2023/cases/ek3e-5_pm2ra200e7/log.pm2ra200e7'
)
```

This extracts about 448 MB instead of unpacking all of the unrelated outputs.

### Wu: `pm2ra10e7`

```bash
python3 tools/convert_magic_to_viewer.py \
  --graph "$DEEP_INPUT/pub_data_Wu2023/cases/ek3e-5_pm2ra10e7/G_19.pm2ra10e7" \
  --magic-python-dir "$MAGIC_PYTHON" \
  --out "$DEEP_PUBLIC/data_magic_Wu24_2" \
  --incremental \
  --cache-dir "$DEEP_CACHE" \
  --spectral-lmax 128 \
  --emf --induction \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --line-seeds 360 \
  --external-rmax 40 \
  --external-nr 192 \
  --line-max-steps 4000
```

### Wu: `pm2ra200e7`

```bash
python3 tools/convert_magic_to_viewer.py \
  --graph "$DEEP_INPUT/pub_data_Wu2023/cases/ek3e-5_pm2ra200e7/G_19.pm2ra200e7" \
  --magic-python-dir "$MAGIC_PYTHON" \
  --out "$DEEP_PUBLIC/data_magic_Wu24" \
  --incremental \
  --cache-dir "$DEEP_CACHE" \
  --spectral-lmax 128 \
  --emf --induction \
  --cmb-br-ltrunc 13 \
  --field-line-mode both \
  --line-seeds 360 \
  --external-rmax 40 \
  --external-nr 192 \
  --line-max-steps 4000
```

These preserve your chosen exterior and low-degree field settings. Exterior
radii are in the simulation's length units. Earth-scaled maps are a display
assumption for these generic spherical-shell dynamos.

## 5. Ganymede motional induction: the Weber22 deep-ocean case

Source: [Cabanes, Gastine and Fournier, Data and software for: Motional induction
in Ganymede's ocean](https://zenodo.org/records/16612142).
The [paper's Open Research statement](https://arxiv.org/html/2603.06305v1)
links this record and explains the Weber22 magnetic model.

If you already have the extracted `data/E1e5Ra2e9/Weber22_deep_T0` directory in
Windows Downloads, skip the large download and extraction and use the existing
path shown after the extraction commands.

Download the **19.10 GB** archive:

```bash
mkdir -p "$DEEP_INPUT/ganymede"

curl -fL --retry 5 --continue-at - \
  "https://zenodo.org/api/records/16612142/files/MI_Gany.tgz/content" \
  -o "$DEEP_INPUT/MI_Gany.tgz"

(
  cd "$DEEP_INPUT" &&
  printf '%s\n' \
    'ffc0d3a7fceded5e4a5db3dd3e7d617b  MI_Gany.tgz' \
    | md5sum -c -
)
```

This is a gzip-compressed TAR containing **another gzip-compressed TAR**.
First extract the deep-ocean archive (3.91 GB compressed), then its Weber22 T0
directory. The two archive levels were verified directly:

```bash
tar -xzf "$DEEP_INPUT/MI_Gany.tgz" \
  -C "$DEEP_INPUT/ganymede" \
  data/E1e5Ra2e9.tgz

tar -xzf "$DEEP_INPUT/ganymede/data/E1e5Ra2e9.tgz" \
  -C "$DEEP_INPUT/ganymede/data" \
  E1e5Ra2e9/Weber22_deep_T0

GANYMEDE_CASE="$DEEP_INPUT/ganymede/data/E1e5Ra2e9/Weber22_deep_T0"
```

Selective TAR extraction still scans the compressed archive; allow it to
finish. If you are reusing the files from your original command, set this
instead:

```bash
GANYMEDE_CASE="/mnt/c/Users/wgdh881/Downloads/data/E1e5Ra2e9/Weber22_deep_T0"
```

Convert your selected `G_7` snapshot:

```bash
python3 tools/convert_magic_to_viewer.py \
  --graph "$GANYMEDE_CASE/G_7.Flow_Rm1p77_Weber22_deep_T0" \
  --magic-python-dir "$MAGIC_PYTHON" \
  --out "$DEEP_PUBLIC/data_magic_Weber22" \
  --incremental \
  --cache-dir "$DEEP_CACHE" \
  --spectral-lmax 128 \
  --emf --induction \
  --field-line-mode shell \
  --no-earth-br
```

The graph filename is the one you supplied. The complete 19 GB archive was not
downloaded or converted in this session. Your existing extracted path can be
used immediately.

This exports the magnetic field stored in that snapshot. It does **not** isolate
the ocean's motional signal, which the paper defines as the difference between
the matched moving-ocean and motionless-ocean solutions. Likewise, `--induction`
exports `curl(u × B)`, not that difference or the full magnetic time derivative.
Shell-only field lines and `--no-earth-br` preserve your choice for this model
with imposed internal and external magnetic sources.

## 6. Duarte18 Jupiter graphic snapshot

Source: [MagIC Jupiter, Edmond, DOI 10.17617/3.1Q](https://doi.org/10.17617/3.1Q).
The [official DOI metadata](https://api.datacite.org/dois/10.17617/3.1q)
identifies the collection, the `G_a60.*` graphic and its use in the Wicht et al.
Jupiter analysis. Your `Duarte18` label is retained.

**Edmond blocks automated access from this session.** I could verify the source
record through its DOI metadata but not retrieve the current per-file download
ID. Consequently, there is no guessed `curl` file URL here.

For a fresh download:

1. Open the source record in your normal browser.
2. Select the original binary named
   `G_a60.vcondInteriorModelRa6e7a13sig02rat090Pm2Pr01ag`.
3. Save it in `C:\Users\wgdh881\Desktop\public\input\duarte18`.
   Create that directory with the command below first if necessary.

The original `G_a60…` file is already a graphic binary and needs **no
decompression**. If you choose the website's “Download ZIP” option, unpack that
ZIP and locate the graphic inside it; the individual-file route avoids that
extra wrapper.

```bash
mkdir -p "$DEEP_INPUT/duarte18"
DUARTE_TAG="vcondInteriorModelRa6e7a13sig02rat090Pm2Pr01ag"
DUARTE_GRAPH="$DEEP_INPUT/duarte18/G_a60.$DUARTE_TAG"

if [ ! -f "$DUARTE_GRAPH" ]; then
    DUARTE_GRAPH="/mnt/c/Users/wgdh881/Downloads/G_a60.$DUARTE_TAG"
fi

python3 tools/convert_magic_to_viewer.py \
  --graph "$DUARTE_GRAPH" \
  --magic-python-dir "$MAGIC_PYTHON" \
  --out "$DEEP_PUBLIC/data_magic_Duarte18" \
  --incremental \
  --cache-dir "$DEEP_CACHE" \
  --spectral-lmax 128 \
  --emf --induction \
  --field-line-mode shell \
  --no-earth-br
```

This automatically reuses your existing Windows Downloads file if the common
input copy does not exist. Current DEEP accepts `G_a60…` directly: **no
`G_60…` symbolic link is needed**. See the [current MagIC converter
instructions](https://github.com/ludhovik/DEEP/blob/main/README.md#magic-converter).
The available graphic is converted as stored; missing inner-core records are
not reconstructed or invented by the compatibility reader.

## 7. Open and check the results

Open each `data_…` folder from the source table using the DEEP viewer's folder
picker. Select the folder containing `metadata.json`, rather than the original
archive or checkpoint directory.

Rerunning a conversion with identical inputs and options uses `--incremental`
to skip a validated unchanged bundle. Cache files stay under
`$HOME/.cache/deepscope`, outside the published data directories.

After converting all six cases, validate their output bundles from the DEEP
repository:

```bash
python3 - "$DEEP_PUBLIC" <<'PY'
import json
import sys
from pathlib import Path
from tools.viewer_bundle import validate_bundle

root = Path(sys.argv[1])
names = [
    'data_rayleigh_tachocline',
    'data_rayleigh_benchmark',
    'data_magic_Wu24_2',
    'data_magic_Wu24',
    'data_magic_Weber22',
    'data_magic_Duarte18',
]
for name in names:
    folder = root / name
    validate_bundle(folder)
    metadata = json.loads((folder / 'metadata.json').read_text())
    print(name, 'OK', len(metadata['fields']), 'fields')
PY
```

Validation performed here: both real Rayleigh conversions, all 16 Rayleigh
tests including the downloaded benchmark, and archive/CLI checks described
above. The four MagIC conversions were not rerun in this session.


## ASPECT mantle convection

[ASPECT_CONVERTER.md](ASPECT_CONVERTER.md) contains full commands for two examples:

- A small, tested 3-D World Builder plume initial-condition mesh from the official
  ASPECT repository (download directly as VTU; not an evolved simulation).
- Euen et al. (2023), the public 3-D spherical-shell ASPECT/CitcomS convection
  benchmark, [DOI 10.7294/22803335](https://doi.org/10.7294/22803335). Its separate
  ASPECT archive is 7.50 GB, with verified download URL and MD5. Internal volume
  file paths and conversion of this archive remain unverified here because the
  file download returned HTTP 403.

The converter handles VTU/PVTU volumes and PVD time sequences with physical
radii and available times, including volume fields for the viewer's Mollweide
map and longitude-average calculator. It requires `requirements-aspect.txt`.
