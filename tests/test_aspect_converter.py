#!/usr/bin/env python3
"""Exercise VTK connectivity, physical units, diagnostics and transactions."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy
except ImportError:
    vtk = None
from tools import aspect_data
from tools import convert_aspect_to_viewer as converter
from tools.viewer_bundle import validate_bundle


def write_shell(path, offset=0, dimension=3):
    r = np.linspace(.5,1.,5)
    theta = np.linspace(0,np.pi,17)
    phi = np.linspace(0,2*np.pi,33)
    pp,tt,rr = np.meshgrid(phi,theta,r,indexing='ij')
    xyz = np.stack((rr*np.sin(tt)*np.cos(pp),rr*np.sin(tt)*np.sin(pp),rr*np.cos(tt)),axis=-1).reshape(-1,3)
    points=vtk.vtkPoints();points.SetData(numpy_to_vtk(xyz,deep=True))
    structured=vtk.vtkStructuredGrid();structured.SetDimensions(len(r),len(theta),len(phi));structured.SetPoints(points)
    append=vtk.vtkAppendFilter();append.AddInputData(structured);append.Update();grid=append.GetOutput()
    def add(name,values,association=None):
        array=numpy_to_vtk(np.ascontiguousarray(values),deep=True);array.SetName(name)
        (association if association is not None else grid.GetPointData()).AddArray(array)
    add('T',xyz[:,2]+offset)
    add('basalt',xyz[:,0])
    add('p',np.full(len(xyz),7.))
    add('velocity',np.tile([1.,2.,3.],(len(xyz),1)))
    add('viscosity',np.full(grid.GetNumberOfCells(),1e21),grid.GetCellData())
    add('TIME',np.array([12.5+offset]),grid.GetFieldData())
    writer=vtk.vtkXMLUnstructuredGridWriter();writer.SetFileName(str(path));writer.SetInputData(grid)
    writer.SetDataModeToAppended();writer.SetCompressorTypeToZLib()
    assert writer.Write()==1
    return grid


@unittest.skipIf(vtk is None,'Install requirements-aspect.txt for VTK integration tests')
class AspectConverterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/'solution.vtu'
        write_shell(self.source)
        self.out=self.root/'viewer'
        self.options=['--input',str(self.source),'--out',str(self.out),'--nr','5','--ntheta','32','--nphi','64',
                      '--r-inner','.6','--r-outer','.95','--composition-field','basalt','--length-units','m','--time-units','yr']

    def tearDown(self):
        self.temp.cleanup()

    def run_converter(self,*extra,options=None):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            converter.main((self.options if options is None else options)+list(extra))
        return stream.getvalue()

    def volume(self,name,root=None):
        root=root or self.out
        meta=json.loads((root/'metadata.json').read_text())
        return np.fromfile(root/meta['fields'][name],dtype='<f4').reshape(meta['nr'],meta['ntheta'],meta['nphi'])

    def test_real_compressed_vtu_fields_units_and_analytic_transport(self):
        self.run_converter()
        validate_bundle(self.out)
        meta=json.loads((self.out/'metadata.json').read_text())
        coords=json.loads((self.out/'coordinates.json').read_text())
        r,theta,phi=[np.asarray(coords[k]) for k in ('r','theta','phi')]
        np.testing.assert_allclose(self.volume('T'),np.broadcast_to(r[:,None,None]*np.cos(theta)[None,:,None],(5,32,64)),atol=1e-6)
        expected=np.sin(theta)[None,:,None]*np.cos(phi)[None,None,:]+2*np.sin(theta)[None,:,None]*np.sin(phi)[None,None,:]+3*np.cos(theta)[None,:,None]
        np.testing.assert_allclose(self.volume('ur'),np.broadcast_to(expected,(5,32,64)),atol=1e-6)
        np.testing.assert_allclose(self.volume('advT'),3,atol=.02)
        np.testing.assert_allclose(self.volume('advC'),1,atol=.03)
        np.testing.assert_allclose(self.volume('dthetaT_phiavg'),np.broadcast_to(-r[:,None,None]*np.sin(theta)[None,:,None],(5,32,64)),atol=.002)
        np.testing.assert_allclose(self.volume('dzup_phiavg'),0,atol=1e-12)
        np.testing.assert_allclose(self.volume('viscosity'),1e21,rtol=1e-6)
        self.assertEqual(meta['time'],12.5)
        self.assertEqual(meta['time_units'],'yr')
        self.assertEqual(meta['length_units'],'m')
        self.assertEqual(meta['r_outer'],.95)
        self.assertEqual(meta['cell_arrays_averaged_to_points'],['viscosity'])
        self.assertFalse(meta['magnetic']['has_magnetic_field'])
        self.assertEqual(meta['field_lines'],{})

    def test_parallel_wrapper_and_pvd_preserve_times_and_grid(self):
        second=self.root/'next.vtu';write_shell(second,offset=2)
        for stem,piece in [('first','solution.vtu'),('second','next.vtu')]:
            wrapper=ET.Element('VTKFile',type='PUnstructuredGrid',version='0.1',byte_order='LittleEndian')
            grid=ET.SubElement(wrapper,'PUnstructuredGrid',GhostLevel='0');point=ET.SubElement(grid,'PPointData')
            for name,components in [('T',1),('basalt',1),('p',1),('velocity',3)]:
                ET.SubElement(point,'PDataArray',type='Float64',Name=name,NumberOfComponents=str(components))
            cell=ET.SubElement(grid,'PCellData');ET.SubElement(cell,'PDataArray',type='Float64',Name='viscosity')
            points=ET.SubElement(grid,'PPoints');ET.SubElement(points,'PDataArray',type='Float64',NumberOfComponents='3')
            ET.SubElement(grid,'Piece',Source=piece);ET.ElementTree(wrapper).write(self.root/f'{stem}.pvtu')
        pvd=self.root/'solution.pvd'
        pvd.write_text('<VTKFile type="Collection"><Collection><DataSet timestep="8" file="second.pvtu"/><DataSet timestep="2" file="first.pvtu"/></Collection></VTKFile>')
        options=self.options.copy();options[1]=str(pvd)
        self.run_converter('--all-frames',options=options)
        validate_bundle(self.out)
        sequence=json.loads((self.out/'sequence.json').read_text())
        self.assertEqual([frame['time'] for frame in sequence['frames']],[2,8])
        first,second=[self.out/frame['path'] for frame in sequence['frames']]
        self.assertEqual((first/'coordinates.json').read_bytes(),(second/'coordinates.json').read_bytes())
        np.testing.assert_allclose(self.volume('T',second)-self.volume('T',first),2,atol=1e-6)
        self.assertEqual(json.loads((second/'metadata.json').read_text())['time'],8)
        (self.root/'next.vtu').unlink()
        with self.assertRaisesRegex(FileNotFoundError,'Missing referenced'):
            aspect_data.read_mesh(self.root/'second.pvtu')

    def test_boundary_projection_is_bounded_and_interior_holes_rejected(self):
        grid,_=aspect_data.read_mesh(self.source)
        th=(np.arange(12)+.5)*np.pi/12;ph=np.arange(24)*2*np.pi/24
        values,report=aspect_data.sample_shell(grid,np.array([.5,.75,1.]),th,ph,['T'],boundary_tolerance=.02)
        self.assertGreater(report['boundary_projected_samples'],0)
        self.assertLessEqual(report['boundary_max_distance'],.02)
        with self.assertRaisesRegex(ValueError,'Boundary sample'):
            aspect_data.sample_shell(grid,np.array([.5,.75,1.2]),th,ph,['T'],boundary_tolerance=.001)
        with self.assertRaisesRegex(ValueError,'outside source cells'):
            aspect_data.sample_shell(grid,np.array([.1,.2,.9]),th,ph,['T'],boundary_tolerance=1)

    def test_selected_outputs_incremental_and_failed_update_preserves_bundle(self):
        self.run_converter('--output','viscosity','advT','--incremental')
        self.assertEqual(set(json.loads((self.out/'metadata.json').read_text())['fields']),{'viscosity','advT'})
        original=(self.out/'metadata.json').read_bytes()
        self.assertIn('skipped',self.run_converter('--output','viscosity','advT','--incremental'))
        with self.assertRaisesRegex(ValueError,'Unavailable --output'):
            self.run_converter('--output','magnetic_field')
        self.assertEqual((self.out/'metadata.json').read_bytes(),original)
        write_shell(self.source,offset=1)
        self.assertNotIn('skipped',self.run_converter('--output','viscosity','advT','--incremental'))

    def test_unknown_time_is_null_and_2d_is_rejected(self):
        grid,_=aspect_data.read_mesh(self.source);grid.GetFieldData().Initialize()
        writer=vtk.vtkXMLUnstructuredGridWriter();writer.SetInputData(grid);writer.SetFileName(str(self.source));writer.Write()
        self.run_converter('--output','T')
        self.assertIsNone(json.loads((self.out/'metadata.json').read_text())['time'])
        self.run_converter('--output','T','--time','123')
        self.assertEqual(json.loads((self.out/'metadata.json').read_text())['time'],123)
        plane=vtk.vtkPlaneSource();plane.Update();append=vtk.vtkAppendFilter();append.AddInputData(plane.GetOutput());append.Update()
        writer.SetInputData(append.GetOutput());writer.Write()
        with self.assertRaisesRegex(ValueError,'2-D annuli'):
            aspect_data.read_mesh(self.source)


if __name__=='__main__':
    unittest.main()
