#!/usr/bin/env python3
"""Convert Rayleigh Spherical_3D fields or single-domain spectral checkpoints."""
from __future__ import annotations
try:
    from converter_parameters import resolve_graph_parameters
except ImportError:
    from tools.converter_parameters import resolve_graph_parameters

try:
    from output_selection import OutputSelection
except ImportError:
    from tools.output_selection import OutputSelection

import argparse
import copy
import json
import math
from pathlib import Path
import re
import shutil
import numpy as np
try:
    from rayleigh_data import (QUANTITIES, main_parameters, read_grid, read_reference,
        read_volume, read_coefficients, synthesize_checkpoint, radial_basis)
    from conversion_cache import run_conversion, cached_calculation
    from convert_magic_to_viewer import add_viewer_arguments, convert_adapted_snapshot
    from convert_leeds_to_viewer import choose_regular_seed_grid
    from spectral_truncation import cutoff_metadata, truncate_graphic_fields
    from viewer_bundle import bundle_path
except ImportError:
    from tools.rayleigh_data import (QUANTITIES, main_parameters, read_grid, read_reference,
        read_volume, read_coefficients, synthesize_checkpoint, radial_basis)
    from tools.conversion_cache import run_conversion, cached_calculation
    from tools.convert_magic_to_viewer import add_viewer_arguments, convert_adapted_snapshot
    from tools.convert_leeds_to_viewer import choose_regular_seed_grid
    from tools.spectral_truncation import cutoff_metadata, truncate_graphic_fields
    from tools.viewer_bundle import bundle_path

CONVERTER_PACKAGE_VERSION='1.0.0'


def build_arg_parser():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--state','--checkpoint','--snapshot',dest='state',help='Checkpoint directory (or grid_etc), or Spherical_3D/ITER_grid.')
    source.add_argument('--folder','-folder',help='Run, Checkpoints or Spherical_3D directory.')
    p.add_argument('--input-format',choices=['auto','checkpoint','spherical3d'],default='auto')
    p.add_argument('--state-number','--ivar',type=int)
    p.add_argument('--main-input',help='Optional explicit main_input; otherwise found next to the source.')
    p.add_argument('--time',type=float,help='Physical time for one Spherical_3D snapshot (not present in its binary header).')
    p.add_argument('--thermal-quantity',type=int,default=501,help='Spherical_3D thermal quantity code; default 501.')
    p.add_argument('--composition-quantity',type=int,help='Spherical_3D composition quantity code; never guessed.')
    p.add_argument('--composition-field',help='Checkpoint scalar filename, e.g. Xa001; never guessed.')
    p.add_argument('--constant-density',type=float,help='Explicit checkpoint reference density when equation_coefficients is absent.')
    p.add_argument('--n2-convention',choices=['none','deepscope'],default='none',help='Default omits N2; deepscope explicitly selects r*Ek^2*(RaT/Pr*T_r+RaC/Sc*C_r).')
    p.add_argument('--modules-dir',help='CLI compatibility; no external modules.py or Rayleigh Python installation is needed.')
    return add_viewer_arguments(p,'public/data_rayleigh')


def state_number(path):
    name=path.parent.name if path.name=='grid_etc' else path.name.split('_')[0]
    return int(name) if name.isdigit() else None


