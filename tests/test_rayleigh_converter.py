"""Rayleigh binary contracts, analytic vector reconstruction and shared export."""
from pathlib import Path
import contextlib
import io
import json
import math
import os
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rayleigh_data import read_grid, read_coefficients, read_volume, synthesize_checkpoint, radial_basis
from convert_rayleigh_to_viewer import main
from viewer_bundle import validate_bundle


def fixture(root, step=1, order='<', ri=.5, axis='z', magnetic=True):
    path=root/f'{step:08d}';path.mkdir(parents=True,exist_ok=True)
    nr=12;lmax=3;nt=8
    x=np.cos(np.pi*(np.arange(nr)+.5)/nr)
    a=(1.5-ri)/(x[0]-x[-1]);b=1.5-a*x[0];r=a*x+b;r[-1]=ri
    with (path/'grid_etc').open('wb') as f:
        np.array([314,2,nr,2,lmax],dtype=order+'i4').tofile(f)
        np.array([.001,.001,*r,.1*step],dtype=order+'f8').tofile(f)
        np.array([step],dtype=order+'i4').tofile(f)
    (path/'main_input').write_text('&problem\n n_theta=8, reference_type=1,\n ekman_number=1d-3, prandtl_number=1, rayleigh_number=1d5\n/\n')
    nm=(lmax+1)*(lmax+2)//2;pairs=[(l,m) for m in range(lmax+1) for l in range(m,lmax+1)]
    def coeff(values):
        c=np.polynomial.chebyshev.chebfit(x,values,nr-1);c[0]*=2;return c
    zero=np.zeros((nr,nm),complex)
    z=zero.copy();z[:,pairs.index((1,0))]=coeff(r*r/math.sqrt(3/(4*math.pi)))
    c=zero.copy()
    if axis=='z':c[:,pairs.index((1,0))]=coeff(r*r/(2*math.sqrt(3/(4*math.pi))))
    else:c[:,pairs.index((1,1))]=coeff(r*r/(2*math.sqrt(3/(8*math.pi))))*(-1 if axis=='x' else 1j)
    thermal=zero.copy();thermal[:,0]=coeff((1+r*r)*math.sqrt(4*math.pi))
    fields={'W':zero,'Z':z,'T':thermal,'P':thermal*.1,'Xa001':thermal*2}
    if magnetic:fields.update(C=c,A=zero)
    for name,values in fields.items():
        np.stack([values.real,values.imag]).astype(order+'f8').tofile(path/name)
    with (path/'equation_coefficients').open('wb') as f:
        np.array([314,2,11,14,*([1]*25)],dtype=order+'i4').tofile(f)
        np.ones(11,dtype=order+'f8').tofile(f)
        np.array([nr],dtype=order+'i4').tofile(f)
        r.astype(order+'f8').tofile(f)
        functions=np.ones((14,nr));functions[0]=2
        functions.astype(order+'f8').tofile(f)
    return path


def physical_fixture(root,step=1,order='<'):
    root.mkdir(parents=True,exist_ok=True);nr,nt,np_=8,10,20
    r=np.linspace(1.5,.5,nr);theta=np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1]);phi=np.arange(np_)*2*np.pi/np_
    grid=root/f'{step:08d}_grid'
    with grid.open('wb') as f:
        np.array([314,nr,nt,np_],dtype=order+'i4').tofile(f)
        np.r_[r,theta].astype(order+'f8').tofile(f)
    shape=(nr,nt,np_)
    values={1:np.zeros(shape),2:np.zeros(shape),3:np.broadcast_to(r[:,None,None]*np.sin(theta)[None,:,None],shape),
            501:np.broadcast_to(1+r[:,None,None]**2+.2*np.polynomial.legendre.legval(np.cos(theta),[0,0,0,0,1])[None,:,None],shape)}
    for code,v in values.items():v.astype(order+'f8').tofile(root/f'{step:08d}_{code:05d}')
    return grid,values


class RayleighTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.state=fixture(self.root/'checkpoints')
    def tearDown(self):self.tmp.cleanup()
    def convert(self,*options,state=None):
        log=io.StringIO()
        with contextlib.redirect_stdout(log):
            main(['--state',str(state or self.state),'--out',str(self.root/'out'),
                  '--incremental','--cache-dir',str(self.root/'cache'),'--skip-field-lines','--no-earth-br',*options])
        return log.getvalue()
    def metadata(self):return json.loads((self.root/'out/metadata.json').read_text())
    def volume(self,name):
        m=self.metadata();return np.fromfile(self.root/'out'/f'{name}_volume.f32',dtype='<f4').reshape(m['nr'],m['ntheta'],m['nphi'])
    def test_scalar_vectors_both_endians_and_centre(self):
        for order in ['<','>']:
            for ri in [0,.5]:
                for axis in 'xyz':
                    path=fixture(self.root/'checkpoints',order=order,ri=ri,axis=axis)
                    g=read_grid(path/'grid_etc',True);r,th,ph=g['r'],g['theta'],g['phi']
                    read=lambda name:read_coefficients(path/name,len(r),g['lmax'],order)
                    B=synthesize_checkpoint(read('C'),r,3,3,th,ph,read('A'))
                    st,ct=np.sin(th)[None,:,None],np.cos(th)[None,:,None];sp,cp=np.sin(ph)[None,None,:],np.cos(ph)[None,None,:]
                    xyz=(B[0]*st*cp+B[1]*ct*cp-B[2]*sp,B[0]*st*sp+B[1]*ct*sp+B[2]*cp,B[0]*ct-B[1]*st)
                    for name,value in zip('xyz',xyz):np.testing.assert_allclose(value,float(name==axis),atol=2e-11)
                    u=synthesize_checkpoint(read('W'),r,3,3,th,ph,read('Z'),np.full(len(r),2.))
                    np.testing.assert_allclose(u[:2],0,atol=1e-12)
                    np.testing.assert_allclose(u[2],np.broadcast_to(r[:,None,None]*st/2,u[2].shape),atol=2e-11)
                    scalar=synthesize_checkpoint(read('T'),r,3,3,th,ph)
                    np.testing.assert_allclose(scalar,np.broadcast_to(1+r[:,None,None]**2,scalar.shape),atol=1e-12)
    def test_physical_layout_endian_and_strict_sizes(self):
        for order in ['<','>']:
            path,values=physical_fixture(self.root/'physical',order=order);g=read_grid(path)
            got=read_volume(path.parent/'00000001_00003',values[3].shape,order)
            np.testing.assert_array_equal(got,values[3]);self.assertTrue(math.isnan(g['time']))
            with (path.parent/'00000001_00003').open('ab') as f:f.write(b'bad')
            with self.assertRaisesRegex(ValueError,'size'):read_volume(path.parent/'00000001_00003',values[3].shape,order)
    def test_checkpoint_export_and_incremental_addition(self):
        self.convert('--composition-field','Xa001')
        m=self.metadata();self.assertEqual(m['source_code'],'Rayleigh');self.assertEqual(m['time'],.1)
        self.assertFalse(m['full_sphere']);self.assertEqual(m['r_icb'],.5)
        self.assertFalse((self.root/'out/N2_volume.f32').exists())
        np.testing.assert_allclose(self.volume('Comp'),2*self.volume('C'))
        self.assertFalse((self.root/'out/C_nom0_volume.f32').exists());validate_bundle(self.root/'out')
        log=self.convert('--composition-field','Xa001','--emf','--induction')
        self.assertIn('Reuse calculation: synthesize_checkpoint',log)
        self.assertTrue((self.root/'out/Ir_volume.f32').exists())
        self.assertIn('skipped',self.convert('--composition-field','Xa001','--emf','--induction'))
    def test_physical_export_truncation_and_unknown_time(self):
        path,_=physical_fixture(self.root/'physical')
        self.convert(state=path);m=self.metadata();self.assertIsNone(m['time']);self.assertEqual(m['ntheta'],10)
        size=(self.root/'out/C_volume.f32').stat().st_size
        self.convert('--spectral-lmax','2',state=path);m=self.metadata()
        self.assertEqual(m['spectral']['lmax'],2);self.assertEqual(m['ntheta'],4)
        self.assertLess((self.root/'out/C_volume.f32').stat().st_size,size)
        c=self.volume('C');np.testing.assert_allclose(c,np.broadcast_to(c[:,:1,:1],c.shape),atol=1e-6)
        validate_bundle(self.root/'out')
    def test_checkpoint_spectral_truncation(self):
        self.convert();original=self.volume('C');self.assertEqual(original.shape,(12,8,16))
        self.convert('--spectral-lmax','1');m=self.metadata()
        self.assertEqual(m['spectral']['lmax'],1);self.assertEqual(self.volume('C').shape,(12,4,8))
        np.testing.assert_allclose(self.volume('C')[:,0,0],original[:,0,0],atol=1e-6)
    def test_n2_is_explicit_and_requires_parameters(self):
        self.convert('--n2-convention','deepscope');m=self.metadata()
        r=np.asarray(json.loads((self.root/'out/coordinates.json').read_text())['r'])
        np.testing.assert_allclose(self.volume('N2_full'),np.broadcast_to(.2*r[:,None,None]**2,self.volume('C').shape),atol=2e-6)
        with self.assertRaisesRegex(ValueError,'N2 for Comp'):self.convert('--n2-convention','deepscope','--composition-field','Xa001')
    def test_incomplete_vectors_preserve_previous_bundle(self):
        self.convert();before=(self.root/'out/metadata.json').read_bytes()
        (self.state/'A').unlink()
        with self.assertRaisesRegex(ValueError,'Incomplete vector'):self.convert()
        self.assertEqual((self.root/'out/metadata.json').read_bytes(),before)
    def test_density_is_not_guessed_and_source_changes_invalidate(self):
        self.convert();u=self.volume('up').copy();(self.state/'equation_coefficients').unlink()
        with self.assertRaisesRegex(ValueError,'mass flux'):self.convert()
        self.convert('--constant-density','1');np.testing.assert_allclose(self.volume('up'),2*u,atol=1e-6)
        (self.state/'T').write_bytes((self.state/'T').read_bytes()[:-8])
        with self.assertRaisesRegex(ValueError,'checkpoint size'):self.convert('--constant-density','1')
    def test_unsupported_grids_and_physics_fail_clearly(self):
        bad=self.root/'archive.zip';bad.write_bytes(b'PK')
        with self.assertRaisesRegex(ValueError,'archive'):self.convert(state=bad)
        g=read_grid(self.state/'grid_etc',True);r=g['r'].copy();r[4]+=.001
        with self.assertRaisesRegex(ValueError,'single-domain'):radial_basis(r)
        with (self.state/'main_input').open('a') as f:f.write('\n pseudo_incompressible=.true.\n')
        with self.assertRaisesRegex(ValueError,'pseudo-incompressible'):self.convert()
    def test_sequence_and_missing_step(self):
        fixture(self.root/'checkpoints',step=2)
        opts=['--folder',str(self.root/'checkpoints'),'--sequence-first','1','--sequence-last','2',
              '--out',str(self.root/'seq'),'--incremental','--cache-dir',str(self.root/'cache'),
              '--skip-field-lines','--no-earth-br']
        with contextlib.redirect_stdout(io.StringIO()):main(opts)
        seq=json.loads((self.root/'seq/sequence.json').read_text());self.assertEqual([f['time'] for f in seq['frames']],[.1,.2])
        validate_bundle(self.root/'seq')
        opts[opts.index('--sequence-last')+1]='3'
        with self.assertRaisesRegex(ValueError,'Missing snapshot'):main(opts)
    def test_full_sphere_export(self):
        fixture(self.root/'checkpoints',ri=0)
        self.convert();m=self.metadata();self.assertTrue(m['full_sphere']);self.assertEqual(m['r_icb'],0)
        validate_bundle(self.root/'out')
    def test_magnetic_lines_use_shared_pairing_pipeline(self):
        # Remove --skip-field-lines by calling main directly.
        with contextlib.redirect_stdout(io.StringIO()):
            main(['--checkpoint',str(self.state),'--out',str(self.root/'lines'),'--no-earth-br',
                  '--field-line-mode','both','--line-seeds','36','--external-nr','32',
                  '--external-rmax','8','--line-max-steps','1000','--external-lmax','3'])
        validate_bundle(self.root/'lines')
        lines=json.loads((self.root/'lines/B_lines.json').read_text())
        self.assertTrue(lines)
        external=json.loads((self.root/'lines/B_lines_exterior_poloidal.json').read_text())
        self.assertGreater(len(external),0)
        internal=json.loads((self.root/'lines/B_lines_shell.json').read_text())
        for arc in external:
            paired=[line for line in internal if line.get('line_id') in (arc.get('paired_shell_line_id'),arc.get('paired_shell_return_line_id'))]
            self.assertGreaterEqual(len(paired),2)
            for endpoint in (arc['points'][0],arc['points'][-1]):
                self.assertLess(min(np.linalg.norm(np.asarray(endpoint)-np.asarray(point)) for line in paired for point in (line['points'][0],line['points'][-1])),1e-7)
        self.assertTrue((self.root/'lines/B_lines_shell.json').exists())
        self.assertTrue((self.root/'lines/B_lines_exterior_poloidal.json').exists())


