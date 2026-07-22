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
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np


EARTH_RADIUS_KM = 6371.0
CMB_RADIUS_KM = 3480.0
DEFAULT_EARTH_RADIUS_SCALE = EARTH_RADIUS_KM / CMB_RADIUS_KM
DEFAULT_EARTH_BR_LMAX = 13


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


def parse_float_from_path_aliases(path: str, aliases: list[str] | tuple[str, ...], default: float = np.nan) -> float:
    """Extract a float from a path using several possible parameter names."""
    for key in aliases:
        value = parse_float_from_path(path, key, None)
        if value is not None:
            return float(value)
    return default


PARAMETER_SPECS = {
    "Ek": {
        "label": "Ekman number",
        "aliases": ("Ek", "E"),
        "arg": "Ek",
    },
    "Pr": {
        "label": "thermal Prandtl number",
        "aliases": ("Pr", "PrT", "Pr_T"),
        "arg": "Pr",
    },
    "Sc": {
        "label": "compositional Prandtl/Schmidt number",
        "aliases": ("Sc", "PrC", "Pr_C"),
        "arg": "Sc",
    },
    "RaT": {
        "label": "thermal Rayleigh number",
        "aliases": ("RaT", "Ra_T", "Ra"),
        "arg": "RaT",
    },
    "RaC": {
        "label": "compositional Rayleigh number",
        "aliases": ("RaC", "Ra_C"),
        "arg": "RaC",
    },
}


def prompt_float_parameter(name: str, label: str, aliases: list[str] | tuple[str, ...]) -> float:
    """Ask the user for a missing parameter. Blank input keeps NaN."""
    aliases_text = "/".join(aliases)
    prompt = f"Enter {name} ({label}; aliases: {aliases_text}); blank = NaN: "
    while True:
        value = input(prompt).strip()
        if value == "":
            return float("nan")
        try:
            return float(value)
        except ValueError:
            print(f"Could not parse {value!r} as a float. Try again, or press Enter for NaN.")


def resolve_parameter_values(path: str, args: argparse.Namespace, prompt_missing: bool = True) -> dict[str, float]:
    """
    Resolve physical/control parameters from CLI overrides, path aliases, or prompt.

    Used for metadata and for N2. Sequence conversion calls this once and passes
    resolved values to each frame so the user is not prompted for every frame.
    """
    values: dict[str, float] = {}

    for name, spec in PARAMETER_SPECS.items():
        cli_value = getattr(args, spec["arg"], None)
        if cli_value is not None:
            values[name] = float(cli_value)
            continue

        values[name] = parse_float_from_path_aliases(path, spec["aliases"], np.nan)

    missing = [name for name, value in values.items() if not np.isfinite(value)]
    if missing and prompt_missing:
        if sys.stdin is not None and sys.stdin.isatty():
            print("\nSome parameters were not found in the path or command line.")
            print("These values are used in metadata and, for Ek/Pr/Sc/RaT/RaC, in N2.")
            for name in missing:
                spec = PARAMETER_SPECS[name]
                values[name] = prompt_float_parameter(name, spec["label"], spec["aliases"])
            print("")
        else:
            print(
                "WARNING: missing parameters could not be prompted because stdin is not interactive: "
                + ", ".join(missing)
            )

    return values


def append_parameter_overrides(cmd: list[str], args: argparse.Namespace) -> None:
    """Forward explicitly resolved parameter values to subprocess conversion."""
    for name, spec in PARAMETER_SPECS.items():
        value = getattr(args, spec["arg"], None)
        if value is not None and np.isfinite(value):
            cmd += [f"--{spec['arg']}", str(value)]


def parse_state_number(path: str) -> int:
    match = re.search(r"state(\d+)\.cdf\.dat", Path(path).name)
    return int(match.group(1)) if match else -1


def latest_state_file(folder: str, pattern: str = "state*.cdf.dat") -> str:
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} in {folder!r}")
    return max(files, key=parse_state_number)