def discover_states(args):
    if args.state:
        path=Path(args.state).expanduser().resolve()
        if path.is_dir():path=path/'grid_etc'
        if not path.is_file():raise FileNotFoundError(path)
        if path.name!='grid_etc' and not re.fullmatch(r'\d+_grid',path.name):
            raise ValueError('Select an extracted checkpoint directory/grid_etc or Spherical_3D/ITER_grid, not an archive or a slice.')
        if args.sequence_first is not None or args.sequence_last is not None or args.state_number is not None:raise ValueError('Use --folder for numbered selection/sequences.')
        paths=[path]
    else:
        folder=Path(args.folder).expanduser().resolve()
        if not folder.is_dir():raise NotADirectoryError(folder)
        full=list(folder.glob('*_grid'))+list(folder.glob('Spherical_3D/*_grid'))
        checkpoints=list(folder.glob('*/grid_etc'))+list(folder.glob('Checkpoints/*/grid_etc'))
        if (folder/'grid_etc').is_file():checkpoints.append(folder/'grid_etc')
        full=[p for p in full if re.fullmatch(r'\d+_grid',p.name)]
        checkpoints=[p for p in checkpoints if state_number(p) is not None]
        if args.input_format=='auto' and full and checkpoints:raise ValueError('Both formats found; choose --input-format spherical3d or checkpoint.')
        paths=full if args.input_format=='spherical3d' or (args.input_format=='auto' and full) else checkpoints
        if not paths:raise ValueError('No supported Rayleigh snapshots found. Need *_grid with quantity files, or numbered Checkpoints directories.')
        found={}
        for path in paths:
            n=state_number(path)
            if n in found:raise ValueError(f'Duplicate snapshot index {n}; select --state explicitly.')
            found[n]=path
        first,last=args.sequence_first,args.sequence_last
        if first is not None or last is not None:
            if first is None or last is None or first>last or args.state_number is not None:raise ValueError('Specify sequence first <= last, without --state-number.')
            if args.time is not None:raise ValueError('--time applies to one snapshot; Spherical_3D sequences have unknown physical times.')
            selected=list(range(first,last+1,args.sequence_step))
        else:selected=[args.state_number if args.state_number is not None else max(found)]
        missing=[n for n in selected if n not in found]
        if missing:raise ValueError(f'Missing snapshot indices {missing[:10]}; use the output cadence for --sequence-step.')
        paths=[found[n] for n in selected]
    for path in paths:
        kind='checkpoint' if path.name=='grid_etc' else 'spherical3d'
        if args.input_format not in ('auto',kind):raise ValueError('--input-format conflicts with selected file.')
    return paths


def input_control(path,args):
    if args.main_input:
        p=Path(args.main_input).expanduser().resolve()
        if not p.is_file():raise FileNotFoundError(p)
        return p
    return next((p for p in (path.parent/'main_input',path.parent.parent/'main_input') if p.is_file()),None)


def field_paths(path,args):
    if path.name=='grid_etc':
        names={'ur':'W','utor':'Z','Br':'C','Btor':'A','T':'T','P':'P'}
        if args.composition_field:names['C']=args.composition_field
        result={k:path.parent/v for k,v in names.items() if (path.parent/v).is_file()}
        if args.composition_field and 'C' not in result:raise FileNotFoundError(path.parent/args.composition_field)
    else:
        prefix=path.name.split('_')[0];mapping=dict(QUANTITIES,T=args.thermal_quantity)
        if args.composition_quantity is not None:mapping['C']=args.composition_quantity
        files={}
        for f in path.parent.glob(prefix+'_*'):
            code=f.name[len(prefix)+1:]
            if code.isdigit():
                if int(code) in files:raise ValueError(f'Duplicate quantity code {code}.')
                files[int(code)]=f
        result={k:files[q] for k,q in mapping.items() if q in files}
        if args.composition_quantity is not None and 'C' not in result:raise ValueError('Requested composition quantity is missing.')
    groups=[('ur','utor'),('Br','Btor')] if path.name=='grid_etc' else [('ur','ut','up'),('Br','Bt','Bp')]
    for group in groups:
        if any(k in result for k in group) and not all(k in result for k in group):raise ValueError(f'Incomplete vector: need all {group}.')
    if not result:raise ValueError('No velocity, magnetic, thermal, pressure or selected composition fields found.')
    return result


def source_files(paths,args):
    files=set(paths)
    for path in paths:
        files.update(field_paths(path,args).values())
        control=input_control(path,args)
        if control:files.add(control)
        ref=path.parent/'equation_coefficients'
        if ref.is_file():files.add(ref)
    return sorted(files)


