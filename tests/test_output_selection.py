"""Selected fields match normal exports while unrelated transforms/diagnostics are skipped."""
from pathlib import Path
import argparse
import contextlib
import importlib
import io
import json
import sys
import tempfile
import types
import unittest
from unittest import mock
import numpy as np
import h5py
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import test_converter_package as fixtures
fixtures.ConverterPackageTests.setUpClass()
from tools.output_selection import OutputSelection,FIELDS,cylindrical_gradient,selected_native_fields
from tools import convert_magic_to_viewer as magic
from tools.conversion_cache import run_conversion
from tools.viewer_bundle import validate_bundle
from test_quicc_converter import fixture as quicc_fixture
from test_calypso_converter import make_run as calypso_fixture
from test_rayleigh_converter import fixture as rayleigh_fixture

class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def meta(self,out):return json.loads((out/'metadata.json').read_text())
    def compare(self,full,selected,names):
        m=self.meta(selected);self.assertEqual(set(m['fields']),set(names));self.assertEqual(set(m['ranges']),set(names))
        self.assertEqual(m['field_lines'],{});self.assertEqual(m['surface_fields'],{})
        self.assertEqual(set(p.name for p in selected.glob('*.f32')),{m['fields'][n] for n in names})
        for name in names:
            a=np.fromfile(selected/m['fields'][name],dtype='<f4');b=np.fromfile(full/self.meta(full)['fields'][name],dtype='<f4')
            np.testing.assert_allclose(a,b,rtol=2e-5,atol=2e-6,err_msg=name)
        validate_bundle(selected)

    def test_cylindrical_gradient_projection(self):
        theta=np.array([0.,np.pi/6,np.pi/2,5*np.pi/6,np.pi])
        gr=np.broadcast_to(np.array([2.])[:,None,None],(1,len(theta),3))
        gt=np.broadcast_to(np.array([3.])[:,None,None],gr.shape)
        gs,gz=cylindrical_gradient(gr,gt,theta)
        th=theta[None,:,None]
        np.testing.assert_allclose(gs,np.broadcast_to(2*np.sin(th)+3*np.cos(th),gr.shape),atol=1e-14)
        np.testing.assert_allclose(gz,np.broadcast_to(2*np.cos(th)-3*np.sin(th),gr.shape),atol=1e-14)
    def magic_run(self,out,outputs=None,extra=()):
        g=fixtures.ConverterPackageTests.fake_magic_graph();source=self.root/'G_1.test';source.write_text('fixture')
        args=magic.build_arg_parser().parse_args(['--graph',str(source),'--out',str(out),'--skip-field-lines','--no-earth-br','--no-parameter-prompt',
            '--cache-dir',str(self.root/'cache'),*extra,*(['--output',*outputs] if outputs else [])])
        adapted=magic.adapt_graph(g)
        native={k:getattr(g,k,None) for k in ('ek','pr','sc','ra','raxi','prmag','time','l_max')}
        with contextlib.redirect_stdout(io.StringIO()) as log:
            run_conversion(args,'magic',[source],lambda opts:magic.convert_adapted_snapshot(source,Path(opts.out),opts,adapted,native))
        return log.getvalue()
    def test_magic_examples_exact_fields_no_unrelated_diagnostics(self):
        full=self.root/'full';self.magic_run(full)
        out=self.root/'selected';names=['ur','Br','C','vort_r']
        with mock.patch.object(magic,'compute_helicity',side_effect=AssertionError('helicity')),mock.patch.object(magic,'gradient_scalar_3d',side_effect=AssertionError('gradients')),mock.patch.object(magic,'compute_emf',side_effect=AssertionError('EMF')),mock.patch.object(magic,'earth_surface_br',side_effect=AssertionError('Earth')):
            self.magic_run(out,names)
        self.compare(full,out,names)
    def test_each_supported_magic_field_matches_full_and_auxiliaries_are_private(self):
        full=self.root/'full';self.magic_run(full,extra=['--emf','--induction'])
        for name in self.meta(full)['fields']:
            with self.subTest(name=name):
                out=self.root/'one';self.magic_run(out,[name],['--emf','--induction'])
                self.compare(full,out,[name])
    def test_leeds_fullsphere_selection_preserves_regular_transform_and_centre(self):
        from tools import convert_leeds_to_viewer as leeds
        r=np.linspace(0,1,7);theta=np.arccos(np.linspace(.95,-.95,8));phi=np.arange(16)*np.pi/8
        shape=(len(r),len(theta),len(phi));rr=r[:,None,None];th=theta[None,:,None]
        coefficients=np.ones((2,6,len(r)));calls=[]
        backend=types.ModuleType('modules');backend.__file__=__file__
        def load(path):
            return dict(uP=coefficients,uT=coefficients,BP=coefficients,BT=coefficients,
                        C=coefficients,Comp=coefficients,r=r,lmax=2,mmax=2,t=1.)
        def vector(pol,tor,radius,lmax,mmax,**kwargs):
            calls.append(kwargs)
            # A uniform axial field plus solid-body rotation: finite Cartesian centre.
            return *(np.broadcast_to(v,shape).copy() for v in (np.cos(th),-np.sin(th),rr*np.sin(th))),theta,phi
        def scalar(coeff,radius,lmax,mmax,**kwargs):
            return np.broadcast_to(rr**2,shape).copy(),theta,phi
        def nom0(coeff,radius,lmax,mmax,**kwargs):return np.zeros(shape),theta,phi
        backend.load_state=load
        backend.PolTor_to_spat=backend.PolTor_to_spat_fullsphere=vector
        backend.SH_to_spat=backend.SH_to_spat_fullsphere=scalar
        backend.SH_to_spat_nom0=backend.SH_to_spat_nom0_fullsphere=nom0
        backend.gradient_spat=leeds.gradient_scalar_3d;backend.curl_spat=leeds.compute_induction_from_emf
        source=self.root/'state00001.cdf.dat';source.touch()
        reps={key:dict(representation='regular_r_power_g_x',power_offset=0,attribute_present=True)
              for key in ('uP','uT','BP','BT','C','Comp')}
        args=leeds.build_arg_parser().parse_args(['--state',str(source),'--out',str(self.root/'full'),
            '--skip-field-lines','--no-earth-br','--no-parameter-prompt','--geometry','full-sphere'])
        with contextlib.redirect_stdout(io.StringIO()),mock.patch.dict(sys.modules,{'modules':backend}), \
             mock.patch.object(leeds,'read_state_radial_representations',return_value=reps), \
             mock.patch.object(leeds,'read_netcdf_attributes',return_value={}):
            leeds.run_leeds_conversion(args)
            args.out=str(self.root/'selected');args.output=['ur','Br','C','vort_r','grad_rC_full']
            leeds.run_leeds_conversion(args)
        self.compare(self.root/'full',self.root/'selected',args.output)
        meta=self.meta(self.root/'selected');self.assertTrue(meta['full_sphere']);self.assertEqual(meta['r_inner'],0.)
        self.assertTrue(all(v['pol_regular_coefficients'] and v['tor_regular_coefficients'] for v in calls))

    def test_unavailable_field_preserves_previous_bundle(self):
        out=self.root/'selected';self.magic_run(out,['ur']);before=(out/'metadata.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'does not contain'):
            self.magic_run(out,['Phase'])
        self.assertEqual((out/'metadata.json').read_bytes(),before)
    def test_unknown_conflicts_and_flags(self):
        for options in (['--output','typo'],['--output','EMFr'],['--output','Ir'],
                        ['--output','ur','--inner-core-only'],['--output','grad_rC','--no-gradients']):
            args=magic.build_arg_parser().parse_args(['--graph','G_1.test',*options])
            with self.assertRaises(ValueError):OutputSelection(args)
        self.assertIsNone(OutputSelection(magic.build_arg_parser().parse_args([])).names)
    def test_selected_incremental_reuses_dependencies_and_updates_exact_inventory(self):
        out=self.root/'selected';self.magic_run(out,['vort_r'],['--incremental'])
        log=self.magic_run(out,['vort_r','vort_z'],['--incremental'])
        self.assertIn('Reuse calculation: compute_induction_from_emf',log)
        self.assertEqual(set(self.meta(out)['fields']),{'vort_r','vort_z'})
        log=self.magic_run(out,['vort_r','vort_z'],['--incremental']);self.assertIn('skipped',log)
        self.magic_run(out,['ur'],['--incremental']);self.assertFalse((out/'vort_r_volume.f32').exists())
    def test_native_quicc_calypso_rayleigh_skip_unselected_synthesis(self):
        cases=[]
        q=self.root/'state0001.hdf5';quicc_fixture(q,scheme='WLFl');cases.append(('convert_quicc_to_viewer',['--state',str(q)]))
        c=self.root/'calypso';calypso_fixture(c);cases.append(('tools.convert_calypso_to_viewer',['--folder',str(c)]))
        r=rayleigh_fixture(self.root/'rayleigh');cases.append(('convert_rayleigh_to_viewer',['--checkpoint',str(r)]))
        for index,(module,source) in enumerate(cases):
            mod=importlib.import_module(module);full=self.root/f'full{index}';out=self.root/f'out{index}'
            common=[*source,'--skip-field-lines','--no-earth-br','--no-parameter-prompt']
            with contextlib.redirect_stdout(io.StringIO()):mod.main([*common,'--out',str(full)])
            self.assertTrue({'grad_sC','grad_zC','grad_sC_full','grad_zC_full'} <= set(self.meta(full)['fields']))
            names=['ur','Br','C','vort_r']
            with contextlib.redirect_stdout(io.StringIO()):mod.main([*common,'--out',str(out),'--output',*names])
            self.compare(full,out,names)
            with contextlib.redirect_stdout(io.StringIO()) as log:mod.main([*common,'--out',str(out),'--output','C'])
            self.compare(full,out,['C'])
            text=log.getvalue()
            self.assertNotIn('Synthesizing velocity',text);self.assertNotIn('Synthesizing magnetic',text)
            self.assertNotIn('Synthesizing ur',text);self.assertNotIn('Synthesizing Br',text)
            self.assertNotIn('Synthesizing Rayleigh ur',text);self.assertNotIn('Synthesizing Rayleigh Br',text)
            gradient_names=['grad_sC_full','grad_zC']
            if 'Comp' in self.meta(full)['fields']:gradient_names += ['grad_sComp','grad_zComp_full']
            with contextlib.redirect_stdout(io.StringIO()):
                mod.main([*common,'--out',str(out),'--output',*gradient_names])
            self.compare(full,out,gradient_names)
    def test_direct_selection_does_not_call_any_diagnostic(self):
        args=magic.build_arg_parser().parse_args(['--output','C'])
        raw={'C':np.ones((3,4,6))};r=np.arange(3)+1
        ops={k:mock.Mock(side_effect=AssertionError(k)) for k in ('gradient','curl','emf','helicity','mean','nom0','remap')}
        fields=selected_native_fields(OutputSelection(args),raw,{'C':r},np.arange(4),np.arange(6),{},args,operations=ops)
        self.assertEqual(set(fields),{'C'})
        for fn in ops.values():fn.assert_not_called()

if __name__=='__main__':unittest.main()
