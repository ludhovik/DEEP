"""Read legacy StagYY Yin–Yang volumes with StagPy; resample both patches.

The StagPy dependency handles processor ordering and binary versions. Geometry
and local spherical velocity conventions follow StagYY's legacy output, also
documented by pypStag (see STAGYY_CONVERTER.md). No source parser is vendored.
"""
from pathlib import Path
import re
import sys

import numpy as np
from scipy.interpolate import RegularGridInterpolator


def parser_module():
    try:
        import stagpy
        from stagpy.parsers.bin import field
    except ImportError as exc:
        raise ImportError('StagYY conversion needs: python3 -m pip install -r requirements-stagyy.txt') from exc
    if stagpy.__version__ != '0.23.0':
        raise ValueError('This legacy reader requires stagpy==0.23.0; install requirements-stagyy.txt.')
    return field


def read_header(path):
    """Validate format, geometry and exact length before allocating a volume."""
    path = Path(path)
    parser = parser_module()
    if sys.byteorder != 'little':
        raise ValueError('The supported legacy files require a little-endian host.')
    with path.open('rb') as stream:
        magic = np.fromfile(stream, '<i4', 1)
        if len(magic) != 1 or int(magic[0]) not in (9,10,11,12,409,410,411,412,8009,8010,8011,8012,8409,8410,8411,8412):
            raise ValueError(f'{path}: expected a little-endian legacy scalar or vp volume (versions 9–12), not HDF5/surface data.')
        width = 8 if magic[0] > 8000 else 4
        stream.seek(width)
        prefix = np.fromfile(stream, f'<i{width}', 4)
        if len(prefix) != 4 or np.any(prefix < 2) or prefix[3] != 2 or np.prod(prefix.astype(object))*width > path.stat().st_size:
            raise ValueError(f'{path}: invalid or truncated 3-D Yin–Yang volume dimensions.')
        stream.seek(0)
        try:
            info = parser._header(path, stream)
        except (IndexError, ValueError) as exc:
            raise ValueError(f'{path}: truncated legacy header.') from exc
        h = info.header
        nts, ncs, ntb, ncb = h['nts'], h['ncs'], int(h['ntb']), int(h['ncb'])
        if np.any(ncs < 1) or ncb < 1 or np.any(nts % ncs) or ntb % ncb:
            raise ValueError(f'{path}: invalid processor decomposition.')
        npc = nts // ncs
        count = int((npc[0]+h['xyp'])*(npc[1]+h['xyp'])*npc[2]*ntb*np.prod(ncs)*info.nval)
        expected = stream.tell() + width*(count + int(info.nval > 1))
        if path.stat().st_size != expected:
            raise ValueError(f'{path}: truncated or unexpected trailing data; expected {expected} bytes, got {path.stat().st_size}.')
    if not np.isfinite([h['rcmb'], h['ti_ad']]).all() or h['rcmb'] <= 0:
        raise ValueError('Only spherical-shell volumes with positive CMB radius and finite time are supported.')
    if not np.allclose(h['aspect'], [np.pi/2, 3*np.pi/2], rtol=1e-5):
        raise ValueError('Only the standard two-patch Yin–Yang geometry is supported.')
    for key in ('e1_coord','e2_coord','e3_coord'):
        a = h[key]
        if not np.isfinite(a).all() or np.any(np.diff(a) <= 0):
            raise ValueError(f'Invalid or non-increasing {key}.')
    # The header stores cell centres before the angular patch offsets.
    for key, extent in [('e1_coord',np.pi/2),('e2_coord',3*np.pi/2)]:
        if h[key][0] <= 0 or h[key][-1] >= extent:
            raise ValueError(f'{key} is outside the supported Yin–Yang patch.')
    if not np.allclose(h['e3_coord'], h['rgeom'][:-1,1], rtol=1e-5, atol=1e-7):
        raise ValueError('Radial cell-centre coordinates disagree in the binary header.')
    return h


def read_volume(path, reference=None, components=1):
    h = read_header(path)
    if bool(h['xyp']) != (components == 4):
        raise ValueError(f'{path}: expected {components} field components.')
    if reference is not None:
        for key in ('nts','ntb','rcmb','ti_step','ti_ad','e1_coord','e2_coord','e3_coord','rgeom'):
            if not np.array_equal(h[key], reference[key]):
                raise ValueError(f'{path}: snapshot/grid mismatch in {key}.')
    _, values = parser_module().field(Path(path))
    # vp carries one redundant high-side horizontal row/column. As in the
    # legacy pypStag reader, use the ntheta*nphi samples indexed by the header.
    nx, ny, _ = h['nts']
    values = values[:, :nx, :ny, :, :]
    if values.shape[0] != components or not np.isfinite(values).all():
        raise ValueError(f'{path}: invalid field components or non-finite data.')
    return h, values


