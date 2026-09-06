"""Angular degree cutoffs and scalar/vector projection of MagIC graphic grids."""
from __future__ import annotations

import argparse
import math
import numpy as np


def nonnegative_lmax(value):
    degree = int(value)
    if degree < 0:
        raise argparse.ArgumentTypeError("--spectral-lmax must be >= 0 (0 keeps all degrees).")
    return degree


def cutoff_metadata(requested, original, mmax=None):
    requested = 0 if requested is None else int(requested)
    if requested < 0:
        raise ValueError("--spectral-lmax must be >= 0.")
    effective = min(requested, int(original)) if requested else int(original)
    info = {"enabled": effective < original, "requested_lmax": requested,
            "lmax_original": int(original), "lmax_effective": effective}
    if mmax is not None:
        info.update(mmax_original=int(mmax), mmax_effective=min(int(mmax), effective))
    return info


def harmonic_basis(lmax, m, theta):
    """Orthonormal Y_lm(theta,0), d_theta Y_lm, m*Y_lm/sin(theta).

    Normalized recurrences avoid overflowing unnormalized associated Legendre
    functions at large m. These grids exclude the coordinate singularities.
    """
    theta = np.asarray(theta, dtype=np.float64)
    x, sine = np.cos(theta), np.sin(theta)
    diagonal = np.full_like(x, 1.0 / math.sqrt(4.0 * math.pi))
    for order in range(1, m + 1):
        diagonal *= -math.sqrt((2 * order + 1) / (2 * order)) * sine
    y = np.empty((lmax - m + 1, len(theta)))
    y[0] = diagonal
    if lmax > m:
        y[1] = math.sqrt(2 * m + 3) * x * diagonal
    for ell in range(m + 2, lmax + 1):
        a = math.sqrt((4 * ell**2 - 1) / (ell**2 - m**2))
        b = math.sqrt(((2 * ell + 1) * ((ell - 1)**2 - m**2)) /
                      ((2 * ell - 3) * (ell**2 - m**2)))
        y[ell - m] = a * x * y[ell - m - 1] - b * y[ell - m - 2]
    derivative = np.empty_like(y)
    for ell in range(m, lmax + 1):
        previous = 0.0 if ell == m else math.sqrt(
            (2 * ell + 1) * (ell**2 - m**2) / (2 * ell - 1)) * y[ell - m - 1]
        derivative[ell - m] = (ell * x * y[ell - m] - previous) / sine
    return y, derivative, m * y / sine


class GraphicProjector:
    """Project a full-longitude Gauss grid, then synthesize a smaller grid.

    Tangential vector components use vector spherical harmonics (Q,S,T),
    not independent scalar fits. Scalars retain their l=0 mean.
    """
    def __init__(self, theta, phi, lmax, minc=1):
        self.theta_in, self.phi_in = np.asarray(theta), np.asarray(phi)
        self.lmax = int(lmax)
        self.minc = max(1, int(minc))
        gx, gw = np.polynomial.legendre.leggauss(len(theta))
        if not np.allclose(np.cos(theta), gx[::-1], rtol=0.0, atol=5e-6):
            raise ValueError("MagIC spectral truncation requires the native Gauss colatitude grid.")
        expected_phi = np.arange(len(phi)) * (2 * math.pi / len(phi))
        if not np.allclose(phi, expected_phi, rtol=0.0, atol=1e-10):
            raise ValueError("MagIC spectral truncation requires a full uniform longitude grid starting at zero.")
        if self.lmax >= len(theta) or 2 * self.lmax >= len(phi):
            raise ValueError("Requested degree is not resolved by the MagIC graphic grid.")
        # Resolve the retained linear harmonics; further downsampling is handled
        # by ViewerSampling. Never increase either angular dimension.
        nt = min(len(theta), max(4, self.lmax + 2))
        np_out = min(len(phi), max(8, 2 * (self.lmax + 1)))
        self.theta = np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1])
        self.phi = np.arange(np_out) * (2 * math.pi / np_out)
        self.weights = 2 * math.pi * gw[::-1]

    def project(self, *components):
        if len(components) not in (1, 3):
            raise ValueError("Supply one scalar or three spherical vector components.")
        arrays = [np.asarray(a, dtype=np.float64) for a in components]
        shape = arrays[0].shape
        if any(a.shape != shape or a.shape[-2:] != (len(self.theta_in), len(self.phi_in))
               or not np.isfinite(a).all() for a in arrays):
            raise ValueError("Invalid/nonfinite MagIC fields for spectral projection.")
        fourier = [np.fft.rfft(a, axis=-1) / len(self.phi_in) for a in arrays]
        output = [np.zeros(shape[:-2] + (len(self.theta), len(self.phi) // 2 + 1), complex)
                  for _ in arrays]
        for m in range(0, self.lmax + 1, self.minc):
            y, d, h = harmonic_basis(self.lmax, m, self.theta_in)
            yo, do, ho = harmonic_basis(self.lmax, m, self.theta)
            q = fourier[0][..., m] @ (y * self.weights).T
            output[0][..., m] = q @ yo
            if len(arrays) == 3:
                ell = np.arange(m, self.lmax + 1)
                inverse = np.zeros_like(ell, dtype=float)
                np.divide(1.0, ell * (ell + 1), out=inverse, where=ell > 0)
                ft, fp = fourier[1][..., m], fourier[2][..., m]
                s = (ft @ (d * self.weights).T - 1j * fp @ (h * self.weights).T) * inverse
                t = (-1j * ft @ (h * self.weights).T - fp @ (d * self.weights).T) * inverse
                output[1][..., m] = s @ do + 1j * t @ ho
                output[2][..., m] = 1j * s @ ho - t @ do
        return tuple(np.ascontiguousarray(np.fft.irfft(a * len(self.phi), n=len(self.phi), axis=-1))
                     for a in output)


def truncate_graphic_fields(fields, theta, phi, requested, original_lmax, minc=1):
    info = cutoff_metadata(requested, original_lmax)
    info["original_grid"] = [len(theta), len(phi)]
    if not info["enabled"]:
        info["output_grid"] = info["original_grid"]
        return fields, theta, phi, info
    projector = GraphicProjector(theta, phi, info["lmax_effective"], minc)
    result = {}
    for names in (("ur", "ut", "up"), ("Br", "Bt", "Bp")):
        if all(name in fields for name in names):
            result.update(zip(names, projector.project(*(fields[name] for name in names))))
        elif any(name in fields for name in names):
            raise ValueError(f"Spectral truncation requires all vector components: {names}.")
    for name, values in fields.items():
        if name not in result:
            result[name] = projector.project(values)[0]
    info.update(output_grid=[len(projector.theta), len(projector.phi)],
                method="Gauss/Fourier scalar and vector spherical-harmonic projection of native graphic samples")
    return result, projector.theta, projector.phi, info
