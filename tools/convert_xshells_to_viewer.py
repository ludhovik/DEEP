#!/usr/bin/env python3
"""Convert XSHELLS field files to Dynamo Three Viewer data.

XSHELLS usually stores one snapshot in separate files, for example::

    fieldU.bench   velocity (poloidal/toroidal)
    fieldB.bench   magnetic field (poloidal/toroidal)
    fieldT.bench   temperature scalar
    fieldC.bench   composition/concentration scalar

The converter accepts explicit paths, or ``--folder`` plus ``--tag`` to discover
these conventional names.  Output follows the same metadata/binary format as
``convert_state_to_viewer.py``.

Requires: numpy, shtns, pyxshells
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pyxshells
except ImportError as exc:  # pragma: no cover - environment-dependent
    raise SystemExit(
        "Could not import pyxshells. Install it in the converter environment with:\n"
        "  python -m pip install pyxshells\n"
        "pyxshells also requires the Python SHTns module."
    ) from exc


def json_number(value: Any, default: float = 0.0) -> float:
    try:
        out = float(np.asarray(value).item())
    except Exception:
        out = float(default)
    return out if math.isfinite(out) else float(default)


def finite_range(arr: np.ndarray) -> dict[str, float]:
    values = np.asarray(arr, dtype=np.float64)
    good = values[np.isfinite(values)]
    if good.size == 0:
        return {"min": 0.0, "max": 0.0, "absmax": 0.0}
    amin = float(np.min(good))
    amax = float(np.max(good))
    return {"min": amin, "max": amax, "absmax": max(abs(amin), abs(amax))}


def write_f32(path: Path, arr: np.ndarray) -> dict[str, float]:
    values = np.asarray(arr, dtype=np.float64)
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    values = np.ascontiguousarray(values.astype("<f4", copy=False))
    values.tofile(path)
    return finite_range(values)


def remove_m0_phi(arr: np.ndarray) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float64)
    return values - np.mean(values, axis=2, keepdims=True)


def phi_average_volume(arr: np.ndarray) -> np.ndarray:
    mean = np.mean(np.asarray(arr, dtype=np.float64), axis=2, keepdims=True)
    return np.broadcast_to(mean, np.asarray(arr).shape).copy()


def gradient_scalar_3d(
    scalar: np.ndarray,
    r: np.ndarray,
    theta: np.ndarray,
    phi: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return physical spherical components d/dr, (1/r)d/dtheta, (1/r sinθ)d/dphi."""
    f = np.asarray(scalar, dtype=np.float64)
    edge_r = 2 if len(r) >= 3 else 1
    edge_t = 2 if len(theta) >= 3 else 1

    d_dr = np.gradient(f, r, axis=0, edge_order=edge_r)
    d_dtheta = np.gradient(f, theta, axis=1, edge_order=edge_t)

    # Periodic phi derivative supports either a non-cyclic grid or an endpoint-duplicated grid.
    nphi = f.shape[2]
    if nphi < 2:
        d_dphi = np.zeros_like(f)
    else:
        period = 2.0 * np.pi
        dphi = period / nphi
        d_dphi = (np.roll(f, -1, axis=2) - np.roll(f, 1, axis=2)) / (2.0 * dphi)

    rr = r[:, None, None]
    sint = np.sin(theta)[None, :, None]
    safe_r = np.where(np.abs(rr) > 1.0e-14, rr, np.inf)
    safe_rs = np.where(np.abs(rr * sint) > 1.0e-14, rr * sint, np.inf)

    grad_theta = d_dtheta / safe_r
    grad_phi = d_dphi / safe_rs
    grad_theta[~np.isfinite(grad_theta)] = 0.0
    grad_phi[~np.isfinite(grad_phi)] = 0.0
    return d_dr, grad_theta, grad_phi


def parse_float_from_path(path: str, aliases: tuple[str, ...]) -> float | None:
    for key in aliases:
        match = re.search(rf"(?:^|[/_]){re.escape(key)}\\?=([0-9eE+.-]+)", path)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
    return None


def prompt_float(name: str, description: str) -> float:
    while True:
        raw = input(f"Enter {name} ({description}); blank = NaN: ").strip()
        if not raw:
            return float("nan")
        try:
            return float(raw)
        except ValueError:
            print(f"Could not parse {raw!r} as a floating-point number.")


