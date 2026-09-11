"""Native EPM/QuICC spherical HDF5 spectral reconstruction.

See QUICC_CONVERTER.md for the upstream definitions and normalization choices.
No QuICC installation, SHTns, or modifications to simulation code are needed.
"""
from __future__ import annotations

import math
from pathlib import Path
import numpy as np
from scipy.special import eval_jacobi, gammaln
try:
    from conversion_cache import cached_calculation
    from spectral_truncation import harmonic_basis
except ImportError:
    from tools.conversion_cache import cached_calculation
    from tools.spectral_truncation import harmonic_basis


def text_attr(value):
    return value.decode('ascii').rstrip('\x00') if isinstance(value, bytes) else str(value)


def modes(lmax, mmax, minc=1, ordering='l'):
    pairs = [(l, m) for l in range(lmax + 1) for m in range(0, min(l, mmax) + 1, minc)]
    return sorted(pairs, key=lambda p: (p[1], p[0])) if ordering == 'm' else pairs


@cached_calculation
def read_state(path):
    import h5py
    if not h5py.is_hdf5(path):
        raise ValueError('Expected an extracted HDF5 state file; unpack .tar.gz archives first and select stateNNNN.hdf5.')
    with h5py.File(path, 'r') as f:
        header = text_attr(f.attrs.get('header', b'StateFile'))
        if header != 'StateFile':
            raise ValueError(f'{path}: expected a spectral StateFile, got {header!r}.')
        version = text_attr(f.attrs.get('version', b'1.0'))
        if version != '1.0':
            raise ValueError(f'Unsupported QuICC state version {version!r}.')
        epm = 'Truncation' in f
        scheme = 'EPM' if epm else text_attr(f.attrs.get('type', b''))
        if not epm and scheme not in ('WLFl', 'WLFm', 'SLFl', 'SLFm'):
            raise ValueError(f'Unsupported QuICC scheme {scheme!r}; supported schemes are EPM, WLFl/WLFm and SLFl/SLFm.')
        def integer(key):
            v = np.asarray(f[key][()])
            if v.size != 1 or not np.isfinite(v.item()) or v.item() != int(v.item()):
                raise ValueError(f'Invalid integer truncation at {key}.')
            return int(v.item())
        if epm:
            nmax, lmax, mmax, minc = [integer('Truncation/' + k) for k in ('N', 'L', 'M', 'Mp')]
            paths = {'ur': 'Velocity/VelocityPol', 'utor': 'Velocity/VelocityTor',
                     'Br': 'Magnetic/MagneticPol', 'Btor': 'Magnetic/MagneticTor',
                     'T': 'Codensity/Codensity'}
            phys, timekey = 'PhysicalParameters', 'RunParameters/Time'
        else:
            nmax, lmax, mmax = [integer('truncation/spectral/dim' + k + 'D') for k in ('1','2','3')]
            minc = 1
            paths = {'ur': 'velocity/velocity_pol', 'utor': 'velocity/velocity_tor',
                     'Br': 'magnetic/magnetic_pol', 'Btor': 'magnetic/magnetic_tor',
                     'T': 'temperature/temperature', 'C': 'composition/composition'}
            phys, timekey = 'physical', 'run/time'
        if nmax < 0 or lmax < 0 or mmax < 0 or mmax > lmax or minc < 1:
            raise ValueError('Invalid spectral truncation.')
        pairs = modes(lmax, mmax, minc, scheme[-1])
        fields = {}
        for name, key in paths.items():
            if key not in f:
                continue
            a = np.asarray(f[key][()])
            if a.dtype.kind != 'c':
                if a.shape != (len(pairs), nmax + 1, 2):
                    raise ValueError(f'{key}: expected complex (harmonic, radial) or trailing real/imag pair, got {a.shape}.')
                a = a[..., 0] + 1j*a[..., 1]
            if a.shape != (len(pairs), nmax + 1) or not np.isfinite(a).all():
                raise ValueError(f'{key}: inconsistent dimensions or nonfinite coefficients.')
            zero = [i for i, (_, m) in enumerate(pairs) if m == 0]
            if np.max(np.abs(a[zero].imag), initial=0) > 1e-10 * max(1.0, np.max(np.abs(a))):
                raise ValueError(f'{key}: m=0 coefficients must be real.')
            fields[name] = a.astype(np.complex128)
        for p, t in [('ur','utor'), ('Br','Btor')]:
            if (p in fields) != (t in fields):
                raise ValueError(f'Both poloidal and toroidal datasets are required for {p}.')
        if not fields:
            raise ValueError('No supported velocity, magnetic, temperature/codensity or composition coefficients found.')
        params = {}
        if phys in f:
            for key, value in f[phys].items():
                if isinstance(value, h5py.Dataset) and value.size == 1 and value.dtype.kind in 'fiu':
                    v = float(value[()].item())
                    if math.isfinite(v): params[key] = v
        time = float(np.asarray(f[timekey][()]).item()) if timekey in f else None
        if time is not None and not math.isfinite(time):
            raise ValueError('Nonfinite simulation time.')
    interval = shell_interval(params) if scheme in ('SLFl','SLFm') else None
    return dict(radial_interval=interval, scheme=scheme, nmax=nmax, lmax=lmax, mmax=mmax, minc=minc,
                fields=fields, parameters=params, time=time)


