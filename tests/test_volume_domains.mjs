import test from "node:test";
import assert from "node:assert/strict";
import { buildSphericalIsosurface } from "../src/isosurface-geometry.js";
import { fieldRadialDomain } from "../src/volume-domain.js";
import { updateIsosurfaceLegend, isosurfaceLegendEntries } from "../src/isosurface-legend.js";
import * as THREE from "three";

test("fluid-only isosurfaces never interpolate through zero-padded solid-core rows", () => {
  const metadata={nr:5,ntheta:4,nphi:8,r_inner:0,r_outer:1,r_icb:.5};
  const coords={r:[0,.25,.5,.75,1],theta:[.1,1,2,3],phi:Array.from({length:8},(_,i)=>2*Math.PI*i/8)};
  const field=new Float32Array(5*4*8);field.fill(1,2*4*8);
  const payload={metadata,coords,field,isoValue:.5,requestedResolution:36};
  const artificial=buildSphericalIsosurface(payload);
  assert.ok(artificial.attributes.position.count>0,"unmasked padding creates a false boundary isosurface");
  const domain=fieldRadialDomain(metadata,coords,{r_min:.5,r_max:1});
  const fluid=buildSphericalIsosurface({...payload,domain});
  assert.equal(fluid.attributes.position?.count || 0,0);
  artificial.dispose();fluid.dispose();
});

test("core-only worker geometry stays inside ICB and domain without cells returns empty", () => {
  const metadata={nr:5,ntheta:4,nphi:8,r_inner:0,r_outer:1,r_icb:.5};
  const coords={r:[0,.25,.5,.75,1],theta:[.1,1,2,3],phi:Array.from({length:8},(_,i)=>2*Math.PI*i/8)};
  const field=Float32Array.from({length:5*4*8},(_,i)=>coords.r[Math.floor(i/32)]);
  const domain=fieldRadialDomain(metadata,coords,{magnetic:true},"inner-core");
  const mesh=buildSphericalIsosurface({metadata,coords,field,isoValue:.3,requestedResolution:36,domain});
  const p=mesh.attributes.position.array;
  assert.ok(p.length>0);
  for(let i=0;i<p.length;i+=3) assert.ok(Math.hypot(p[i],p[i+1],p[i+2])<=.500001);
  const empty=buildSphericalIsosurface({metadata,coords,field,isoValue:.3,requestedResolution:36,domain:{start:3,end:2,empty:true}});
  assert.equal(empty.attributes.position,undefined);
  mesh.dispose();empty.dispose();
});

test("legend labels use text nodes and omit hidden, empty and transparent surfaces", () => {
  const mesh=new THREE.Mesh(new THREE.SphereGeometry(.5,8,8),new THREE.MeshBasicMaterial({color:"#aa1234"}));
  mesh.userData.isoLegend={field:"<img onerror=bad>",value:-.004};
  const document={createElement(){return {ownerDocument:document,style:{},children:[],append(...nodes){this.children.push(...nodes)},replaceChildren(){this.children=[]}}}};
  const element=document.createElement();
  updateIsosurfaceLegend(element,isosurfaceLegendEntries([mesh]));
  assert.equal(element.style.display,"block");
  assert.equal(element.children[1].children[1].textContent,"<img onerror=bad> = -0.004");
  assert.equal(element.children[1].children[0].style.backgroundColor,"#aa1234");
  mesh.material.opacity=0;
  assert.equal(isosurfaceLegendEntries([mesh]).length,0);
  mesh.material.opacity=1;mesh.visible=false;
  updateIsosurfaceLegend(element,isosurfaceLegendEntries([mesh]));
  assert.equal(element.style.display,"none");assert.equal(element.children.length,0);
  mesh.visible=true;mesh.geometry.dispose();mesh.geometry=new THREE.BufferGeometry();
  assert.equal(isosurfaceLegendEntries([mesh]).length,0);
  mesh.geometry.dispose();mesh.material.dispose();
});
