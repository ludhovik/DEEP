"""Read Calypso merged ASCII restart data and reconstruct spherical fields.

Conventions follow Calypso/Kemorin: zonal_wavenumber_4_legendre.f90,
copy_rj_phys_data_4_IO.f90, schmidt.f90 and legendre_bwd_trans_org.f90.
The file's three vector columns are P, T, dP/dr, in that order.
"""
from __future__ import annotations

import gzip
import math
from pathlib import Path
import shlex

import numpy as np

try:
    from conversion_cache import cached_calculation
    from spectral_truncation import harmonic_basis
except ImportError:
    from tools.conversion_cache import cached_calculation
    from tools.spectral_truncation import harmonic_basis


def _line(stream):
    while True:
        line = stream.readline()
        if not line:
            raise ValueError("Unexpected end of Calypso file.")
        line = line.strip()
        if line and not line.startswith((b"!", b"#")):
            return line


def read_merged_ascii(path, selected=None):
    """Read merged .fst/.fld (also gzip), validating rank and byte stacks."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        ranks = int(_line(stream))
        step = int(_line(stream))
        clock = np.fromstring(_line(stream).decode().replace("D", "E"), sep=" ")
        counts = np.fromstring(_line(stream), sep=" ", dtype=np.int64)
        nf = int(_line(stream))
        components = np.fromstring(_line(stream), sep=" ", dtype=np.int64)
        if (ranks < 1 or len(counts) != ranks or np.any(np.diff(np.r_[0, counts]) <= 0)
                or len(clock) != 2 or not np.isfinite(clock).all()
                or nf < 1 or len(components) != nf or np.any(components < 1)):
            raise ValueError("Invalid Calypso merged field header.")
        fields = {}
        names = []
        for nc in components:
            name = _line(stream).decode("ascii")
            if name in names:
                raise ValueError(f"Duplicate Calypso field {name!r}.")
            names.append(name)
            sizes = np.fromstring(_line(stream), sep=" ", dtype=np.int64)
            if len(sizes) != ranks or not np.array_equal(sizes, counts * (25 * nc + 1)):
                raise ValueError(f"Invalid byte offsets for Calypso field {name!r}.")
            size = int(sizes[-1])
            if selected is not None and name not in selected:
                start = stream.tell()
                if path.suffix != ".gz" and start + size > path.stat().st_size:
                    raise ValueError(f"Truncated Calypso field {name!r}.")
                stream.seek(size, 1)
                if stream.tell() != start + size:
                    raise ValueError(f"Truncated Calypso field {name!r}.")
                continue
            payload = stream.read(size)
            if len(payload) != size:
                raise ValueError(f"Truncated Calypso field {name!r}.")
            values = np.fromstring(payload.replace(b"D", b"E"), sep=" ")
            if values.size != counts[-1] * nc or not np.isfinite(values).all():
                raise ValueError(f"Invalid/nonfinite Calypso field {name!r}.")
            fields[name] = values.reshape(int(counts[-1]), int(nc))
        if stream.read(1):
            raise ValueError("Unexpected trailing data in Calypso merged ASCII file.")
    return {"ranks": ranks, "step": step, "time": float(clock[0]),
            "dt": float(clock[1]), "counts": np.diff(np.r_[0, counts]),
            "fields": fields, "field_names": names}


def read_controls(path):
    """Read control entries and the linked spherical-grid control, without exec."""
    records, files, active = [], [], set()
    root = Path(path).resolve().parent

    def read(current, context=()):
        current = current.resolve()
        if current in active:
            raise ValueError("Cyclic Calypso control-file reference.")
        active.add(current)
        files.append(current)
        stack = list(context)
        for line in current.read_text().splitlines():
            lex = shlex.shlex(line, posix=True)
            lex.whitespace_split = True
            lex.commenters = "!#"
            parts = list(lex)
            if not parts:
                continue
            key = parts[0].lower()
            if key in ("begin", "array"):
                stack.append(parts[1].lower())
            elif key == "end":
                if stack:
                    stack.pop()
            elif key == "file" and len(parts) == 3 and parts[1].lower() == "spherical_shell_ctl":
                target = root / parts[2]
                if not target.is_file():
                    target = current.parent / parts[2]
                read(target, tuple(stack))
            else:
                records.append((tuple(stack), key, parts[1:]))
        active.remove(current)

    read(Path(path))
    return records, files


def control_value(records, name, default=None, section=None):
    values = [args for scope, key, args in records
              if key == name.lower() and (section is None or section.lower() in scope)]
    if not values:
        return default
    if len(values) != 1 or len(values[0]) != 1:
        raise ValueError(f"Expected one Calypso control value for {name!r}.")
    return values[0][0]


def number(text):
    value = float(str(text).replace("d", "e").replace("D", "E"))
    if not math.isfinite(value):
        raise ValueError("Nonfinite Calypso control value.")
    return value


def spectral_rank_modes(lmax, radial_domains, horizontal_domains, folding=1,
                        distribution="cyclic_eq_mode"):
    """Native RJ ordering: descending signed m, then increasing l.

    The old, unused set_zonal_wavenum_4_legendre routine has the opposite
    signed-m order. Use the active select_zonal_4_legendre implementation.
    """
    if min(radial_domains, horizontal_domains, folding) < 1:
        raise ValueError("Calypso domain counts and folding must be positive.")
    assignments = {}
    ip, direction = 0, 1
    half = (lmax - lmax % 2) // (2 * folding)
    order = (range(lmax // folding + 1) if distribution == "simple" else
             [*range(1, half + 1), 0, *range(half + 1, lmax // folding + 1)])
    if distribution not in ("cyclic_eq_mode", "original", "simple"):
        raise ValueError(f"Unsupported Calypso mode distribution {distribution!r}.")
    for m in order:
        assignments[m] = ip
        ip += direction
        if ip >= horizontal_domains:
            ip, direction = horizontal_domains - 1, -1
        elif ip < 0:
            ip, direction = 0, 1
    groups = []
    for domain in range(horizontal_domains):
        modes = [(ell, m * folding) for m in range(lmax // folding, -(lmax // folding) - 1, -1)
                 if assignments[abs(m)] == domain for ell in range(abs(m * folding), lmax + 1)]
        groups.append(np.array_split(np.asarray(modes, dtype=int).reshape(-1, 2), radial_domains))
    return [groups[m][r] for r in range(radial_domains) for m in range(horizontal_domains)]


def unpack_spectra(merged, modes, nr, has_center=False):
    """Reorder rank-contiguous (radius, local mode) blocks to l(l+1)+m."""
    expected = np.array([nr * len(group) + int(has_center and np.any(np.all(group == (0, 0), axis=1)))
                         for group in modes])
    if not np.array_equal(merged["counts"], expected):
        raise ValueError(f"Restart node counts {merged['counts'].tolist()} do not match the control grid "
                         f"{expected.tolist()}; supply the matching control/grid files.")
    max_degree = max(int(group[:, 0].max()) for group in modes if len(group))
    result, centres = {}, {}
    for name, values in merged["fields"].items():
        data = np.zeros((nr, (max_degree + 1)**2, values.shape[1]))
        offset = 0
        for group, count in zip(modes, expected):
            size = nr * len(group)
            ids = group[:, 0] * (group[:, 0] + 1) + group[:, 1]
            data[:, ids] = values[offset:offset + size].reshape(nr, len(group), values.shape[1])
            if count > size:
                centres[name] = values[offset + size].copy()
            offset += int(count)
        result[name] = data
    return result, centres


@cached_calculation
def synthesize_spectra(coefficients, radius, theta, nphi, lmax, vector=False):
    """Schmidt real harmonics: m>0 cos(m phi), m<0 sin(|m| phi).

    Vector: Vr=l(l+1)P/r², Vtheta=(P' dthetaY+T dphiY/sinθ)/r,
    Vphi=(P' dphiY/sinθ-T dthetaY)/r. The stored P' is used directly.
    """
    radius = np.asarray(radius)
    if np.any(radius <= 0):
        raise ValueError("Synthesize positive radii; reconstruct a centre separately.")
    nc = 3 if vector else 1
    if coefficients.shape[0] != len(radius) or coefficients.shape[-1] != nc:
        raise ValueError("Calypso coefficient shape does not match its field/grid.")
    spectra = [np.zeros((len(radius), len(theta), nphi // 2 + 1), complex) for _ in range(nc)]
    for m in range(lmax + 1):
        ell = np.arange(m, lmax + 1)
        pos = ell * (ell + 1) + m
        neg = ell * (ell + 1) - m
        # Convert orthonormal Condon--Shortley basis to Schmidt, no CS phase.
        y, d, h = harmonic_basis(lmax, m, theta)
        norm = (-1)**m * np.sqrt((8 if m else 4) * np.pi / (2 * ell + 1))
        y, d, h = [basis * norm[:, None] for basis in (y, d, h)]
        c = coefficients[:, pos].astype(complex)
        if m:
            c = (c - 1j * coefficients[:, neg]) * 0.5
        if vector:
            p, t, deriv = c[..., 0], c[..., 1], c[..., 2]
            spectra[0][..., m] = (p * (ell * (ell + 1))[None, :]) @ y / radius[:, None]**2
            spectra[1][..., m] = (deriv @ d + 1j * t @ h) / radius[:, None]
            spectra[2][..., m] = (1j * deriv @ h - t @ d) / radius[:, None]
        else:
            spectra[0][..., m] = c[..., 0] @ y
    return tuple(np.ascontiguousarray(np.fft.irfft(a * nphi, n=nphi, axis=-1)) for a in spectra)


def grid_from_controls(records, geometry="auto"):
    """Recover the native grid, including explicit grids and insulating extensions."""
    get = lambda key, default=None: control_value(records, key, default)
    lmax = int(get("truncation_level_ctl"))
    nranks_r = int(get("num_radial_domain_ctl", 1))
    nranks_m = int(get("num_horizontal_domain_ctl", 1))
    folding = int(get("longitude_symmetry_ctl", 1))
    distribution = get("rlm_order_distribution", "cyclic_eq_mode").lower()
    ordering = get("ordering_set_ctl", "").lower()
    if ordering in ("ver_1", "ver_2"):
        distribution = "original" if ordering == "ver_1" else "cyclic_eq_mode"
    elif ordering:
        raise ValueError(f"Unsupported Calypso ordering_set_ctl {ordering!r}.")
    if distribution not in ("cyclic_eq_mode", "original", "simple"):
        raise ValueError(f"Unsupported Calypso rlm_order_distribution {distribution!r}.")
    if get("rj_inner_loop_direction", "horizontal").lower() not in ("horizontal", "mode", "modes"):
        raise ValueError("Calypso reader requires the default horizontal RJ inner loop.")
    if any(key in ("num_domain_sph_grid", "num_domain_legendre", "num_domain_spectr") for _, key, _ in records):
        raise ValueError("Use native num_radial_domain_ctl/num_horizontal_domain_ctl controls; custom domain arrays need their RJ grid map.")
    if get("ngrid_meridonal_ctl") is None:
        raise ValueError("Matching Calypso ngrid_meridonal_ctl is required; the restart has no angular grid.")
    nt = int(get("ngrid_meridonal_ctl"))
    if folding < 1 or 2 * nt % folding:
        raise ValueError("Calypso longitude symmetry must divide twice the meridional resolution.")
    # set_global_sph_resolution derives the sector FFT size from theta.
    # ngrid_zonal_ctl is retained in old controls but ignored by native code.
    np_sector = 2 * nt // folding
    if lmax < 1 or nt <= lmax or np_sector * folding <= 2 * lmax:
        raise ValueError("Calypso angular control grid does not resolve its truncation.")
    kind = get("radial_grid_type_ctl", "Chebyshev").lower()
    boundaries = {args[0].lower(): int(args[1]) - 1 for _, key, args in records
                  if key == "boundaries_ctl" and len(args) == 2}
    if kind == "explicit":
        entries = [(int(args[0]), number(args[1])) for _, key, args in records
                   if key == "r_layer" and len(args) == 2]
        entries.sort()
        if [i for i, _ in entries] != list(range(1, len(entries) + 1)):
            raise ValueError("Explicit Calypso r_layer indices must cover 1..nr once.")
        r = np.array([value for _, value in entries])
        icb = boundaries.get("icb", 0)
        cmb = boundaries.get("cmb", len(r) - 1)
        center = get("sph_coef_type_ctl", "").lower() == "with_center"
    else:
        if kind not in ("chebyshev", "equi_distance"):
            raise ValueError(f"Unsupported generated Calypso radial grid {kind!r}; supply explicit r_layer controls.")
        inner, outer = get("icb_radius_ctl"), get("cmb_radius_ctl")
        if inner is not None and outer is not None:
            ri, ro = number(inner), number(outer)
        else:
            ratio = number(get("icb_to_cmb_ratio_ctl"))
            thickness = number(get("fluid_core_size_ctl"))
            if not 0 <= ratio < 1 or thickness <= 0:
                raise ValueError("Invalid Calypso shell radius ratio/size.")
            ri = thickness * ratio / (1 - ratio)
            ro = ri + thickness
        intervals = int(get("num_fluid_grid_ctl"))
        if intervals < 2 or not 0 <= ri < ro:
            raise ValueError("Invalid Calypso radial resolution or boundaries.")
        rmin, rmax = number(get("min_radius_ctl", ri)), number(get("max_radius_ctl", ro))
        if not 0 <= rmin <= ri or rmax < ro:
            raise ValueError("Invalid Calypso minimum/maximum radial extension.")
        width = ro - ri
        if kind == "equi_distance":
            dr = width / intervals
            nin = max(0, int((ri-rmin) / dr))
            nout = max(0, int((rmax-ro) / dr) + 1) if rmax > ro else 0
            icb, cmb = nin, nin + intervals
            r = ri + (np.arange(cmb + nout + 1) - icb) * dr
        else:
            # Same half-Chebyshev continuation, then linear spacing, as Calypso.
            half = intervals // 2
            offset = lambda k: 0.5 * width * (1 - math.cos(math.pi * k / intervals))
            k, value = 0, ri
            dr = offset(1)
            while value > rmin and k < half:
                k += 1
                value = ri - offset(k)
                dr = offset(k) - offset(k - 1)
            if k == half:
                k = int((value - rmin) / dr) + half
            nin = max(0, k - 1)
            k, value = 0, ro
            while value < rmax and k < half:
                k += 1
                value = ro + offset(k)
                dr = offset(k) - offset(k - 1)
            while value < rmax:
                k += 1
                value += dr
            nout = k if k > 1 else 0
            icb, cmb = nin, nin + intervals
            fluid = ri + np.array([offset(i) for i in range(intervals + 1)])
            inside = [ri - offset(i) for i in range(1, min(nin, half) + 1)]
            while len(inside) < nin:
                inside.append(inside[-1] - (offset(half) - offset(half - 1)))
            outside = [ro + offset(i) for i in range(1, min(nout, half) + 1)]
            while len(outside) < nout:
                outside.append(outside[-1] + (offset(half) - offset(half - 1)))
            r = np.r_[inside[::-1], fluid, outside]
        center = rmin == 0
    if (r.size < 3 or not np.isfinite(r).all() or np.any(r < 0) or np.any(np.diff(r) <= 0)
            or not 0 <= icb < cmb < r.size):
        raise ValueError("Invalid Calypso radial grid or ICB/CMB indices.")
    centre_velocity = any(key == "bc_velocity" and any("center" in arg.lower() for arg in args[:1])
                          for _, key, args in records)
    full = bool(r[icb] == 0 or centre_velocity or (geometry == "full-sphere" and center and icb == 0))
    if geometry == "full-sphere" and not full:
        raise ValueError("A positive-radius Calypso shell cannot be relabelled full-sphere; need centre controls.")
    if geometry in ("shell", "conducting-inner-core") and full:
        raise ValueError("Requested shell geometry conflicts with Calypso centre controls.")
    return {"r": r, "icb": icb, "cmb": cmb, "center": center,
            "full_sphere": full, "radial_domains": nranks_r, "horizontal_domains": nranks_m,
            "lmax": lmax, "minc": folding, "ntheta": nt, "nphi": np_sector * folding,
            "mode_distribution": distribution,
            "radial_grid_type": kind}


NATIVE_FIELDS = ("velocity", "temperature", "composition", "magnetic_field", "pressure")


@cached_calculation
def read_restart(path, grid):
    merged = read_merged_ascii(path, NATIVE_FIELDS)
    modes = spectral_rank_modes(grid["lmax"], grid["radial_domains"],
                                grid["horizontal_domains"], grid["minc"], grid["mode_distribution"])
    if merged["ranks"] != len(modes):
        raise ValueError("Calypso restart MPI count differs from the control files.")
    spectra, centres = unpack_spectra(merged, modes, len(grid["r"]), grid["center"])
    return spectra, centres, {key: merged[key] for key in ("time", "dt", "step", "field_names")}


def centre_vector(coefficients, first_radius, theta, nphi):
    """Regular degree-one centre estimate from the nearest radial shell.

    Calypso's centre transform uses P_1m(r_first)/r_first². Project one
    Cartesian vector onto every spherical basis; there is no toroidal limit.
    """
    v = coefficients[0]
    xyz = 2 * np.array([v[3, 0], v[1, 0], v[2, 0]]) / first_radius**2
    th = np.asarray(theta)[:, None]
    ph = np.arange(nphi)[None, :] * (2 * math.pi / nphi)
    x, y, z = xyz
    radial = x*np.sin(th)*np.cos(ph) + y*np.sin(th)*np.sin(ph) + z*np.cos(th)
    polar = x*np.cos(th)*np.cos(ph) + y*np.cos(th)*np.sin(ph) - z*np.sin(th)
    azimuthal = np.broadcast_to(-x*np.sin(ph) + y*np.cos(ph), radial.shape)
    return radial[None], polar[None], azimuthal[None]
