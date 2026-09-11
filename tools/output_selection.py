"""Strict volume selection and dependency-driven diagnostics for all converters."""
from __future__ import annotations
import numpy as np

VELOCITY = {'ur','ut','up','us','uz','Uabs','helicity',
            *(f'{v}_{mode}' for v in ('ur','ut','up') for mode in ('nom0','phiavg')),
            *(f'vort_{v}' for v in ('r','theta','phi','s','z','abs'))}
MAGNETIC = {'Br','Bt','Bp','Babs',*(f'{v}_{mode}' for v in ('Br','Bt','Bp') for mode in ('nom0','phiavg'))}
EMF = {'EMFr','EMFt','EMFp','EMFabs','EMFr_fluct','EMFt_fluct','EMFp_fluct'}
INDUCTION = {'Ir','It','Ip','Iz','Iabs'}
SCALARS = {'T','C','Phase','P','T_nom0','C_nom0','T_phiavg','C_phiavg'}
GRADIENTS = {f'grad_{axis}{scalar}{suffix}' for axis in ('r','theta','phi','s','z') for scalar in ('T','C') for suffix in ('','_nom0')}
FIELDS = VELOCITY | MAGNETIC | EMF | INDUCTION | SCALARS | GRADIENTS | {'N2','N2_nom0'}


def cylindrical_gradient(grad_r, grad_theta, theta):
    """Return cylindrical-radial (s) and axial (z) scalar-gradient components.

    The spherical and cylindrical unit vectors satisfy
    e_s = sin(theta)e_r + cos(theta)e_theta and
    e_z = cos(theta)e_r - sin(theta)e_theta.
    """
    th = np.asarray(theta, dtype=np.float64)[None, :, None]
    return (
        np.asarray(grad_r) * np.sin(th) + np.asarray(grad_theta) * np.cos(th),
        np.asarray(grad_r) * np.cos(th) - np.asarray(grad_theta) * np.sin(th),
    )


def add_output_argument(parser):
    parser.add_argument('--output', nargs='+', metavar='FIELD',
        help='Only calculate/export these volume fields, e.g. --output ur Br C vort_r. Dependencies stay internal; maps/lines are skipped. Omit for normal output. EMF/induction selections require --emf/--induction.')


class OutputSelection:
    def __init__(self, args):
        names = getattr(args,'output',None)
        self.names = None if names is None else tuple(dict.fromkeys(names))
        if self.names is None: return
        if not self.names: raise ValueError('--output needs at least one volume field.')
        unknown = set(self.names)-FIELDS
        if unknown: raise ValueError('Unknown --output volume field(s): '+', '.join(sorted(unknown))+'. Available names: '+', '.join(sorted(FIELDS)))
        if set(self.names)&EMF and not args.emf: raise ValueError('Selected EMF fields require --emf.')
        if set(self.names)&INDUCTION and not args.induction: raise ValueError('Selected induction fields require --induction.')
        if getattr(args,'inner_core_only',False): raise ValueError('--output cannot be combined with --inner-core-only; use normal --incremental conversion.')
        if getattr(args,'no_gradients',False) and set(self.names)&(GRADIENTS|{'N2','N2_nom0'}):
            raise ValueError('--output gradient/N2 fields conflict with --no-gradients.')
        if getattr(args,'no_m0_fields',False) and any(v.endswith(('_nom0','_phiavg')) for v in self.names):
            raise ValueError('--output mean/fluctuation fields conflict with --no-m0-fields.')

    def wants(self,name):return self.names is None or name in self.names
    def needs(self,name):
        if self.names is None:return True
        names=set(self.names)
        if name in ('ur','ut','up','utor'):return bool(names&(VELOCITY|EMF|INDUCTION))
        if name in ('Br','Bt','Bp','Btor'):return bool(names&(MAGNETIC|EMF|INDUCTION))
        if name=='T':
            return bool(names&{'T','T_nom0','T_phiavg','N2','N2_nom0'}) or any(v.startswith('grad_') and (v.endswith('T') or v.endswith('T_nom0')) for v in names)
        if name=='C':
            return bool(names&{'C','C_nom0','C_phiavg','N2','N2_nom0'}) or any(v.startswith('grad_') and (v.endswith('C') or v.endswith('C_nom0')) for v in names)
        return name in names


