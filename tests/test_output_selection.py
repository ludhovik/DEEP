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

    def test_removing_m0_before_or_after_gradient_is_equivalent(self):
        r=np.linspace(.35,1.,8);theta=np.linspace(.15,np.pi-.15,10)
        phi=np.linspace(0,2*np.pi,16,endpoint=False)
        rr=r[:,None,None];th=theta[None,:,None];ph=phi[None,None,:]
        scalar=rr**2*np.cos(th)+rr*np.sin(th)*np.cos(2*ph)
        full=magic.gradient_scalar_3d(scalar,r,theta,phi)
        before=magic.gradient_scalar_3d(magic.remove_m0_phi(scalar),r,theta,phi)
        after=tuple(magic.remove_m0_phi(component) for component in full)
        for lhs,rhs in zip(before,after):
            np.testing.assert_allclose(lhs,rhs,rtol=2e-13,atol=2e-13)
        before_sz=cylindrical_gradient(before[0],before[1],theta)
        after_sz=tuple(magic.remove_m0_phi(component) for component in cylindrical_gradient(full[0],full[1],theta))
        for lhs,rhs in zip(before_sz,after_sz):
            np.testing.assert_allclose(lhs,rhs,rtol=2e-13,atol=2e-13)
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
            args.out=str(self.root/'selected');args.output=['ur','Br','T','vort_r','grad_rT']
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

    def test_explicit_zero_RaC_disables_composition_and_rejects_conflicting_outputs(self):
        args=magic.build_arg_parser().parse_args(['--RaC','0'])
        selection=OutputSelection(args)
        self.assertTrue(selection.composition_disabled)
        self.assertFalse(selection.needs('C'))
        self.assertTrue(selection.needs('T'))
        for name in ('C','C_nom0','C_phiavg','grad_rC','grad_zC_nom0'):
            args=magic.build_arg_parser().parse_args(['--RaC','0','--output',name])
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'--RaC 0 disables composition'):
                OutputSelection(args)

    def test_zero_RaC_full_export_is_thermal_only_and_incremental_removes_composition(self):
        out=self.root/'bundle'
        self.magic_run(out,extra=['--incremental'])
        original=self.meta(out)
        self.assertIn('C',original['fields'])
        (out/'view.DTV2').write_text('keep this view')
        log=self.magic_run(out,extra=['--incremental','--RaC','0'])
        metadata=self.meta(out)
        self.assertIn('Composition disabled',log)
        self.assertTrue(metadata['composition_disabled_by_RaC_zero'])
        self.assertIn('T',metadata['fields'])
        self.assertFalse(any(name in {'C','C_nom0','C_phiavg'} or
                             (name.startswith('grad_') and (name.endswith('C') or name.endswith('C_nom0')))
                             for name in metadata['fields']))
        self.assertFalse((out/'C_volume.f32').exists())
        self.assertEqual((out/'view.DTV2').read_text(),'keep this view')
        validate_bundle(out)
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
            self.assertTrue({'grad_sT','grad_zT','grad_sT_nom0','grad_zT_nom0'} <= set(self.meta(full)['fields']))
            thermal=self.root/f'thermal{index}'
            with contextlib.redirect_stdout(io.StringIO()):mod.main([*common,'--out',str(thermal),'--RaC','0'])
            thermal_meta=self.meta(thermal)
            self.assertTrue(thermal_meta['composition_disabled_by_RaC_zero'])
            self.assertIn('T',thermal_meta['fields'])
            self.assertFalse(set(thermal_meta['fields']) & {'C','C_nom0','C_phiavg','grad_rC','grad_zC_nom0'})
            names=['ur','Br','T','vort_r']
            with contextlib.redirect_stdout(io.StringIO()):mod.main([*common,'--out',str(out),'--output',*names])
            self.compare(full,out,names)
            with contextlib.redirect_stdout(io.StringIO()) as log:mod.main([*common,'--out',str(out),'--output','T'])
            self.compare(full,out,['T'])
            text=log.getvalue()
            self.assertNotIn('Synthesizing velocity',text);self.assertNotIn('Synthesizing magnetic',text)
            self.assertNotIn('Synthesizing ur',text);self.assertNotIn('Synthesizing Br',text)
            self.assertNotIn('Synthesizing Rayleigh ur',text);self.assertNotIn('Synthesizing Rayleigh Br',text)
            gradient_names=['grad_sT','grad_zT_nom0']
            if 'C' in self.meta(full)['fields']:gradient_names += ['grad_sC_nom0','grad_zC']
            with contextlib.redirect_stdout(io.StringIO()):
                mod.main([*common,'--out',str(out),'--output',*gradient_names])
            self.compare(full,out,gradient_names)
    def test_direct_selection_does_not_call_any_diagnostic(self):
        args=magic.build_arg_parser().parse_args(['--output','T'])
        raw={'T':np.ones((3,4,6))};r=np.arange(3)+1
        ops={k:mock.Mock(side_effect=AssertionError(k)) for k in ('gradient','curl','emf','helicity','mean','nom0','remap')}
        fields=selected_native_fields(OutputSelection(args),raw,{'T':r},np.arange(4),np.arange(6),{},args,operations=ops)
        self.assertEqual(set(fields),{'T'})
        for fn in ops.values():fn.assert_not_called()

if __name__=='__main__':unittest.main()