def convert_state(path,outdir,args):
    selection=OutputSelection(args)
    checkpoint=path.name=='grid_etc';grid=read_grid(path,checkpoint)
    control=input_control(path,args);native=main_parameters(control)
    files={k:v for k,v in field_paths(path,args).items() if selection.needs(k)};r=grid['r'];theta=grid['theta'];phi=grid['phi']
    fields={};info=None
    lmax=int(native.get('l_max',grid['lmax'])) if not checkpoint else grid['lmax']
    if checkpoint:
        if native.get('compressible') or native.get('pseudo_incompressible'):
            raise ValueError('Compressible/pseudo-incompressible checkpoints need Spherical_3D export; no density convention is guessed.')
        radial_basis(r) # reject multidomain/other radial layouts before allocating fields
        info=cutoff_metadata(args.spectral_lmax,lmax,lmax);leff=info['lmax_effective']
        nt=int(native.get('n_theta',len(theta)))
        if nt<=lmax:raise ValueError('main_input n_theta is inconsistent with checkpoint lmax.')
        original=[nt,2*nt]
        if info['enabled']:nt=min(nt,max(4,leff+2))
        theta=np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1]);phi=np.arange(2*nt)*math.pi/nt
        info.update(original_grid=original,output_grid=[nt,2*nt],method='native angular truncation before checkpoint synthesis')
        density=None
        if 'ur' in files:
            ref=path.parent/'equation_coefficients'
            if args.constant_density is not None:density=np.full(len(r),args.constant_density)
            elif ref.is_file():density=read_reference(ref,r)
            else:raise ValueError('Velocity potentials describe mass flux: supply equation_coefficients or an explicit --constant-density.')
        def read(key):return read_coefficients(files[key],len(r),lmax,grid['endian'])
        for key,components,tor in [('ur',('ur','ut','up'),'utor'),('Br',('Br','Bt','Bp'),'Btor'),('T',None,None),('C',None,None),('P',None,None)]:
            if key not in files:continue
            print(f'Synthesizing Rayleigh {key}, l <= {leff}...',flush=True)
            values=synthesize_checkpoint(read(key),r,lmax,leff,theta,phi,read(tor) if tor else None,density if key=='ur' else None)
            if components:fields.update(zip(components,values))
            else:fields[key]=values
        lmax=leff
    else:
        shape=(len(r),len(theta),len(phi))
        for key,f in files.items():fields[key]=read_volume(f,shape,grid['endian'])
    ir=np.argsort(r);it=np.argsort(theta);r=r[ir];theta=theta[it]
    fields={k:v[ir][:,it,:] for k,v in fields.items()}
    if not checkpoint:
        fields,theta,phi,info=cached_calculation(truncate_graphic_fields)(fields,theta,phi,args.spectral_lmax,lmax,1)
        lmax=info['lmax_effective']
    time=grid['time'] if args.time is None else args.time
    params=dict(l_max=lmax,time=time,ek=native.get('ekman_number',math.nan),pr=native.get('prandtl_number',math.nan),
                prmag=native.get('magnetic_prandtl_number',math.nan),sc=native.get('schmidt_number',math.nan),ra=native.get('rayleigh_number',math.nan),raxi=native.get('compositional_rayleigh_number',math.nan),radratio=r[0]/r[-1])
    params=resolve_graph_parameters(args,{**native,**params},str(control or path))
    factors={}
    if args.n2_convention=='deepscope' and (selection.wants('N2') or selection.wants('N2_nom0')):
        ek=args.Ek if args.Ek is not None else params['ek']
        for field,ra,pr in [('T',args.RaT if args.RaT is not None else params['ra'],args.Pr if args.Pr is not None else params['pr']),('C',params['raxi'],params['sc'])]:
            if field in fields:
                if any(v is None or not math.isfinite(v) for v in (ek,ra,pr)) or pr<=0:raise ValueError(f'N2 for {field} needs finite Ek, Rayleigh and positive Pr/Sc.')
                factors[field]=r*ek**2*ra/pr
    adapted=dict(fields=fields,r_shell=r,r_master=r,theta=theta,phi=phi,minc=1,n2_factors=factors,
        has_conducting_inner_core=False,magnetic_extends_inner_core=False,
        thermal_source='temperature' if native.get('reference_type')==1 else 'stored thermal scalar (entropy/temperature depends on model)',
        metadata=dict(source_code='Rayleigh',description='Native Rayleigh snapshot; no background fields added.',converter_version=CONVERTER_PACKAGE_VERSION,
          source_fields={k:str(v) for k,v in files.items()},state_number=grid['step'],
          rayleigh=dict(input_format='checkpoint' if checkpoint else 'spherical3d',native_parameters=native,
            physical_time_known=math.isfinite(time),n2_convention=args.n2_convention,
            scalar_policy='stored thermal/composition fields only; imposed/reference scalar profiles are not added',
            checkpoint_velocity='curlcurl(W e_r)/rho + curl(Z e_r)/rho',
            angular_normalization='orthonormal Y_lm; Re(sum_m>=0 a_lm Y_lm); no extra m>0 factor'),
          spectral=dict(lmax=lmax,mmax=lmax,minc=1,nlat=len(theta),nphi=len(phi),library='NumPy/SciPy Rayleigh native reader'),
          geometry_detection=dict(method='native radial grid',requested_geometry=args.geometry)))
    if info is not None:adapted['spectral_truncation']=info
    return convert_adapted_snapshot(path,outdir,args,adapted,params,source_label='Rayleigh',source_format='rayleigh_checkpoint' if checkpoint else 'rayleigh_spherical3d')