def companion_files(temperature, no_velocity=False, no_viscosity=False, composition_suffix=None):
    path = Path(temperature).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    match = re.fullmatch(r'(.*)_t(\d+)',path.name)
    if not match:
        raise ValueError('Input must be a legacy temperature volume named STEM_tNNNNN.')
    def sibling(suffix):
        return path.with_name(f'{match[1]}_{suffix}{match[2]}')
    result = {'T':path}
    for name,suffix,disabled in [('eta','eta',no_viscosity),('vp','vp',no_velocity)]:
        p = sibling(suffix)
        if not disabled and p.exists():
            result[name] = p
    if composition_suffix:
        if not re.fullmatch('[A-Za-z][A-Za-z0-9]*',composition_suffix):
            raise ValueError('Composition suffix must contain only letters and digits.')
        p = sibling(composition_suffix)
        if not p.is_file():
            raise FileNotFoundError(f'Requested composition volume missing: {p}')
        if p in result.values():
            raise ValueError('Composition must be a distinct scalar file.')
        result['C'] = p
    return result


def patch_axes(header):
    return (np.asarray(header['e1_coord'],float)+np.pi/4,
            np.asarray(header['e2_coord'],float)-3*np.pi/4,
            np.asarray(header['e3_coord'],float)+float(header['rcmb']))


def rotate_yang(vector):
    """Self-inverse Cartesian rotation between Yang-local and global axes."""
    return np.stack((-vector[...,0],vector[...,2],vector[...,1]),axis=-1)


def spherical_to_cartesian(ut, up, ur, theta, phi):
    st,ct,sp,cp = np.sin(theta),np.cos(theta),np.sin(phi),np.cos(phi)
    return np.stack((ur*st*cp+ut*ct*cp-up*sp,
                     ur*st*sp+ut*ct*sp+up*cp, ur*ct-ut*st),axis=-1)


class YinYangSampler:
    """Trilinear interpolation with smooth overlap weights.

    Vectors are rotated to global Cartesian axes before blending patches. Work
    one radial layer at a time to bound interpolation point memory.
    """
    def __init__(self, header, r, theta, phi):
        self.axes = patch_axes(header)
        self.r, self.theta, self.phi = r,theta,phi
        th,ph = np.meshgrid(theta,phi,indexing='ij')
        xyz = spherical_to_cartesian(np.zeros_like(th),np.zeros_like(th),np.ones_like(th),th,ph)
        self.queries,self.weights = [],[]
        for local in (xyz,rotate_yang(xyz)):
            t = np.arccos(np.clip(local[...,2],-1,1))
            p = np.arctan2(local[...,1],local[...,0])
            a,b,_ = self.axes
            # Centres alone leave small gaps where patch corners meet. Allow
            # at most half a cell to each angular wall, using the local linear
            # slope there. Radial extrapolation remains strictly forbidden.
            margin = np.minimum.reduce((t-(a[0]-(a[1]-a[0])/2),
                                        (a[-1]+(a[-1]-a[-2])/2)-t,
                                        p-(b[0]-(b[1]-b[0])/2),
                                        (b[-1]+(b[-1]-b[-2])/2)-p))
            weight = np.maximum(margin,0.)
            self.queries.append((t,p))
            self.weights.append(weight)
        total = self.weights[0]+self.weights[1]
        if np.any(total <= 0):
            raise ValueError('Yin–Yang cell-centre grids do not cover the requested sphere; source grid is too coarse or incomplete.')
        self.weights = [w/total for w in self.weights]
        if r[0] < self.axes[2][0] or r[-1] > self.axes[2][-1]:
            raise ValueError('Requested radius lies outside the saved cell centres; extrapolation is disabled.')

    def sample(self, values):
        """values has axes (theta,phi,r,block[,Cartesian component])."""
        tail = values.shape[4:]
        out = np.zeros((len(self.r),len(self.theta),len(self.phi))+tail)
        for block,((t,p),weight) in enumerate(zip(self.queries,self.weights)):
            active = weight > 0
            interp = RegularGridInterpolator(self.axes,values[:,:,:,block],bounds_error=False,fill_value=None)
            points = np.column_stack((t[active],p[active],np.zeros(active.sum())))
            factor = weight[active].reshape((-1,)+(1,)*len(tail))
            for i,radius in enumerate(self.r):
                points[:,2] = radius
                out[i][active] += interp(points)*factor
        return out

    def velocity(self, values):
        t,p,_ = self.axes
        th,ph = t[:,None,None,None],p[None,:,None,None]
        xyz = spherical_to_cartesian(values[0],values[1],values[2],th,ph)
        xyz[:,:,:,1] = rotate_yang(xyz[:,:,:,1])
        velocity = self.sample(xyz)
        th,ph = self.theta[None,:,None],self.phi[None,None,:]
        x,y,z = np.moveaxis(velocity,-1,0)
        return dict(ur=x*np.sin(th)*np.cos(ph)+y*np.sin(th)*np.sin(ph)+z*np.cos(th),
                    ut=x*np.cos(th)*np.cos(ph)+y*np.cos(th)*np.sin(ph)-z*np.sin(th),
                    up=-x*np.sin(ph)+y*np.cos(ph))
