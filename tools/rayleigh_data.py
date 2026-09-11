"""Native Rayleigh stream checkpoints and Spherical_3D outputs (NumPy/SciPy).

Checkpoint harmonics use m-major packing, normalized Y_lm, and one real
contribution for each stored m>=0 (not the usual factor two for m>0).
Single-domain radial coefficients use c0/2 + sum(cn Tn), on rescaled roots.
"""
from pathlib import Path
import math
import re
import numpy as np
try:
    from conversion_cache import cached_calculation
    from spectral_truncation import harmonic_basis
except ImportError:
    from tools.conversion_cache import cached_calculation
    from tools.spectral_truncation import harmonic_basis

QUANTITIES = {'ur':1,'ut':2,'up':3,'Br':801,'Bt':802,'Bp':803,'C':501,'P':502}


def endian(path):
    with Path(path).open('rb') as stream:tag=stream.read(4)
    for order in ('<','>'):
        if len(tag)==4 and np.frombuffer(tag,dtype=order+'i4')[0]==314:return order
    raise ValueError(f'{path}: expected Rayleigh endian tag 314; extract archives first.')


def read_values(f,dtype,count):
    values=np.fromfile(f,dtype=dtype,count=count)
    if len(values)!=count:raise ValueError(f'Truncated Rayleigh file: {f.name}')
    return values


def main_parameters(path):
    if not path or not Path(path).is_file():return {}
    text='\n'.join(line.split('!')[0] for line in Path(path).read_text().splitlines())
    result={}
    for key,value in re.findall(r'\b([A-Za-z_]\w*)\s*=\s*([^,\n/]+)',text):
        value=value.strip().lower()
        if value in ('.true.','t','.false.','f'):result[key.lower()]=value in ('.true.','t')
        else:
            try:
                parsed=float(value.replace('d','e'))
                if math.isfinite(parsed):result[key.lower()]=parsed
            except ValueError:pass
    return result


def validate_axis(values,name):
    if len(values)<3 or not np.isfinite(values).all() or not (np.all(np.diff(values)>0) or np.all(np.diff(values)<0)):
        raise ValueError(f'Invalid/nonmonotone Rayleigh {name} grid.')


def read_grid(path,checkpoint=False):
    order=endian(path)
    with Path(path).open('rb') as f:
        read_values(f,order+'i4',1)
        if checkpoint:
            version,nr,kind,lmax=read_values(f,order+'i4',4).tolist()
            if version!=2 or kind!=2:raise ValueError('Checkpoint reader supports stream version 2, Chebyshev grid_type=2. Export Spherical_3D for other layouts.')
            nt=max(4,math.ceil(1.5*(lmax+1)));np_=2*nt
            dt=read_values(f,order+'f8',2)
        else:
            nr,nt,np_=read_values(f,order+'i4',3).tolist();lmax=(2*nt)//3-1
        if min(nr,nt,np_)<3 or max(nr,nt,np_)>100000:raise ValueError('Invalid Rayleigh grid dimensions.')
        r=read_values(f,order+'f8',nr)
        if checkpoint:
            time=float(read_values(f,order+'f8',1)[0]);step=int(read_values(f,order+'i4',1)[0])
            theta=np.arccos(np.polynomial.legendre.leggauss(nt)[0][::-1])
        else:
            theta=read_values(f,order+'f8',nt);time=math.nan;step=int(Path(path).name.split('_')[0])
            if np_!=2*nt:raise ValueError('Spherical_3D expects nphi=2*ntheta.')
        if f.read(1):raise ValueError(f'Unexpected trailing grid data in {path}.')
    validate_axis(r,'radius');validate_axis(theta,'colatitude')
    if min(r)<0 or min(theta)<=0 or max(theta)>=math.pi:raise ValueError('Rayleigh radius/colatitude is out of range.')
    return dict(r=r,theta=theta,phi=np.arange(np_)*2*math.pi/np_,lmax=lmax,time=time,step=step,endian=order)


def read_reference(path,radius):
    order=endian(path)
    with Path(path).open('rb') as f:
        tag,version=read_values(f,order+'i4',2)
        if version not in (1,2):raise ValueError('Unsupported equation_coefficients version.')
        nc,nf=read_values(f,order+'i4',2) if version==2 else (10,14)
        if not (10<=nc<=100 and 14<=nf<=100):raise ValueError('Invalid equation_coefficients dimensions.')
        read_values(f,order+'i4',int(nc+nf))
        constants=read_values(f,order+'f8',int(nc))
        nr=int(read_values(f,order+'i4',1)[0]);r=read_values(f,order+'f8',nr)
        functions=read_values(f,order+'f8',int(nr*nf)).reshape(nf,nr)
        if f.read(1):raise ValueError('Unexpected equation_coefficients layout; no density guess is made.')
    if r.shape!=radius.shape or not np.allclose(r,radius,rtol=1e-12,atol=1e-12):raise ValueError('Reference density grid differs from checkpoint grid.')
    rho=functions[0]
    if not np.isfinite(rho).all() or np.any(rho<=0):raise ValueError('Reference density must be finite and positive.')
    return rho


