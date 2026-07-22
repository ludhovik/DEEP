#!/usr/bin/env python3
"""Regression checks for the v2 Leeds full-sphere module/converter interface."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULES_PATH = PROJECT_ROOT / "modules.py"
CONVERTER_PATH = Path(__file__).with_name("convert_state_to_viewer.py")


class _FakeSH:
    def __init__(self, lmax: int, mmax: int):
        # SHTns packed ordering used by the Leeds arrays: m-major, l=m..lmax.
        pairs = [(ell, m) for m in range(mmax + 1) for ell in range(m, lmax + 1)]
        self.l = np.asarray([pair[0] for pair in pairs], dtype=int)
        self.m = np.asarray([pair[1] for pair in pairs], dtype=int)
        self.cos_theta = np.cos(np.linspace(0.2, math.pi - 0.2, 6))
        self.records: list[tuple[np.ndarray, ...]] = []

    def set_grid(self, *_args):
        return 6, 12

    def synth(self, *coefficients):
        self.records.append(tuple(np.asarray(value).copy() for value in coefficients))
        zeros = np.zeros((6, 12), dtype=float)
        if len(coefficients) == 1:
            return zeros
        if len(coefficients) == 3:
            return zeros.copy(), zeros.copy(), zeros.copy()
        raise TypeError(f"Unexpected synth argument count: {len(coefficients)}")


class _FakeShtns(ModuleType):
    sht_schmidt = 1
    SHT_NO_CS_PHASE = 2

    def __init__(self):
        super().__init__("shtns")
        self.last: _FakeSH | None = None

    def sht(self, lmax, mmax, *_args):
        self.last = _FakeSH(int(lmax), int(mmax))
        return self.last


def load_python_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fullsphere_grid(n: int = 128) -> np.ndarray:
    j = np.arange(n, dtype=float)
    x = 0.5 * (1.0 - np.cos(np.pi * j / (n - 1)))
    return np.sqrt(x)


def check_leeds_x_derivative(modules) -> None:
    r = fullsphere_grid()
    x = r * r
    D, x_returned = modules.fullsphere_x_derivative_matrix(r)
    np.testing.assert_allclose(x_returned, x, atol=0.0, rtol=0.0)
    for power in range(1, 7):
        numerical = D @ (x**power)
        exact = power * x ** (power - 1)
        np.testing.assert_allclose(numerical, exact, atol=2.0e-9, rtol=0.0)


def check_leeds_projection(modules) -> None:
    r = fullsphere_grid()
    x = r * r
    regular = 1.0 + 0.2 * x - 0.1 * x * x
    for power in (1, 3, 10, 31):
        physical = r**power * regular
        W = modules.leeds_regular_projection_weights(r, power)
        projected = W @ physical
        resolved = np.flatnonzero(r**power >= 1.0e-6)
        first = int(resolved[0]) if resolved.size else len(r) - 1
        np.testing.assert_allclose(projected[first:], regular[first:], atol=3.0e-9, rtol=0.0)
        assert np.max(np.abs(projected)) < 10.0


def check_direct_regular_qst(modules) -> None:
    l = np.asarray([0, 1, 2], dtype=int)
    r = fullsphere_grid(64)
    x = r * r
    G = np.zeros((3, r.size), dtype=np.complex128)
    H = np.zeros_like(G)
    G[1] = 1.0 + 0.3 * x + 0.07 * x * x
    H[1] = 0.2 - 0.1 * x
    G[2] = (0.4 - 0.05 * x) * (1.0 - 0.25j)
    H[2] = (-0.3 + 0.02 * x) * (1.0 + 0.5j)

    Q, S, T = modules.PolTor_to_qst_fullsphere(G, H, l, r)
    gx1 = 0.3 + 0.14 * x
    np.testing.assert_allclose(Q[1], 2.0 * G[1], atol=3.0e-8)
    np.testing.assert_allclose(S[1], 2.0 * G[1] + 2.0 * x * gx1, atol=3.0e-8)
    np.testing.assert_allclose(T[1], r * H[1], atol=3.0e-8)

    gx2 = -0.05 * (1.0 - 0.25j)
    np.testing.assert_allclose(Q[2], 6.0 * r * G[2], atol=3.0e-8)
    np.testing.assert_allclose(S[2], r * (3.0 * G[2] + 2.0 * x * gx2), atol=3.0e-8)
    np.testing.assert_allclose(T[2], r**2 * H[2], atol=3.0e-8)
    assert np.isfinite(Q).all() and np.isfinite(S).all() and np.isfinite(T).all()


def check_spatial_api_and_independent_storage_flags(modules, fake_shtns) -> None:
    lmax = mmax = 3
    sh_template = _FakeSH(lmax, mmax)
    nlm = len(sh_template.l)
    r = fullsphere_grid(32)
    x = r * r
    pol_regular = np.zeros((2, nlm, r.size))
    tor_physical = np.zeros_like(pol_regular)
    idx = int(np.flatnonzero((sh_template.l == 1) & (sh_template.m == 0))[0])
    pol_regular[0, idx] = 1.0 + 0.1 * x
    # Conventional T=r^l H for l=1; the module must project only T back to H.
    tor_physical[0, idx] = r * (0.2 - 0.05 * x)

    result = modules.PolTor_to_spat_fullsphere(
        pol_regular,
        tor_physical,
        r,
        lmax,
        mmax,
        pol_regular_coefficients=True,
        tor_regular_coefficients=False,
        enforce_center=False,
    )
    assert len(result) == 5
    ur, ut, up, theta, phi = result
    assert ur.shape == ut.shape == up.shape == (r.size, theta.size, phi.size)
    assert np.isfinite(ur).all() and np.isfinite(ut).all() and np.isfinite(up).all()
    assert fake_shtns.last is not None


def check_scalar_nom0_api(modules) -> None:
    lmax = mmax = 3
    sh_template = _FakeSH(lmax, mmax)
    nlm = len(sh_template.l)
    r = fullsphere_grid(24)
    scalar = np.zeros((2, nlm, r.size))
    scalar[0, 0, :] = 2.0
    field, theta, phi = modules.SH_to_spat_nom0_fullsphere(
        scalar, r, lmax, mmax, regular_coefficients=True
    )
    assert field.shape == (r.size, theta.size, phi.size)
    np.testing.assert_allclose(field[0], 0.0, atol=0.0, rtol=0.0)


def check_converter_dispatch(converter) -> None:
    assert not hasattr(converter, "fullsphere_regular_poltors_to_spat")
    assert not hasattr(converter, "leeds_regular_projection_weights")
    regular = {
        "representation": converter.REGULAR_RADIAL_REPRESENTATION,
        "power_offset": 2,
    }
    conventional = {
        "representation": converter.CONVENTIONAL_RADIAL_REPRESENTATION,
        "power_offset": 1,
    }
    assert converter.fullsphere_storage_info(regular, "uP") == (True, 2, "stored_regular")
    assert converter.fullsphere_storage_info(conventional, "BP") == (
        False,
        1,
        "legacy_conventional_projected_by_modules",
    )


def main() -> None:
    fake_shtns = _FakeShtns()
    sys.modules["shtns"] = fake_shtns
    modules = load_python_module("viewer_modules_v2", MODULES_PATH)
    converter = load_python_module("convert_state_to_viewer_v2", CONVERTER_PATH)

    assert modules.FULLSPHERE_MODULE_API_VERSION == 2
    check_leeds_x_derivative(modules)
    check_leeds_projection(modules)
    check_direct_regular_qst(modules)
    check_spatial_api_and_independent_storage_flags(modules, fake_shtns)
    check_scalar_nom0_api(modules)
    check_converter_dispatch(converter)
    print("PASS Leeds full-sphere v2 module/converter regression")


if __name__ == "__main__":
    main()
