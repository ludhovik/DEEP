#!/usr/bin/env python3
"""
Convert a Leeds spherical-dynamo spectral state file into the binary files read by
this local Three.js viewer.

This script expects your existing `modules.py` to provide:

    load_state
    PolTor_to_spat
    SH_to_spat
    SH_to_spat_nom0
    gradient_spat

It writes:

    public/data/metadata.json
    public/data/<field>_volume.f32
    public/data/B_lines.json                optional magnetic field lines
    public/data/profiles.json               1-D radial profiles, including N2

The browser assumes all 3-D fields are flattened in C order as:

    field[ir, itheta, iphi]

where theta is colatitude and phi is longitude.
"""

from __future__ import annotations

import argparse
import glob
import importlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np


# -----------------------------------------------------------------------------
# Path / parsing helpers
# -----------------------------------------------------------------------------


def parse_float_from_path(path: str, key: str, default: float | None = None) -> float | None:
    """Extract values like Ek=2e-5 or RaC=1e9 from a path string."""
    # Accept either normal '=' or an escaped '\=' that may appear in copied paths.
    pattern = rf"{re.escape(key)}\\?=([0-9eE+.-]+)"
    match = re.search(pattern, path)
    if match is None:
        return default
    return float(match.group(1))


def parse_state_number(path: str) -> int:
    match = re.search(r"state(\d+)\.cdf\.dat", Path(path).name)
    return int(match.group(1)) if match else -1


def latest_state_file(folder: str, pattern: str = "state*.cdf.dat") -> str:
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} in {folder!r}")
    return max(files, key=parse_state_number)


def add_modules_dir(modules_dir: str | None) -> None:
    """Make the user's modules.py importable."""
    if modules_dir:
        sys.path.insert(0, str(Path(modules_dir).expanduser().resolve()))

    # Also try the current directory and the script directory.
    sys.path.insert(0, str(Path.cwd()))
    sys.path.insert(0, str(Path(__file__).resolve().parent))


# -----------------------------------------------------------------------------
# Array helpers
# -----------------------------------------------------------------------------


def as_scalar_int(x: Any, name: str) -> int:
    try:
        return int(np.asarray(x).item())
    except Exception as exc:
        raise ValueError(f"Could not convert {name}={x!r} to int") from exc


def as_r_theta_phi(arr: np.ndarray, nr: int, ntheta: int | None = None, nphi: int | None = None) -> np.ndarray:
    """
    Return a C-contiguous array shaped as (nr, ntheta, nphi).

    The transform functions used by the user's plotting workflow normally return
    this order already. This helper only catches a few common accidental orders.
    """
    arr = np.asarray(arr)

    if arr.ndim != 3:
        raise ValueError(f"Expected a 3-D array, got shape {arr.shape}")

    if arr.shape[0] == nr:
        out = arr
    elif arr.shape[-1] == nr:
        # Common Fortran-ish output: (theta, phi, r) or (phi, theta, r).
        # We can only safely move r to the front; theta/phi are inferred below.
        out = np.moveaxis(arr, -1, 0)
    else:
        raise ValueError(
            f"Cannot identify radial dimension nr={nr} in array shape {arr.shape}. "
            "Please transpose explicitly in convert_state_to_viewer.py."
        )

    if ntheta is not None and nphi is not None and out.shape != (nr, ntheta, nphi):
        raise ValueError(
            f"Expected shape {(nr, ntheta, nphi)}, got {out.shape}. "
            "The theta/phi order may need transposing."
        )

    return np.ascontiguousarray(out, dtype=np.float64)


def remove_global_mean(arr: np.ndarray) -> np.ndarray:
    return arr - np.mean(arr, axis=(0, 1, 2))


def json_number(x: Any) -> float | None:
    """Return a JSON-safe finite float, or None for NaN/inf/missing."""
    try:
        y = float(x)
    except Exception:
        return None
    return y if math.isfinite(y) else None


def format_param(x: Any, fmt: str, missing: str = "NA") -> str:
    y = json_number(x)
    return missing if y is None else format(y, fmt)


def write_f32(path: Path, arr: np.ndarray) -> dict[str, float | None]:
    arr32 = np.asarray(arr, dtype="<f4", order="C")
    arr32.tofile(path)

    finite = np.isfinite(arr32)
    if not np.any(finite):
        return {"min": None, "max": None, "mean": None}

    good = arr32[finite]
    return {
        "min": float(np.min(good)),
        "max": float(np.max(good)),
        "mean": float(np.mean(good)),
    }


def downsample_3d(arr: np.ndarray, dr: int, dt: int, dp: int) -> np.ndarray:
    return np.ascontiguousarray(arr[::dr, ::dt, ::dp])


# -----------------------------------------------------------------------------
# Spherical geometry / field-line helpers
# -----------------------------------------------------------------------------


def sph_to_cart(r: float, theta: float, phi: float) -> np.ndarray:
    st = math.sin(theta)
    return np.array(
        [r * st * math.cos(phi), r * st * math.sin(phi), r * math.cos(theta)],
        dtype=np.float64,
    )


def cart_to_sph(x: np.ndarray) -> tuple[float, float, float]:
    xx, yy, zz = float(x[0]), float(x[1]), float(x[2])
    r = math.sqrt(xx * xx + yy * yy + zz * zz)
    if r == 0.0:
        return 0.0, 0.0, 0.0
    theta = math.acos(max(-1.0, min(1.0, zz / r)))
    phi = math.atan2(yy, xx) % (2.0 * math.pi)
    return r, theta, phi


