#!/usr/bin/env python3
"""Convert legacy 3-D StagYY Yin–Yang mantle snapshots to DEEP volumes."""
from pathlib import Path
import argparse
import shutil
import sys

import numpy as np

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.stagyy_data import companion_files, read_header, read_volume, patch_axes, YinYangSampler
from tools.convert_aspect_to_viewer import field_products, json_write
from tools.conversion_cache import run_conversion
from tools.scalar_diagnostics import scalar_diagnostic_metadata
from tools.viewer_bundle import write_f32

VERSION = '1.1.0'


def build_arg_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,nargs='+',help='STEM_tNNNNN temperature files. Multiple inputs produce a sequence sorted by saved time.')
    p.add_argument('--out',default='public/data_stagyy')
    p.add_argument('--inspect',action='store_true',help='Validate headers and list fields, time and geometry without converting.')
    p.add_argument('--nr',type=int,help='Regular radial resolution; default preserves all native, nonuniform radial centres.')
    p.add_argument('--ntheta',type=int,default=128)
    p.add_argument('--nphi',type=int,default=256)
    p.add_argument('--no-velocity',action='store_true',help='Ignore matching STEM_vpNNNNN (velocity and pressure).')
    p.add_argument('--no-viscosity',action='store_true',help='Ignore matching STEM_etaNNNNN.')
    p.add_argument('--composition-suffix',help='Explicit scalar suffix mapped to C, e.g. c for STEM_cNNNNN; never inferred from tracers.')
    p.add_argument('--output',dest='selected_fields',nargs='+',help='Only export these fields, e.g. T T_anomaly log10_eta ur advT.')
    p.add_argument('--no-gradients',action='store_true')
    p.add_argument('--no-m0-fields',action='store_true')
    p.add_argument('--title',default='StagYY 3-D mantle convection')
    p.add_argument('--source-url',help='Publication or dataset URL saved in metadata.')
    p.add_argument('--time-units',default='native StagYY time units')
    p.add_argument('--length-units',default='native StagYY length units')
    p.add_argument('--velocity-units',default='native StagYY velocity units')
    p.add_argument('--incremental',action='store_true')
    p.add_argument('--cache-dir')
    p.add_argument('--force',action='store_true')
    return p


