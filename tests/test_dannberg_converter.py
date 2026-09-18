import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
try:
    import pyshtools as pysh
except ImportError:
    pysh = None

from tools.convert_dannberg_to_viewer import discover, expand_surface, main
from tools.viewer_bundle import validate_bundle


@unittest.skipIf(pysh is None, 'Install requirements-dannberg.txt')
class DannbergTests(unittest.TestCase):
    def test_sign_phase_longitude_and_spherical_mean(self):
        c = pysh.SHCoeffs.from_zeros(4, normalization='schmidt', csphase=-1)
        c.set_coeffs(-2., 0, 0)
        # Schmidt P11 with Condon-Shortley phase is -sin(theta).
        c.set_coeffs(0.3, 1, 1)
        q, theta, phi, mean = expand_surface(c, 4, 'geographic', 'out-of-core')
        expected = 2. - 0.3 * np.sin(theta[:, None]) * np.cos(phi[None, :])
        np.testing.assert_allclose(q, expected, atol=1e-14)
        self.assertAlmostEqual(mean, 2.)
        self.assertLess(phi[-1], 2*np.pi)

    def test_two_real_netcdf_frames_export_only_surfaces(self):
        with tempfile.TemporaryDirectory() as temp:
            source, out = Path(temp)/'source', Path(temp)/'out'
            source.mkdir()
            for step, value in [(8, -2.), (17, -3.)]:
                c = pysh.SHCoeffs.from_zeros(4, normalization='schmidt', csphase=-1)
                c.set_coeffs(value, 0, 0)
                c.to_netcdf(str(source/f'heat_flux_sph.{step:05d}.cdf.dat'))
            main(['--input',str(source),'--out',str(out),'--all-frames','--lmax','4'])
            validate_bundle(out)
            sequence = json.loads((out/'sequence.json').read_text())
            self.assertEqual(len(sequence['frames']), 2)
            self.assertIsNone(sequence['frames'][0]['time'])
            for index, expected in enumerate([2.,3.]):
                frame = out/sequence['frames'][index]['path']
                meta = json.loads((frame/'metadata.json').read_text())
                self.assertTrue(meta['surface_only'])
                self.assertEqual(meta['fields'], {})
                self.assertFalse(list(frame.glob('*_volume.f32')))
                np.testing.assert_allclose(np.fromfile(frame/'q_CMB_cmb.f32',dtype='<f4'),expected)
                np.testing.assert_allclose(np.fromfile(frame/'q_CMB_anomaly_cmb.f32',dtype='<f4'),0)
            with self.assertRaises(SystemExit):
                main(['--input',str(source),'--nominal-age-schedule','--inspect'])

    def test_mixed_models_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for model in ['thermal','thermochemical']:
                folder=Path(temp)/model
                folder.mkdir()
                (folder/'heat_flux_sph.00000.cdf.dat').touch()
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                discover(temp)