def shell_interval(parameters):
    """Read native length units. A radius ratio alone cannot set the length scale."""
    if not {'lower1d','upper1d'} <= parameters.keys():
        raise ValueError('Shell states require physical/lower1d and physical/upper1d; rratio alone does not specify the native length scale.')
    ri, ro = parameters['lower1d'], parameters['upper1d']
    if not (math.isfinite(ri) and math.isfinite(ro) and 0 < ri < ro):
        raise ValueError('Shell radii must satisfy 0 < lower1d < upper1d.')
    for key in ('rratio','r_ratio'):
        if key in parameters and not math.isclose(ri/ro,parameters[key],rel_tol=1e-10,abs_tol=1e-12):
            raise ValueError(f'{key} disagrees with lower1d/upper1d.')
    return ri, ro


def chebyshev_shell(count, radius, interval):
    """Native QuICC FCT convention: c0 + 2 sum_{n>0} cn Tn(x)."""
    from numpy.polynomial import chebyshev as cheb
    ri, ro = interval
    a, b = (ro-ri)/2, (ro+ri)/2
    r = np.asarray(radius,dtype=float)
    if a <= 0 or ri <= 0 or np.any(r < ri-1e-12) or np.any(r > ro+1e-12):
        raise ValueError('Shell synthesis points must lie inside the native radial interval.')
    x = np.clip((r-b)/a,-1.,1.)
    coefficients = 2*np.eye(count)
    coefficients[0,0] = 1.
    w = cheb.chebval(x,coefficients).T
    derivative = cheb.chebval(x,cheb.chebder(coefficients)).T/a
    over = w/r[:,None]
    return w, over, derivative+over


def worland(l, count, radius, family='chebyshev', normalization='unity'):
    """W, W/r and (d/dr+1/r)W, with exact regular l>=1 centre limits."""
    r = np.asarray(radius, dtype=float)
    alpha = -0.5 if family == 'chebyshev' else 0.0
    beta = l - 0.5
    n = np.arange(count, dtype=float)
    if normalization == 'natural':
        inv = np.ones(count)
    elif family == 'chebyshev' and l == 0:
        lognorm = -math.log(2) + gammaln(n + .5) - gammaln(n + 1)
        lognorm[0] += .5 * math.log(2)
        inv = np.exp(-lognorm)
    else:
        # Jacobi norm after x=2r^2-1, weight (1-r^2)^alpha.
        lognorm2 = (gammaln(n+alpha+1) + gammaln(n+beta+1)
                    - gammaln(n+1) - gammaln(n+alpha+beta+1)
                    - np.log(2*(2*n+alpha+beta+1)))
        inv = np.exp(-.5*lognorm2)
    x = 2*r*r-1
    j = np.array([eval_jacobi(k, alpha, beta, x) for k in range(count)]).T * inv
    dj = np.zeros_like(j)
    for k in range(1, count):
        dj[:, k] = 2*(k+alpha+beta+1)*eval_jacobi(k-1, alpha+1, beta+1, x)*inv[k]
    w = r[:, None]**l*j
    if l:
        over = r[:, None]**(l-1)*j
        tangent = (l+1)*over + r[:, None]**(l+1)*dj
    else:
        # l=0 is used for scalars only; toroidal/poloidal l=0 is a null mode.
        over = tangent = np.zeros_like(w)
    return w, over, tangent


