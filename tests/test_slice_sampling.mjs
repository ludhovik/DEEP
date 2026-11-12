import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createSliceSampler, createPolarSliceSampler, regularPoleField, stencilValue, appendSliceStencil, cachedSliceValue } from '../src/slice-sampling.js';
import { setSliceColours } from '../src/slice-colours.js';

const r = [.2, .23, .55, 1], theta = [.1, .45, 1.1, 1.8, 2.8, 3.05], phi = [0, .6, 2, 3.5, 5.8];
const domain = {start: 0, end: 3, rMin: .2, rMax: 1};
const sample = createSliceSampler(r, theta, phi, domain);
const volume = formula => Float64Array.from(r.flatMap(x => theta.flatMap(t => phi.map(p => formula(x,t,p)))));
const near = (a, b, tol = 1e-10) => assert.ok(Math.abs(a-b) < tol, `${a} ≈ ${b}`);

test('radial velocity of a uniform Cartesian vector has a unique north/south pole limit', () => {
  const ph = Array.from({length:32},(_,i)=>2*Math.PI*i/32);
  const values=Float64Array.from(r.flatMap(rr=>theta.flatMap(t=>ph.map(p=>
    rr*(.7*Math.sin(t)*Math.cos(p)-.2*Math.sin(t)*Math.sin(p)+1.3*Math.cos(t))))));
  const native=createSliceSampler(r,theta,ph,domain);
  const corrected=createPolarSliceSampler(r,theta,ph,domain,i=>values[i],true);
  const read=(sampler,rr,t,p)=>stencilValue(sampler(rr,t,p),sampler.valueAt || (i=>values[i]));
  assert.ok(Math.abs(read(native,.55,0,0)-read(native,.55,0,Math.PI))>.05,'old clamping creates a radial seam');
  for(const rr of [.2,.4,1]) for(const p of [0,.37,2.1,5.6]) {
    near(read(corrected,rr,0,p),1.3*rr);
    near(read(corrected,rr,Math.PI,p),-1.3*rr);
    for(const t of [1e-9,Math.PI-1e-9]) near(read(corrected,rr,t,p),read(corrected,rr,t,p+Math.PI),1e-8);
  }
  for(const t of theta) for(const p of [.37,3.2]) near(read(corrected,.4,t,p),read(native,.4,t,p));
  for(const boundary of [theta[0],theta.at(-1)]) near(read(corrected,.4,boundary-1e-9,.37),read(corrected,.4,boundary+1e-9,.37),1e-8);
});

test('tangential basis sign changes are retained instead of averaged across the axis', () => {
  const ph=Array.from({length:16},(_,i)=>i*2*Math.PI/16);
  const up=Float64Array.from(r.flatMap(()=>theta.flatMap(()=>ph.map(p=>-.7*Math.sin(p)-.2*Math.cos(p)))));
  assert.equal(regularPoleField('ur'),true);assert.equal(regularPoleField('ur_phiavg'),true);
  for(const name of ['up','ut','Bp','Bt','grad_thetaT']) assert.equal(regularPoleField(name),false);
  const sampler=createPolarSliceSampler(r,theta,ph,domain,i=>up[i],regularPoleField('up'));
  for(const t of [0,Math.PI]) {
    near(stencilValue(sampler(.55,t,0),sampler.valueAt),-.2);
    near(stencilValue(sampler(.55,t,Math.PI),sampler.valueAt),.2);
  }
});

test('virtual polar stencils survive field/frame updates, explicit poles and field domains', () => {
  const ph=Array.from({length:8},(_,i)=>i*Math.PI/4);
  for(const th of [theta,[0,...theta,Math.PI]]) {
    const field=Float64Array.from(r.flatMap(rr=>th.flatMap(t=>ph.map(p=>rr+Math.cos(t)+Math.sin(t)*Math.cos(p)))));
    const sampler=createPolarSliceSampler(r,th,ph,{...domain,start:2,rMin:.55},i=>field[i],true);
    assert.equal(sampler(.3,0,.3).length,0);
    for(const t of [0,.05,Math.PI-.03,Math.PI]) {
      const entries=sampler(.7,t,.3),indices=[],weights=[];
      appendSliceStencil(indices,weights,entries);
      near(cachedSliceValue(indices,weights,0,sampler.valueAt),stencilValue(entries,sampler.valueAt));
      const next=createPolarSliceSampler(r,th,ph,domain,i=>2*field[i]+3,true);
      near(cachedSliceValue(indices,weights,0,next.valueAt),2*stencilValue(entries,sampler.valueAt)+3);
    }
  }
});

