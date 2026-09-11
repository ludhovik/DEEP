"""Native transforms for explicit output selection; full exports keep their original path."""
from pathlib import Path
import numpy as np
try:
    from output_selection import OutputSelection
    from conversion_cache import cached_native, calculation_identity
except ImportError:
    from tools.output_selection import OutputSelection
    from tools.conversion_cache import cached_native, calculation_identity


def selected_leeds(c):
    try:
        import convert_leeds_to_viewer as leeds
        from convert_magic_to_viewer import convert_adapted_snapshot
        from inner_core import extend_leeds_inner_core
    except ImportError:
        from tools import convert_leeds_to_viewer as leeds
        from tools.convert_magic_to_viewer import convert_adapted_snapshot
        from tools.inner_core import extend_leeds_inner_core
    args=c['args'];selection=OutputSelection(args);r=c['r'];lmax=c['lmax_transform'];mmax=c['mmax_transform']
    regular=c['transform_fullsphere'];representations=c['radial_representations'];geometry=dict(c['geometry'])
    start=c['fluid_inner_index'];validate_ic=regular and c['has_inner_core'] and start>0
    raw={};theta=phi=None
    for pol,tor,names in [('uP','uT',('ur','ut','up')),('BP','BT',('Br','Bt','Bp'))]:
        if not selection.needs(names[0]) and not validate_ic:continue
        a,b=c[pol],c[tor]
        if a is None and b is None:continue
        if a is None:a=np.zeros_like(b)
        if b is None:b=np.zeros_like(a)
        print(f'Transforming required {names[0]} vector family...',flush=True)
        if regular:
            pa,po,_=leeds.fullsphere_storage_info(representations[pol],pol)
            ta,to,_=leeds.fullsphere_storage_info(representations[tor],tor)
            values= c['PolTor_to_spat_fullsphere'](a,b,r,lmax,mmax,pol_power_offset=po,tor_power_offset=to,
                pol_regular_coefficients=pa,tor_regular_coefficients=ta,enforce_center=False)
        else:values=c['PolTor_to_spat'](a,b,r,lmax,mmax,alpha_map=args.alpha_map)
        theta,phi=values[-2:];arrays=[leeds.as_r_theta_phi(v,len(r),len(theta),len(phi)) for v in values[:3]]
        if regular:
            *arrays,_=leeds.enforce_fullsphere_cartesian_center_limit(*arrays,theta,phi,c['center_mask'],pol)
        raw.update(zip(names,arrays))
    # The inferred leading solid region needs a velocity check even for a scalar-only export.
    if validate_ic:
        speed=np.sqrt(sum(raw[k]**2 for k in ('ur','ut','up')))
        threshold=max(args.flow_zero_abs_tol,args.flow_zero_rel_tol*float(np.max(speed)))
        stop=max(0,start-args.inner_core_validation_buffer_points)
        if np.max(speed[:stop or start])>threshold:
            if args.geometry!='auto':raise ValueError('The inferred inner-core interval contains non-zero physical velocity.')
            start=0;geometry.update(has_inner_core=False,has_conducting_inner_core=False,full_sphere=True,
                physical_geometry='full_fluid_sphere',r_icb=float(r[0]))
        elif geometry['has_conducting_inner_core'] and not any(np.max(np.abs(raw[k][:start]))>args.magnetic_tol for k in ('Br','Bt','Bp') if k in raw):
            if args.geometry=='conducting-inner-core':raise ValueError('No resolved inner-core magnetic field.')
            geometry.update(has_conducting_inner_core=False,physical_geometry='spherical_shell')
    for name in ('C','Comp'):
        if not selection.needs(name):continue
        if c[name] is None:continue
        print(f'Transforming required {name}...',flush=True)
        if regular:
            stored,offset,_=leeds.fullsphere_storage_info(representations[name],name)
            values=c['SH_to_spat_fullsphere'](c[name],r,lmax,mmax,power_offset=offset,regular_coefficients=stored)
        else:values=c['SH_to_spat'](c[name],lmax,mmax)
        theta,phi=values[-2:];a=leeds.as_r_theta_phi(values[0],len(r),len(theta),len(phi))
        raw[name]=leeds.regularize_scalar_center(a,c['center_mask'],name) if regular else a
    if theta is None:raise ValueError('None of the selected output dependencies are available in this Leeds state.')
    raw={k:v for k,v in raw.items() if selection.needs(k)}
    fluid=r[start:];master=r.copy();radii={}
    for key in list(raw):
        if key in ('Br','Bt','Bp'):radii[key]=r
        else:raw[key]=raw[key][start:];radii[key]=fluid
    inner=c['inner_core_state']
    if inner is not None and any(np.any(inner[k]) for k in ('icBP','icBT')):
        geometry['has_conducting_inner_core']=True
    ricb=float(geometry['r_icb']);extends=selection.needs('Br') and master[0]<ricb
    info=dict(c['spectral_meta']);info.setdefault('original_grid',[len(theta),len(phi)]);info.setdefault('output_grid',[len(theta),len(phi)])
    params={'_resolved_parameters':c['params_resolved'],'_parameter_sources':dict(args._parameter_sources),
            'l_max':lmax,'time':c['time'],'radratio':ricb/r[-1]}
    meta=dict(source_code='Leeds',source_state=str(c['path']),state_number=c['state_number'],
              description='Selected physical-space quantities from a Leeds spectral state.',
              state_radial_representations=representations,
              spectral={'lmax':lmax,'mmax':mmax,'minc':1,'nlat':len(theta),'nphi':len(phi),'library':'Leeds modules.py / SHTns'},
              full_sphere_transform={'enabled':regular,'method':'modules_v2_regular_qst_in_x' if regular else 'shell_PolTor_to_spat'},
              geometry_detection={k:(v.item() if isinstance(v,np.generic) else v)
                                  for k,v in geometry.items() if not isinstance(v,np.ndarray)},parameters={k:leeds.json_number(v) for k,v in c['params_resolved'].items()})
    adapted=dict(fields=raw,field_radii=radii,r_shell=fluid,r_master=master,r_fluid_inner=ricb,theta=theta,phi=phi,
        minc=1,has_conducting_inner_core=geometry['has_conducting_inner_core'],magnetic_extends_inner_core=extends,
        spectral_truncation=info,metadata=meta,gradient_operator=leeds.gradient_scalar_3d,
        induction_operator=c['curl_spat'])
    result=convert_adapted_snapshot(c['path'],Path(args.out),args,adapted,params,source_label='Leeds',source_format='leeds')
    if inner is not None and any(name in result['fields'] for name in ('Br','Bt','Bp','Babs','Br_phiavg','Bt_phiavg','Bp_phiavg','Br_nom0','Bt_nom0','Bp_nom0')):
        # Preserve the full converter's independent IC sampling and shared-ICB convention.
        extend_leeds_inner_core(Path(args.out),c['path'],c['user_modules'],inner=inner,
                               required=args.geometry=='conducting-inner-core')
    return result


