#!/usr/bin/env python3
"""Convert XSHELLS field files to Dynamo Three Viewer data.

XSHELLS commonly stores one snapshot in separate files::

    fieldU.<tag>   velocity (poloidal/toroidal; fluid shell)
    fieldB.<tag>   magnetic field (poloidal/toroidal; may include solid conductors)
    fieldT.<tag>   temperature scalar (usually fluid shell)
    fieldC.<tag>   composition/concentration scalar (usually fluid shell)

A conducting inner core is supported.  In that case the magnetic field can have
a wider radial domain than velocity and scalar fields.  The converter uses the
magnetic radial grid as the viewer grid, retains B throughout the inner core,
and embeds shell-only quantities as zero outside their native radial domain.
The actual ICB radius and radial index are stored in metadata.json.

Requires: numpy, shtns, pyxshells
"""

from __future__ import annotations

import argparse
import json
import math
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


RADIAL_ATOL = 1.0e-11


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
    values = np.asarray(arr)
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    values = np.ascontiguousarray(values.astype("<f4", copy=False))
    values.tofile(path)
    return finite_range(values)


def remove_m0_phi(arr: np.ndarray) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float64)
    return values - np.mean(values, axis=2, keepdims=True)


def phi_average_volume(arr: np.ndarray) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float64)
    mean = np.mean(values, axis=2, keepdims=True)
    return np.broadcast_to(mean, values.shape).copy()


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

    nphi = f.shape[2]
    if nphi < 2:
        d_dphi = np.zeros_like(f)
    else:
        dphi = 2.0 * np.pi / nphi
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


def load_xshells_field(path: Path, angular_reference: Any | None = None) -> Any:
    # Share only the SHTns angular transform.  Do not share the radial grid:
    # fieldB may include a conducting inner core while fieldU/T/C are shell-only.
    kwargs: dict[str, Any] = {"lazy": True}
    if angular_reference is not None:
        kwargs["sht"] = angular_reference.sht
    return pyxshells.load_field(str(path), **kwargs)


def field_radii(field: Any) -> np.ndarray:
    r = np.asarray(field.grid.r[field.irs : field.ire + 1], dtype=np.float64)
    if r.ndim != 1 or r.size == 0:
        raise ValueError("XSHELLS field has an empty or invalid radial grid.")
    if np.any(np.diff(r) <= 0.0):
        raise ValueError("XSHELLS radial coordinates must be strictly increasing.")
    return r


def validate_angular_compatibility(reference: Any, field: Any, label: str) -> None:
    ref_spec = (reference.lmax, reference.mmax, reference.mres)
    field_spec = (field.lmax, field.mmax, field.mres)
    if field_spec != ref_spec:
        raise ValueError(
            f"{label} spectral truncation {field_spec} does not match reference {ref_spec}."
        )


def choose_master_field(loaded: dict[str, Any]) -> tuple[str, Any]:
    # A magnetic field is the natural master because XSHELLS allows it to extend
    # into conducting solid layers beyond the velocity/scalar domain.
    if "magnetic" in loaded:
        return "magnetic", loaded["magnetic"]
    key = max(
        loaded,
        key=lambda name: (
            field_radii(loaded[name])[-1] - field_radii(loaded[name])[0],
            field_radii(loaded[name]).size,
        ),
    )
    return key, loaded[key]


