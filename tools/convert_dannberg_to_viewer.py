#!/usr/bin/env python3
"""Convert Dannberg et al. (2024) CMB heat-flux SH coefficients to surface maps.

Dataset: https://doi.org/10.5281/zenodo.10642097 (CC BY 4.0).
No mantle volume, temperature, or velocity is reconstructed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.conversion_cache import run_conversion
from tools.viewer_bundle import write_f32

SOURCE = 'https://doi.org/10.5281/zenodo.10642097'
PAPER = 'https://doi.org/10.1093/gji/ggae075'
PATTERN = re.compile(r'heat_flux_sph\.(\d+)\.cdf\.dat$')


def discover(path):
    path = Path(path)
    files = list(path.rglob('heat_flux_sph.*.cdf.dat')) if path.is_dir() else [path]
    files = [p for p in files if p.is_file() and PATTERN.fullmatch(p.name)]
    files.sort(key=lambda p: int(PATTERN.fullmatch(p.name)[1]))
    if not files:
        raise ValueError('No heat_flux_sph.NNNNN.cdf.dat files found. Extract one sph_*.tar.gz archive first.')
    steps = [int(PATTERN.fullmatch(p.name)[1]) for p in files]
    if len(set(steps)) != len(steps):
        raise ValueError('Duplicate solver steps: point --input at one model, not several models.')
    return files


def expand_surface(coeffs, lmax, longitude, sign):
    if not 1 <= lmax <= coeffs.lmax:
        raise ValueError(f'--lmax must be between 1 and source degree {coeffs.lmax}.')
    if coeffs.kind != 'real':
        raise ValueError('Expected real heat-flux coefficients.')
    # DH2 uses uniform colatitude/longitude. No duplicated 360-degree seam.
    grid = coeffs.expand(grid='DH2', lmax=lmax, lmax_calc=lmax, extend=False)
    values = np.asarray(grid.data, dtype=float)
    if longitude == 'geographic':
        # The archived processing script used 180 + atan2(y,x).
        # q_geo(phi) = q_archive(phi + 180 degrees).
        values = np.roll(values, -values.shape[1] // 2, axis=1)
    if sign == 'out-of-core':
        # ASPECT bottom outward normal points into the core.
        values = -values
    if not np.isfinite(values).all():
        raise ValueError('Non-finite reconstructed heat flux.')
    theta = np.deg2rad(90 - grid.lats())
    phi = np.deg2rad(grid.lons())
    # The degree-zero coefficient is the exact spherical average in 4pi norm.
    mean = float(coeffs.to_array(normalization='4pi', csphase=1)[0, 0, 0])
    if sign == 'out-of-core':
        mean = -mean
    return values, theta, phi, mean


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def convert_one(path, out, args, age):
    import pyshtools as pysh
    # from_netcdf reads normalization and csphase from the archive attributes.
    coeffs = pysh.SHCoeffs.from_netcdf(str(path))
    if coeffs.normalization != 'schmidt' or coeffs.csphase != -1:
        raise ValueError('Unexpected coefficient convention for this dataset; expected schmidt, csphase=-1.')
    values, theta, phi, mean = expand_surface(coeffs, args.lmax, args.longitude, args.sign)
    out.mkdir(parents=True, exist_ok=True)
    surface_fields, ranges = {}, {}
    for name, data in [('q_CMB', values), ('q_CMB_anomaly', values - mean)]:
        filename = f'{name}_cmb.f32'
        ranges[name] = write_f32(out / filename, data)
        surface_fields[name] = {'file': filename, 'surface': 'cmb', 'radius': args.radius,
                                'units': 'W m^-2'}
    # The existing viewer coordinate schema needs two radial bounds. These are
    # display geometry only: fields={} and surface_only=True prevent volume use.
    coordinates = {'r': [0., args.radius], 'theta': theta.tolist(), 'phi': phi.tolist()}
    meta = dict(source_code='ASPECT', title=args.title, converter_version='1.0.0',
        description='CMB heat-flux surface only; no mantle volume fields.',
        source_url=SOURCE, paper_url=PAPER, license='CC-BY-4.0',
        attribution='Dannberg, Gassmöller, Thallner, LaCombe & Sprain (2024)',
        source_file=str(path.resolve()), source_step=int(PATTERN.fullmatch(path.name)[1]),
        time=age, time_units='Ma before present (nominal)',
        time_source='Archive 1 Myr schedule, 1000 to 0 Ma; not exact solver times' if age is not None else 'unavailable',
        surface_only=True, physical_geometry='cmb_surface', nr=2,
        ntheta=len(theta), nphi=len(phi), r_inner=0., r_outer=args.radius,
        has_inner_core=False, full_sphere=True, length_units='m',
        boundary_labels={'outer': 'CMB'}, inner_core={'available': False},
        magnetic={'has_magnetic_field': False, 'classification': 'heat_flux_surface'},
        layout='theta_phi', endianness='little', coordinates='coordinates.json',
        fields={}, surface_fields=surface_fields, ranges=ranges, field_lines={},
        heat_flux={'units': 'W m^-2', 'sign': args.sign, 'longitude': args.longitude,
            'mean': mean, 'lmax': args.lmax, 'source_lmax': int(coeffs.lmax),
            'normalization': coeffs.normalization, 'csphase': int(coeffs.csphase),
            'anomaly': 'q_CMB minus exact spherical mean (degree zero).',
            'source_processing': 'SPH_scripts/analyze_heatflux_mpi_gmt.py in Zenodo archive',
            'radial_coordinates': 'Display bounds only; data exist exclusively at r_outer.'})
    write_json(out / 'coordinates.json', coordinates)
    write_json(out / 'metadata.json', meta)
    return meta


def convert(args, selected):
    out = Path(args.out)
    entries = []
    for index, (path, age) in enumerate(selected):
        destination = out / f'frames/frame{index:05d}' if args.all_frames else out
        print(f'{index + 1}/{len(selected)}: {path.name}, nominal age={age}', flush=True)
        meta = convert_one(path, destination, args, age)
        if args.all_frames:
            if index == 0:
                for file in destination.iterdir():
                    shutil.copy2(file, out / file.name)
            folder = destination.relative_to(out).as_posix()
            entries.append({'path': folder, 'metadata': folder + '/metadata.json',
                            'time': age, 'label': f'{age:g} Ma' if age is not None else path.name})
    if args.all_frames:
        write_json(out / 'sequence.json', {'version': 1, 'frame_count': len(entries),
            'frames': entries, 'time_units': meta['time_units'], 'time_source': meta['time_source']})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, help='Extracted folder for ONE model, or one coefficient file.')
    p.add_argument('--out', default='public/data_aspect_dannberg')
    select = p.add_mutually_exclusive_group()
    select.add_argument('--frame', type=int, default=-1, help='Sorted frame index; default last.')
    select.add_argument('--all-frames', action='store_true')
    p.add_argument('--frame-step', type=int, default=1)
    p.add_argument('--nominal-age-schedule', action='store_true',
        help='Assign 1000..0 Ma to the COMPLETE 1001-file model archive before applying frame stride.')
    p.add_argument('--inspect', action='store_true')
    p.add_argument('--lmax', type=int, default=128, help='SH truncation; use 256 to retain the full archive bandwidth.')
    p.add_argument('--radius', type=float, default=3481000.)
    p.add_argument('--longitude', choices=['geographic', 'archive'], default='geographic')
    p.add_argument('--sign', choices=['out-of-core', 'archive'], default='out-of-core')
    p.add_argument('--title', default='Dannberg et al. 2024 — CMB heat flux')
    p.add_argument('--incremental', action='store_true')
    p.add_argument('--cache-dir')
    p.add_argument('--force', action='store_true')
    args = p.parse_args(argv)
    files = discover(args.input)
    if args.frame_step < 1 or args.lmax < 1 or not np.isfinite(args.radius) or args.radius <= 0:
        p.error('Require positive frame stride, lmax and finite radius.')
    if args.nominal_age_schedule and len(files) != 1001:
        p.error(f'Nominal age mapping requires all 1001 source frames; found {len(files)}. '
                'Omit --nominal-age-schedule to export with unknown times.')
    selected = [(file, float(1000 - i) if args.nominal_age_schedule else None)
                for i, file in enumerate(files)]
    if args.inspect:
        print(f'{len(files)} frames; first={files[0]}; last={files[-1]}')
        print('File numbers are solver steps, NOT times. Nominal schedule:', args.nominal_age_schedule)
        return
    try:
        selected = selected[::args.frame_step] if args.all_frames else [selected[args.frame]]
    except IndexError:
        p.error(f'Frame index outside {len(files)} available files.')
    run_conversion(args, 'dannberg', files, lambda current: convert(current, selected))


if __name__ == '__main__':
    main()
