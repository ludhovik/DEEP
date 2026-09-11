#!/usr/bin/env python3
"""Convert Calypso merged ASCII/binary spectral restarts to DEEPscope bundles.

Uses NumPy/SciPy only. The native control_MHD and spherical-grid controls are
required because restart files do not contain their radial coordinates or (l,m)
ordering. See CALYPSO_CONVERTER.md for conventions and supported formats.
"""
from __future__ import annotations

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
    from converter_parameters import resolve_graph_parameters
except ImportError:
    from tools.converter_parameters import resolve_graph_parameters

import numpy as np

try:
    from calypso_data import (centre_vector, control_value, grid_from_controls,
                              number, read_controls, read_restart, synthesize_spectra)
    from conversion_cache import run_conversion
    from convert_magic_to_viewer import add_viewer_arguments, convert_adapted_snapshot
    from convert_leeds_to_viewer import choose_regular_seed_grid
    from spectral_truncation import cutoff_metadata
    from viewer_bundle import bundle_path
except ImportError:
    from tools.calypso_data import (centre_vector, control_value, grid_from_controls,
                                    number, read_controls, read_restart, synthesize_spectra)
    from tools.conversion_cache import run_conversion
    from tools.convert_magic_to_viewer import add_viewer_arguments, convert_adapted_snapshot
    from tools.convert_leeds_to_viewer import choose_regular_seed_grid
    from tools.spectral_truncation import cutoff_metadata
    from tools.viewer_bundle import bundle_path


CONVERTER_PACKAGE_VERSION = "3.7.2"
RESTART_RE = re.compile(r"^.+\.(\d+)\.fs[tb](?:\.gz)?$")


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", "-folder", help="Calypso run folder containing control_MHD.")
    parser.add_argument("--state", "--restart", help="Explicit merged rst.<index>.fst/.fsb file (also native gzip).")
    parser.add_argument("--state-number", "--ivar", type=int, help="Restart filename index; default is the latest available.")
    parser.add_argument("--control", help="Explicit control_MHD path; otherwise found in the run folder.")
    parser.add_argument("--modules-dir", help="Accepted for command compatibility; the Calypso reader needs no modules.py.")
    return add_viewer_arguments(parser, "public/data_calypso")


def find_control(args):
    if args.control:
        path = Path(args.control).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Calypso control file not found: {path}")
        return path
    location = Path(args.folder).expanduser() if args.folder else (Path(args.state).expanduser().parent if args.state else None)
    if location is None:
        raise ValueError("Give --folder or --state, with --control if control_MHD is elsewhere.")
    location = location.resolve()
    for candidate in (location / "control_MHD", location.parent / "control_MHD"):
        if candidate.is_file():
            return candidate
    # Accept the extracted shell/ folder without requiring the user to know its nested run name.
    candidates = list(location.glob("*/control_MHD"))
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("Could not select one control_MHD. Give the run folder or --control explicitly.")


def restart_step(path):
    match = RESTART_RE.match(Path(path).name)
    if not match:
        raise ValueError("Expected a merged Calypso rst.<index>.fst/.fsb file, optionally .gz; rank-local files are unsupported.")
    return int(match[1])