def resolve_parameter(
    cli_value: float | None,
    source_paths: list[str],
    aliases: tuple[str, ...],
    name: str,
    description: str,
    prompt_missing: bool,
) -> float:
    if cli_value is not None:
        return float(cli_value)
    for source in source_paths:
        value = parse_float_from_path(source, aliases)
        if value is not None:
            return value
    if prompt_missing and sys.stdin.isatty():
        return prompt_float(name, description)
    return float("nan")


def discover_file(folder: Path, prefix: str, tag: str | None) -> Path | None:
    if tag:
        exact = folder / f"{prefix}.{tag}"
        if exact.exists():
            return exact
    candidates = sorted(folder.glob(f"{prefix}.*"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def resolve_inputs(args: argparse.Namespace) -> dict[str, Path | None]:
    resolved: dict[str, Path | None] = {
        "velocity": Path(args.velocity).expanduser() if args.velocity else None,
        "magnetic": Path(args.magnetic).expanduser() if args.magnetic else None,
        "temperature": Path(args.temperature).expanduser() if args.temperature else None,
        "composition": Path(args.composition).expanduser() if args.composition else None,
    }

    if args.folder:
        folder = Path(args.folder).expanduser()
        if not folder.is_dir():
            raise FileNotFoundError(f"XSHELLS folder does not exist: {folder}")
        conventions = {
            "velocity": args.velocity_prefix,
            "magnetic": args.magnetic_prefix,
            "temperature": args.temperature_prefix,
            "composition": args.composition_prefix,
        }
        for key, prefix in conventions.items():
            if resolved[key] is None:
                resolved[key] = discover_file(folder, prefix, args.tag)

    for key, path in resolved.items():
        if path is not None and not path.is_file():
            raise FileNotFoundError(f"{key} field file does not exist: {path}")

    if all(path is None for path in resolved.values()):
        raise ValueError(
            "No XSHELLS fields were found. Give --folder [--tag], or explicit "
            "--velocity/--magnetic/--temperature/--composition paths."
        )
    return resolved


def configure_sht_grid(field: Any, nlat: int | None, nphi: int | None) -> None:
    if not hasattr(field, "sht"):
        raise TypeError("Loaded pyxshells field has no SHTns transform object.")
    if nlat is None and nphi is None:
        field.sht.set_grid()
    elif nlat is not None and nphi is not None:
        field.sht.set_grid(int(nlat), int(nphi))
    else:
        raise ValueError("Use --nlat and --nphi together, or omit both.")


def load_xshells_field(path: Path, reference: Any | None = None) -> Any:
    kwargs: dict[str, Any] = {"lazy": True}
    if reference is not None:
        kwargs.update({"sht": reference.sht, "grid": reference.grid})
    return pyxshells.load_field(str(path), **kwargs)


def validate_field_compatibility(reference: Any, field: Any, label: str) -> None:
    r0 = np.asarray(reference.grid.r[reference.irs : reference.ire + 1])
    r1 = np.asarray(field.grid.r[field.irs : field.ire + 1])
    if r0.shape != r1.shape or not np.allclose(r0, r1, rtol=0.0, atol=1.0e-12):
        raise ValueError(f"{label} radial grid does not match the reference field.")
    if (field.lmax, field.mmax, field.mres) != (reference.lmax, reference.mmax, reference.mres):
        raise ValueError(
            f"{label} spectral truncation {(field.lmax, field.mmax, field.mres)} does not match "
            f"reference {(reference.lmax, reference.mmax, reference.mres)}."
        )


def downsample(arr: np.ndarray, dr: int, dt: int, dp: int) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(arr)[::dr, ::dt, ::dp])


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert XSHELLS field files using pyxshells to viewer data.")
    source = p.add_argument_group("XSHELLS input")
    source.add_argument("--folder", help="Folder containing conventional fieldU.*, fieldB.*, fieldT.*, fieldC.* files.")
    source.add_argument("--tag", help="Suffix/tag, e.g. bench for fieldU.bench. Without it, newest matching files are used.")
    source.add_argument("--velocity", help="Explicit XSHELLS velocity field file (normally fieldU.*).")
    source.add_argument("--magnetic", help="Explicit XSHELLS magnetic field file (normally fieldB.*).")
    source.add_argument("--temperature", help="Explicit XSHELLS temperature scalar file (normally fieldT.*).")
    source.add_argument("--composition", help="Explicit XSHELLS composition scalar file (normally fieldC.*).")
    source.add_argument("--velocity-prefix", default="fieldU")
    source.add_argument("--magnetic-prefix", default="fieldB")
    source.add_argument("--temperature-prefix", default="fieldT")
    source.add_argument("--composition-prefix", default="fieldC")

    p.add_argument("--out", default="public/data_xshells", help="Viewer output directory.")
    p.add_argument("--nlat", type=int, help="Requested SHTns latitude count. Must be used with --nphi.")
    p.add_argument("--nphi", type=int, help="Requested SHTns longitude count. Must be used with --nlat.")
    p.add_argument("--downsample-r", type=int, default=1)
    p.add_argument("--downsample-theta", type=int, default=1)
    p.add_argument("--downsample-phi", type=int, default=1)
    p.add_argument("--no-gradients", action="store_true", help="Do not export scalar gradients.")
    p.add_argument("--no-m0-fields", action="store_true", help="Do not export m=0-removed and phi-average variants.")
    p.add_argument("--no-parameter-prompt", action="store_true")

    p.add_argument("--Ek", "--E", dest="Ek", type=float)
    p.add_argument("--Pr", "--PrT", "--Pr_T", dest="Pr", type=float)
    p.add_argument("--Sc", "--PrC", "--Pr_C", dest="Sc", type=float)
    p.add_argument("--RaT", "--Ra", "--Ra_T", dest="RaT", type=float)
    p.add_argument("--RaC", "--Ra_C", dest="RaC", type=float)
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    paths = resolve_inputs(args)
    existing_paths = [str(p) for p in paths.values() if p is not None]

    print("XSHELLS input files:")
    for name, path in paths.items():
        print(f"  {name:12s}: {path if path is not None else '(not provided)'}")

    # Load first available field as the shared radial/spectral reference.
    reference_key = next(key for key, path in paths.items() if path is not None)
    reference = load_xshells_field(paths[reference_key])
    configure_sht_grid(reference, args.nlat, args.nphi)

    loaded: dict[str, Any] = {reference_key: reference}
    for key, path in paths.items():
        if path is None or key == reference_key:
            continue
        field = load_xshells_field(path, reference=reference)
        validate_field_compatibility(reference, field, key)
        loaded[key] = field

    r = np.asarray(reference.grid.r[reference.irs : reference.ire + 1], dtype=np.float64)
    theta = np.asarray(reference.theta_array(), dtype=np.float64)
    phi = np.asarray(reference.phi_array(), dtype=np.float64)
    time_values = [float(getattr(field, "time", np.nan)) for field in loaded.values()]
    time = next((v for v in time_values if np.isfinite(v)), float("nan"))

    print(
        f"Grid: nr={len(r)}, ntheta={len(theta)}, nphi={len(phi)}; "
        f"lmax={reference.lmax}, mmax={reference.mmax}, mres={reference.mres}, time={time:.8e}"
    )

    fields: dict[str, np.ndarray] = {}
    scalar_full: dict[str, np.ndarray] = {}

    velocity = loaded.get("velocity")
    if velocity is not None:
        if not isinstance(velocity, pyxshells.PolTor):
            raise TypeError("--velocity must be an XSHELLS poloidal/toroidal field.")
        print("Synthesizing velocity...")
        u = np.asarray(velocity.spat_full(), dtype=np.float64)
        Ur, Ut, Up = u[:, 0], u[:, 1], u[:, 2]
        fields.update({"ur": Ur, "ut": Ut, "up": Up, "Uabs": np.sqrt(Ur**2 + Ut**2 + Up**2)})
        if not args.no_m0_fields:
            fields.update({
                "ur_phiavg": phi_average_volume(Ur),
                "ut_phiavg": phi_average_volume(Ut),
                "up_phiavg": phi_average_volume(Up),
                "ur_nom0": remove_m0_phi(Ur),
                "ut_nom0": remove_m0_phi(Ut),
                "up_nom0": remove_m0_phi(Up),
            })

    magnetic = loaded.get("magnetic")
    if magnetic is not None:
        if not isinstance(magnetic, pyxshells.PolTor):
            raise TypeError("--magnetic must be an XSHELLS poloidal/toroidal field.")
        print("Synthesizing magnetic field...")
        b = np.asarray(magnetic.spat_full(), dtype=np.float64)
        Br, Bt, Bp = b[:, 0], b[:, 1], b[:, 2]
        fields.update({"Br": Br, "Bt": Bt, "Bp": Bp, "Babs": np.sqrt(Br**2 + Bt**2 + Bp**2)})
        if not args.no_m0_fields:
            fields.update({
                "Br_phiavg": phi_average_volume(Br),
                "Bt_phiavg": phi_average_volume(Bt),
                "Bp_phiavg": phi_average_volume(Bp),
                "Br_nom0": remove_m0_phi(Br),
                "Bt_nom0": remove_m0_phi(Bt),
                "Bp_nom0": remove_m0_phi(Bp),
            })

    temperature = loaded.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, pyxshells.ScalarSH):
            raise TypeError("--temperature must be an XSHELLS scalar field.")
        print("Synthesizing temperature...")
        T = np.asarray(temperature.spat_full(), dtype=np.float64)
        fields["T"] = T
        scalar_full["T"] = T
        if not args.no_m0_fields:
            fields["T_nom0"] = remove_m0_phi(T)
            fields["T_phiavg"] = phi_average_volume(T)

    composition = loaded.get("composition")
    if composition is not None:
        if not isinstance(composition, pyxshells.ScalarSH):
            raise TypeError("--composition must be an XSHELLS scalar field.")
        print("Synthesizing composition...")
        Comp = np.asarray(composition.spat_full(), dtype=np.float64)
        fields["Comp"] = Comp
        scalar_full["Comp"] = Comp
        if not args.no_m0_fields:
            fields["Comp_nom0"] = remove_m0_phi(Comp)
            fields["Comp_phiavg"] = phi_average_volume(Comp)

    gradients: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    if not args.no_gradients:
        for name, scalar in scalar_full.items():
            print(f"Computing gradients of {name}...")
            gr, gt, gp = gradient_scalar_3d(scalar, r, theta, phi)
            gradients[name] = (gr, gt, gp)
            fields[f"grad_r{name}_full"] = gr
            fields[f"grad_theta{name}_full"] = gt
            fields[f"grad_phi{name}_full"] = gp
            if not args.no_m0_fields:
                fields[f"grad_r{name}"] = remove_m0_phi(gr)
                fields[f"grad_theta{name}"] = remove_m0_phi(gt)
                fields[f"grad_phi{name}"] = remove_m0_phi(gp)

    prompt_missing = not args.no_parameter_prompt
    Ek = resolve_parameter(args.Ek, existing_paths, ("Ek", "E"), "Ek", "Ekman number", prompt_missing)
    Pr = resolve_parameter(args.Pr, existing_paths, ("Pr", "PrT", "Pr_T"), "Pr", "thermal Prandtl number", prompt_missing)
    Sc = resolve_parameter(args.Sc, existing_paths, ("Sc", "PrC", "Pr_C"), "Sc", "compositional Prandtl/Schmidt number", prompt_missing)
    RaT = resolve_parameter(args.RaT, existing_paths, ("RaT", "Ra_T", "Ra"), "RaT", "thermal Rayleigh number", prompt_missing)
    RaC = resolve_parameter(args.RaC, existing_paths, ("RaC", "Ra_C"), "RaC", "compositional Rayleigh number", prompt_missing)

    # Compute N2 only when at least one scalar radial gradient and all required scaling values exist.
    grad_rT = gradients.get("T", (None, None, None))[0]
    grad_rComp = gradients.get("Comp", (None, None, None))[0]
    can_n2 = np.isfinite(Ek) and (
        (grad_rT is not None and np.isfinite(Pr) and np.isfinite(RaT))
        or (grad_rComp is not None and np.isfinite(Sc) and np.isfinite(RaC))
    )
    N2_full = None
    if can_n2:
        N2_full = np.zeros_like(next(x for x in (grad_rT, grad_rComp) if x is not None))
        if grad_rT is not None and np.isfinite(Pr) and np.isfinite(RaT):
            N2_full += r[:, None, None] * Ek**2 * grad_rT * RaT / Pr
        if grad_rComp is not None and np.isfinite(Sc) and np.isfinite(RaC):
            N2_full += r[:, None, None] * Ek**2 * grad_rComp * RaC / Sc
        fields["N2_full"] = N2_full
        if not args.no_m0_fields:
            fields["N2"] = remove_m0_phi(N2_full)
    else:
        print("N2 not generated: provide scalar field(s) and finite Ek/Ra/Pr or Ek/RaC/Sc values.")

    dr = max(1, int(args.downsample_r))
    dt = max(1, int(args.downsample_theta))
    dp = max(1, int(args.downsample_phi))
    if (dr, dt, dp) != (1, 1, 1):
        print(f"Downsampling r/theta/phi by {dr}/{dt}/{dp}")
        fields = {name: downsample(arr, dr, dt, dp) for name, arr in fields.items()}
    r_out, theta_out, phi_out = r[::dr], theta[::dt], phi[::dp]

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for old in outdir.glob("*_volume.f32"):
        old.unlink()
    for old_name in ("metadata.json", "coordinates.json", "profiles.json"):
        old = outdir / old_name
        if old.exists():
            old.unlink()

    field_files: dict[str, str] = {}
    ranges: dict[str, dict[str, float]] = {}
    print(f"Writing viewer fields to {outdir}...")
    for name, arr in fields.items():
        filename = f"{name}_volume.f32"
        ranges[name] = write_f32(outdir / filename, arr)
        field_files[name] = filename
        print(f"  {name:20s} {arr.shape} -> {filename}")

    coordinates = {
        "r": [json_number(x) for x in r_out],
        "theta": [json_number(x) for x in theta_out],
        "phi": [json_number(x) for x in phi_out],
    }
    with open(outdir / "coordinates.json", "w", encoding="utf-8") as stream:
        json.dump(coordinates, stream, allow_nan=False)

    profiles: dict[str, Any] = {"r": [json_number(x) for x in r_out]}
    if N2_full is not None:
        n2_profile = np.mean(N2_full, axis=(1, 2))[::dr]
        profiles["N2"] = [json_number(x) for x in n2_profile]
    with open(outdir / "profiles.json", "w", encoding="utf-8") as stream:
        json.dump(profiles, stream, allow_nan=False)

    has_magnetic = magnetic is not None and "Babs" in fields and ranges["Babs"]["absmax"] > 0.0
    source_map = {key: str(path) if path is not None else None for key, path in paths.items()}
    title = f"XSHELLS, t={time:.3e}, lmax={reference.lmax}, mmax={reference.mmax}"
    metadata = {
        "description": "Converted physical-space quantities from XSHELLS field files using pyxshells.",
        "source_format": "xshells",
        "source_fields": source_map,
        "time": json_number(time),
        "parameters": {
            "Ek": json_number(Ek),
            "Pr": json_number(Pr),
            "Sc": json_number(Sc),
            "RaT": json_number(RaT),
            "RaC": json_number(RaC),
        },
        "spectral": {
            "lmax": int(reference.lmax),
            "mmax": int(reference.mmax),
            "mres": int(reference.mres),
            "nlat": int(len(theta)),
            "nphi": int(len(phi)),
            "library": "pyxshells/SHTns",
        },
        "magnetic": {
            "has_magnetic_field": bool(has_magnetic),
            "classification": "magnetic" if has_magnetic else "non_magnetic",
        },
        "title": title,
        "nr": int(len(r_out)),
        "ntheta": int(len(theta_out)),
        "nphi": int(len(phi_out)),
        "r_inner": json_number(r_out[0]),
        "r_outer": json_number(r_out[-1]),
        "has_inner_core": bool(float(r_out[0]) > 0.0),
        "layout": "r_theta_phi",
        "endianness": "little",
        "theta_min": json_number(theta_out[0]),
        "theta_max": json_number(theta_out[-1]),
        "phi_min": json_number(phi_out[0]),
        "phi_max": json_number(phi_out[-1]),
        "fields": field_files,
        "surface_fields": {},
        "ranges": ranges,
        "coordinates": "coordinates.json",
        "profiles": "profiles.json",
        "field_lines": {},
    }
    with open(outdir / "metadata.json", "w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2, allow_nan=False)

    print("Done.")
    print(f"Viewer data written to: {outdir.resolve()}")
    print(f"Fields: {', '.join(field_files)}")


if __name__ == "__main__":
    main()
