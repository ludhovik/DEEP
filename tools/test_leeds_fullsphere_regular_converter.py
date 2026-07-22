#!/usr/bin/env python3
"""Regression checks for the Leeds full-sphere converter regularization."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np

MODULE_PATH = Path(__file__).with_name("convert_state_to_viewer.py")
spec = importlib.util.spec_from_file_location("convert_state_to_viewer", MODULE_PATH)
converter = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(converter)


def fullsphere_grid(n: int = 128) -> np.ndarray:
    j = np.arange(n, dtype=float)
    x = 0.5 * (1.0 - np.cos(np.pi * j / (n - 1)))
    return np.sqrt(x)


def check_leeds_x_derivative() -> None:
    r = fullsphere_grid()
    x = r * r
    D, _, method = converter.fullsphere_x_derivative_matrix(r)
    assert method == "leeds_local_finite_difference_x_KL3"
    for power in range(1, 7):
        numerical = D @ (x**power)
        exact = power * x ** (power - 1)
        np.testing.assert_allclose(numerical, exact, atol=2.0e-9, rtol=0.0)


def check_leeds_projection() -> None:
    r = fullsphere_grid()
    x = r * r
    regular = 1.0 + 0.2 * x - 0.1 * x * x
    for power in (1, 3, 10, 31):
        physical = r**power * regular
        W = converter.leeds_regular_projection_weights(r, power)
        projected = W @ physical
        resolved = np.flatnonzero(r**power >= 1.0e-6)
        first = int(resolved[0]) if resolved.size else len(r) - 1
        np.testing.assert_allclose(projected[first:], regular[first:], atol=3.0e-9, rtol=0.0)
        assert np.max(np.abs(projected)) < 10.0


class _FakeSH:
    def __init__(self, lmax: int, mmax: int):
        self.l = np.array([ell for m in range(mmax + 1) for ell in range(m, lmax + 1)])
        self.m = np.array([m for m in range(mmax + 1) for _ell in range(m, lmax + 1)])
        self.cos_theta = np.cos(np.linspace(0.2, math.pi - 0.2, 6))
        self.records: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []

    def set_grid(self):
        return 6, 12

    def synth(self, q, s, t):
        self.records.append((np.asarray(q).copy(), np.asarray(s).copy(), np.asarray(t).copy()))
        zeros = np.zeros((6, 12), dtype=float)
        return zeros.copy(), zeros.copy(), zeros.copy()


class _FakeShtns:
    sht_schmidt = 1
    SHT_NO_CS_PHASE = 2

    def __init__(self):
        self.last = None

    def sht(self, lmax, mmax, *_args):
        self.last = _FakeSH(int(lmax), int(mmax))
        return self.last


def check_direct_regular_qst() -> None:
    lmax = mmax = 5
    fake = _FakeShtns()
    modules = SimpleNamespace(shtns=fake)
    sh = _FakeSH(lmax, mmax)
    nlm = len(sh.l)
    r = fullsphere_grid(64)
    x = r * r
    pol = np.zeros((2, nlm, len(r)))
    tor = np.zeros_like(pol)

    # Analytic regular coefficient for an l=1,m=0 mode.
    idx = int(np.flatnonzero((sh.l == 1) & (sh.m == 0))[0])
    G = 1.0 + 0.3 * x + 0.07 * x * x
    H = 0.2 - 0.1 * x
    pol[0, idx] = G
    tor[0, idx] = H

    converter.fullsphere_regular_poltors_to_spat(pol, tor, r, lmax, mmax, modules)
    assert fake.last is not None
    gx = 0.3 + 0.14 * x
    for ir, rr in enumerate(r):
        q, s, t = fake.last.records[ir]
        np.testing.assert_allclose(q[idx].real, 2.0 * G[ir], atol=3.0e-8)
        np.testing.assert_allclose(s[idx].real, -(2.0 * G[ir] + 2.0 * x[ir] * gx[ir]), atol=3.0e-8)
        np.testing.assert_allclose(t[idx].real, rr * H[ir], atol=3.0e-8)
        assert np.isfinite(q).all() and np.isfinite(s).all() and np.isfinite(t).all()


def main() -> None:
    check_leeds_x_derivative()
    check_leeds_projection()
    check_direct_regular_qst()
    print("PASS Leeds full-sphere converter regularization")


if __name__ == "__main__":
    main()
