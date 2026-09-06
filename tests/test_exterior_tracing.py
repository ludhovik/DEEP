"""Analytic checks for exterior arc selection, sampling and CMB roundoff."""
from __future__ import annotations

import contextlib
import io
import math
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import convert_state_to_viewer as converter


def exterior_grid(nr=96, rmax=40.0, lmax=128, step=None):
    with contextlib.redirect_stdout(io.StringIO()):
        return converter.prepare_exterior_tracing(1.0, rmax, nr, lmax, step)


def field_grid(radii, quadrupole=0.0):
    theta = np.linspace(0.005, math.pi - 0.005, 241)
    phi = np.linspace(0.0, 2.0 * math.pi, 8, endpoint=False)
    r, th, _ = np.meshgrid(radii, theta, phi, indexing="ij")
    # V=cos(theta)/r^2 + a*P2(cos(theta))/r^3, B=-grad(V).
    br = 2.0 * np.cos(th) / r**3 + 1.5 * quadrupole * (3.0 * np.cos(th)**2 - 1.0) / r**4
    bt = np.sin(th) / r**3 + 3.0 * quadrupole * np.cos(th) * np.sin(th) / r**4
    return br, bt, np.zeros_like(br), theta, phi


def seed_record(degrees, longitude=0.0, line_id="test"):
    theta = math.radians(degrees)
    return {
        "line_id": line_id, "cmb_seed_source": "traced_cmb_intersection",
        "cmb_seed": converter.sph_to_cart(1.0, theta, longitude).tolist(),
        "polarity": 1 if math.cos(theta) > 0.0 else -1,
        "cmb_br_seed": 2.0 * math.cos(theta),
    }