def selected_native_fields(selection,raw,radii,theta,phi,parameters,args,*,n2_factors=None,source_format='',operations):
    """Evaluate only requested nodes. Coupled native vector/curl operators are shared."""
    result={};memo={}
    def op(name,*values):return operations[name](*values)
    def base(name):
        if name not in raw:raise ValueError(f'--output needs {name}, but this input does not contain it.')
        return raw[name],radii[name]
    def vector(prefix):return [base(v)[0] for v in (('ur','ut','up') if prefix=='u' else ('Br','Bt','Bp'))]
    def shared(key,fn):
        if key not in memo:memo[key]=fn()
        return memo[key]
    th=np.asarray(theta)[None,:,None]
    def grad(scalar):
        a,r=base(scalar)
        def calculate():
            g=op('gradient',a,r,theta,phi)
            if source_format=='leeds' and r[0]==0:
                g=op('regularize_gradient',*g,np.isclose(r,0,rtol=0,atol=1e-12))
            return g
        return shared('grad:'+scalar,calculate)
    def emf(fluct=False):
        def calculate():
            u=vector('u');b=vector('B');ru=base('ur')[1];rb=base('Br')[1]
            b=[op('remap',v,rb,ru) for v in b]
            if fluct:u=[op('nom0',v) for v in u];b=[op('nom0',v) for v in b]
            return op('emf',*u,*b)
        return shared('emf_fluct' if fluct else 'emf',calculate)
    def scalar_of(name):
        if name.startswith('T') or name.startswith('grad_') and name.split('_nom0',1)[0].endswith('T'):return 'T'
        return 'C'
    for name in selection.names:
        if name in raw or name in ('ur','ut','up','Br','Bt','Bp','T','C','Phase','P'):a,r=base(name)
        elif name.endswith(('_nom0','_phiavg')) and name in (VELOCITY|MAGNETIC|SCALARS):
            base_name=name.rsplit('_',1)[0]
            a,r=base(base_name);a=op('mean' if name.endswith('_phiavg') else 'nom0',a)
        elif name in ('Uabs','Babs'):
            prefix='u' if name=='Uabs' else 'B';v=vector(prefix);r=base('ur' if prefix=='u' else 'Br')[1]
            a=np.sqrt(sum(c*c for c in v))
        elif name in ('us','uz'):
            ur,r=base('ur');ut,_=base('ut')
            a=ur*np.sin(th)+ut*np.cos(th) if name=='us' else ur*np.cos(th)-ut*np.sin(th)
        elif name=='helicity':
            r=base('ur')[1];a=op('helicity',*vector('u'),r,theta,phi)
        elif name.startswith('vort_'):
            r=base('ur')[1];wr,wt,wp=shared('vorticity',lambda:op('curl',*vector('u'),r,theta,phi))
            axis=name[5:]
            if axis in ('r','theta','phi'):a={'r':wr,'theta':wt,'phi':wp}[axis]
            elif axis=='s':a=wr*np.sin(th)+wt*np.cos(th)
            elif axis=='z':a=wr*np.cos(th)-wt*np.sin(th)
            else:a=np.sqrt(wr*wr+wt*wt+wp*wp)
        elif name in GRADIENTS:
            scalar=scalar_of(name);r=base(scalar)[1];axis=name[5:].split(scalar)[0]
            spherical=grad(scalar)
            if axis in ('s','z'):
                a=cylindrical_gradient(spherical[0],spherical[1],theta)[('s','z').index(axis)]
            else:
                a=spherical[('r','theta','phi').index(axis)]
            if name.endswith('_nom0'):a=op('nom0',a)
        elif name in EMF:
            values=emf(name.endswith('_fluct'));r=base('ur')[1]
            a=np.sqrt(sum(v*v for v in values)) if name=='EMFabs' else values[('r','t','p').index(name[3])]
        elif name in INDUCTION:
            r=base('ur')[1];ir,it,ip=shared('induction',lambda:op('induction',*emf(),r,theta,phi))
            if name in ('Ir','It','Ip'):a={'Ir':ir,'It':it,'Ip':ip}[name]
            elif name=='Iz':a=ir*np.cos(th)-it*np.sin(th)
            else:a=np.sqrt(ir*ir+it*it+ip*ip)
        elif name in ('N2','N2_nom0'):
            def calculate_n2():
                available=[s for s in ('T','C') if s in raw]
                if not available:raise ValueError('--output N2 needs a thermal or composition field.')
                r=base(available[0])[1];total=np.zeros_like(base(available[0])[0],dtype=np.float64)
                for scalar in available:
                    if n2_factors is not None:
                        if scalar not in n2_factors:raise ValueError(f'--output N2 has no valid {scalar} factor; check parameters and --n2-convention.')
                        factor=n2_factors[scalar]
                    else:
                        ek,ra,pr=(parameters[k] for k in ('Ek','RaT' if scalar=='T' else 'RaC','Pr' if scalar=='T' else 'Sc'))
                        if not all(np.isfinite(v) for v in (ek,ra,pr)) or pr<=0:raise ValueError('--output N2 requires finite parameters and positive Pr/Sc.')
                        factor=base(scalar)[1]*ek**2*ra/pr
                    term=grad(scalar)[0]*np.asarray(factor)[:,None,None]
                    total+=op('remap',term,base(scalar)[1],r)
                return total,r
            a,r=shared('N2',calculate_n2)
            if name=='N2_nom0':a=op('nom0',a)
        else:raise ValueError(f'Cannot calculate --output {name} from this input.')
        source='magnetic' if name in MAGNETIC else 'velocity' if name in VELOCITY|EMF|INDUCTION else 'scalar'
        result[name]=(np.asarray(a,dtype=np.float32),r,source)
    return result
