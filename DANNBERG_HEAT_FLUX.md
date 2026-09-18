# Dannberg et al. (2024): CMB heat-flux maps

Dataset: https://doi.org/10.5281/zenodo.10642097 (CC BY 4.0).
Paper: https://doi.org/10.1093/gji/ggae075.
Credit: Juliane Dannberg, Rene Gassmöller, Daniele Thallner,
Frederick LaCombe and Courtney Sprain (2024).

This importer reads the published spherical-harmonic heat-flux coefficients.
It does **not** recreate temperature, velocity or subducted slabs inside the
mantle. Use `convert_aspect_to_viewer.py` for actual VTU/PVTU volume output.
The viewer must include the surface-only dataset update accompanying this script.

## Download and extract the thermochemical example

The complete download is 3.54 GB. Extract only the desired heat-flux archive
to avoid unpacking two complete ASPECT source distributions. Allow roughly
5 GB total space for the ZIP, selected compressed archive and extracted inputs,
plus converted output.

```bash
ASPECT_DATA="$HOME/Downloads/aspect-dannberg2024"
mkdir -p "$ASPECT_DATA"
curl -fL --retry 3 -C - \
  "https://zenodo.org/records/10642097/files/data_package.zip?download=1" \
  -o "$ASPECT_DATA/data_package.zip"

printf '%s  %s\n' '405f180937bb89058aacf0f4e584c790' \
  "$ASPECT_DATA/data_package.zip" | md5sum -c -

unzip -n "$ASPECT_DATA/data_package.zip" \
  'heat_flux/sph_thermochemical.tar.gz' -d "$ASPECT_DATA"
mkdir -p "$ASPECT_DATA/thermochemical"
tar -xzf "$ASPECT_DATA/heat_flux/sph_thermochemical.tar.gz" \
  -C "$ASPECT_DATA/thermochemical"
```

Other available model names are `thermal`, `p_T_dependent`, `strong_basalt`,
`weak_ppv` and `CMB_3300K`. Extract each into its own directory. Do not combine
models with identical coefficient filenames.

## Convert from the DEEP checkout

```bash
python3 -m pip install -r requirements-dannberg.txt

python3 tools/convert_dannberg_to_viewer.py \
  --input "$ASPECT_DATA/thermochemical" --inspect

# Last frame (nominal present day), first try:
python3 tools/convert_dannberg_to_viewer.py \
  --input "$ASPECT_DATA/thermochemical" \
  --out "/mnt/c/Users/wgdh881/Desktop/public/data_aspect_dannberg_present" \
  --frame -1 --nominal-age-schedule --lmax 128 \
  --title "Dannberg 2024 — thermochemical CMB heat flux" \
  --incremental --cache-dir "$HOME/.cache/deepscope"

# Sequence, keeping one frame every 10 Myr:
python3 tools/convert_dannberg_to_viewer.py \
  --input "$ASPECT_DATA/thermochemical" \
  --out "/mnt/c/Users/wgdh881/Desktop/public/data_aspect_dannberg_sequence" \
  --all-frames --frame-step 10 --nominal-age-schedule --lmax 128 \
  --title "Dannberg 2024 — thermochemical CMB heat flux" \
  --incremental --cache-dir "$HOME/.cache/deepscope"
```

Use `--frame-step 1` for every published frame. Use `--lmax 256` to retain
the archived spectral bandwidth; 128 reduces resolution and file size.
At lmax 128 each frame contains two 258 x 516 float32 surface maps (~1.1 MB).

## Meaning of the exported fields

- `q_CMB`: W/m², positive **out of the core into the mantle** by default.
- `q_CMB_anomaly`: q_CMB minus its exact spherical mean (degree zero).
- `--sign archive` retains the original ASPECT bottom-boundary outward-normal
  convention, which is negative for heat entering the mantle from the core.
- `--longitude geographic` (default) undoes the 180-degree longitude shift in
  the archived `SPH_scripts/analyze_heatflux_mpi_gmt.py`; `--longitude archive`
  retains the authors' stored longitude coordinate.
- Schmidt normalization and Condon–Shortley phase -1 are read from the NetCDF
  metadata and preserved during synthesis by pyshtools.
- CMB radius is 3,481,000 m. The viewer normalizes display coordinates. The
  two radial coordinates required by the bundle schema are display bounds;
  **no volume field is written or implied**.

Filenames contain **solver step numbers**, not times. The source description
specifies a 1 Myr output schedule from model start to present day. The optional
`--nominal-age-schedule` assigns 1000 down to 0 Ma before present to the ordered
1001 files **before** applying the frame stride. It requires the complete
model archive and labels times as nominal, not exact solver output times.
Without this flag the time is unknown. Do not rename or remove frames before
applying the nominal schedule.

Open the converted output folder in the updated viewer. The CMB sphere and
Mollweide map open automatically. Select either field in their controls.
Volume cuts and isosurfaces are unavailable for these surface-only data.
The map participates in sequence preloading; the time overlay uses the
nominal-age metadata and can be included in PNG/PDF/video exports.

Validation: two real thermochemical coefficient files (solver steps 00000 and
00008), analytic degree-one sign/longitude/phase check, surface-only bundle and
sequence checks, viewer loader and preload regression test. The complete
1001-frame archive was not converted during development.
