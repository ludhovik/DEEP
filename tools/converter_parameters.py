"""Dimensionless parameters from native simulation metadata, never path names."""
from __future__ import annotations
import math
import sys
from collections.abc import Mapping
import numpy as np

PARAMETER_SPECS = {
    'Ek': ('Ekman number', ('Ek', 'E', 'ek', 'ekman', 'ekman_number')),
    'Pr': ('thermal Prandtl number', ('Pr', 'PrT', 'Pr_T', 'pr', 'prandtl', 'prandtl_number')),
    'Sc': ('compositional Prandtl/Schmidt number', ('Sc', 'PrC', 'Pr_C', 'sc', 'schmidt', 'schmidt_number', 'compositional_prandtl_number')),
    'RaT': ('thermal Rayleigh number', ('RaT', 'Ra_T', 'Ra', 'ra', 'rayleigh', 'rayleigh_number')),
    'RaC': ('compositional Rayleigh number', ('RaC', 'Ra_C', 'Ra_comp', 'raxi', 'rayleigh_composition', 'compositional_rayleigh_number')),
    'Pm': ('magnetic Prandtl number', ('Pm', 'PrMag', 'prmag', 'magnetic_prandtl', 'magnetic_prandtl_number')),
}
EXTRA_PARAMETERS = {'Ro': ('Ro',), 'q': ('q',), 'radius_ratio': ('riro', 'radratio', 'radius_ratio')}
GRAPH_KEYS = dict(Ek='ek', Pr='pr', Sc='sc', RaT='ra', RaC='raxi', Pm='prmag')


def finite_number(value):
    try:
        a = np.asarray(value)
        if a.size != 1 or a.dtype.kind == 'b': return None
        value = a.item()
        if isinstance(value, bytes): value = value.decode('ascii')
        if isinstance(value, str): value = value.replace('D', 'e').replace('d', 'e')
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError, UnicodeError):
        return None


def native_value(native, aliases):
    for key in aliases:
        value = finite_number(native.get(key))
        if value is not None: return value
    return None


def prompt_parameter(name, label):
    while True:
        # A separate line remains readable with redirected output or a piped stdin.
        print(f'Enter {name} ({label}); blank = unknown:', flush=True)
        try: raw = input().strip()
        except EOFError: return None
        if not raw: return None
        value = finite_number(raw)
        if value is not None: return value
        print('Enter a finite number, or leave blank for unknown.', flush=True)


def resolve_parameters(native, args, source='simulation metadata', prompt_missing=None):
    """CLI > this frame's native value > answer previously supplied for a missing value.

    Answers are shared by sequence frames, but never override a later native value.
    Unknown values remain NaN in calculations and are serialized as null by exporters.
    """
    if prompt_missing is None: prompt_missing = not getattr(args, 'no_parameter_prompt', False)
    answers = vars(args).setdefault('_parameter_prompt_answers', {})
    values, origins, missing = {}, {}, []
    for name, (label, aliases) in PARAMETER_SPECS.items():
        supplied = getattr(args, name, None)
        if supplied is not None:
            value = finite_number(supplied)
            if value is None: raise ValueError(f'--{name} must be a finite number.')
            origin = 'command_line'
        else:
            value = native_value(native, aliases)
            origin = 'native'
            if value is None:
                if name in answers:
                    value, origin = answers[name], 'prompt' if answers[name] is not None else 'unknown'
                else:
                    missing.append(name)
                    origin = 'unknown'
        values[name] = float('nan') if value is None else value
        origins[name] = origin
    interactive = sys.stdin is not None and sys.stdin.isatty()
    if missing and prompt_missing and interactive:
        print(f'Missing dimensionless parameters in {source}. Folder names are not used.', flush=True)
        for name in missing:
            value = prompt_parameter(name, PARAMETER_SPECS[name][0])
            answers[name] = value
            values[name] = float('nan') if value is None else value
            origins[name] = 'unknown' if value is None else 'prompt'
    elif missing:
        print('WARNING: unknown parameters: ' + ', '.join(missing) +
              '. Supply CLI overrides' + (' or run interactively.' if not interactive else ' (prompting disabled).'), flush=True)
    for name, aliases in EXTRA_PARAMETERS.items():
        value = native_value(native, aliases)
        if value is not None:
            values[name], origins[name] = value, 'native'
    args._parameter_sources = origins
    return values


def resolve_graph_parameters(args, native, source='native header/control'):
    """Resolve before source-specific N2 factors are constructed."""
    values = resolve_parameters(native, args, source)
    result = dict(native)
    for key, attr in GRAPH_KEYS.items():
        result[attr] = finite_number(values[key])
    result['_resolved_parameters'] = values
    result['_parameter_sources'] = dict(args._parameter_sources)
    return result


def read_netcdf_attributes(path):
    """Read only global attributes; handle modern NetCDF4 and legacy NetCDF3."""
    try:
        from netCDF4 import Dataset
    except ImportError:
        try:
            import h5py
        except ImportError:
            h5py = None
        if h5py is not None and h5py.is_hdf5(path):
            with h5py.File(path, 'r') as f: return dict(f.attrs)
        from scipy.io import netcdf_file
        with netcdf_file(path, 'r', mmap=False) as f: return dict(f._attributes)
    with Dataset(path, 'r') as f:
        return {key: f.getncattr(key) for key in f.ncattrs()}


def xshells_native_parameters(fields):
    """Read exposed native header attributes; ordinary field files may lack them."""
    native = {}
    aliases = {a for _, names in PARAMETER_SPECS.values() for a in names}
    for field in fields:
        candidates = [getattr(field, key, None) for key in ('parameters', 'attrs', 'header')]
        candidates.append({key: getattr(field, key, None) for key in aliases})
        for candidate in candidates:
            if not isinstance(candidate, Mapping): continue
            for key in aliases:
                value = finite_number(candidate.get(key))
                if value is not None:
                    if key in native and not math.isclose(native[key], value, rel_tol=1e-10, abs_tol=0):
                        raise ValueError(f'Conflicting XSHELLS native parameter {key}.')
                    native[key] = value
    return native