def radial_remap_to_master(
    arr: np.ndarray,
    r_src: np.ndarray,
    r_master: np.ndarray,
    *,
    outside_value: float = 0.0,
) -> np.ndarray:
    """Map an ``(r,theta,phi)`` array to the master radial grid.

    The fast path embeds an exact contiguous subset, which is the normal XSHELLS
    conducting-inner-core layout.  A linear interpolation fallback handles
    compatible but non-identical radial grids.
    """
    values = np.asarray(arr)
    if values.shape[0] != len(r_src):
        raise ValueError(
            f"Radial array length {values.shape[0]} does not match source grid length {len(r_src)}."
        )

    if len(r_src) == len(r_master) and np.allclose(r_src, r_master, rtol=0.0, atol=RADIAL_ATOL):
        return np.ascontiguousarray(values.astype(np.float32, copy=False))

    out_shape = (len(r_master),) + values.shape[1:]
    out = np.full(out_shape, outside_value, dtype=np.float32)

    i0 = int(np.searchsorted(r_master, r_src[0] - RADIAL_ATOL, side="left"))
    i1 = i0 + len(r_src)
    if i1 <= len(r_master):
        candidate = r_master[i0:i1]
        if candidate.shape == r_src.shape and np.allclose(candidate, r_src, rtol=0.0, atol=RADIAL_ATOL):
            out[i0:i1] = values.astype(np.float32, copy=False)
            return np.ascontiguousarray(out)

    inside = (r_master >= r_src[0] - RADIAL_ATOL) & (r_master <= r_src[-1] + RADIAL_ATOL)
    targets = r_master[inside]
    if targets.size == 0:
        raise ValueError(
            f"Source radial domain [{r_src[0]}, {r_src[-1]}] does not overlap master "
            f"domain [{r_master[0]}, {r_master[-1]}]."
        )

    hi = np.searchsorted(r_src, targets, side="left")
    hi = np.clip(hi, 0, len(r_src) - 1)
    lo = np.maximum(hi - 1, 0)
    exact = np.isclose(r_src[hi], targets, rtol=0.0, atol=RADIAL_ATOL)
    lo[exact] = hi[exact]

    denom = r_src[hi] - r_src[lo]
    weight = np.zeros_like(targets)
    moving = np.abs(denom) > RADIAL_ATOL
    weight[moving] = (targets[moving] - r_src[lo[moving]]) / denom[moving]
    reshape = (len(targets),) + (1,) * (values.ndim - 1)
    w = weight.reshape(reshape)
    interp = (1.0 - w) * values[lo] + w * values[hi]
    out[inside] = interp.astype(np.float32, copy=False)
    return np.ascontiguousarray(out)


def sanitise_synthesised_field(arr: np.ndarray, r: np.ndarray, label: str) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float64)
    bad = ~np.isfinite(values)
    nbad = int(np.count_nonzero(bad))
    if nbad:
        centre_bad = bool(abs(r[0]) <= RADIAL_ATOL and np.any(bad[0]))
        if centre_bad:
            # Spherical components are undefined at the single coordinate r=0.
            # Setting only that layer to zero preserves all conducting-IC data at r>0.
            values[0] = 0.0
            bad = ~np.isfinite(values)
        remaining = int(np.count_nonzero(bad))
        if remaining:
            print(f"Warning: replacing {remaining} non-finite values in {label} with zero.")
            values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
        if centre_bad:
            print(f"  {label}: set the singular r=0 spherical-component layer to zero.")
    return values


def downsample(arr: np.ndarray, dr: int, dt: int, dp: int) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(arr)[::dr, ::dt, ::dp])