def discover_states(args, control, records):
    if args.state:
        path = Path(args.state).expanduser().resolve()
        restart_step(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if args.sequence_first is not None or args.sequence_last is not None:
            raise ValueError("Use --folder for sequences; --state selects a single restart.")
        return [path]
    prefix = Path(control_value(records, "restart_file_prefix", "restart/rst"))
    prefix = prefix if prefix.is_absolute() else control.parent / prefix
    found = {}
    for path in prefix.parent.glob(prefix.name + ".*.fs*"):
        if not path.is_file() or not RESTART_RE.match(path.name):
            continue
        step = restart_step(path)
        if step in found:
            raise ValueError(f"Two Calypso restarts have step {step}: {found[step]} and {path}. Select one with --state.")
        found[step] = path.resolve()
    if not found:
        raise FileNotFoundError(f"No merged restarts at {prefix}.<index>.fst/.fsb (also .gz). Keep restart and control files together.")
    first, last = args.sequence_first, args.sequence_last
    if first is not None or last is not None:
        if first is None or last is None or last < first or args.sequence_step < 1:
            raise ValueError("Sequences require first <= last and --sequence-step >= 1.")
        requested = list(range(first, last + 1, args.sequence_step))
        missing = [step for step in requested if step not in found]
        if missing:
            raise ValueError(f"Missing Calypso restart steps: {missing[:20]}.")
        return [found[step] for step in requested]
    step = args.state_number if args.state_number is not None else max(found)
    if step not in found:
        raise ValueError(f"No Calypso restart at step {step}.")
    return [found[step]]


def physical_parameters(records, args, radius, r_icb=None):
    """Keep native parameter names and derive N²/Ω² from momentum coefficients.

    Calypso: c_v du/dt = ... + c_T r T + c_C r C - c_Ω ez×u.
    Thus Ω*=c_Ω/(2c_v), and N²/Ω² = r(c_T T_r+c_C C_r)/(c_v Ω*²).
    Explicit --RaT/--RaC retain the other converters' E² Ra/Pr convention.
    """
    dim = {}
    for _, key, values in records:
        if key == "dimless_ctl" and len(values) == 2:
            name = values[0].lower()
            if name in dim:
                raise ValueError(f"Duplicate Calypso dimensionless number {name}.")
            dim[name] = number(values[1])
    aliases = {"Ek": "ekman_number", "Pr": "prandtl_number", "Sc": "schmidt_number"}
    for cli, native in aliases.items():
        if getattr(args, cli) is not None:
            dim[native] = number(getattr(args, cli))
    params = {"ek": dim.get("ekman_number"), "pr": dim.get("prandtl_number"),
              "sc": dim.get("schmidt_number", dim.get("compositional_prandtl_number")),
              "ra": dim.get("rayleigh_number"), "raxi": dim.get("compositional_rayleigh_number"),
              "prmag": dim.get("magnetic_prandtl_number")}
    params = resolve_graph_parameters(args, params, "Calypso dimensionless controls")
    for canonical, native in {"Ek": "ekman_number", "Pr": "prandtl_number", "Sc": "schmidt_number",
                              "Pm": "magnetic_prandtl_number"}.items():
        value = params["_resolved_parameters"][canonical]
        if math.isfinite(value): dim[native] = value
    ratio = (radius[0] if r_icb is None else r_icb) / radius[-1]
    symbols = {**dim, "one": 1.0, "zero": 0.0, "two": 2.0,
               "radial_parameter": 1-ratio, "radial_35": 0.65}

    def coefficient(key):
        rows = [values for _, label, values in records if label == key]
        if not rows:
            return None
        product = 1.0
        for symbol, power in rows:
            value = symbols.get(symbol.lower())
            if value is None:
                return None
            if symbol.lower() == "zero":
                return 0.0
            product *= value ** number(power)
        return number(product)

    cv, cor = coefficient("coef_4_velocity_ctl"), coefficient("coef_4_coriolis_ctl")
    thermal = coefficient("coef_4_thermal_buoyancy_ctl")
    composition = coefficient("coef_4_composit_buoyancy_ctl")
    factors = {}
    if cv is not None and cv > 0 and cor is not None and cor != 0:
        for field, coef in (("T", thermal), ("C", composition)):
            if field == "C" and getattr(args, "RaC", None) == 0.0:
                continue
            if coef is not None:
                factors[field] = radius * (4 * cv * coef / cor**2)
    for field, cli, denominator in (("T", "RaT", "pr"), ("C", "RaC", "sc")):
        if field == "C" and getattr(args, "RaC", None) == 0.0:
            continue
        if getattr(args, cli) is not None or (field not in factors and params["_parameter_sources"].get(cli) == "prompt"):
            ek, denom = params["ek"], params[denominator]
            if ek is None or denom is None or denom <= 0:
                raise ValueError(f"--{cli} needs finite Ek and positive Pr/Sc for N2.")
            factors[field] = radius * (ek**2 * params["_resolved_parameters"][cli] / denom)
    info = {"native_dimensionless_numbers": dim,
            "momentum_coefficients": {"time": cv, "coriolis": cor, "thermal_buoyancy": thermal,
                                      "compositional_buoyancy": composition},
            "N2_definition": "N2/Omega^2 = r * (c_T*dT/dr + c_C*dC/dr) / (c_v*(c_Omega/(2*c_v))^2)",
            "N2_cli_override": [name for name in ("RaT", "RaC") if getattr(args, name) is not None],
            "N2_available_scalars": list(factors)}
    return params, factors, info


def convert_state(path, outdir, args, records, grid, control_files):
    selection = OutputSelection(args)
    print(f"Calypso restart: {path}", flush=True)
    spectra, centres, header = read_restart(path, grid)
    # Filenames count restart outputs, while the header counts solver steps.
    state_number = restart_step(path)
    native_mmax = grid["lmax"] // grid["minc"] * grid["minc"]
    info = cutoff_metadata(args.spectral_lmax, grid["lmax"], native_mmax)
    lmax = info["lmax_effective"]
    info["mmax_effective"] = lmax // grid["minc"] * grid["minc"]
    nt = min(grid["ntheta"], max(4, lmax + 2)) if info["enabled"] else grid["ntheta"]
    np_ = min(grid["nphi"], max(8, 2 * (lmax + 1))) if info["enabled"] else grid["nphi"]
    theta = np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1])
    phi = np.arange(np_) * (2 * math.pi / np_)
    info.update(original_grid=[grid["ntheta"], grid["nphi"]], output_grid=[nt, np_],
                method="native Calypso spectral cutoff before physical synthesis")
    native_r = grid["r"]
    icb, cmb = grid["icb"], grid["cmb"]
    positive = native_r > 0
    r = native_r[positive]
    r_cmb = native_r[cmb]
    full = grid["full_sphere"]
    r_icb = 0.0 if full else float(native_r[icb])
    shell_mask = (r >= r_icb) & (r <= r_cmb)
    core_mask = r <= r_cmb
    add_centre = bool(grid["center"] or native_r[0] == 0)
    master = r[core_mask]
    if add_centre:
        master = np.r_[0., master]
    fluid = np.r_[0., r[shell_mask]] if full and add_centre else r[shell_mask]
    fields = {}
    for native, names in (("velocity", ("ur", "ut", "up")),
                           ("magnetic_field", ("Br", "Bt", "Bp")),
                           ("temperature", ("T",)), ("composition", ("C",)), ("pressure", ("P",))):
        if native not in spectra or not any(selection.needs(name) for name in names):
            continue
        vector = len(names) == 3
        coefficients = spectra[native][positive]
        print(f"  Synthesizing {native}, l <= {lmax}...", flush=True)
        values = synthesize_spectra(coefficients, r, theta, np_, lmax, vector)
        mask = core_mask if native == "magnetic_field" else shell_mask
        values = tuple(a[mask] for a in values)
        if add_centre and (full or native == "magnetic_field"):
            if vector:
                centre = centre_vector(coefficients, r[0], theta, np_)
            else:
                if native in centres:
                    scalar = float(centres[native][0])
                elif native_r[0] == 0:
                    scalar = float(spectra[native][0, 0, 0])
                else:
                    raise ValueError(f"No stored Calypso centre value for {native}.")
                centre = (np.full((1, nt, np_), scalar),)
            values = tuple(np.concatenate((c, a)) for c, a in zip(centre, values))
        fields.update(zip(names, values))
    if not fields:
        raise ValueError("The restart contains no supported physical fields.")
    magnetic_extends = "Br" in fields and master[0] < r_icb
    if not magnetic_extends:
        master = fluid
    cond_ic = magnetic_extends and not any(key == "bc_magnetic_field" and len(v) >= 2
                    and v[0].lower() == "insulator" and v[1].lower() == "icb" for _, key, v in records)
    params, factors, normalization = physical_parameters(records, args, fluid, r_icb)
    params.update(time=header["time"], l_max=lmax, radratio=r_icb/r_cmb)
    adapted = {"r_shell": fluid, "r_master": master, "theta": theta, "phi": phi,
               "r_fluid_inner": r_icb, "fields": fields, "minc": grid["minc"],
               "has_conducting_inner_core": cond_ic, "magnetic_extends_inner_core": magnetic_extends,
               "spectral_truncation": info, "thermal_source": "temperature", "n2_factors": factors,
               "metadata": {
                   "description": "Calypso spectral restart reconstructed with native Schmidt harmonics.",
                   "source_format": "calypso", "converter_version": CONVERTER_PACKAGE_VERSION,
                   "source_state": str(path.resolve()), "state_number": state_number,
                   "source_fields": {"restart": str(path.resolve()), "controls": [str(p) for p in control_files]},
                   "calypso": {**normalization, "dt": header["dt"], "simulation_step": header["step"],
                               "source_field_names": header["field_names"],
                               "restart_vector_columns": ["poloidal", "toroidal", "d_poloidal_dr"],
                               "harmonics": "Schmidt semi-normalized, no Condon-Shortley; positive m cosine, negative m sine",
                               "centre_policy": "scalar stored centre; vector l=1 nearest-shell regular limit" if add_centre else "no centre sample"},
                   "spectral": {"lmax": lmax, "mmax": lmax // grid["minc"] * grid["minc"],
                                "minc": grid["minc"], "nlat": nt, "nphi": np_, "library": "NumPy/SciPy native Calypso synthesis"},
                   "geometry_detection": {"method": "Calypso native controls and validated MPI node counts",
                                          "transform_geometry": "spectral", "requested_geometry": args.geometry}}}
    return convert_adapted_snapshot(path, outdir, args, adapted, params,
                                    source_label="Calypso", source_format="calypso")