def convert_snapshot(files, destination, args, coordinates=None):
    h,temperature = read_volume(files['T'])
    native_r = patch_axes(h)[2]
    if coordinates is None:
        r = native_r if args.nr is None else np.linspace(native_r[0],native_r[-1],args.nr)
        theta = (np.arange(args.ntheta)+.5)*np.pi/args.ntheta
        phi = np.arange(args.nphi)*2*np.pi/args.nphi
        coordinates = dict(r=r.tolist(),theta=theta.tolist(),phi=phi.tolist())
    r,theta,phi = (np.asarray(coordinates[key]) for key in ('r','theta','phi'))
    sampler = YinYangSampler(h,r,theta,phi)
    print(f"Sampling {files['T'].name}: {len(r)} x {len(theta)} x {len(phi)}, t={float(h['ti_ad']):.9g}",flush=True)
    raw = {'T':sampler.sample(temperature[0])}
    del temperature
    for name in ('eta','C'):
        if name in files:
            _,values = read_volume(files[name],h)
            if name == 'eta':
                if np.any(values <= 0):
                    raise ValueError('Viscosity must be positive for logarithmic interpolation.')
                raw['log10_eta'] = sampler.sample(np.log10(values[0]))
                raw['eta'] = 10.**raw['log10_eta']
            else:
                raw[name] = sampler.sample(values[0])
            del values
    if 'vp' in files:
        _,values = read_volume(files['vp'],h,components=4)
        raw.update(sampler.velocity(values))
        raw['P'] = sampler.sample(values[3])
        del values
    destination = Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    selected = set(args.selected_fields) if args.selected_fields else None
    available,fields,ranges = set(),{},{}
    for name,value in field_products(raw,r,theta,phi,args):
        available.add(name)
        if selected is not None and name not in selected:
            continue
        fields[name] = f'{name}_volume.f32'
        ranges[name] = write_f32(destination/fields[name],value)
    if selected is not None and selected-available:
        raise ValueError('Unavailable --output fields: '+', '.join(sorted(selected-available))+'. Available: '+', '.join(sorted(available)))
    ri,ro = float(r[0]),float(r[-1])
    meta = dict(source_code='StagYY',title=args.title,converter_version=VERSION,
        description='3-D legacy Yin–Yang mantle volume; native units; sampled only between saved radial cell centres.',
        source_files={k:str(v) for k,v in files.items()},source_url=args.source_url,
        time=float(h['ti_ad']),time_source='StagYY binary header ti_ad',time_step=int(h['ti_step']),
        time_units=args.time_units,length_units=args.length_units,velocity_units=args.velocity_units,
        scalar_naming_version=2,nr=len(r),ntheta=len(theta),nphi=len(phi),r_inner=ri,r_outer=ro,
        r_icb=ri,icb_index=0,has_inner_core=True,full_sphere=False,physical_geometry='mantle_spherical_shell',
        boundary_labels={'inner':'Near CMB','outer':'Near surface'},inner_core={'available':False},
        magnetic={'has_magnetic_field':False,'classification':'mantle_convection'},
        layout='r_theta_phi',endianness='little',coordinates='coordinates.json',fields=fields,ranges=ranges,
        surface_fields={},field_lines={},output_selection=args.selected_fields,
        source_grid={'type':'Yin–Yang','shape':[int(n) for n in h['nts']]+[int(h['ntb'])],
                     'cmb_radius':float(h['rcmb']),
                     'boundary_radii':(h['rgeom'][:,0][[0,-1]].astype(float)+float(h['rcmb'])).tolist()},
        interpolation={'method':'remove redundant Yin–Yang corners; convex-hull angular triangles with barycentric interpolation; linear interpolation in native radius',
                       'retained_angular_nodes_per_patch':int(sampler.active.sum()),
                       'discarded_angular_nodes_per_patch':int((~sampler.active).sum()),
                       'reference':'https://github.com/auguryerc/ReadStagYY/blob/fa7969ade79817fcac255cd9d6a9864eaec25873/WriteStag3D_VTK_YinYang_LB.m',
                       'vectors':'legacy header samples; trim redundant high-side vp rows; rotate to Cartesian before interpolation on the stitched angular mesh',
                       'viscosity':'linear interpolation of log10(eta); eta reconstructed from interpolated log10_eta',
                       'radial_boundaries':'first/last saved cell centres; no extrapolation to physical walls'},
        field_domains={name:{'r_min':ri,'r_max':ro,'source':'mantle'} for name in fields},
        scalar_diagnostics=scalar_diagnostic_metadata(fields))
    meta['scalar_diagnostics'].update(
        sampling='Finite differences on the resampled volume; periodic longitude; midpoint colatitudes. Derivatives and advection are visualization diagnostics, not the native solver discretization.',
        units='Native units: dtheta scalar/radian; dzup velocity/length; advT or advC velocity*scalar/length.',
        anomaly='T_anomaly/C_anomaly subtract the area-weighted spherical-surface mean at each radius.')
    json_write(destination/'coordinates.json',coordinates)
    json_write(destination/'metadata.json',meta)
    return meta,coordinates


def convert_frames(args, frames):
    root = Path(args.out)
    if len(frames) == 1:
        convert_snapshot(frames[0],root,args)
        return
    entries,coordinates,first_fields = [],None,None
    for i,files in enumerate(frames):
        folder = f'frames/frame{i:05d}'
        meta,coordinates = convert_snapshot(files,root/folder,args,coordinates)
        if first_fields is None:
            first_fields = set(meta['fields'])
            for file in (root/folder).iterdir():
                shutil.copy2(file,root/file.name)
        elif first_fields != set(meta['fields']):
            raise ValueError('Sequence fields differ; use --output to select a common field set.')
        entries.append(dict(path=folder,metadata=folder+'/metadata.json',time=meta['time'],label=files['T'].name))
    json_write(root/'sequence.json',dict(version=1,frame_count=len(entries),frames=entries,time_units=args.time_units))


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    if (args.nr is not None and args.nr < 3) or args.ntheta < 3 or args.nphi < 4:
        raise ValueError('Use nr >= 3, ntheta >= 3 and nphi >= 4.')
    frames = [companion_files(p,args.no_velocity,args.no_viscosity,args.composition_suffix) for p in args.input]
    if len({f['T'] for f in frames}) != len(frames):
        raise ValueError('Duplicate input snapshots.')
    frames.sort(key=lambda f:float(read_header(f['T'])['ti_ad']))
    for files in frames:
        h = read_header(files['T'])
        if min(h['nts']) < 3:
            raise ValueError('At least three source samples per direction are required.')
        if args.inspect:
            print(f"{files['T']}\n  grid={[int(n) for n in h['nts']]} x 2 blocks; t={float(h['ti_ad']):.9g}; timestep={int(h['ti_step'])}")
            print(f"  fields={list(files)}; sampled radii={patch_axes(h)[2][[0,-1]]}")
            for path in files.values():
                read_header(path)
    if args.inspect:
        return
    args.stagpy_version = '0.23.0'
    inputs = sorted({p for f in frames for p in f.values()})
    run_conversion(args,'stagyy',inputs,lambda current:convert_frames(current,frames))


if __name__ == '__main__':
    main()
