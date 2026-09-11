#!/usr/bin/env python3
"""Convert EPMDynamoCode and QuICC WLFl/WLFm full-sphere and SLFl/SLFm shell HDF5 states to DEEPscope."""
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

try:
    from quicc_data import read_state, modes, grids, synthesize_field
    from conversion_cache import run_conversion
    from convert_magic_to_viewer import add_viewer_arguments, convert_adapted_snapshot
    from convert_leeds_to_viewer import choose_regular_seed_grid
    from spectral_truncation import cutoff_metadata
    from viewer_bundle import bundle_path
except ImportError:
    from tools.quicc_data import read_state, modes, grids, synthesize_field
    from tools.conversion_cache import run_conversion
    from tools.convert_magic_to_viewer import add_viewer_arguments, convert_adapted_snapshot
    from tools.convert_leeds_to_viewer import choose_regular_seed_grid
    from tools.spectral_truncation import cutoff_metadata
    from tools.viewer_bundle import bundle_path

CONVERTER_PACKAGE_VERSION = '1.1.0'
STATE_RE = re.compile(r'^state_?(\d+)\.(?:hdf5|h5)$', re.I)


def build_arg_parser():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--state', '--restart', help='Explicit spectral state HDF5 file.')
    source.add_argument('--folder', '-folder', help='Run folder containing stateNNNN.hdf5 files.')
    p.add_argument('--state-number', '--ivar', type=int, help='Select a numbered state; default latest.')
    p.add_argument('--modules-dir', help='Compatibility option; no modules.py is needed.')
    p.add_argument('--worland-family', choices=['chebyshev','legendre'], default='chebyshev',
                   help='Must match the solver build; default is upstream Chebyshev Worland.')
    p.add_argument('--worland-normalization', choices=['unity','natural'], default='unity',
                   help='Must match the solver build; default normalized Worland.')
    p.add_argument('--angular-normalization', choices=['auto','unity','schmidt','epm'], default='auto',
                   help='Auto: EPM Schmidt with sqrt(2) for m>0; QuICC SHUnity. Override for custom builds.')
    p.add_argument('--n2-convention', choices=['none','deepscope','quicc-rotating'], default='none',
                   help='N2 scaling must match the source equations: none (default), r*Ek^2*Ra/Pr, or r*Ek*Ra/Pr (full sphere) or (r/ro)*Ek*Ra (shell). The shell convention has no Pr factor.')
    return add_viewer_arguments(p, 'public/data_quicc')


def state_number(path):
    match = STATE_RE.match(Path(path).name)
    return int(match[1]) if match else None


def discover_states(args):
    sequence = args.sequence_first is not None or args.sequence_last is not None
    if args.state:
        if sequence or args.state_number is not None:
            raise ValueError('--state selects one file; use --folder for numbered states or sequences.')
        path = Path(args.state).expanduser().resolve()
        if not path.is_file(): raise FileNotFoundError(path)
        return [path]
    folder = Path(args.folder).expanduser().resolve()
    if not folder.is_dir(): raise NotADirectoryError(folder)
    found = {}
    for path in folder.iterdir():
        n = state_number(path)
        if path.is_file() and n is not None:
            if n in found: raise ValueError(f'Duplicate state index {n}: use --state to choose explicitly.')
            found[n] = path
    if not found: raise ValueError('No stateNNNN.hdf5 files found. Use --state for differently named files.')
    if sequence:
        if args.sequence_first is None or args.sequence_last is None or args.sequence_last < args.sequence_first:
            raise ValueError('Sequences need --sequence-first <= --sequence-last, both supplied.')
        if args.state_number is not None: raise ValueError('Do not combine --state-number with a sequence.')
        selected = range(args.sequence_first, args.sequence_last+1, args.sequence_step)
    else:
        selected = [args.state_number if args.state_number is not None else max(found)]
    missing = [n for n in selected if n not in found]
    if missing: raise ValueError(f'Missing requested state indices: {missing[:10]}')
    return [found[n] for n in selected]


