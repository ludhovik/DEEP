"""Analytic spectral checks and shared-export tests; optional upstream benchmark.

QUICC_BENCHMARK_DIR=/path/to/Explicit python3 tests/test_quicc_converter.py
"""
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
from scipy.integrate import quad
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from quicc_data import modes, worland, grids, synthesize_field, read_state
from convert_quicc_to_viewer import main, build_arg_parser, discover_states
from convert_magic_to_viewer import build_arg_parser as magic_parser
from viewer_bundle import validate_bundle


def fixture(path, scheme='EPM', axis='z', scalar=True, minc=1):
    pairs = modes(3,3,minc,scheme[-1])
    arrays = {name: np.zeros((len(pairs),3),complex) for name in ('ur','utor','Br','Btor','C','Comp')}
    # Specify physical potentials with the EPM angular basis and r^l radial basis.
    idx = pairs.index((1,0))
    inv = worland(1,3,[1.])[0][0,0]
    arrays['utor'][idx,0] = 1/inv  # u=(-y,x,0)
    if axis=='z': arrays['Br'][idx,0] = .5/inv
    else:
        idx=pairs.index((1,1))
        arrays['Br'][idx,0] = (-.25 if axis=='x' else .25j)/inv
    # C=1+r^2, Comp=2C: P_0=1, P_1=r^2-1/2 in l=0 Chebyshev Worland.
    inv0=worland(0,3,[1.])[0][0]
    i0=pairs.index((0,0))
    arrays['C'][i0,:2] = [1.5/inv0[0], .5/inv0[1]]
    arrays['Comp']=2*arrays['C']
    if scheme!='EPM':
        for i,(l,m) in enumerate(pairs):
            factor=math.sqrt(4*math.pi/(2*l+1))*(math.sqrt(2) if m else 1)
            for a in arrays.values():a[i] *= factor
    with h5py.File(path,'w') as f:
        f.attrs.update(header=np.bytes_('StateFile'), version=np.bytes_('1.0'))
        if scheme=='EPM':
            for k,v in zip(('N','L','M','Mp'),(2,3,3,minc)):f['Truncation/'+k]=v
            paths={'ur':'Velocity/VelocityPol','utor':'Velocity/VelocityTor',
                   'Br':'Magnetic/MagneticPol','Btor':'Magnetic/MagneticTor','C':'Codensity/Codensity'}
            f['RunParameters/Time']=.75
            for k,v in dict(E=.001,Pr=1.,Pm=2.,Ra=100.).items():f['PhysicalParameters/'+k]=v
        else:
            f.attrs['type']=np.bytes_(scheme)
            for k,v in zip(('1','2','3'),(2,3,3)):f['truncation/spectral/dim'+k+'D']=v
            paths={'ur':'velocity/velocity_pol','utor':'velocity/velocity_tor',
                   'Br':'magnetic/magnetic_pol','Btor':'magnetic/magnetic_tor',
                   'C':'temperature/temperature','Comp':'composition/composition'}
            f['run/time']=.75
            for k,v in dict(ekman=.001,prandtl=1.,magnetic_prandtl=2.,rayleigh=100.,schmidt=1.,rayleigh_composition=0.).items():f['physical/'+k]=v
        for k,p in paths.items():
            if not scalar and k in ('C','Comp'):continue
            # Native EPM uses an HDF5 array datatype for each complex coefficient.
            a=arrays[k]
            if scheme=='EPM':
                d=f.create_dataset(p,shape=a.shape,dtype=np.dtype((np.float64,(2,))))
                d[:]=np.stack([a.real,a.imag],axis=-1)
            else:f[p]=a