def list_state_files(folder: str, pattern: str = "state*.cdf.dat") -> list[str]:
    files = glob.glob(os.path.join(folder, pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} in {folder!r}")
    return sorted(files, key=parse_state_number)


def choose_regular_seed_grid(total_seeds: int) -> tuple[int, int]:
    """Choose an approximately regular theta/phi seed grid for about total_seeds points."""
    total = max(1, int(total_seeds))
    # For a spherical lon/lat grid, roughly twice as many longitudes as colatitudes
    # gives a visually regular sampling. For 360 this gives 13 x 28 ~= 364.
    ntheta = max(2, int(round(math.sqrt(total / 2.0))))
    nphi = max(4, int(math.ceil(total / ntheta)))
    return ntheta, nphi


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


def full_sphere_center_mask(r: np.ndarray, tolerance: float) -> np.ndarray:
    """Return the radial mask corresponding to the coordinate-singular centre."""
    rr = np.asarray(r, dtype=np.float64)
    scale = max(1.0, float(np.nanmax(np.abs(rr))))
    return np.abs(rr) <= float(tolerance) * scale


REGULAR_RADIAL_REPRESENTATION = "regular_r_power_g_x"
CONVENTIONAL_RADIAL_REPRESENTATION = "conventional_r_coefficient"


def _decode_netcdf_attribute(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    arr = np.asarray(value)
    if arr.size == 0:
        return default
    item = arr.reshape(-1)[0]
    if isinstance(item, bytes):
        return item.decode("utf-8", errors="replace")
    if isinstance(item, np.generic):
        return item.item()
    return item


def read_state_radial_representations(path: str) -> dict[str, dict[str, Any]]:
    """Read Leeds radial-representation attributes without depending on modules.py.

    Stage-5/6 full-sphere states store regular coefficients G_lm(x), not the
    conventional f_lm(r). Older states either carry
    ``conventional_r_coefficient`` or no attribute at all.
    """
    names = ("uP", "uT", "BP", "BT", "C", "Comp")
    result = {
        name: {
            "representation": None,
            "power_offset": 0,
            "attribute_present": False,
        }
        for name in names
    }

    try:
        import h5py  # type: ignore

        with h5py.File(path, "r") as handle:
            for name in names:
                if name not in handle:
                    continue
                var = handle[name]
                raw_rep = var.attrs.get("radial_representation")
                raw_offset = var.attrs.get("radial_power_offset", 0)
                rep = _decode_netcdf_attribute(raw_rep, None)
                result[name] = {
                    "representation": None if rep is None else str(rep).strip(),
                    "power_offset": int(_decode_netcdf_attribute(raw_offset, 0)),
                    "attribute_present": raw_rep is not None,
                }
            return result
    except Exception:
        pass

    try:
        from scipy import io as scipy_io  # type: ignore

        handle = scipy_io.netcdf_file(path, "r", mmap=False)
        try:
            for name in names:
                if name not in handle.variables:
                    continue
                var = handle.variables[name]
                raw_rep = getattr(var, "radial_representation", None)
                raw_offset = getattr(var, "radial_power_offset", 0)
                rep = _decode_netcdf_attribute(raw_rep, None)
                result[name] = {
                    "representation": None if rep is None else str(rep).strip(),
                    "power_offset": int(_decode_netcdf_attribute(raw_offset, 0)),
                    "attribute_present": raw_rep is not None,
                }
        finally:
            handle.close()
    except Exception as exc:
        print(f"WARNING: could not inspect radial-representation attributes: {exc}")

    return result


def get_shtns_transform(user_modules: Any, lmax: int, mmax: int) -> tuple[Any, Any]:
    """Return the SHTns module and configured transform used by modules.py."""
    shtns_module = getattr(user_modules, "shtns", None)
    if shtns_module is None:
        try:
            shtns_module = importlib.import_module("shtns")
        except Exception as exc:
            raise RuntimeError(
                "Full-sphere regular-coefficient conversion requires SHTns. "
                "Use the same Python environment as modules.py."
            ) from exc

    sh = shtns_module.sht(
        int(lmax),
        int(mmax),
        1,
        shtns_module.sht_schmidt | shtns_module.SHT_NO_CS_PHASE,
    )
    return shtns_module, sh


def lsd_to_shtns_coefficients(coeffs_lsd: np.ndarray, sh: Any, user_modules: Any) -> np.ndarray:
    """Convert Leeds real/imag storage to the SHTns complex normalization."""
    if hasattr(user_modules, "lsd_to_shtns"):
        out = np.asarray(user_modules.lsd_to_shtns(np.asarray(coeffs_lsd), sh))
    else:
        arr = np.asarray(coeffs_lsd)
        if arr.ndim != 3 or arr.shape[0] != 2:
            raise ValueError(f"Expected Leeds coefficients (2,nlm,nr), got {arr.shape}.")
        out = arr[0].astype(np.complex128) + 1j * arr[1].astype(np.complex128)
        correction = np.where(np.asarray(sh.m) > 0, math.sqrt(2.0), 1.0)
        out = out * correction[:, None]

    if out.shape[0] != len(sh.l):
        raise ValueError(
            f"SHTns coefficient count mismatch: coefficients={out.shape[0]}, transform={len(sh.l)}."
        )
    return np.ascontiguousarray(out, dtype=np.complex128)


def fullsphere_x_derivative_matrix(r: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    """Leeds local finite-difference matrix in x=r^2.

    This mirrors ``mes_rdom_init`` in the uploaded Leeds code. With the normal
    ``i_KL=3``, each interior row uses seven points. The local Taylor matrix is
    built with columns (x_j-x_n)^k/k!, so row 2 of its inverse gives d/dx.
    """
    rr = np.asarray(r, dtype=np.float64)
    x = rr * rr
    nrad = x.size
    if nrad < 3:
        raise ValueError("Full-sphere conversion requires at least three radial points.")
    if not np.all(np.diff(x) > 0.0):
        raise ValueError("Full-sphere x=r^2 grid must be strictly increasing.")

    kl = min(3, max(1, (nrad - 1) // 2))
    D = np.zeros((nrad, nrad), dtype=np.float64)
    for n in range(nrad):
        left = max(0, n - kl)
        right = min(n + kl, nrad - 1)
        ids = np.arange(left, right + 1)
        nn = ids.size
        A = np.ones((nn, nn), dtype=np.float64)
        delta = x[ids] - x[n]
        for column in range(1, nn):
            A[:, column] = A[:, column - 1] * delta / float(column)
        try:
            invA = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            invA = np.linalg.pinv(A, rcond=1.0e-14)
        D[n, ids] = invA[1, :]
    return D, x, f"leeds_local_finite_difference_x_KL{kl}"


def derivative_in_fullsphere_x(values: np.ndarray, r: np.ndarray) -> tuple[np.ndarray, str]:
    """Differentiate spectral radial values with the Leeds seven-point x stencil."""
    D, _x, method = fullsphere_x_derivative_matrix(r)
    arr = np.asarray(values, dtype=np.complex128)
    out = np.empty_like(arr)
    for n in range(D.shape[0]):
        ids = np.flatnonzero(D[n])
        out[:, n] = arr[:, ids] @ D[n, ids]
    return np.ascontiguousarray(out), method


def safe_radius_powers(r: np.ndarray, powers: np.ndarray) -> np.ndarray:
    """Return r**power for non-negative integer powers, including r=0."""
    rr = np.asarray(r, dtype=np.float64)[None, :]
    pp = np.asarray(powers, dtype=np.int64)[:, None]
    if np.any(pp < 0):
        raise ValueError("Negative radial powers are not regular at the full-sphere centre.")
    out = np.ones((pp.shape[0], rr.shape[1]), dtype=np.float64)
    positive = pp[:, 0] > 0
    if np.any(positive):
        out[positive] = np.power(rr, pp[positive], dtype=np.float64)
    return out


def leeds_regular_projection_weights(
    r: np.ndarray,
    power: int,
    stencil_size: int = 7,
    amplitude_floor: float = 1.0e-6,
) -> np.ndarray:
    """Leeds stage-5 bounded projection f=r^p G -> G.

    This mirrors ``var_fullsphere_projection_precompute`` from the uploaded
    Leeds code. The standard Leeds ``i_KL=3`` gives K=2*i_KL+1=7.
    """
    rr = np.asarray(r, dtype=np.float64)
    x = rr * rr
    nrad = rr.size
    K = min(int(stencil_size), nrad)
    if K % 2 == 0:
        K -= 1
    if K < 3:
        raise ValueError("Not enough radial points for the full-sphere regular projection.")
    if power == 0:
        return np.eye(nrad, dtype=np.float64)

    half = K // 2
    nsafe = nrad - K
    for n in range(1, nrad - K + 1):
        if rr[n] ** power >= amplitude_floor:
            nsafe = n
            break

    W = np.zeros((nrad, nrad), dtype=np.float64)
    for n in range(nsafe, nrad):
        i0 = max(nsafe, n - half)
        i0 = min(i0, nrad - K)
        ids = np.arange(i0, i0 + K)
        x0 = x[n]
        scale = max(float(np.max(np.abs(x[ids] - x0))), np.finfo(np.float64).eps)
        z = (x[ids] - x0) / scale
        A = np.empty((K, K), dtype=np.float64)
        A[:, 0] = rr[ids] ** power
        for k in range(1, K):
            A[:, k] = A[:, k - 1] * z
        try:
            invA = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            invA = np.linalg.pinv(A, rcond=1.0e-13)
        W[n, ids] = invA[0, :]

    if nsafe > 0:
        W[:nsafe, :] = W[nsafe, :]
    return W


def conventional_lsd_to_regular(
    coeffs_lsd: np.ndarray,
    r: np.ndarray,
    degrees: np.ndarray,
    power_offset: int,
    field_name: str,
) -> np.ndarray:
    """Project legacy conventional full-sphere coefficients to regular G_lm(x)."""
    arr = np.asarray(coeffs_lsd, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[0] != 2:
        raise ValueError(f"{field_name}: expected coefficients (2,nlm,nr), got {arr.shape}.")
    out = np.empty_like(arr)
    cache: dict[int, np.ndarray] = {}
    for mode, degree in enumerate(np.asarray(degrees, dtype=int)):
        power = int(degree) + int(power_offset)
        if power not in cache:
            cache[power] = leeds_regular_projection_weights(r, power)
        W = cache[power]
        out[0, mode, :] = W @ arr[0, mode, :]
        out[1, mode, :] = W @ arr[1, mode, :]
    print(
        f"  {field_name}: projected legacy conventional coefficients to Leeds regular G_lm(x) "
        "with the bounded K=7 stage-5 projection."
    )
    return np.ascontiguousarray(out)


def ensure_fullsphere_regular_coefficients(
    coeffs_lsd: np.ndarray,
    radial_meta: dict[str, Any],
    r: np.ndarray,
    degrees: np.ndarray,
    field_name: str,
) -> tuple[np.ndarray, int, str]:
    """Return regular G_lm(x) coefficients for a full-sphere variable."""
    representation = radial_meta.get("representation")
    offset = int(radial_meta.get("power_offset", 0))
    if representation == REGULAR_RADIAL_REPRESENTATION:
        return np.ascontiguousarray(coeffs_lsd), offset, "stored_regular"
    if representation in (None, "", CONVENTIONAL_RADIAL_REPRESENTATION):
        regular = conventional_lsd_to_regular(coeffs_lsd, r, degrees, offset, field_name)
        return regular, offset, "legacy_conventional_projected"
    raise ValueError(
        f"{field_name}: unsupported radial_representation={representation!r}."
    )


def regular_scalar_lsd_to_conventional(
    coeffs_lsd: np.ndarray,
    r: np.ndarray,
    degrees: np.ndarray,
    power_offset: int,
) -> np.ndarray:
    """Form the physical scalar coefficients f_lm=r^(l+p0)G_lm(x)."""
    powers = np.asarray(degrees, dtype=int) + int(power_offset)
    radial_factor = safe_radius_powers(r, powers)
    return np.ascontiguousarray(np.asarray(coeffs_lsd) * radial_factor[None, :, :])


def fullsphere_regular_poltors_to_spat(
    pol_lsd: np.ndarray,
    tor_lsd: np.ndarray,
    r: np.ndarray,
    lmax: int,
    mmax: int,
    user_modules: Any,
    pol_power_offset: int = 0,
    tor_power_offset: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, str]:
    """Leeds full-sphere regular QST reconstruction followed by SHTns synthesis.

    For P=r^(l+pP)G(x), T=r^(l+pT)H(x), x=r^2, the coefficients
    passed directly to SHTns are

      Q = l(l+1) r^(l+pP-1) G,
      S = +r^(l+pP-1)[(l+pP+1)G + 2x G_x],
      T = r^(l+pT) H.

    The positive S sign is the Leeds full-sphere convention. In
    ``var_coll_TorPol2qst_fullsphere`` the code first forms
    s_code=sqrt(l(l+1))*[...] and t_code=-sqrt(l(l+1))*r^l H;
    ``tra_qst2rtp_shtns`` then applies the SHTns normalization and negates
    t_code. The resulting direct SHTns coefficients are therefore +S and +T.
    This differs from the shell helper ``modules.py::PolTor_to_qst``, whose
    conventional-potential S line is marked ``#check the sign`` and must not
    be reused for the regular full-sphere path.
    """
    _, sh = get_shtns_transform(user_modules, lmax, mmax)
    nlat, nphi = sh.set_grid()
    theta = np.arccos(np.asarray(sh.cos_theta, dtype=np.float64))
    phi = np.linspace(0.0, 2.0 * np.pi, int(nphi) + 2)[1:-1]

    G = lsd_to_shtns_coefficients(pol_lsd, sh, user_modules)
    H = lsd_to_shtns_coefficients(tor_lsd, sh, user_modules)
    Gx, derivative_method = derivative_in_fullsphere_x(G, r)

    degrees = np.asarray(sh.l, dtype=int)
    ll1 = degrees * (degrees + 1)
    pol_exponent = degrees + int(pol_power_offset) - 1
    tor_exponent = degrees + int(tor_power_offset)

    # l=0 is absent from a solenoidal vector. Set its Q/S factors separately
    # so no negative exponent is ever evaluated.
    pol_factor = np.zeros((degrees.size, len(r)), dtype=np.float64)
    active = ll1 > 0
    if np.any(active):
        if np.any(pol_exponent[active] < 0):
            raise ValueError("Full-sphere poloidal power offset produces a singular l>0 mode.")
        pol_factor[active] = safe_radius_powers(r, pol_exponent[active])
    tor_factor = safe_radius_powers(r, tor_exponent)

    x = (np.asarray(r, dtype=np.float64) ** 2)[None, :]
    Qlm = ll1[:, None] * pol_factor * G
    # Leeds full-sphere -> SHTns convention:
    # var_coll_TorPol2qst_fullsphere forms a positive code-space s, and
    # tra_qst2rtp_shtns multiplies it by +shtns_norm_st.  Do not copy the
    # negative shell-potential sign from modules.py::PolTor_to_qst here.
    Slm = pol_factor * (
        (degrees + int(pol_power_offset) + 1)[:, None] * G + 2.0 * x * Gx
    )
    Tlm = tor_factor * H
    Qlm[~active, :] = 0.0
    Slm[~active, :] = 0.0
    Tlm[degrees == 0, :] = 0.0

    nr = len(r)
    vr = np.empty((nr, nlat, nphi), dtype=np.float64)
    vt = np.empty_like(vr)
    vp = np.empty_like(vr)
    for k in range(nr):
        vr[k], vt[k], vp[k] = sh.synth(Qlm[:, k], Slm[:, k], Tlm[:, k])

    for name, arr in (("radial", vr), ("theta", vt), ("phi", vp)):
        if not np.all(np.isfinite(arr)):
            count = int(np.sum(~np.isfinite(arr)))
            raise ValueError(
                f"Full-sphere regular {name} vector component contains {count} non-finite values."
            )
    return vr, vt, vp, theta, phi, derivative_method


def enforce_fullsphere_cartesian_center_limit(
    ur: np.ndarray,
    ut: np.ndarray,
    up: np.ndarray,
    theta: np.ndarray,
    phi: np.ndarray,
    center_mask: np.ndarray,
    name: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, float]]:
    """Enforce the single Cartesian vector represented by the l=1 centre limit.

    At r=0 the spherical basis varies with angle, but a regular vector has one
    Cartesian value. Leeds' direct regular QST reconstruction supplies finite
    l=1 spherical components. We average their Cartesian representation and
    project that one vector back onto every angular basis at the centre.
    """
    vr = np.ascontiguousarray(np.asarray(ur, dtype=np.float64).copy())
    vt = np.ascontiguousarray(np.asarray(ut, dtype=np.float64).copy())
    vp = np.ascontiguousarray(np.asarray(up, dtype=np.float64).copy())
    th = np.asarray(theta, dtype=np.float64)[:, None]
    ph = np.asarray(phi, dtype=np.float64)[None, :]
    st, ct = np.sin(th), np.cos(th)
    sp, cp = np.sin(ph), np.cos(ph)

    diagnostics = {"cartesian_center_magnitude": 0.0, "cartesian_center_relative_spread": 0.0}
    for ir in np.flatnonzero(center_mask):
        rr = vr[int(ir)]
        tt = vt[int(ir)]
        pp = vp[int(ir)]
        ux = rr * st * cp + tt * ct * cp - pp * sp
        uy = rr * st * sp + tt * ct * sp + pp * cp
        uz = rr * ct - tt * st
        finite = np.isfinite(ux) & np.isfinite(uy) & np.isfinite(uz)
        if not np.any(finite):
            raise ValueError(f"{name} has no finite Cartesian centre values.")
        center_vector = np.array(
            [np.mean(ux[finite]), np.mean(uy[finite]), np.mean(uz[finite])],
            dtype=np.float64,
        )
        sample_norm = np.sqrt(ux * ux + uy * uy + uz * uz)
        sample_scale = float(np.nanmax(sample_norm[finite]))
        global_scale = float(
            np.nanmax(np.sqrt(vr * vr + vt * vt + vp * vp))
        )
        if sample_scale <= 1.0e-12 * max(global_scale, 1.0):
            center_vector[:] = 0.0
            sample_scale = 0.0
        magnitude = float(np.linalg.norm(center_vector))
        spread = np.sqrt(
            (ux - center_vector[0]) ** 2
            + (uy - center_vector[1]) ** 2
            + (uz - center_vector[2]) ** 2
        )
        relative_spread = (
            0.0
            if sample_scale == 0.0
            else float(np.nanmax(spread[finite]) / max(sample_scale, 1.0e-30))
        )
        diagnostics = {
            "cartesian_center_magnitude": magnitude,
            "cartesian_center_relative_spread": relative_spread,
        }
        if relative_spread > 1.0e-6:
            print(
                f"WARNING: {name} centre Cartesian spread is {relative_spread:.3e}; "
                "replacing it by the angular mean regular limit."
            )

        vx, vy, vz = center_vector
        vr[int(ir)] = vx * st * cp + vy * st * sp + vz * ct
        vt[int(ir)] = vx * ct * cp + vy * ct * sp - vz * st
        vp[int(ir)] = -vx * sp + vy * cp

    for component_name, arr in (("r", vr), ("theta", vt), ("phi", vp)):
        if not np.all(np.isfinite(arr)):
            count = int(np.sum(~np.isfinite(arr)))
            raise ValueError(f"{name}_{component_name} contains {count} non-finite values.")
    return vr, vt, vp, diagnostics


def regularize_scalar_center(arr: np.ndarray, center_mask: np.ndarray, name: str) -> np.ndarray:
    """Enforce angular regularity of a scalar at the origin."""
    out = np.ascontiguousarray(np.asarray(arr, dtype=np.float64).copy())
    for ir in np.flatnonzero(center_mask):
        layer = out[int(ir)]
        finite = np.isfinite(layer)
        if not np.any(finite):
            raise ValueError(f"{name} has no finite values at the full-sphere centre.")
        centre_value = float(np.mean(layer[finite]))
        out[int(ir), :, :] = centre_value

    nonfinite = ~np.isfinite(out)
    if np.any(nonfinite):
        count = int(np.sum(nonfinite))
        raise ValueError(f"{name} contains {count} non-finite values after centre regularization.")
    return out


def regularize_scalar_gradient_center(
    grad_r: np.ndarray,
    grad_theta: np.ndarray,
    grad_phi: np.ndarray,
    center_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Make scalar-gradient diagnostics finite at r=0.

    Angular derivatives vanish at a regular scalar centre.  The radial derivative
    is represented by its angular mean because all angular grid points collapse
    to the same Cartesian point at r=0.
    """
    gr = np.ascontiguousarray(np.asarray(grad_r, dtype=np.float64).copy())
    gt = np.ascontiguousarray(np.asarray(grad_theta, dtype=np.float64).copy())
    gp = np.ascontiguousarray(np.asarray(grad_phi, dtype=np.float64).copy())
    for ir in np.flatnonzero(center_mask):
        finite = np.isfinite(gr[int(ir)])
        radial_value = float(np.mean(gr[int(ir)][finite])) if np.any(finite) else 0.0
        gr[int(ir), :, :] = radial_value
        gt[int(ir), :, :] = 0.0
        gp[int(ir), :, :] = 0.0
    return gr, gt, gp


def remove_global_mean(arr: np.ndarray) -> np.ndarray:
    return arr - np.mean(arr, axis=(0, 1, 2))


def phi_average_volume(arr: np.ndarray, name: str = "field") -> np.ndarray:
    """
    Phi-average a 3-D field and broadcast it back to full (r,theta,phi) shape.

    This intentionally ignores non-finite values and extreme floating-point
    outliers on each longitude ring. A single corrupted value in phi should not
    contaminate the whole m=0 diagnostic.
    """
    arr = np.asarray(arr, dtype=np.float64)
    finite = np.isfinite(arr)

    if not np.any(finite):
        print(f"WARNING: {name}_phiavg has no finite input values; writing NaNs.")
        mean2d = np.full(arr.shape[:2] + (1,), np.nan, dtype=np.float64)
        return np.broadcast_to(mean2d, arr.shape).copy()

    # Global sanity limit removes obvious uninitialised/sentinel values while
    # keeping the real dynamic range. This is deliberately permissive.
    abs_good = np.abs(arr[finite])
    global_med = float(np.nanmedian(abs_good))
    global_p99 = float(np.nanpercentile(abs_good, 99.9))
    global_limit = min(max(1.0e8 * max(global_med, 1.0e-300), 100.0 * global_p99), 1.0e20)

    good = finite & (np.abs(arr) <= global_limit)
    counts = np.sum(good, axis=2, keepdims=True)
    sums = np.sum(np.where(good, arr, 0.0), axis=2, keepdims=True)

    with np.errstate(invalid="ignore", divide="ignore"):
        mean2d = sums / counts

    mean2d[counts == 0] = np.nan

    rejected = int(arr.size - np.sum(good))
    if rejected > 0:
        print(
            f"WARNING: {name}_phiavg ignored {rejected} non-finite/extreme values "
            f"(limit={global_limit:.3e})."
        )

    return np.broadcast_to(mean2d, arr.shape).copy()


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


def truncate_lsd_coefficients(
    coeffs_lsd: np.ndarray | None,
    lmax_in: int,
    mmax_in: int,
    lmax_out: int,
    mmax_out: int,
    user_modules: Any,
) -> np.ndarray | None:
    """
    Return LSD coefficients truncated to l <= lmax_out and m <= mmax_out.

    The Leeds modules.py helper lsd_to_shtns assumes the LSD coefficient ordering
    matches the SHTns (l,m) list for the chosen lmax/mmax. Therefore, reducing
    lmax must build a smaller LSD array rather than simply passing a smaller
    lmax to PolTor_to_spat/SH_to_spat.
    """
    if coeffs_lsd is None:
        return None

    if lmax_out >= lmax_in and mmax_out >= mmax_in:
        return coeffs_lsd

    if not hasattr(user_modules, "shtns"):
        raise RuntimeError("modules.py must expose shtns for --spectral-lmax truncation.")

    arr = np.asarray(coeffs_lsd)
    if arr.ndim < 2 or arr.shape[0] != 2:
        raise ValueError(f"Expected LSD coefficients shaped like (2, nlm, ...), got {arr.shape}")

    shtns = user_modules.shtns
    sh_in = shtns.sht(int(lmax_in), int(mmax_in), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    sh_out = shtns.sht(int(lmax_out), int(mmax_out), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)

    in_map = {(int(l), int(m)): i for i, (l, m) in enumerate(zip(sh_in.l, sh_in.m))}
    out = np.zeros((2, len(sh_out.l)) + tuple(arr.shape[2:]), dtype=arr.dtype)

    missing = 0
    for j, (l, m) in enumerate(zip(sh_out.l, sh_out.m)):
        src = in_map.get((int(l), int(m)))
        if src is None:
            missing += 1
            continue
        out[:, j, ...] = arr[:, src, ...]

    if missing:
        print(f"WARNING: spectral truncation could not map {missing} (l,m) coefficients.")

    return np.ascontiguousarray(out)


def apply_spectral_lmax_to_state(
    uP: np.ndarray,
    uT: np.ndarray,
    BP: np.ndarray | None,
    BT: np.ndarray | None,
    C: np.ndarray,
    Comp: np.ndarray | None,
    lmax: int,
    mmax: int,
    spectral_lmax: int | None,
    user_modules: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None, np.ndarray, np.ndarray | None, int, int, dict[str, Any]]:
    """
    Apply an angular spectral cutoff before transforming to physical space.
    """
    if spectral_lmax is None or int(spectral_lmax) <= 0:
        return uP, uT, BP, BT, C, Comp, int(lmax), int(mmax), {
            "enabled": False,
            "requested_lmax": None if spectral_lmax is None else int(spectral_lmax),
            "lmax_original": int(lmax),
            "mmax_original": int(mmax),
            "lmax_effective": int(lmax),
            "mmax_effective": int(mmax),
        }

    l_eff = min(int(spectral_lmax), int(lmax))
    m_eff = min(int(mmax), l_eff)

    if l_eff == int(lmax) and m_eff == int(mmax):
        return uP, uT, BP, BT, C, Comp, int(lmax), int(mmax), {
            "enabled": False,
            "requested_lmax": int(spectral_lmax),
            "lmax_original": int(lmax),
            "mmax_original": int(mmax),
            "lmax_effective": int(lmax),
            "mmax_effective": int(mmax),
        }

    print(
        f"Applying angular spectral truncation before spatial transform: "
        f"lmax {int(lmax)} -> {l_eff}, mmax {int(mmax)} -> {m_eff}"
    )

    return (
        truncate_lsd_coefficients(uP, lmax, mmax, l_eff, m_eff, user_modules),
        truncate_lsd_coefficients(uT, lmax, mmax, l_eff, m_eff, user_modules),
        truncate_lsd_coefficients(BP, lmax, mmax, l_eff, m_eff, user_modules),
        truncate_lsd_coefficients(BT, lmax, mmax, l_eff, m_eff, user_modules),
        truncate_lsd_coefficients(C, lmax, mmax, l_eff, m_eff, user_modules),
        truncate_lsd_coefficients(Comp, lmax, mmax, l_eff, m_eff, user_modules),
        l_eff,
        m_eff,
        {
            "enabled": True,
            "requested_lmax": int(spectral_lmax),
            "lmax_original": int(lmax),
            "mmax_original": int(mmax),
            "lmax_effective": int(l_eff),
            "mmax_effective": int(m_eff),
            "method": "LSD coefficients remapped by (l,m) before physical-space synthesis",
        },
    )


def remove_m0_phi(arr: np.ndarray) -> np.ndarray:
    """Remove the azimuthal m=0 component, i.e. subtract the phi-mean."""
    return arr - np.mean(arr, axis=2, keepdims=True)


def gradient_phi_periodic(arr: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """Periodic central-difference derivative along phi for arr[r,theta,phi]."""
    phi = np.asarray(phi, dtype=np.float64)
    if phi.size < 2:
        return np.zeros_like(arr, dtype=np.float64)
    dphi = float(np.mean(np.diff(phi)))
    return (np.roll(arr, -1, axis=2) - np.roll(arr, 1, axis=2)) / (2.0 * dphi)


def gradient_scalar_3d(field: np.ndarray, r: np.ndarray, theta: np.ndarray, phi: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return d/dr, d/dtheta, d/dphi for a scalar field[r,theta,phi]."""
    dr = np.gradient(field, np.asarray(r, dtype=np.float64), axis=0, edge_order=2)
    dtheta = np.gradient(field, np.asarray(theta, dtype=np.float64), axis=1, edge_order=2)
    dphi = gradient_phi_periodic(field, phi)
    return np.ascontiguousarray(dr), np.ascontiguousarray(dtheta), np.ascontiguousarray(dphi)


def compute_helicity(Ur: np.ndarray, Ut: np.ndarray, Up: np.ndarray, r: np.ndarray, theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """Compute kinetic helicity u·(curl u), with a finite full-sphere centre."""
    rr = np.asarray(r, dtype=np.float64)
    r3 = rr[:, None, None]
    center_mask = np.abs(rr) <= max(1.0, float(np.nanmax(np.abs(rr)))) * 1.0e-14
    r_safe = np.where(center_mask, 1.0, rr)[:, None, None]

    theta1 = np.asarray(theta, dtype=np.float64)[None, :, None]
    sin_theta = np.sin(theta1)
    sin_safe = np.where(np.abs(sin_theta) < 1.0e-8, 1.0e-8, sin_theta)

    dtheta_up_sin = np.gradient(Up * sin_theta, np.asarray(theta, dtype=np.float64), axis=1, edge_order=2)
    dphi_ut = gradient_phi_periodic(Ut, phi)
    dphi_ur = gradient_phi_periodic(Ur, phi)

    dr_rup = np.gradient(r3 * Up, rr, axis=0, edge_order=2)
    dr_rut = np.gradient(r3 * Ut, rr, axis=0, edge_order=2)
    dtheta_ur = np.gradient(Ur, np.asarray(theta, dtype=np.float64), axis=1, edge_order=2)

    with np.errstate(invalid="ignore", divide="ignore", over="ignore"):
        omega_r = (dtheta_up_sin - dphi_ut) / (r_safe * sin_safe)
        omega_theta = ((dphi_ur / sin_safe) - dr_rup) / r_safe
        omega_phi = (dr_rut - dtheta_ur) / r_safe
        helicity = Ur * omega_r + Ut * omega_theta + Up * omega_phi

    if np.any(center_mask):
        helicity[center_mask, :, :] = 0.0
    if not np.all(np.isfinite(helicity)):
        count = int(np.sum(~np.isfinite(helicity)))
        raise ValueError(f"Helicity contains {count} non-finite values after centre regularization.")
    return np.ascontiguousarray(helicity, dtype=np.float64)


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



def sample_line_strengths(
    points: list[list[float]],
    Br: np.ndarray,
    Bt: np.ndarray,
    Bp: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
) -> list[float | None]:
    """
    Sample |B| along a traced field line.

    JSON does not allow NaN/Inf.  Non-finite interpolation samples are written
    as None, which becomes null in JSON and is safely ignored by the viewer.
    """
    strengths: list[float | None] = []
    for p in points:
        x = np.asarray(p, dtype=np.float64)
        r, theta, phi = cart_to_sph(x)
        br = interp_spherical_field(Br, r_grid, theta_grid, phi_grid, r, theta, phi)
        bt = interp_spherical_field(Bt, r_grid, theta_grid, phi_grid, r, theta, phi)
        bp = interp_spherical_field(Bp, r_grid, theta_grid, phi_grid, r, theta, phi)
        if not np.isfinite([br, bt, bp]).all():
            strengths.append(None)
        else:
            babs = float(math.sqrt(br * br + bt * bt + bp * bp))
            strengths.append(babs if math.isfinite(babs) else None)
    return strengths


def radius_of(x: np.ndarray) -> float:
    return float(np.linalg.norm(x))


def append_point(points: list[list[float]], x: np.ndarray, min_separation: float = 0.0) -> None:
    if min_separation > 0.0 and points:
        last = np.asarray(points[-1], dtype=np.float64)
        if float(np.linalg.norm(np.asarray(x, dtype=np.float64) - last)) <= min_separation:
            return
    points.append([float(x[0]), float(x[1]), float(x[2])])


def segment_sphere_intersection(x0: np.ndarray, x1: np.ndarray, radius: float) -> np.ndarray:
    """Return the point where the Cartesian segment x0->x1 intersects |x|=radius."""
    x0 = np.asarray(x0, dtype=np.float64)
    x1 = np.asarray(x1, dtype=np.float64)
    d = x1 - x0
    a = float(np.dot(d, d))
    b = 2.0 * float(np.dot(x0, d))
    c = float(np.dot(x0, x0) - radius * radius)

    if a <= 1.0e-300:
        r0, th0, ph0 = cart_to_sph(x0)
        return sph_to_cart(radius, th0, ph0)

    disc = max(0.0, b * b - 4.0 * a * c)
    sqrt_disc = math.sqrt(disc)
    roots = [(-b - sqrt_disc) / (2.0 * a), (-b + sqrt_disc) / (2.0 * a)]
    roots = [t for t in roots if -1.0e-12 <= t <= 1.0 + 1.0e-12]

    if roots:
        # Prefer the intersection reached while moving from x0 to x1.
        t = min(max(0.0, min(1.0, t)) for t in roots)
        if abs(roots[-1]) < abs(t):
            t = min(max(0.0, roots[-1]), 1.0)
        hit = x0 + t * d
    else:
        # Fallback: use the closest point to the target radius and project radially.
        t = max(0.0, min(1.0, -b / (2.0 * a)))
        hit = x0 + t * d

    r_hit, th_hit, ph_hit = cart_to_sph(hit)
    return sph_to_cart(radius, th_hit, ph_hit)


def local_boundary_hit(x: np.ndarray, unit_velocity: np.ndarray, boundary_radius: float) -> np.ndarray:
    """First-order event point on a spherical boundary, radially projected exactly."""
    r, th, ph = cart_to_sph(x)
    er, _, _ = spherical_basis(th, ph)
    drds = float(np.dot(unit_velocity, er))
    if abs(drds) <= 1.0e-300:
        return sph_to_cart(boundary_radius, th, ph)
    h = (boundary_radius - r) / drds
    guess = np.asarray(x, dtype=np.float64) + h * np.asarray(unit_velocity, dtype=np.float64)
    _, th_hit, ph_hit = cart_to_sph(guess)
    return sph_to_cart(boundary_radius, th_hit, ph_hit)


def boundary_limited_rk4_step(
    x: np.ndarray,
    direction: float,
    Br: np.ndarray,
    Bt: np.ndarray,
    Bp: np.ndarray,
    r_grid: np.ndarray,
    theta_grid: np.ndarray,
    phi_grid: np.ndarray,
    step_size: float,
    boundary_mode: str,
    boundary_margin: float = 0.20,
) -> tuple[np.ndarray | None, str, float | None]:
    """
    Boundary-aware RK4 step for dx/ds = +/-B/|B|.

    Returns (x_new, status, hit_radius).  status is one of:
      ok, hit_inner, hit_outer, hit_cmb, interpolation_stop.

    The step uses RK4 away from boundaries.  When the local radial derivative
    predicts a boundary crossing within this step, the endpoint is placed
    exactly on the spherical boundary.  Otherwise the step length is reduced
    adaptively if an intermediate RK4 sample would leave the interpolation
    domain.
    """
    x = np.asarray(x, dtype=np.float64)
    r_now, th_now, ph_now = cart_to_sph(x)
    rmin = float(r_grid[0])
    rmax = float(r_grid[-1])
    h_requested = float(step_size)
    h_min = max(1.0e-8 * max(abs(rmax), 1.0), 1.0e-5 * abs(h_requested))

    k1 = interpolate_B_cartesian(x, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
    if k1 is None:
        return None, "interpolation_stop", None
    velocity = float(direction) * k1
    er, _, _ = spherical_basis(th_now, ph_now)
    drds = float(np.dot(velocity, er))

    boundary_radius = None
    boundary_status = None

    if boundary_mode == "shell":
        if drds > 0.0 and r_now < rmax:
            h_to_outer = (rmax - r_now) / drds
            if 0.0 <= h_to_outer <= h_requested:
                boundary_radius = rmax
                boundary_status = "hit_outer"
        elif drds < 0.0 and r_now > rmin:
            h_to_inner = (rmin - r_now) / drds
            if 0.0 <= h_to_inner <= h_requested:
                boundary_radius = rmin
                boundary_status = "hit_inner"
    elif boundary_mode == "exterior":
        if drds < 0.0 and r_now > rmin:
            h_to_cmb = (rmin - r_now) / drds
            if 0.0 <= h_to_cmb <= h_requested:
                boundary_radius = rmin
                boundary_status = "hit_cmb"
        elif drds > 0.0 and r_now < rmax:
            h_to_outer = (rmax - r_now) / drds
            if 0.0 <= h_to_outer <= h_requested:
                boundary_radius = rmax
                boundary_status = "hit_outer"

    if boundary_radius is not None:
        return local_boundary_hit(x, velocity, float(boundary_radius)), str(boundary_status), float(boundary_radius)

    h = h_requested
    while abs(h) >= h_min:
        x_new = rk4_step_cartesian(x, direction, Br, Bt, Bp, r_grid, theta_grid, phi_grid, h)
        if x_new is None:
            h *= 0.5
            continue

        r_new = radius_of(x_new)
        if boundary_mode == "shell" and (r_new < rmin or r_new > rmax):
            hit_radius = rmin if r_new < rmin else rmax
            status = "hit_inner" if r_new < rmin else "hit_outer"
            return segment_sphere_intersection(x, x_new, hit_radius), status, float(hit_radius)
        if boundary_mode == "exterior" and (r_new < rmin or r_new > rmax):
            hit_radius = rmin if r_new < rmin else rmax
            status = "hit_cmb" if r_new < rmin else "hit_outer"
            return segment_sphere_intersection(x, x_new, hit_radius), status, float(hit_radius)

        return x_new, "ok", None

    return None, "interpolation_stop", None

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
    """Trace one shell field-line branch with RK4 and exact shell-boundary endpoints."""
    points: list[list[float]] = []
    x = np.asarray(seed, dtype=np.float64).copy()

    rmin = float(r_grid[0])
    rmax = float(r_grid[-1])
    min_sep = 1.0e-6 * max(abs(rmax), 1.0)

    for _ in range(max_steps):
        r_now = radius_of(x)
        if r_now < rmin or r_now > rmax:
            break

        append_point(points, x, min_sep)

        x_new, status, _ = boundary_limited_rk4_step(
            x,
            direction,
            Br,
            Bt,
            Bp,
            r_grid,
            theta_grid,
            phi_grid,
            step_size,
            boundary_mode="shell",
        )
        if x_new is None:
            break

        if status in ("hit_inner", "hit_outer"):
            append_point(points, x_new, min_sep)
            break

        append_point(points, x_new, min_sep)
        x = x_new

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

    The arc is integrated with boundary-aware RK4 in the exterior domain.  When
    the line returns to the CMB, the endpoint is placed exactly on r = r_cmb.
    This gives more geometrically coherent exterior arcs than the previous
    first-order stepping while avoiding invalid RK4 samples just inside the CMB.
    """
    r_outer = float(r_grid[0])
    r_max_allowed = float(r_grid[-1])
    x = np.asarray(seed, dtype=np.float64).copy()

    points: list[list[float]] = []
    _, theta_seed, phi_seed = cart_to_sph(x)
    start_foot = sph_to_cart(r_outer, theta_seed, phi_seed)
    append_point(points, start_foot)
    append_point(points, x)

    r0 = radius_of(x)
    max_r_seen = float(r0)
    moved_outward = False
    outward_threshold = r_outer + max(2.0 * step_size, 1.0e-6 * r_outer)
    min_sep = 1.0e-6 * max(abs(r_max_allowed), 1.0)

    for _ in range(max_steps):
        r_now = radius_of(x)
        max_r_seen = max(max_r_seen, r_now)

        if r_now > r_max_allowed:
            return points, "hit_external_rmax", max_r_seen

        if r_now < r_outer:
            if moved_outward and len(points) >= min_points:
                _, tt, pp = cart_to_sph(x)
                foot = sph_to_cart(r_outer, tt, pp)
                append_point(points, foot, min_sep)
                return points, "returned_cmb", max_r_seen
            return points, "immediate_cmb", max_r_seen

        x_new, status, hit_radius = boundary_limited_rk4_step(
            x,
            direction,
            Br,
            Bt,
            Bp,
            r_grid,
            theta_grid,
            phi_grid,
            step_size,
            boundary_mode="exterior",
        )

        if x_new is None:
            return points, "interpolation_stop", max_r_seen

        r_new = radius_of(x_new)
        max_r_seen = max(max_r_seen, r_new)

        if r_new >= outward_threshold:
            moved_outward = True

        if status == "hit_outer":
            append_point(points, x_new, min_sep)
            return points, "hit_external_rmax", max_r_seen

        if status == "hit_cmb" or r_new <= r_outer:
            if moved_outward and len(points) >= min_points:
                # x_new is already projected exactly to r_cmb by the event handler.
                _, tt, pp = cart_to_sph(x_new)
                foot = sph_to_cart(r_outer, tt, pp)
                append_point(points, foot, min_sep)
                return points, "returned_cmb", max_r_seen
            return points, "immediate_cmb", max_r_seen

        append_point(points, x_new, min_sep)
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


def synthesize_potential_Br_surface_ltrunc(
    BP_lsd: np.ndarray,
    r_state: np.ndarray,
    lmax: int,
    mmax: int,
    l_trunc: int,
    target_radius: float,
    user_modules: Any,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Synthesize external potential-field B_r at ``target_radius``.

    The CMB poloidal coefficients are truncated to ``l <= l_trunc`` and
    continued through the current-free mantle.  For each spherical-harmonic
    degree, the radial field obeys

        B_r^{l,m}(r) = B_r^{l,m}(r_cmb) (r_cmb / r)^(l + 2).

    ``target_radius`` and the state radii must use the same nondimensional
    length scale.
    """
    if not hasattr(user_modules, "shtns") or not hasattr(user_modules, "lsd_to_shtns"):
        raise RuntimeError("modules.py must expose shtns and lsd_to_shtns for Earth-surface Br.")

    l_trunc = int(l_trunc)
    if l_trunc < 0:
        raise ValueError("--earth-br-ltrunc must be >= 0")

    r_cmb = float(r_state[-1])
    target_radius = float(target_radius)
    if r_cmb <= 0.0 or target_radius < r_cmb:
        raise ValueError("Earth-surface target radius must be at or outside the CMB.")

    shtns = user_modules.shtns
    sh = shtns.sht(int(lmax), int(mmax), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    nlat, nphi = sh.set_grid()
    theta = np.arccos(sh.cos_theta)
    phi = np.linspace(0.0, 2.0 * np.pi, nphi + 2)[1:-1]

    BP_shtns = user_modules.lsd_to_shtns(BP_lsd, sh)
    P_cmb = BP_shtns[:, -1].copy()
    ell = np.asarray(sh.l, dtype=np.float64)
    P_cmb[ell > l_trunc] = 0.0
    P_cmb[ell == 0] = 0.0

    # Exterior poloidal potential: P_lm(r) = P_lm(r_cmb) (r_cmb/r)^(l+1).
    P_target = P_cmb * (r_cmb / target_radius) ** (ell + 1.0)
    Qlm_target = (ell * (ell + 1.0) / target_radius) * P_target
    Br_target = sh.synth(Qlm_target)
    return (
        np.ascontiguousarray(Br_target, dtype=np.float64),
        np.ascontiguousarray(theta),
        np.ascontiguousarray(phi),
    )


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
            # Use the CMB value for polarity/coherence with shell lines, but
            # use the slightly offset seed only for numerical integration.
            br_cmb = interp_spherical_field(Br_ext, r_ext, theta_grid, phi_grid, r_outer, theta, phi)
            br_seed = interp_spherical_field(Br_ext, r_ext, theta_grid, phi_grid, seed_r, theta, phi)
            if not math.isfinite(br_seed) or abs(br_seed) <= 1.0e-300:
                continue
            if not math.isfinite(br_cmb) or abs(br_cmb) <= 1.0e-300:
                br_cmb = br_seed

            seed = sph_to_cart(seed_r, float(theta), float(phi))
            cmb_seed = sph_to_cart(r_outer, float(theta), float(phi))
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

            polarity = 1 if br_cmb >= 0.0 else -1
            start_r = radius_of(np.asarray(points[0], dtype=np.float64)) if points else float("nan")
            end_r = radius_of(np.asarray(points[-1], dtype=np.float64)) if points else float("nan")
            strengths = sample_line_strengths(points, Br_ext, Bt_ext, Bp_ext, r_ext, theta_grid, phi_grid)
            lines.append(
                {
                    "seed": [float(seed[0]), float(seed[1]), float(seed[2])],
                    "cmb_seed": [float(cmb_seed[0]), float(cmb_seed[1]), float(cmb_seed[2])],
                    "polarity": polarity,
                    "cmb_br_seed": float(br_cmb),
                    "region": "outside_cmb_potential_poloidal",
                    "mode": "exterior_potential_poloidal_cmb_to_cmb_rk4",
                    "integrator": "boundary-aware RK4 with exact spherical-boundary event endpoints",
                    "status": status,
                    "direction": float(direction),
                    "max_r": float(max_r_seen),
                    "start_r": float(start_r),
                    "end_r": float(end_r),
                    "end_r_error": float(abs(end_r - r_outer)) if math.isfinite(end_r) else None,
                    "strength_kind": "Babs",
                    "strength": strengths,
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
    full_sphere: bool = False,
) -> list[dict[str, Any]]:
    """
    Trace the actual simulation magnetic field inside the conducting fluid domain.
    For shell models the solid inner core is excluded; for full-sphere models the
    exact centre is treated as the coordinate-singular inner endpoint. Each line
    is integrated in both
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
            # Use the CMB value for polarity so shell and exterior lines seeded
            # at the same (theta, phi) use the same colour convention.
            br_cmb = interp_spherical_field(Br, r_grid, theta_grid, phi_grid, r_outer, theta, phi)
            br_seed = interp_spherical_field(Br, r_grid, theta_grid, phi_grid, seed_r, theta, phi)
            if not math.isfinite(br_seed) or abs(br_seed) <= 1.0e-300:
                continue
            if not math.isfinite(br_cmb) or abs(br_cmb) <= 1.0e-300:
                br_cmb = br_seed

            polarity = 1 if br_cmb >= 0.0 else -1
            seed = sph_to_cart(seed_r, float(theta), float(phi))
            cmb_seed = sph_to_cart(r_outer, float(theta), float(phi))

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

            start_r = radius_of(np.asarray(points[0], dtype=np.float64)) if points else float("nan")
            end_r = radius_of(np.asarray(points[-1], dtype=np.float64)) if points else float("nan")
            strengths = sample_line_strengths(points, Br, Bt, Bp, r_grid, theta_grid, phi_grid)
            lines.append(
                {
                    "seed": [float(seed[0]), float(seed[1]), float(seed[2])],
                    "cmb_seed": [float(cmb_seed[0]), float(cmb_seed[1]), float(cmb_seed[2])],
                    "polarity": polarity,
                    "cmb_br_seed": float(br_cmb),
                    "region": "full_fluid_sphere" if full_sphere else "fluid_shell_outside_inner_core",
                    "mode": "full_sphere_bidirectional_actual_B_rk4" if full_sphere else "shell_bidirectional_actual_B_rk4",
                    "integrator": "boundary-aware RK4 with exact inner/outer spherical-boundary endpoints",
                    "closed": bool(closed),
                    "endpoint_distance": endpoint_distance,
                    "start_r": float(start_r),
                    "end_r": float(end_r),
                    "strength_kind": "Babs",
                    "strength": strengths,
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
    p.add_argument(
        "--no-inner-core",
        "--full-sphere",
        dest="no_inner_core",
        action="store_true",
        help=(
            "Convert a full-sphere Leeds state whose radial grid includes r=0. "
            "Stage-5/6 regular coefficients G_lm(x), x=r^2, are detected from the "
            "NetCDF radial_representation attributes and transformed with the same "
            "direct regular QST formulae and seven-point x derivatives as Leeds. "
            "Legacy conventional coefficients are projected with the bounded Leeds "
            "K=7 regular projector. Alias: --full-sphere. Full-sphere states are also "
            "detected automatically."
        ),
    )
    p.add_argument(
        "--center-tolerance",
        type=float,
        default=1.0e-12,
        help="Relative tolerance used to identify r=0 in full-sphere states. Default: 1e-12.",
    )

    # Optional explicit parameter overrides. If omitted, the converter tries to
    # parse them from the path and then asks interactively when missing.
    p.add_argument("--Ek", "--E", dest="Ek", type=float, default=None, help="Ekman number metadata/N2 override. Aliases: --Ek, --E.")
    p.add_argument("--Pr", "--PrT", "--Pr_T", dest="Pr", type=float, default=None, help="Thermal Prandtl number metadata/N2 override.")
    p.add_argument("--Sc", "--PrC", "--Pr_C", dest="Sc", type=float, default=None, help="Compositional Prandtl/Schmidt number metadata/N2 override.")
    p.add_argument("--RaT", "--Ra", "--Ra_T", dest="RaT", type=float, default=None, help="Thermal Rayleigh number metadata/N2 override.")
    p.add_argument("--RaC", "--Ra_C", dest="RaC", type=float, default=None, help="Compositional Rayleigh number metadata/N2 override.")
    p.add_argument(
        "--no-parameter-prompt",
        action="store_true",
        help="Do not prompt for missing Ek/Pr/Sc/RaT/RaC; keep missing values as NaN.",
    )

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
        "--earth-br-ltrunc",
        type=int,
        default=DEFAULT_EARTH_BR_LMAX,
        help=(
            "Export B_r at the Earth's surface by potential-field continuation "
            "of the CMB field, retaining l <= L. Default: 13."
        ),
    )
    p.add_argument(
        "--earth-radius-scale",
        type=float,
        default=DEFAULT_EARTH_RADIUS_SCALE,
        help=(
            "Earth-surface radius divided by the dynamo CMB radius. "
            f"Default: 6371/3480 = {DEFAULT_EARTH_RADIUS_SCALE:.8f}."
        ),
    )
    p.add_argument(
        "--no-earth-br",
        action="store_true",
        help="Do not export the l-truncated Earth-surface radial magnetic field.",
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
    p.add_argument(
        "--spectral-lmax",
        type=int,
        default=128,
        help=(
            "Angular spectral cutoff applied before physical-space synthesis. "
            "Default is 128. Use --spectral-lmax 0 to disable. "
            "This is preferred over --downsample-theta/--downsample-phi because it removes high-l modes "
            "before creating the theta/phi grid."
        ),
    )
    p.add_argument("--downsample-r", type=int, default=1, help="Keep every Nth radial point.")
    p.add_argument("--downsample-theta", type=int, default=1, help="Keep every Nth theta point after spectral synthesis. Usually leave at 1 when using --spectral-lmax.")
    p.add_argument("--downsample-phi", type=int, default=1, help="Keep every Nth phi point after spectral synthesis. Usually leave at 1 when using --spectral-lmax.")

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

    p.add_argument("--line-seeds", type=int, default=None, help="Approximate total number of regular CMB seed points for field lines, e.g. 360. Overrides --line-seed-theta/--line-seed-phi.")
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
        help="Skip exporting 3-D scalar gradient fields. N2 and helicity are still computed.",
    )

    p.add_argument("--sequence-first", type=int, default=None, help="First state number to convert in a multi-frame sequence.")
    p.add_argument("--sequence-last", type=int, default=None, help="Last state number to convert in a multi-frame sequence.")
    p.add_argument("--sequence-step", type=int, default=1, help="State-number interval for multi-frame conversion.")
    p.add_argument("--sequence-subdir", default="frames", help="Subdirectory under --out where sequence frames are written.")
    p.add_argument("--sequence-clear", action="store_true", help="Delete the existing sequence frame directory before converting.")

    return p



def run_sequence_conversion(args: argparse.Namespace) -> None:
    """Convert several state files into public/data/frames/stateXXXXX and write sequence.json."""
    if not args.folder:
        raise ValueError("--sequence-first/--sequence-last requires --folder.")

    first = int(args.sequence_first)
    last = int(args.sequence_last)
    step = max(1, int(args.sequence_step))
    if last < first:
        raise ValueError("--sequence-last must be >= --sequence-first.")

    files = list_state_files(args.folder, args.pattern)
    selected: list[str] = []
    wanted = set(range(first, last + 1, step))
    for path in files:
        n = parse_state_number(path)
        if n in wanted:
            selected.append(path)

    if not selected:
        raise FileNotFoundError(f"No state files found for requested sequence {first}:{step}:{last}")

    # Resolve parameters once for the sequence and pass them to each frame.
    # This avoids prompting once per frame when folder names do not contain all tokens.
    sequence_params = resolve_parameter_values(selected[0], args, prompt_missing=not args.no_parameter_prompt)
    for name, value in sequence_params.items():
        setattr(args, PARAMETER_SPECS[name]["arg"], value)

    outdir = Path(args.out)
    frames_root = outdir / str(args.sequence_subdir)
    if args.sequence_clear and frames_root.exists():
        shutil.rmtree(frames_root)
    frames_root.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).resolve()
    frames = []

    for state_path in selected:
        state_number = parse_state_number(state_path)
        frame_name = f"state{state_number:05d}"
        frame_out = frames_root / frame_name
        frame_out.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable,
            str(script_path),
            "--state", str(state_path),
            "--out", str(frame_out),
            "--alpha-map", str(args.alpha_map),
            "--magnetic-tol", str(args.magnetic_tol),
            "--spectral-lmax", str(args.spectral_lmax),
            "--field-line-mode", str(args.field_line_mode),
            "--line-max-steps", str(args.line_max_steps),
            "--external-nr", str(args.external_nr),
            "--external-btheta-sign", str(args.external_btheta_sign),
            "--no-parameter-prompt",
        ]

        if args.modules_dir:
            cmd += ["--modules-dir", str(args.modules_dir)]
        if args.no_inner_core:
            cmd += ["--no-inner-core"]
        cmd += ["--center-tolerance", str(args.center_tolerance)]
        append_parameter_overrides(cmd, args)
        if args.cmb_br_ltrunc is not None:
            cmd += ["--cmb-br-ltrunc", str(args.cmb_br_ltrunc)]
        cmd += ["--earth-br-ltrunc", str(args.earth_br_ltrunc)]
        cmd += ["--earth-radius-scale", str(args.earth_radius_scale)]
        if args.no_earth_br:
            cmd += ["--no-earth-br"]
        if args.external_rmax is not None:
            cmd += ["--external-rmax", str(args.external_rmax)]
        if args.line_step_size is not None:
            cmd += ["--line-step-size", str(args.line_step_size)]
        if args.line_seeds is not None:
            cmd += ["--line-seeds", str(args.line_seeds)]
        else:
            cmd += ["--line-seed-theta", str(args.line_seed_theta), "--line-seed-phi", str(args.line_seed_phi)]
        if args.skip_field_lines:
            cmd += ["--skip-field-lines"]
        if not args.external_closed_only:
            cmd += ["--no-external-closed-only"]
        if args.no_gradients:
            cmd += ["--no-gradients"]
        if args.downsample_r != 1:
            cmd += ["--downsample-r", str(args.downsample_r)]
        if args.downsample_theta != 1:
            cmd += ["--downsample-theta", str(args.downsample_theta)]
        if args.downsample_phi != 1:
            cmd += ["--downsample-phi", str(args.downsample_phi)]

        print(f"\n=== Converting frame {frame_name}: {state_path} ===")
        subprocess.run(cmd, check=True)

        metadata_path = frame_out / "metadata.json"
        t = None
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                t = meta.get("time")
            except Exception:
                t = None

        frames.append({
            "state_number": state_number,
            "time": t,
            "path": f"{args.sequence_subdir}/{frame_name}",
            "metadata": f"{args.sequence_subdir}/{frame_name}/metadata.json",
            "label": frame_name,
        })

    sequence = {
        "version": 1,
        "frame_count": len(frames),
        "first": first,
        "last": last,
        "step": step,
        "frames": frames,
    }

    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "sequence.json", "w", encoding="utf-8") as f:
        json.dump(sequence, f, indent=2, allow_nan=False)

    # Also copy the first frame to --out so the viewer can load normally before playback starts.
    first_frame_dir = frames_root / frames[0]["label"]
    for item in first_frame_dir.iterdir():
        dst = outdir / item.name
        if item.is_file():
            shutil.copy2(item, dst)

    print("\nDone.")
    print(f"Sequence written to: {(outdir / 'sequence.json').resolve()}")
    print(f"Frames written under: {frames_root.resolve()}")
    print(f"Copied first frame to: {outdir.resolve()}")



def main() -> None:
    args = build_arg_parser().parse_args()

    if not math.isfinite(float(args.center_tolerance)) or float(args.center_tolerance) <= 0.0:
        raise ValueError("--center-tolerance must be finite and > 0.")

    if args.sequence_first is not None or args.sequence_last is not None:
        if args.sequence_first is None or args.sequence_last is None:
            raise ValueError("Both --sequence-first and --sequence-last are required for sequence conversion.")
        run_sequence_conversion(args)
        return

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

    if args.line_seeds is not None:
        args.line_seed_theta, args.line_seed_phi = choose_regular_seed_grid(args.line_seeds)
        print(f"Regular field-line seed grid requested: ~{args.line_seeds} seeds -> "
              f"{args.line_seed_theta} x {args.line_seed_phi} = {args.line_seed_theta * args.line_seed_phi}")

    # Parameter extraction from CLI overrides, path aliases, or interactive prompt.
    params_resolved = resolve_parameter_values(path, args, prompt_missing=not args.no_parameter_prompt)
    E = params_resolved["Ek"]
    Pr = params_resolved["Pr"]
    Sc = params_resolved["Sc"]
    RaT = params_resolved["RaT"]
    RaC = params_resolved["RaC"]

    print(
        "Parameters: "
        f"Ek={E:.6g}, Pr={Pr:.6g}, Sc={Sc:.6g}, "
        f"RaT={RaT:.6g}, RaC={RaC:.6g}"
    )

    print("Loading spectral state...")
    state = load_state(path)
    radial_representations = read_state_radial_representations(path)

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

    center_mask = full_sphere_center_mask(r, args.center_tolerance)
    detected_full_sphere = bool(np.any(center_mask))
    if args.no_inner_core and not detected_full_sphere:
        raise ValueError(
            "--no-inner-core/--full-sphere was requested, but the radial grid does not include r=0. "
            f"The first radius is {float(r[0]):.8e}."
        )
    full_sphere = bool(args.no_inner_core or detected_full_sphere)
    if detected_full_sphere and not args.no_inner_core:
        print("Full-sphere state detected automatically from r[0]=0.")
    if full_sphere:
        print("Full-sphere/no-inner-core mode enabled.")
        print(
            "  Using the Leeds regular representation f_lm=r^(l+p0)G_lm(x), x=r^2, "
            "and direct regular QST reconstruction."
        )

    print(f"lmax={lmax}, mmax={mmax}, nr={len(r)}, time={time:.8e}")

    (
        uP,
        uT,
        BP,
        BT,
        C,
        Comp,
        lmax_transform,
        mmax_transform,
        spectral_meta,
    ) = apply_spectral_lmax_to_state(
        uP,
        uT,
        BP,
        BT,
        C,
        Comp,
        lmax,
        mmax,
        args.spectral_lmax,
        user_modules,
    )

    print(f"Transform grid: lmax={lmax_transform}, mmax={mmax_transform}")
    fullsphere_transform_meta: dict[str, Any] = {
        "enabled": bool(full_sphere),
        "method": "shell_PolTor_to_spat" if not full_sphere else "leeds_direct_regular_qst_in_x",
        "fields": {},
    }

    if full_sphere:
        _, sh_regular = get_shtns_transform(user_modules, lmax_transform, mmax_transform)
        degrees = np.asarray(sh_regular.l, dtype=int)

        print("Transforming velocity from Leeds regular G_lm(x), H_lm(x) coefficients...")
        uP_regular, uP_offset, uP_source = ensure_fullsphere_regular_coefficients(
            uP, radial_representations["uP"], r, degrees, "uP"
        )
        uT_regular, uT_offset, uT_source = ensure_fullsphere_regular_coefficients(
            uT, radial_representations["uT"], r, degrees, "uT"
        )
        Ur, Ut, Up, theta, phi, velocity_derivative_method = fullsphere_regular_poltors_to_spat(
            uP_regular,
            uT_regular,
            r,
            lmax_transform,
            mmax_transform,
            user_modules,
            pol_power_offset=uP_offset,
            tor_power_offset=uT_offset,
        )
        fullsphere_transform_meta["fields"]["velocity"] = {
            "poloidal_input": uP_source,
            "toroidal_input": uT_source,
            "poloidal_power_offset": int(uP_offset),
            "toroidal_power_offset": int(uT_offset),
            "x_derivative": velocity_derivative_method,
            "shtns_qst_convention": {
                "Q": "+l(l+1) r^(l+pP-1) G",
                "S": "+r^(l+pP-1)[(l+pP+1)G+2xG_x]",
                "T": "+r^(l+pT) H",
                "source": "Leeds var_coll_TorPol2qst_fullsphere + tra_qst2rtp_shtns",
            },
        }
    else:
        print("Transforming velocity to physical space...")
        Ur, Ut, Up, theta, phi = PolTor_to_spat(
            uP, uT, r, lmax_transform, mmax_transform, alpha_map=args.alpha_map
        )

    BP_abs_max = float(np.nanmax(np.abs(BP))) if BP is not None else 0.0
    BT_abs_max = float(np.nanmax(np.abs(BT))) if BT is not None else 0.0
    has_magnetic_field = BP_abs_max > args.magnetic_tol

    if has_magnetic_field:
        print(f"Magnetic state detected: max(abs(BP))={BP_abs_max:.6e}, max(abs(BT))={BT_abs_max:.6e}")
        if full_sphere:
            print("Transforming magnetic field with the Leeds full-sphere regular QST formulation...")
            BP_regular, BP_offset, BP_source = ensure_fullsphere_regular_coefficients(
                BP, radial_representations["BP"], r, degrees, "BP"
            )
            BT_regular, BT_offset, BT_source = ensure_fullsphere_regular_coefficients(
                BT, radial_representations["BT"], r, degrees, "BT"
            )
            Br, Bt, Bp, theta_B, phi_B, magnetic_derivative_method = fullsphere_regular_poltors_to_spat(
                BP_regular,
                BT_regular,
                r,
                lmax_transform,
                mmax_transform,
                user_modules,
                pol_power_offset=BP_offset,
                tor_power_offset=BT_offset,
            )
            fullsphere_transform_meta["fields"]["magnetic"] = {
                "poloidal_input": BP_source,
                "toroidal_input": BT_source,
                "poloidal_power_offset": int(BP_offset),
                "toroidal_power_offset": int(BT_offset),
                "x_derivative": magnetic_derivative_method,
                "shtns_qst_convention": {
                    "Q": "+l(l+1) r^(l+pP-1) G",
                    "S": "+r^(l+pP-1)[(l+pP+1)G+2xG_x]",
                    "T": "+r^(l+pT) H",
                    "source": "Leeds var_coll_TorPol2qst_fullsphere + tra_qst2rtp_shtns",
                },
            }
        else:
            print("Transforming magnetic field to physical space...")
            Br, Bt, Bp, theta_B, phi_B = PolTor_to_spat(
                BP, BT, r, lmax_transform, mmax_transform, alpha_map=args.alpha_map
            )
    else:
        print(f"No magnetic/dynamo field detected: max(abs(BP))={BP_abs_max:.6e} <= {args.magnetic_tol:.6e}")
        if BT_abs_max > args.magnetic_tol:
            print(f"Warning: BP is zero but BT is not zero: max(abs(BT))={BT_abs_max:.6e}. Exterior field lines require BP.")
        Br = Bt = Bp = None

    print("Transforming scalar fields to physical space...")
    C_for_transform = C
    Comp_for_transform = Comp
    if full_sphere:
        C_meta = radial_representations["C"]
        if C_meta.get("representation") == REGULAR_RADIAL_REPRESENTATION:
            C_for_transform = regular_scalar_lsd_to_conventional(
                C, r, degrees, int(C_meta.get("power_offset", 0))
            )
            fullsphere_transform_meta["fields"]["C"] = "stored_regular_to_physical_r_power"
        else:
            fullsphere_transform_meta["fields"]["C"] = "stored_conventional"

        Comp_meta = radial_representations["Comp"]
        if Comp is not None and Comp_meta.get("representation") == REGULAR_RADIAL_REPRESENTATION:
            Comp_for_transform = regular_scalar_lsd_to_conventional(
                Comp, r, degrees, int(Comp_meta.get("power_offset", 0))
            )
            fullsphere_transform_meta["fields"]["Comp"] = "stored_regular_to_physical_r_power"
        else:
            fullsphere_transform_meta["fields"]["Comp"] = "stored_conventional"

    Cspat, theta_C, phi_C = SH_to_spat(C_for_transform, lmax_transform, mmax_transform)
    Compspat, theta_Comp, phi_Comp = SH_to_spat(Comp_for_transform, lmax_transform, mmax_transform)

    Cspatnom0, _, _ = SH_to_spat_nom0(C_for_transform, lmax_transform, mmax_transform)
    Compspatnom0, _, _ = SH_to_spat_nom0(Comp_for_transform, lmax_transform, mmax_transform)

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

    center_vector_diagnostics: dict[str, Any] = {}
    if full_sphere:
        Ur, Ut, Up, velocity_center_diag = enforce_fullsphere_cartesian_center_limit(
            Ur, Ut, Up, theta, phi, center_mask, "velocity"
        )
        center_vector_diagnostics["velocity"] = velocity_center_diag
        if has_magnetic_field:
            Br, Bt, Bp, magnetic_center_diag = enforce_fullsphere_cartesian_center_limit(
                Br, Bt, Bp, theta, phi, center_mask, "magnetic"
            )
            center_vector_diagnostics["magnetic"] = magnetic_center_diag
        Cspat = regularize_scalar_center(Cspat, center_mask, "C")
        Compspat = regularize_scalar_center(Compspat, center_mask, "Comp")
        Cspatnom0 = regularize_scalar_center(Cspatnom0, center_mask, "C_nom0")
        Compspatnom0 = regularize_scalar_center(Compspatnom0, center_mask, "Comp_nom0")

    Uabs = np.sqrt(Ur * Ur + Ut * Ut + Up * Up)
    if has_magnetic_field:
        Babs = np.sqrt(Br * Br + Bt * Bt + Bp * Bp)

    Cspatnol0 = remove_global_mean(Cspat)
    Compspatnol0 = remove_global_mean(Compspat)

    print("Computing full 3-D scalar gradients, N2 fluctuations, and helicity...")
    grad_rC_3d, grad_thetaC_3d, grad_phiC_3d = gradient_scalar_3d(Cspat, r, theta, phi)
    grad_rComp_3d, grad_thetaComp_3d, grad_phiComp_3d = gradient_scalar_3d(Compspat, r, theta, phi)
    if full_sphere:
        grad_rC_3d, grad_thetaC_3d, grad_phiC_3d = regularize_scalar_gradient_center(
            grad_rC_3d, grad_thetaC_3d, grad_phiC_3d, center_mask
        )
        grad_rComp_3d, grad_thetaComp_3d, grad_phiComp_3d = regularize_scalar_gradient_center(
            grad_rComp_3d, grad_thetaComp_3d, grad_phiComp_3d, center_mask
        )

    # Fluctuating (m != 0) gradient fields.
    grad_rC_fluct = remove_m0_phi(grad_rC_3d)
    grad_thetaC_fluct = remove_m0_phi(grad_thetaC_3d)
    grad_phiC_fluct = remove_m0_phi(grad_phiC_3d)
    grad_rComp_fluct = remove_m0_phi(grad_rComp_3d)
    grad_thetaComp_fluct = remove_m0_phi(grad_thetaComp_3d)
    grad_phiComp_fluct = remove_m0_phi(grad_phiComp_3d)

    # Full N^2 everywhere, plus its fluctuating m != 0 component.
    # N2 is kept as the historical/default fluctuating field for compatibility.
    # N2_full keeps the axisymmetric m=0 component.
    N2_full = r[:, None, None] * E**2 * (grad_rComp_3d * RaC / Sc + grad_rC_3d * RaT / Pr)
    N2_volume = remove_m0_phi(N2_full)

    helicity = compute_helicity(Ur, Ut, Up, r, theta, phi)

    # Keep simple 1-D profiles for reference.
    N2_profile = np.mean(N2_full, axis=(1, 2))
    N2_fluct_rms = np.sqrt(np.mean(N2_volume * N2_volume, axis=(1, 2)))
    grad_rC_mean_r = np.mean(grad_rC_3d, axis=(1, 2))
    grad_rComp_mean_r = np.mean(grad_rComp_3d, axis=(1, 2))

    Ur_phiavg = phi_average_volume(Ur, "ur")
    Ut_phiavg = phi_average_volume(Ut, "ut")
    Up_phiavg = phi_average_volume(Up, "up")

    fields: dict[str, np.ndarray] = {
        "ur": Ur,
        "ut": Ut,
        "up": Up,
        "Uabs": Uabs,
        "ur_phiavg": Ur_phiavg,
        "ut_phiavg": Ut_phiavg,
        "up_phiavg": Up_phiavg,
        "helicity": helicity,
        "C": Cspat,
        "Comp": Compspat,
        "Cnom0": Cspatnom0,
        "Compnom0": Compspatnom0,
        "Cnol0": Cspatnol0,
        "Compnol0": Compspatnol0,
        "N2": N2_volume,
        "N2_full": N2_full,
    }

    if has_magnetic_field:
        Br_phiavg = phi_average_volume(Br, "Br")
        Bt_phiavg = phi_average_volume(Bt, "Bt")
        Bp_phiavg = phi_average_volume(Bp, "Bp")
        fields = {
            "Br": Br,
            "Bt": Bt,
            "Bp": Bp,
            "Babs": Babs,
            "Br_phiavg": Br_phiavg,
            "Bt_phiavg": Bt_phiavg,
            "Bp_phiavg": Bp_phiavg,
            **fields,
        }

    if not args.no_gradients:
        print("Exporting 3-D scalar gradients for C and Comp, both fluctuating and full m=0-included fields...")

        # Historical/default names: m=0 removed, i.e. non-axisymmetric fluctuations.
        fields["grad_rC"] = grad_rC_fluct
        fields["grad_thetaC"] = grad_thetaC_fluct
        fields["grad_phiC"] = grad_phiC_fluct
        fields["grad_rComp"] = grad_rComp_fluct
        fields["grad_thetaComp"] = grad_thetaComp_fluct
        fields["grad_phiComp"] = grad_phiComp_fluct

        # Full fields: m=0 retained.
        fields["grad_rC_full"] = grad_rC_3d
        fields["grad_thetaC_full"] = grad_thetaC_3d
        fields["grad_phiC_full"] = grad_phiC_3d
        fields["grad_rComp_full"] = grad_rComp_3d
        fields["grad_thetaComp_full"] = grad_thetaComp_3d
        fields["grad_phiComp_full"] = grad_phiComp_3d

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
        N2_fluct_rms_out = N2_fluct_rms[::dr]
        grad_rC_mean_r_out = grad_rC_mean_r[::dr]
        grad_rComp_mean_r_out = grad_rComp_mean_r[::dr]
    else:
        r_out = r
        theta_out = theta
        phi_out = phi
        N2_profile_out = N2_profile
        N2_fluct_rms_out = N2_fluct_rms
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
    for old in outdir.glob("*_earth.f32"):
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
            effective_lcut = min(lcut, lmax_transform)
            if effective_lcut != lcut:
                print(f"Requested --cmb-br-ltrunc {lcut} exceeds transform lmax {lmax_transform}; using {effective_lcut}.")
            Br_cmb_lcut, theta_lcut, phi_lcut = synthesize_cmb_Br_ltrunc(
                BP,
                r,
                lmax_transform,
                mmax_transform,
                effective_lcut,
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

    if not args.no_earth_br:
        if not has_magnetic_field:
            print("Skipping Earth-surface Br because this state is non-magnetic/BP is zero.")
        else:
            requested_lcut = int(args.earth_br_ltrunc)
            if requested_lcut < 0:
                raise ValueError("--earth-br-ltrunc must be >= 0")
            radius_scale = float(args.earth_radius_scale)
            if not math.isfinite(radius_scale) or radius_scale < 1.0:
                raise ValueError("--earth-radius-scale must be finite and >= 1.")
            effective_lcut = min(requested_lcut, lmax_transform)
            earth_radius = float(r[-1]) * radius_scale
            print(
                f"Synthesizing Earth-surface Br with l <= {effective_lcut} at "
                f"r/r_cmb={radius_scale:.8g}..."
            )
            Br_earth, _, _ = synthesize_potential_Br_surface_ltrunc(
                BP,
                r,
                lmax_transform,
                mmax_transform,
                effective_lcut,
                earth_radius,
                user_modules,
            )
            Br_earth = np.ascontiguousarray(Br_earth[::dt, ::dp])
            if Br_earth.shape != (ntheta_out, nphi_out):
                raise ValueError(
                    f"Earth-surface Br shape {Br_earth.shape} does not match viewer angular grid "
                    f"{(ntheta_out, nphi_out)}."
                )
            name = f"Br_Earth_lmax{requested_lcut}"
            filename = f"{name}_earth.f32"
            ranges[name] = write_f32(outdir / filename, Br_earth)
            surface_fields[name] = {
                "file": filename,
                "surface": "earth",
                "layout": "theta_phi",
                "l_trunc": requested_lcut,
                "effective_l_trunc": effective_lcut,
                "radius_scale": radius_scale,
                "radius": earth_radius,
                "source": "BP at CMB continued as an external potential field",
                "radial_decay": "(r_cmb/r)^(l+2)",
                "description": (
                    f"Potential-field B_r at the Earth surface from CMB degrees "
                    f"1 <= l <= {effective_lcut}"
                ),
            }
            print(f"  {name:20s} {Br_earth.shape} -> {filename}")

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
        "N2_fluct_rms": [json_number(x) for x in N2_fluct_rms_out],
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
                (
                    "shell = actual simulation B traced inside the full fluid sphere; "
                    if full_sphere
                    else "shell = actual simulation B traced inside fluid shell outside the inner core; "
                )
                + "exterior = exterior potential/poloidal field outside the CMB reconstructed from BP at the CMB with toroidal field set to zero"
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
                full_sphere=full_sphere,
            )
            shell_count = len(shell_lines)
            combined_lines.extend(shell_lines)
            with open(outdir / "B_lines_shell.json", "w", encoding="utf-8") as f:
                json.dump(shell_lines, f, allow_nan=False)
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
                    lmax_transform,
                    mmax_transform,
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
                json.dump(exterior_lines, f, allow_nan=False)
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
            json.dump(combined_lines, f, allow_nan=False)

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
        },
        "spectral": spectral_meta,
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
        "has_inner_core": bool(not full_sphere and float(r_out[0]) > 0.0),
        "full_sphere": bool(full_sphere),
        "state_radial_representations": radial_representations,
        "full_sphere_transform": fullsphere_transform_meta,
        "center_regularization": {
            "enabled": bool(full_sphere),
            "requested_explicitly": bool(args.no_inner_core),
            "detected_from_radius_grid": bool(detected_full_sphere),
            "center_tolerance": json_number(args.center_tolerance),
            "method": "Leeds direct regular coefficients f_lm=r^(l+p0)G_lm(x), x=r^2",
            "vector_center_policy": "analytic l=1 regular QST limit, enforced as one Cartesian vector",
            "magnetic_center_policy": "same analytic regular QST limit when magnetic data are present",
            "scalar_center_policy": "physical coefficients r^(l+p0)G_lm synthesized; centre reduced to its angular mean",
            "gradient_center_policy": "angular derivatives zero; radial derivative angular mean",
            "helicity_center_policy": "zero at the coordinate-singular centre",
            "vector_center_diagnostics": center_vector_diagnostics,
        },
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