def convert_state(path, outdir, args):
    selection = OutputSelection(args)
    data = read_state(path)
    interval = data['radial_interval']
    expected_geometry = 'shell' if interval is not None else 'full-sphere'
    if args.geometry not in ('auto',expected_geometry):
        raise ValueError(f"Native {data['scheme']} geometry is {expected_geometry}; --geometry {args.geometry} is incompatible.")
    ri = interval[0] if interval is not None else 0.
    if args.fluid_inner_radius is not None and not math.isclose(args.fluid_inner_radius,ri,rel_tol=1e-10,abs_tol=1e-12):
        raise ValueError('--fluid-inner-radius disagrees with the native inner boundary.')
    if interval is not None and (args.worland_family != 'chebyshev' or args.worland_normalization != 'unity'):
        raise ValueError('Worland options apply to full spheres; SLFl/SLFm use their native Chebyshev FCT basis.')
    angular = args.angular_normalization
    if angular == 'auto': angular = 'epm' if data['scheme'] == 'EPM' else 'unity'
    info = cutoff_metadata(args.spectral_lmax, data['lmax'], data['mmax'])
    leff = info['lmax_effective']
    meff = info['mmax_effective'] // data['minc'] * data['minc']
    info['mmax_effective'] = meff
    radius, theta, phi = grids(data['nmax'], leff, meff, interval)
    _, old_theta, old_phi = grids(data['nmax'], data['lmax'], data['mmax'], interval)
    info.update(original_grid=[len(old_theta),len(old_phi)], output_grid=[len(theta),len(phi)],
                method='native spectral truncation before Worland/vector harmonic synthesis')
    pairs = modes(data['lmax'], data['mmax'], data['minc'], data['scheme'][-1])
    fields = {}
    for name, components in [('ur',('ur','ut','up')), ('Br',('Br','Bt','Bp')), ('T',None), ('C',None)]:
        if name not in data['fields'] or not selection.needs(name): continue
        print(f'Synthesizing {name}, l <= {leff}...', flush=True)
        coef = data['fields'][name]
        if components: coef = (coef, data['fields']['utor' if name == 'ur' else 'Btor'])
        result = synthesize_field(coef, pairs, radius, theta, phi, leff, angular,
                                  args.worland_family, args.worland_normalization, interval)
        if components: fields.update(zip(components, result))
        else: fields[name] = result
    p = data['parameters']
    def get(*keys):
        return next((p[k] for k in keys if k in p), math.nan)
    params = dict(l_max=leff, ek=get('E','ekman'), pr=get('Pr','prandtl'),
                  sc=get('Sc','schmidt'), ra=get('Ra','rayleigh'), raxi=get('RaC','rayleigh_composition'),
                  prmag=get('Pm','magnetic_prandtl'), time=data['time'], radratio=ri/radius[-1])
    params = resolve_graph_parameters(args, {**p, **params}, str(path))
    # HDF5 identifies a spatial scheme, not the governing nondimensional equations.
    # Do not silently assign the Leeds Ra convention to a modified-Rayleigh model.
    if args.n2_convention == 'quicc-rotating' and interval is not None and not math.isclose(interval[1]-interval[0],1.,rel_tol=1e-10,abs_tol=1e-12):
        raise ValueError('--n2-convention quicc-rotating for shells assumes the standard unit-gap dynamo model; select none for other nondimensionalizations.')
    factors = {}
    if args.n2_convention != 'none' and (selection.wants('N2') or selection.wants('N2_nom0')):
        ek = args.Ek if args.Ek is not None else params['ek']
        for field, ra_key, pr_key, ra_arg, pr_arg in [('T','ra','pr','RaT','Pr'), ('C','raxi','sc','RaC','Sc')]:
            ra = getattr(args,ra_arg) if getattr(args,ra_arg) is not None else params[ra_key]
            pr = getattr(args,pr_arg) if getattr(args,pr_arg) is not None else params[pr_key]
            shell_rotating = args.n2_convention == 'quicc-rotating' and interval is not None
            if field in fields and all(v is not None and math.isfinite(v) for v in (ek,ra)) and (shell_rotating or (pr is not None and math.isfinite(pr) and pr != 0)):
                if args.n2_convention == 'quicc-rotating' and interval is not None:
                    # Shell dynamo uses modified Ra without Pr and gravity r/ro.
                    factors[field] = (radius/radius[-1]) * ek * ra
                else:
                    factors[field] = radius * ek**(2 if args.n2_convention == 'deepscope' else 1) * ra/pr
    elif not args.no_gradients and any(k in fields for k in ('T','C')):
        print('N2 omitted: select --n2-convention to match the source nondimensional equations.', flush=True)
    adapted = dict(n2_factors=factors, r_shell=radius, r_master=radius, r_fluid_inner=ri, theta=theta, phi=phi,
        fields=fields, minc=data['minc'], has_conducting_inner_core=False, magnetic_extends_inner_core=False,
        spectral_truncation=info,
        metadata={'source_code':'QuICC/EPM' if data['scheme']=='EPM' else 'QuICC',
                  'state_number':state_number(path),
                  'quicc':{'scheme':data['scheme'], 'radial_basis':'mapped_chebyshev' if interval is not None else args.worland_family,
                           'radial_normalization':'fct_c0_plus_2cn' if interval is not None else args.worland_normalization, 'angular_normalization':angular,
                           'nmax':data['nmax'], 'native_parameters':p,
                           'scalar_policy':'stored state coefficients; external imposed/background files are not added',
                           'radial_interval':list(interval) if interval is not None else [0.,1.],
                           'centre_policy':'not_in_fluid_domain' if interval is not None else 'analytic regular Worland limits',
                           'diagnostics_units':'native code units', 'n2_convention':args.n2_convention},
                  'spectral':{'lmax':leff,'mmax':meff,'minc':data['minc'], 'nlat':len(theta),'nphi':len(phi),
                              'library':'NumPy/SciPy native radial and vector spherical harmonics'},
                  'geometry_detection':{'method':'native shell Chebyshev interval' if interval is not None else 'native full-sphere Worland spectral scheme',
                                        'transform_geometry':'spectral', 'requested_geometry':args.geometry}})
    return convert_adapted_snapshot(path, outdir, args, adapted, params,
                                    source_label='QuICC/EPM' if data['scheme']=='EPM' else 'QuICC',
                                    source_format='quicc_spectral_hdf5')


