#!/usr/bin/env python3
"""Convert MagIC ``G_#.TAG`` graphic snapshots to DEEPscope viewer data.

The official MagIC ``MagicGraph`` reader is used for the binary format.  MagIC
stores physical arrays as ``(phi_sector, theta, radius)``; this converter
unfolds ``minc`` symmetry and writes little-endian C-order ``(r, theta, phi)``
arrays, matching the Leeds and XSHELLS converter contract.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.special import gammaln, lpmv

try:
    from convert_state_to_viewer import (
        choose_regular_seed_grid,
        compute_emf,
        compute_external_field_lines_from_cmb,
        compute_helicity,
        compute_induction_from_emf,
        compute_shell_field_lines_from_cmb,
        gradient_scalar_3d,
    )
except ImportError:  # pragma: no cover - package-style invocation
    from tools.convert_state_to_viewer import (
        choose_regular_seed_grid,
        compute_emf,
        compute_external_field_lines_from_cmb,
        compute_helicity,
        compute_induction_from_emf,
        compute_shell_field_lines_from_cmb,
        gradient_scalar_3d,
    )


EARTH_RADIUS_KM = 6371.0
CMB_RADIUS_KM = 3480.0
DEFAULT_EARTH_RADIUS_SCALE = EARTH_RADIUS_KM / CMB_RADIUS_KM
DEFAULT_EARTH_BR_LMAX = 13
RADIAL_ATOL = 1.0e-10
CONVERTER_PACKAGE_VERSION = "3.2.0"


def json_number(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(np.asarray(value).item())
    except Exception:
        return default
    return out if math.isfinite(out) else default


def finite_range(arr: np.ndarray) -> dict[str, float]:
    values = np.asarray(arr, dtype=np.float64)
    good = values[np.isfinite(values)]
    if good.size == 0:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "absmax": 0.0}
    amin, amax = float(np.min(good)), float(np.max(good))
    return {
        "min": amin,
        "max": amax,
        "mean": float(np.mean(good)),
        "absmax": max(abs(amin), abs(amax)),
    }


def write_f32(path: Path, arr: np.ndarray) -> dict[str, float]:
    values = np.nan_to_num(np.asarray(arr), nan=0.0, posinf=0.0, neginf=0.0)
    values = np.ascontiguousarray(values.astype("<f4", copy=False))
    values.tofile(path)
    return finite_range(values)


def remove_m0_phi(arr: np.ndarray) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float64)
    return values - np.mean(values, axis=2, keepdims=True)


def phi_average_volume(arr: np.ndarray) -> np.ndarray:
    values = np.asarray(arr, dtype=np.float64)
    return np.broadcast_to(np.mean(values, axis=2, keepdims=True), values.shape).copy()


def nearest_index(values: np.ndarray, target: float) -> int:
    return int(np.argmin(np.abs(np.asarray(values, dtype=np.float64) - float(target))))


def radial_remap_to_master(
    arr: np.ndarray,
    r_src: np.ndarray,
    r_master: np.ndarray,
    *,
    outside_value: float = 0.0,
) -> np.ndarray:
    """Map ``(r,theta,phi)`` data onto a master radius, zero outside its domain."""
    values = np.asarray(arr)
    rs = np.asarray(r_src, dtype=np.float64)
    rm = np.asarray(r_master, dtype=np.float64)
    if values.shape[0] != rs.size:
        raise ValueError("Field radial dimension does not match its coordinate array.")
    if rs.size == rm.size and np.allclose(rs, rm, rtol=0.0, atol=RADIAL_ATOL):
        return np.ascontiguousarray(values.astype(np.float32, copy=False))

    out = np.full((rm.size,) + values.shape[1:], outside_value, dtype=np.float32)
    inside = (rm >= rs[0] - RADIAL_ATOL) & (rm <= rs[-1] + RADIAL_ATOL)
    targets = rm[inside]
    if not targets.size:
        raise ValueError("Native and master radial domains do not overlap.")
    hi = np.clip(np.searchsorted(rs, targets, side="left"), 0, rs.size - 1)
    lo = np.maximum(hi - 1, 0)
    exact = np.isclose(rs[hi], targets, rtol=0.0, atol=RADIAL_ATOL)
    lo[exact] = hi[exact]
    denom = rs[hi] - rs[lo]
    weight = np.zeros_like(targets)
    moving = np.abs(denom) > RADIAL_ATOL
    weight[moving] = (targets[moving] - rs[lo[moving]]) / denom[moving]
    w = weight.reshape((targets.size,) + (1,) * (values.ndim - 1))
    out[inside] = ((1.0 - w) * values[lo] + w * values[hi]).astype(np.float32)
    return np.ascontiguousarray(out)


def _add_magic_python_path(path: str | None) -> None:
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path).expanduser())
    magic_home = os.environ.get("MAGIC_HOME")
    if magic_home:
        candidates.append(Path(magic_home).expanduser() / "python")
    for candidate in candidates:
        if candidate.name == "magic" and (candidate / "graph.py").is_file():
            candidate = candidate.parent
        if (candidate / "magic" / "graph.py").is_file():
            resolved = str(candidate.resolve())
            if resolved not in sys.path:
                sys.path.insert(0, resolved)
            return
    if path:
        raise FileNotFoundError(
            f"Could not find magic/graph.py below --magic-python-dir={path!r}. "
            "Give MagIC's python directory (normally $MAGIC_HOME/python)."
        )


def import_magic_graph(magic_python_dir: str | None) -> Any:
    _add_magic_python_path(magic_python_dir)
    try:
        from magic import MagicGraph
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "Could not import the official MagIC Python package. Set MAGIC_HOME "
            "or use --magic-python-dir /path/to/magic/python."
        ) from exc
    return MagicGraph


GRAPH_RE = re.compile(r"^G_(?P<ivar>\d+|ave)(?:\.(?P<tag>.+))?$")


def parse_graph_filename(path: Path) -> tuple[int | None, str | None, bool]:
    match = GRAPH_RE.match(path.name)
    if not match:
        raise ValueError(
            f"{path.name!r} is not a MagIC graphic filename. Expected G_<number>.TAG "
            "or G_ave.TAG."
        )
    value = match.group("ivar")
    return (None if value == "ave" else int(value), match.group("tag"), value == "ave")


def discover_graph(folder: Path, tag: str | None, ivar: int | None, average: bool) -> Path:
    if not folder.is_dir():
        raise FileNotFoundError(f"MagIC folder does not exist: {folder}")
    if average:
        pattern = f"G_ave.{tag}" if tag else "G_ave*"
    elif ivar is not None:
        pattern = f"G_{ivar}.{tag}" if tag else f"G_{ivar}*"
    else:
        pattern = f"G_[0-9]*.{tag}" if tag else "G_[0-9]*"
    candidates = [p for p in folder.glob(pattern) if p.is_file() and GRAPH_RE.match(p.name)]
    if not candidates:
        raise FileNotFoundError(f"No MagIC graphic file matching {pattern!r} in {folder}")
    if ivar is None and not average:
        candidates.sort(key=lambda p: (parse_graph_filename(p)[0] or -1, p.stat().st_mtime))
    else:
        candidates.sort(key=lambda p: p.stat().st_mtime)
    return candidates[-1]


def load_graph(path: Path, magic_python_dir: str | None, precision: str) -> Any:
    MagicGraph = import_magic_graph(magic_python_dir)
    ivar, tag, average = parse_graph_filename(path)
    dtype = np.float64 if precision == "float64" else np.float32
    graph = MagicGraph(
        ivar=ivar,
        tag=tag,
        ave=average,
        datadir=str(path.parent),
        quiet=False,
        precision=dtype,
    )
    for required in ("radius", "colatitude", "vr", "vtheta", "vphi"):
        if not hasattr(graph, required):
            raise ValueError(f"MagIC reader did not provide required field {required!r}.")
    return graph


def unfold_magic_array(
    arr: np.ndarray,
    radial_order: np.ndarray,
    theta_order: np.ndarray,
    minc: int,
) -> np.ndarray:
    """Convert MagIC ``(phi-sector,theta,r)`` to full ``(r,theta,phi)``."""
    values = np.asarray(arr)
    if values.ndim != 3:
        raise ValueError(f"Expected a 3-D MagIC field, got shape {values.shape}.")
    values = values[:, theta_order, :]
    values = values[:, :, radial_order]
    values = np.transpose(values, (2, 1, 0))
    if int(minc) > 1:
        values = np.tile(values, (1, 1, int(minc)))
    return np.ascontiguousarray(values.astype(np.float64, copy=False))


def adapt_graph(graph: Any) -> dict[str, Any]:
    """Extract coordinates and consistently oriented physical fields."""
    radius = np.asarray(graph.radius, dtype=np.float64)
    theta = np.asarray(graph.colatitude, dtype=np.float64)
    if radius.ndim != 1 or theta.ndim != 1 or radius.size < 2 or theta.size < 2:
        raise ValueError("MagIC radius/colatitude coordinates are invalid.")
    radial_order = np.argsort(radius)
    theta_order = np.argsort(theta)
    radius = radius[radial_order]
    theta = theta[theta_order]
    if np.any(np.diff(radius) <= 0.0) or np.any(np.diff(theta) <= 0.0):
        raise ValueError("MagIC coordinates must be strictly monotonic after sorting.")

    minc = max(1, int(getattr(graph, "minc", 1)))
    nphi_sector = np.asarray(graph.vr).shape[0]
    nphi = nphi_sector * minc
    phi = np.linspace(0.0, 2.0 * np.pi, nphi, endpoint=False, dtype=np.float64)

    names = {
        "ur": "vr",
        "ut": "vtheta",
        "up": "vphi",
        "C": "entropy",
        "Comp": "xi",
        "Phase": "phase",
        "P": "pre",
        "Br": "Br",
        "Bt": "Btheta",
        "Bp": "Bphi",
    }
    fields: dict[str, np.ndarray] = {}
    for target, source in names.items():
        if hasattr(graph, source):
            candidate = np.asarray(getattr(graph, source))
            if candidate.shape == np.asarray(graph.vr).shape:
                fields[target] = unfold_magic_array(candidate, radial_order, theta_order, minc)

    result: dict[str, Any] = {
        "r_shell": radius,
        "r_master": radius,
        "theta": theta,
        "phi": phi,
        "fields": fields,
        "minc": minc,
        "has_conducting_inner_core": False,
        "magnetic_extends_inner_core": False,
    }

    if all(hasattr(graph, name) for name in ("radius_ic", "Br_ic", "Btheta_ic", "Bphi_ic")):
        radius_ic = np.asarray(graph.radius_ic, dtype=np.float64)
        valid = np.isfinite(radius_ic) & (radius_ic >= 0.0) & (radius_ic <= radius[-1] + RADIAL_ATOL)
        radius_ic = radius_ic[valid]
        if radius_ic.size:
            ic_order_all = np.flatnonzero(valid)[np.argsort(radius_ic)]
            radius_ic = np.asarray(graph.radius_ic, dtype=np.float64)[ic_order_all]
            keep = np.ones(radius_ic.size, dtype=bool)
            keep[1:] = np.diff(radius_ic) > RADIAL_ATOL
            radius_ic = radius_ic[keep]
            ic_order = ic_order_all[keep]
            inner_fields: dict[str, np.ndarray] = {}
            for target, source in (("Br", "Br_ic"), ("Bt", "Btheta_ic"), ("Bp", "Bphi_ic")):
                raw = np.asarray(getattr(graph, source))
                if raw.ndim == 3 and raw.shape[2] >= int(np.max(ic_order)) + 1:
                    inner_fields[target] = unfold_magic_array(
                        raw[:, :, ic_order], np.arange(radius_ic.size), theta_order, minc
                    )
            inner_only = radius_ic < radius[0] - RADIAL_ATOL
            if inner_fields and np.any(inner_only):
                r_inner = radius_ic[inner_only]
                result["r_master"] = np.concatenate((r_inner, radius))
                for name in ("Br", "Bt", "Bp"):
                    if name in fields and name in inner_fields:
                        fields[name] = np.concatenate((inner_fields[name][inner_only], fields[name]), axis=0)
                result["magnetic_extends_inner_core"] = True
                result["has_conducting_inner_core"] = bool(
                    abs(float(getattr(graph, "sigma", 0.0))) > 0.0
                )
                result["r_inner_magnetic"] = r_inner

    return result


def _angular_weights(theta: np.ndarray) -> np.ndarray:
    """Return weights for integration over x=cos(theta), preferring Gauss nodes."""
    th = np.asarray(theta, dtype=np.float64)
    x = np.cos(th)
    gx, gw = np.polynomial.legendre.leggauss(th.size)
    order = np.argsort(gx)[::-1]
    if np.allclose(x, gx[order], rtol=0.0, atol=5.0e-6):
        return gw[order]
    edges = np.empty(th.size + 1, dtype=np.float64)
    edges[1:-1] = 0.5 * (th[:-1] + th[1:])
    edges[0], edges[-1] = 0.0, np.pi
    return np.cos(edges[:-1]) - np.cos(edges[1:])


def _ylm_theta(l: int, m: int, theta: np.ndarray) -> np.ndarray:
    norm = math.exp(0.5 * (math.log(2 * l + 1) - math.log(4 * math.pi)
                           + gammaln(l - m + 1) - gammaln(l + m + 1)))
    return norm * lpmv(m, l, np.cos(theta))


def analyse_real_surface(field: np.ndarray, theta: np.ndarray, lmax: int) -> dict[tuple[int, int], complex]:
    values = np.asarray(field, dtype=np.float64)
    ntheta, nphi = values.shape
    if ntheta != len(theta):
        raise ValueError("Surface field and theta grid do not match.")
    lmax = min(int(lmax), ntheta - 1, nphi // 2)
    fourier = np.fft.rfft(values, axis=1) / float(nphi)
    weights = _angular_weights(theta)
    coeff: dict[tuple[int, int], complex] = {}
    for m in range(lmax + 1):
        fm = fourier[:, m]
        for l in range(m, lmax + 1):
            coeff[(l, m)] = complex(2.0 * np.pi * np.sum(weights * fm * _ylm_theta(l, m, theta)))
    coeff[(0, 0)] = 0.0j  # magnetic monopole removal
    return coeff


def synthesize_real_surface(
    coeff: dict[tuple[int, int], complex],
    theta: np.ndarray,
    phi: np.ndarray,
    factors: dict[int, float] | None = None,
) -> np.ndarray:
    out = np.zeros((len(theta), len(phi)), dtype=np.float64)
    factors = factors or {}
    for (l, m), value in coeff.items():
        value *= factors.get(l, 1.0)
        angular = _ylm_theta(l, m, theta)[:, None]
        if m == 0:
            out += (value.real * angular)
        else:
            out += 2.0 * np.real(value * angular * np.exp(1j * m * phi)[None, :])
    return np.ascontiguousarray(out)


def truncated_surface(field: np.ndarray, theta: np.ndarray, phi: np.ndarray, lmax: int) -> np.ndarray:
    return synthesize_real_surface(analyse_real_surface(field, theta, lmax), theta, phi)


def earth_surface_br(
    field: np.ndarray,
    theta: np.ndarray,
    phi: np.ndarray,
    lmax: int,
    radius_scale: float,
) -> np.ndarray:
    coeff = analyse_real_surface(field, theta, lmax)
    factors = {l: radius_scale ** (-(l + 2)) for l in range(lmax + 1)}
    return synthesize_real_surface(coeff, theta, phi, factors)


def exterior_potential_field(
    field: np.ndarray,
    theta: np.ndarray,
    phi: np.ndarray,
    r_cmb: float,
    r_ext: np.ndarray,
    lmax: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    coeff = analyse_real_surface(field, theta, lmax)
    shape = (len(r_ext), len(theta), len(phi))
    br, bt, bp = (np.empty(shape, dtype=np.float64) for _ in range(3))
    sin_theta = np.sin(theta)[:, None]
    for ir, radius in enumerate(r_ext):
        decay = {l: (r_cmb / radius) ** (l + 2) for l in range(lmax + 1)}
        br[ir] = synthesize_real_surface(coeff, theta, phi, decay)
        potential_factors = {l: decay[l] / (l + 1.0) for l in range(lmax + 1)}
        angular_potential = synthesize_real_surface(coeff, theta, phi, potential_factors)
        bt[ir] = -np.gradient(angular_potential, theta, axis=0, edge_order=2)
        dphi = 2.0 * np.pi / len(phi)
        dp = (np.roll(angular_potential, -1, axis=1) - np.roll(angular_potential, 1, axis=1)) / (2.0 * dphi)
        bp[ir] = -dp / np.where(np.abs(sin_theta) > 1.0e-12, sin_theta, np.inf)
    return br, bt, bp


def parameter_value(args: argparse.Namespace, graph: Any, cli: str, attrs: tuple[str, ...]) -> float:
    supplied = getattr(args, cli)
    if supplied is not None:
        return float(supplied)
    for name in attrs:
        value = json_number(getattr(graph, name, None))
        if value is not None:
            return value
    return float("nan")


def inferred_lmax(graph: Any, ntheta: int) -> int:
    for name in ("l_max", "lmax"):
        value = getattr(graph, name, None)
        if value is not None and int(value) > 0:
            return int(value)
    return max(1, 2 * int(ntheta) // 3)


def clean_output_directory(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    patterns = ("*_volume.f32", "*_cmb.f32", "*_earth.f32", "B_lines*.json")
    for pattern in patterns:
        for old in outdir.glob(pattern):
            old.unlink()
    for name in ("metadata.json", "coordinates.json", "profiles.json"):
        old = outdir / name
        if old.exists():
            old.unlink()


def convert_graph(path: Path, outdir: Path, args: argparse.Namespace) -> dict[str, Any]:
    graph = load_graph(path, args.magic_python_dir, args.precision)
    adapted = adapt_graph(graph)
    r_shell = adapted["r_shell"]
    r_master = adapted["r_master"]
    theta = adapted["theta"]
    phi = adapted["phi"]
    raw = adapted["fields"]
    r_icb, r_cmb = float(r_shell[0]), float(r_shell[-1])
    has_inner_core = r_icb > RADIAL_ATOL
    has_cond_ic = bool(adapted["has_conducting_inner_core"])
    magnetic_extends_ic = bool(adapted["magnetic_extends_inner_core"])
    lmax = inferred_lmax(graph, len(theta))

    if args.fluid_inner_radius is not None:
        spacing = float(np.median(np.diff(r_shell)))
        tolerance = max(RADIAL_ATOL, 0.51 * spacing)
        if abs(float(args.fluid_inner_radius) - r_icb) > tolerance:
            raise ValueError(
                f"--fluid-inner-radius={args.fluid_inner_radius} does not match "
                f"the MagIC ICB radius {r_icb} within {tolerance}."
            )
    if args.geometry == "full-sphere" and has_inner_core:
        raise ValueError("--geometry full-sphere conflicts with the native MagIC shell grid.")
    if args.geometry in ("shell", "conducting-inner-core") and not has_inner_core:
        raise ValueError(f"--geometry {args.geometry} conflicts with the native full-sphere grid.")
    if args.geometry == "conducting-inner-core" and not has_cond_ic:
        raise ValueError(
            "--geometry conducting-inner-core was requested, but MagIC's sigma value is zero."
        )

    print(
        f"MagIC grid: shell nr={len(r_shell)}, master nr={len(r_master)}, "
        f"ntheta={len(theta)}, nphi={len(phi)}, minc={adapted['minc']}, lmax~{lmax}"
    )
    native: dict[str, tuple[np.ndarray, np.ndarray, str]] = {}

    def register(name: str, values: np.ndarray, radius: np.ndarray, source: str) -> None:
        native[name] = (np.asarray(values, dtype=np.float32), radius, source)

    Ur = raw.get("ur")
    Ut = raw.get("ut")
    Up = raw.get("up")
    if Ur is not None and Ut is not None and Up is not None:
        register("ur", Ur, r_shell, "velocity")
        register("ut", Ut, r_shell, "velocity")
        register("up", Up, r_shell, "velocity")
        th3 = theta[None, :, None]
        register("us", Ur * np.sin(th3) + Ut * np.cos(th3), r_shell, "velocity")
        register("uz", Ur * np.cos(th3) - Ut * np.sin(th3), r_shell, "velocity")
        register("Uabs", np.sqrt(Ur**2 + Ut**2 + Up**2), r_shell, "velocity")
        register("helicity", compute_helicity(Ur, Ut, Up, r_shell, theta, phi), r_shell, "velocity")
        if not args.no_m0_fields:
            for name, arr in (("ur", Ur), ("ut", Ut), ("up", Up)):
                register(f"{name}_phiavg", phi_average_volume(arr), r_shell, "velocity")
                register(f"{name}_nom0", remove_m0_phi(arr), r_shell, "velocity")

    r_magnetic = r_master if magnetic_extends_ic else r_shell
    Br, Bt, Bp = raw.get("Br"), raw.get("Bt"), raw.get("Bp")
    if Br is not None and Bt is not None and Bp is not None:
        for name, arr in (("Br", Br), ("Bt", Bt), ("Bp", Bp)):
            register(name, arr, r_magnetic, "magnetic")
        register("Babs", np.sqrt(Br**2 + Bt**2 + Bp**2), r_magnetic, "magnetic")
        if not args.no_m0_fields:
            for name, arr in (("Br", Br), ("Bt", Bt), ("Bp", Bp)):
                register(f"{name}_phiavg", phi_average_volume(arr), r_magnetic, "magnetic")
                register(f"{name}_nom0", remove_m0_phi(arr), r_magnetic, "magnetic")

    scalars: dict[str, tuple[np.ndarray, np.ndarray, str]] = {}
    if "C" in raw:
        C = raw["C"]
        scalars["C"] = (C, r_shell, "entropy")
        register("C", C, r_shell, "entropy")
        register("T", C, r_shell, "entropy")
        register("Cnom0", remove_m0_phi(C), r_shell, "entropy")
        register("C_nom0", remove_m0_phi(C), r_shell, "entropy")
        register("Cnol0", C - np.mean(C), r_shell, "entropy")
        register("C_phiavg", phi_average_volume(C), r_shell, "entropy")
        if not args.no_m0_fields:
            register("T_nom0", remove_m0_phi(C), r_shell, "entropy")
            register("T_phiavg", phi_average_volume(C), r_shell, "entropy")
    if "Comp" in raw:
        Comp = raw["Comp"]
        scalars["Comp"] = (Comp, r_shell, "composition")
        register("Comp", Comp, r_shell, "composition")
        register("Compnom0", remove_m0_phi(Comp), r_shell, "composition")
        register("Comp_nom0", remove_m0_phi(Comp), r_shell, "composition")
        register("Compnol0", Comp - np.mean(Comp), r_shell, "composition")
        register("Comp_phiavg", phi_average_volume(Comp), r_shell, "composition")
    for optional in ("Phase", "P"):
        if optional in raw:
            register(optional, raw[optional], r_shell, optional.lower())

    gradients: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    if not args.no_gradients:
        for name, (scalar, radius, source) in scalars.items():
            print(f"Computing gradients of {name}...")
            gr, gt, gp = gradient_scalar_3d(scalar, radius, theta, phi)
            gradients[name] = (gr, gt, gp)
            register(f"grad_r{name}_full", gr, radius, source)
            register(f"grad_theta{name}_full", gt, radius, source)
            register(f"grad_phi{name}_full", gp, radius, source)
            if not args.no_m0_fields:
                register(f"grad_r{name}", remove_m0_phi(gr), radius, source)
                register(f"grad_theta{name}", remove_m0_phi(gt), radius, source)
                register(f"grad_phi{name}", remove_m0_phi(gp), radius, source)

    diagnostics = {
        "emf_requested": bool(args.emf),
        "emf_exported": False,
        "induction_requested": bool(args.induction),
        "induction_exported": False,
        "emf_definition": "u x B",
        "fluctuating_emf_definition": "u_prime x B_prime",
        "induction_definition": "curl(u x B)",
        "curl_implementation": "shared finite-difference spherical curl",
    }
    if args.emf or args.induction:
        if Ur is None or Br is None:
            print("Skipping EMF/induction: both velocity and magnetic fields are required.")
        else:
            Br_u = radial_remap_to_master(Br, r_magnetic, r_shell)
            Bt_u = radial_remap_to_master(Bt, r_magnetic, r_shell)
            Bp_u = radial_remap_to_master(Bp, r_magnetic, r_shell)
            Er, Et, Ep = compute_emf(Ur, Ut, Up, Br_u, Bt_u, Bp_u)
            Erf, Etf, Epf = compute_emf(
                remove_m0_phi(Ur), remove_m0_phi(Ut), remove_m0_phi(Up),
                remove_m0_phi(Br_u), remove_m0_phi(Bt_u), remove_m0_phi(Bp_u),
            )
            if args.emf:
                register("EMFr", Er, r_shell, "velocity")
                register("EMFt", Et, r_shell, "velocity")
                register("EMFp", Ep, r_shell, "velocity")
                register("EMFr_fluct", Erf, r_shell, "velocity")
                register("EMFt_fluct", Etf, r_shell, "velocity")
                register("EMFp_fluct", Epf, r_shell, "velocity")
                register("EMFabs", np.sqrt(Er**2 + Et**2 + Ep**2), r_shell, "velocity")
                diagnostics["emf_exported"] = True
            if args.induction:
                Ir, It, Ip = compute_induction_from_emf(Er, Et, Ep, r_shell, theta, phi)
                register("Ir", Ir, r_shell, "velocity")
                register("It", It, r_shell, "velocity")
                register("Ip", Ip, r_shell, "velocity")
                register("Iz", Ir * np.cos(th3) - It * np.sin(th3), r_shell, "velocity")
                register("Iabs", np.sqrt(Ir**2 + It**2 + Ip**2), r_shell, "velocity")
                diagnostics["induction_exported"] = True

    Ek = parameter_value(args, graph, "Ek", ("ek",))
    Pr = parameter_value(args, graph, "Pr", ("pr",))
    Sc = parameter_value(args, graph, "Sc", ("sc",))
    RaT = parameter_value(args, graph, "RaT", ("ra",))
    RaC = parameter_value(args, graph, "RaC", ("raxi",))
    N2_full = None
    if gradients and np.isfinite(Ek):
        N2_full = np.zeros_like(next(iter(gradients.values()))[0], dtype=np.float64)
        used = False
        if "C" in gradients and np.isfinite(Pr) and Pr != 0.0 and np.isfinite(RaT):
            N2_full += r_shell[:, None, None] * (Ek**2 * RaT / Pr) * gradients["C"][0]
            used = True
        if "Comp" in gradients and np.isfinite(Sc) and Sc != 0.0 and np.isfinite(RaC):
            N2_full += r_shell[:, None, None] * (Ek**2 * RaC / Sc) * gradients["Comp"][0]
            used = True
        if used:
            register("N2_full", N2_full, r_shell, "scalar_shell")
            if not args.no_m0_fields:
                register("N2", remove_m0_phi(N2_full), r_shell, "scalar_shell")
        else:
            N2_full = None

    fields: dict[str, np.ndarray] = {}
    field_domains: dict[str, dict[str, Any]] = {}
    for name, (arr, radius, source) in native.items():
        fields[name] = radial_remap_to_master(arr, radius, r_master)
        field_domains[name] = {
            "source": source,
            "r_min": json_number(radius[0]),
            "r_max": json_number(radius[-1]),
            "outside_native_domain": "zero",
        }

    dr = max(1, int(args.downsample_r))
    dt = max(1, int(args.downsample_theta))
    dp = max(1, int(args.downsample_phi))
    fields = {name: np.ascontiguousarray(arr[::dr, ::dt, ::dp]) for name, arr in fields.items()}
    r_out, theta_out, phi_out = r_master[::dr], theta[::dt], phi[::dp]

    clean_output_directory(outdir)
    field_files: dict[str, str] = {}
    ranges: dict[str, dict[str, float]] = {}
    print(f"Writing viewer data to {outdir}...")
    for name, arr in fields.items():
        filename = f"{name}_volume.f32"
        field_files[name] = filename
        ranges[name] = write_f32(outdir / filename, arr)

    has_magnetic = "Babs" in fields and ranges["Babs"]["absmax"] > 0.0
    surface_fields: dict[str, dict[str, Any]] = {}
    Br_cmb = None
    if has_magnetic and Br is not None:
        Br_cmb = np.asarray(Br[nearest_index(r_magnetic, r_cmb)], dtype=np.float64)
    if args.cmb_br_ltrunc is not None and Br_cmb is not None:
        requested = max(0, int(args.cmb_br_ltrunc))
        effective = min(requested, lmax)
        surface = truncated_surface(Br_cmb, theta, phi, effective)[::dt, ::dp]
        name = f"Br_CMB_lmax{requested}"
        filename = f"{name}_cmb.f32"
        ranges[name] = write_f32(outdir / filename, surface)
        surface_fields[name] = {
            "file": filename, "surface": "cmb", "layout": "theta_phi",
            "l_trunc": requested, "effective_l_trunc": effective,
            "source": "MagIC Br at the CMB",
        }
    if not args.no_earth_br and Br_cmb is not None:
        requested = max(0, int(args.earth_br_ltrunc))
        effective = min(requested, lmax)
        scale = float(args.earth_radius_scale)
        if not math.isfinite(scale) or scale < 1.0:
            raise ValueError("--earth-radius-scale must be finite and >= 1.")
        surface = earth_surface_br(Br_cmb, theta, phi, effective, scale)[::dt, ::dp]
        name = f"Br_Earth_lmax{requested}"
        filename = f"{name}_earth.f32"
        ranges[name] = write_f32(outdir / filename, surface)
        surface_fields[name] = {
            "file": filename, "surface": "earth", "layout": "theta_phi",
            "l_trunc": requested, "effective_l_trunc": effective,
            "radius_scale": scale, "radius": r_cmb * scale,
            "source": "MagIC CMB Br continued as an external potential field",
            "radial_decay": "(r_cmb/r)^(l+2)",
        }

    coordinates = {
        "r": [json_number(x) for x in r_out],
        "theta": [json_number(x) for x in theta_out],
        "phi": [json_number(x) for x in phi_out],
    }
    with open(outdir / "coordinates.json", "w", encoding="utf-8") as stream:
        json.dump(coordinates, stream, allow_nan=False)
    profiles: dict[str, Any] = {"r": coordinates["r"]}
    if N2_full is not None:
        profiles["N2"] = [json_number(x) for x in np.mean(N2_full, axis=(1, 2))[::dr]]
    with open(outdir / "profiles.json", "w", encoding="utf-8") as stream:
        json.dump(profiles, stream, allow_nan=False)

    field_lines_meta: dict[str, Any] = {}
    if not args.skip_field_lines and Br_cmb is not None:
        combined: list[dict[str, Any]] = []
        shell_lines: list[dict[str, Any]] = []
        field_lines_meta = {"mode": args.field_line_mode, "counts": {}}
        shell_mask = (r_magnetic >= r_icb - RADIAL_ATOL) & (r_magnetic <= r_cmb + RADIAL_ATOL)
        r_b_shell = r_magnetic[shell_mask]
        shell_step = args.line_step_size or 0.5 * float(np.median(np.diff(r_b_shell)))
        if args.field_line_mode in ("shell", "both"):
            shell_lines = compute_shell_field_lines_from_cmb(
                Br[shell_mask], Bt[shell_mask], Bp[shell_mask], r_b_shell, theta, phi,
                ntheta_seed=args.line_seed_theta, nphi_seed=args.line_seed_phi,
                max_steps=args.line_max_steps, step_size=shell_step,
                seed_offset=1.5 * shell_step, full_sphere=not has_inner_core,
            )
            combined.extend(shell_lines)
            with open(outdir / "B_lines_shell.json", "w", encoding="utf-8") as stream:
                json.dump(shell_lines, stream, allow_nan=False)
            field_lines_meta.update({"shell": "B_lines_shell.json", "B_lines_shell": "B_lines_shell.json"})
            field_lines_meta["counts"]["shell"] = len(shell_lines)
        if args.field_line_mode in ("exterior", "both"):
            rmax = args.external_rmax or 2.5 * r_cmb
            if rmax <= r_cmb:
                raise ValueError("--external-rmax must exceed the CMB radius.")
            r_ext = np.linspace(r_cmb, rmax, max(8, int(args.external_nr)))
            ext_lmax = min(lmax, max(1, int(args.external_lmax)))
            Br_ext, Bt_ext, Bp_ext = exterior_potential_field(
                Br_cmb, theta, phi, r_cmb, r_ext, ext_lmax
            )
            ext_step = args.line_step_size or 0.5 * float(np.mean(np.diff(r_ext)))
            lines = compute_external_field_lines_from_cmb(
                Br_ext, Bt_ext, Bp_ext, r_ext, theta, phi,
                ntheta_seed=args.line_seed_theta, nphi_seed=args.line_seed_phi,
                max_steps=args.line_max_steps, step_size=ext_step,
                closed_only=args.external_closed_only,
                seed_records=shell_lines if args.field_line_mode == "both" else None,
            )
            combined.extend(lines)
            with open(outdir / "B_lines_exterior_poloidal.json", "w", encoding="utf-8") as stream:
                json.dump(lines, stream, allow_nan=False)
            field_lines_meta.update({
                "exterior": "B_lines_exterior_poloidal.json",
                "exterior_poloidal": "B_lines_exterior_poloidal.json",
                "B_lines_exterior_poloidal": "B_lines_exterior_poloidal.json",
                "external_lmax": ext_lmax,
            })
            field_lines_meta["counts"]["exterior"] = len(lines)
            field_lines_meta["exterior_seed_policy"] = (
                "paired_actual_shell_cmb_intersections"
                if args.field_line_mode == "both"
                else "regular_cmb_grid"
            )
            field_lines_meta["polarity_definition"] = (
                "sign of Br at each line's starting CMB footpoint: +1 outward, -1 inward"
            )
        with open(outdir / "B_lines.json", "w", encoding="utf-8") as stream:
            json.dump(combined, stream, allow_nan=False)
        field_lines_meta["B_lines"] = "B_lines.json"
        field_lines_meta["count"] = len(combined)

    time = json_number(getattr(graph, "time", None))
    radial_domains = {
        "fluid_shell": {"nr": len(r_shell), "r_min": json_number(r_shell[0]), "r_max": json_number(r_shell[-1])},
        "magnetic": {"nr": len(r_magnetic), "r_min": json_number(r_magnetic[0]), "r_max": json_number(r_magnetic[-1])},
    }
    metadata = {
        "description": "Converted physical-space quantities from a MagIC graphic snapshot using MagicGraph.",
        "source_format": "magic_graph",
        "converter_version": CONVERTER_PACKAGE_VERSION,
        "viewer_field_contract": "dynamo-three-viewer-v2-common",
        "source_fields": {"graphic": str(path)},
        "time": time,
        "parameters": {"Ek": json_number(Ek), "Pr": json_number(Pr), "Sc": json_number(Sc),
                       "RaT": json_number(RaT), "RaC": json_number(RaC),
                       "PrMag": json_number(getattr(graph, "prmag", None)),
                       "radius_ratio": json_number(getattr(graph, "radratio", None))},
        "spectral": {"lmax": lmax, "minc": int(adapted["minc"]),
                     "nlat": len(theta), "nphi": len(phi),
                     "library": "MagIC MagicGraph; SciPy surface harmonic analysis"},
        "optional_magnetic_diagnostics": diagnostics,
        "magnetic": {"has_magnetic_field": has_magnetic,
                     "classification": "magnetic" if has_magnetic else "non_magnetic",
                     "has_conducting_inner_core": has_cond_ic,
                     "extends_into_inner_core": magnetic_extends_ic},
        "title": f"MagIC, t={time if time is not None else float('nan'):.3e}",
        "nr": len(r_out), "ntheta": len(theta_out), "nphi": len(phi_out),
        "r_inner": json_number(r_out[0]), "r_outer": json_number(r_out[-1]),
        "r_icb": json_number(r_icb), "icb_radius": json_number(r_icb),
        "icb_index": nearest_index(r_out, r_icb), "r_fluid_inner": json_number(r_icb),
        "has_inner_core": has_inner_core, "has_conducting_inner_core": has_cond_ic,
        "full_sphere": not has_inner_core,
        "physical_geometry": "spherical_shell_conducting_inner_core" if has_cond_ic else
                             ("spherical_shell" if has_inner_core else "full_fluid_sphere"),
        "geometry_detection": {"method": "native_magic_graph_radial_domains",
                               "transform_geometry": "physical_space",
                               "requested_geometry": args.geometry},
        "master_radial_field": "magnetic" if magnetic_extends_ic else "fluid_shell",
        "radial_domains": radial_domains, "field_domains": field_domains,
        "layout": "r_theta_phi", "endianness": "little",
        "theta_min": json_number(theta_out[0]), "theta_max": json_number(theta_out[-1]),
        "phi_min": json_number(phi_out[0]), "phi_max": json_number(phi_out[-1]),
        "fields": field_files, "surface_fields": surface_fields, "ranges": ranges,
        "coordinates": "coordinates.json", "profiles": "profiles.json",
        "field_lines": field_lines_meta,
    }
    with open(outdir / "metadata.json", "w", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2, allow_nan=False)
    print(f"Done: {outdir.resolve()} ({len(field_files)} volume fields)")
    return metadata


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Convert MagIC G_#.TAG graphic files to DEEPscope viewer data.")
    source = p.add_argument_group("MagIC input")
    source.add_argument("--graph", help="Explicit G_<number>.TAG or G_ave.TAG file.")
    source.add_argument("--folder", help="MagIC run folder; selects a graphic using --ivar/--tag.")
    source.add_argument("--ivar", type=int, help="Graphic number, for example 1 for G_1.TAG.")
    source.add_argument("--tag", help="MagIC run tag/filename suffix.")
    source.add_argument("--average", action="store_true", help="Read G_ave.TAG instead of G_<number>.TAG.")
    source.add_argument("--magic-python-dir", help="MagIC python directory, normally $MAGIC_HOME/python.")
    source.add_argument("--precision", choices=["float32", "float64"], default="float32")

    p.add_argument("--out", default="public/data_magic")
    p.add_argument("--downsample-r", type=int, default=1)
    p.add_argument("--downsample-theta", type=int, default=1)
    p.add_argument("--downsample-phi", type=int, default=1)
    p.add_argument("--no-gradients", action="store_true")
    p.add_argument("--no-m0-fields", action="store_true")
    p.add_argument("--no-parameter-prompt", action="store_true", help="Accepted for CLI parity; MagIC parameters come from the G header.")
    p.add_argument("--emf", action="store_true")
    p.add_argument("--induction", action="store_true")
    p.add_argument("--geometry", choices=["auto", "full-sphere", "shell", "conducting-inner-core"], default="auto")
    p.add_argument("--fluid-inner-radius", type=float, help="Validate the MagIC ICB radius against this value.")
    p.add_argument("--Ek", "--E", dest="Ek", type=float)
    p.add_argument("--Pr", "--PrT", "--Pr_T", dest="Pr", type=float)
    p.add_argument("--Sc", "--PrC", "--Pr_C", dest="Sc", type=float)
    p.add_argument("--RaT", "--Ra", "--Ra_T", dest="RaT", type=float)
    p.add_argument("--RaC", "--Ra_C", dest="RaC", type=float)
    p.add_argument("--cmb-br-ltrunc", type=int)
    p.add_argument("--earth-br-ltrunc", type=int, default=DEFAULT_EARTH_BR_LMAX)
    p.add_argument("--earth-radius-scale", type=float, default=DEFAULT_EARTH_RADIUS_SCALE)
    p.add_argument("--no-earth-br", action="store_true")
    p.add_argument("--skip-field-lines", action="store_true")
    p.add_argument("--field-line-mode", choices=["shell", "exterior", "both"], default="shell")
    p.add_argument("--external-rmax", type=float)
    p.add_argument("--external-nr", type=int, default=96)
    p.add_argument("--external-lmax", type=int, default=32, help="Maximum degree used for exterior field-line reconstruction.")
    p.add_argument("--external-closed-only", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--external-btheta-sign", choices=["auto", "plus", "minus"], default="auto",
                   help="Accepted for CLI parity; MagIC potential-field signs are fixed analytically.")
    p.add_argument("--line-seeds", type=int)
    p.add_argument("--line-seed-theta", type=int, default=9)
    p.add_argument("--line-seed-phi", type=int, default=18)
    p.add_argument("--line-max-steps", type=int, default=1000)
    p.add_argument("--line-step-size", type=float)
    p.add_argument("--sequence-first", type=int)
    p.add_argument("--sequence-last", type=int)
    p.add_argument("--sequence-step", type=int, default=1)
    p.add_argument("--sequence-subdir", default="frames")
    p.add_argument("--sequence-clear", action="store_true")
    return p


def resolve_single_path(args: argparse.Namespace) -> Path:
    if args.graph:
        path = Path(args.graph).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"MagIC graphic file does not exist: {path}")
        return path
    if not args.folder:
        raise ValueError("Give --graph, or --folder with optional --ivar/--tag.")
    return discover_graph(Path(args.folder).expanduser(), args.tag, args.ivar, args.average)


def run_sequence(args: argparse.Namespace) -> None:
    if not args.folder or args.sequence_first is None or args.sequence_last is None:
        raise ValueError("Sequence conversion requires --folder, --sequence-first, and --sequence-last.")
    first, last, step = int(args.sequence_first), int(args.sequence_last), max(1, int(args.sequence_step))
    if last < first:
        raise ValueError("--sequence-last must be >= --sequence-first.")
    folder = Path(args.folder).expanduser()
    selected = [discover_graph(folder, args.tag, ivar, False) for ivar in range(first, last + 1, step)]
    root = Path(args.out)
    frames_root = root / args.sequence_subdir
    if args.sequence_clear and frames_root.exists():
        shutil.rmtree(frames_root)
    frames_root.mkdir(parents=True, exist_ok=True)
    frames: list[dict[str, Any]] = []
    first_out: Path | None = None
    for path in selected:
        ivar, _, _ = parse_graph_filename(path)
        name = f"G_{ivar:05d}"
        frame_out = frames_root / name
        metadata = convert_graph(path, frame_out, args)
        if first_out is None:
            first_out = frame_out
        frames.append({"state_number": ivar, "time": metadata["time"],
                       "path": f"{args.sequence_subdir}/{name}",
                       "metadata": f"{args.sequence_subdir}/{name}/metadata.json", "label": name})
    assert first_out is not None
    root.mkdir(parents=True, exist_ok=True)
    for item in first_out.iterdir():
        if item.is_file():
            shutil.copy2(item, root / item.name)
    sequence = {"version": 1, "frame_count": len(frames), "first": first, "last": last,
                "step": step, "frames": frames}
    with open(root / "sequence.json", "w", encoding="utf-8") as stream:
        json.dump(sequence, stream, indent=2, allow_nan=False)
    print(f"Sequence written to {(root / 'sequence.json').resolve()}")


def main() -> None:
    args = build_arg_parser().parse_args()
    if args.line_seeds is not None:
        args.line_seed_theta, args.line_seed_phi = choose_regular_seed_grid(args.line_seeds)
    sequence_requested = args.sequence_first is not None or args.sequence_last is not None
    if sequence_requested:
        if args.sequence_first is None or args.sequence_last is None:
            raise ValueError("Both --sequence-first and --sequence-last are required.")
        run_sequence(args)
    else:
        convert_graph(resolve_single_path(args), Path(args.out), args)


if __name__ == "__main__":
    main()
