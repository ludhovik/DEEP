#!/usr/bin/env python3
"""Convert ASPECT 3-D spherical-shell VTU/PVTU/PVD output to DEEPscope.

Coordinates and field values retain source units. No dynamo nondimensional
parameters or magnetic fields are invented for a mantle-convection model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

import numpy as np

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.aspect_data import (discover_snapshots, read_mesh, mesh_arrays, mesh_time,
                               radial_bounds, referenced_file, sample_shell, vtk_modules)
from tools.conversion_cache import run_conversion
from tools.scalar_diagnostics import dtheta_phi_average, dz_up_phi_average, scalar_diagnostic_metadata
from tools.viewer_bundle import write_f32

VERSION = '1.0.0'


def build_arg_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, help='One .vtu/.pvtu volume or solution.pvd time collection.')
    p.add_argument('--out', default='public/data_aspect')
    select = p.add_mutually_exclusive_group()
    select.add_argument('--frame', type=int, default=-1, help='Zero-based PVD frame index; default -1 (last).')
    select.add_argument('--all-frames', action='store_true', help='Convert the complete PVD collection to a viewer sequence.')
    p.add_argument('--frame-step', type=int, default=1, help='Stride for --all-frames.')
    p.add_argument('--inspect', action='store_true', help='List frames, arrays and radial bounds, without writing a bundle.')
    p.add_argument('--nr', type=int, default=64)
    p.add_argument('--ntheta', type=int, default=96)
    p.add_argument('--nphi', type=int, default=192)
    p.add_argument('--r-inner', type=float, help='Inner sampling radius in source length units; default minimum node radius.')
    p.add_argument('--r-outer', type=float, help='Outer sampling radius in source length units; default maximum node radius.')
    p.add_argument('--center', type=float, nargs=3, default=[0., 0., 0.], metavar=('X','Y','Z'))
    p.add_argument('--boundary-tolerance', type=float, default=0.002,
                   help='Maximum endpoint projection distance as a fraction of ro (default 0.002). Interior gaps always fail.')
    p.add_argument('--temperature-field', help='VTK scalar mapped to T; automatic only for T or Temperature.')
    p.add_argument('--velocity-field', default='velocity', help='Cartesian 3-component velocity array; optional if absent.')
    p.add_argument('--composition-field', help='VTK scalar mapped to C (e.g. pyrolite); never guessed from unnamed tracers.')
    p.add_argument('--output', dest='selected_fields', nargs='+', metavar='FIELD', help='Export only these viewer fields, including named scalar arrays. Omit to export all scalars and available diagnostics.')
    p.add_argument('--no-gradients', action='store_true', help='Skip gradients, mean derivatives and advection.')
    p.add_argument('--no-m0-fields', action='store_true', help='Skip longitude means/fluctuations and their derivatives.')
    p.add_argument('--time', type=float, help='Explicit time for a single VTU/PVTU; PVD times take precedence.')
    p.add_argument('--time-units', default='native ASPECT output units (unspecified)')
    p.add_argument('--length-units', default='native length units')
    p.add_argument('--velocity-units', default='native velocity units')
    p.add_argument('--title', default='ASPECT mantle convection')
    p.add_argument('--inner-boundary-label', default='CMB', help='Name of the inner surface; use Inner mantle boundary for a truncated mantle.')
    p.add_argument('--source-url', help='Publication/data DOI or URL recorded in the bundle.')
    p.add_argument('--incremental', action='store_true', help='Skip an unchanged, checksum-verified complete conversion.')
    p.add_argument('--cache-dir', help='Shared converter cache location, outside public/ and the output directory.')
    p.add_argument('--force', action='store_true', help='Rebuild even with --incremental.')
    return p


def scalar_mappings(arrays, args):
    temperature = args.temperature_field
    if temperature is None:
        temperature = next((name for name in ('T', 'Temperature') if arrays.get(name) == 1), None)
    mapping = {}
    for canonical, source in [('T', temperature), ('C', args.composition_field)]:
        if source is not None:
            if arrays.get(source) != 1:
                raise ValueError(f'{canonical} requires a scalar array named {source!r}. Available arrays: {arrays}')
            if source in mapping.values():
                raise ValueError('Temperature and composition must use different source arrays.')
            mapping[canonical] = source
    for source, components in arrays.items():
        if components != 1 or source in mapping.values() or source in ('vtkGhostType', 'vtkValidPointMask'):
            continue
        name = 'P' if source == 'p' else re.sub('[^A-Za-z0-9_]', '_', source)
        if not name or not name[0].isalpha():
            name = 'scalar_' + name
        if name in mapping:
            raise ValueError(f'Conflicting scalar export name {name!r}; rename the source array.')
        mapping[name] = source
    return mapping


def spherical_velocity(values, theta, phi):
    th, ph = theta[None, :, None], phi[None, None, :]
    ux, uy, uz = np.moveaxis(values, -1, 0)
    return (ux*np.sin(th)*np.cos(ph) + uy*np.sin(th)*np.sin(ph) + uz*np.cos(th),
            ux*np.cos(th)*np.cos(ph) + uy*np.cos(th)*np.sin(ph) - uz*np.sin(th),
            -ux*np.sin(ph) + uy*np.cos(ph))


def scalar_gradient(values, r, theta, phi):
    # Midpoint colatitudes avoid the coordinate singularities at the poles;
    # the longitude stencil is periodic (no duplicated 2pi seam).
    gr = np.gradient(values, r, axis=0, edge_order=2)
    gt = np.gradient(values, theta, axis=1, edge_order=2) / r[:, None, None]
    gp = (np.roll(values, -1, axis=2) - np.roll(values, 1, axis=2)) / (2*(phi[1]-phi[0]))
    gp /= r[:, None, None] * np.sin(theta)[None, :, None]
    return gr, gt, gp


def field_products(raw, r, theta, phi, args):
    yield from raw.items()
    if all(name in raw for name in ('ur','ut','up')):
        yield 'Uabs', np.sqrt(sum(raw[name]**2 for name in ('ur','ut','up')))
        yield 'us', raw['ur']*np.sin(theta)[None,:,None] + raw['ut']*np.cos(theta)[None,:,None]
        yield 'uz', raw['ur']*np.cos(theta)[None,:,None] - raw['ut']*np.sin(theta)[None,:,None]
    for scalar in ('T','C'):
        if scalar not in raw:
            continue
        value = raw[scalar]
        # Angular cell areas give a spherical-surface mean at each radius.
        edges = np.linspace(0, np.pi, len(theta)+1)
        weights = (np.cos(edges[:-1])-np.cos(edges[1:])) / 2
        radial_mean = np.einsum('rt,t->r', value.mean(axis=2), weights)
        yield scalar + '_anomaly', value - radial_mean[:,None,None]
        if not args.no_gradients:
            gradients = scalar_gradient(value, r, theta, phi)
            for axis, gradient in zip(('r','theta','phi'), gradients):
                yield f'grad_{axis}{scalar}', gradient
            gr, gt, _ = gradients
            yield f'grad_s{scalar}', gr*np.sin(theta)[None,:,None] + gt*np.cos(theta)[None,:,None]
            yield f'grad_z{scalar}', gr*np.cos(theta)[None,:,None] - gt*np.sin(theta)[None,:,None]
            if all(name in raw for name in ('ur','ut','up')):
                yield f'adv{scalar}', sum(raw[name]*gradient for name,gradient in zip(('ur','ut','up'),gradients))
            if not args.no_m0_fields:
                yield f'dtheta{scalar}_phiavg', dtheta_phi_average(value,r,theta,phi)
    if not args.no_m0_fields:
        for name in ('T','C','ur','ut','up'):
            if name in raw:
                mean = raw[name].mean(axis=2,keepdims=True)
                yield name + '_phiavg', np.broadcast_to(mean, raw[name].shape)
                yield name + '_nom0', raw[name]-mean
        if not args.no_gradients and 'up' in raw:
            yield 'dzup_phiavg', dz_up_phi_average(raw['up'],r,theta,phi)


def json_write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def convert_snapshot(snapshot, destination, args, coordinates=None):
    grid, promoted = read_mesh(snapshot.path)
    arrays = mesh_arrays(grid)
    mapping = scalar_mappings(arrays, args)
    names = list(mapping.values())
    velocity = args.velocity_field if args.velocity_field in arrays else None
    if velocity and arrays[velocity] != 3:
        raise ValueError('Velocity must contain three Cartesian components.')
    if velocity:
        names.append(velocity)
    if not names:
        raise ValueError('No usable scalar or velocity arrays in this volume.')
    if coordinates is None:
        ri, ro = radial_bounds(grid, np.asarray(args.center))
        ri = ri if args.r_inner is None else args.r_inner
        ro = ro if args.r_outer is None else args.r_outer
        if not np.isfinite([ri,ro]).all() or not 0 < ri < ro:
            raise ValueError('Mantle sampling requires 0 < r-inner < r-outer; choose a spherical shell, not a full ball.')
        r = np.linspace(ri,ro,args.nr)
        theta = (np.arange(args.ntheta)+0.5) * np.pi/args.ntheta
        phi = np.arange(args.nphi) * 2*np.pi/args.nphi
        coordinates = {'r':r.tolist(),'theta':theta.tolist(),'phi':phi.tolist()}
    r, theta, phi = (np.asarray(coordinates[key]) for key in ('r','theta','phi'))
    print(f'Sampling {snapshot.path.name}: {len(r)} x {len(theta)} x {len(phi)}...', flush=True)
    values, interpolation = sample_shell(grid,r,theta,phi,names,args.center,args.boundary_tolerance)
    raw = {name:values[source] for name,source in mapping.items()}
    if velocity:
        if set(raw) & {'ur','ut','up'}:
            raise ValueError('Source scalar names collide with spherical velocity components.')
        raw.update(zip(('ur','ut','up'),spherical_velocity(values[velocity],theta,phi)))
    destination = Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    fields, ranges, available = {}, {}, set()
    selected = set(args.selected_fields) if args.selected_fields else None
    for name, value in field_products(raw,r,theta,phi,args):
        if name in available:
            raise ValueError(f'Source array collides with generated diagnostic {name!r}.')
        available.add(name)
        if selected is not None and name not in selected:
            continue
        file = f'{name}_volume.f32'
        ranges[name] = write_f32(destination/file,value)
        fields[name] = file
    if selected is not None and selected - available:
        raise ValueError('Unavailable --output fields: '+', '.join(sorted(selected-available))+'. Available: '+', '.join(sorted(available)))
    time = snapshot.time if snapshot.time is not None else args.time
    time_source = 'PVD timestep' if snapshot.time is not None else ('--time' if args.time is not None else 'VTK field data')
    if time is None:
        time = mesh_time(grid)
    meta = dict(source_code='ASPECT',title=args.title,converter_version=VERSION,
        description='3-D mantle shell sampled from ASPECT-compatible VTK cells; source units retained.',
        source_file=str(snapshot.path),source_url=args.source_url,time=time,time_source=time_source if time is not None else 'unavailable',
        time_units=args.time_units,length_units=args.length_units,velocity_units=args.velocity_units,
        scalar_naming_version=2,nr=len(r),ntheta=len(theta),nphi=len(phi),r_inner=float(r[0]),r_outer=float(r[-1]),
        r_icb=float(r[0]),icb_index=0,has_inner_core=True,full_sphere=False,
        physical_geometry='mantle_spherical_shell',boundary_labels={'inner':args.inner_boundary_label,'outer':'Surface'},
        inner_core={'available':False},magnetic={'has_magnetic_field':False,'classification':'mantle_convection'},
        layout='r_theta_phi',endianness='little',coordinates='coordinates.json',fields=fields,ranges=ranges,
        surface_fields={},field_lines={},output_selection=args.selected_fields,
        source_arrays=mapping,velocity_array=velocity,cartesian_center=args.center,
        cell_arrays_averaged_to_points=promoted,interpolation=interpolation,
        scalar_diagnostics=scalar_diagnostic_metadata(fields),
        field_domains={name:{'r_min':float(r[0]),'r_max':float(r[-1]),'source':'mantle'} for name in fields})
    meta['scalar_diagnostics']['sampling'] = 'Finite differences on resampled physical-radius grid; periodic longitude; midpoint colatitudes. Mesh interpolation and grid resolution affect derivatives.'
    meta['scalar_diagnostics']['units'] = 'Source units retained: dtheta scalar/radian, dzup velocity/length, advection velocity*scalar/length. No conversion between seconds and years.'
    meta['scalar_diagnostics']['anomaly'] = 'T_anomaly/C_anomaly subtract the area-weighted spherical-surface mean independently at each radius; not the longitude mean.'
    json_write(destination/'coordinates.json',coordinates)
    json_write(destination/'metadata.json',meta)
    return meta, coordinates


def convert_frames(args, frames):
    root = Path(args.out)
    if not args.all_frames:
        convert_snapshot(frames[0],root,args)
        return
    entries, coordinates, first_fields = [], None, None
    for index, snapshot in enumerate(frames):
        folder = f'frames/frame{index:05d}'
        meta, coordinates = convert_snapshot(snapshot,root/folder,args,coordinates)
        if first_fields is None:
            first_fields = set(meta['fields'])
            for file in (root/folder).iterdir():
                shutil.copy2(file,root/file.name)
        elif set(meta['fields']) != first_fields:
            raise ValueError('Sequence field arrays change between frames; use --output to choose a shared set.')
        entries.append({'path':folder,'metadata':folder+'/metadata.json','time':meta['time'],
                        'label':snapshot.path.stem})
    json_write(root/'sequence.json',{'version':1,'frame_count':len(entries),'frames':entries,'time_units':args.time_units})


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    if min(args.nr,args.ntheta) < 3 or args.nphi < 4:
        raise ValueError('Use nr >= 3, ntheta >= 3 and nphi >= 4.')
    if args.frame_step < 1 or not np.isfinite(args.center).all():
        raise ValueError('Frame stride must be positive and center coordinates finite.')
    if not np.isfinite(args.boundary_tolerance) or args.boundary_tolerance < 0:
        raise ValueError('--boundary-tolerance must be finite and nonnegative.')
    if args.time is not None and (not np.isfinite(args.time) or Path(args.input).suffix.lower() == '.pvd'):
        raise ValueError('--time must be finite and is only for a single VTU/PVTU; PVD supplies its own times.')
    snapshots = discover_snapshots(args.input)
    if args.inspect:
        print('Frames:')
        for i,s in enumerate(snapshots):
            print(f'  {i}: t={s.time} {s.path}')
        grid, promoted = read_mesh(snapshots[args.frame].path)
        print('Arrays:',json.dumps(mesh_arrays(grid),indent=2))
        print('Node radial bounds:',radial_bounds(grid,np.asarray(args.center)))
        print('Cell arrays averaged to points:',promoted)
        return
    try:
        frames = snapshots[::args.frame_step] if args.all_frames else [snapshots[args.frame]]
    except IndexError as exc:
        raise ValueError(f'Frame index {args.frame} outside {len(snapshots)} available frames.') from exc
    inputs = {Path(args.input).resolve()}
    for s in frames:
        inputs.add(s.path)
        if s.path.suffix.lower() == '.pvtu':
            for piece in ET.parse(s.path).getroot().findall('./PUnstructuredGrid/Piece'):
                inputs.add(referenced_file(s.path.parent,piece.get('Source')))
    vtk, _, _ = vtk_modules()
    args.vtk_version = vtk.vtkVersion.GetVTKVersion()
    run_conversion(args,'aspect',sorted(inputs),lambda current:convert_frames(current,frames))


if __name__ == '__main__':
    main()
