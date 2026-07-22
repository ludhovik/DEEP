import numpy as np
import matplotlib.pyplot as plt
import h5py
from scipy import io
import shtns
from scipy.interpolate import RegularGridInterpolator, interp2d
from matplotlib.colors import LogNorm, Normalize
try:
    import cartopy.crs as ccrs
except ImportError:
    ccrs = None
#from scipy.fft import dct, idct
from scipy.interpolate import CubicSpline
from scipy.interpolate import UnivariateSpline


def cheb_diff_matrix(N, alpha_map=-1):
    """
    Generates the Chebyshev Differentiation Matrix for N+1 nodes
    on the standard interval [-1, 1].
    Assumes Chebyshev-Gauss-Lobatto (extrema) nodes: x_j = cos(pi*j/N)
    """
    if N == 0: return np.array([0])

    # Define the nodes
    x = np.cos(np.pi * np.arange(N + 1) / N)
    c = np.ones(N + 1)
    c[0] = 2; c[-1] = 2
    c = c * (-1)**np.arange(N + 1)

    X = np.tile(x, (N + 1, 1))
    dX = X - X.T

    # Off-diagonal entries
    D = (c[:, None] / c[None, :]) / (dX + np.eye(N + 1))

    # Diagonal entries (sum property: sum of rows must be 0)
    D = D - np.diag(np.sum(D, axis=1))

    if alpha_map > 0:
        y = np.arcsin(alpha_map * x) / np.arcsin(alpha_map)
        metric = np.arcsin(alpha_map) * np.sqrt(1 - alpha_map**2 * x**2) / alpha_map
        D = D * metric[:, None]
        return D, y

    return D, x

import numpy as np


def remove_m0(clm_shtns, sh):
    """
    Remove all m=0 coefficients from a SHTns spectral array.
    """
    clm_shtns_no_m0 = clm_shtns.copy()

    #print(sh.l.shape)
    #print(sh.m.shape)
    #print(sh.nlm)

    m0_mask = (sh.m == 0)

    if clm_shtns_no_m0.ndim == 1:
        clm_shtns_no_m0[m0_mask] = 0.0
    else:
        clm_shtns_no_m0[m0_mask, :] = 0.0

    return clm_shtns_no_m0   
    
def radial_derivative_Chebyshev(X, D):
    """
    Return the radial derivative of X using the Chebyshev derivative matrix D
    """
    
    X_rev = X[:, ::-1]
    dX_rev = np.matmul(D, X_rev.T).T
    return dX_rev[:, ::-1]
    #return  np.matmul(D, X.T).T

def radial_derivative_fd(X, R):
    #Radial derivative computed with finite differences
    DR = R[:,2:] - R[:,:-2]
    DR = np.concatenate((np.reshape((R[:,1]-R[:,0]), (DR.shape[0], 1)), DR, np.reshape((R[:,-1]-R[:,-2]), (DR.shape[0],1))), axis=1)
    DX = X[:,2:] - X[:,:-2]
    DX = np.concatenate((np.reshape((X[:,1]-X[:,0]), (DX.shape[0],1)), DX, np.reshape((X[:,-1]-X[:,-2]), (DX.shape[0],1))), axis=1)
    return(DX/DR)

def radial_derivative_fd2(X, dr):
    #Second order radial derivative computed with finite differences
    DR2 = dr**2
    D2X = X[:,2:] + X[:,:-2] - 2*X[:,1:-1]

    D2XDR2 = D2X/DR2
    D2XDR2_start = (X[:,2] - 2*X[:,1] + X[:,0])/DR2
    D2XDR2_end = (X[:,-1] - 2*X[:,-2] + X[:,-3])/DR2
    # D2XDR2_start = 2*(X[:,0]/(DRp[0]*(DRp[0]+DRp[1])) + X[:,1]/(DRp[0]*DRp[1]) + X[:,2]/(DRp[1]*(DRp[0]+DRp[1])))
    # D2XDR2_end = 2*(X[:,-1]/(DRp[-1]*(DRp[-1]+DRp[-2])) + X[:,-2]/(DRp[-1]*DRp[-2]) + X[:,-3]/(DRp[-2]*(DRp[-1]+DRp[-2])))

    D2XDR2 = np.concatenate((np.reshape((D2XDR2_start), (D2XDR2.shape[0],1)), D2XDR2, np.reshape((D2XDR2_end), (D2XDR2.shape[0],1))), axis=1)
    return(D2XDR2)

def radial_derivative_fd_var(X, R):
    #Radial derivative computed with finite difference on an irregular grid
    DR = R[:,1:] - R[:,:-1]
    DXDR = np.zeros(X.shape, dtype=complex)
    DRb = DR[:,:-1]
    DRf = DR[:,1:]
    num = DRb**2*X[:,2:] + (DRf**2-DRb**2)*X[:,1:-1] - DRf**2*X[:,:-2]
    den = DRf*DRb*(DRf+DRb)
    DXDR[:,1:-1] = num/den
    d1 = DR[0,0]
    d2 = DR[0,0]+ DR[0,1]
    DXDR[:,0] = (-d1**2*X[:,2] + d2**2*X[:,1] - (d2**2-d1**2)*X[:,0]) / (d1*d2*(d2-d1))
    d1 = DR[0,-1]
    d2 = DR[0,-1] + DR[0,-2]
    DXDR[:,-1] = (d1**2*X[:,-3] - d2**2*X[:,-2] + (d2**2-d1**2)*X[:,-1]) / (d1*d2*(d2-d1))
    return(DXDR)


def PolTor_to_qst(Pol, Tor, l, r, alpha_map=-1):
    """
    Computes the QST coefficients from Poloidal/Toroidal coefficients
    """
    L, R = np.meshgrid(l, r, indexing='ij')
    dPol_dr = np.zeros(Pol.shape)
    Nr = len(r)
    N = Nr - 1
    D_standard, _ = cheb_diff_matrix(N, alpha_map=alpha_map)
    D_physical = D_standard * (2.0 / (r[-1] - r[0]))
    dPol_dr = radial_derivative_Chebyshev(R*Pol, D_physical)
    dPol_dr = dPol_dr/R
    #dPol_dr = radial_derivative(R*Pol, r)/R
    #print(dPol_dr.shape, Pol.shape)
    Qlm = (L*(L+1)/R) * Pol
    Slm = -dPol_dr #check the sign
    Tlm = Tor  #check the sign
    return(Qlm, Slm, Tlm)

#def PolTor_to_qst_curl(Pol, Tor, l, r, alpha_map=-1):
#
#    Nr = len(r)
#    N = Nr - 1
#    D_standard, _ = cheb_diff_matrix(N, alpha_map=alpha_map)
#    D_physical = D_standard * (2.0 / (r[-1] - r[0]))
#    #dPol_dr = radial_derivative_Chebyshev(Pol, D_physical)
#    #D2_standard, _ = cheb_diff_matrix2(N, alpha_map=alpha_map)
#    #D2_physical = D2_standard * (2.0 / (r[-1] - r[0]))**2
#    #d2Pol_dr2 = radial_derivative_Chebyshev(Pol, D2_physical)
#    #D_physical = diff_matrix_from_nodes(r)
#    #dPol_dr = radial_derivative_Chebyshev(Pol, D_physical)
#    #d2Pol_dr2 *= (2.0 / (r[-1] - r[0]))**2
#    #d2Pol_dr2 = radial_derivative_Chebyshev(dPol_dr, D_physical)
#    
#    L, R = np.meshgrid(l, r, indexing='ij')
#    dr_min = (r[1] - r[0])
#    r_dense = np.arange(r[0], r[-1] + dr_min, dr_min)
#    L, R_dense = np.meshgrid(l, r_dense, indexing='ij')
#    spl = CubicSpline(r, Pol, axis=1)
#    Pol_dense = spl(r_dense)
#    spl = CubicSpline(r, Tor, axis=1)
#    Tor_dense = spl(r_dense)
#    dPol_dr = radial_derivative_fd(Pol_dense, R_dense)
#    d2Pol_dr2 = radial_derivative_fd(dPol_dr, R_dense)
#    dRTor_dr = radial_derivative_fd(R_dense*Tor_dense, R_dense)
#    spl = CubicSpline(r_dense, dPol_dr, axis=1)
#    dPol_dr = spl(r)
#    spl = CubicSpline(r_dense, d2Pol_dr2, axis=1)
#    d2Pol_dr2 = spl(r)
#    spl = CubicSpline(r_dense, dRTor_dr, axis=1)
#    dRTor_dr = spl(r)
#    
#
#    L, R = np.meshgrid(l, r, indexing='ij')
#    Qlm_curl = L*(L+1)*Tor/R
#    Slm_curl = dRTor_dr/R
#    #Slm_curl = radial_derivative_Chebyshev(R*Tor, D_physical)/R
#    Tlm_curl = -(d2Pol_dr2 + 2/R*dPol_dr - (L*(L+1)/R**2*Pol))
#    return(Qlm_curl, Slm_curl, Tlm_curl)

