"""Analytic checks of native-grid mean derivatives and positive scalar advection."""
import argparse
import unittest
import numpy as np
from scipy.interpolate import interp1d
from tools.scalar_diagnostics import (
    longitude_mean, dtheta_phi_average, dz_up_phi_average, scalar_advection,
    default_diagnostic_names, iter_scalar_diagnostics, SCALAR_DIAGNOSTICS,
)
from tools.output_selection import OutputSelection


class ScalarDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.r = np.linspace(0, 1, 12)
        self.theta = np.linspace(.01, np.pi-.01, 192)
        self.phi = np.linspace(0, 2*np.pi, 32, endpoint=False)
        self.rr, self.th, self.ph = np.meshgrid(self.r, self.theta, self.phi, indexing='ij')

    def test_colatitude_derivative_has_no_inverse_radius_and_removes_nonaxisymmetric_modes(self):
        scalar = self.rr**2*self.th**2 + self.rr*np.cos(3*self.ph)
        result = dtheta_phi_average(scalar, self.r, self.theta, self.phi)
        np.testing.assert_allclose(result, 2*self.rr**2*self.th, atol=3e-12)
        np.testing.assert_allclose(result[..., 0], result[..., -1])

    def test_axial_shear_is_at_fixed_cylindrical_radius_not_fixed_colatitude(self):
        s = self.rr*np.sin(self.th)
        z = self.rr*np.cos(self.th)
        up = s*z + self.rr*np.cos(2*self.ph)
        result = dz_up_phi_average(up, self.r, self.theta, self.phi)
        np.testing.assert_allclose(result, s, atol=2e-4)
        np.testing.assert_array_equal(result[0], 0)
        solid_rotation = dz_up_phi_average(3*s, self.r, self.theta, self.phi)
        np.testing.assert_allclose(solid_rotation, 0, atol=2e-4)

    def test_positive_advection_of_cartesian_linear_scalar_and_nonzero_centre_limit(self):
        # T=x, u=e_x: u.grad(T)=+1 everywhere, including r=0.
        ur = np.sin(self.th)*np.cos(self.ph)
        ut = np.cos(self.th)*np.cos(self.ph)
        up = -np.sin(self.ph)
        scalar = self.rr*ur
        gradients = [ur.copy(), ut.copy(), up.copy()]
        gradients[1][0] = 0
        gradients[2][0] = 0
        adv = scalar_advection((ur, ut, up), gradients, scalar, self.r, self.theta, self.phi)
        np.testing.assert_allclose(adv, 1, atol=2e-14)
        composition = scalar_advection((ur, ut, up), [-2*g for g in gradients],
                                       -2*scalar, self.r, self.theta, self.phi)
        np.testing.assert_allclose(composition, -2, atol=4e-14)

    def test_periodic_nonuniform_longitude_weights(self):
        phi = np.array([0, np.pi/4, np.pi, 3*np.pi/2])
        values = np.array([[[0., 4., 8., 12.]]])
        np.testing.assert_allclose(longitude_mean(values, phi), 6.5)
        with self.assertRaises(ValueError):
            longitude_mean(values, [0, 1, 2, 2*np.pi])

    def test_advection_respects_intersection_of_native_scalar_and_velocity_domains(self):
        rt = np.array([.2, .4, .6, .8, 1.])
        ru = np.array([.4, .5, .8])
        theta, phi = self.theta[:4], self.phi
        t = np.broadcast_to(rt[:, None, None]**2, (5, 4, 32))
        u = np.ones((3, 4, 32))
        raw = dict(T=t, ur=u, ut=0*u, up=0*u)
        radii = dict(T=rt, ur=ru, ut=ru, up=ru)
        gradient = lambda _: (2*np.sqrt(t), 0*t, 0*t)
        remap = lambda a, rs, target: interp1d(rs, a, axis=0)(target)
        name, values, r, source = next(iter_scalar_diagnostics(['advT'], raw, radii, theta, phi, gradient, remap))
        np.testing.assert_array_equal(r, [.4, .6, .8])
        np.testing.assert_allclose(values, np.broadcast_to(2*r[:, None, None], values.shape))
        self.assertEqual(source, 'scalar_velocity_overlap')

    def test_dependencies_flag_conflicts_and_missing_composition(self):
        def selection(name, **extra):
            return OutputSelection(argparse.Namespace(output=[name], emf=False, induction=False, **extra))
        for name in SCALAR_DIAGNOSTICS:
            with self.subTest(name=name):
                selected = selection(name)
                self.assertFalse(selected.needs('Br'))
                self.assertEqual(selected.needs('ur'), name in ('advT', 'advC', 'dzup_phiavg'))
                with self.assertRaises(ValueError): selection(name, no_gradients=True)
        self.assertTrue(selection('advT').needs('T'))
        self.assertFalse(selection('advT').needs('C'))
        self.assertTrue(selection('advC').needs('C'))
        self.assertFalse(selection('dzup_phiavg').needs('T'))
        for name in ('advC', 'dthetaC_phiavg'):
            with self.assertRaisesRegex(ValueError, 'composition'): selection(name, RaC=0)
        with self.assertRaises(ValueError): selection('dzup_phiavg', no_m0_fields=True)
        self.assertEqual(default_diagnostic_names({'T': None}, argparse.Namespace()), ['dthetaT_phiavg'])
        self.assertEqual(default_diagnostic_names({'T': None}, argparse.Namespace(no_gradients=True)), [])


if __name__ == '__main__':
    unittest.main()