def run_sequence(args,paths):
    root=Path(args.out);frames_root=bundle_path(root,args.sequence_subdir);frames_root.mkdir(parents=True,exist_ok=True)
    frames=[];first_out=None
    for path in paths:
        n=state_number(path);label=f'state{n:08d}';frame_out=frames_root/label
        opts=copy.copy(args);opts.out=str(frame_out);opts.state=str(path);opts.folder=None;opts.sequence_first=opts.sequence_last=None
        if args.incremental:
            previous=Path(args._incremental_source_root)/args.sequence_subdir/label
            if previous.is_dir():shutil.copytree(previous,frame_out)
        run_conversion(opts,'rayleigh',source_files([path],opts),lambda current:convert_state(path,Path(current.out),current))
        meta=json.loads((frame_out/'metadata.json').read_text())
        if first_out is None:first_out=frame_out
        frames.append(dict(state_number=n,time=meta['time'],path=f'{args.sequence_subdir}/{label}',metadata=f'{args.sequence_subdir}/{label}/metadata.json',label=label))
    for item in first_out.iterdir():
        if item.is_file() and item.name not in ('view.DTV2','conversion_manifest.json'):shutil.copy2(item,root/item.name)
    (root/'sequence.json').write_text(json.dumps(dict(version=1,frame_count=len(frames),first=args.sequence_first,last=args.sequence_last,step=args.sequence_step,frames=frames),indent=2,allow_nan=False)+'\n')


def main(argv=None):
    args=build_arg_parser().parse_args(argv)
    for name in ('downsample_r','downsample_theta','downsample_phi','line_seed_theta','line_seed_phi','line_max_steps','sequence_step'):
        if getattr(args,name)<1:raise ValueError(f'--{name.replace("_","-")} must be positive.')
    if args.line_step_size is not None and (not math.isfinite(args.line_step_size) or args.line_step_size<=0):raise ValueError('--line-step-size must be finite and positive.')
    if args.constant_density is not None and (not math.isfinite(args.constant_density) or args.constant_density<=0):raise ValueError('--constant-density must be finite and positive.')
    if args.time is not None and not math.isfinite(args.time):raise ValueError('--time must be finite.')
    if args.composition_field and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',args.composition_field):raise ValueError('--composition-field must be a filename, not a path.')
    if args.line_seeds is not None:
        if args.line_seeds<1:raise ValueError('--line-seeds must be positive.')
        args.line_seed_theta,args.line_seed_phi=choose_regular_seed_grid(args.line_seeds)
    if args.inner_core_only:raise ValueError('Rayleigh inputs have no separately resolved conducting inner-core domain.')
    paths=discover_states(args);files=source_files(paths,args)
    if args.sequence_first is not None:run_conversion(args,'rayleigh',files,lambda current:run_sequence(current,paths))
    else:run_conversion(args,'rayleigh',files,lambda current:convert_state(paths[0],Path(current.out),current))

if __name__=='__main__':main()
