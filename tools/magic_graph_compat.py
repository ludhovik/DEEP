"""Narrow, read-only support for archived MagIC V9 shells without IC records.

The normal MagicGraph reader owns every other format. V9 stores seven fields
in Fortran records, in (theta-block, phi) order; latitude rows alternate north
and south. No inner-core values or boundary conditions are manufactured here.
"""
from __future__ import annotations

import os
from pathlib import Path
import struct
from types import SimpleNamespace
import warnings

import numpy as np


def _record(stream, endian, expected):
    """Read one record with an exact, bounded payload and matching markers."""
    offset = stream.tell()
    marker = stream.read(4)
    if len(marker) != 4 or struct.unpack(endian + "i", marker)[0] != expected:
        raise ValueError(f"Invalid MagIC V9 record at byte {offset}: expected {expected} bytes.")
    payload = stream.read(expected)
    tail = stream.read(4)
    if len(payload) != expected or tail != marker:
        raise ValueError(f"Incomplete or mismatched MagIC V9 record at byte {offset}.")
    return payload


def read_v9_shell_without_ic(path: Path, precision):
    """Return a graph only for a complete V9 magnetic shell with absent IC data.

Recognition checks the exact file size before allocating volumes. Record
markers, per-radius latitude coverage, coordinates and finite values are then
validated. A partial IC section is never discarded. A clean EOF after the
shell cannot establish whether IC data were omitted or lost during transfer.
"""
    with Path(path).open("rb") as stream:
        marker = stream.read(4)
        endians = [e for e in ("<", ">") if marker == struct.pack(e + "i", 20)]
        if not endians:
            return None
        endian = endians[0]
        stream.seek(0)
        version = _record(stream, endian, 20).rstrip(b" \x00")
        if version != b"Graphout_Version_9":
            return None
        run_id = _record(stream, endian, 64).rstrip(b" \x00").decode("utf-8", errors="replace")
        marker = stream.read(4)
        if len(marker) != 4:
            raise ValueError("Missing MagIC V9 numeric header.")
        header_size = struct.unpack(endian + "i", marker)[0]
        if header_size not in (52, 104):
            raise ValueError(f"Unsupported MagIC V9 numeric header size: {header_size}.")
        word = header_size // 13
        if np.dtype(precision).itemsize != word:
            raise ValueError(f"MagIC V9 input is float{word * 8}; use --precision float{word * 8}.")
        dtype = np.dtype(endian + ("f4" if word == 4 else "f8"))
        stream.seek(-4, os.SEEK_CUR)
        header = np.frombuffer(_record(stream, endian, header_size), dtype=dtype)
        if not np.isfinite(header).all():
            raise ValueError("Nonfinite MagIC V9 header.")
        dims = header[1:7]
        if np.any(dims != np.floor(dims)) or np.any(dims < 1):
            raise ValueError("Invalid MagIC V9 grid dimensions.")
        nr, nt, np_header, nr_ic, minc, blocks = map(int, dims)
        pm, ratio, sigma = map(float, header[10:13])
        if pm == 0 or nr_ic <= 2:
            return None
        if nr < 2 or nt < 2 or nt % 2 or blocks > nt or not 0 < ratio < 1:
            raise ValueError("Invalid MagIC V9 shell grid.")
        # Match MagicGraph's legacy full-phi versus sector-phi convention.
        if np_header == 2 * nt:
            if np_header % minc:
                raise ValueError("MagIC V9 phi grid is incompatible with minc.")
            nphi = np_header // minc
        else:
            nphi = np_header
        shell_size = (stream.tell() + nt * word + 8
                      + nr * blocks * (4 * word + 8 + 7 * 8)
                      + 7 * nr * nt * nphi * word)
        if os.fstat(stream.fileno()).st_size != shell_size:
            return None

        theta = np.frombuffer(_record(stream, endian, nt * word), dtype=dtype).copy()
        if (not np.isfinite(theta).all() or np.any(theta <= 0)
                or np.any(theta >= np.pi) or np.any(np.diff(theta) <= 0)):
            raise ValueError("Invalid MagIC V9 colatitudes.")
        names = ("entropy", "vr", "vtheta", "vphi", "Br", "Btheta", "Bphi")
        fields = {name: np.empty((nphi, nt, nr), dtype=precision) for name in names}
        radius = np.full(nr, np.nan, dtype=precision)
        covered = np.zeros((nr, nt), dtype=bool)
        block_counts = np.zeros(nr, dtype=int)
        for _ in range(nr * blocks):
            ir, rad, first, last = np.frombuffer(_record(stream, endian, 4 * word), dtype=dtype)
            if (not np.isfinite([ir, rad, first, last]).all()
                    or ir != int(ir) or first != int(first) or last != int(last)
                    or not 0 <= ir < nr or not 1 <= first <= last <= nt or rad <= 0):
                raise ValueError("Invalid MagIC V9 radius/latitude block.")
            ir, lo, hi = int(ir), int(first) - 1, int(last)
            if covered[ir, lo:hi].any() or (np.isfinite(radius[ir]) and radius[ir] != rad):
                raise ValueError("Overlapping or inconsistent MagIC V9 blocks.")
            radius[ir] = rad
            covered[ir, lo:hi] = True
            block_counts[ir] += 1
            for name in names:
                data = np.frombuffer(_record(stream, endian, (hi - lo) * nphi * word), dtype=dtype)
                if not np.isfinite(data).all():
                    raise ValueError(f"Nonfinite MagIC V9 field {name}.")
                fields[name][:, lo:hi, ir] = data.reshape(hi - lo, nphi).T
        if not covered.all() or np.any(block_counts != blocks) or stream.read(1):
            raise ValueError("Incomplete MagIC V9 shell coverage or unexpected trailing data.")
        if not (np.all(np.diff(radius) < 0) or np.all(np.diff(radius) > 0)):
            raise ValueError("Invalid MagIC V9 radii.")
        # This is MagicGraph.rearangeLat's legacy hemispherical unfolding.
        for name, field in fields.items():
            fields[name] = np.concatenate((field[:, ::2, :], field[:, 1::2, :][:, ::-1, :]), axis=1)
        graph = SimpleNamespace(
            **fields, radius=radius / (1.0 - ratio), colatitude=theta,
            nr=nr, ntheta=nt, npI=nphi, nphi=nphi * minc + 1, minc=minc,
            n_r_ic_max=0, precision=precision, time=float(header[0]),
            ra=float(header[7]), ek=float(header[8]), pr=float(header[9]),
            prmag=pm, radratio=ratio, sigma=sigma,
            deepscope_reader_metadata={
                "reader": "deepscope_magic_v9_shell", "format": "Graphout_Version_9",
                "run_id": run_id, "input_precision": f"float{word * 8}",
                "inner_core_records": "absent", "declared_inner_radial_points": nr_ic,
                "sigma": sigma, "shell_records_validated": True,
            },
        )
    warnings.warn(
        "MagIC V9 file contains a complete fluid shell but no declared inner-core records. "
        "Loading shell fields only; conductivity sigma is preserved. "
        "Inner-core omission versus truncation at the shell boundary cannot be distinguished.",
        RuntimeWarning, stacklevel=2,
    )
    return graph
