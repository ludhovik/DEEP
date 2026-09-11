"""Native parameter ingestion and prompt parity; no folder-name inference."""
import argparse
import contextlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
import h5py
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import converter_parameters as cp
from tools import convert_leeds_to_viewer as leeds
from tools import conversion_cache as cache

try:
    from netCDF4 import Dataset
except ImportError:
    Dataset = None

NATIVE = dict(E=3e-5, Ra=110000000., Ra_comp=22000000., Pr=1., Sc=10., Pm=5.,
              Ro=6e-6, q=5., riro=.01, t=16.4489153639252, LSD_version='v4.1.0')

class ParameterTests(unittest.TestCase):
    def args(self, **kw):return argparse.Namespace(no_parameter_prompt=False, **kw)
    def quiet(self, native, args):
        with contextlib.redirect_stdout(io.StringIO()): return cp.resolve_parameters(native,args)

    @unittest.skipIf(Dataset is None, "optional netCDF4 fixture writer is unavailable")
    def test_leeds_netcdf4_and_classic_read_attributes_not_folder_tokens(self):
        from netCDF4 import Dataset
        with tempfile.TemporaryDirectory(prefix='Ek=999_RaC=999_') as folder:
            for fmt in ('NETCDF4','NETCDF3_CLASSIC'):
                path=Path(folder)/f'{fmt}.cdf.dat'
                with Dataset(path,'w',format=fmt) as f:
                    for key,value in NATIVE.items():f.setncattr(key,value)
                values=leeds.resolve_parameter_values(path,self.args())
                for key,want in dict(Ek=3e-5,RaT=110000000.,RaC=22000000.,Pm=5.,Ro=6e-6,q=5.,radius_ratio=.01).items():
                    self.assertAlmostEqual(values[key],want)
                self.assertNotIn('t',values)

    @unittest.skipIf(Dataset is None, "optional netCDF4 fixture writer is unavailable")
    def test_attribute_reader_fallback_without_netcdf4_package(self):
        from netCDF4 import Dataset
        with tempfile.TemporaryDirectory() as folder:
            for fmt in ('NETCDF4','NETCDF3_CLASSIC'):
                path=Path(folder)/fmt
                with Dataset(path,'w',format=fmt) as f:f.setncattr('Ra_comp',22e6)
                with mock.patch.dict(sys.modules,{'netCDF4':None}):
                    self.assertEqual(cp.read_netcdf_attributes(path)['Ra_comp'],22e6)

    def test_only_missing_values_prompt_and_cli_wins(self):
        native={**NATIVE};del native['Sc'];del native['Pm']
        args=self.args(Ek=2e-5)
        with mock.patch.object(sys,'stdin',io.StringIO()) as stdin, mock.patch('builtins.input',side_effect=['7','2']) as ask:
            stdin.isatty=lambda:True
            values=self.quiet(native,args)
        self.assertEqual(ask.call_count,2);self.assertEqual(values['Sc'],7);self.assertEqual(values['Pm'],2)
        self.assertEqual(values['Ek'],2e-5);self.assertEqual(values['RaC'],22e6)
        self.assertEqual(args._parameter_sources['Ek'],'command_line');self.assertEqual(args._parameter_sources['Sc'],'prompt')

    def test_noninteractive_or_disabled_prompt_keeps_unknown_and_zero_is_not_missing(self):
        for disabled in (False,True):
            args=self.args();args.no_parameter_prompt=disabled
            with mock.patch.object(sys,'stdin',io.StringIO()) as stdin, mock.patch('builtins.input',side_effect=AssertionError('prompt')):
                stdin.isatty=lambda:disabled
                values=self.quiet({'Ra_comp':0,'Pm':0},args)
            self.assertEqual(values['RaC'],0);self.assertEqual(values['Pm'],0);self.assertTrue(math.isnan(values['Ek']))

    def test_prompt_validation_fortran_exponents_blank_and_eof(self):
        with contextlib.redirect_stdout(io.StringIO()) as out, mock.patch('builtins.input',side_effect=['bad','inf','1D-4']):
            self.assertEqual(cp.prompt_parameter('Ek','Ekman'),1e-4)
        self.assertEqual(out.getvalue().count('blank = unknown:\n'),3)
        with contextlib.redirect_stdout(io.StringIO()),mock.patch('builtins.input',return_value=''):
            self.assertIsNone(cp.prompt_parameter('Pm','magnetic'))
        with contextlib.redirect_stdout(io.StringIO()),mock.patch('builtins.input',side_effect=EOFError):
            self.assertIsNone(cp.prompt_parameter('Pm','magnetic'))

    def test_sequence_answers_are_fallbacks_not_overrides_of_later_native_values(self):
        args=self.args();native={**NATIVE};del native['Pm']
        with mock.patch.object(sys,'stdin',io.StringIO()) as stdin,mock.patch('builtins.input',return_value='8') as ask:
            stdin.isatty=lambda:True
            first=self.quiet(native,args);second=self.quiet({**native,'Pm':3},args);third=self.quiet(native,args)
        self.assertEqual([first['Pm'],second['Pm'],third['Pm']],[8,3,8]);self.assertEqual(ask.call_count,1)

    @unittest.skipIf(Dataset is None, "optional netCDF4 fixture writer is unavailable")
    def test_leeds_sequence_subprocesses_keep_each_frames_native_values(self):
        from netCDF4 import Dataset
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input';source.mkdir()
            for step,ek,pm in [(1,.01,None),(2,.02,3.)]:
                with Dataset(source/f'state{step:05d}.cdf.dat','w') as f:
                    attrs={**NATIVE,'E':ek}
                    if pm is None:attrs.pop('Pm')
                    else:attrs['Pm']=pm
                    for key,value in attrs.items():f.setncattr(key,value)
            args=leeds.build_arg_parser().parse_args(['--folder',str(source),'--out',str(root/'out'),
                '--sequence-first','1','--sequence-last','2','--Sc','4','--output','ur','vort_r'])
            results=[]
            def child(cmd,check):
                self.assertTrue(cmd[1].endswith('convert_leeds_to_viewer.py'))
                opts=leeds.build_arg_parser().parse_args(cmd[2:])
                self.assertNotIn('--Ek',cmd)
                self.assertEqual(opts.output,['ur','vort_r'])
                results.append(leeds.resolve_parameter_values(opts.state,opts,False))
                out=Path(opts.out);out.mkdir(parents=True)
                (out/'metadata.json').write_text('{"time":1}')
            with contextlib.redirect_stdout(io.StringIO()),mock.patch.object(sys,'stdin',io.StringIO()) as stdin, \
                 mock.patch('builtins.input',return_value='8') as ask,mock.patch.object(leeds.subprocess,'run',side_effect=child):
                stdin.isatty=lambda:True
                leeds.run_sequence_conversion(args)
            self.assertEqual([(v['Ek'],v['Pm'],v['Sc']) for v in results],[(.01,8.,4.),(.02,3.,4.)])
            self.assertEqual(ask.call_count,1)

    def test_malformed_and_nonfinite_native_are_missing_and_cli_is_rejected(self):
        for value in ([1,2],float('inf'),'bad',True):
            result=self.quiet({**NATIVE,'Pm':value},self.args(noop=0))
            self.assertTrue(math.isnan(result['Pm']))
        with self.assertRaisesRegex(ValueError,'finite'):self.quiet(NATIVE,self.args(Pm=float('nan')))

    def test_xshells_native_headers_or_missing_without_path_inference(self):
        fields=[argparse.Namespace(header={'Ek':.01,'Pr':2},parameters={'Pm':5},filename='/Ek=99_Ra=999/fieldU')]
        values=self.quiet(cp.xshells_native_parameters(fields),self.args())
        self.assertEqual(values['Ek'],.01);self.assertEqual(values['Pm'],5);self.assertTrue(math.isnan(values['RaT']))
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            cp.xshells_native_parameters([*fields,argparse.Namespace(header={'Ek':.02})])

    def test_module_rename_does_not_invalidate_calculation_identity(self):
        fn=leeds.cart_to_sph;original=fn.__module__
        try:
            fn.__module__='convert_state_to_viewer';old=cache.calculation_identity(fn)
            fn.__module__='convert_leeds_to_viewer';new=cache.calculation_identity(fn)
            self.assertEqual(old,new)
        finally:fn.__module__=original

    def test_all_six_clis_share_pm_rac_alias_and_prompt_control(self):
        import test_converter_package as fixtures
        fixtures.ConverterPackageTests.setUpClass()
        from tools import convert_calypso_to_viewer,convert_quicc_to_viewer,convert_rayleigh_to_viewer
        converters=[leeds,fixtures.ConverterPackageTests.xshells,fixtures.ConverterPackageTests.magic,
                    convert_calypso_to_viewer,convert_quicc_to_viewer,convert_rayleigh_to_viewer]
        for module in converters:
            parser=module.build_arg_parser()
            for option in ('--Pm','--Ra_comp','--no-parameter-prompt'):
                self.assertIn(option,parser._option_string_actions,module.__name__)

    def test_common_export_uses_prompted_parameters_in_metadata_and_n2(self):
        import test_converter_package as fixtures
        fixtures.ConverterPackageTests.setUpClass();magic=fixtures.ConverterPackageTests.magic
        graph=fixtures.ConverterPackageTests.fake_magic_graph()
        args=magic.build_arg_parser().parse_args(['--graph','G_1.test','--skip-field-lines','--no-earth-br'])
        native=dict(ek=.01,pr=2,sc=3,ra=10,raxi=0) # missing Pm
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()),mock.patch.object(sys,'stdin',io.StringIO()) as stdin,mock.patch('builtins.input',return_value='7') as ask:
            stdin.isatty=lambda:True
            magic.convert_adapted_snapshot(Path('G_1.test'),Path(folder),args,magic.adapt_graph(graph),native)
            meta=json.loads((Path(folder)/'metadata.json').read_text())
        self.assertEqual(ask.call_count,1);self.assertEqual(meta['parameters']['Pm'],7)
        self.assertEqual(meta['parameter_sources']['Pm'],'prompt');self.assertIn('N2_full',meta['fields'])

if __name__=='__main__':unittest.main()
