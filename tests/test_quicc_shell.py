"""Mapped Chebyshev shell reconstruction and optional native benchmark checks."""
from pathlib import Path
import contextlib
import io
import json
import math
import os
import sys
import tempfile
import unittest

import h5py
import numpy as np
from scipy.fft import dct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from quicc_data import read_state,modes,grids,chebyshev_shell,synthesize_field
from convert_quicc_to_viewer import main
from viewer_bundle import validate_bundle
from test_quicc_converter import fixture


def shell_fixture(path,scheme='SLFl',axis='z',ri=.5,ro=1.5):
    fixture(path,'WLFl' if scheme=='SLFl' else 'WLFm')
    pairs=modes(3,3,1,scheme[-1]);a,b=(ro-ri)/2,(ro+ri)/2
    with h5py.File(path,'r+') as f:
        f.attrs['type']=np.bytes_(scheme)
        for key,value in [('lower1d',ri),('upper1d',ro),('rratio',ri/ro)]:f['physical/'+key]=value
        for prefix in ('velocity','magnetic'):
            for part in ('tor','pol'):f[prefix+'/'+prefix+'_'+part][:]=0
        tor=np.zeros((len(pairs),3),complex)
        tor[pairs.index((1,0)),:2]=np.array([b,a/2])/math.sqrt(3/(4*math.pi))
        f['velocity/velocity_tor'][:]=tor
        pol=np.zeros_like(tor)
        if axis=='z':
            pol[pairs.index((1,0)),:2]=np.array([b/2,a/4])/math.sqrt(3/(4*math.pi))
        else:
            pol[pairs.index((1,1)),:2]=np.array([b,a/2])*(-1 if axis=='x' else 1j)/(4*math.sqrt(3/(8*math.pi)))
        f['magnetic/magnetic_pol'][:]=pol
        scalar=np.zeros_like(tor)
        scalar[pairs.index((0,0))]=np.array([1+b*b+a*a/2,a*b,a*a/4])*math.sqrt(4*math.pi)
        f['temperature/temperature'][:]=scalar
        f['composition/composition'][:]=2*scalar


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.state=self.root/'state0001.hdf5';shell_fixture(self.state)
    def tearDown(self):self.temp.cleanup()
    def convert(self,*extra):
        log=io.StringIO()
        with contextlib.redirect_stdout(log):
            main(['--state',str(self.state),'--out',str(self.root/'out'),'--incremental',
                  '--cache-dir',str(self.root/'cache'),'--skip-field-lines','--no-earth-br',*extra])
        return log.getvalue()
    def test_chebyshev_normalization_matches_dct(self):
        count=24;n=60;ri,ro=.5384615384615384,1.5384615384615383
        x=np.cos(np.pi*(np.arange(n)+.5)/n);r=(ro-ri)/2*x+(ro+ri)/2
        coef=np.random.default_rng(71).normal(size=count)
        w,over,tangent=chebyshev_shell(count,r,(ri,ro))
        np.testing.assert_allclose(w@coef,dct(np.pad(coef,(0,n-count)),type=3),atol=1e-12)
        eps=1e-7
        plus=chebyshev_shell(count,r+eps,(ri,ro))[0]
        minus=chebyshev_shell(count,r-eps,(ri,ro))[0]
        np.testing.assert_allclose((tangent-over)@coef,(plus-minus)@coef/(2*eps),rtol=3e-7,atol=1e-6)
    def test_vectors_scalar_and_both_orderings(self):
        for scheme in ('SLFl','SLFm'):
            for axis in 'xyz':
                shell_fixture(self.state,scheme,axis)
                s=read_state(self.state);r,th,ph=grids(2,3,3,s['radial_interval']);pairs=modes(3,3,1,scheme[-1])
                b=synthesize_field((s['fields']['Br'],s['fields']['Btor']),pairs,r,th,ph,3,radial_interval=s['radial_interval'])
                st,ct=np.sin(th)[None,:,None],np.cos(th)[None,:,None]
                sp,cp=np.sin(ph)[None,None,:],np.cos(ph)[None,None,:]
                xyz=(b[0]*st*cp+b[1]*ct*cp-b[2]*sp,b[0]*st*sp+b[1]*ct*sp+b[2]*cp,b[0]*ct-b[1]*st)
                for name,value in zip('xyz',xyz):np.testing.assert_allclose(value,float(name==axis),atol=2e-14)
                u=synthesize_field((s['fields']['ur'],s['fields']['utor']),pairs,r,th,ph,3,radial_interval=s['radial_interval'])
                np.testing.assert_allclose(u[0],0,atol=1e-14);np.testing.assert_allclose(u[1],0,atol=1e-14)
                np.testing.assert_allclose(u[2],np.broadcast_to(r[:,None,None]*st,u[2].shape),atol=2e-14)
                c=synthesize_field(s['fields']['T'],pairs,r,th,ph,3,radial_interval=s['radial_interval'])
                np.testing.assert_allclose(c,np.broadcast_to(1+r[:,None,None]**2,c.shape),atol=2e-14)
    def test_geometry_export_and_incremental_addition(self):
        self.convert('--geometry','shell','--fluid-inner-radius','.5')
        m=json.loads((self.root/'out/metadata.json').read_text())
        self.assertFalse(m['full_sphere']);self.assertEqual(m['r_icb'],.5);self.assertEqual(m['r_outer'],1.5)
        self.assertFalse(m['has_conducting_inner_core']);validate_bundle(self.root/'out')
        log=self.convert('--geometry','shell','--fluid-inner-radius','.5','--emf','--induction')
        self.assertIn('Reuse calculation: synthesize_field',log)
        self.assertTrue((self.root/'out/Ir_volume.f32').exists())
        self.assertIn('skipped',self.convert('--geometry','shell','--fluid-inner-radius','.5','--emf','--induction'))
    def test_n2_shell_gravity_and_rayleigh_convention(self):
        self.convert('--n2-convention','quicc-rotating','--Pr','7','--RaC','0')
        m=json.loads((self.root/'out/metadata.json').read_text());shape=(m['nr'],m['ntheta'],m['nphi'])
        r=np.asarray(json.loads((self.root/'out/coordinates.json').read_text())['r'])
        n2=np.fromfile(self.root/'out/N2_volume.f32',dtype='<f4').reshape(shape)
        np.testing.assert_allclose(n2,np.broadcast_to(.2*r[:,None,None]**2/1.5,shape),rtol=3e-5,atol=1e-6)
    def test_boundaries_are_required_and_checked(self):
        for key,value in [('lower1d',0.),('upper1d',.1),('rratio',.9)]:
            shell_fixture(self.state)
            with h5py.File(self.state,'r+') as f:f['physical/'+key][()]=value
            with self.assertRaises(ValueError):read_state(self.state)
        shell_fixture(self.state)
        with h5py.File(self.state,'r+') as f:del f['physical/lower1d']
        with self.assertRaisesRegex(ValueError,'lower1d'):read_state(self.state)
    def test_conflicting_options_and_archive_error(self):
        for options in [('--geometry','full-sphere'),('--geometry','conducting-inner-core'),
                        ('--fluid-inner-radius','.4'),('--worland-family','legendre')]:
            with self.assertRaises(ValueError):self.convert(*options)
        archive=self.root/'Explicit.tar.gz';archive.write_bytes(b'not an HDF5 state')
        with self.assertRaisesRegex(ValueError,'unpack .tar.gz'):read_state(archive)
    def test_shell_sequence(self):
        shell_fixture(self.root/'state0002.hdf5','SLFm')
        args=['--folder',str(self.root),'--out',str(self.root/'sequence'),'--sequence-first','1',
              '--sequence-last','2','--incremental','--cache-dir',str(self.root/'cache'),'--skip-field-lines','--no-earth-br']
        with contextlib.redirect_stdout(io.StringIO()):main(args)
        validate_bundle(self.root/'sequence')
        for path in (self.root/'sequence').rglob('metadata.json'):
            self.assertEqual(json.loads(path.read_text())['r_icb'],.5)


