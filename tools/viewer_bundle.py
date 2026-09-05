"""Numerical sampling and transactional output for the three viewer converters."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import math
import os
import shutil
import tempfile
import uuid

import numpy as np
from scipy.signal import resample


def write_f32(path: Path, arr: np.ndarray) -> dict[str, float]:
    """Reject invalid scientific values, including overflow during float32 conversion."""
    values = np.asarray(arr)
    if not values.size or not np.all(np.isfinite(values)):
        raise ValueError(f"{Path(path).name}: empty field or non-finite input values; no file written.")
    if np.iscomplexobj(values):
        raise ValueError(f"{Path(path).name}: expected a real physical-space field.")
    with np.errstate(over="ignore", invalid="ignore"):
        values = np.ascontiguousarray(values, dtype="<f4")
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{Path(path).name}: values overflow float32; no file written.")
    minimum, maximum = float(values.min()), float(values.max())
    result = {
        "min": minimum, "max": maximum,
        "mean": float(np.mean(values, dtype=np.float64)),
        "absmax": max(abs(minimum), abs(maximum)),
    }
    values.tofile(path)
    return result


def _coordinate(values, name):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.isfinite(values).all():
        raise ValueError(f"{name} must contain at least two finite coordinates.")
    if np.any(np.diff(values) <= 0):
        raise ValueError(f"{name} coordinates must be strictly increasing.")
    return values


class ViewerSampling:
    """Keep radial boundaries; low-pass angular fields before reducing samples.

    Phi is Fourier-resampled onto a complete periodic grid, even when the
    requested stride does not divide nphi. Theta uses a Gaussian low-pass in
    physical colatitude (trapezoidal integration), then retains native nodes.
    Native arrays used for derivatives and line tracing are never modified.
    """
    def __init__(self, r, theta, phi, dr=1, dt=1, dp=1, required_radii=()):
        self.native_r = _coordinate(r, "r")
        self.native_theta = _coordinate(theta, "theta")
        self.native_phi = _coordinate(phi, "phi")
        self.dr, self.dt, self.dp = (max(1, int(v)) for v in (dr, dt, dp))
        ridx = set(range(0, len(r), self.dr)) | {0, len(r) - 1}
        extra_radii = []
        for radius in required_radii:
            index = int(np.argmin(np.abs(self.native_r - radius)))
            if not np.isclose(self.native_r[index], radius, rtol=1e-9, atol=1e-11):
                if not self.native_r[0] <= radius <= self.native_r[-1]:
                    raise ValueError(f"Required boundary r={radius} is outside the native radial grid.")
                extra_radii.append(float(radius))
            else:
                ridx.add(index)
        self.r_indices = np.asarray(sorted(ridx), dtype=int)
        self.theta_indices = np.asarray(sorted(set(range(0, len(theta), self.dt)) | {0, len(theta) - 1}), dtype=int)
        self.r = np.unique(np.concatenate((self.native_r[self.r_indices], extra_radii)))
        self.radial_hi = np.clip(np.searchsorted(self.native_r, self.r), 1, len(r) - 1)
        self.radial_lo = self.radial_hi - 1
        self.radial_weight = (self.r - self.native_r[self.radial_lo]) / (self.native_r[self.radial_hi] - self.native_r[self.radial_lo])
        self.theta = self.native_theta[self.theta_indices]
        self.phi = self.native_phi.copy()
        self.theta_weights = None
        if self.dt > 1:
            th = self.native_theta
            widths = np.empty_like(th)
            widths[1:-1] = 0.5 * (th[2:] - th[:-2])
            widths[0], widths[-1] = 0.5 * (th[1] - th[0]), 0.5 * (th[-1] - th[-2])
            sigma = 0.5 * self.dt * float(np.median(np.diff(th)))
            delta = (self.theta[:, None] - th[None, :]) / sigma
            weights = np.exp(-0.5 * delta**2) * widths[None, :]
            weights[np.abs(delta) > 4.0] = 0.0
            self.theta_weights = weights / weights.sum(axis=1, keepdims=True)
        if self.dp > 1:
            spacing = np.diff(self.native_phi)
            if not np.allclose(spacing, 2 * np.pi / len(phi), rtol=1e-6, atol=1e-9):
                raise ValueError("Phi downsampling requires a uniform, full-2pi, endpoint-exclusive grid.")
            count = max(2, int(math.ceil(len(phi) / self.dp)))
            self.phi = self.native_phi[0] + 2 * np.pi * np.arange(count) / count

    def radial(self, values):
        values = np.asarray(values)
        if values.shape[0] != len(self.native_r):
            raise ValueError("Radial field shape does not match the native grid.")
        if np.array_equal(self.r, self.native_r):
            return values
        if np.array_equal(self.r, self.native_r[self.r_indices]):
            return values[self.r_indices]
        weights = self.radial_weight.reshape((-1,) + (1,) * (values.ndim - 1))
        return (1 - weights) * values[self.radial_lo] + weights * values[self.radial_hi]

    def angular(self, values):
        values = np.asarray(values)
        if values.shape[-2:] != (len(self.native_theta), len(self.native_phi)):
            raise ValueError("Angular field shape does not match the native coordinates.")
        if not np.isfinite(values).all():
            raise ValueError("Cannot downsample a field containing non-finite values.")
        if self.dp > 1:
            values = resample(values, len(self.phi), axis=-1)
        if self.theta_weights is not None:
            values = np.einsum("jt,...tp->...jp", self.theta_weights, values, optimize=True)
        return np.ascontiguousarray(values)

    def volume(self, values):
        if not np.isfinite(values).all():
            raise ValueError("Cannot downsample a field containing non-finite values.")
        return self.angular(self.radial(values))

    def description(self):
        return {
            "requested_strides": [self.dr, self.dt, self.dp],
            "radial_indices": self.r_indices.tolist(),
            "preserves_cmb_icb": True,
            "theta_filter": "gaussian_in_colatitude" if self.dt > 1 else "none",
            "phi_filter": "fourier_resample" if self.dp > 1 else "none",
            "field_lines": "traced_on_native_grid_not_viewer_downsampled_grid",
        }


def _json(path):
    def invalid(value):
        raise ValueError(f"Non-finite JSON number {value} in {path}")
    def finite_float(value):
        result = float(value)
        return result if math.isfinite(result) else invalid(value)
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, parse_constant=invalid, parse_float=finite_float)


def bundle_path(root, relative):
    """Only allow paths inside the output bundle (also for sequence subdirs)."""
    relative = Path(relative)
    root = Path(root).resolve()
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError(f"Expected a relative path inside the bundle: {relative}")
    result = (root / relative).resolve()
    if not result.is_relative_to(root) or result == root:
        raise ValueError(f"Path escapes the output bundle: {relative}")
    return result


def validate_bundle(root):
    """Validate dimensions, coordinates, binaries and referenced line files before publishing."""
    root = Path(root)
    meta = _json(root / "metadata.json")
    shape = tuple(meta[k] for k in ("nr", "ntheta", "nphi"))
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 2 for n in shape):
        raise ValueError("Invalid viewer grid dimensions.")
    coordinates = _json(bundle_path(root, meta["coordinates"]))
    for name, length in zip(("r", "theta", "phi"), shape):
        if len(_coordinate(coordinates[name], name)) != length:
            raise ValueError(f"Wrong {name} coordinate count.")
    r_inner, r_outer = float(meta["r_inner"]), float(meta["r_outer"])
    if not (math.isfinite(r_inner) and math.isfinite(r_outer) and 0 <= r_inner < r_outer):
        raise ValueError("Invalid radial domain in metadata.")
    if not np.allclose([coordinates["r"][0], coordinates["r"][-1]], [r_inner, r_outer], rtol=0, atol=1e-8 * max(1, abs(r_outer))):
        raise ValueError("Radial endpoints do not match metadata.")
    if coordinates["theta"][0] < -1e-6 or coordinates["theta"][-1] > math.pi + 1e-6:
        raise ValueError("Colatitudes are outside [0, pi].")
    if coordinates["phi"][-1] - coordinates["phi"][0] >= 2 * math.pi - 1e-10:
        raise ValueError("Longitude coordinates duplicate the periodic seam.")
    if not meta.get("fields"):
        raise ValueError("No volume fields were exported.")
    binaries = [(name, math.prod(shape)) for name in meta["fields"].values()]
    binaries += [(info["file"], shape[1] * shape[2]) for info in meta.get("surface_fields", {}).values()]
    for filename, length in binaries:
        path = bundle_path(root, filename)
        if path.stat().st_size != length * 4:
            raise ValueError(f"Wrong binary size: {filename}")
        with path.open("rb") as stream:
            while True:
                chunk = np.fromfile(stream, dtype="<f4", count=262144)
                if not chunk.size:
                    break
                if not np.isfinite(chunk).all():
                    raise ValueError(f"Non-finite float32 values in {filename}")
    if meta.get("profiles"):
        _json(bundle_path(root, meta["profiles"]))
    for filename in set(v for v in meta.get("field_lines", {}).values() if isinstance(v, str) and v.endswith(".json")):
        _json(bundle_path(root, filename))
    sequence_path = root / "sequence.json"
    if sequence_path.exists():
        sequence = _json(sequence_path)
        if not sequence.get("frames"):
            raise ValueError("The sequence contains no frames.")
        for frame in sequence["frames"]:
            frame_root = bundle_path(root, frame["path"])
            if (frame_root / "sequence.json").exists():
                raise ValueError("Nested sequence indices are not supported.")
            validate_bundle(frame_root)


def _managed_names(root):
    root = Path(root)
    names = {"metadata.json", "coordinates.json", "profiles.json", "sequence.json", "frames"}
    for pattern in ("*_volume.f32", "*_cmb.f32", "*_earth.f32", "B_lines*.json"):
        names.update(path.name for path in root.glob(pattern))
    if (root / "sequence.json").exists():
        # Preserve unrelated files, but not stale frames from an older sequence.
        for frame in _json(root / "sequence.json").get("frames", []):
            frame_path = bundle_path(root, frame["path"])
            names.add(frame_path.relative_to(root.resolve()).parts[0])
    return names


def _backup_path(target):
    # In a checkout, keep old bundles outside public/ so Vite does not copy
    # them into the deployed site. Renames still require the same filesystem.
    for parent in target.parents:
        if (parent / ".git").exists() and parent.stat().st_dev == target.stat().st_dev:
            history = parent / ".deepscope-backups"
            if history.is_symlink():
                raise ValueError("The output-backup directory must not be a symbolic link.")
            history.mkdir(exist_ok=True)
            return history / f"{target.name}-{uuid.uuid4().hex[:12]}"
    return target.with_name(f".deepscope-backup-{target.name}-{uuid.uuid4().hex[:12]}")


@contextmanager
def staged_bundle_output(destination):
    """Publish only a complete bundle, retaining the preceding directory as a backup.

    Conversion/validation failures never change the destination. Both rename
    operations are on the same filesystem; a failed second rename is rolled
    back. An abrupt interruption between renames leaves the previous bundle in
    the printed backup, rather than deleting it.
    """
    raw = Path(destination).expanduser()
    if raw.is_symlink():
        raise ValueError("Choose a real output directory, not a symbolic link.")
    target = raw.resolve()
    forbidden = {Path.home().resolve(), Path.cwd().resolve(), *Path.cwd().resolve().parents}
    if target in forbidden or (target / ".git").exists():
        raise ValueError("Use a dedicated output subdirectory, not a home, project or working-directory root.")
    if target.exists() and not target.is_dir():
        raise ValueError(f"Output is not a directory: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".deepscope-stage-{target.name}-", dir=target.parent) as temp:
        stage = Path(temp) / "bundle"
        stage.mkdir()
        yield stage
        validate_bundle(stage)
        if target.exists():
            managed = _managed_names(target)
            for item in target.iterdir():
                if item.name in managed:
                    continue
                dest = stage / item.name
                if dest.exists() or dest.is_symlink():
                    raise ValueError(f"Refusing to overwrite unrelated output content: {item.name}")
                if item.is_dir() and not item.is_symlink():
                    shutil.copytree(item, dest, symlinks=True)
                else:
                    shutil.copy2(item, dest, follow_symlinks=False)
            backup = _backup_path(target)
            print(f"Previous output backup: {backup}", flush=True)
            os.replace(target, backup)
            try:
                os.replace(stage, target)
            except BaseException:
                os.replace(backup, target)
                raise
        else:
            os.replace(stage, target)
    print(f"Validated viewer bundle published to: {target}")
