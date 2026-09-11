#!/usr/bin/env python3
from __future__ import annotations

import ast
from contextlib import ExitStack
import importlib.util
import math
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LEEDS_PATH = ROOT / "tools" / "convert_leeds_to_viewer.py"
XSHELLS_PATH = ROOT / "tools" / "convert_xshells_to_viewer.py"
MAGIC_PATH = ROOT / "tools" / "convert_magic_to_viewer.py"
MODULES_PATH = ROOT / "modules.py"


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def literal_output_names(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    output_names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "register"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            output_names.add(node.args[0].value)
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    output_names.add(key.value)
    return output_names


class ConverterPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.leeds = load_module("converter_leeds_test", LEEDS_PATH)

        # modules.py imports shtns at module import time. The curl and geometry
        # tests do not need spectral transforms, so a minimal stub is sufficient.
        sys.modules.setdefault("shtns", types.ModuleType("shtns"))
        sys.modules.setdefault("h5py", types.ModuleType("h5py"))
        sys.modules.setdefault("pyxshells", types.ModuleType("pyxshells"))
        cls.modules = load_module("converter_modules_test", MODULES_PATH)
        cls.xshells = load_module("converter_xshells_test", XSHELLS_PATH)
        cls.magic = load_module("converter_magic_test", MAGIC_PATH)

    @staticmethod
    def dipole_grid(r, theta, phi):
        R, T, _ = np.meshgrid(r, theta, phi, indexing="ij")
        return 2.0 * np.cos(T) / R**3, np.sin(T) / R**3, np.zeros_like(R)

    @staticmethod
    def fake_dipole_sht(theta, phi):
        class FakeDipoleSht:
            l = np.array([1], dtype=np.int64)
            m = np.array([0], dtype=np.int64)
            cos_theta = np.cos(theta)

            def set_grid(self):
                return len(theta), len(phi)

            def analys(self, _field):
                # B_r(R) = 2 cos(theta), so Q_10(R) = 2 in this test basis.
                return np.array([2.0 + 0.0j])

            def synth(self, qlm, slm=None, tlm=None):
                q = float(np.real(np.asarray(qlm)[0]))
                br = q * np.cos(theta)[:, None] * np.ones((1, len(phi)))
                if slm is None:
                    return br
                # SHTns: B_theta = S_lm * partial_theta Y_lm, with Y_10=cos(theta).
                s = float(np.real(np.asarray(slm)[0]))
                bt = -s * np.sin(theta)[:, None] * np.ones((1, len(phi)))
                bp = np.zeros_like(br)
                return br, bt, bp

        return FakeDipoleSht()

    def geometry(self, r, up, ut, bp, bt, **kwargs):
        defaults = dict(
            center_tolerance=1.0e-12,
            magnetic_tolerance=1.0e-300,
            flow_zero_relative_tolerance=1.0e-10,
            flow_zero_absolute_tolerance=0.0,
            minimum_inner_core_points=2,
            minimum_inner_core_radius_fraction=0.02,
            requested_geometry="auto",
            fluid_inner_radius=None,
        )
        defaults.update(kwargs)
        return self.leeds.infer_leeds_geometry(r, up, ut, bp, bt, **defaults)

    def test_leeds_full_sphere_geometry(self):
        r = np.linspace(0.0, 1.0, 11)
        u = np.zeros((2, 4, r.size))
        u[0, 1, 1:] = 1.0
        b = np.ones_like(u)
        g = self.geometry(r, u, u * 0.2, b, b * 0.3)
        self.assertEqual(g["physical_geometry"], "full_fluid_sphere")
        self.assertTrue(g["transform_fullsphere"])
        self.assertFalse(g["has_inner_core"])

    def test_leeds_conducting_inner_core_geometry(self):
        r = np.linspace(0.0, 1.0, 11)
        u = np.zeros((2, 4, r.size))
        # Inner solid including a no-slip ICB at r=0.4; flow starts at r=0.5.
        u[0, 1, 5:] = 2.0
        b = np.ones_like(u)
        g = self.geometry(r, u, u * 0.1, b, b * 0.4)
        self.assertEqual(g["physical_geometry"], "spherical_shell_conducting_inner_core")
        self.assertTrue(g["transform_fullsphere"])
        self.assertTrue(g["has_inner_core"])
        self.assertTrue(g["has_conducting_inner_core"])
        self.assertEqual(g["fluid_inner_index"], 4)
        self.assertAlmostEqual(g["r_icb"], 0.4)

    def test_leeds_shell_grid_geometry(self):
        r = np.linspace(0.35, 1.0, 9)
        u = np.ones((2, 3, r.size))
        b = np.ones_like(u)
        g = self.geometry(r, u, u, b, b)
        self.assertEqual(g["physical_geometry"], "spherical_shell")
        self.assertFalse(g["transform_fullsphere"])
        self.assertTrue(g["has_inner_core"])
        self.assertFalse(g["has_conducting_inner_core"])
        self.assertAlmostEqual(g["r_icb"], 0.35)

    def test_regular_central_decay_is_not_inner_core(self):
        r = np.linspace(0.0, 1.0, 21)
        u = np.zeros((2, 3, r.size))
        # A regular full-sphere field can vanish exactly at r=0 and become
        # non-zero immediately outside it. This must not be called a solid core.
        u[0, 1, 1:] = r[1:] ** 3
        b = np.ones_like(u)
        g = self.geometry(r, u, u, b, b)
        self.assertEqual(g["physical_geometry"], "full_fluid_sphere")

    def test_emf_cross_product(self):
        shape = (3, 4, 5)
        one = np.ones(shape)
        zero = np.zeros(shape)
        # e_theta x e_phi = e_r
        er, et, ep = self.leeds.compute_emf(zero, one, zero, zero, zero, one)
        self.assertTrue(np.allclose(er, 1.0))
        self.assertTrue(np.allclose(et, 0.0))
        self.assertTrue(np.allclose(ep, 0.0))

    def test_vector_curl_solid_rotation(self):
        r = np.linspace(0.2, 1.0, 17)
        theta = np.linspace(0.15, math.pi - 0.15, 31)
        phi = np.linspace(0.0, 2.0 * math.pi, 32, endpoint=False)
        R, T, P = np.meshgrid(r, theta, phi, indexing="ij")
        ar = np.zeros_like(R)
        at = np.zeros_like(R)
        ap = R * np.sin(T)  # Omega x r for Omega=1 along z
        cr, ct, cp = self.modules.curl_spat(ar, at, ap, r, theta, phi)
        expected_r = 2.0 * np.cos(T)
        expected_t = -2.0 * np.sin(T)
        # Ignore first/last theta lines where one-sided finite differences dominate.
        sl = (slice(None), slice(1, -1), slice(None))
        self.assertLess(float(np.max(np.abs(cr[sl] - expected_r[sl]))), 2.0e-2)
        self.assertLess(float(np.max(np.abs(ct[sl] - expected_t[sl]))), 2.0e-12)
        self.assertLess(float(np.max(np.abs(cp[sl]))), 2.0e-12)

    def test_modules_curl_matches_independent_reference(self):
        r = np.linspace(0.25, 1.0, 30)
        theta = np.linspace(0.12, math.pi - 0.12, 40)
        phi = np.linspace(0.0, 2.0 * math.pi, 48, endpoint=False)
        R, T, P = np.meshgrid(r, theta, phi, indexing="ij")
        ar = R**2 * np.sin(T) * np.cos(2.0 * P)
        at = R * np.cos(T) * np.sin(P)
        ap = R**3 * np.sin(T)**2 * np.cos(P)

        actual = self.modules.curl_spat(ar, at, ap, r, theta, phi)
        reference = self.leeds.compute_induction_from_emf(ar, at, ap, r, theta, phi)
        interior = (slice(1, -1), slice(1, -1), slice(1, -1))
        for component_actual, component_reference in zip(actual, reference):
            error = np.max(np.abs(component_actual[interior] - component_reference[interior]))
            self.assertLess(float(error), 2.0e-13)

    def test_common_output_contract(self):
        leeds_names = literal_output_names(LEEDS_PATH)
        xshells_names = literal_output_names(XSHELLS_PATH)
        magic_names = literal_output_names(MAGIC_PATH)
        required = {
            "ur", "ut", "up", "us", "uz", "Uabs", "helicity",
            "Br", "Bt", "Bp", "Babs",
            "T", "C", "T_nom0", "C_nom0",
            "N2", "N2_nom0",
            "EMFr", "EMFt", "EMFp", "EMFabs",
            "EMFr_fluct", "EMFt_fluct", "EMFp_fluct",
            "Ir", "It", "Ip", "Iz", "Iabs",
        }
        self.assertTrue(required <= leeds_names, sorted(required - leeds_names))
        self.assertTrue(required <= xshells_names, sorted(required - xshells_names))
        self.assertTrue(required <= magic_names, sorted(required - magic_names))

    def test_cli_flags_present_in_both(self):
        for path in (LEEDS_PATH, XSHELLS_PATH, MAGIC_PATH):
            text = path.read_text(encoding="utf-8")
            self.assertIn('"--emf"', text)
            self.assertIn('"--induction"', text)
            self.assertIn('"--geometry"', text)
            self.assertIn('"--fluid-inner-radius"', text)
            self.assertIn('"dynamo-three-viewer-v2-common"', text)

    def test_magic_layout_unfolds_symmetry_and_reverses_radius(self):
        graph = types.SimpleNamespace(
            radius=np.array([1.0, 0.7, 0.35]),
            colatitude=np.array([2.5, 1.5, 0.5]),
            minc=2,
        )
        base = np.arange(4 * 3 * 3, dtype=np.float64).reshape(4, 3, 3)
        graph.vr = base
        graph.vtheta = base + 100.0
        graph.vphi = base + 200.0
        adapted = self.magic.adapt_graph(graph)
        self.assertTrue(np.allclose(adapted["r_shell"], [0.35, 0.7, 1.0]))
        self.assertTrue(np.allclose(adapted["theta"], [0.5, 1.5, 2.5]))
        self.assertEqual(adapted["fields"]["ur"].shape, (3, 3, 8))
        self.assertTrue(np.array_equal(
            adapted["fields"]["ur"][:, :, :4],
            adapted["fields"]["ur"][:, :, 4:],
        ))
        self.assertEqual(adapted["fields"]["ur"][0, 0, 0], base[0, 2, 2])

    def test_magic_surface_transform_recovers_low_degree_field(self):
        theta = np.arccos(np.polynomial.legendre.leggauss(24)[0][::-1])
        phi = np.linspace(0.0, 2.0 * math.pi, 48, endpoint=False)
        field = 0.7 * np.cos(theta)[:, None] + 0.2 * np.sin(theta)[:, None] * np.cos(phi)[None, :]
        recovered = self.magic.truncated_surface(field, theta, phi, 1)
        self.assertLess(float(np.max(np.abs(recovered - field))), 2.0e-12)

    def test_exterior_potential_dipole_is_correct_in_all_three_converters(self):
        theta = np.arccos(np.polynomial.legendre.leggauss(64)[0][::-1])
        phi = np.linspace(0.0, 2.0 * math.pi, 48, endpoint=False)
        r_ext = np.array([1.0, 1.5, 2.0])
        R, T, _ = np.meshgrid(r_ext, theta, phi, indexing="ij")
        expected_br = 2.0 * np.cos(T) / R**3
        expected_bt = np.sin(T) / R**3

        # MagIC analyses physical CMB Br directly and differentiates the
        # exterior scalar potential in physical angular space.
        br_cmb = 2.0 * np.cos(theta)[:, None] * np.ones((1, len(phi)))
        br, bt, bp = self.magic.exterior_potential_field(
            br_cmb, theta, phi, 1.0, r_ext, 1
        )
        self.assertLess(float(np.max(np.abs(br - expected_br))), 1.0e-11)
        self.assertLess(float(np.max(np.abs(bt[:, 1:-1] - expected_bt[:, 1:-1]))), 5.0e-4)
        self.assertLess(float(np.max(np.abs(bp))), 1.0e-12)

        # XSHELLS supplies Q_lm at the CMB.  The documented SHTns relation
        # S_lm=-Q_lm/(l+1) must recover the same axial dipole.
        sht = self.fake_dipole_sht(theta, phi)
        br, bt, bp = self.xshells.external_potential_field_from_cmb_br(
            sht, br_cmb, 1.0, r_ext
        )
        self.assertLess(float(np.max(np.abs(br - expected_br))), 1.0e-12)
        self.assertLess(float(np.max(np.abs(bt - expected_bt))), 1.0e-12)
        self.assertLess(float(np.max(np.abs(bp))), 1.0e-12)

        # Leeds supplies the poloidal coefficient P_10(R)=1, for which
        # Q_10=2 and S_10=-1 at R=1.
        fake_sht = self.fake_dipole_sht(theta, phi)
        fake_shtns_module = types.SimpleNamespace(
            sht_schmidt=0,
            SHT_NO_CS_PHASE=0,
            sht=lambda *_args, **_kwargs: fake_sht,
        )
        fake_modules = types.SimpleNamespace(
            shtns=fake_shtns_module,
            lsd_to_shtns=lambda _coeff, _sht: np.array([[1.0 + 0.0j]]),
        )
        br, bt, bp, _, _ = self.leeds.external_potential_field_from_BP(
            np.zeros((2, 1, 2)), np.array([0.35, 1.0]), r_ext, 1, 0, fake_modules
        )
        self.assertLess(float(np.max(np.abs(br - expected_br))), 1.0e-12)
        self.assertLess(float(np.max(np.abs(bt - expected_bt))), 1.0e-12)
        self.assertLess(float(np.max(np.abs(bp))), 1.0e-12)

    def test_exterior_dipole_trace_obeys_field_line_equation_and_polarity(self):
        r_ext = np.linspace(1.0, 2.5, 151)
        theta = np.linspace(0.02, math.pi - 0.02, 181)
        phi = np.linspace(0.0, 2.0 * math.pi, 24, endpoint=False)
        br, bt, bp = self.dipole_grid(r_ext, theta, phi)
        seed_records = []
        for index, theta0 in enumerate((math.pi / 4.0, 3.0 * math.pi / 4.0)):
            cmb_seed = self.leeds.sph_to_cart(1.0, theta0, 0.0)
            polarity = 1 if math.cos(theta0) > 0.0 else -1
            seed_records.append({
                "line_id": f"dipole-{index}",
                "cmb_seed": cmb_seed.tolist(),
                "cmb_seed_source": "traced_cmb_intersection",
                "cmb_br_seed": 2.0 * math.cos(theta0),
                "polarity": polarity,
            })

        lines = self.leeds.compute_external_field_lines_from_cmb(
            br, bt, bp, r_ext, theta, phi,
            ntheta_seed=1, nphi_seed=1, max_steps=3000,
            step_size=0.005, min_points=8, closed_only=True,
            seed_records=seed_records,
        )
        self.assertEqual(len(lines), 2)
        by_id = {line["line_id"]: line for line in lines}

        for index, expected_polarity in enumerate((1, -1)):
            line = by_id[f"dipole-{index}"]
            points = np.asarray(line["points"], dtype=np.float64)
            self.assertTrue(np.array_equal(points[0], np.asarray(line["cmb_seed"])))
            self.assertEqual(line["polarity"], expected_polarity)
            self.assertEqual(line["direction"], float(expected_polarity))
            self.assertEqual(line["status"], "returned_cmb")
            self.assertLess(line["end_r_error"], 1.0e-12)
            self.assertGreater(
                self.leeds.radius_of(points[1]),
                self.leeds.radius_of(points[0]),
            )

            _, end_theta, end_phi = self.leeds.cart_to_sph(points[-1])
            end_br = self.leeds.interp_spherical_field(
                br, r_ext, theta, phi, 1.0, end_theta, end_phi
            )
            self.assertEqual(1 if end_br > 0.0 else -1, -expected_polarity)

            # For an axial dipole, every field line satisfies r/sin(theta)^2=L.
            invariant = []
            for point in points:
                radius, colatitude, _ = self.leeds.cart_to_sph(point)
                invariant.append(radius / math.sin(colatitude) ** 2)
            relative_spread = float(np.ptp(invariant) / np.mean(invariant))
            self.assertLess(relative_spread, 2.0e-5)

    def test_paired_exterior_seed_is_actual_shell_cmb_intersection(self):
        r_shell = np.linspace(0.35, 1.0, 131)
        r_ext = np.linspace(1.0, 2.5, 151)
        theta = np.linspace(0.02, math.pi - 0.02, 181)
        phi = np.linspace(0.0, 2.0 * math.pi, 24, endpoint=False)
        br_shell, bt_shell, bp_shell = self.dipole_grid(r_shell, theta, phi)
        br_ext, bt_ext, bp_ext = self.dipole_grid(r_ext, theta, phi)

        shell_lines = self.leeds.compute_shell_field_lines_from_cmb(
            br_shell, bt_shell, bp_shell, r_shell, theta, phi,
            ntheta_seed=5, nphi_seed=1, max_steps=3000,
            step_size=0.005, seed_offset=0.0075,
        )
        exterior_lines = self.leeds.compute_external_field_lines_from_cmb(
            br_ext, bt_ext, bp_ext, r_ext, theta, phi,
            ntheta_seed=5, nphi_seed=1, max_steps=3000,
            step_size=0.005, closed_only=True, seed_records=shell_lines,
        )
        self.assertGreater(len(exterior_lines), 0)
        shell_by_id = {line["line_id"]: line for line in shell_lines}
        for exterior in exterior_lines:
            shell = shell_by_id[exterior["paired_shell_line_id"]]
            self.assertEqual(shell["cmb_seed_source"], "traced_cmb_intersection")
            self.assertTrue(np.array_equal(
                np.asarray(exterior["points"][0]),
                np.asarray(shell["cmb_seed"]),
            ))
            self.assertTrue(exterior["polarity_matches_source"])
            self.assertEqual(exterior["line_id"], shell["line_id"])

    @staticmethod
    def fake_magic_graph():
        nr, ntheta, nphi = 5, 8, 12
        radius = np.linspace(1.0, 0.35, nr)
        theta = np.arccos(np.polynomial.legendre.leggauss(ntheta)[0][::-1])
        phi = np.linspace(0.0, 2.0 * math.pi, nphi, endpoint=False)
        P, T, R = np.meshgrid(phi, theta, radius, indexing="ij")
        return types.SimpleNamespace(
            radius=radius,
            colatitude=theta,
            minc=1,
            vr=R * np.sin(T) * np.cos(P),
            vtheta=R * np.cos(T) * np.cos(P),
            vphi=R * np.sin(P),
            entropy=R * np.cos(T),
            xi=0.1 * R * np.sin(T) * np.sin(P),
            Br=2.0 * R * np.cos(T),
            Btheta=R * np.sin(T),
            Bphi=0.1 * R * np.sin(P),
            time=1.25,
            ek=1.0e-4,
            pr=1.0,
            sc=1.0,
            ra=1.0e6,
            raxi=0.0,
            prmag=2.0,
            radratio=0.35,
        )

    def test_magic_end_to_end_binary_contract(self):
        graph = self.fake_magic_graph()
        args = self.magic.build_arg_parser().parse_args([
            "--graph", "G_1.test", "--skip-field-lines", "--no-earth-br",
            "--no-gradients", "--no-m0-fields",
        ])
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder)
            with mock.patch.object(self.magic, "load_graph", return_value=graph):
                metadata = self.magic.convert_graph(pathlib.Path("G_1.test"), output, args)
            expected_size = metadata["nr"] * metadata["ntheta"] * metadata["nphi"] * 4
            self.assertEqual(metadata["viewer_field_contract"], "dynamo-three-viewer-v2-common")
            self.assertIn("T", metadata["fields"])
            self.assertIn("C", metadata["fields"])
            for canonical in ("T_nom0", "C_nom0"):
                self.assertNotIn(canonical, metadata["fields"])
            for filename in metadata["fields"].values():
                self.assertEqual((output / filename).stat().st_size, expected_size)

    def test_all_converter_cutoffs_default_to_full_resolution_and_reject_negative_values(self):
        import contextlib, io
        for converter in (self.leeds, self.xshells, self.magic):
            parser = converter.build_arg_parser()
            self.assertEqual(parser.parse_args(["--folder", "unused"]).spectral_lmax, 0)
            self.assertEqual(parser.parse_args(["--folder", "unused", "--spectral-lmax", "128"]).spectral_lmax, 128)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args(["--folder", "unused", "--spectral-lmax", "-1"])

    @staticmethod
    def spectral_layout(lmax, mmax, mres=1, *unused):
        pairs = [(l, m) for m in range(0, mmax*mres+1, mres) for l in range(m, lmax+1)]
        return types.SimpleNamespace(lmax=lmax, mmax=mmax, mres=mres,
                                     l=np.array([p[0] for p in pairs]), m=np.array([p[1] for p in pairs]))

    def test_leeds_cutoff_preserves_retained_coefficients_and_default_full_representation(self):
        backend = types.SimpleNamespace(shtns=types.SimpleNamespace(
            sht=self.spectral_layout, sht_schmidt=0, SHT_NO_CS_PHASE=0))
        layout = self.spectral_layout(8, 8)
        coefficients = np.arange(2*len(layout.l)*5).reshape(2, len(layout.l), 5)
        unchanged = self.leeds.apply_spectral_lmax_to_state(
            *([coefficients]*6), 8, 8, 0, backend)
        self.assertIs(unchanged[0], coefficients)
        self.assertEqual(unchanged[6:8], (8, 8))
        result = self.leeds.apply_spectral_lmax_to_state(
            *([coefficients]*6), 8, 8, 3, backend)
        for field in result[:6]:
            np.testing.assert_array_equal(field, coefficients[:, layout.l <= 3])
        self.assertEqual(result[6:8], (3, 3))

    def test_xshells_cutoff_preserves_radial_domains_ghost_data_and_boundary_conditions(self):
        layout_factory = self.spectral_layout
        class Field:
            components = 2
            def __init__(self, grid, sht):
                self.grid, self.sht = grid, sht
                self.lmax, self.mmax, self.mres = sht.lmax, sht.mmax, sht.mres
                self.l, self.m = sht.l, sht.m
            def alloc(self, irs, ire, dtype=complex):
                self.irs, self.ire = irs, ire
                self.data = np.zeros((ire-irs+3, self.components, len(self.sht.l)), dtype=dtype)
            def copy_data_from(self, source):
                raise AssertionError("Do not use pyxshells 2.8's NumPy 2-incompatible copy helper")
        class Scalar(Field):
            components = 1
        for mres in (1, 3):
            sht = layout_factory(12, 12//mres, mres)
            loaded = {}
            for name, cls, inner in (("magnetic",Field,0), ("velocity",Field,2), ("temperature",Scalar,2)):
                native = cls(types.SimpleNamespace(r=np.linspace(0,1,8)), sht)
                native.alloc(inner, 7)
                native.data[:] = np.arange(native.data.size).reshape(native.data.shape) + 1j
                native.BC, native.curl, native.time = [2,3], 1, 1.25
                loaded[name] = native
            unchanged, info = self.xshells.truncate_xshells_fields(loaded, "magnetic", 0)
            self.assertIs(unchanged, loaded)
            with mock.patch.object(self.xshells.pyxshells, "shtns", types.SimpleNamespace(sht=layout_factory), create=True):
                result, info = self.xshells.truncate_xshells_fields(loaded, "magnetic", 4)
            self.assertEqual(info["mmax_effective"], (4//mres)*mres)
            for name, target in result.items():
                native = loaded[name]
                np.testing.assert_array_equal(target.data, native.data[..., sht.l <= 4])
                self.assertIs(target.grid, native.grid)
                self.assertEqual((target.irs,target.ire,target.BC,target.time,target.curl),
                                 (native.irs,native.ire,native.BC,native.time,native.curl))

    def test_magic_truncation_reduces_every_volume_file_and_retains_scalar_mean(self):
        from scipy.special import sph_harm_y
        from tools.viewer_bundle import validate_bundle
        graph = self.fake_magic_graph()
        graph.l_max = 20
        graph.colatitude = np.arccos(np.polynomial.legendre.leggauss(32)[0][::-1])
        phi = np.arange(64)*2*math.pi/64
        P,T,R = np.meshgrid(phi, graph.colatitude, graph.radius, indexing="ij")
        graph.vr, graph.vtheta, graph.vphi = R*np.cos(T), -R*np.sin(T), 0*R
        graph.Br, graph.Btheta, graph.Bphi = 2*np.cos(T)/R**3, np.sin(T)/R**3, 0*R
        graph.entropy = 3 + R*np.cos(T) + .2*sph_harm_y(12,3,T,P).real
        graph.xi = .1*R
        outputs = []
        with tempfile.TemporaryDirectory() as folder:
            for cutoff in (0, 4):
                root = pathlib.Path(folder)/str(cutoff)
                root.mkdir()
                args = self.magic.build_arg_parser().parse_args([
                    "--graph", "G_1.test", "--spectral-lmax", str(cutoff), "--skip-field-lines",
                    "--emf", "--induction", "--cmb-br-ltrunc", "3", "--earth-br-ltrunc", "3",
                ])
                with mock.patch.object(self.magic, "load_graph", return_value=graph):
                    meta = self.magic.convert_graph(pathlib.Path("G_1.test"), root, args)
                validate_bundle(root)
                outputs.append((root,meta))
            native, cut = outputs
            self.assertEqual(set(native[1]["fields"]), set(cut[1]["fields"]))
            self.assertEqual(cut[1]["nr"], native[1]["nr"])
            self.assertLess(cut[1]["ntheta"]*cut[1]["nphi"], native[1]["ntheta"]*native[1]["nphi"])
            for name, file in cut[1]["fields"].items():
                self.assertLess((cut[0]/file).stat().st_size, (native[0]/native[1]["fields"][name]).stat().st_size)
            import json
            coordinates = json.loads((cut[0]/"coordinates.json").read_text())
            expected = 3 + np.asarray(coordinates["r"])[:,None,None]*np.cos(coordinates["theta"])[None,:,None]
            values = np.fromfile(cut[0]/cut[1]["fields"]["T"], dtype="<f4").reshape(cut[1]["nr"],cut[1]["ntheta"],cut[1]["nphi"])
            np.testing.assert_allclose(values, np.broadcast_to(expected,values.shape), atol=3e-7)

    def test_magic_downsampled_bundle_passes_publication_validation(self):
        from tools.viewer_bundle import staged_bundle_output, validate_bundle
        graph = self.fake_magic_graph()
        args = self.magic.build_arg_parser().parse_args([
            "--graph", "G_1.test", "--skip-field-lines", "--downsample-r", "3",
            "--downsample-theta", "3", "--downsample-phi", "5",
            "--cmb-br-ltrunc", "2", "--earth-br-ltrunc", "2",
        ])
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder) / "bundle"
            with staged_bundle_output(output) as stage, mock.patch.object(self.magic, "load_graph", return_value=graph):
                metadata = self.magic.convert_graph(pathlib.Path("G_1.test"), stage, args)
            validate_bundle(output)
            self.assertEqual(metadata["nphi"], 3)
            self.assertTrue(metadata["surface_fields"])
            self.assertFalse({"Cnol0", "Compnol0"} & metadata["fields"].keys())
            self.assertAlmostEqual(metadata["r_outer"], 1.0)
            self.assertAlmostEqual(metadata["r_inner"], 0.35)

    def test_magic_large_exterior_domain_exports_paired_lines_and_diagnostics(self):
        import json
        from tools.viewer_bundle import validate_bundle
        graph = self.fake_magic_graph()
        args = self.magic.build_arg_parser().parse_args([
            "--graph", "G_1.test", "--field-line-mode", "both",
            "--external-rmax", "40", "--line-seed-theta", "4", "--line-seed-phi", "4",
            "--no-earth-br", "--no-gradients", "--no-m0-fields",
        ])
        with tempfile.TemporaryDirectory() as folder:
            output = pathlib.Path(folder)
            with mock.patch.object(self.magic, "load_graph", return_value=graph):
                metadata = self.magic.convert_graph(pathlib.Path("G_1.test"), output, args)
            validate_bundle(output)
            diagnostics = metadata["field_lines"]
            counts = diagnostics["exterior_seed_counts"]
            self.assertEqual(diagnostics["exterior_sampling"]["rmax"], 40.0)
            self.assertEqual(counts["input"], diagnostics["counts"]["shell_seed_lines"])
            self.assertEqual(counts["traced"], sum(diagnostics["exterior_status_counts"].values()))
            self.assertEqual(counts["input"], counts["traced"] + sum(counts["skipped"].values()))
            exterior = json.loads((output / diagnostics["exterior"]).read_text())
            shell = {line["line_id"]: line for line in json.loads((output / diagnostics["shell"]).read_text())}
            self.assertGreater(len(exterior), 0)
            self.assertEqual(len(exterior), counts["retained"])
            for line in exterior:
                self.assertEqual(line["status"], "returned_cmb")
                self.assertEqual(line["points"][0], shell[line["paired_shell_line_id"]]["cmb_seed"])
                self.assertLess(line["end_r_error"], 1e-12)
                self.assertEqual(line["return_connection_status"], "connected")
                branch = shell[line["paired_shell_return_line_id"]]
                self.assertEqual(line["points"][-1], branch["points"][0])
                self.assertEqual(line["direction"], branch["direction"])
                self.assertEqual(branch["line_group_id"], line["line_group_id"])
            self.assertEqual(diagnostics["counts"]["shell_return_branches"], len(exterior))
            self.assertEqual(diagnostics["counts"]["shell"], len(shell))
            published = json.loads((output / "metadata.json").read_text())
            self.assertEqual(published["field_lines"], diagnostics)

    def test_removed_diagnostics_are_not_exported(self):
        for path in (LEEDS_PATH, XSHELLS_PATH, MAGIC_PATH):
            self.assertFalse({"Cnol0", "Compnol0"} & literal_output_names(path))

    def test_leeds_exterior_coordinates_match_shtns(self):
        theta = np.linspace(0.1, math.pi - 0.1, 24)
        phi = np.linspace(0, 2 * math.pi, 48, endpoint=False)
        sh = self.fake_dipole_sht(theta, phi)
        backend = types.SimpleNamespace(
            shtns=types.SimpleNamespace(sht_schmidt=0, SHT_NO_CS_PHASE=0, sht=lambda *a: sh),
            lsd_to_shtns=lambda *a: np.array([[1 + 0j]]),
        )
        result = self.leeds.external_potential_field_from_BP(
            np.zeros((2, 1, 2)), np.array([0.35, 1.0]), np.array([1.0]), 1, 0, backend
        )
        np.testing.assert_array_equal(result[-1], phi)
        self.assertNotIn("nphi+2", MODULES_PATH.read_text())
        self.assertNotIn("nphi + 2", MODULES_PATH.read_text())

    def test_magic_exterior_nonaxisymmetric_harmonic(self):
        theta = np.arccos(np.polynomial.legendre.leggauss(24)[0][::-1])
        phi = np.linspace(0, 2 * math.pi, 48, endpoint=False)
        m = 8
        cmb = np.sin(theta)[:, None]**m * np.cos(m * phi)[None, :]
        r = np.array([1.0, 1.3, 2.0])
        br, bt, bp = self.magic.exterior_potential_field(cmb, theta, phi, 1.0, r, m)
        decay = r[:, None, None] ** (-m - 2)
        expected_t = -m / (m + 1) * np.sin(theta)[:, None]**(m - 1) * np.cos(theta)[:, None] * np.cos(m * phi)[None, :]
        expected_p = m / (m + 1) * np.sin(theta)[:, None]**(m - 1) * np.sin(m * phi)[None, :]
        for actual, expected in ((br, cmb * decay), (bt, expected_t * decay), (bp, expected_p * decay)):
            self.assertLess(np.linalg.norm(actual - expected) / np.linalg.norm(expected), 1e-11)

    def test_magic_analytic_gradient_at_poles(self):
        theta = np.array([0.0, 0.3, math.pi / 2, math.pi])
        phi = np.linspace(0, 2 * math.pi, 16, endpoint=False)
        # V=sin(theta) cos(phi)=-2 sqrt(2pi/3) Re(Y_11).
        gt, gp = self.magic.synthesize_angular_gradient({(1, 1): -math.sqrt(2 * math.pi / 3)}, theta, phi)
        np.testing.assert_allclose(gt, np.cos(theta)[:, None] * np.cos(phi)[None, :], atol=2e-14)
        np.testing.assert_allclose(gp, -np.ones((len(theta), 1)) * np.sin(phi)[None, :], atol=2e-14)

    def test_magic_exact_graph_number(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root / "G_1.test").touch()
            (root / "G_10.test").touch()
            self.assertEqual(self.magic.discover_graph(root, None, 1, False).name, "G_1.test")

    def test_sampling_preserves_boundaries_and_filters_longitude(self):
        r = np.array([0.0, 0.35, 0.7, 1.0])
        theta = np.linspace(0.0, math.pi, 17)
        phi = np.linspace(0.0, 2 * math.pi, 48, endpoint=False)
        sampling = self.leeds.ViewerSampling(r, theta, phi, 2, 2, 5, required_radii=[0.35])
        self.assertEqual(sampling.r.tolist(), [0.0, 0.35, 0.7, 1.0])
        self.assertEqual(sampling.theta[[0, -1]].tolist(), [0.0, math.pi])
        np.testing.assert_allclose(np.diff(sampling.phi), 2 * math.pi / len(sampling.phi))
        field = np.broadcast_to(2 + np.cos(phi)[None, None, :] + np.cos(8 * phi)[None, None, :], (4, 17, 48))
        result = sampling.volume(field)
        expected = np.broadcast_to(2 + np.cos(sampling.phi), result.shape)
        np.testing.assert_allclose(result, expected, atol=2e-14)
        np.testing.assert_allclose(sampling.angular(field[-1]), result[-1], atol=2e-14)

    def test_sampling_inserts_required_interior_boundary(self):
        r = np.array([0.0, 0.4, 0.7, 1.0])
        theta = np.linspace(0, math.pi, 8)
        phi = np.linspace(0, 2 * math.pi, 12, endpoint=False)
        sampling = self.leeds.ViewerSampling(r, theta, phi, 3, required_radii=[0.35])
        np.testing.assert_allclose(sampling.r, [0, 0.35, 1])
        np.testing.assert_allclose(sampling.radial(2 * r), 2 * sampling.r)

    def test_theta_lowpass_and_nonfinite_values_on_discarded_radii(self):
        r = np.linspace(0.35, 1.0, 5)
        theta = np.linspace(0, math.pi, 65)
        phi = np.linspace(0, 2 * math.pi, 16, endpoint=False)
        sampling = self.leeds.ViewerSampling(r, theta, phi, 2, 4, 1)
        wave = np.broadcast_to(np.cos(22 * theta)[None, :, None], (5, 65, 16))
        filtered = sampling.volume(wave)
        self.assertLess(np.max(np.abs(filtered[:, 3:-3])), 0.12)
        bad = np.ones((5, 65, 16))
        bad[1, 0, 0] = np.nan  # radial index 1 would otherwise be dropped
        with self.assertRaises(ValueError):
            sampling.volume(bad)

    def test_all_writers_reject_invalid_values_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "field.f32"
            for converter in (self.leeds, self.xshells, self.magic):
                for bad in (np.nan, np.inf, -np.inf, 1e100):
                    path.write_bytes(b"old output")
                    with self.assertRaises(ValueError):
                        converter.write_f32(path, np.array([1.0, bad]))
                    self.assertEqual(path.read_bytes(), b"old output")
                stats = converter.write_f32(path, np.array([-1., 0., 2.]))
                self.assertAlmostEqual(stats["mean"], 1 / 3)

    @staticmethod
    def minimal_bundle(root, value=1.0):
        import json
        from tools.viewer_bundle import write_f32
        root.mkdir(parents=True, exist_ok=True)
        write_f32(root / "C_volume.f32", np.full((2, 2, 2), value))
        (root / "coordinates.json").write_text(json.dumps({"r": [0.35, 1.0], "theta": [0.1, 3.0], "phi": [0.0, math.pi]}))
        (root / "metadata.json").write_text(json.dumps({"nr": 2, "ntheta": 2, "nphi": 2, "r_inner": 0.35, "r_outer": 1.0, "coordinates": "coordinates.json", "fields": {"C": "C_volume.f32"}}))

    def test_output_transaction_failure_preserves_previous_bundle(self):
        from tools.viewer_bundle import staged_bundle_output
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder) / "output"
            self.minimal_bundle(root)
            before = (root / "C_volume.f32").read_bytes()
            with self.assertRaises(RuntimeError):
                with staged_bundle_output(root) as stage:
                    self.minimal_bundle(stage, 2)
                    raise RuntimeError("Simulated failure after writing a field")
            self.assertEqual((root / "C_volume.f32").read_bytes(), before)
            self.assertEqual(list(pathlib.Path(folder).glob(".deepscope-*")), [])
            with self.assertRaises(ValueError):
                with staged_bundle_output(root) as stage:
                    self.minimal_bundle(stage, 2)
                    (stage / "C_volume.f32").write_bytes(b"bad")
            self.assertEqual((root / "C_volume.f32").read_bytes(), before)

    def test_output_transaction_retains_backup_and_unrelated_files(self):
        from tools.viewer_bundle import staged_bundle_output
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder) / "output"
            self.minimal_bundle(root)
            (root / "notes.txt").write_text("keep me")
            with staged_bundle_output(root) as stage:
                self.minimal_bundle(stage, 2)
            self.assertTrue(np.all(np.fromfile(root / "C_volume.f32", dtype="<f4") == 2))
            self.assertEqual((root / "notes.txt").read_text(), "keep me")
            backups = list(pathlib.Path(folder).glob(".deepscope-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue(np.all(np.fromfile(backups[0] / "C_volume.f32", dtype="<f4") == 1))

    def test_output_publish_failure_rolls_back(self):
        from tools import viewer_bundle
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder) / "output"
            self.minimal_bundle(root)
            actual_replace = viewer_bundle.os.replace
            calls = 0
            def replace(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated publish failure")
                return actual_replace(source, destination)
            with self.assertRaises(OSError), mock.patch.object(viewer_bundle.os, "replace", side_effect=replace):
                with viewer_bundle.staged_bundle_output(root) as stage:
                    self.minimal_bundle(stage, 2)
            self.assertTrue(np.all(np.fromfile(root / "C_volume.f32", dtype="<f4") == 1))
            self.assertEqual(list(pathlib.Path(folder).glob(".deepscope-*")), [])

    def test_all_converter_cli_entrypoints_stage_before_writing(self):
        for converter, function in ((self.leeds, "convert_state"), (self.xshells, "convert_xshells"), (self.magic, "convert_graph")):
            with self.subTest(converter=function), tempfile.TemporaryDirectory() as folder:
                root = pathlib.Path(folder) / "output"
                self.minimal_bundle(root)
                source = pathlib.Path(folder) / ("G_1.test" if function == "convert_graph" else "state00001.cdf.dat")
                source.touch()
                cli_source = ["--graph", str(source)] if function == "convert_graph" else ["--velocity", str(source)] if function == "convert_xshells" else ["--state", str(source)]
                args = converter.build_arg_parser().parse_args(cli_source + ["--out", str(root)])
                parser = types.SimpleNamespace(parse_args=lambda: args)
                def fail(*arguments):
                    stage = pathlib.Path(arguments[1] if function == "convert_graph" else arguments[0].out)
                    self.assertNotEqual(stage, root)
                    self.minimal_bundle(stage, 2)
                    raise RuntimeError("simulated backend failure")
                with ExitStack() as stack:
                    stack.enter_context(mock.patch.object(converter, "build_arg_parser", return_value=parser))
                    stack.enter_context(mock.patch.object(converter, function, side_effect=fail))
                    stack.enter_context(mock.patch.object(converter, "import_magic_graph", create=True))
                    if function == "convert_state":
                        stack.enter_context(mock.patch.dict(sys.modules, {"modules": self.modules}))
                    with self.assertRaisesRegex(RuntimeError, "simulated backend failure"):
                        converter.main()
                self.assertTrue(np.all(np.fromfile(root / "C_volume.f32", dtype="<f4") == 1))

    def test_late_sequence_failure_leaves_previous_sequence_intact(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder) / "output"
            inputs = pathlib.Path(folder) / "input"
            inputs.mkdir()
            for number in (1, 2):
                (inputs / f"G_{number}.test").touch()
            self.minimal_bundle(root)
            self.minimal_bundle(root / "frames" / "old")
            old_index = json.dumps({"frames": [{"path": "frames/old"}]})
            (root / "sequence.json").write_text(old_index)
            args = self.magic.build_arg_parser().parse_args([
                "--folder", str(inputs), "--tag", "test", "--sequence-first", "1",
                "--sequence-last", "2", "--sequence-clear", "--out", str(root),
            ])
            completed = []
            def convert(path, output, _args):
                if completed:
                    raise RuntimeError("second frame is broken")
                self.minimal_bundle(output, 2)
                completed.append(path)
                metadata_path = output / "metadata.json"
                metadata = json.loads(metadata_path.read_text())
                metadata["time"] = 1.0
                metadata_path.write_text(json.dumps(metadata))
                return metadata
            with mock.patch.object(self.magic, "build_arg_parser", return_value=types.SimpleNamespace(parse_args=lambda: args)), \
                 mock.patch.object(self.magic, "convert_graph", side_effect=convert), \
                 mock.patch.object(self.magic, "import_magic_graph"), \
                 self.assertRaisesRegex(RuntimeError, "second frame is broken"):
                self.magic.main()
            self.assertEqual(len(completed), 1)
            self.assertEqual((root / "sequence.json").read_text(), old_index)
            self.assertTrue((root / "frames" / "old" / "metadata.json").is_file())
            self.assertFalse((root / "frames" / "G_00001").exists())

    def test_repository_backups_are_outside_the_public_directory(self):
        from tools.viewer_bundle import staged_bundle_output
        with tempfile.TemporaryDirectory() as folder:
            repo = pathlib.Path(folder)
            (repo / ".git").mkdir()
            root = repo / "public" / "data"
            self.minimal_bundle(root)
            with staged_bundle_output(root) as stage:
                self.minimal_bundle(stage, 2)
            backups = list((repo / ".deepscope-backups").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "C_volume.f32").is_file())
            self.assertEqual([p.name for p in (repo / "public").iterdir()], ["data"])

    def test_reconversion_preserves_the_dataset_default_view(self):
        from tools.viewer_bundle import staged_bundle_output
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder) / "output"
            self.minimal_bundle(root)
            code = "DTV2:eyJ2ZXJzaW9uIjoyLCJzY29wZSI6InZpZXctb25seSIsInBhcmFtcyI6e319\n"
            (root / "view.DTV2").write_text(code)
            with staged_bundle_output(root) as stage:
                self.minimal_bundle(stage, 2)
            self.assertEqual((root / "view.DTV2").read_text(), code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
