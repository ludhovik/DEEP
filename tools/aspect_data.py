"""Read ASPECT VTK meshes and sample complete 3-D spherical shells.

VTK cell interpolation respects the source connectivity, including the core
cavity. Never build a point-cloud Delaunay triangulation through that cavity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


def vtk_modules():
    try:
        import vtk
        from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy
    except ImportError as exc:
        raise ImportError('ASPECT conversion needs VTK: python3 -m pip install -r requirements-aspect.txt') from exc
    return vtk, numpy_to_vtk, vtk_to_numpy


@dataclass(frozen=True)
class Snapshot:
    path: Path
    time: float | None = None


def referenced_file(parent, value):
    if not value or '://' in value:
        raise ValueError(f'Expected a local VTK file reference, got {value!r}')
    path = (Path(parent) / value).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Missing referenced VTK file: {path}; keep all PVTU pieces together.')
    return path


def discover_snapshots(filename):
    path = Path(filename).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() in ('.vtu', '.pvtu'):
        return [Snapshot(path)]
    if path.suffix.lower() != '.pvd':
        raise ValueError('Choose a volume .vtu, .pvtu, or solution.pvd; archives and restart files are not visualization meshes.')
    root = ET.parse(path).getroot()
    result = []
    for entry in root.findall('./Collection/DataSet'):
        time = float(entry.attrib['timestep'])
        if not np.isfinite(time):
            raise ValueError('Non-finite PVD timestep.')
        file = referenced_file(path.parent, entry.get('file'))
        if file.suffix.lower() not in ('.vtu', '.pvtu'):
            raise ValueError(f'PVD references unsupported volume format: {file}')
        result.append(Snapshot(file, time))
    result.sort(key=lambda frame: frame.time)
    if not result or len({s.time for s in result}) != len(result):
        raise ValueError('PVD must contain one volume VTU/PVTU per distinct timestep; use PVTU to group parallel pieces.')
    return result


def read_mesh(filename):
    vtk, _, to_numpy = vtk_modules()
    path = Path(filename)
    if path.suffix.lower() == '.pvtu':
        pieces = ET.parse(path).getroot().findall('./PUnstructuredGrid/Piece')
        if not pieces:
            raise ValueError('PVTU contains no pieces.')
        for piece in pieces:
            referenced_file(path.parent, piece.get('Source'))
        reader = vtk.vtkXMLPUnstructuredGridReader()
    elif path.suffix.lower() == '.vtu':
        reader = vtk.vtkXMLUnstructuredGridReader()
    else:
        raise ValueError('Expected .vtu or .pvtu.')
    errors = []
    reader.AddObserver('ErrorEvent', lambda *_: errors.append('VTK reader reported an error'))
    reader.SetFileName(str(path))
    reader.Update()
    grid = reader.GetOutput()
    if errors or grid.GetNumberOfCells() == 0 or grid.GetNumberOfPoints() == 0:
        raise ValueError(f'Could not read complete VTK volume: {path}')
    types = vtk.vtkCellTypes()
    grid.GetCellTypes(types)
    if any(vtk.vtkCellTypes.GetDimension(types.GetCellType(i)) != 3 for i in range(types.GetNumberOfTypes())):
        raise ValueError('Only complete 3-D spherical-shell volumes are supported; 2-D annuli, surfaces and particles are not 3-D mantle data.')
    points = to_numpy(grid.GetPoints().GetData())
    if not np.isfinite(points).all():
        raise ValueError('Non-finite source mesh coordinates.')
    # ASPECT usually writes point arrays. Preserve cell data by explicitly
    # averaging it to points; record this approximation in output metadata.
    point_names = {grid.GetPointData().GetArrayName(i) for i in range(grid.GetPointData().GetNumberOfArrays())}
    cell_names = {grid.GetCellData().GetArrayName(i) for i in range(grid.GetCellData().GetNumberOfArrays())}
    promoted = sorted(name for name in cell_names - point_names if name and name != 'vtkGhostType')
    if promoted:
        promote = vtk.vtkCellDataToPointData()
        promote.SetInputData(grid)
        promote.ProcessAllArraysOff()
        for name in promoted:
            promote.AddCellDataArray(name)
        promote.Update()
        grid = promote.GetOutput()
    return grid, promoted


def mesh_time(grid):
    _, _, to_numpy = vtk_modules()
    for name in ('TIME', 'TimeValue', 'Time', 'time'):
        array = grid.GetFieldData().GetArray(name)
        if array is not None:
            values = to_numpy(array).ravel()
            if values.size == 1 and np.isfinite(values[0]):
                return float(values[0])
    return None


def mesh_arrays(grid):
    data = grid.GetPointData()
    return {data.GetArrayName(i): data.GetArray(i).GetNumberOfComponents()
            for i in range(data.GetNumberOfArrays()) if data.GetArray(i) is not None}


def radial_bounds(grid, center):
    _, _, to_numpy = vtk_modules()
    radii = np.linalg.norm(to_numpy(grid.GetPoints().GetData()).astype(float) - center, axis=1)
    return float(radii.min()), float(radii.max())


def sample_shell(grid, r, theta, phi, names, center=(0, 0, 0), boundary_tolerance=0.002,
                 chunk_size=65536):
    """Interpolate point arrays through VTK cells in bounded-size target chunks.

    Curved shell boundaries are approximated by mesh faces. Samples at the two
    radial endpoints may project to the closest cell within tolerance*ro.
    Interior misses are errors, never filled with nearest-neighbour values.
    """
    vtk, to_vtk, to_numpy = vtk_modules()
    shape = (len(r), len(theta), len(phi))
    total = int(np.prod(shape))
    arrays = mesh_arrays(grid)
    missing = set(names) - set(arrays)
    if missing:
        raise ValueError('Missing source arrays: ' + ', '.join(sorted(missing)))
    # Keep only requested arrays in a shallow copy: source geometry remains
    # shared, while probe output memory scales with the selected fields.
    source = vtk.vtkUnstructuredGrid()
    source.ShallowCopy(grid)
    source.GetPointData().Initialize()
    source.GetCellData().Initialize()
    for name in names:
        source.GetPointData().AddArray(grid.GetPointData().GetArray(name))
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(source)
    locator.BuildLocator()
    probe = vtk.vtkProbeFilter()
    probe.SetSourceData(source)
    probe.SetCellLocatorPrototype(locator)
    probe.ComputeToleranceOff()
    probe.SetTolerance(float(r[-1]) * 1e-10)
    source_values = {name: to_numpy(source.GetPointData().GetArray(name)) for name in names}
    output = {name: np.empty((total, arrays[name]), dtype=np.float64) for name in names}
    projected = 0
    max_distance = 0.0
    limit = boundary_tolerance * r[-1]
    for start in range(0, total, chunk_size):
        stop = min(total, start + chunk_size)
        ids = np.arange(start, stop)
        ir, it, ip = np.unravel_index(ids, shape)
        th, ph, radius = theta[it], phi[ip], r[ir]
        xyz = np.column_stack((radius*np.sin(th)*np.cos(ph), radius*np.sin(th)*np.sin(ph), radius*np.cos(th))) + center
        points = vtk.vtkPoints()
        points.SetData(to_vtk(np.ascontiguousarray(xyz), deep=True))
        target = vtk.vtkPolyData()
        target.SetPoints(points)
        probe.SetInputData(target)
        probe.Update()
        data = probe.GetOutput().GetPointData()
        valid = to_numpy(data.GetArray('vtkValidPointMask')).astype(bool)
        for name in names:
            output[name][start:stop] = to_numpy(data.GetArray(name)).reshape(-1, arrays[name])
        for index in np.flatnonzero(~valid):
            if ir[index] not in (0, len(r)-1):
                raise ValueError(f'Target sample r={radius[index]:g}, theta={th[index]:g}, phi={ph[index]:g} lies outside source cells. Select a complete 3-D shell and all PVTU pieces, or adjust --r-inner/--r-outer.')
            closest = [0., 0., 0.]
            cell_id, sub_id, dist2 = vtk.reference(0), vtk.reference(0), vtk.reference(0.)
            locator.FindClosestPoint(xyz[index], closest, cell_id, sub_id, dist2)
            distance = float(dist2)**0.5
            if int(cell_id) < 0 or distance > limit:
                raise ValueError(f'Boundary sample is {distance:g} from the mesh (allowed {limit:g}). Check spherical geometry/radii, or explicitly adjust --boundary-tolerance (fraction of outer radius).')
            cell = source.GetCell(int(cell_id))
            weights = [0.] * cell.GetNumberOfPoints()
            pcoords, evaluate_closest = [0., 0., 0.], [0., 0., 0.]
            result = cell.EvaluatePosition(closest, evaluate_closest, sub_id, pcoords, dist2, weights)
            if result < 0 or not np.isfinite(weights).all() or abs(sum(weights)-1) > 1e-6:
                raise ValueError('Could not interpolate a projected boundary cell.')
            node_ids = [cell.GetPointId(i) for i in range(cell.GetNumberOfPoints())]
            for name in names:
                values = source_values[name][node_ids].reshape(-1, arrays[name])
                output[name][start + index] = np.asarray(weights) @ values
            projected += 1
            max_distance = max(max_distance, distance)
    result = {}
    for name, values in output.items():
        if not np.isfinite(values).all():
            raise ValueError(f'Sampled {name} contains non-finite values.')
        result[name] = values.reshape(shape if arrays[name] == 1 else (*shape, arrays[name]))
    return result, {'method': 'VTK source-cell interpolation', 'boundary_projected_samples': projected,
                    'boundary_max_distance': max_distance, 'boundary_tolerance_fraction_ro': boundary_tolerance,
                    'interior_missing_samples': 0}
