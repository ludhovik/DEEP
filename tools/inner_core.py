"""Measured inner-core magnetic data and additive updates of viewer bundles.

The volume contract stays r/theta/phi. New radial rows are prepended; existing
outer-core float32 values, surface files and field lines are copied unchanged.
No magnetic continuation into an unmeasured solid region is invented here.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.modules.setdefault("inner_core", sys.modules[__name__])
sys.modules.setdefault("tools.inner_core", sys.modules[__name__])

try:
    from viewer_bundle import ViewerSampling, bundle_path, write_f32
except ImportError:
    from tools.viewer_bundle import ViewerSampling, bundle_path, write_f32


MAGNETIC_FIELDS = ("Br", "Bt", "Bp", "Babs", "Br_phiavg", "Bt_phiavg", "Bp_phiavg",
                   "Br_nom0", "Bt_nom0", "Bp_nom0")


def _text(value):
    if isinstance(value, np.ndarray):
        value = value.item()
    return value.decode() if isinstance(value, bytes) else value


def read_leeds_inner_core(path):
    """Read icr/icBP/icBT only; classic NetCDF and HDF5, including padded ic arrays."""
    path = Path(path)
    with path.open("rb") as stream:
        signature = stream.read(8)
    if signature.startswith(b"CDF"):
        from scipy.io import netcdf_file
        handle = netcdf_file(path, "r", mmap=False)
        variables = handle.variables
        attributes = lambda variable: variable._attributes
    elif signature == b"\x89HDF\r\n\x1a\n":
        import h5py
        handle = h5py.File(path, "r")
        variables = handle
        attributes = lambda variable: variable.attrs
    else:
        return None
    try:
        present = [name in variables for name in ("icBP", "icBT")]
        if not any(present):
            return None
        if "icr" not in variables:
            raise ValueError("icBP/icBT are present but their icr coordinate is missing.")
        r = np.array(variables["icr"][:], dtype=float)
        # Leeds writes a one-point placeholder when there is no inner core.
        if r.size <= 1:
            return None
        if r.ndim != 1 or not np.isfinite(r).all() or np.any(r < 0):
            raise ValueError("Invalid Leeds icr coordinates.")
        order = np.argsort(r)
        r = r[order]
        if np.any(np.diff(r) <= 0):
            raise ValueError("Leeds icr coordinates must be distinct.")
        result = {"r": r, "representations": {}}
        limits = []
        for name in ("icBP", "icBT"):
            if name not in variables:
                result[name] = None
                continue
            variable = variables[name]
            # Some Leeds releases declare the outer-core radial dimension for
            # icBP/icBT but write only the first len(icr) collocation rows.
            array = np.array(variable[..., :len(r)], dtype=float)
            if array.ndim != 3 or array.shape[0] != 2 or array.shape[-1] != len(r):
                raise ValueError(f"{name}: expected (2, nlm, nr_ic), got {array.shape}.")
            if not np.isfinite(array).all() or np.any(np.abs(array) > 1e30):
                raise ValueError(f"{name}: nonfinite values or unwritten NetCDF fill values.")
            result[name] = array[..., order]
            attrs = attributes(variable)
            limits.append((int(np.asarray(attrs["L"]).item()) - 1,
                           int(np.asarray(attrs["M"]).item()) - 1))
            if int(np.asarray(attrs.get("Mp", 1)).item()) != 1:
                raise ValueError("Leeds inner-core Mp != 1 is not supported.")
            result["representations"][name] = {
                "representation": _text(attrs.get("radial_representation", "conventional_r_coefficient")),
                "power_offset": int(np.asarray(attrs.get("radial_power_offset", 0)).item()),
            }
        if len(set(limits)) != 1:
            raise ValueError("icBP/icBT have different angular truncations.")
        result["lmax"], result["mmax"] = limits[0]
        for name, other in (("icBP", "icBT"), ("icBT", "icBP")):
            if result[name] is None:
                result[name] = np.zeros_like(result[other])
                result["representations"][name] = result["representations"][other].copy()
        return result
    finally:
        handle.close()


def radial_derivative(values, radius):
    """Leeds local seven-point (KL=3) physical-r derivative, shortened at edges."""
    r = np.asarray(radius, dtype=float)
    derivative = np.empty_like(values)
    for i in range(len(r)):
        start, stop = max(0, i - 3), min(len(r), i + 4)
        delta = r[start:stop] - r[i]
        scale = np.max(np.abs(delta))
        matrix = (delta / scale)[None, :] ** np.arange(len(delta))[:, None]
        rhs = np.zeros(len(delta)); rhs[1] = 1 / scale
        weights = np.linalg.solve(matrix, rhs)
        derivative[..., i] = np.einsum("...r,r->...", values[..., start:stop], weights)
    return derivative


def leeds_inner_qst(pol, tor, degrees, radius, representations, backend):
    """Direct SHTns Q=l(l+1)P/r, S=P/r+dP/dr, T=T (regular G also supported)."""
    r = np.asarray(radius)
    degree = np.asarray(degrees)
    pp, tt = representations["icBP"], representations["icBT"]
    known = {"regular_r_power_g_x", "conventional_r_coefficient"}
    if pp["representation"] not in known or tt["representation"] not in known:
        raise ValueError("Unknown inner-core radial representation; cannot infer coefficient powers safely.")
    if r[0] == 0 and pp["representation"] != "regular_r_power_g_x":
        raise ValueError("Leeds icr includes zero but icBP has no regular_r_power_g_x marker. "
                         "A centre-safe representation is required; do not treat stored P as G.")
    if pp["representation"] == "regular_r_power_g_x":
        # This formula also works on a centre-excluding regular grid.
        exponent = degree + pp["power_offset"] - 1
        active = degree > 0
        if np.any(exponent[active] < 0):
            raise ValueError("Singular poloidal inner-core radial power.")
        factor = np.zeros_like(pol.real)
        factor[active] = r[None, :] ** exponent[active, None]
        gx = radial_derivative(pol, r * r)
        q = degree[:, None] * (degree + 1)[:, None] * factor * pol
        s = factor * ((degree + pp["power_offset"] + 1)[:, None] * pol + 2*r[None, :]**2 * gx)
    else:
        q = degree[:, None] * (degree + 1)[:, None] * pol / r
        s = pol / r + radial_derivative(pol, r)
    if tt["representation"] == "regular_r_power_g_x":
        exponent = degree + tt["power_offset"]
        if np.any(exponent < 0):
            raise ValueError("Singular toroidal inner-core radial power.")
        tor = tor * r[None, :] ** exponent[:, None]
    q[degree == 0] = 0; s[degree == 0] = 0
    tor = tor.copy(); tor[degree == 0] = 0
    return q, s, tor


def synthesise_leeds_inner(inner, metadata, backend):
    try:
        from convert_leeds_to_viewer import truncate_lsd_coefficients
    except ImportError:
        from tools.convert_leeds_to_viewer import truncate_lsd_coefficients
    spectral = metadata["spectral_truncation"]
    lmax, mmax = int(spectral["lmax_effective"]), int(spectral["mmax_effective"])
    if lmax > inner["lmax"] or mmax > inner["mmax"]:
        raise ValueError("Inner-core angular truncation is smaller than the existing outer-core grid.")
    shtns = backend.shtns
    sh = shtns.sht(lmax, mmax, 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    _, nphi = sh.set_grid()
    pol, tor = [backend.lsd_to_shtns(truncate_lsd_coefficients(inner[name], inner["lmax"], inner["mmax"],
                   lmax, mmax, backend), sh) for name in ("icBP", "icBT")]
    qst = leeds_inner_qst(pol, tor, sh.l, inner["r"], inner["representations"], backend)
    theta = np.arccos(sh.cos_theta)
    phi = np.linspace(0, 2*np.pi, nphi, endpoint=False)
    fields = np.asarray([sh.synth(*(v[:, ir] for v in qst)) for ir in range(len(inner["r"]))])
    return {name: fields[:, i] for i, name in enumerate(("Br", "Bt", "Bp"))}, theta, phi


def describe_inner_core(root):
    """Expose valid magnetic/fluid domains for all three converters, including old bundles."""
    root = Path(root)
    path = root / "metadata.json"
    meta = json.loads(path.read_text())
    ricb = float(meta.get("r_icb", meta["r_inner"]))
    domains = meta.get("field_domains", {})
    magnetic_minimum = max(meta["r_inner"], *(domains.get(name, {}).get("r_min", meta["r_inner"])
                                              for name in ("Br", "Bt", "Bp")))
    available = ricb > 0 and magnetic_minimum < ricb and all(n in meta["fields"] for n in ("Br", "Bt", "Bp"))
    if not available:
        return False
    domains = meta.setdefault("field_domains", {})
    for name in meta["fields"]:
        if name in MAGNETIC_FIELDS:
            domains.setdefault(name, {"source": "magnetic", "r_min": meta["r_inner"], "r_max": meta["r_outer"]})
        else:
            domains.setdefault(name, {"source": "fluid", "r_min": ricb, "r_max": meta["r_outer"], "outside_native_domain": "zero"})
    meta["inner_core"] = {**meta.get("inner_core", {}), "available": True,
        "version": 1,
        "r_min": magnetic_minimum, "r_max": ricb,
        "fields": [name for name in MAGNETIC_FIELDS if name in meta["fields"]],
        "centre_sampled": magnetic_minimum == 0,
        "boundary_sample": "outer_core_at_shared_icb"}
    path.write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n")
    return True


def extend_leeds_inner_core(root, source, backend, *, required=False, inner=None):
    root = Path(root)
    meta = json.loads((root / "metadata.json").read_text())
    if describe_inner_core(root):
        return  # Existing combined-grid data already include the core.
    inner = read_leeds_inner_core(source) if inner is None else inner
    if inner is None:
        if required:
            raise ValueError("No resolved icr/icBP/icBT inner-core data in this Leeds state.")
        return
    if not all(name in meta["fields"] for name in ("Br", "Bt", "Bp")):
        if not required and not any(np.any(inner[name]) for name in ("icBP", "icBT")):
            return  # Zero-filled IC placeholders in a non-magnetic run.
        raise ValueError("Existing bundle lacks Br/Bt/Bp; run a full magnetic conversion first.")
    old_coords = json.loads(bundle_path(root, meta["coordinates"]).read_text())
    ricb = float(meta.get("r_icb", meta["r_inner"]))
    if ricb <= 0 or not np.isclose(inner["r"][-1], ricb, rtol=1e-8, atol=1e-12):
        raise ValueError("Leeds icr outer boundary does not match the existing ICB.")
    if not np.isclose(meta["r_inner"], ricb, rtol=1e-8):
        raise ValueError("Cannot prepend a separate inner core to an overlapping radial grid.")
    print("Adding inner-core magnetism from icBP/icBT; outer-core outputs are reused.", flush=True)
    native, theta, phi = synthesise_leeds_inner(inner, meta, backend)
    native["Babs"] = np.sqrt(sum(native[name]**2 for name in ("Br", "Bt", "Bp")))
    for name in ("Br", "Bt", "Bp"):
        mean = np.broadcast_to(native[name].mean(axis=-1, keepdims=True), native[name].shape)
        native[name + "_phiavg"] = mean
        native[name + "_nom0"] = native[name] - mean
    strides = meta.get("sampling", {}).get("requested_strides", [1, 1, 1])
    sampling = ViewerSampling(inner["r"], theta, phi, *strides)
    for axis in ("theta", "phi"):
        values = getattr(sampling, axis)
        if len(values) != len(old_coords[axis]) or not np.allclose(values, old_coords[axis], rtol=0, atol=1e-9):
            raise ValueError(f"Inner-core {axis} sampling differs from existing output; no files replaced.")
    keep = sampling.r < ricb - 1e-10 * max(1, ricb)
    prefix_r = sampling.r[keep]
    if not len(prefix_r):
        raise ValueError("No inner-core radial samples below the ICB.")
    old_shape = tuple(meta[n] for n in ("nr", "ntheta", "nphi"))
    prefix_shape = (len(prefix_r), *old_shape[1:])
    domains = meta.setdefault("field_domains", {})
    for name, filename in meta["fields"].items():
        path = bundle_path(root, filename)
        prefix = sampling.volume(native[name])[keep] if name in native else np.zeros(prefix_shape)
        prefix_file = path.with_name(path.name + ".inner-tmp")
        write_f32(prefix_file, prefix)
        # Byte-copy the old part. No re-filtering, re-rounding or outer-core calculation.
        with prefix_file.open("ab") as dest, path.open("rb") as old:
            shutil.copyfileobj(old, dest, 1024 * 1024)
        prefix_file.replace(path)
        if name in native:
            combined = np.memmap(path, mode="r", dtype="<f4", shape=(len(prefix_r) + old_shape[0], *old_shape[1:]))
            lo, hi = float(combined.min()), float(combined.max())
            meta["ranges"][name] = {"min": lo, "max": hi, "absmax": max(abs(lo), abs(hi)),
                                     "mean": float(combined.mean(dtype=np.float64))}
            del combined
        domains[name] = {"source": "magnetic" if name in native else "fluid",
            "r_min": float(prefix_r[0]) if name in native else ricb,
            "r_max": meta["r_outer"], "outside_native_domain": "zero"}
    old_coords["r"] = prefix_r.tolist() + old_coords["r"]
    bundle_path(root, meta["coordinates"]).write_text(json.dumps(old_coords, allow_nan=False) + "\n")
    meta.update(nr=len(old_coords["r"]), r_inner=float(prefix_r[0]), icb_index=len(prefix_r),
                has_conducting_inner_core=True, has_inner_core=True, full_sphere=False,
                physical_geometry="spherical_shell_conducting_inner_core")
    meta.setdefault("magnetic", {})["has_conducting_inner_core"] = True
    meta["magnetic"]["extends_into_inner_core"] = True
    meta.setdefault("geometry_detection", {})["separate_inner_core_data"] = True
    meta.setdefault("sampling", {})["inner_core"] = sampling.description()
    meta["inner_core"] = {"source": "Leeds icr/icBP/icBT", "radial_representations": inner["representations"],
                           "radial_derivative": "local_polynomial_KL3", "outer_core_values_reused": True}
    # Profiles remain on their own explicit r array; they describe fluid diagnostics.
    (root / "metadata.json").write_text(json.dumps(meta, indent=2, allow_nan=False) + "\n")
    describe_inner_core(root)