def run_sequence(args, paths, records, grid, controls):
    root = Path(args.out)
    frames_root = bundle_path(root, args.sequence_subdir)
    frames_root.mkdir(parents=True, exist_ok=True)
    frames, first_out = [], None
    for path in paths:
        step = restart_step(path)
        label = f"state{step:05d}"
        frame_out = frames_root / label
        opts = copy.copy(args)
        opts.out, opts.state, opts.folder = str(frame_out), str(path), None
        opts.sequence_first = opts.sequence_last = None
        if args.incremental:
            previous = Path(args._incremental_source_root) / args.sequence_subdir / label
            if previous.is_dir():
                shutil.copytree(previous, frame_out)
        run_conversion(opts, "calypso", [path, *controls],
                       lambda current: convert_state(path, Path(current.out), current, records, grid, controls))
        meta = json.loads((frame_out / "metadata.json").read_text())
        first_out = frame_out if first_out is None else first_out
        frames.append({"state_number": step, "time": meta["time"], "path": f"{args.sequence_subdir}/{label}",
                       "metadata": f"{args.sequence_subdir}/{label}/metadata.json", "label": label})
    for item in first_out.iterdir():
        if item.is_file() and item.name not in ("view.DTV2", "conversion_manifest.json"):
            shutil.copy2(item, root / item.name)
    (root / "sequence.json").write_text(json.dumps({"version": 1, "frame_count": len(frames),
        "first": args.sequence_first, "last": args.sequence_last, "step": args.sequence_step,
        "frames": frames}, indent=2, allow_nan=False) + "\n")


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    control = find_control(args)
    records, controls = read_controls(control)
    grid = grid_from_controls(records, args.geometry)
    paths = discover_states(args, control, records)
    for attr in ("downsample_r", "downsample_theta", "downsample_phi", "line_max_steps",
                 "line_seed_theta", "line_seed_phi"):
        if getattr(args, attr) < 1:
            raise ValueError(f"--{attr.replace('_', '-')} must be positive.")
    if args.line_step_size is not None and (not math.isfinite(args.line_step_size) or args.line_step_size <= 0):
        raise ValueError("--line-step-size must be finite and positive.")
    if args.line_seeds is not None:
        if args.line_seeds < 1:
            raise ValueError("--line-seeds must be positive.")
        args.line_seed_theta, args.line_seed_phi = choose_regular_seed_grid(args.line_seeds)
    if args.sequence_first is not None:
        run_conversion(args, "calypso", [*paths, *controls],
                       lambda current: run_sequence(current, paths, records, grid, controls))
    else:
        path = paths[0]
        run_conversion(args, "calypso", [path, *controls],
                       lambda current: convert_state(path, Path(current.out), current, records, grid, controls))


if __name__ == "__main__":
    main()
