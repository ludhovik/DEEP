from pathlib import Path
import sys
import unittest
import numpy as np
from scipy.special import sph_harm_y

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.spectral_truncation import GraphicProjector, harmonic_basis, truncate_graphic_fields


class SpectralProjectionTests(unittest.TestCase):
    def setUp(self):
        self.theta = np.arccos(np.polynomial.legendre.leggauss(32)[0][::-1])
        self.phi = np.arange(64) * 2 * np.pi / 64
        self.r = np.array([0.35, 0.65, 1.0])[:, None, None]

    def harmonic(self, l, m, theta=None, phi=None):
        theta = self.theta if theta is None else theta
        phi = self.phi if phi is None else phi
        return sph_harm_y(l, m, theta[:, None], phi[None, :]).real

    def test_normalized_basis_is_finite_and_correct_through_degree_128(self):
        for m in (0, 1, 17, 85, 128):
            y, derivative, divided = harmonic_basis(128, m, self.theta)
            reference = np.array([sph_harm_y(l, m, self.theta, 0).real for l in range(m, 129)])
            np.testing.assert_allclose(y, reference, atol=3e-13)
            self.assertTrue(np.isfinite(derivative).all())
            self.assertTrue(np.isfinite(divided).all())

    def test_scalar_mean_and_low_harmonic_survive_while_high_degree_is_removed(self):
        field = 3 + self.r * self.harmonic(2, 1) + 0.4 * self.harmonic(12, 3)
        projector = GraphicProjector(self.theta, self.phi, 4)
        filtered = projector.project(field)[0]
        expected = 3 + self.r * self.harmonic(2, 1, projector.theta, projector.phi)
        np.testing.assert_allclose(filtered, expected, atol=5e-13)
        self.assertLess(filtered.size, field.size)

    def test_vector_projection_retains_dipole_and_removes_high_poloidal_and_toroidal_modes(self):
        low_q = 2 * np.cos(self.theta)[None, :, None] / self.r**3
        low_t = np.sin(self.theta)[None, :, None] / self.r**3
        # Independent analytic derivatives of Y_12^3 from SciPy.
        high, gradient = sph_harm_y(12, 3, self.theta[:, None], self.phi[None, :], diff_n=1)
        gt = gradient[..., 0].real
        gp = gradient[..., 1].real / np.sin(self.theta)[:, None]
        br = np.broadcast_to(low_q, (3, 32, 64)) + 0.2 * high.real
        bt = np.broadcast_to(low_t, br.shape) + 0.2 * gt + 0.3 * gp
        bp = np.broadcast_to(0.2 * gp - 0.3 * gt, br.shape).copy()
        projector = GraphicProjector(self.theta, self.phi, 4)
        q, t, p = projector.project(br, bt, bp)
        np.testing.assert_allclose(q, np.broadcast_to(2*np.cos(projector.theta)[None,:,None]/self.r**3, q.shape), atol=1e-11)
        np.testing.assert_allclose(t, np.broadcast_to(np.sin(projector.theta)[None,:,None]/self.r**3, t.shape), atol=1e-11)
        np.testing.assert_allclose(p, 0, atol=1e-11)

    def test_nonaxisymmetric_vector_signs_and_scalar_l0(self):
        y, g = sph_harm_y(3, 2, self.theta[:, None], self.phi[None, :], diff_n=1)
        gt, gp = g[...,0].real, g[...,1].real / np.sin(self.theta)[:,None]
        projector = GraphicProjector(self.theta, self.phi, 4, minc=2)
        q, t, p = projector.project(y.real[None], (gt + 2*gp)[None], (gp - 2*gt)[None])
        yo, go = sph_harm_y(3, 2, projector.theta[:,None], projector.phi[None,:], diff_n=1)
        gto, gpo = go[...,0].real, go[...,1].real / np.sin(projector.theta)[:,None]
        np.testing.assert_allclose(q[0], yo.real, atol=1e-12)
        np.testing.assert_allclose(t[0], gto + 2*gpo, atol=1e-12)
        np.testing.assert_allclose(p[0], gpo - 2*gto, atol=1e-12)
        mean = projector.project(np.ones((1,32,64)) * 7)[0]
        np.testing.assert_allclose(mean, 7, atol=1e-12)

    def test_default_zero_and_above_source_cutoffs_leave_arrays_unchanged(self):
        fields = {"C": np.ones((3,32,64))}
        for cutoff in (None, 0, 32, 64):
            result, th, ph, info = truncate_graphic_fields(fields, self.theta, self.phi, cutoff, 20)
            self.assertIs(result, fields)
            self.assertIs(th, self.theta)
            self.assertIs(ph, self.phi)
            self.assertFalse(info["enabled"])

    def test_invalid_or_unresolved_projection_is_rejected(self):
        with self.assertRaises(ValueError):
            GraphicProjector(np.linspace(.01, np.pi-.01,32), self.phi, 4)
        with self.assertRaises(ValueError):
            GraphicProjector(self.theta, self.phi, 40)
        projector = GraphicProjector(self.theta, self.phi, 4)
        with self.assertRaises(ValueError):
            projector.project(np.full((2,32,64), np.nan))
        with self.assertRaises(ValueError):
            truncate_graphic_fields({"ur": np.ones((2,32,64))}, self.theta, self.phi, 4, 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
