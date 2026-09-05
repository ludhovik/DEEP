#!/usr/bin/env python3
from __future__ import annotations

import ast
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
LEEDS_PATH = ROOT / "tools" / "convert_state_to_viewer.py"
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
            "C", "Comp", "Cnom0", "Compnom0", "Cnol0", "Compnol0",
            "N2", "N2_full",
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

    def test_magic_end_to_end_binary_contract(self):
        nr, ntheta, nphi = 5, 8, 12
        radius = np.linspace(1.0, 0.35, nr)
        theta = np.arccos(np.polynomial.legendre.leggauss(ntheta)[0][::-1])
        phi = np.linspace(0.0, 2.0 * math.pi, nphi, endpoint=False)
        P, T, R = np.meshgrid(phi, theta, radius, indexing="ij")
        graph = types.SimpleNamespace(
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
            self.assertIn("Comp", metadata["fields"])
            for filename in metadata["fields"].values():
                self.assertEqual((output / filename).stat().st_size, expected_size)


if __name__ == "__main__":
    unittest.main(verbosity=2)