@unittest.skipUnless(os.environ.get('QUICC_SHELL_BENCHMARK_DIR'),'Set QUICC_SHELL_BENCHMARK_DIR for native reference data')
class NativeBenchmarkTests(unittest.TestCase):
    def test_reconstructed_energy_matches_solver(self):
        folder=Path(os.environ['QUICC_SHELL_BENCHMARK_DIR'])
        s=read_state(folder/'state0000.hdf5');ri,ro=s['radial_interval']
        x,w=np.polynomial.legendre.leggauss(72);r=ri+(x+1)*(ro-ri)/2;rw=w*(ro-ri)/2*r*r
        x,tw=np.polynomial.legendre.leggauss(72);th=np.arccos(x[::-1]);ph=np.arange(144)*2*np.pi/144
        for name,stem in [('ur','kinetic'),('Br','magnetic'),('C','temperature')]:
            a=s['fields'][name]
            if name!='C':a=(a,s['fields']['utor' if name=='ur' else 'Btor'])
            v=synthesize_field(a,modes(s['lmax'],s['mmax']),r,th,ph,s['lmax'],radial_interval=(ri,ro))
            if name=='C':v=[v]
            energy=sum(np.einsum('r,t,rtp->',rw,tw[::-1],b*b)*2*np.pi/len(ph)/(4*np.pi/3*(ro**3-ri**3)) for b in v)
            if name!='C':energy/=2
            expected=np.loadtxt(folder/(stem+'_energy.dat'))[0,1]
            self.assertAlmostEqual(energy/expected,1.,places=11)

if __name__=='__main__':unittest.main()