def selected_xshells(c):
    try:
        from convert_magic_to_viewer import convert_adapted_snapshot
    except ImportError:
        from tools.convert_magic_to_viewer import convert_adapted_snapshot
    args=c['args'];selection=OutputSelection(args);raw={};radii={}
    mapping={'velocity':('ur','ut','up'),'magnetic':('Br','Bt','Bp'),'temperature':('C',),'composition':('Comp',)}
    for source,names in mapping.items():
        if source not in c['loaded'] or not selection.needs(names[0]):continue
        field=c['loaded'][source];rr=c['radial_grids'][source]
        print(f'Synthesizing required XSHELLS {source}...',flush=True)
        with np.errstate(divide='ignore',invalid='ignore'):
            a=np.ascontiguousarray(cached_native('xshells-'+source+'-synthesis',field.spat_full,
                {'path':c['paths'][source],'transform':c['transform_signature']},calculation_identity(type(field).spat_full)),dtype=np.float64)
        a=c['sanitise'](a,rr,source)
        values=[a[:,i] for i in range(3)] if len(names)==3 else [a]
        for key,value in zip(names,values):raw[key]=value;radii[key]=rr
    magnetic=raw.get('Br');rb=radii.get('Br',c['r_shell']);ricb=c['r_icb']
    extends=magnetic is not None and rb[0]<ricb
    cond=extends and any(np.any(raw[k][rb<ricb]) for k in ('Br','Bt','Bp'))
    info=dict(c['spectral_truncation']);reference=c['angular_reference']
    params={'_resolved_parameters':c['resolved_parameters'],'_parameter_sources':dict(args._parameter_sources),
            'l_max':reference.lmax,'time':c['time'],'radratio':ricb/c['r_cmb']}
    adapted=dict(fields=raw,field_radii=radii,r_shell=c['r_shell'],r_master=c['r_master'],r_fluid_inner=ricb,
        theta=c['theta'],phi=c['phi'],minc=reference.mres,has_conducting_inner_core=cond,
        magnetic_extends_inner_core=extends,spectral_truncation=info,induction_operator=c['induction_operator'],
        metadata={'source_fields':{k:str(v) for k,v in c['paths'].items() if v is not None},'source_code':'XSHELLS',
                  'spectral':{'lmax':reference.lmax,'mmax':reference.mmax,'minc':reference.mres,'nlat':len(c['theta']),'nphi':len(c['phi']),'library':'pyxshells / SHTns'},
                  'geometry_detection':{'method':'native_xshells_radial_domains','requested_geometry':args.geometry},
                  'description':'Selected physical-space quantities from XSHELLS native fields.'})
    if args.geometry=='conducting-inner-core' and not selection.needs('Br'):
        # Only geometric coverage is relevant when magnetic outputs were not selected.
        adapted['has_conducting_inner_core']=c['magnetic_domain_extends_inside_icb']
    return convert_adapted_snapshot(next(v for v in c['paths'].values() if v is not None),Path(args.out),args,adapted,params,
        source_label='XSHELLS',source_format='xshells')