def lsd_to_shtns(coeffs_lsd, sh):
    """
    Tranform SH coefficients from LSD definition to shtns definition
    """
    coeffs_shtns = coeffs_lsd[0] + 1j*coeffs_lsd[1]
    #sh = shtns.sht(int(lmax), int(mmax), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    corr = np.zeros((len(sh.l)))
    corr[sh.m>0] = np.sqrt(2)
    corr[sh.m==0] = 1
    #print(len(corr))
    for k in range(coeffs_shtns.shape[1]):
        coeffs_shtns[:,k] *= corr
    return(coeffs_shtns)


# =============================================================================
# Leeds full-sphere regular transforms
# =============================================================================
# In a full sphere, the Leeds code stores regular radial functions in x=r^2:
#
#     P_lm(r) = r^(l+pP) G_lm(x),
#     T_lm(r) = r^(l+pT) H_lm(x).
#
# The direct coefficients passed to SHTns are
#
#     Q_lm = l(l+1) r^(l+pP-1) G_lm,
#     S_lm = +r^(l+pP-1) [(l+pP+1)G_lm + 2x dG_lm/dx],
#     T_lm = r^(l+pT) H_lm.
#
# The positive S sign follows the complete Leeds chain
# var_coll_TorPol2qst_fullsphere -> tra_qst2rtp_shtns.  It must not be
# confused with the spherical-shell helper above, where the Chebyshev matrix
# returns the negative physical r derivative and Slm=-dPol_dr compensates it.

FULLSPHERE_MODULE_API_VERSION = 2

REGULAR_RADIAL_REPRESENTATION = "regular_r_power_g_x"
CONVENTIONAL_RADIAL_REPRESENTATION = "conventional_r_coefficient"


def _is_full_sphere_grid(r, tolerance=1.0e-12):
    """Return True when the radial grid contains the geometrical centre."""
    rr = np.asarray(r, dtype=np.float64)
    if rr.ndim != 1 or rr.size == 0:
        return False
    scale = max(1.0, float(np.max(np.abs(rr))))
    return bool(abs(float(rr[0])) <= float(tolerance) * scale)


