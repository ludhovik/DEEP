"""Scalar transport and derivatives of longitude means on native fluid grids."""
from __future__ import annotations

import numpy as np

MEAN_DERIVATIVES = {'dthetaT_phiavg', 'dthetaC_phiavg', 'dzup_phiavg'}
ADVECTION = {'advT', 'advC'}
SCALAR_DIAGNOSTICS = MEAN_DERIVATIVES | ADVECTION
DEFINITIONS = {
    'dthetaT_phiavg': 'd<T>_phi/dtheta; theta is colatitude in radians; no 1/r factor',
    'dthetaC_phiavg': 'd<C>_phi/dtheta; theta is colatitude in radians; no 1/r factor',
    'dzup_phiavg': 'd<up>_phi/dz at fixed s = cos(theta)*d<up>/dr - sin(theta)/r*d<up>/dtheta',
    'advT': 'u dot grad(T) = ur*dT/dr + ut/r*dT/dtheta + up/(r*sin(theta))*dT/dphi; positive sign',
    'advC': 'u dot grad(C) = ur*dC/dr + ut/r*dC/dtheta + up/(r*sin(theta))*dC/dphi; positive sign',
}


def longitude_mean(values, phi):
    """Periodic trapezoidal mean; arithmetic mean on a uniform longitude grid."""
    values = np.asarray(values, dtype=np.float64)
    phi = np.asarray(phi, dtype=np.float64)
    if len(phi) != values.shape[-1] or len(phi) < 2 or not np.isfinite(phi).all():
        raise ValueError('Invalid longitude coordinates for scalar diagnostics.')
    gaps = np.diff(np.r_[phi, phi[0] + 2 * np.pi])
    if np.any(gaps <= 0):
        raise ValueError('Longitudes must increase without a duplicate periodic seam.')
    if np.allclose(gaps, 2 * np.pi / len(phi), rtol=1e-6, atol=1e-10):
        return values.mean(axis=-1)
    weights = (gaps + np.roll(gaps, 1)) / (4 * np.pi)
    return np.einsum('rtp,p->rt', values, weights)


def derivative(values, coordinate, axis):
    return np.gradient(values, coordinate, axis=axis, edge_order=2 if len(coordinate) >= 3 else 1)


def dtheta_phi_average(values, r, theta, phi):
    result = derivative(longitude_mean(values, phi), theta, axis=1)
    # A regular scalar has one value at the origin, independently of angle.
    result[np.asarray(r) == 0] = 0
    return np.broadcast_to(result[..., None], np.shape(values))


def dz_up_phi_average(up, r, theta, phi):
    mean = longitude_mean(up, phi)
    r = np.asarray(r, dtype=np.float64)
    theta = np.asarray(theta, dtype=np.float64)
    safe_r = np.where(r != 0, r, np.inf)[:, None]
    result = (np.cos(theta)[None, :] * derivative(mean, r, axis=0)
              - np.sin(theta)[None, :] / safe_r * derivative(mean, theta, axis=1))
    # Smooth axisymmetric azimuthal velocity is s*Omega(s,z), hence this
    # derivative vanishes at the origin. No derivative crosses a padded ICB.
    result[r == 0] = 0
    return np.broadcast_to(result[..., None], np.shape(up))


def scalar_advection(velocity, gradients, scalar, r, theta, phi):
    """Positive u.grad(scalar), including a finite Cartesian centre limit."""
    ur, ut, up = (np.asarray(v, dtype=np.float64) for v in velocity)
    result = sum(v * np.asarray(g, dtype=np.float64) for v, g in zip((ur, ut, up), gradients))
    if np.asarray(r)[0] == 0:
        # The spherical angular gradient is undefined at r=0. Estimate the
        # regular l=1 Cartesian gradient from the native radial derivative,
        # rather than using zero angular components at this coordinate point.
        th, ph = np.meshgrid(theta, phi, indexing='ij')
        er = np.stack((np.sin(th)*np.cos(ph), np.sin(th)*np.sin(ph), np.cos(th)), axis=-1)
        et = np.stack((np.cos(th)*np.cos(ph), np.cos(th)*np.sin(ph), -np.sin(th)), axis=-1)
        ep = np.stack((-np.sin(ph), np.cos(ph), np.zeros_like(ph)), axis=-1)
        edge = 2 if len(r) >= 3 else 1
        # Only the first 2/3 rows are needed for the one-sided derivative.
        radial = derivative(np.asarray(scalar, dtype=np.float64)[:edge+1], np.asarray(r)[:edge+1], axis=0)[0]
        cart_grad = np.linalg.lstsq(er.reshape(-1, 3), radial.ravel(), rcond=None)[0]
        cart_u = ur[0, ..., None]*er + ut[0, ..., None]*et + up[0, ..., None]*ep
        centre = np.mean(cart_u, axis=(0, 1)) @ cart_grad
        result[0] = centre
    return result


