"""Analytic two-patch volumes test geometry, vector rotation and diagnostics."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools import convert_stagyy_to_viewer as converter
from tools.stagyy_data import read_header, read_volume, YinYangSampler
from tools.viewer_bundle import validate_bundle

try:
    from stagpy.parsers.bin import field as stagpy_field
except ImportError:
    stagpy_field = None


def write_fixture(root, index=0, time=2.5, offset=0, composition=True, precision=4, poison_corners=False):
    """Write a decomposed legacy stream independently of the StagPy reader.

    T=z+offset, C=x, velocity=(1,2,3), eta=100, P=7 on both patches.
    Vector ghost rows are deliberately junk, to catch accidental inclusion.
    """
    nx,ny,nz = 32,96,6
    x = (np.arange(nx)+.5)*np.pi/(2*nx)
    y = (np.arange(ny)+.5)*3*np.pi/(2*ny)
    zedge = np.linspace(0,1,nz+1)**1.3
    z = (zedge[1:]+zedge[:-1])/2
    r = 1.2+z
    t,p = x[:,None,None]+np.pi/4,y[None,:,None]-3*np.pi/4
    st,ct,sp,cp = np.sin(t),np.cos(t),np.sin(p),np.cos(p)
    xyz = np.stack(np.broadcast_arrays(r*st*cp,r*st*sp,r*ct),axis=-1)
    yang = np.stack((-xyz[...,0],xyz[...,2],xyz[...,1]),axis=-1)
    def local_velocity(u):
        ux,uy,uz = u
        vt=ux*ct*cp+uy*ct*sp-uz*st
        vp=-ux*sp+uy*cp+np.zeros_like(st)
        vr=ux*st*cp+uy*st*sp+uz*ct
        return np.stack([np.broadcast_to(a,(nx,ny,nz)) for a in (vt,vp,vr)],axis=0)
    vp = np.full((4,nx+1,ny+1,nz,2),-999.)
    vp[:3,:nx,:ny,:,0] = local_velocity((1,2,3))
    vp[:3,:nx,:ny,:,1] = local_velocity((-1,3,2))
    vp[3,:nx,:ny,:,:] = 7
    temp = np.stack((xyz[...,2]+offset,yang[...,2]+offset),axis=-1)[None]
    if poison_corners:
        # Independent Cartesian form of the reference exporter's corner cut.
        # These unused values must never affect the physical stitched sphere.
        ux,uy = st*cp,st*sp
        redundant = ((ux < 0) & (np.abs(uy) < 1/np.sqrt(2)))[:,:,0]
        temp[0][redundant] = -1000
    fields = {'t':temp,'eta':np.full_like(temp,100.),'vp':vp}
    if composition:
        fields['c'] = np.stack((xyz[...,0],yang[...,0]),axis=-1)[None]
    for suffix,data in fields.items():
        path = root/f'test_{suffix}{index:05d}'
        with path.open('wb') as f:
            def ints(v):np.asarray(v,dtype=f'<i{precision}').tofile(f)
            def floats(v):np.asarray(v,dtype=f'<f{precision}').tofile(f)
            ints([(409 if suffix=='vp' else 9)+(8000 if precision==8 else 0),nx,ny,nz,2])
            floats([np.pi/2,3*np.pi/2]);ints([2,2,2,2])
            radial = np.empty(2*nz+1);radial[::2]=zedge;radial[1::2]=z
            floats(radial);floats([1.2]);ints([int(time*100)]);floats([time,0,1])
            floats(x);floats(y);floats(z)
            if suffix=='vp':floats([2])
            ghost = int(suffix=='vp')
            for b in range(2):
                for k in range(2):
                    for j in range(2):
                        for i in range(2):
                            block=data[:,i*16:(i+1)*16+ghost,j*48:(j+1)*48+ghost,k*3:(k+1)*3,b:b+1]
                            floats(block.transpose(4,3,2,1,0)/(2 if suffix=='vp' else 1))
    return root/f'test_t{index:05d}'


@unittest.skipIf(stagpy_field is None,'Install requirements-stagyy.txt')
class StagYYTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=write_fixture(self.root)
        self.out=self.root/'output'
        self.options=['--input',str(self.source),'--out',str(self.out),'--ntheta','40','--nphi','80','--composition-suffix','c']

    def tearDown(self):self.tmp.cleanup()

    def run_converter(self,*extra,options=None):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            converter.main((options or self.options)+list(extra))
        return stream.getvalue()

    def volume(self,name):
        m=json.loads((self.out/'metadata.json').read_text())
        return np.fromfile(self.out/m['fields'][name],dtype='<f4').reshape(m['nr'],m['ntheta'],m['nphi'])

    def test_two_patch_scalar_vectors_transport_and_native_time(self):
        self.run_converter();validate_bundle(self.out)
        m=json.loads((self.out/'metadata.json').read_text())
        c=json.loads((self.out/'coordinates.json').read_text())
        r,t,p=(np.asarray(c[k]) for k in ('r','theta','phi'))
        expected=r[:,None,None]*np.cos(t)[None,:,None]+np.zeros((1,1,len(p)))
        np.testing.assert_allclose(self.volume('T'),expected,atol=.0015)
        np.testing.assert_allclose(self.volume('log10_eta'),2,atol=1e-6)
        np.testing.assert_allclose(self.volume('P'),7,atol=1e-6)
        np.testing.assert_allclose(self.volume('Uabs'),np.sqrt(14),atol=2e-6)
        np.testing.assert_allclose(self.volume('uz'),3,atol=2e-6)
        # The regular-grid derivative amplifies interpolation error near the
        # poles; bound both the worst error (<2%) and whole-volume RMS.
        np.testing.assert_allclose(self.volume('advT'),3,atol=.06)
        self.assertLess(np.sqrt(np.mean((self.volume('advT')-3)**2)),.01)
        np.testing.assert_allclose(self.volume('advC'),1,atol=.02)
        self.assertIn('dthetaT_phiavg',m['fields']);self.assertIn('dthetaC_phiavg',m['fields'])
        np.testing.assert_allclose(self.volume('dzup_phiavg'),0,atol=1e-7)
        self.assertEqual(m['time'],2.5);self.assertEqual(m['time_step'],250)
        self.assertGreater(m['r_outer'],2)
        self.assertEqual(m['boundary_labels']['outer'],'Near surface')
        self.assertFalse(m['magnetic']['has_magnetic_field'])

    def test_precision_and_decomposition(self):
        source=write_fixture(self.root,index=1,precision=8)
        h,a=read_volume(source);_,b=read_volume(self.source)
        np.testing.assert_allclose(a,b,atol=2e-7)
        self.assertEqual(a.shape,(1,32,96,6,2))
        self.assertEqual(h['ti_ad'],2.5)

    def test_redundant_corner_values_cannot_create_meridional_anomaly_bands(self):
        self.run_converter('--output','T','T_anomaly','advT')
        clean={name:self.volume(name) for name in ('T','T_anomaly','advT')}
        write_fixture(self.root,poison_corners=True)
        self.run_converter('--output','T','T_anomaly','advT')
        for name,values in clean.items():
            # Includes all meridian longitudes, not only the coordinate planes
            # where the overlap has zero width and the old bug was invisible.
            np.testing.assert_array_equal(self.volume(name),values)

    def test_truncated_extra_and_wrong_endian_fail_before_allocation(self):
        original=self.source.read_bytes()
        for damaged in (original[:-4],original+b'1234',b'\x00\x00\x00\x09'+original[4:]):
            self.source.write_bytes(damaged)
            with self.assertRaises(ValueError):read_header(self.source)

    def test_companion_time_mismatch_does_not_replace_existing_output(self):
        self.run_converter('--output','T')
        before=(self.out/'metadata.json').read_bytes()
        write_fixture(self.root,index=1,time=8)
        (self.root/'test_eta00000').write_bytes((self.root/'test_eta00001').read_bytes())
        with self.assertRaisesRegex(ValueError,'snapshot/grid mismatch'):
            self.run_converter()
        self.assertEqual((self.out/'metadata.json').read_bytes(),before)

    def test_selected_fields_and_incremental(self):
        self.run_converter('--output','T','log10_eta','advC','--incremental')
        self.assertEqual(set(json.loads((self.out/'metadata.json').read_text())['fields']),{'T','log10_eta','advC'})
        before=(self.out/'metadata.json').stat().st_mtime_ns
        self.run_converter('--output','T','log10_eta','advC','--incremental')
        self.assertEqual(before,(self.out/'metadata.json').stat().st_mtime_ns)
        with self.assertRaisesRegex(ValueError,'Unavailable'):
            self.run_converter('--no-velocity','--output','advT')

    def test_sequences_saved_times_and_shared_coordinates(self):
        second=write_fixture(self.root,index=1,time=5,offset=1)
        options=self.options.copy();options[1:2]=[str(second),str(self.source)]
        self.run_converter(options=options);validate_bundle(self.out)
        sequence=json.loads((self.out/'sequence.json').read_text())
        self.assertEqual([f['time'] for f in sequence['frames']],[2.5,5])
        self.assertEqual((self.out/'frames/frame00000/coordinates.json').read_bytes(),(self.out/'frames/frame00001/coordinates.json').read_bytes())

    def test_no_radial_extrapolation(self):
        h=read_header(self.source)
        with self.assertRaisesRegex(ValueError,'outside the saved cell centres'):
            YinYangSampler(h,np.array([1.,2.]),np.linspace(.1,3.,20),np.linspace(0,6.,40))


if __name__ == '__main__':unittest.main()