def spherical_basis(theta: float, phi: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    st, ct = math.sin(theta), math.cos(theta)
    sp, cp = math.sin(phi), math.cos(phi)

    er = np.array([st * cp, st * sp, ct], dtype=np.float64)
    et = np.array([ct * cp, ct * sp, -st], dtype=np.float64)
    ep = np.array([-sp, cp, 0.0], dtype=np.float64)
    return er, et, ep


def interp_spherical_field(
    arr: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
    r: float,
    theta: float,
    phi: float,
) -> float:
    """Trilinear interpolation for arr[ir, itheta, iphi], periodic in phi."""
    nr, nt, np_ = arr.shape

    if r < r_grid[0] or r > r_grid[-1]:
        return float("nan")

    theta = max(float(theta_grid[0]), min(float(theta_grid[-1]), theta))
    phi = phi % (2.0 * math.pi)

    ir1 = int(np.searchsorted(r_grid, r, side="right"))
    ir0 = max(0, min(nr - 2, ir1 - 1))
    ir1 = ir0 + 1

    it1 = int(np.searchsorted(theta_grid, theta, side="right"))
    it0 = max(0, min(nt - 2, it1 - 1))
    it1 = it0 + 1

    # Periodic phi interpolation.  Use the actual SHTns longitude array when
    # available, but fall back to a uniform grid if it is absent/malformed.
    if len(phi_grid) == np_ and np_ > 1:
        dphi = float(np.median(np.diff(np.unwrap(phi_grid))))
        phi0 = float(phi_grid[0])
        if not math.isfinite(dphi) or abs(dphi) <= 1.0e-300:
            dphi = 2.0 * math.pi / np_
            phi0 = 0.0
    else:
        dphi = 2.0 * math.pi / np_
        phi0 = 0.0

    fp = ((phi - phi0) % (2.0 * math.pi)) / dphi
    ip0 = int(math.floor(fp)) % np_
    ip1 = (ip0 + 1) % np_

    wr = (r - r_grid[ir0]) / (r_grid[ir1] - r_grid[ir0] + 1.0e-300)
    wt = (theta - theta_grid[it0]) / (theta_grid[it1] - theta_grid[it0] + 1.0e-300)
    wp = fp - math.floor(fp)

    c000 = arr[ir0, it0, ip0]
    c001 = arr[ir0, it0, ip1]
    c010 = arr[ir0, it1, ip0]
    c011 = arr[ir0, it1, ip1]
    c100 = arr[ir1, it0, ip0]
    c101 = arr[ir1, it0, ip1]
    c110 = arr[ir1, it1, ip0]
    c111 = arr[ir1, it1, ip1]

    c00 = c000 * (1.0 - wp) + c001 * wp
    c01 = c010 * (1.0 - wp) + c011 * wp
    c10 = c100 * (1.0 - wp) + c101 * wp
    c11 = c110 * (1.0 - wp) + c111 * wp

    c0 = c00 * (1.0 - wt) + c01 * wt
    c1 = c10 * (1.0 - wt) + c11 * wt

    return float(c0 * (1.0 - wr) + c1 * wr)


def interpolate_B_cartesian(
    x: np.ndarray,
    Br: np.ndarray,
    Bt: np.ndarray,
    Bp: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
) -> np.ndarray | None:
    r, theta, phi = cart_to_sph(x)

    if r < r_grid[0] or r > r_grid[-1]:
        return None

    br = interp_spherical_field(Br, r_grid, theta_grid, phi_grid, r, theta, phi)
    bt = interp_spherical_field(Bt, r_grid, theta_grid, phi_grid, r, theta, phi)
    bp = interp_spherical_field(Bp, r_grid, theta_grid, phi_grid, r, theta, phi)

    if not np.isfinite([br, bt, bp]).all():
        return None

    er, et, ep = spherical_basis(theta, phi)
    B = br * er + bt * et + bp * ep
    norm = float(np.linalg.norm(B))

    if norm <= 1.0e-300:
        return None

    return B / norm


def trace_one_line(
    seed: np.ndarray,
    direction: float,
    Br: np.ndarray,
    Bt: np.ndarray,
    Bp: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
    step_size: float,
    max_steps: int,
) -> list[list[float]]:
    points: list[list[float]] = []
    x = np.asarray(seed, dtype=np.float64).copy()

    rmin = float(r_grid[0])
    rmax = float(r_grid[-1])

    for _ in range(max_steps):
        r, _, _ = cart_to_sph(x)
        if r < rmin or r > rmax:
            break

        points.append([float(x[0]), float(x[1]), float(x[2])])

        # RK4 integration of dx/ds = +/- B/|B| in Cartesian coordinates.
        k1 = interpolate_B_cartesian(x, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
        if k1 is None:
            break
        k1 *= direction

        k2 = interpolate_B_cartesian(x + 0.5 * step_size * k1, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
        if k2 is None:
            break
        k2 *= direction

        k3 = interpolate_B_cartesian(x + 0.5 * step_size * k2, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
        if k3 is None:
            break
        k3 *= direction

        k4 = interpolate_B_cartesian(x + step_size * k3, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
        if k4 is None:
            break
        k4 *= direction

        x = x + (step_size / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    return points


def rk4_step_cartesian(
    x: np.ndarray,
    direction: float,
    Br: np.ndarray,
    Bt: np.ndarray,
    Bp: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
    step_size: float,
) -> np.ndarray | None:
    """One RK4 step for dx/ds = +/- B/|B| in Cartesian coordinates."""
    k1 = interpolate_B_cartesian(x, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
    if k1 is None:
        return None
    k1 *= direction

    k2 = interpolate_B_cartesian(x + 0.5 * step_size * k1, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
    if k2 is None:
        return None
    k2 *= direction

    k3 = interpolate_B_cartesian(x + 0.5 * step_size * k2, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
    if k3 is None:
        return None
    k3 *= direction

    k4 = interpolate_B_cartesian(x + step_size * k3, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
    if k4 is None:
        return None
    k4 *= direction

    return x + (step_size / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def trace_exterior_cmb_to_cmb_arc(
    seed: np.ndarray,
    direction: float,
    Br: np.ndarray,
    Bt: np.ndarray,
    Bp: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
    step_size: float,
    max_steps: int,
    min_points: int,
) -> tuple[list[list[float]], str, float]:
    """
    Trace one exterior potential-field arc as a CMB-to-CMB segment.

    This version deliberately uses a robust first-order field-line step rather
    than RK4.  RK4 samples intermediate points; near the CMB one of those
    samples can fall just inside r_cmb, making the whole step fail with an
    interpolation_stop before a valid CMB-returning arc is detected.  For the
    viewer, robust topology of CMB-to-CMB arcs is more important than very high
    integration order.
    """
    r_outer = float(r_grid[0])
    r_max_allowed = float(r_grid[-1])
    x = np.asarray(seed, dtype=np.float64).copy()

    points: list[list[float]] = [[float(x[0]), float(x[1]), float(x[2])]]
    r0, _, _ = cart_to_sph(x)
    max_r_seen = float(r0)
    moved_outward = False
    outward_threshold = r_outer + max(2.0 * step_size, 1.0e-6 * r_outer)

    for _ in range(max_steps):
        r_now, _, _ = cart_to_sph(x)

        if r_now > r_max_allowed:
            return points, "hit_external_rmax", max_r_seen

        if r_now < r_outer:
            if moved_outward and len(points) >= min_points:
                rr, tt, pp = cart_to_sph(x)
                foot = sph_to_cart(r_outer, tt, pp)
                points.append([float(foot[0]), float(foot[1]), float(foot[2])])
                return points, "returned_cmb", max_r_seen
            return points, "immediate_cmb", max_r_seen

        bhat = interpolate_B_cartesian(x, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
        if bhat is None:
            return points, "interpolation_stop_at_current_point", max_r_seen

        x_new = x + float(direction) * float(step_size) * bhat
        r_new, theta_new, phi_new = cart_to_sph(x_new)
        max_r_seen = max(max_r_seen, float(r_new))

        if r_new >= outward_threshold:
            moved_outward = True

        # If the step crosses back through the CMB after moving outward,
        # place the endpoint exactly on r_cmb by linear interpolation along
        # the Cartesian segment.
        if r_new <= r_outer:
            if moved_outward and len(points) >= min_points:
                frac = (r_now - r_outer) / ((r_now - r_new) + 1.0e-300)
                frac = max(0.0, min(1.0, float(frac)))
                x_hit = x + frac * (x_new - x)
                _, theta_hit, phi_hit = cart_to_sph(x_hit)
                foot = sph_to_cart(r_outer, theta_hit, phi_hit)
                points.append([float(foot[0]), float(foot[1]), float(foot[2])])
                return points, "returned_cmb", max_r_seen
            return points, "immediate_cmb", max_r_seen

        if r_new > r_max_allowed:
            return points, "hit_external_rmax", max_r_seen

        points.append([float(x_new[0]), float(x_new[1]), float(x_new[2])])
        x = x_new

    return points, "max_steps", max_r_seen


def external_potential_field_from_BP(
    BP_lsd: np.ndarray,
    r_state: np.ndarray,
    r_ext: np.ndarray,
    lmax: int,
    mmax: int,
    user_modules: Any,
    btheta_sign: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Build a potential magnetic field outside the CMB from the surface poloidal
    coefficients.

    For r >= r_cmb, the exterior poloidal scalar is taken as

        P_lm(r) = P_lm(r_cmb) * (r_cmb / r)^(l+1)

    and the toroidal component is zero. This gives exterior field lines, not
    field lines inside the fluid shell.
    """
    if not hasattr(user_modules, "shtns") or not hasattr(user_modules, "lsd_to_shtns"):
        raise RuntimeError("modules.py must expose shtns and lsd_to_shtns for exterior field-line tracing.")

    shtns = user_modules.shtns
    sh = shtns.sht(int(lmax), int(mmax), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    nlat, nphi = sh.set_grid()

    theta_ext = np.arccos(sh.cos_theta)
    phi_ext = np.linspace(0.0, 2.0 * np.pi, nphi + 2)[1:-1]

    BP_shtns = user_modules.lsd_to_shtns(BP_lsd, sh)
    P_cmb = BP_shtns[:, -1]

    ell = np.asarray(sh.l, dtype=np.float64)
    r_cmb = float(r_state[-1])

    Br_ext = np.zeros((len(r_ext), nlat, nphi), dtype=np.float64)
    Bt_ext = np.zeros_like(Br_ext)
    Bp_ext = np.zeros_like(Br_ext)

    zero = np.zeros_like(P_cmb)

    for k, rr in enumerate(r_ext):
        rr = float(rr)
        factor = (r_cmb / rr) ** (ell + 1.0)
        P = P_cmb * factor

        Qlm = (ell * (ell + 1.0) / rr) * P
        # SHTns vector-spherical-harmonic sign conventions can differ between
        # codes. The physically expected exterior potential field has
        # |S_lm| = l P_lm / r. btheta_sign lets the converter choose the sign
        # that produces the expected CMB-to-CMB potential-field arcs.
        Slm = float(btheta_sign) * (ell / rr) * P
        Tlm = zero

        Br_ext[k], Bt_ext[k], Bp_ext[k] = sh.synth(Qlm, Slm, Tlm)

    return Br_ext, Bt_ext, Bp_ext, np.ascontiguousarray(theta_ext), np.ascontiguousarray(phi_ext)



def synthesize_cmb_Br_ltrunc(
    BP_lsd: np.ndarray,
    r_state: np.ndarray,
    lmax: int,
    mmax: int,
    l_trunc: int,
    user_modules: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Synthesize B_r on the CMB after truncating the poloidal magnetic
    coefficients to spherical-harmonic degree l <= l_trunc.

    Output is a 2-D array shaped as (ntheta, nphi), using the same SHTns grid
    convention as PolTor_to_spat/SH_to_spat.
    """
    if not hasattr(user_modules, "shtns") or not hasattr(user_modules, "lsd_to_shtns"):
        raise RuntimeError("modules.py must expose shtns and lsd_to_shtns for CMB Br truncation.")

    l_trunc = int(l_trunc)
    if l_trunc < 0:
        raise ValueError("--cmb-br-ltrunc must be >= 0")

    shtns = user_modules.shtns
    sh = shtns.sht(int(lmax), int(mmax), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    nlat, nphi = sh.set_grid()

    theta = np.arccos(sh.cos_theta)
    phi = np.linspace(0.0, 2.0 * np.pi, nphi + 2)[1:-1]

    BP_shtns = user_modules.lsd_to_shtns(BP_lsd, sh)
    P_cmb = BP_shtns[:, -1].copy()
    P_cmb[np.asarray(sh.l) > l_trunc] = 0.0

    ell = np.asarray(sh.l, dtype=np.float64)
    r_cmb = float(r_state[-1])
    Qlm = (ell * (ell + 1.0) / r_cmb) * P_cmb

    Br_cmb = sh.synth(Qlm)
    return np.ascontiguousarray(Br_cmb, dtype=np.float64), np.ascontiguousarray(theta), np.ascontiguousarray(phi)


def compute_external_field_lines_from_cmb(
    Br_ext: np.ndarray,
    Bt_ext: np.ndarray,
    Bp_ext: np.ndarray,
    r_ext: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
    ntheta_seed: int,
    nphi_seed: int,
    max_steps: int,
    step_size: float,
    seed_offset: float,
    min_points: int = 8,
    closed_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Trace exterior potential/poloidal field lines as CMB-to-CMB arcs.

    For each seed just outside the CMB, both +/-B directions are tried; the
    direction that returns to the CMB after moving outward is kept.
    """
    r_outer = float(r_ext[0])
    seed_r = r_outer + seed_offset

    theta_seeds = np.linspace(0.08 * math.pi, 0.92 * math.pi, ntheta_seed)
    phi_seeds = np.linspace(0.0, 2.0 * math.pi, nphi_seed, endpoint=False)

    lines: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}

    for theta in theta_seeds:
        for phi in phi_seeds:
            br_seed = interp_spherical_field(Br_ext, r_ext, theta_grid, phi_grid, seed_r, theta, phi)
            if not math.isfinite(br_seed) or abs(br_seed) <= 1.0e-300:
                continue

            seed = sph_to_cart(seed_r, float(theta), float(phi))
            candidates = []

            for direction in (1.0, -1.0):
                pts, status, max_r_seen = trace_exterior_cmb_to_cmb_arc(
                    seed,
                    direction,
                    Br_ext,
                    Bt_ext,
                    Bp_ext,
                    r_ext,
                    theta_grid,
                    phi_grid,
                    step_size,
                    max_steps,
                    min_points,
                )
                status_counts[status] = status_counts.get(status, 0) + 1
                candidates.append((status, max_r_seen, pts, direction))

            returned = [c for c in candidates if c[0] == "returned_cmb" and len(c[2]) >= min_points]
            if returned:
                status, max_r_seen, points, direction = max(returned, key=lambda c: len(c[2]))
            elif not closed_only:
                status, max_r_seen, points, direction = max(candidates, key=lambda c: len(c[2]))
            else:
                continue

            polarity = 1 if br_seed >= 0.0 else -1
            lines.append(
                {
                    "seed": [float(seed[0]), float(seed[1]), float(seed[2])],
                    "polarity": polarity,
                    "region": "outside_cmb_potential_poloidal",
                    "mode": "exterior_potential_poloidal_cmb_to_cmb",
                    "status": status,
                    "direction": float(direction),
                    "max_r": float(max_r_seen),
                    "points": points,
                }
            )

    compute_external_field_lines_from_cmb.last_status_counts = status_counts
    return lines


def compute_shell_field_lines_from_cmb(
    Br: np.ndarray,
    Bt: np.ndarray,
    Bp: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
    ntheta_seed: int,
    nphi_seed: int,
    max_steps: int,
    step_size: float,
    seed_offset: float,
    min_points: int = 12,
) -> list[dict[str, Any]]:
    """
    Trace the actual simulation magnetic field inside the conducting fluid shell,
    excluding the solid inner core.  Each displayed line is integrated in both
    directions from a seed just below the CMB, then concatenated so the visible
    object is a complete field-line segment rather than a one-sided trace.

    This is the mode to use when you want the dynamo field lines to loop through
    the outer-core fluid shell.
    """
    r_inner = float(r_grid[0])
    r_outer = float(r_grid[-1])
    seed_r = max(r_inner + 2.0 * step_size, r_outer - seed_offset)

    # Avoid exactly the poles because spherical basis components are singular.
    theta_seeds = np.linspace(0.08 * math.pi, 0.92 * math.pi, ntheta_seed)
    phi_seeds = np.linspace(0.0, 2.0 * math.pi, nphi_seed, endpoint=False)

    lines: list[dict[str, Any]] = []

    for theta in theta_seeds:
        for phi in phi_seeds:
            br_seed = interp_spherical_field(Br, r_grid, theta_grid, phi_grid, seed_r, theta, phi)
            if not math.isfinite(br_seed) or abs(br_seed) <= 1.0e-300:
                continue

            polarity = 1 if br_seed >= 0.0 else -1
            seed = sph_to_cart(seed_r, float(theta), float(phi))

            forward = trace_one_line(
                seed,
                1.0,
                Br,
                Bt,
                Bp,
                r_grid,
                theta_grid,
                phi_grid,
                step_size,
                max_steps,
            )
            backward = trace_one_line(
                seed,
                -1.0,
                Br,
                Bt,
                Bp,
                r_grid,
                theta_grid,
                phi_grid,
                step_size,
                max_steps,
            )

            if not forward and not backward:
                continue

            if backward:
                points = list(reversed(backward))
                if forward:
                    points += forward[1:]
            else:
                points = forward

            if len(points) < min_points:
                continue

            p0 = np.asarray(points[0], dtype=np.float64)
            p1 = np.asarray(points[-1], dtype=np.float64)
            endpoint_distance = float(np.linalg.norm(p1 - p0))
            closed = endpoint_distance <= 2.5 * step_size

            lines.append(
                {
                    "seed": [float(seed[0]), float(seed[1]), float(seed[2])],
                    "polarity": polarity,
                    "region": "fluid_shell_outside_inner_core",
                    "mode": "shell_bidirectional_actual_B",
                    "closed": bool(closed),
                    "endpoint_distance": endpoint_distance,
                    "points": points,
                }
            )

    return lines

# -----------------------------------------------------------------------------
# Main converter
# -----------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Convert a spectral Leeds spherical-dynamo state into Three.js viewer data."
    )

    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--state", "--file", dest="state", help="Path to a specific state*.cdf.dat file. --file is an alias for --state.")
    src.add_argument("--folder", help="Folder containing state*.cdf.dat files; the latest state number is used.")

    p.add_argument("--pattern", default="state*.cdf.dat", help="State filename pattern when using --folder.")
    p.add_argument("--out", default="public/data", help="Output directory for viewer data.")
    p.add_argument("--modules-dir", default=None, help="Directory containing modules.py, if not in the current directory.")
    p.add_argument("--alpha-map", type=int, default=-1, help="alpha_map argument passed to PolTor_to_spat.")
    p.add_argument(
        "--magnetic-tol",
        type=float,
        default=1.0e-300,
        help="If max(abs(BP)) is <= this value, treat the state as non-magnetic and skip B fields.",
    )
    p.add_argument(
        "--cmb-br-ltrunc",
        type=int,
        default=None,
        help=(
            "If set, export an extra CMB-only field Br_CMB_lmax<L> obtained by "
            "synthesizing B_r at the CMB after truncating BP to spherical-harmonic "
            "degree l <= L. This appears only in the CMB field selector."
        ),
    )
    p.add_argument(
        "--external-rmax",
        type=float,
        default=None,
        help="Maximum radius for external potential-field line tracing. Default is 2.5 * r_outer.",
    )
    p.add_argument(
        "--external-nr",
        type=int,
        default=96,
        help="Number of radial points in the exterior potential-field grid used for field lines.",
    )
    p.add_argument("--downsample-r", type=int, default=1, help="Keep every Nth radial point.")
    p.add_argument("--downsample-theta", type=int, default=1, help="Keep every Nth theta point.")
    p.add_argument("--downsample-phi", type=int, default=1, help="Keep every Nth phi point.")

    p.add_argument("--skip-field-lines", action="store_true", help="Do not compute magnetic field lines.")
    p.add_argument(
        "--field-line-mode",
        choices=["shell", "exterior", "both"],
        default="shell",
        help=(
            "Field-line mode. 'shell' traces the actual simulation B field inside the fluid shell "
            "outside the inner core. 'exterior' traces the exterior potential/poloidal field outside the CMB from BP at "
            "the CMB. 'both' writes both sets into the same line file."
        ),
    )
    p.add_argument(
        "--external-closed-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "For exterior lines, keep only lines that return to the CMB after moving outward. "
            "This gives CMB-to-CMB arcs. Use --no-external-closed-only to keep truncated/open traces too."
        ),
    )
    p.add_argument(
        "--external-btheta-sign",
        choices=["auto", "plus", "minus"],
        default="auto",
        help=(
            "Sign convention for the exterior poloidal B_theta coefficient. "
            "auto tries both signs and keeps the one producing more CMB-to-CMB arcs."
        ),
    )

    p.add_argument("--line-seed-theta", type=int, default=9, help="Number of CMB seed colatitudes for field lines.")
    p.add_argument("--line-seed-phi", type=int, default=18, help="Number of CMB seed longitudes for field lines.")
    p.add_argument("--line-max-steps", type=int, default=1000, help="Maximum RK4 steps for each field-line branch.")
    p.add_argument(
        "--line-step-size",
        type=float,
        default=None,
        help="Field-line RK4 step length. Default is 0.5 * median radial spacing for shell lines or 0.5 * exterior radial spacing for exterior lines.",
    )

    p.add_argument(
        "--no-gradients",
        action="store_true",
        help="Skip 3-D grad_rC and grad_rComp export. N2 profile is still computed from m=0 gradients.",
    )

    return p


def main() -> None:
    args = build_arg_parser().parse_args()

    add_modules_dir(args.modules_dir)

    try:
        user_modules = importlib.import_module("modules")
    except Exception as exc:
        raise ImportError(
            "Could not import modules.py. Run from the directory containing modules.py, "
            "or pass --modules-dir /path/to/directory."
        ) from exc

    load_state = user_modules.load_state
    PolTor_to_spat = user_modules.PolTor_to_spat
    SH_to_spat = user_modules.SH_to_spat
    SH_to_spat_nom0 = user_modules.SH_to_spat_nom0
    gradient_spat = user_modules.gradient_spat

    if args.folder:
        path = latest_state_file(args.folder, args.pattern)
    else:
        path = args.state

    path = str(Path(path).expanduser())
    state_number = parse_state_number(path)

    print(f"State file: {path}")
    print(f"State number: {state_number}")

    # Parameter extraction from path. Defaults avoid hard failure if a token is absent.
    E = parse_float_from_path(path, "Ek", np.nan)
    Pr = parse_float_from_path(path, "Pr", np.nan)
    Sc = parse_float_from_path(path, "Sc", np.nan)
    RaT = parse_float_from_path(path, "Ra", np.nan)
    RaC = parse_float_from_path(path, "RaC", np.nan)
    Cps = parse_float_from_path(path, "Cps", np.nan)

    print("Loading spectral state...")
    state = load_state(path)

    uP = state["uP"]
    uT = state["uT"]
    BP = state["BP"]
    BT = state["BT"]
    C = state["C"]
    Comp = state["Comp"]
    r = np.ascontiguousarray(np.asarray(state["r"], dtype=np.float64))
    lmax = as_scalar_int(state["lmax"], "lmax")
    mmax = as_scalar_int(state["mmax"], "mmax")
    time = float(np.asarray(state.get("t", np.nan)).item())

    print(f"lmax={lmax}, mmax={mmax}, nr={len(r)}, time={time:.8e}")
    print("Transforming velocity to physical space...")
    Ur, Ut, Up, theta, phi = PolTor_to_spat(uP, uT, r, lmax, mmax, alpha_map=args.alpha_map)

    BP_abs_max = float(np.nanmax(np.abs(BP))) if BP is not None else 0.0
    BT_abs_max = float(np.nanmax(np.abs(BT))) if BT is not None else 0.0
    has_magnetic_field = BP_abs_max > args.magnetic_tol

    if has_magnetic_field:
        print(f"Magnetic state detected: max(abs(BP))={BP_abs_max:.6e}, max(abs(BT))={BT_abs_max:.6e}")
        print("Transforming magnetic field to physical space...")
        Br, Bt, Bp, theta_B, phi_B = PolTor_to_spat(BP, BT, r, lmax, mmax, alpha_map=args.alpha_map)
    else:
        print(f"No magnetic/dynamo field detected: max(abs(BP))={BP_abs_max:.6e} <= {args.magnetic_tol:.6e}")
        if BT_abs_max > args.magnetic_tol:
            print(f"Warning: BP is zero but BT is not zero: max(abs(BT))={BT_abs_max:.6e}. Exterior field lines require BP.")
        Br = Bt = Bp = None

    print("Transforming scalar fields to physical space...")
    Cspat, theta_C, phi_C = SH_to_spat(C, lmax, mmax)
    Compspat, theta_Comp, phi_Comp = SH_to_spat(Comp, lmax, mmax)

    Cspatnom0, _, _ = SH_to_spat_nom0(C, lmax, mmax)
    Compspatnom0, _, _ = SH_to_spat_nom0(Comp, lmax, mmax)

    theta = np.ascontiguousarray(np.asarray(theta, dtype=np.float64))
    phi = np.ascontiguousarray(np.asarray(phi, dtype=np.float64))

    nr = len(r)
    ntheta = len(theta)
    nphi = len(phi)

    # Validate and standardize shapes.
    Ur = as_r_theta_phi(Ur, nr, ntheta, nphi)
    Ut = as_r_theta_phi(Ut, nr, ntheta, nphi)
    Up = as_r_theta_phi(Up, nr, ntheta, nphi)
    if has_magnetic_field:
        Br = as_r_theta_phi(Br, nr, ntheta, nphi)
        Bt = as_r_theta_phi(Bt, nr, ntheta, nphi)
        Bp = as_r_theta_phi(Bp, nr, ntheta, nphi)
    Cspat = as_r_theta_phi(Cspat, nr, ntheta, nphi)
    Compspat = as_r_theta_phi(Compspat, nr, ntheta, nphi)
    Cspatnom0 = as_r_theta_phi(Cspatnom0, nr, ntheta, nphi)
    Compspatnom0 = as_r_theta_phi(Compspatnom0, nr, ntheta, nphi)

    Uabs = np.sqrt(Ur * Ur + Ut * Ut + Up * Up)
    if has_magnetic_field:
        Babs = np.sqrt(Br * Br + Bt * Bt + Bp * Bp)

    Cspatnol0 = remove_global_mean(Cspat)
    Compspatnol0 = remove_global_mean(Compspat)

    print("Computing m=0 gradients and N2 profile...")
    Cspat_m0 = np.mean(Cspat, axis=2)
    Compspat_m0 = np.mean(Compspat, axis=2)

    grad_rC_m0, grad_theta_C_m0 = gradient_spat(Cspat_m0, r, theta)
    grad_rComp_m0, grad_theta_Comp_m0 = gradient_spat(Compspat_m0, r, theta)

    grad_rC_mean_r = np.mean(grad_rC_m0, axis=1)
    grad_rComp_mean_r = np.mean(grad_rComp_m0, axis=1)

    # If any parameter is unavailable, this will become NaN. That is intentional.
    N2_profile = r * E**2 * (grad_rComp_mean_r * RaC / Sc + grad_rC_mean_r * RaT / Pr)

    # Broadcast N2(r) to a 3-D volume so the current viewer can display it.
    N2_volume = np.broadcast_to(N2_profile[:, None, None], (nr, ntheta, nphi)).copy()

    fields: dict[str, np.ndarray] = {
        "ur": Ur,
        "ut": Ut,
        "up": Up,
        "Uabs": Uabs,
        "C": Cspat,
        "Comp": Compspat,
        "Cnom0": Cspatnom0,
        "Compnom0": Compspatnom0,
        "Cnol0": Cspatnol0,
        "Compnol0": Compspatnol0,
        "N2": N2_volume,
    }

    if has_magnetic_field:
        fields = {
            "Br": Br,
            "Bt": Bt,
            "Bp": Bp,
            "Babs": Babs,
            **fields,
        }

    if not args.no_gradients:
        print("Computing full 3-D radial gradients of C and Comp...")
        grad_rC_3d = np.empty_like(Cspat)
        grad_rComp_3d = np.empty_like(Compspat)

        for ip in range(nphi):
            grad_rC_3d[:, :, ip], _ = gradient_spat(Cspat[:, :, ip], r, theta)
            grad_rComp_3d[:, :, ip], _ = gradient_spat(Compspat[:, :, ip], r, theta)

        fields["grad_rC"] = grad_rC_3d
        fields["grad_rComp"] = grad_rComp_3d

    # Downsample after all derived quantities are computed.
    dr = max(1, int(args.downsample_r))
    dt = max(1, int(args.downsample_theta))
    dp = max(1, int(args.downsample_phi))

    if (dr, dt, dp) != (1, 1, 1):
        print(f"Downsampling fields by r/theta/phi strides: {dr}/{dt}/{dp}")
        fields = {name: downsample_3d(arr, dr, dt, dp) for name, arr in fields.items()}
        r_out = r[::dr]
        theta_out = theta[::dt]
        phi_out = phi[::dp]
        N2_profile_out = N2_profile[::dr]
        grad_rC_mean_r_out = grad_rC_mean_r[::dr]
        grad_rComp_mean_r_out = grad_rComp_mean_r[::dr]
    else:
        r_out = r
        theta_out = theta
        phi_out = phi
        N2_profile_out = N2_profile
        grad_rC_mean_r_out = grad_rC_mean_r
        grad_rComp_mean_r_out = grad_rComp_mean_r

    nr_out = len(r_out)
    ntheta_out = len(theta_out)
    nphi_out = len(phi_out)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    # Remove stale viewer files from previous conversions, but keep .gitkeep if present.
    for old in outdir.glob("*_volume.f32"):
        old.unlink()
    for old in outdir.glob("*_cmb.f32"):
        old.unlink()
    for old_name in ["metadata.json", "coordinates.json", "profiles.json", "B_lines.json", "B_lines_shell.json", "B_lines_exterior.json", "B_lines_exterior_poloidal.json", "B_lines_from_cmb.json"]:
        old = outdir / old_name
        if old.exists():
            old.unlink()

    print(f"Writing fields to {outdir}...")
    field_files: dict[str, str] = {}
    surface_fields: dict[str, dict[str, Any]] = {}
    ranges: dict[str, dict[str, float]] = {}

    for name, arr in fields.items():
        filename = f"{name}_volume.f32"
        ranges[name] = write_f32(outdir / filename, arr)
        field_files[name] = filename
        print(f"  {name:12s} {arr.shape} -> {filename}")

    if args.cmb_br_ltrunc is not None:
        if not has_magnetic_field:
            print("Skipping --cmb-br-ltrunc because this state is non-magnetic/BP is zero.")
        else:
            lcut = int(args.cmb_br_ltrunc)
            print(f"Synthesizing CMB Br truncated to l <= {lcut}...")
            Br_cmb_lcut, theta_lcut, phi_lcut = synthesize_cmb_Br_ltrunc(
                BP,
                r,
                lmax,
                mmax,
                lcut,
                user_modules,
            )

            # If the main viewer output was downsampled, use the same angular stride.
            Br_cmb_lcut = np.ascontiguousarray(Br_cmb_lcut[::dt, ::dp])
            if Br_cmb_lcut.shape != (ntheta_out, nphi_out):
                raise ValueError(
                    f"Truncated CMB Br shape {Br_cmb_lcut.shape} does not match viewer angular grid "
                    f"{(ntheta_out, nphi_out)}."
                )

            name = f"Br_CMB_lmax{lcut}"
            filename = f"{name}_cmb.f32"
            ranges[name] = write_f32(outdir / filename, Br_cmb_lcut)
            surface_fields[name] = {
                "file": filename,
                "surface": "cmb",
                "layout": "theta_phi",
                "l_trunc": lcut,
                "source": "BP at CMB",
                "description": f"B_r at the CMB synthesized from BP with l <= {lcut}",
            }
            print(f"  {name:12s} {Br_cmb_lcut.shape} -> {filename}")

    coordinates = {
        "r": [json_number(x) for x in r_out],
        "theta": [json_number(x) for x in theta_out],
        "phi": [json_number(x) for x in phi_out],
    }
    with open(outdir / "coordinates.json", "w", encoding="utf-8") as f:
        json.dump(coordinates, f, allow_nan=False)

    profiles = {
        "r": [json_number(x) for x in r_out],
        "N2": [json_number(x) for x in N2_profile_out],
        "grad_rC_mean_r": [json_number(x) for x in grad_rC_mean_r_out],
        "grad_rComp_mean_r": [json_number(x) for x in grad_rComp_mean_r_out],
    }
    with open(outdir / "profiles.json", "w", encoding="utf-8") as f:
        json.dump(profiles, f, allow_nan=False)

    field_lines_meta: dict[str, Any] = {}

    if not args.skip_field_lines and has_magnetic_field:
        shell_count = 0
        exterior_count = 0

        field_lines_meta = {
            "mode": args.field_line_mode,
            "description": (
                "shell = actual simulation B traced inside fluid shell outside the inner core; "
                "exterior = exterior potential/poloidal field outside the CMB reconstructed from BP at the CMB with toroidal field set to zero"
            ),
            "counts": {},
        }

        combined_lines: list[dict[str, Any]] = []

        if args.field_line_mode in ("shell", "both"):
            print("Computing shell magnetic field lines from the actual simulation B field...")
            shell_dr = np.diff(r)
            shell_dr = np.abs(shell_dr[np.isfinite(shell_dr) & (np.abs(shell_dr) > 0.0)])
            if shell_dr.size == 0:
                raise ValueError("Could not determine radial spacing for shell field-line tracing.")

            shell_step_size = float(args.line_step_size) if args.line_step_size is not None else 0.5 * float(np.median(shell_dr))
            shell_seed_offset = 1.5 * shell_step_size

            shell_lines = compute_shell_field_lines_from_cmb(
                Br,
                Bt,
                Bp,
                r,
                theta,
                phi,
                ntheta_seed=args.line_seed_theta,
                nphi_seed=args.line_seed_phi,
                max_steps=args.line_max_steps,
                step_size=shell_step_size,
                seed_offset=shell_seed_offset,
            )
            shell_count = len(shell_lines)
            combined_lines.extend(shell_lines)
            with open(outdir / "B_lines_shell.json", "w", encoding="utf-8") as f:
                json.dump(shell_lines, f)
            field_lines_meta["shell"] = "B_lines_shell.json"
            field_lines_meta["B_lines_shell"] = "B_lines_shell.json"
            field_lines_meta["counts"]["shell"] = shell_count
            print(f"  wrote {shell_count} shell field-line segments to B_lines_shell.json")

        if args.field_line_mode in ("exterior", "both"):
            print("Computing exterior potential magnetic field lines from BP at the CMB...")

            r_outer = float(r[-1])
            external_rmax = float(args.external_rmax) if args.external_rmax is not None else 2.5 * r_outer
            if external_rmax <= r_outer:
                raise ValueError("--external-rmax must be larger than r_outer for exterior field-line tracing.")

            external_nr = max(8, int(args.external_nr))
            r_ext = np.linspace(r_outer, external_rmax, external_nr, dtype=np.float64)

            exterior_step_size = (
                float(args.line_step_size)
                if args.line_step_size is not None
                else 0.5 * float(np.mean(np.abs(np.diff(r_ext))))
            )
            exterior_seed_offset = 0.75 * exterior_step_size

            sign_choices = {"plus": [1.0], "minus": [-1.0], "auto": [1.0, -1.0]}[args.external_btheta_sign]
            best_choice = None

            for btheta_sign in sign_choices:
                Br_ext, Bt_ext, Bp_ext, theta_ext, phi_ext = external_potential_field_from_BP(
                    BP,
                    r,
                    r_ext,
                    lmax,
                    mmax,
                    user_modules,
                    btheta_sign=btheta_sign,
                )

                trial_lines = compute_external_field_lines_from_cmb(
                    Br_ext,
                    Bt_ext,
                    Bp_ext,
                    r_ext,
                    theta_ext,
                    phi_ext,
                    ntheta_seed=args.line_seed_theta,
                    nphi_seed=args.line_seed_phi,
                    max_steps=args.line_max_steps,
                    step_size=exterior_step_size,
                    seed_offset=exterior_seed_offset,
                    closed_only=args.external_closed_only,
                )
                trial_counts = getattr(compute_external_field_lines_from_cmb, "last_status_counts", {})
                returned = int(trial_counts.get("returned_cmb", 0))
                score = (len(trial_lines), returned)
                print(
                    f"  exterior Btheta sign {btheta_sign:+.0f}: "
                    f"kept {len(trial_lines)} lines; statuses={trial_counts}"
                )
                if best_choice is None or score > best_choice[0]:
                    best_choice = (score, btheta_sign, trial_lines, trial_counts)

            assert best_choice is not None
            _, exterior_btheta_sign, exterior_lines, exterior_status_counts = best_choice
            exterior_count = len(exterior_lines)
            combined_lines.extend(exterior_lines)
            with open(outdir / "B_lines_exterior_poloidal.json", "w", encoding="utf-8") as f:
                json.dump(exterior_lines, f)
            field_lines_meta["exterior"] = "B_lines_exterior_poloidal.json"
            field_lines_meta["exterior_poloidal"] = "B_lines_exterior_poloidal.json"
            field_lines_meta["B_lines_exterior_poloidal"] = "B_lines_exterior_poloidal.json"
            field_lines_meta["B_lines_exterior"] = "B_lines_exterior_poloidal.json"
            field_lines_meta["counts"]["exterior"] = exterior_count
            field_lines_meta["exterior_btheta_sign"] = float(exterior_btheta_sign)
            field_lines_meta["exterior_status_counts"] = exterior_status_counts
            field_lines_meta["exterior_closed_only"] = bool(args.external_closed_only)
            print(
                f"  wrote {exterior_count} exterior potential/poloidal CMB-to-CMB arcs "
                f"to B_lines_exterior_poloidal.json using Btheta sign {exterior_btheta_sign:+.0f}"
            )

        # Backward-compatible combined file for older viewer versions.  The new
        # viewer reads the separate shell/exterior files when available.
        with open(outdir / "B_lines.json", "w", encoding="utf-8") as f:
            json.dump(combined_lines, f)

        field_lines_meta["B_lines"] = "B_lines.json"
        field_lines_meta["count"] = len(combined_lines)
        print(
            f"  wrote {len(combined_lines)} total magnetic field lines to B_lines.json "
            f"(shell={shell_count}, exterior={exterior_count})"
        )
    elif not args.skip_field_lines and not has_magnetic_field:
        print("Skipping field lines because BP is zero/non-magnetic.")

    meta_title = (
        f"E={format_param(E, '.1e')}, "
        f"RaT={format_param(RaT, '.1e')}, "
        f"RaC={format_param(RaC, '.1e')}, "
        f"Cps={format_param(Cps, '.0f')}, "
        f"Pr={format_param(Pr, '.2f')}, "
        f"Sc={format_param(Sc, '.2f')}, "
        f"t={format_param(time, '.2e')}"
    )

    metadata = {
        "description": "Converted physical-space quantities from Leeds spherical-dynamo state file.",
        "source_state": path,
        "state_number": state_number,
        "time": json_number(time),
        "parameters": {
            "Ek": json_number(E),
            "Pr": json_number(Pr),
            "Sc": json_number(Sc),
            "RaT": json_number(RaT),
            "RaC": json_number(RaC),
            "Cps": json_number(Cps),
        },
        "magnetic": {
            "has_magnetic_field": bool(has_magnetic_field),
            "classification": "dynamo" if has_magnetic_field else "non_magnetic",
            "BP_abs_max": json_number(BP_abs_max),
            "BT_abs_max": json_number(BT_abs_max),
            "criterion": "BP_abs_max > magnetic_tol",
            "magnetic_tol": json_number(args.magnetic_tol),
        },
        "title": meta_title,
        "nr": nr_out,
        "ntheta": ntheta_out,
        "nphi": nphi_out,
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
        "surface_fields": surface_fields,
        "ranges": ranges,
        "coordinates": "coordinates.json",
        "profiles": "profiles.json",
        "field_lines": field_lines_meta,
    }

    with open(outdir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, allow_nan=False)

    print("Done.")
    print(f"Viewer data written to: {outdir.resolve()}")
    print(f"Grid written: nr={nr_out}, ntheta={ntheta_out}, nphi={nphi_out}")
    print(f"Fields: {', '.join(field_files.keys())}")


if __name__ == "__main__":
    main()