def grids(nmax, lmax, mmax, radial_interval=None):
    # Resolve radial products r^l P_n(2r^2-1); include centre and boundary exactly.
    nr = max(8, 2*(nmax+1) + (lmax+1)//2)
    r = np.r_[0., np.sin(np.pi*(np.arange(nr)+.5)/(2*nr)), 1.]
    if radial_interval is not None:
        ri, ro = radial_interval
        nr = max(8,2*(nmax+1))
        r = ri + (ro-ri)*(1-np.cos(np.linspace(0,np.pi,nr+1)))/2
        r[0], r[-1] = ri, ro
    nt = max(6, math.ceil(1.5*(lmax+1)))
    np_ = max(12, 3*(mmax+1))
    theta = np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1])
    phi = np.arange(np_)*2*np.pi/np_
    return r, theta, phi


@cached_calculation
def synthesize_field(coefficients, pairs, radius, theta, phi, lmax,
                     angular='unity', family='chebyshev', normalization='unity', radial_interval=None):
    """Synthesize one scalar or (poloidal,toroidal) pair; Fourier synthesis by m.

    B = curl(T r) + curl curl(P r): Q=l(l+1)P/r, S=P'+P/r.
    Btheta=S*dtheta(Y)+T*i*m*Y/sin(theta); Bphi=S*i*m*Y/sin(theta)-T*dtheta(Y).
    """
    vector = isinstance(coefficients, tuple)
    arrays = coefficients if vector else (coefficients,)
    shape = (len(radius), len(theta), len(phi))
    result = [np.zeros(shape) for _ in range(3 if vector else 1)]
    radial = {}
    shell_basis = chebyshev_shell(arrays[0].shape[1], radius, radial_interval) if radial_interval is not None else None
    by_m = {}
    for i, (l,m) in enumerate(pairs):
        if l <= lmax:
            by_m.setdefault(m, []).append((i,l))
    for m, entries in by_m.items():
        y, dy, my = harmonic_basis(lmax, m, theta)
        if angular != 'unity':
            degrees = np.arange(m, lmax+1)
            factors = np.sqrt(4*np.pi/(2*degrees+1))
            if angular == 'epm' and m: factors *= math.sqrt(2)
            y, dy, my = (a*factors[:,None] for a in (y,dy,my))
        sums = [np.zeros(shape[:2], dtype=complex) for _ in result]
        for i,l in entries:
            if l not in radial:
                radial[l] = shell_basis if shell_basis is not None else worland(l, arrays[0].shape[1], radius, family, normalization)
            w, over, tangent = radial[l]
            k = l-m
            if vector:
                if not l: continue
                q = l*(l+1)*(over @ arrays[0][i])
                s = tangent @ arrays[0][i]
                t = w @ arrays[1][i]
                sums[0] += q[:,None]*y[k]
                sums[1] += s[:,None]*dy[k] + 1j*t[:,None]*my[k]
                sums[2] += 1j*s[:,None]*my[k] - t[:,None]*dy[k]
            else:
                sums[0] += (w @ arrays[0][i])[:,None]*y[k]
        phase = np.exp(1j*m*phi)
        for out, value in zip(result, sums):
            # Block radial writes to avoid a second full 3D complex volume.
            for start in range(0, len(radius), 8):
                out[start:start+8] += (1 if m == 0 else 2)*np.real(value[start:start+8,:,None]*phase)
    if not all(np.isfinite(a).all() for a in result):
        raise ValueError('Spectral synthesis produced nonfinite fields.')
    return tuple(result) if vector else result[0]
