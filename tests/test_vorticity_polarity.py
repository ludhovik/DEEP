"""Physical curl and independently sampled local magnetic polarity."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from convert_state_to_viewer import vorticity_fields, annotate_line_radial_field
from conversion_cache import CalculationCache, _active_cache
from test_rayleigh_converter import fixture
from convert_rayleigh_to_viewer import main
from viewer_bundle import validate_bundle


class VorticityTests(unittest.TestCase):
    def grid(self, nt=96, centre=False):
        r=np.linspace(0 if centre else .5,1.5,12)**1.1
        t=np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1]);p=np.arange(2*nt)*np.pi/nt
        st,ct=np.sin(t)[None,:,None],np.cos(t)[None,:,None];sp,cp=np.sin(p)[None,None,:],np.cos(p)[None,None,:]
        return r,t,p,st,ct,sp,cp
    def rotation_error(self,nt,axis='z',centre=False):
        r,t,p,st,ct,sp,cp=self.grid(nt,centre)
        # Cartesian u = Omega cross x, independently projected to spherical.
        x,y,z=r[:,None,None]*st*cp,r[:,None,None]*st*sp,np.broadcast_to(r[:,None,None]*ct,(len(r),len(t),len(p)))
        om=np.eye(3)['xyz'.index(axis)]
        u=np.cross(om,np.stack([x,y,z],axis=-1));ux,uy,uz=np.moveaxis(u,-1,0)
        ur=ux*st*cp+uy*st*sp+uz*ct;ut=ux*ct*cp+uy*ct*sp-uz*st;up=-ux*sp+uy*cp
        w=vorticity_fields(ur,ut,up,r,t,p)
        xyz=np.stack([w['vort_r']*st*cp+w['vort_theta']*ct*cp-w['vort_phi']*sp,
                      w['vort_r']*st*sp+w['vort_theta']*ct*sp+w['vort_phi']*cp,
                      w['vort_z']],axis=-1)
        self.assertTrue(all(np.isfinite(a).all() for a in w.values()))
        if centre:
            self.assertLess(np.max(np.ptp(xyz[0],axis=(0,1))),1e-12)
        return np.sqrt(np.mean((xyz-2*om)**2))
    def test_solid_rotation_all_axes_and_nonzero_centre(self):
        for axis in 'xyz':
            for centre in (False,True):self.assertLess(self.rotation_error(128,axis,centre),.003)
    def test_second_order_convergence(self):
        coarse=self.rotation_error(32);fine=self.rotation_error(64)
        self.assertGreater(coarse/fine,3.3)
    def test_irrotational_radial_flow_and_units(self):
        r,t,p,*_=self.grid();shape=(len(r),len(t),len(p));zero=np.zeros(shape)
        ur=np.broadcast_to(r[:,None,None]**2,shape)
        for a in vorticity_fields(ur,zero,zero,r,t,p).values():np.testing.assert_allclose(a,0,atol=1e-10)
        up=np.broadcast_to(r[:,None,None]*np.sin(t)[None,:,None],shape)
        base=vorticity_fields(zero,zero,up,r,t,p)
        scaled=vorticity_fields(zero,zero,3*up,2*r,t,p)
        for name in base:np.testing.assert_allclose(scaled[name],1.5*base[name],atol=1e-10)
    def test_reject_nonfinite_velocity(self):
        r,t,p,*_=self.grid(8);v=np.ones((len(r),len(t),len(p)));v[4,4,4]=np.nan
        with self.assertRaises(ValueError):vorticity_fields(v,v,v,r,t,p)
    def test_polarity_along_closed_arc_and_reversed_storage(self):
        r=np.linspace(1,4,12);t=np.linspace(.05,np.pi-.05,129);p=np.arange(32)*np.pi/16
        br=np.broadcast_to(2*np.cos(t)[None,:,None]/r[:,None,None]**3,(len(r),len(t),len(p)))
        th=np.linspace(.4,np.pi-.4,51);rr=3*np.sin(th)**2;rr=np.maximum(rr,1)
        points=np.column_stack([rr*np.sin(th),np.zeros(len(th)),rr*np.cos(th)]).tolist()
        original={'points':points,'polarity':1,'line_id':'one'}
        forward=annotate_line_radial_field([original],br,r,t,p)[0]
        backward=annotate_line_radial_field([{**original,'points':points[::-1]}],br,r,t,p)[0]
        self.assertNotIn('radial_field',original)
        self.assertGreater(forward['radial_field'][0],0);self.assertLess(forward['radial_field'][-1],0)
        np.testing.assert_allclose(forward['radial_field'],backward['radial_field'][::-1])
        reversed_B=annotate_line_radial_field([original],-br,r,t,p)[0]
        np.testing.assert_allclose(reversed_B['radial_field'],-np.asarray(forward['radial_field']))
    def test_polarity_unknown_is_null_not_positive(self):
        r,t,p,*_=self.grid(8,True);br=np.ones((len(r),len(t),len(p)))
        values=annotate_line_radial_field([{'points':[[0,0,0],[99,0,0],[1,0,0]]}],br,r,t,p)[0]['radial_field']
        self.assertEqual(values,[None,None,1.])
        json.dumps(values,allow_nan=False)
    def test_incremental_annotation_does_not_mutate_cached_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=CalculationCache(tmp,{'test':'local-Br'});token=_active_cache.set(cache)
            try:
                r,t,p,*_=self.grid(8);br=np.ones((len(r),len(t),len(p)));lines=[{'points':[[1,0,0],[1.1,0,0]]}]
                a=annotate_line_radial_field(lines,br,r,t,p);b=annotate_line_radial_field(lines,br,r,t,p)
                self.assertEqual(a,b);self.assertEqual(cache.hits,1);self.assertNotIn('radial_field',lines[0])
            finally:_active_cache.reset(token)
    def test_export_incremental_and_fluid_domain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=fixture(root/'input')
            args=['--checkpoint',str(state),'--out',str(root/'out'),'--incremental','--cache-dir',str(root/'cache'),'--skip-field-lines','--no-earth-br']
            with contextlib.redirect_stdout(io.StringIO()):main(args)
            m=json.loads((root/'out/metadata.json').read_text())
            for name in ('vort_r','vort_theta','vort_phi','vort_s','vort_z','vort_abs'):
                self.assertIn(name,m['fields']);self.assertEqual(m['field_domains'][name]['r_min'],.5)
            validate_bundle(root/'out')
            log=io.StringIO()
            with contextlib.redirect_stdout(log):main(args+['--emf'])
            self.assertIn('Reuse calculation: vorticity_fields',log.getvalue())
            self.assertIn('Reuse calculation: synthesize_checkpoint',log.getvalue())

if __name__=='__main__':unittest.main()