@cached_calculation
def read_volume(path,shape,order):
    if Path(path).stat().st_size!=math.prod(shape)*8:raise ValueError(f'{path}: incorrect Spherical_3D file size.')
    # Native Fortran shape (phi,theta,r) equals C-order (r,theta,phi).
    a=np.fromfile(path,dtype=order+'f8').reshape(shape)
    if not np.isfinite(a).all():raise ValueError(f'{path}: nonfinite samples.')
    return a


@cached_calculation
def read_coefficients(path,nr,lmax,order):
    nm=(lmax+1)*(lmax+2)//2
    if Path(path).stat().st_size!=16*nr*nm:raise ValueError(f'{path}: incorrect checkpoint size (expected radial spectral coefficients).')
    data=np.fromfile(path,dtype=order+'f8').reshape(2,nr,nm)
    if not np.isfinite(data).all():raise ValueError(f'{path}: nonfinite coefficients.')
    return data[0]+1j*data[1]


def radial_basis(radius):
    """Validate the native single-domain root grid before differentiating."""
    n=len(radius);x=np.cos(np.pi*(np.arange(n)+.5)/n)
    a=(radius[0]-radius[-1])/(x[0]-x[-1]);b=radius[0]-a*x[0]
    if not np.allclose(radius,a*x+b,rtol=1e-11,atol=max(abs(a),1)*1e-12):
        raise ValueError('Not a single-domain Rayleigh Chebyshev grid. Export Spherical_3D for multidomain/other grids.')
    coefficients=np.eye(n);coefficients[0,0]=.5
    basis=np.polynomial.chebyshev.chebval(x,coefficients).T
    derivative=np.polynomial.chebyshev.chebval(x,np.polynomial.chebyshev.chebder(coefficients)).T/a
    second=np.polynomial.chebyshev.chebval(x,np.polynomial.chebyshev.chebder(coefficients,m=2)).T/a**2
    return basis,derivative,second


@cached_calculation
def synthesize_checkpoint(coefficients,radius,lmax,cutoff,theta,phi,tor=None,density=None):
    basis,derivative,second=radial_basis(radius)
    p=basis@coefficients
    if tor is not None:
        dp=derivative@coefficients;t=basis@tor
    output=np.zeros((3 if tor is not None else 1,len(radius),len(theta),len(phi)))
    zero=np.flatnonzero(radius==0);safe=np.where(radius==0,1.,radius)[:,None]
    dd=second@coefficients if len(zero) and tor is not None else None
    offset=0
    for m in range(lmax+1):
        count=lmax-m+1
        if m<=cutoff:
            sl=slice(offset,offset+cutoff-m+1);ell=np.arange(m,cutoff+1)
            y,dy,my=harmonic_basis(cutoff,m,theta)
            if tor is None:values=[p[:,sl]@y]
            else:
                q=p[:,sl]*ell*(ell+1)/safe**2;s=dp[:,sl]/safe;v=t[:,sl]/safe
                if len(zero):
                    scale=max(1.,float(np.max(np.abs(p[:,sl]))))
                    if np.max(np.abs(p[zero,sl]))>1e-9*scale or np.max(np.abs(dp[zero,sl]))>1e-8*scale or np.max(np.abs(t[zero,sl]))>1e-9*max(1.,float(np.max(np.abs(t[:,sl])))):
                        raise ValueError('Checkpoint potentials are not regular at r=0; centre limits cannot be inferred.')
                    q[zero]=np.where(ell==1,dd[zero,sl],0)
                    s[zero]=np.where(ell==1,dd[zero,sl],0)
                    v[zero]=0 # regular toroidal vectors vanish at the centre
                values=[q@y,s@dy+1j*v@my,1j*s@my-v@dy]
            phase=np.exp(1j*m*phi)
            for k,value in enumerate(values):output[k]+=(value[:,:,None]*phase).real
        offset+=count
    if density is not None:output/=density[None,:,None,None]
    if not np.isfinite(output).all():raise ValueError('Nonfinite reconstructed Rayleigh field.')
    return output if tor is not None else output[0]