class ExteriorTracingTests(unittest.TestCase):
    def test_large_domain_resolves_near_cmb_decay_and_has_independent_base_step(self):
        r, step, info = exterior_grid()
        _, default_step, _ = exterior_grid(rmax=2.5)
        self.assertEqual(step, default_step)
        self.assertEqual(r[0], 1.0)
        self.assertEqual(r[-1], 40.0)
        self.assertTrue(np.all(np.diff(r) > 0.0))
        self.assertLess(info["first_radial_spacing"], 0.001)
        samples = 1.0 + np.linspace(0.0, 4.0 / 130.0, 200)
        exact = samples**-130  # Degree-128 radial field near the CMB.
        coarse_error = np.max(np.abs(np.interp(samples, r, r**-130) / exact - 1.0))
        fine, _, _ = exterior_grid(nr=192)
        fine_error = np.max(np.abs(np.interp(samples, fine, fine**-130) / exact - 1.0))
        self.assertLess(coarse_error, 0.03)
        self.assertLess(fine_error, coarse_error / 3.0)
        old = np.linspace(1.0, 40.0, 96)
        self.assertGreater(np.max(np.abs(np.interp(samples, old, old**-130) / exact - 1.0)), 1.0)

    def test_fixed_step_and_invalid_geometry(self):
        _, step, info = exterior_grid(step=0.004)
        self.assertEqual(step, 0.004)
        self.assertEqual(info["step_policy"], "fixed")
        for rmax in (1.0, 0.0, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                exterior_grid(rmax=rmax)
        for step in (0.0, -1.0, float("nan")):
            with self.assertRaises(ValueError):
                exterior_grid(step=step)

    def test_interpolation_accepts_roundoff_but_rejects_real_boundary_crossings(self):
        r, _, _ = exterior_grid()
        br, bt, bp, theta, phi = field_grid(r)
        for boundary, outside in ((1.0, 0.0), (40.0, math.inf)):
            almost = np.nextafter(boundary, outside)
            sampled = converter.interp_spherical_field(br, r, theta, phi, almost, 0.7, 0.2)
            self.assertTrue(math.isfinite(sampled))
        self.assertTrue(math.isnan(converter.interp_spherical_field(br, r, theta, phi, 1.0 - 1e-9, 0.7, 0.2)))
        self.assertIsNone(converter.interpolate_B_cartesian(
            converter.sph_to_cart(1.0 - 1e-9, 0.7, 0.2), br, bt, bp, r, theta, phi))

    def test_long_shallow_and_roundoff_dipole_arcs_all_close_at_their_paired_seed(self):
        r, step, _ = exterior_grid()
        br, bt, bp, theta, phi = field_grid(r)
        records = [seed_record(deg, ph, str(i)) for i, (deg, ph) in enumerate([
            (10.0, 0.2), (60.0, 0.2), (70.0, 0.0), (89.5, 2.7), (120.0, 0.7),
        ])]
        # A real CMB seed which rounds just inside the interpolation domain.
        point = converter.sph_to_cart(1.0, 0.8, 2.6927937030769655)
        point *= np.nextafter(1.0, 0.0) / np.linalg.norm(point)
        record = seed_record(math.degrees(0.8), 2.6927937030769655, "roundoff")
        record["cmb_seed"] = point.tolist()
        records.append(record)
        lines = converter.compute_external_field_lines_from_cmb(
            br, bt, bp, r, theta, phi, 1, 1, 1000, step,
            seed_records=records, adaptive_step=True,
        )
        self.assertEqual(len(lines), len(records))
        for record, line in zip(records, lines):
            points = np.asarray(line["points"])
            self.assertTrue(np.array_equal(points[0], record["cmb_seed"]))
            self.assertEqual(line["status"], "returned_cmb")
            self.assertEqual(line["polarity"], record["polarity"])
            self.assertEqual(line["paired_shell_line_id"], record["line_id"])
            self.assertLess(line["end_r_error"], 1e-12)
            radii = np.linalg.norm(points, axis=1)
            sin_squared = (points[:, 0]**2 + points[:, 1]**2) / radii**2
            invariant = radii / sin_squared
            self.assertLess(np.ptp(invariant) / np.mean(invariant), 2e-5)
            self.assertGreater(len(points), 7)
            self.assertTrue(np.isfinite(line["strength"]).all())

    def test_short_arc_is_refined_even_with_an_explicit_large_step(self):
        r, _, _ = exterior_grid()
        br, bt, bp, theta, phi = field_grid(r)
        seed = converter.sph_to_cart(1.0, math.radians(89.5), 2.7)
        points, status, apex = converter.trace_exterior_cmb_to_cmb_arc(
            seed, 1.0, br, bt, bp, r, theta, phi, 0.2, 1000, 8,
        )
        self.assertEqual(status, "returned_cmb")
        self.assertGreaterEqual(len(points), 8)
        self.assertLess(abs(apex - 1.0 / math.sin(math.radians(89.5))**2), 1e-6)

    def test_outer_boundary_and_step_budget_are_distinguished_from_closure(self):
        r, step, _ = exterior_grid(rmax=2.5)
        br, bt, bp, theta, phi = field_grid(r)
        seed = seed_record(10.0, 0.2)
        lines = converter.compute_external_field_lines_from_cmb(
            br, bt, bp, r, theta, phi, 1, 1, 1000, step,
            seed_records=[seed], adaptive_step=True, closed_only=False,
        )
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["status"], "hit_external_rmax")
        self.assertAlmostEqual(lines[0]["end_r"], 2.5, places=12)
        closed = converter.compute_external_field_lines_from_cmb(
            br, bt, bp, r, theta, phi, 1, 1, 1000, step,
            seed_records=[seed], adaptive_step=True,
        )
        self.assertEqual(closed, [])
        _, status, _ = converter.trace_exterior_cmb_to_cmb_arc(
            np.asarray(seed["cmb_seed"]), 1.0, br, bt, bp, r, theta, phi, step, 1, 8,
        )
        self.assertEqual(status, "max_steps")

    def test_skipped_seed_counts_reconcile_with_input(self):
        r, step, _ = exterior_grid()
        br, bt, bp, theta, phi = field_grid(r)
        records = [seed_record(60.0, 0.2), {"cmb_seed_source": "nominal_radial_projection"},
                   {"cmb_seed_source": "traced_cmb_intersection", "cmb_seed": [float("nan"), 0, 0]}]
        converter.compute_external_field_lines_from_cmb(
            br, bt, bp, r, theta, phi, 1, 1, 1000, step,
            seed_records=records, adaptive_step=True,
        )
        counts = converter.compute_external_field_lines_from_cmb.last_seed_counts
        self.assertEqual(counts["input"], 3)
        self.assertEqual(counts["traced"], 1)
        self.assertEqual(counts["retained"], 1)
        self.assertEqual(sum(counts["skipped"].values()) + counts["traced"], counts["input"])

    def test_mixed_degree_field_converges_toward_analytic_flux_surface(self):
        errors = []
        for nr in (96, 192):
            r, step, _ = exterior_grid(nr=nr)
            br, bt, bp, theta, phi = field_grid(r, quadrupole=0.4)
            points, status, _ = converter.trace_exterior_cmb_to_cmb_arc(
                converter.sph_to_cart(1.0, 0.8, 0.2), 1.0,
                br, bt, bp, r, theta, phi, step, 1000, 8, adaptive_step=True,
            )
            self.assertEqual(status, "returned_cmb")
            xyz = np.asarray(points)
            radius = np.linalg.norm(xyz, axis=1)
            costheta = xyz[:, 2] / radius
            flux = (1.0 - costheta**2) * (1.0 / radius + 0.6 * costheta / radius**2)
            errors.append(float(np.max(np.abs(flux / flux[0] - 1.0))))
        self.assertLess(errors[0], 0.002)
        self.assertLess(errors[1], errors[0] / 2.0)

    def test_return_branch_follows_simulated_field_from_exact_exterior_endpoint(self):
        r, step, _ = exterior_grid(rmax=2.5)
        br, bt, bp, theta, phi = field_grid(r)
        origin = seed_record(60.0, 0.2)
        exterior = converter.compute_external_field_lines_from_cmb(
            br, bt, bp, r, theta, phi, 1, 1, 1000, step,
            seed_records=[origin], adaptive_step=True,
        )
        shell_r = np.linspace(.35, 1., 181)
        br, bt, bp, theta, phi = field_grid(shell_r)
        extra, counts = converter.connect_exterior_return_footpoints(
            [origin], exterior, br, bt, bp, shell_r, theta, phi, .002, 1500,
        )
        self.assertEqual(counts, {"connected": 1})
        branch = extra[0]
        self.assertEqual(branch["points"][0], exterior[0]["points"][-1])
        self.assertEqual(branch["direction"], exterior[0]["direction"])
        points = np.asarray(branch["points"])
        radius = np.linalg.norm(points, axis=1)
        self.assertLess(radius[1], radius[0])
        self.assertAlmostEqual(radius[-1], .35, places=12)
        flux = radius / ((points[:,0]**2 + points[:,1]**2) / radius**2)
        self.assertLess(np.ptp(flux)/np.mean(flux), 2e-5)
        bad = dict(exterior[0])
        bad.pop("paired_shell_return_line_id")
        extra, counts = converter.connect_exterior_return_footpoints(
            [origin], [bad], -br, -bt, -bp, shell_r, theta, phi, .002, 1500,
        )
        self.assertEqual(extra, [])
        self.assertEqual(counts, {"radial_polarity_mismatch": 1})
        self.assertNotIn("paired_shell_return_line_id", bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