def default_diagnostic_names(raw, args):
    if getattr(args, 'no_gradients', False):
        return []
    names = []
    if not getattr(args, 'no_m0_fields', False):
        names += [f'dtheta{s}_phiavg' for s in ('T', 'C') if s in raw]
        if 'up' in raw:
            names.append('dzup_phiavg')
    if all(v in raw for v in ('ur', 'ut', 'up')):
        names += [f'adv{s}' for s in ('T', 'C') if s in raw]
    return names


def iter_scalar_diagnostics(names, raw, radii, theta, phi, gradient, remap):
    """Yield (name, values, radius, source), leaving dependencies unexported.

    ``gradient(scalar_name)`` supplies physical spherical components on the
    scalar's native grid. Scalars and velocity may have different radial grids.
    """
    for name in names:
        dependencies = ('up',) if name == 'dzup_phiavg' else (
            (name[3:], 'ur', 'ut', 'up') if name in ADVECTION else (name[6],))
        for key in dependencies:
            if key not in raw:
                raise ValueError(f'--output {name} needs {key}, but this input does not contain it.')
        if name == 'dzup_phiavg':
            r = radii['up']
            yield name, dz_up_phi_average(raw['up'], r, theta, phi), r, 'velocity'
        elif name in MEAN_DERIVATIVES:
            scalar = name[6]
            r = radii[scalar]
            yield name, dtheta_phi_average(raw[scalar], r, theta, phi), r, 'scalar'
        elif name in ADVECTION:
            scalar = name[3:]
            r = np.asarray(radii[scalar])
            low = max(r[0], *(radii[v][0] for v in ('ur', 'ut', 'up')))
            high = min(r[-1], *(radii[v][-1] for v in ('ur', 'ut', 'up')))
            inside = (r >= low) & (r <= high)
            if np.count_nonzero(inside) < 2:
                raise ValueError(f'{name} needs at least two scalar radii in the common velocity/scalar domain.')
            target = r[inside]
            velocity = [raw[v] if np.array_equal(radii[v], target)
                        else remap(raw[v], radii[v], target) for v in ('ur', 'ut', 'up')]
            gradients = [g[inside] for g in gradient(scalar)]
            value = scalar_advection(velocity, gradients, raw[scalar][inside], target, theta, phi)
            yield name, value, target, 'scalar_velocity_overlap'
        else:
            raise ValueError(f'Unknown scalar diagnostic: {name}')


def scalar_diagnostic_metadata(fields):
    return {
        'definitions': {name: DEFINITIONS[name] for name in sorted(SCALAR_DIAGNOSTICS & set(fields))},
        'mean': 'longitude only; periodic trapezoidal weights; uniform grids use arithmetic mean',
        'theta': 'colatitude in radians',
        'z': 'axial coordinate r*cos(theta); derivative at fixed cylindrical radius s=r*sin(theta)',
        'scalar_policy': 'uses the same stored scalar as exported T/C; no additional background profile',
        'units': 'native code units; dtheta uses scalar units per radian, dzup uses velocity/length, adv uses velocity*scalar/length',
        'sampling': 'computed before viewer downsampling; finite differences on native physical grids',
        'centre': 'dtheta mean and dzup mean zero at r=0; advection uses Cartesian l=1 radial-derivative fit and mean Cartesian velocity',
    }