def nearest_index(values: np.ndarray, target: float) -> int:
    return int(np.argmin(np.abs(np.asarray(values, dtype=np.float64) - float(target))))


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

    load_order = [key for key in ("magnetic", "velocity", "temperature", "composition") if paths[key] is not None]
    angular_key = load_order[0]
    angular_reference = load_xshells_field(paths[angular_key])
    configure_sht_grid(angular_reference, args.nlat, args.nphi)

    loaded: dict[str, Any] = {angular_key: angular_reference}
    for key in load_order[1:]:
        field = load_xshells_field(paths[key], angular_reference=angular_reference)
        validate_angular_compatibility(angular_reference, field, key)
        loaded[key] = field

    theta = np.asarray(angular_reference.theta_array(), dtype=np.float64)
    phi = np.asarray(angular_reference.phi_array(), dtype=np.float64)
    time_values = [float(getattr(field, "time", np.nan)) for field in loaded.values()]
    time = next((v for v in time_values if np.isfinite(v)), float("nan"))

    radial_grids = {key: field_radii(field) for key, field in loaded.items()}
    print("Radial domains:")
    for key in load_order:
        rr = radial_grids[key]
        print(f"  {key:12s}: nr={len(rr):4d}, r=[{rr[0]:.12g}, {rr[-1]:.12g}]")

    master_key, master_field = choose_master_field(loaded)
    r_master = radial_grids[master_key]
    print(
        f"Viewer master grid: {master_key}; nr={len(r_master)}, ntheta={len(theta)}, nphi={len(phi)}; "
        f"lmax={angular_reference.lmax}, mmax={angular_reference.mmax}, "
        f"mres={angular_reference.mres}, time={time:.8e}"
    )

    shell_key = next((key for key in ("velocity", "temperature", "composition") if key in loaded), master_key)
    r_shell = radial_grids[shell_key]
    r_icb = float(r_shell[0])
    magnetic_r = radial_grids.get("magnetic")
    has_conducting_inner_core = bool(
        magnetic_r is not None and magnetic_r[0] < r_icb - RADIAL_ATOL and r_icb > RADIAL_ATOL
    )
    if has_conducting_inner_core:
        print(
            f"Conducting inner core detected: B extends to r={magnetic_r[0]:.12g}; "
            f"fluid shell begins at r_icb={r_icb:.12g}."
        )

    # Native arrays retain their own radial grids until all derivatives are computed.
    native_fields: dict[str, tuple[np.ndarray, np.ndarray, str]] = {}

    def register(name: str, arr: np.ndarray, r_native: np.ndarray, source_key: str) -> None:
        native_fields[name] = (np.asarray(arr, dtype=np.float32), r_native, source_key)

    velocity = loaded.get("velocity")
    if velocity is not None:
        if not isinstance(velocity, pyxshells.PolTor):
            raise TypeError("--velocity must be an XSHELLS poloidal/toroidal field.")
        print("Synthesizing velocity...")
        with np.errstate(divide="ignore", invalid="ignore"):
            u = np.asarray(velocity.spat_full(), dtype=np.float64)
        ru = radial_grids["velocity"]
        u = sanitise_synthesised_field(u, ru, "velocity")
        Ur, Ut, Up = u[:, 0], u[:, 1], u[:, 2]
        register("ur", Ur, ru, "velocity")
        register("ut", Ut, ru, "velocity")
        register("up", Up, ru, "velocity")
        register("Uabs", np.sqrt(Ur**2 + Ut**2 + Up**2), ru, "velocity")
        if not args.no_m0_fields:
            register("ur_phiavg", phi_average_volume(Ur), ru, "velocity")
            register("ut_phiavg", phi_average_volume(Ut), ru, "velocity")
            register("up_phiavg", phi_average_volume(Up), ru, "velocity")
            register("ur_nom0", remove_m0_phi(Ur), ru, "velocity")
            register("ut_nom0", remove_m0_phi(Ut), ru, "velocity")
            register("up_nom0", remove_m0_phi(Up), ru, "velocity")

    magnetic = loaded.get("magnetic")
    if magnetic is not None:
        if not isinstance(magnetic, pyxshells.PolTor):
            raise TypeError("--magnetic must be an XSHELLS poloidal/toroidal field.")
        print("Synthesizing magnetic field, including conducting solid regions...")
        with np.errstate(divide="ignore", invalid="ignore"):
            b = np.asarray(magnetic.spat_full(), dtype=np.float64)
        rb = radial_grids["magnetic"]
        b = sanitise_synthesised_field(b, rb, "magnetic field")
        Br, Bt, Bp = b[:, 0], b[:, 1], b[:, 2]
        register("Br", Br, rb, "magnetic")
        register("Bt", Bt, rb, "magnetic")
        register("Bp", Bp, rb, "magnetic")
        register("Babs", np.sqrt(Br**2 + Bt**2 + Bp**2), rb, "magnetic")
        if not args.no_m0_fields:
            register("Br_phiavg", phi_average_volume(Br), rb, "magnetic")
            register("Bt_phiavg", phi_average_volume(Bt), rb, "magnetic")
            register("Bp_phiavg", phi_average_volume(Bp), rb, "magnetic")
            register("Br_nom0", remove_m0_phi(Br), rb, "magnetic")
            register("Bt_nom0", remove_m0_phi(Bt), rb, "magnetic")
            register("Bp_nom0", remove_m0_phi(Bp), rb, "magnetic")

    scalar_native: dict[str, tuple[np.ndarray, np.ndarray, str]] = {}

    temperature = loaded.get("temperature")
    if temperature is not None:
        if not isinstance(temperature, pyxshells.ScalarSH):
            raise TypeError("--temperature must be an XSHELLS scalar field.")
        print("Synthesizing temperature...")
        with np.errstate(divide="ignore", invalid="ignore"):
            T = np.asarray(temperature.spat_full(), dtype=np.float64)
        rt = radial_grids["temperature"]
        T = sanitise_synthesised_field(T, rt, "temperature")
        scalar_native["T"] = (T, rt, "temperature")
        register("T", T, rt, "temperature")
        if not args.no_m0_fields:
            register("T_nom0", remove_m0_phi(T), rt, "temperature")
            register("T_phiavg", phi_average_volume(T), rt, "temperature")

    composition = loaded.get("composition")
    if composition is not None:
        if not isinstance(composition, pyxshells.ScalarSH):
            raise TypeError("--composition must be an XSHELLS scalar field.")
        print("Synthesizing composition...")
        with np.errstate(divide="ignore", invalid="ignore"):
            Comp = np.asarray(composition.spat_full(), dtype=np.float64)
        rc = radial_grids["composition"]
        Comp = sanitise_synthesised_field(Comp, rc, "composition")
        scalar_native["Comp"] = (Comp, rc, "composition")
        register("Comp", Comp, rc, "composition")
        if not args.no_m0_fields:
            register("Comp_nom0", remove_m0_phi(Comp), rc, "composition")
            register("Comp_phiavg", phi_average_volume(Comp), rc, "composition")

    gradients: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]] = {}
    if not args.no_gradients:
        for name, (scalar, rr, source_key) in scalar_native.items():
            print(f"Computing gradients of {name} on its native shell grid...")
            gr, gt, gp = gradient_scalar_3d(scalar, rr, theta, phi)
            gradients[name] = (gr, gt, gp, rr, source_key)
            register(f"grad_r{name}_full", gr, rr, source_key)
            register(f"grad_theta{name}_full", gt, rr, source_key)
            register(f"grad_phi{name}_full", gp, rr, source_key)
            if not args.no_m0_fields:
                register(f"grad_r{name}", remove_m0_phi(gr), rr, source_key)
                register(f"grad_theta{name}", remove_m0_phi(gt), rr, source_key)
                register(f"grad_phi{name}", remove_m0_phi(gp), rr, source_key)

    prompt_missing = not args.no_parameter_prompt
    Ek = resolve_parameter(args.Ek, existing_paths, ("Ek", "E"), "Ek", "Ekman number", prompt_missing)
    Pr = resolve_parameter(args.Pr, existing_paths, ("Pr", "PrT", "Pr_T"), "Pr", "thermal Prandtl number", prompt_missing)
    Sc = resolve_parameter(args.Sc, existing_paths, ("Sc", "PrC", "Pr_C"), "Sc", "compositional Prandtl/Schmidt number", prompt_missing)
    RaT = resolve_parameter(args.RaT, existing_paths, ("RaT", "Ra_T", "Ra"), "RaT", "thermal Rayleigh number", prompt_missing)
    RaC = resolve_parameter(args.RaC, existing_paths, ("RaC", "Ra_C"), "RaC", "compositional Rayleigh number", prompt_missing)

    grad_t = gradients.get("T")
    grad_c = gradients.get("Comp")
    can_n2 = np.isfinite(Ek) and (
        (grad_t is not None and np.isfinite(Pr) and np.isfinite(RaT))
        or (grad_c is not None and np.isfinite(Sc) and np.isfinite(RaC))
    )
    n2_native: tuple[np.ndarray, np.ndarray] | None = None
    if can_n2:
        # Use the widest available scalar grid, remapping the other scalar gradient if needed.
        available = [item for item in (grad_t, grad_c) if item is not None]
        n2_ref = max(available, key=lambda item: (item[3][-1] - item[3][0], len(item[3])))
        r_n2 = n2_ref[3]
        shape = (len(r_n2), len(theta), len(phi))
        N2_full = np.zeros(shape, dtype=np.float32)
        if grad_t is not None and np.isfinite(Pr) and np.isfinite(RaT):
            grt = radial_remap_to_master(grad_t[0], grad_t[3], r_n2)
            N2_full += r_n2[:, None, None].astype(np.float32) * np.float32(Ek**2 * RaT / Pr) * grt
        if grad_c is not None and np.isfinite(Sc) and np.isfinite(RaC):
            grc = radial_remap_to_master(grad_c[0], grad_c[3], r_n2)
            N2_full += r_n2[:, None, None].astype(np.float32) * np.float32(Ek**2 * RaC / Sc) * grc
        register("N2_full", N2_full, r_n2, "scalar_shell")
        if not args.no_m0_fields:
            register("N2", remove_m0_phi(N2_full), r_n2, "scalar_shell")
        n2_native = (N2_full, r_n2)
    else:
        print("N2 not generated: provide scalar field(s) and finite Ek/Ra/Pr or Ek/RaC/Sc values.")

    print(f"Mapping all fields to the {master_key} radial grid...")
    fields: dict[str, np.ndarray] = {}
    field_domains: dict[str, dict[str, Any]] = {}
    for name, (arr, rr, source_key) in native_fields.items():
        fields[name] = radial_remap_to_master(arr, rr, r_master, outside_value=0.0)
        field_domains[name] = {
            "source": source_key,
            "r_min": json_number(rr[0]),
            "r_max": json_number(rr[-1]),
            "outside_native_domain": "zero",
        }

    dr = max(1, int(args.downsample_r))
    dt = max(1, int(args.downsample_theta))
    dp = max(1, int(args.downsample_phi))
    if (dr, dt, dp) != (1, 1, 1):
        print(f"Downsampling r/theta/phi by {dr}/{dt}/{dp}")
        fields = {name: downsample(arr, dr, dt, dp) for name, arr in fields.items()}
    r_out, theta_out, phi_out = r_master[::dr], theta[::dt], phi[::dp]
    icb_index = nearest_index(r_out, r_icb)

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
    if n2_native is not None:
        n2_on_master = radial_remap_to_master(n2_native[0], n2_native[1], r_master)
        n2_profile = np.mean(n2_on_master, axis=(1, 2))[::dr]
        profiles["N2"] = [json_number(x) for x in n2_profile]
    with open(outdir / "profiles.json", "w", encoding="utf-8") as stream:
        json.dump(profiles, stream, allow_nan=False)

    has_magnetic = magnetic is not None and "Babs" in fields and ranges["Babs"]["absmax"] > 0.0
    source_map = {key: str(path) if path is not None else None for key, path in paths.items()}
    radial_domains = {
        key: {
            "nr": int(len(rr)),
            "r_min": json_number(rr[0]),
            "r_max": json_number(rr[-1]),
        }
        for key, rr in radial_grids.items()
    }
    title = f"XSHELLS, t={time:.3e}, lmax={angular_reference.lmax}, mmax={angular_reference.mmax}"
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
            "lmax": int(angular_reference.lmax),
            "mmax": int(angular_reference.mmax),
            "mres": int(angular_reference.mres),
            "nlat": int(len(theta)),
            "nphi": int(len(phi)),
            "library": "pyxshells/SHTns",
        },
        "magnetic": {
            "has_magnetic_field": bool(has_magnetic),
            "classification": "magnetic" if has_magnetic else "non_magnetic",
            "has_conducting_inner_core": has_conducting_inner_core,
        },
        "title": title,
        "nr": int(len(r_out)),
        "ntheta": int(len(theta_out)),
        "nphi": int(len(phi_out)),
        "r_inner": json_number(r_out[0]),
        "r_outer": json_number(r_out[-1]),
        "r_icb": json_number(r_icb),
        "icb_radius": json_number(r_icb),
        "icb_index": int(icb_index),
        "r_fluid_inner": json_number(r_icb),
        "has_inner_core": bool(r_icb > r_out[0] + RADIAL_ATOL),
        "has_conducting_inner_core": has_conducting_inner_core,
        "master_radial_field": master_key,
        "radial_domains": radial_domains,
        "field_domains": field_domains,
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
    print(f"ICB: r={r_icb:.12g}, output radial index={icb_index}")
    print(f"Fields: {', '.join(field_files)}")


if __name__ == "__main__":
    main()