def run_sequence(args, paths):
    root = Path(args.out)
    frames_root = bundle_path(root, args.sequence_subdir)
    frames_root.mkdir(parents=True, exist_ok=True)
    frames = []
    first_out = None
    for path in paths:
        n = state_number(path)
        label = f'state{n:05d}'
        frame_out = frames_root / label
        opts = copy.copy(args)
        opts.out, opts.state, opts.folder = str(frame_out), str(path), None
        opts.sequence_first = opts.sequence_last = None
        if args.incremental:
            previous = Path(args._incremental_source_root) / args.sequence_subdir / label
            if previous.is_dir(): shutil.copytree(previous, frame_out)
        run_conversion(opts, 'quicc', [path], lambda current: convert_state(path, Path(current.out), current))
        meta = json.loads((frame_out/'metadata.json').read_text())
        if first_out is None: first_out = frame_out
        frames.append(dict(state_number=n, time=meta['time'], path=f'{args.sequence_subdir}/{label}',
                           metadata=f'{args.sequence_subdir}/{label}/metadata.json', label=label))
    for item in first_out.iterdir():
        if item.is_file() and item.name not in ('view.DTV2','conversion_manifest.json'):
            shutil.copy2(item, root/item.name)
    (root/'sequence.json').write_text(json.dumps(dict(version=1, frame_count=len(frames),
        first=args.sequence_first, last=args.sequence_last, step=args.sequence_step, frames=frames),
        indent=2, allow_nan=False)+'\n')


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    for name in ('downsample_r','downsample_theta','downsample_phi','line_seed_theta','line_seed_phi',
                 'line_max_steps','sequence_step'):
        if getattr(args,name) < 1: raise ValueError(f'--{name.replace("_","-")} must be positive.')
    if args.line_step_size is not None and (not math.isfinite(args.line_step_size) or args.line_step_size <= 0):
        raise ValueError('--line-step-size must be finite and positive.')
    if args.line_seeds is not None:
        if args.line_seeds < 1: raise ValueError('--line-seeds must be positive.')
        args.line_seed_theta, args.line_seed_phi = choose_regular_seed_grid(args.line_seeds)
    if args.inner_core_only:
        raise ValueError('--inner-core-only is unavailable: these QuICC formats contain no separately resolved inner-core fields.')
    paths = discover_states(args)
    if args.sequence_first is not None:
        run_conversion(args, 'quicc', paths, lambda current: run_sequence(current, paths))
    else:
        run_conversion(args, 'quicc', paths, lambda current: convert_state(paths[0], Path(current.out), current))


if __name__ == '__main__':
    main()