def fullsphere_x_derivative_matrix(r, derivative_order=1, half_width=3):
    """Build the Leeds local finite-difference matrix in x=r^2.

    This mirrors the local factorial-scaled Taylor construction used by the
    full-sphere Leeds mesh.  With half_width=3, an interior row uses seven
    radial points.  derivative_order=1 returns d/dx and order=2 returns d2/dx2.
    """
    rr = np.asarray(r, dtype=np.float64)
    if rr.ndim != 1:
        raise ValueError(f"r must be one-dimensional; received {rr.shape}.")
    x = rr * rr
    nrad = x.size
    if nrad < 3:
        raise ValueError("At least three radial points are required.")
    if not np.all(np.diff(x) > 0.0):
        raise ValueError("The full-sphere grid must increase strictly from r=0.")

    order = int(derivative_order)
    if order < 0:
        raise ValueError("derivative_order must be non-negative.")
    kl = min(int(half_width), max(1, (nrad - 1) // 2))
    D = np.zeros((nrad, nrad), dtype=np.float64)

    for n in range(nrad):
        left = max(0, n - kl)
        right = min(n + kl, nrad - 1)
        ids = np.arange(left, right + 1)
        nn = ids.size
        if order >= nn:
            raise ValueError(
                f"Derivative order {order} requires more than {nn} local points."
            )

        delta = x[ids] - x[n]
        A = np.ones((nn, nn), dtype=np.float64)
        for k in range(1, nn):
            A[:, k] = A[:, k - 1] * delta / float(k)

        try:
            invA = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            invA = np.linalg.pinv(A, rcond=1.0e-14)
        D[n, ids] = invA[order, :]

    return D, x


def derivative_in_fullsphere_x(values, r, derivative_order=1):
    """Differentiate arrays whose final axis is the full-sphere radial grid."""
    D, _ = fullsphere_x_derivative_matrix(r, derivative_order=derivative_order)
    arr = np.asarray(values)
    if arr.shape[-1] != D.shape[0]:
        raise ValueError(
            f"Radial size mismatch: values has {arr.shape[-1]}, grid has {D.shape[0]}."
        )
    return np.tensordot(arr, D.T, axes=([-1], [0]))


def _safe_radius_powers(r, powers):
    """Evaluate non-negative integer powers of r, including exactly r=0."""
    rr = np.asarray(r, dtype=np.float64)
    pp = np.asarray(powers, dtype=np.int64)
    if np.any(pp < 0):
        raise ValueError("A negative radial power is singular at r=0.")
    out = np.empty((pp.size, rr.size), dtype=np.float64)
    for i, power in enumerate(pp):
        out[i, :] = rr ** int(power)
    return out


def leeds_regular_projection_weights(r, power, stencil_size=7,
                                     amplitude_floor=1.0e-6):
    """Bounded Leeds projection from conventional f=r^p G to regular G(x).

    This is provided for legacy full-sphere states that store conventional
    coefficients.  New regular state files should set regular_coefficients=True
    and bypass this projection.
    """
    rr = np.asarray(r, dtype=np.float64)
    x = rr * rr
    nrad = rr.size
    K = min(int(stencil_size), nrad)
    if K % 2 == 0:
        K -= 1
    if K < 3:
        raise ValueError("Not enough radial points for regular projection.")
    if int(power) == 0:
        return np.eye(nrad, dtype=np.float64)

    half = K // 2
    nsafe = nrad - K
    for n in range(1, nrad - K + 1):
        if rr[n] ** int(power) >= float(amplitude_floor):
            nsafe = n
            break

    W = np.zeros((nrad, nrad), dtype=np.float64)
    for n in range(nsafe, nrad):
        i0 = max(nsafe, n - half)
        i0 = min(i0, nrad - K)
        ids = np.arange(i0, i0 + K)
        x0 = x[n]
        scale = max(float(np.max(np.abs(x[ids] - x0))), np.finfo(float).eps)
        z = (x[ids] - x0) / scale
        A = np.empty((K, K), dtype=np.float64)
        A[:, 0] = rr[ids] ** int(power)
        for k in range(1, K):
            A[:, k] = A[:, k - 1] * z
        try:
            invA = np.linalg.inv(A)
        except np.linalg.LinAlgError:
            invA = np.linalg.pinv(A, rcond=1.0e-13)
        W[n, ids] = invA[0, :]

    if nsafe > 0:
        W[:nsafe, :] = W[nsafe, :]
    return W


def conventional_lsd_to_regular(coeffs_lsd, r, degrees, power_offset=0):
    """Convert legacy conventional Leeds coefficients to regular G_lm(x)."""
    arr = np.asarray(coeffs_lsd, dtype=np.float64)
    if arr.ndim != 3 or arr.shape[0] != 2:
        raise ValueError(f"Expected coefficients (2,nlm,nr); received {arr.shape}.")
    if arr.shape[1] != len(degrees) or arr.shape[2] != len(r):
        raise ValueError("Coefficient dimensions do not match l or r.")

    out = np.empty_like(arr)
    weight_cache = {}
    for mode, degree in enumerate(np.asarray(degrees, dtype=int)):
        power = int(degree) + int(power_offset)
        if power not in weight_cache:
            weight_cache[power] = leeds_regular_projection_weights(r, power)
        W = weight_cache[power]
        out[0, mode, :] = W @ arr[0, mode, :]
        out[1, mode, :] = W @ arr[1, mode, :]
    return np.ascontiguousarray(out)


def PolTor_to_qst_fullsphere(Pol, Tor, l, r,
                             pol_power_offset=0, tor_power_offset=0):
    """Construct direct SHTns Q,S,T coefficients from regular G(x),H(x).

    Parameters
    ----------
    Pol, Tor : complex arrays, shape (nlm, nr)
        SHTns-normalised regular Leeds coefficients G_lm(x), H_lm(x).
    l : array_like
        Degree associated with each packed SHTns coefficient.
    r : array_like
        Strictly increasing radial grid beginning at r=0.

    Returns
    -------
    Qlm, Slm, Tlm : complex arrays, shape (nlm, nr)
        Coefficients ready for ``sh.synth(Qlm, Slm, Tlm)``.
    """
    G = np.asarray(Pol, dtype=np.complex128)
    H = np.asarray(Tor, dtype=np.complex128)
    rr = np.asarray(r, dtype=np.float64)
    degree = np.asarray(l, dtype=int)
    if G.shape != H.shape:
        raise ValueError(f"Poloidal and toroidal shapes differ: {G.shape}, {H.shape}.")
    if G.ndim != 2 or G.shape != (degree.size, rr.size):
        raise ValueError(
            f"Expected complex coefficients ({degree.size},{rr.size}); received {G.shape}."
        )

    Gx = derivative_in_fullsphere_x(G, rr, derivative_order=1)
    ll1 = degree * (degree + 1)
    pol_exponent = degree + int(pol_power_offset) - 1
    tor_exponent = degree + int(tor_power_offset)
    active = ll1 > 0

    pol_factor = np.zeros((degree.size, rr.size), dtype=np.float64)
    if np.any(active):
        if np.any(pol_exponent[active] < 0):
            raise ValueError("The selected poloidal power offset is singular at r=0.")
        pol_factor[active, :] = _safe_radius_powers(rr, pol_exponent[active])
    tor_factor = _safe_radius_powers(rr, tor_exponent)
    x = (rr * rr)[None, :]

    Qlm = ll1[:, None] * pol_factor * G

    # Correct direct SHTns sign for the regular full-sphere expression.
    Slm = pol_factor * (
        (degree + int(pol_power_offset) + 1)[:, None] * G
        + 2.0 * x * Gx
    )

    # Leeds code forms t_code=-sqrt(l(l+1))*r^l H; its SHTns wrapper applies
    # another minus sign, leaving the direct SHTns coefficient +r^l H.
    Tlm = tor_factor * H

    Qlm[~active, :] = 0.0
    Slm[~active, :] = 0.0
    Tlm[degree == 0, :] = 0.0
    return Qlm, Slm, Tlm


def PolTor_to_qst_curl_fullsphere(Pol, Tor, l, r):
    """Q,S,T coefficients of curl(u) for standard pP=pT=0 regular fields."""
    G = np.asarray(Pol, dtype=np.complex128)
    H = np.asarray(Tor, dtype=np.complex128)
    rr = np.asarray(r, dtype=np.float64)
    degree = np.asarray(l, dtype=int)
    Gx = derivative_in_fullsphere_x(G, rr, derivative_order=1)
    Gxx = derivative_in_fullsphere_x(G, rr, derivative_order=2)
    Hx = derivative_in_fullsphere_x(H, rr, derivative_order=1)

    ll1 = degree * (degree + 1)
    active = ll1 > 0
    rm1 = np.zeros((degree.size, rr.size), dtype=np.float64)
    rm1[active, :] = _safe_radius_powers(rr, degree[active] - 1)
    rl = _safe_radius_powers(rr, degree)
    x = (rr * rr)[None, :]

    Qlm = ll1[:, None] * rm1 * H
    Slm = rm1 * ((degree + 1)[:, None] * H + 2.0 * x * Hx)
    Tlm = -rl * (4.0 * x * Gxx + 2.0 * (2 * degree + 3)[:, None] * Gx)
    Qlm[~active, :] = 0.0
    Slm[~active, :] = 0.0
    Tlm[degree == 0, :] = 0.0
    return Qlm, Slm, Tlm


def _enforce_fullsphere_cartesian_center(ur, ut, up, theta, phi,
                                         center_tolerance=1.0e-12):
    """Replace the centre shell by its unique regular Cartesian vector."""
    vr = np.asarray(ur, dtype=np.float64).copy()
    vt = np.asarray(ut, dtype=np.float64).copy()
    vp = np.asarray(up, dtype=np.float64).copy()

    th = np.asarray(theta, dtype=np.float64)[:, None]
    ph = np.asarray(phi, dtype=np.float64)[None, :]
    st, ct = np.sin(th), np.cos(th)
    sp, cp = np.sin(ph), np.cos(ph)

    # This function is called only for a grid whose first radius is zero.
    ir = 0
    rr, tt, pp = vr[ir], vt[ir], vp[ir]
    ux = rr * st * cp + tt * ct * cp - pp * sp
    uy = rr * st * sp + tt * ct * sp + pp * cp
    uz = rr * ct - tt * st
    finite = np.isfinite(ux) & np.isfinite(uy) & np.isfinite(uz)
    if not np.any(finite):
        raise ValueError("No finite values were obtained at the full-sphere centre.")

    center = np.array([
        np.mean(ux[finite]),
        np.mean(uy[finite]),
        np.mean(uz[finite]),
    ])
    scale = float(np.nanmax(np.sqrt(vr * vr + vt * vt + vp * vp)))
    if np.linalg.norm(center) <= float(center_tolerance) * max(scale, 1.0):
        center[:] = 0.0

    vr[ir] = center[0] * st * cp + center[1] * st * sp + center[2] * ct
    vt[ir] = center[0] * ct * cp + center[1] * ct * sp - center[2] * st
    vp[ir] = -center[0] * sp + center[1] * cp
    return vr, vt, vp


def PolTor_to_spat_fullsphere(Pol, Tor, r, lmax, mmax,
                              pol_power_offset=0, tor_power_offset=0,
                              regular_coefficients=True,
                              pol_regular_coefficients=None,
                              tor_regular_coefficients=None,
                              enforce_center=True):
    """Transform Leeds full-sphere regular poloidal/toroidal coefficients."""
    lmax = _scalar_int(lmax, "lmax")
    mmax = _scalar_int(mmax, "mmax")
    rr = np.asarray(r, dtype=np.float64)
    if not _is_full_sphere_grid(rr):
        raise ValueError("PolTor_to_spat_fullsphere requires a radial grid beginning at r=0.")

    sh = shtns.sht(
        lmax, mmax, 1,
        shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE,
    )
    nlat, nphi = sh.set_grid()
    theta = np.arccos(sh.cos_theta)
    phi = np.linspace(0.0, 2.0 * np.pi, nphi + 2)[1:-1]

    pol_lsd = np.asarray(Pol)
    tor_lsd = np.asarray(Tor)
    pol_is_regular = (
        bool(regular_coefficients)
        if pol_regular_coefficients is None
        else bool(pol_regular_coefficients)
    )
    tor_is_regular = (
        bool(regular_coefficients)
        if tor_regular_coefficients is None
        else bool(tor_regular_coefficients)
    )
    if not pol_is_regular:
        pol_lsd = conventional_lsd_to_regular(
            pol_lsd, rr, sh.l, power_offset=pol_power_offset
        )
    if not tor_is_regular:
        tor_lsd = conventional_lsd_to_regular(
            tor_lsd, rr, sh.l, power_offset=tor_power_offset
        )

    G = lsd_to_shtns(pol_lsd, sh)
    H = lsd_to_shtns(tor_lsd, sh)
    Qlm, Slm, Tlm = PolTor_to_qst_fullsphere(
        G, H, sh.l, rr,
        pol_power_offset=pol_power_offset,
        tor_power_offset=tor_power_offset,
    )

    V_r = np.empty((rr.size, nlat, nphi), dtype=np.float64)
    V_tta = np.empty_like(V_r)
    V_phi = np.empty_like(V_r)
    for k in range(rr.size):
        V_r[k], V_tta[k], V_phi[k] = sh.synth(
            Qlm[:, k], Slm[:, k], Tlm[:, k]
        )

    if bool(enforce_center):
        V_r, V_tta, V_phi = _enforce_fullsphere_cartesian_center(
            V_r, V_tta, V_phi, theta, phi
        )

    if not (
        np.all(np.isfinite(V_r))
        and np.all(np.isfinite(V_tta))
        and np.all(np.isfinite(V_phi))
    ):
        raise ValueError("The full-sphere vector transform produced non-finite values.")
    return V_r, V_tta, V_phi, theta, phi


def PolTor_to_curl_spat_fullsphere(Pol, Tor, r, lmax, mmax,
                                   regular_coefficients=True,
                                   enforce_center=True):
    """Transform the curl of a standard regular full-sphere vector field."""
    lmax = _scalar_int(lmax, "lmax")
    mmax = _scalar_int(mmax, "mmax")
    rr = np.asarray(r, dtype=np.float64)
    sh = shtns.sht(
        lmax, mmax, 1,
        shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE,
    )
    nlat, nphi = sh.set_grid()
    theta = np.arccos(sh.cos_theta)
    phi = np.linspace(0.0, 2.0 * np.pi, nphi + 2)[1:-1]

    pol_lsd = np.asarray(Pol)
    tor_lsd = np.asarray(Tor)
    if not bool(regular_coefficients):
        pol_lsd = conventional_lsd_to_regular(pol_lsd, rr, sh.l, 0)
        tor_lsd = conventional_lsd_to_regular(tor_lsd, rr, sh.l, 0)

    G = lsd_to_shtns(pol_lsd, sh)
    H = lsd_to_shtns(tor_lsd, sh)
    Qlm, Slm, Tlm = PolTor_to_qst_curl_fullsphere(G, H, sh.l, rr)

    V_r = np.empty((rr.size, nlat, nphi), dtype=np.float64)
    V_tta = np.empty_like(V_r)
    V_phi = np.empty_like(V_r)
    for k in range(rr.size):
        V_r[k], V_tta[k], V_phi[k] = sh.synth(
            Qlm[:, k], Slm[:, k], Tlm[:, k]
        )
    if bool(enforce_center):
        V_r, V_tta, V_phi = _enforce_fullsphere_cartesian_center(
            V_r, V_tta, V_phi, theta, phi
        )
    return V_r, V_tta, V_phi, theta, phi


def SH_to_spat_fullsphere(clm, r, lmax, mmax, power_offset=0,
                          regular_coefficients=True):
    """Transform a scalar stored as f_lm=r^(l+p0)G_lm(r^2)."""
    lmax = _scalar_int(lmax, "lmax")
    mmax = _scalar_int(mmax, "mmax")
    rr = np.asarray(r, dtype=np.float64)
    sh = shtns.sht(
        lmax, mmax, 1,
        shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE,
    )
    nlat, nphi = sh.set_grid()
    theta = np.arccos(sh.cos_theta)
    phi = np.linspace(0.0, 2.0 * np.pi, nphi + 2)[1:-1]

    coeffs_lsd = np.asarray(clm)
    if bool(regular_coefficients):
        powers = np.asarray(sh.l, dtype=int) + int(power_offset)
        factors = _safe_radius_powers(rr, powers)
        coeffs_lsd = coeffs_lsd * factors[None, :, :]

    coeffs_shtns = lsd_to_shtns(coeffs_lsd, sh)
    A = np.empty((rr.size, nlat, nphi), dtype=np.float64)
    for k in range(rr.size):
        A[k] = sh.synth(coeffs_shtns[:, k])

    # A scalar is single-valued at the origin; only l=0 remains analytically.
    if _is_full_sphere_grid(rr):
        A[0, :, :] = np.mean(A[0])
    return A, theta, phi


def SH_to_spat_nom0_fullsphere(clm, r, lmax, mmax, power_offset=0,
                               regular_coefficients=True):
    """Transform a full-sphere scalar after removing its axisymmetric m=0 part."""
    lmax = _scalar_int(lmax, "lmax")
    mmax = _scalar_int(mmax, "mmax")
    rr = np.asarray(r, dtype=np.float64)
    sh = shtns.sht(
        lmax, mmax, 1,
        shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE,
    )
    nlat, nphi = sh.set_grid()
    theta = np.arccos(sh.cos_theta)
    phi = np.linspace(0.0, 2.0 * np.pi, nphi + 2)[1:-1]

    coeffs_lsd = np.asarray(clm)
    if bool(regular_coefficients):
        powers = np.asarray(sh.l, dtype=int) + int(power_offset)
        factors = _safe_radius_powers(rr, powers)
        coeffs_lsd = coeffs_lsd * factors[None, :, :]

    coeffs_shtns = lsd_to_shtns(coeffs_lsd, sh)
    coeffs_shtns = remove_m0(coeffs_shtns, sh)
    A = np.empty((rr.size, nlat, nphi), dtype=np.float64)
    for k in range(rr.size):
        A[k] = sh.synth(coeffs_shtns[:, k])

    if _is_full_sphere_grid(rr):
        A[0, :, :] = 0.0
    return A, theta, phi


def read_radial_representation(path, field):
    """Read radial representation metadata from an HDF5/NetCDF state field."""
    try:
        with h5py.File(path, "r") as f:
            var = f[field]
            representation = var.attrs.get("radial_representation", None)
            if isinstance(representation, bytes):
                representation = representation.decode("utf-8")
            elif hasattr(representation, "item"):
                representation = representation.item()
                if isinstance(representation, bytes):
                    representation = representation.decode("utf-8")
            offset = var.attrs.get("radial_power_offset", 0)
            offset = int(np.asarray(offset).reshape(-1)[0])
            return {"representation": representation, "power_offset": offset}
    except Exception:
        f = io.netcdf_file(path, mmap=False)
        try:
            var = f.variables[field]
            representation = getattr(var, "radial_representation", None)
            if isinstance(representation, bytes):
                representation = representation.decode("utf-8")
            offset = int(np.asarray(getattr(var, "radial_power_offset", 0)).reshape(-1)[0])
            return {"representation": representation, "power_offset": offset}
        finally:
            f.close()


def load_state(path, fields=None):
    """
    Load selected fields from a state file.

    fields: list or None
        e.g. ['uP','uT','C','Comp','r']
        if None → load everything (default behavior)
    """

    if fields is None:
        fields = ['uP', 'uT', 'BP', 'BT', 'C', 'Comp', 'r', 'lmax', 'mmax', 't']

    try:
        f = h5py.File(path)

        data = {}

        # fields in file
        if 'uP' in fields:
            data['uP'] = f['uP'][:]
        if 'uT' in fields:
            data['uT'] = f['uT'][:]
        if 'BP' in fields:
            data['BP'] = f['BP'][:]
        if 'BT' in fields:
            data['BT'] = f['BT'][:]
        if 'C' in fields:
            data['C'] = f['C'][:]
        if 'Comp' in fields:
            data['Comp'] = f['Comp'][:] if 'Comp' in f else None
        if 'r' in fields:
            data['r'] = f['r'][:]

        # metadata always available if requested
        if 'lmax' in fields:
            data['lmax'] = f['uP'].attrs['L'] - 1
        if 'mmax' in fields:
            data['mmax'] = f['uP'].attrs['M'] - 1
        if 't' in fields:
            data['t'] = f.attrs['t'][0]

        f.close()

    except:
        f = io.netcdf_file(path)

        data = {}

        if 'uP' in fields:
            data['uP'] = f.variables['uP'][:]
        if 'uT' in fields:
            data['uT'] = f.variables['uT'][:]
        if 'BP' in fields:
            data['BP'] = f.variables['BP'][:]
        if 'BT' in fields:
            data['BT'] = f.variables['BT'][:]
        if 'C' in fields:
            data['C'] = f.variables['C'][:]
        if 'Comp' in fields:
            data['Comp'] = f.variables['Comp'][:] if 'Comp' in f.variables else None
        if 'r' in fields:
            data['r'] = f.variables['r'][:]

        if 'lmax' in fields:
            data['lmax'] = f.variables['uP'].L - 1
        if 'mmax' in fields:
            data['mmax'] = f.variables['uP'].M - 1
        if 't' in fields:
            data['t'] = f.t

        f.close()

    return data

def _scalar_int(value, name):
    arr = np.asarray(value)
    if arr.size != 1:
        raise ValueError(
            f"{name} must contain one value, but received "
            f"shape={arr.shape}, values={arr}"
        )
    return int(arr.item())


def PolTor_to_spat(Pol, Tor, r, lmax, mmax, alpha_map=-1,
                   full_sphere=None, regular_coefficients=True,
                   pol_power_offset=0, tor_power_offset=0,
                   enforce_center=True):
    """Transform poloidal/toroidal coefficients into spherical components.

    The existing spherical-shell path is retained unchanged.  A grid beginning
    at r=0 is dispatched automatically to the Leeds regular full-sphere path.
    Set ``full_sphere=False`` to force the shell path or ``full_sphere=True`` to
    force the regular path.
    """
    lmax = _scalar_int(lmax, "lmax")
    mmax = _scalar_int(mmax, "mmax")
    if full_sphere is None:
        full_sphere = _is_full_sphere_grid(r)
    if bool(full_sphere):
        return PolTor_to_spat_fullsphere(
            Pol, Tor, r, lmax, mmax,
            pol_power_offset=pol_power_offset,
            tor_power_offset=tor_power_offset,
            regular_coefficients=regular_coefficients,
            enforce_center=enforce_center,
        )

    # Validated spherical-shell path.  Do not change Slm=-dPol_dr in
    # PolTor_to_qst: radial_derivative_Chebyshev has the opposite derivative
    # orientation, and this minus sign restores the physical radial derivative.
    sh = shtns.sht(
        lmax, mmax, 1,
        shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE,
    )
    nlat, nphi = sh.set_grid()
    tta = np.arccos(sh.cos_theta)
    phi = np.linspace(0, 2*np.pi, nphi+2)[1:-1]

    Pol_shtns = lsd_to_shtns(Pol, sh)
    Tor_shtns = lsd_to_shtns(Tor, sh)
    Qlm, Slm, Tlm = PolTor_to_qst(
        Pol_shtns, Tor_shtns, sh.l, r, alpha_map=alpha_map
    )

    V_r = np.zeros((len(r), nlat, nphi))
    V_tta = np.zeros((len(r), nlat, nphi))
    V_phi = np.zeros((len(r), nlat, nphi))
    for k in range(Qlm.shape[1]):
        V_r[k], V_tta[k], V_phi[k] = sh.synth(
            Qlm[:, k], Slm[:, k], Tlm[:, k]
        )
    return V_r, V_tta, V_phi, tta, phi

def _PolTor_to_curl_spat_shell(Pol, Tor, r, lmax, mmax, alpha_map):
    """
    Tranform Pol Tor coefficients into spatial curl components
    """
    sh = shtns.sht(int(lmax), int(mmax), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    nlat, nphi = sh.set_grid()
    tta = np.arccos(sh.cos_theta)
    phi = np.linspace(0, 2*np.pi, nphi+2)[1:-1]

    Pol_shtns = lsd_to_shtns(Pol, sh)
    Tor_shtns = lsd_to_shtns(Tor, sh)

    Pol_curl, Tor_curl = PolTor_to_curl_PolTor(Pol_shtns, Tor_shtns, r, sh, alpha_map=alpha_map)    

    Qlm, Slm, Tlm = PolTor_to_qst(Pol_curl, Tor_curl, sh.l, r, alpha_map=alpha_map)

    ## Qlm, Slm, Tlm = PolTor_to_qst(Pol_shtns, Tor_shtns, sh.l, r, alpha_map=alpha_map)

    # Qlm, Slm, Tlm = PolTor_to_qst_curl(Pol_shtns, Tor_shtns, sh.l, r, alpha_map=alpha_map)

    V_r = np.zeros((len(r), nlat, nphi))
    V_tta = np.zeros((len(r), nlat, nphi))
    V_phi = np.zeros((len(r), nlat, nphi))
    for k in range(Qlm.shape[1]):
        V_r[k], V_tta[k], V_phi[k] = sh.synth(Qlm[:,k], Slm[:,k], Tlm[:,k])
    
    return(V_r, V_tta, V_phi, tta, phi)


def PolTor_to_curl_spat(Pol, Tor, r, lmax, mmax, alpha_map=-1,
                        full_sphere=None, regular_coefficients=True,
                        enforce_center=True):
    """Curl transform with automatic shell/full-sphere dispatch."""
    if full_sphere is None:
        full_sphere = _is_full_sphere_grid(r)
    if bool(full_sphere):
        return PolTor_to_curl_spat_fullsphere(
            Pol, Tor, r, lmax, mmax,
            regular_coefficients=regular_coefficients,
            enforce_center=enforce_center,
        )
    return _PolTor_to_curl_spat_shell(
        Pol, Tor, r, lmax, mmax, alpha_map
    )


def PolTor_to_curl_PolTor(Pol, Tor, r, sh, alpha_map, lmax=None):
    """
    Transform Pol Tor coefficients to the equivalent coefficients for the curl
    """
    if lmax == None:
        lmax = np.max(sh.l)
    Pol[sh.l>lmax] *= 0
    Tor[sh.l>lmax] *= 0

    L, R = np.meshgrid(sh.l, r, indexing='ij')
    
    Nr = len(r)
    N = Nr - 1
    #D_standard, _ = cheb_diff_matrix(N, alpha_map=alpha_map)
    #D_physical = D_standard * (2.0 / (r[-1] - r[0]))

    #D2_standard, _ = cheb_diff_matrix2(N, alpha_map=alpha_map)
    #D2_physical = D2_standard * (2.0 / (r[-1] - r[0]))**2

    #rPol = cheb_filter_radial(R*Pol, axis=-1, p=8, beta=20)
    rPol = R*Pol
    # d_rPol = radial_derivative_Chebyshev(rPol, D_physical)
    # d2_rPol = radial_derivative_Chebyshev(d_rPol, D_physical)
    #d2_rPol = radial_derivative_Chebyshev(rPol, D2_physical)

    ##finite difference
    #Finite differences are used here because of instabilities in the Chebyshev matrix when computing the curl
    d_rPol = radial_derivative_fd_var(rPol, R)
    d2_rPol = radial_derivative_fd_var(d_rPol, R)
    
    ##spline derivative
    # dr_min = (r[1] - r[0])
    # r_dense = np.arange(r[0], r[-1] + dr_min, dr_min)
    # spl = CubicSpline(r, rPol, axis=1)
    # d2_rPol = spl(r,2)

    ##spline smoothed
    # d2_rPol = np.zeros(rPol.shape)
    # for k in range(len(rPol)):
    #     d2_rPol[k] = smooth_second_derivative(r, rPol[k], s=0)
    
    Pol_curl = Tor.copy()
    Tor_curl = -(d2_rPol/R) + (L*(L+1)/R**2) * Pol
    
    return(Pol_curl, Tor_curl)


def gradient_spat(A, r, tta, phi=[]):
    """
    Computes the gradient of the scalar field A using finite differences. 
    A should be phi-averaged, unless the phi coordinates are provided.
    """
    if len(phi)==0:
        R, TTA = np.meshgrid(r, tta, indexing='ij')
    else:
        R, TTA, PHI = np.meshgrid(r, tta, phi, indexing='ij')
    # dA_dr = np.zeros(A.shape)
    # dA_dr[1:-1] = (A[2:] - A[:-2]) / (R[2:] - R[:-2])
    # dA_dr[0] = (A[1] - A[0]) / (R[1] - R[0])
    # dA_dr[-1] = (A[-1] - A[-2]) / (R[-1] - R[-2])
    #radial derivative
    DR = R[1:] - R[:-1]
    dA_dr = np.zeros(A.shape)
    DRb = DR[:-1]
    DRf = DR[1:]
    num = DRb**2*A[2:] + (DRf**2-DRb**2)*A[1:-1] - DRf**2*A[:-2]
    den = DRf*DRb*(DRf+DRb)
    dA_dr[1:-1] = num/den
    d1 = DR[0,0]
    d2 = DR[0,0]+ DR[1,0]
    dA_dr[0] = (-d1**2*A[2] + d2**2*A[1] - (d2**2-d1**2)*A[0]) / (d1*d2*(d2-d1))
    #d1 = DR[0,-1]
    #d2 = DR[0,-1] + DR[0,-2]
    d1 = DR[-1,0]
    d2 = DR[-1,0] + DR[-2,0]
    dA_dr[-1] = (d1**2*A[-3] - d2**2*A[-2] + (d2**2-d1**2)*A[-1]) / (d1*d2*(d2-d1))

    dA_dtta = np.zeros(A.shape)
    dA_dtta[:,1:-1] = (A[:,2:] - A[:,:-2]) / (TTA[:,2:] - TTA[:,:-2])
    dA_dtta[:,0] = (-3*A[:,0] + 4*A[:,1] - A[:,2]) / (TTA[:,2] - TTA[:,0])
    dA_dtta[:,-1] = (A[:,-3] - 4*A[:,-2] +3*A[:,-1]) / (TTA[:,-1] - TTA[:,-3])
    
    grad_r = dA_dr
    grad_tta = dA_dtta/R

    if len(phi)!=0:
        dA_dphi = np.zeros(A.shape)
        dA_dphi[:,:,1:-1] = (A[:,:,2:] - A[:,:,:-2]) / (PHI[:,:,2:] - PHI[:,:,:-2])
        dA_dphi[:,:,0] = (-3*A[:,:,0] + 4*A[:,:,1] - A[:,:,2]) / (PHI[:,:,2] - PHI[:,:,0])
        dA_dphi[:,:,-1] = (A[:,:,-3] - 4*A[:,:,-2] +3*A[:,:,-1]) / (PHI[:,:,-1] - PHI[:,:,-3])

        grad_phi = dA_dphi/(R*np.sin(TTA))
        return(grad_r, grad_tta, grad_phi)

    return(grad_r, grad_tta)



def curl_spat(A, r, tta, phi=[]):
    """
    Computes the curl of the scalar field A using finite differences
    """
    if len(phi)==0:
        R, TTA = np.meshgrid(r, tta, indexing='ij')
    else:
        R, TTA, PHI = np.meshgrid(r, tta, phi, indexing='ij')
    dA_dr = np.zeros(A.shape)
    dA_dr[1:-1] = (A[2:] - A[:-2]) / (R[2:] - R[:-2])
    dA_dr[0] = (A[1] - A[0]) / (R[1] - R[0])
    dA_dr[-1] = (A[-1] - A[-2]) / (R[-1] - R[-2])

    dA_dtta = np.zeros(A.shape)
    dA_dtta[:,1:-1] = (A[:,2:] - A[:,:-2]) / (TTA[:,2:] - TTA[:,:-2])
    dA_dtta[:,0] = (A[:,1] - A[:,0]) / (TTA[:,1] - TTA[:,0])
    dA_dtta[:,-1] = (A[:,-1] - A[:,-2]) / (TTA[:,-1] - TTA[:,-2])
    
    grad_r = dA_dr
    grad_tta = dA_dtta/R

    if len(phi)!=0:
        dA_dphi = np.zeros(A.shape)
        dA_dphi[:,:,1:-1] = (A[:,:,2:] - A[:,:,:-2]) / (PHI[:,:,2:] - PHI[:,:,:-2])
        dA_dphi[:,:,0] = (A[:,:,1] - A[:,:,0]) / (PHI[:,:,1] - PHI[:,:,0])
        dA_dphi[:,:,-1] = (A[:,:,-1] - A[:,:,-2]) / (PHI[:,:,-1] - PHI[:,:,-2])

        grad_phi = dA_dphi/(R*np.sin(TTA))
        return(grad_r, grad_tta, grad_phi)

    return(grad_r, grad_tta)

def SH_to_spat(clm, lmax, mmax, r=None, full_sphere=None,
               power_offset=0, regular_coefficients=True):
    """Transform scalar coefficients, with optional regular full-sphere mode.

    Existing calls ``SH_to_spat(clm,lmax,mmax)`` retain the conventional shell
    behaviour.  For a regular full-sphere scalar, pass its radial grid as ``r``.
    """
    if r is not None:
        if full_sphere is None:
            full_sphere = _is_full_sphere_grid(r)
        if bool(full_sphere):
            return SH_to_spat_fullsphere(
                clm, r, lmax, mmax,
                power_offset=power_offset,
                regular_coefficients=regular_coefficients,
            )

    sh = shtns.sht(
        int(lmax), int(mmax), 1,
        shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE,
    )
    nlat, nphi = sh.set_grid()
    tta = np.arccos(sh.cos_theta)
    phi = np.linspace(0, 2*np.pi, nphi+2)[1:-1]
    clm_shtns = lsd_to_shtns(clm, sh)
    A = np.zeros((clm_shtns.shape[1], nlat, nphi))
    for k in range(clm_shtns.shape[1]):
        A[k] = sh.synth(clm_shtns[:, k])
    return A, tta, phi
    
def SH_to_spat_nom0(clm, lmax, mmax):

    sh = shtns.sht(
        int(lmax),
        int(mmax),
        1,
        shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE
    )

    nlat, nphi = sh.set_grid()

    tta = np.arccos(sh.cos_theta)
    phi = np.linspace(0, 2*np.pi, nphi+2)[1:-1]

    clm_shtns = lsd_to_shtns(clm, sh)

    # remove axisymmetric component
    clm_shtns = remove_m0(clm_shtns, sh)

    A = np.zeros((clm_shtns.shape[1], nlat, nphi))

    for k in range(clm_shtns.shape[1]):
        A[k] = sh.synth(clm_shtns[:, k])

    return A, tta, phi

def read_gauss(path_to_sim, lmax='maxi'):
    """
    Read the Gauss coefficients from the simulation stored at path_to_sim up to maximum degree lmax.
    Returns GLM (4d array: time x l x m x cos/sin) and t (1d time array)
    """
    try:
        d = np.loadtxt(path_to_sim+'/GLM/gauss_coeffs_surface')
        t = np.loadtxt(path_to_sim+'/GLM/gauss_coeffs_time', skiprows=1)[:,0]
    except:
        d = np.loadtxt(path_to_sim+'/GAUSS/gauss_coeffs_surface')
        t = np.loadtxt(path_to_sim+'/GAUSS/gauss_coeffs_time', skiprows=1)[:,0]
    L = d[:,0]
    M = d[:,1]
    c_lmt = d[:,2]
    
    dt = np.diff(t)
    M_corr = M
    for k in range(1,len(M)):
        if M[k] == M[k-1]:
            M_corr[k] *= -1
    M = M_corr
    if lmax=='maxi':
        GLM = np.zeros((len(t),int(L.max())+1,int(M.max())+1,2))
    else:
        GLM = np.zeros((len(t),lmax+1,lmax+1,2))
    for l in range(1,GLM.shape[1]):
        print('Load degree ' + str(l))
        conv = 1
        for m in range(0,l+1):
            c_t_mpos = c_lmt[(L==l)&(M==m)][:]
            GLM[:,l,m,0] = c_t_mpos*conv
            if m>0:
                c_t_mneg = c_lmt[(L==l)&(M==-m)][:]
                GLM[:,l,m,1] = c_t_mneg*conv
    return(GLM, t)
      

def plot_surf(dat, tta, phi,
              cmap,
              label,
              vmin,
              vmax,
              nb_levels=41,
              ax=None):

    if ax is None:
        if ccrs is None:
            raise ImportError("plot_surf requires Cartopy; install cartopy to use map plotting.")
        ax = plt.axes(projection=ccrs.Mollweide())

    ax.set_global()
    ax.gridlines()

    p = ax.contourf(
        phi*180/np.pi - 180,
        90 - tta*180/np.pi,
        dat,
        transform=ccrs.PlateCarree(),
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        levels=np.linspace(vmin, vmax, nb_levels),
        extend='both'
    )

    cb = plt.colorbar(p, ax=ax)
    cb.set_label(label=label, size=15)
    cb.ax.tick_params(labelsize=12)

    return p
    

def plot_merid(field, r, tta,
               title='None',
               cmap='bwr',
               savepath='None',
               minmax_equal=True,
               mini=None,
               maxi=None,
               nb_levels=41,
               saturation=1,
               contours=[],
               minmax_equal_contours=True,
               saturation_contours=1,
               nb_levels_contours=21):
    """
    Meridional slice plot: field(r, theta)

    Adds θ=0 and θ=π by boundary extension (no interpolation).
    """

    # ==========================================
    # Extend theta with boundary values
    # ==========================================
    field_ext = np.zeros((field.shape[0], field.shape[1] + 2))
    field_ext[:, 1:-1] = field
    field_ext[:, 0] = field[:, 0]        # θ = 0
    field_ext[:, -1] = field[:, -1]      # θ = π

    # extended theta grid
    dtheta = tta[1] - tta[0]
    tta_ext = np.concatenate((
        [0],
        tta,
        [np.pi]
    ))

    # ==========================================
    # Interpolator
    # ==========================================
    fT = RegularGridInterpolator((r, tta_ext), field_ext, bounds_error=False)

    # ==========================================
    # Grid for plotting
    # ==========================================
    R_plot, TTA_plot = np.meshgrid(r, tta_ext, indexing='ij')

    X_plot = R_plot * np.sin(TTA_plot)
    Y_plot = R_plot * np.cos(TTA_plot)

    # ==========================================
    # Plot setup
    # ==========================================
    plt.axis("equal")
    plt.axis("off")
    plt.title(title, fontsize=20)

    # ==========================================
    # Color scaling
    # ==========================================
    if maxi is None:
        maxi = np.max(field) * saturation
    if mini is None:
        mini = np.min(field) * saturation

    if minmax_equal:
        m = max(abs(maxi), abs(mini))
        maxi, mini = m, -m

    norm = Normalize(vmin=mini, vmax=maxi)

    # ==========================================
    # Main plot
    # ==========================================
    p = plt.contourf(
        X_plot, Y_plot,
        fT((R_plot, TTA_plot)),
        levels=np.linspace(mini, maxi, nb_levels),
        cmap=cmap,
        norm=norm,
        extend='both'
    )

    # ==========================================
    # Optional contour overlay
    # ==========================================
    if len(contours) > 0:

        if minmax_equal_contours:
            m = max(abs(np.max(contours)), abs(np.min(contours)))
            cmax, cmin = m * saturation_contours, -m * saturation_contours
        else:
            cmax = np.max(contours) * saturation_contours
            cmin = np.min(contours) * saturation_contours

        fC = RegularGridInterpolator((r, tta_ext), contours, bounds_error=False)

        plt.contour(
            X_plot, Y_plot,
            fC((R_plot, TTA_plot)),
            levels=nb_levels_contours,
            colors='grey',
            vmin=cmin,
            vmax=cmax
        )

    return p


def plot_equat(field, r, phi,
               title='None',
               cmap='bwr',
               minmax_equal=True,
               mini=None,
               maxi=None,
               nb_levels=41,
               alpha=1,
               linestyles='None',
               linewidths=1,
               pcolormesh=False,
               contours_cmap='None',
               contours_color='grey',
               saturation=1):
    """
    Equatorial slice plot for field(r, theta, phi)

    field shape: (Nr, Ntheta, Nphi)
    """

    # ==========================================
    # Equatorial plane (theta = pi/2)
    # ==========================================
    itta_eq = field.shape[1] // 2
    field_eq = field[:, itta_eq, :]   # (r, phi)

    # ==========================================
    # Enforce periodicity in phi (FIELD only)
    # ==========================================
    field_eq = np.concatenate((field_eq, field_eq[:, :1]), axis=1)

    # Build a clean periodic phi grid
    phi_plot = np.linspace(0, 2*np.pi, field_eq.shape[1])

    # ==========================================
    # Cartesian grid
    # ==========================================
    R, PHI = np.meshgrid(r, phi_plot, indexing='ij')
    X = R * np.cos(PHI)
    Y = R * np.sin(PHI)

    # ==========================================
    # Plot setup
    # ==========================================
    plt.axis("equal")
    plt.axis("off")
    if title != 'None':
        plt.title(title, fontsize=20)

    # ==========================================
    # Color limits
    # ==========================================
    if maxi is None:
        maxi = np.max(field_eq) * saturation
    if mini is None:
        mini = np.min(field_eq) * saturation

    if minmax_equal:
        m = max(abs(maxi), abs(mini))
        maxi, mini = m, -m

    norm = Normalize(vmin=mini, vmax=maxi)

    # ==========================================
    # Plot
    # ==========================================
    if cmap != 'None':
        p = plt.contourf(
            X, Y,
            field_eq,
            levels=np.linspace(mini, maxi, nb_levels),
            cmap=cmap,
            norm=norm,
            extend='both',
            alpha=alpha
        )
    elif pcolormesh:
        p = plt.pcolormesh(
            X, Y,
            field_eq,
            cmap=cmap,
            norm=norm,
            extend='both',
            alpha=alpha
        )
    else:
        p = plt.contour(
            X, Y,
            field_eq,
            levels=np.linspace(mini, maxi, nb_levels),
            norm=norm,
            #colors=contours_color,
            cmap=contours_cmap,
            linestyles=linestyles,
            linewidths=linewidths
        )

    return p

def plot_merid_combine(merids,
                       r,
                       tta,
                       cmaps,
                       labels,
                       nb_levels=21,
                       sats=[0.5,0.5],
                       figsize=(13.5,8),
                       logscales=[False,False],
                       maxs=[None,None],
                       mins=[None,None],
                       minmax_equals=[True,True],
                       title=None,
                       extends=['both','both'],
                       color_extends=[[None,None],[None,None]],
                       c_datas=[None,None],
                       c_rs=[None,None],
                       c_ttas=[None,None],
                       c_colors=[None,None],
                       c_linestyles=[None,None],
                       c_levels=[None,None],
                       colorbars=True,
                       Ustreams=[None,None],
                       Ninterp=3,
                       Ngrid=100,
                       fontsize_ticks=12,
                       fontsize_label=15,):
    """
    Plot two meridional slices, one on the right side and the second one mirrored on the left side
    """
    shift_x = 0.05
    plt.axis("equal")
    plt.axis("off")
    if title != None:
        plt.title(title, fontsize=20)
    for i in range(len(merids)):
        merid = merids[i]
        Ustream = Ustreams[i]
        minmax_equal = minmax_equals[i]
        extend = extends[i]
        color_extend = color_extends[i]
        cmap = cmaps[i]
        sat = sats[i]
        if color_extend[0] != None:
            cmap.set_under(color_extend[0])
        if color_extend[0] != None:
            cmap.set_over(color_extend[1])
        label = labels[i]
        c_data = c_datas[i]
        rc = c_rs[i]
        ttac = c_ttas[i]
        c_color = c_colors[i]
        c_linestyle = c_linestyles[i]
        c_level = c_levels[i]
        mini, maxi = mins[i], maxs[i]
        logscale = logscales[i]
        location = 'right'
        side = 1
        if i == 1:
            side = -1
            # tta *= -1
            # Ustream[:,1] *= 1
            location = 'left'
        #######################################################################
        merid[np.logical_not(np.isfinite(merid))] = 0
        # Bmerid[np.logical_not(np.isfinite(Bmerid))] = 0
        r_corr = r[(len(r) - merid.shape[0]):]
        # rB = r[(len(r) - Bmerid.shape[0]):]
        tta_plot = np.arange(0, np.pi*(1+1/tta.shape[0]), np.pi/tta.shape[0])
        tta_plot *= np.sign(tta[0])
        if type(ttac) != type(None):
            ttac_plot = np.arange(0, np.pi*(1+1/ttac.shape[0]), np.pi/ttac.shape[0])
            ttac_plot *= np.sign(ttac[0])
        #print(r_corr.shape, tta.shape, merid.T.shape)
        f = interp2d(r_corr, tta, merid.T , kind='linear')
        if np.all(c_data!=None):
            rc_corr = rc[(len(rc) - c_data.shape[0]):]
            f_c = interp2d(rc_corr, ttac, c_data.T, kind='linear')
            Rc_plot,TTAc_plot = np.meshgrid(rc_corr,ttac_plot,indexing='xy')
            Xc_plot, Yc_plot = Rc_plot*np.sin(TTAc_plot), Rc_plot*np.cos(TTAc_plot)
        R_plot,TTA_plot = np.meshgrid(r_corr,tta_plot,indexing='xy')
        X_plot, Y_plot = R_plot*np.sin(TTA_plot), R_plot*np.cos(TTA_plot)

        if minmax_equal :
            maxi = np.max((np.max(merid), -np.min(merid)))*sat
            mini = -maxi
            if maxi>10:
                ticks = np.linspace(-(int(maxi)-int(maxi)%3),
                                    int(maxi)-int(maxi)%3, 7)
            else:
                ticks = np.linspace(-1,1,7)*maxi
        else:
            if mini == None:
                mini = np.min(merid[np.isfinite(merid)])*sat
            else:
                mini = mini
            if maxi == None:
                maxi = np.max(merid[np.isfinite(merid)])*sat
            else:
                maxi = maxi
            ticks = np.linspace(mini,
                                maxi, 9)

        if logscale:
            norm = LogNorm(vmin=mini,vmax=maxi)
        else:
            norm = Normalize(vmin=mini,vmax=maxi)

        if nb_levels < 1000:
            axp = plt.contourf((X_plot+shift_x)*side, Y_plot, f(r_corr,tta_plot), levels=np.linspace(mini,maxi,nb_levels),
                         cmap=cmap, norm=norm, extend=extend)
        else:
            axp = plt.pcolormesh((X_plot+shift_x)*side, Y_plot, f(r_corr,tta_plot),
                         cmap=cmap, norm=norm, shading='nearest')
        #plt.axvline(x=0, ymin=-1, ymax=1, linestyle='--', color='black', linewidth=4)
        if logscale:
            if colorbars:
                cb = plt.colorbar(axp, ax=[ax],location=location, pad=0.1)
        else:
            if colorbars:
                nb_decimal = 3
                if np.max((maxi,-mini))<0.02:
                    nb_decimal = 4
                cb = plt.colorbar(axp,location=location, pad=-0.01, ticks=np.around(ticks,nb_decimal))
        if colorbars:
            cb.set_label(label=label,size=fontsize_label, labelpad=-0)
            cb.ax.tick_params(labelsize=fontsize_ticks)
        shift = 0.05
        if np.all(c_data!=None):
            if type(c_level) == int:
                c_max = np.max(np.abs(c_data))
                levels = np.linspace(-c_max,c_max,c_level)
            else:
                levels = c_level
            CS = plt.contour((Xc_plot+shift_x)*side, Yc_plot, f_c(rc_corr, ttac_plot), colors=c_color, levels=levels, linestyles=c_linestyle)
            # ax.clabel(CS, inline=True, fontsize=10)
    plt.ylim(-1.02*r[-1],1.02*r[-1])
    plt.xlim(-1.1*r[-1]-shift_x, 1.1*r[-1]+shift_x)
    arc_angles = np.linspace(-np.pi/2, np.pi/2, 40)
    ri = r_corr[0]
    ro = r_corr[-1]
    arc_xs = ri * np.cos(arc_angles)
    arc_ys = ri * np.sin(arc_angles)
    lw=3
    plt.plot(arc_xs+shift_x, arc_ys, color = 'black', lw = lw, ls='--')
    plt.plot(arc_xs*ro/ri+shift_x, arc_ys*ro/ri, color = 'black', lw = lw)
    plt.plot(-arc_xs-shift_x, -arc_ys, color = 'black', lw = lw, ls='--')
    plt.plot(-arc_xs*ro/ri-shift_x, -arc_ys*ro/ri, color = 'black', lw = lw)
    plt.plot([shift_x*0.9, shift_x*0.9], [ri,ro], color='black', lw=lw)
    plt.plot([-shift_x, -shift_x], [ri,ro], color='black', lw=lw)
    plt.plot([shift_x*0.9, shift_x*0.9], [-ri,-ro], color='black', lw=lw)
    plt.plot([-shift_x, -shift_x], [-ri,-ro], color='black', lw=lw)
    return()

def expand_pol(pol, r, rmax, lmax, mmax):
    """
    Expand poloidal coefficients (pol) in radius up to rmax.
    """
    sh = shtns.sht(int(lmax), int(mmax), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    l = sh.l
    r_expand = np.linspace(r[-1], rmax, 101)
    r_expand = r_expand[1:]
    l = np.reshape(l, (len(l),1))
    r_expand = np.reshape(r_expand, (1,len(r_expand)))
    pol_surf_Re = np.reshape(pol[0,:,-1], (len(pol[0,:,-1]),1))
    pol_surf_Im = np.reshape(pol[0,:,-1], (len(pol[0,:,-1]),1))
    factor_expand = (r[-1]/r_expand)**(l+1)
    pol_expand_Re = pol_surf_Re*factor_expand
    pol_expand_Im = pol_surf_Im*factor_expand
    pol_expand = np.zeros((2,pol_expand_Re.shape[0], pol_expand_Re.shape[1]))
    pol_expand[0] = pol_expand_Re
    pol_expand[1] = pol_expand_Im
    pol_expanded = np.concatenate((pol,pol_expand),axis=2)
    r_expand = np.concatenate((r,r_expand[0]))
    return(pol_expanded, r_expand)

def sh_to_spat_shtns(coeffs_lsd, lmax, mmax):
    coeffs_shtns = coeffs_lsd[0] + 1j*coeffs_lsd[1]
    sh = shtns.sht(int(lmax), int(mmax), 1, shtns.sht_schmidt | shtns.SHT_NO_CS_PHASE)
    nlat, nphi = sh.set_grid(int(lmax+1)*2, int(lmax*2+2)*2)
    corr = np.zeros((len(sh.l)))
    corr[sh.m>0] = np.sqrt(2)
    corr[sh.m==0] = 1
    field_spat = np.zeros((coeffs_lsd.shape[2],nlat,nphi))
    for k in range(len(field_spat)):
        field_spat[k] = sh.synth(coeffs_shtns[:,k]*corr)
    tta = np.arccos(sh.cos_theta)
    phi = np.arange(0, 2*np.pi, 2*np.pi/nphi)
    return(tta, phi, field_spat, sh.l, sh.m, coeffs_shtns)

def stream_from_Pol(r, tta, Pol):
    r = r[(len(r) - Pol.shape[0]):]
    r = r.reshape((len(r),1))
    tta_res = tta.reshape((1,len(tta)))
    Pol_intp = Pol
    Pol_intp = Pol_intp*r
    dPol_dtta = np.zeros(Pol_intp.shape)
    dPol_dtta[:,1:-1] = (Pol_intp[:,2:] - Pol_intp[:,:-2]) / (tta_res[:,2:] - tta_res[:,:-2])
    dPol_dtta[:,0] = (Pol_intp[:,1] - Pol_intp[:,0]) / (tta_res[:,1] - tta_res[:,0])
    dPol_dtta[:,-1] = (Pol_intp[:,-1] - Pol_intp[:,-2]) / (tta_res[:,-1] - tta_res[:,-2])
    Phi = np.zeros(Pol_intp.shape)
    Phi[1:] = -1/r[1:] * dPol_dtta[1:]
    Phi[0] = (Phi[1,0] + Phi[1,-1]) / 2
    return(Phi, tta_res[0])

def integrate_field(r, tta, phi, f, r_lim=[0,np.inf], tta_lim=[0,np.inf], phi_lim=[0,np.inf], s_lim=[0,np.inf], z_lim=[-np.inf,np.inf]):
    if f.shape[1] == len(phi):
        R, PHI, TTA = np.meshgrid(r, phi, tta, indexing='ij')
        axis_tta = 2
        axis_phi = 1
    elif f.shape[1] == len(tta):
        R, TTA, PHI = np.meshgrid(r, tta, phi, indexing='ij')    
        axis_tta = 1
        axis_phi = 2
    # DR = np.diff(R, axis=0)
    # DR = np.concatenate((DR, np.reshape(DR[-1],(1,DR.shape[1], DR.shape[2]))), axis=0)
    DR = (R[2:] - R[1:-1])/2 + (R[1:-1] - R[:-2])/2
    DR = np.concatenate((np.reshape((R[1]-R[0])/2, (1, DR.shape[1], DR.shape[2])), DR, np.reshape((R[-1]-R[-2])/2, (1, DR.shape[1], DR.shape[2]))), axis=0)    
    DTTA = np.diff(TTA, axis=axis_tta)
    if axis_tta == 2:
        DTTA = np.concatenate((DTTA, np.reshape(DTTA[:,:,-1],(DTTA.shape[0], DTTA.shape[1], 1))), axis=axis_tta)
    elif axis_tta == 1:
        DTTA = np.concatenate((DTTA, np.reshape(DTTA[:,-1],(DTTA.shape[0], 1, DTTA.shape[2]))), axis=axis_tta)
    DPHI = np.diff(PHI, axis=axis_phi)
    if axis_phi == 1:
        DPHI = np.concatenate((DPHI, np.reshape(DPHI[:,-1],(DPHI.shape[0], 1, DPHI.shape[2]))), axis=axis_phi)
    elif axis_phi == 2:
        DPHI = np.concatenate((DPHI, np.reshape(DPHI[:,:,-1],(DPHI.shape[0], DPHI.shape[1], 1))), axis=axis_phi)  
    DV = R**2*np.sin(TTA)*DR*DTTA*DPHI
    S = R*np.sin(TTA)
    Z = R*np.cos(TTA)

    filt = (R>r_lim[0])&(R<r_lim[1])&(TTA>tta_lim[0])&(TTA<tta_lim[1])&(PHI>phi_lim[0])&(PHI<phi_lim[1])&(S>s_lim[0])&(S<s_lim[1])&(Z>z_lim[0])&(Z<z_lim[1])

    #print(R.shape, TTA.shape, PHI.shape, filt.shape, f.shape)

    f_int = np.sum(f[filt]*DV[filt])/np.sum(DV[filt])
    return(f_int) 


def integrate_merid(r, tta, f, r_lim=[0,np.inf], tta_lim=[0,np.inf], s_lim=[0,np.inf], z_lim=[-np.inf,np.inf]):
    R, TTA = np.meshgrid(r, tta, indexing='ij')
    DR = np.diff(R, axis=0)
    DR = np.concatenate((DR, np.reshape(DR[-1],(1,DR.shape[1]))), axis=0)
    DTTA = np.diff(TTA, axis=1)
    DTTA = np.concatenate((DTTA, np.reshape(DTTA[:,-1],(DTTA.shape[0], 1))), axis=1)
    DV = R*DR*DTTA
    S = R*np.sin(TTA)
    Z = R*np.cos(TTA)

    filt = (R>r_lim[0])&(R<r_lim[1])&(TTA>tta_lim[0])&(TTA<tta_lim[1])&(S>s_lim[0])&(S<s_lim[1])&(Z>z_lim[0])&(Z<z_lim[1])
    f_int = np.sum(f[filt]*DV[filt])/np.sum(DV[filt])
    return(f_int)


def integrate_surf(tta, phi, f, tta_lim=[0,np.inf], phi_lim=[0,np.inf], s_lim=[0,np.inf], z_lim=[-np.inf,np.inf], r=20/13):
    TTA, PHI = np.meshgrid(tta, phi, indexing='ij')
    DTTA = np.diff(TTA, axis=0)
    DTTA = np.concatenate((DTTA, np.reshape(DTTA[-1],(1, DTTA.shape[1]))), axis=0)
    DPHI = np.diff(PHI, axis=1)
    DPHI = np.concatenate((DPHI, np.reshape(DPHI[:,-1],(DPHI.shape[0], 1))), axis=1)
    DS = np.sin(TTA)*DTTA*DPHI
    S = r*np.sin(TTA)
    Z = r*np.cos(TTA)

    filt = (TTA>tta_lim[0])&(TTA<tta_lim[1])&(PHI>phi_lim[0])&(PHI<phi_lim[1])&(S>s_lim[0])&(S<s_lim[1])&(Z>z_lim[0])&(Z<z_lim[1])

    #print(R.shape, TTA.shape, PHI.shape, filt.shape, f.shape)

    f_int = np.sum(f[filt]*DS[filt])/np.sum(DS[filt])
    return(f_int)