class MathTests(unittest.TestCase):
    def test_worland_orthonormality(self):
        for family in ('chebyshev','legendre'):
            for l in (0,1,2,12):
                for n,k in ((0,0),(1,1),(3,3),(0,2),(1,3)):
                    def integrand(t):
                        # r=sin(t), removes Chebyshev endpoint weight singularity.
                        w=worland(l,4,[math.sin(t)],family)[0][0]
                        return w[n]*w[k]*(1 if family=='chebyshev' else math.cos(t))
                    value=quad(integrand,0,math.pi/2,epsabs=1e-11)[0]
                    self.assertAlmostEqual(value,float(n==k),places=10)

    def test_analytic_vectors_and_scalars_including_centre(self):
        with tempfile.TemporaryDirectory() as d:
            for scheme in ('EPM','WLFl','WLFm'):
                for axis in ('x','y','z'):
                    p=Path(d)/'state0000.hdf5';fixture(p,scheme,axis)
                    state=read_state(p);pairs=modes(3,3,1,scheme[-1])
                    r,th,ph=grids(2,3,3)
                    norm='epm' if scheme=='EPM' else 'unity'
                    b=synthesize_field((state['fields']['Br'],state['fields']['Btor']),pairs,r,th,ph,3,norm)
                    st,ct=np.sin(th)[None,:,None],np.cos(th)[None,:,None]
                    sp,cp=np.sin(ph)[None,None,:],np.cos(ph)[None,None,:]
                    x=b[0]*st*cp+b[1]*ct*cp-b[2]*sp
                    y=b[0]*st*sp+b[1]*ct*sp+b[2]*cp
                    z=b[0]*ct-b[1]*st
                    for name,value in zip('xyz',(x,y,z)):
                        np.testing.assert_allclose(value,float(name==axis),atol=2e-14)
                    u=synthesize_field((state['fields']['ur'],state['fields']['utor']),pairs,r,th,ph,3,norm)
                    np.testing.assert_allclose(u[0],0,atol=1e-14)
                    np.testing.assert_allclose(u[1],0,atol=1e-14)
                    np.testing.assert_allclose(u[2],np.broadcast_to(r[:,None,None]*st,u[2].shape),atol=1e-14)
                    c=synthesize_field(state['fields']['C'],pairs,r,th,ph,3,norm)
                    np.testing.assert_allclose(c,np.broadcast_to(1+r[:,None,None]**2,c.shape),atol=2e-14)

    def test_radial_derivatives(self):
        r=np.linspace(.1,.9,13);eps=1e-6
        for l in (1,2,8):
            w,over,s=worland(l,7,r)
            derivative=(worland(l,7,r+eps)[0]-worland(l,7,r-eps)[0])/(2*eps)
            np.testing.assert_allclose(s-over,derivative,rtol=3e-8,atol=3e-8)
            np.testing.assert_allclose(over,w/r[:,None])

    def test_minc_and_truncation(self):
        pairs=modes(6,6,2);r,th,ph=grids(2,6,6);ph=np.arange(24)*2*np.pi/24
        a=np.zeros((len(pairs),3),complex);a[pairs.index((6,4)),0]=1+2j
        field=synthesize_field(a,pairs,r,th,ph,6,'epm')
        np.testing.assert_allclose(field,np.roll(field,6,axis=2),atol=2e-13)
        np.testing.assert_allclose(synthesize_field(a,pairs,r,th,ph,3,'epm'),0,atol=0)


class IOTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.state=self.root/'state0001.hdf5';fixture(self.state,'WLFl')
    def tearDown(self):self.temp.cleanup()
    def convert(self,*extra):
        log=io.StringIO()
        with contextlib.redirect_stdout(log):
            main(['--state',str(self.state),'--out',str(self.root/'bundle'),
                  '--incremental','--cache-dir',str(self.root/'cache'),'--skip-field-lines',*extra])
        return log.getvalue()
    def test_shared_option_parity(self):
        expected={o for a in magic_parser()._actions for o in a.option_strings}
        actual={o for a in build_arg_parser()._actions for o in a.option_strings}
        magic_only={'--graph','--ivar','--tag','--average','--magic-python-dir','--precision'}
        self.assertFalse(expected-actual-magic_only)
    def test_bundle_incremental_and_diagnostics(self):
        self.convert('--emf','--induction','--cmb-br-ltrunc','3')
        out=self.root/'bundle';validate_bundle(out)
        m=json.loads((out/'metadata.json').read_text())
        self.assertTrue(m['full_sphere']);self.assertEqual(m['r_inner'],0.)
        self.assertTrue({'Br','Bt','Bp','ur','ut','up','C','Comp','EMFr','Ir','helicity','grad_rC'} <= set(m['fields']))
        self.assertNotIn('C_nom0',m['fields'])
        saved={p.name:p.read_bytes() for p in out.glob('*.f32')}
        log=self.convert('--emf','--induction','--cmb-br-ltrunc','3')
        self.assertIn('skipped',log)
        (out/'Br_volume.f32').unlink()
        log=self.convert('--emf','--induction','--cmb-br-ltrunc','3')
        self.assertIn('Reuse calculation: synthesize_field',log)
        for name,b in saved.items():self.assertEqual((out/name).read_bytes(),b)
    def test_adding_diagnostics_reuses_synthesis(self):
        self.convert()
        log=self.convert('--emf','--induction')
        self.assertIn('Reuse calculation: synthesize_field',log)
        self.assertTrue((self.root/'bundle/Ir_volume.f32').is_file())
    def test_n2_scaling_requires_explicit_convention(self):
        self.convert()
        m=json.loads((self.root/'bundle/metadata.json').read_text())
        self.assertNotIn('N2_full',m['fields'])
        self.convert('--n2-convention','quicc-rotating','--RaC','0')
        m=json.loads((self.root/'bundle/metadata.json').read_text())
        shape=(m['nr'],m['ntheta'],m['nphi'])
        value=np.fromfile(self.root/'bundle/N2_full_volume.f32',dtype='<f4').reshape(shape)
        # C=1+r^2, E=.001, Ra=100, Pr=1 gives N2=0.2 r^2.
        r=np.asarray(json.loads((self.root/'bundle/coordinates.json').read_text())['r'])
        np.testing.assert_allclose(value,np.broadcast_to(.2*r[:,None,None]**2,shape),rtol=2e-5,atol=1e-6)
        self.convert('--n2-convention','deepscope','--Ek','.01','--RaC','0')
        changed=np.fromfile(self.root/'bundle/N2_full_volume.f32',dtype='<f4').reshape(shape)
        np.testing.assert_allclose(changed,value*.1,rtol=2e-5,atol=1e-6)

    def test_invalid_input_does_not_replace_bundle(self):
        self.convert();before=(self.root/'bundle/metadata.json').read_bytes()
        with h5py.File(self.state,'r+') as f:f['velocity/velocity_pol'][0,0]=complex(float('nan'),0)
        with self.assertRaisesRegex(ValueError,'nonfinite'):self.convert()
        self.assertEqual((self.root/'bundle/metadata.json').read_bytes(),before)
    def test_unknown_schema_and_incomplete_vector(self):
        with h5py.File(self.state,'r+') as f:f.attrs['type']=np.bytes_('TFF')
        with self.assertRaisesRegex(ValueError,'Unsupported QuICC scheme'):read_state(self.state)
        fixture(self.state)
        with h5py.File(self.state,'r+') as f:del f['Magnetic/MagneticTor']
        with self.assertRaisesRegex(ValueError,'Both poloidal'):read_state(self.state)
    def test_rejects_incompatible_geometry(self):
        for extra in (['--geometry','shell'],['--inner-core-only']):
            with self.assertRaises(ValueError):self.convert(*extra)
    def test_sequence_and_missing_indices(self):
        fixture(self.root/'state0002.hdf5','WLFl')
        args=['--folder',str(self.root),'--out',str(self.root/'sequence'),'--sequence-first','1',
              '--sequence-last','2','--incremental','--cache-dir',str(self.root/'cache'),'--skip-field-lines','--no-earth-br']
        with contextlib.redirect_stdout(io.StringIO()):main(args)
        validate_bundle(self.root/'sequence')
        index=json.loads((self.root/'sequence/sequence.json').read_text())
        self.assertEqual(len(index['frames']),2)
        with contextlib.redirect_stdout(io.StringIO()):main(args+['--emf'])
        self.assertTrue((self.root/'sequence/frames/state00002/EMFr_volume.f32').exists())
        opts=build_arg_parser().parse_args(args+['--sequence-last','3'])
        with self.assertRaisesRegex(ValueError,'Missing requested'):discover_states(opts)
    def test_small_grid_after_spectral_cutoff(self):
        self.convert('--spectral-lmax','1')
        m=json.loads((self.root/'bundle/metadata.json').read_text())
        self.assertEqual(m['spectral']['lmax'],1)


@unittest.skipUnless(os.environ.get('QUICC_BENCHMARK_DIR'),'Set QUICC_BENCHMARK_DIR for upstream reference data')
class UpstreamBenchmarkTests(unittest.TestCase):
    def test_native_kinetic_magnetic_and_temperature_energies(self):
        folder=Path(os.environ['QUICC_BENCHMARK_DIR'])
        state=read_state(folder/'state0000.hdf5');pairs=modes(state['lmax'],state['mmax'])
        x,w=np.polynomial.legendre.leggauss(64);r=(x+1)/2;rw=w/2*r*r
        x,tw=np.polynomial.legendre.leggauss(48);th=np.arccos(x[::-1]);ph=np.arange(96)*2*np.pi/96
        for name,stem in [('ur','kinetic'),('Br','magnetic'),('C','temperature')]:
            a=state['fields'][name]
            if name!='C':a=(a,state['fields']['utor' if name=='ur' else 'Btor'])
            values=synthesize_field(a,pairs,r,th,ph,state['lmax'])
            if name=='C':values=[values]
            energy=sum(np.einsum('r,t,rtp->',rw,tw[::-1],v*v)*2*np.pi/96/(4*np.pi/3) for v in values)
            if name!='C':energy/=2
            expected=np.loadtxt(folder/(stem+'_energy.dat'))[0,1]
            self.assertAlmostEqual(energy/expected,1.,places=11)


if __name__=='__main__':unittest.main()