test('nonuniform spherical interpolation reproduces affine fields between grid points', () => {
  const field = volume((r,t,p) => 2*r - 3*t + p);
  for (const [r,t,p] of [[.21,.3,.4],[.3,1.3,1.5],[.8,2.9,4.5]]) {
    near(stencilValue(sample(r,t,p), i=>field[i]), 2*r - 3*t + p);
  }
});

test('offset equatorial slice is continuous across radial and latitude cell boundaries', () => {
  const field = volume((r,t) => 2*r + 3*t), z = .17;
  for (let s = .13; s < .98; s += .001) {
    const radius = Math.hypot(s,z), t = Math.acos(z/radius);
    near(stencilValue(sample(radius,t,.7), i=>field[i]), 2*radius + 3*t);
  }
  // Nearest-neighbour evaluation would jump here, by a whole theta cell.
  for (const t of theta.slice(1,-1)) {
    const rr = z/Math.cos(t);
    if (rr > .2 && rr < 1) {
      const a = stencilValue(sample(rr,t-1e-7,.7), i=>field[i]);
      const b = stencilValue(sample(rr,t+1e-7,.7), i=>field[i]);
      near(b-a, 6e-7);
    }
  }
});

test('longitude interpolation wraps continuously at 0/2pi and preserves exact grid nodes', () => {
  const field = volume((r,t,p)=>r + Math.cos(p));
  const a = stencilValue(sample(.55,1.1,-1e-8),i=>field[i]);
  const b = stencilValue(sample(.55,1.1,1e-8),i=>field[i]);
  near(a,b,2e-8);
  for(let ir=0;ir<r.length;ir++) for(let it=0;it<theta.length;it++) for(let ip=0;ip<phi.length;ip++) {
    near(stencilValue(sample(r[ir],theta[it],phi[ip]),i=>field[i]),field[(ir*theta.length+it)*phi.length+ip]);
  }
});

test('domain-limited interpolation never uses padded inner-core values or fills missing data', () => {
  const confined = createSliceSampler(r,theta,phi,{start:2,end:3,rMin:.55,rMax:1});
  assert.equal(confined(.3,1,0).length,0);
  assert.ok(confined(.7,1,0).every(([i])=>i>=2*theta.length*phi.length));
  assert.ok(confined(1+1e-15,1,0).length>0,'floating point boundary roundoff');
  assert.equal(confined(1.001,1,0).length,0);
  assert.ok(Number.isNaN(stencilValue([[0,.5],[1,.5]],i=>i?NaN:1)));
});

test('cached stencils reproduce construction and field/frame updates', () => {
  const entries=sample(.7,1.2,6.1), indices=[],weights=[];
  appendSliceStencil(indices,weights,entries);
  const field=volume((r,t,p)=>r+t+Math.sin(p));
  near(cachedSliceValue(indices,weights,0,i=>field[i]),stencilValue(entries,i=>field[i]));
  near(cachedSliceValue(indices,weights,0,i=>2*field[i]+7),2*stencilValue(entries,i=>field[i])+7);
});

test('slice material maps interpolated scalar values and retains unclipped values for manual ranges', () => {
  const mesh=new THREE.Mesh(new THREE.BufferGeometry(),new THREE.MeshBasicMaterial({vertexColors:true}));
  const stops=[[0,[0,0,255]],[.5,[255,255,255]],[1,[255,0,0]]];
  setSliceColours(mesh,[-2,0,2,NaN],-1,1,stops);
  assert.deepEqual([...mesh.geometry.getAttribute('sliceSample').array],[-.5,1,.5,1,1.5,1,0,0]);
  const shader={uniforms:{},vertexShader:THREE.ShaderLib.basic.vertexShader,fragmentShader:THREE.ShaderLib.basic.fragmentShader};
  mesh.material.onBeforeCompile(shader);
  assert.match(shader.fragmentShader,/diffuseColor.rgb = sliceColour\(vSliceSample.x\)/);
  assert.equal(mesh.material.vertexColors,false);
  const oldKey=mesh.material.customProgramCacheKey();
  setSliceColours(mesh,[0,1,2,3],0,3,[[0,[0,0,0]],[1,[255,255,255]]]);
  assert.notEqual(mesh.material.customProgramCacheKey(),oldKey);
  near(mesh.geometry.getAttribute('sliceSample').getX(1),1/3,1e-7);
});