@unittest.skipUnless(os.environ.get('RAYLEIGH_BENCHMARK_DIR'),'optional official Rayleigh benchmark download')
class PublishedBenchmarkTests(unittest.TestCase):
    def test_christensen_case_zero_kinetic_energy(self):
        # Independent radial quadrature and angular orthogonality; does not call synthesis.
        p=Path(os.environ['RAYLEIGH_BENCHMARK_DIR'])/'Checkpoints/00040000'
        g=read_grid(p/'grid_etc',True);r=g['r'];n=len(r);lm=g['lmax']
        roots=np.cos(np.pi*(np.arange(n)+.5)/n);a=(r[0]-r[-1])/(roots[0]-roots[-1]);b=r[0]-a*roots[0]
        x,w=np.polynomial.legendre.leggauss(96);rq=(r[0]+r[-1])/2+(r[0]-r[-1])/2*x;w*=.5*(r[0]-r[-1]);xq=(rq-b)/a
        co=[]
        for name in ['W','Z']:
            c=read_coefficients(p/name,n,lm,g['endian']).copy();c[0]*=.5;co.append(c)
        pq=np.polynomial.chebyshev.chebval(xq,co[0]).T;tq=np.polynomial.chebyshev.chebval(xq,co[1]).T
        dp=np.polynomial.chebyshev.chebval(xq,np.polynomial.chebyshev.chebder(co[0])).T/a
        pairs=[(l,m) for m in range(lm+1) for l in range(m,lm+1)]
        ell=np.array([l for l,m in pairs]);mult=np.array([1 if m==0 else .5 for l,m in pairs]);ll=ell*(ell+1)
        energy=.5*np.sum(w[:,None]*mult*(ll**2*abs(pq)**2/rq[:,None]**2+ll*(abs(dp)**2+abs(tq)**2)))/(4*np.pi/3*(r[0]**3-r[-1]**3))
        self.assertLess(abs(energy/58.348-1),1e-5)


if __name__=='__main__':unittest.main()
