import test from 'node:test';
import assert from 'node:assert/strict';
import { parseViewerCommand, createCommandHistory, COMMAND_EXAMPLES } from '../src/viewer-commands.js';
const volume = ['ur', 'Br', 'T', 'C', 'Tanomaly'].map(name => ({name, value:name, dataset:1}));
volume.push({ name:'T', value:'D2:T', dataset:2 });
const fields = Object.fromEntries(['meridian', 'meridian2', 'equator', 'equator2', 'radial', 'icb', 'cmb'].map(s => [s,volume]));
const options = { fields, params: {meridianField:'T', cmbField:'Br'}, cameraAzimuth:-45 };
const parse = text => parseViewerCommand(text,options);

test('user sentence applies all requested settings with linked meridional halves', () => {
  const c = parse('show me meriodional crosssection of ur and equatorial of Br and Br at cmb with a sphere open for 1/8th north hemisphere?');
  assert.equal(c.patch.meridianField,'ur'); assert.equal(c.patch.meridianLeftField,'ur');
  assert.equal(c.patch.meridianIndependentSides,false);
  assert.equal(c.patch.equatorField,'Br'); assert.equal(c.patch.cmbField,'Br');
  assert.equal(c.patch.showCMB,true); assert.equal(c.patch.showEquator,true); assert.equal(c.patch.showMeridian,true);
  assert.equal(c.patch.quarterN4,false); assert.equal(c.patch.quarterS4,true);
});
test('every displayed example parses', () => { for (const s of COMMAND_EXAMPLES) assert.equal(parse(s).action,'apply',s); });
test('explicit and wrapped octants follow the geometry sector numbering', () => {
  for (const start of [0,30,90,180,270,300]) {
    const p = parse(`open southern octant between ${start} and ${start+90} degrees`).patch;
    const bounds = [start,(start+90)%360,(start+180)%360,(start+270)%360].sort((a,b)=>a-b);
    assert.equal(p[`quarterS${bounds.indexOf(start)+1}`],false);
    assert.equal(Object.entries(p).filter(([k,v])=>k.startsWith('quarter')&&!v).length,1);
  }
});
test('unrecognised suffixes and unavailable fields cannot partly apply', () => {
  for (const s of ['show meridional ur and paint it red', 'show equatorial nonexistent',
    'show cmb Br tomorrow', 'open north octant and close sphere', 'close sphere and open north octant', 'hide meridional ur', 'open north octant between 0 and 180',
    'show meridional Br from dataset 2', 'open north octant and hide meridional and hide meridional 2']) {
    assert.throws(()=>parse(s),undefined,s);
  }
});
test('surface-only field is accepted only on a boundary', () => {
  const o = {...options,fields:{...fields,cmb:[{name:'flux',value:'flux',dataset:1}]}};
  assert.equal(parseViewerCommand('show cmb flux',o).patch.cmbField,'flux');
  assert.throws(()=>parseViewerCommand('show equatorial flux',o));
});
test('dataset-specific selection and exact diagnostic names', () => {
  assert.equal(parse('show meridional 2 temperature from dataset 2').patch.meridian2Field,'D2:T');
  assert.equal(parse('change the meridional field to Tanomaly').patch.meridianField,'Tanomaly');
  assert.equal(parse('show meridional radial velocity').patch.meridianField,'ur');
});
test('radial depth, visibility, minmax and closing the opening', () => {
  const p = parse('show Br at radius 0.7 and hide field lines and show time').patch;
  assert.equal(p.radialField,'Br'); assert.equal(p.radialSurfaceRadiusRo,.7);
  assert.equal(p.showFieldLines,false); assert.equal(p.showSimulationTime,true);
  assert.throws(()=>parse('show Br at radius 1.5'));
  assert.equal(parse('set all colour scales to min-max').patch.meridianLeftScale,'minmax');
  assert.equal(parse('close sphere').patch.cmbClipMode,'none');
});
test('help/undo do not require fields',()=>{
  assert.equal(parseViewerCommand('help').action,'help');
  assert.equal(parseViewerCommand('undo').action,'undo');
  assert.throws(()=>parseViewerCommand('show equatorial Br'));
});
function harness() {
  let state={params:{equatorField:'T',showEquator:true}}, id={};
  let fail=false;
  const h=createCommandHistory({capture:()=>structuredClone(state),identity:()=>id,ready:()=>{},
    apply:async s=>{state=structuredClone(s);if(fail){fail=false;throw new Error('Missing volume');}}});
  return {h,get state(){return state;},fail:()=>fail=true,change:()=>id={}};
}
test('undo restores previous view and is invalidated by changing dataset',async()=>{
  const a=harness();
  await a.h.run(parse('show equatorial Br')); assert.equal(a.state.params.equatorField,'Br');
  await a.h.run({action:'undo'}); assert.equal(a.state.params.equatorField,'T');
  await assert.rejects(a.h.run({action:'undo'}),/Nothing to undo/);
  await a.h.run(parse('show equatorial Br')); a.change();
  await assert.rejects(a.h.run({action:'undo'}),/Nothing to undo/);
});
test('failed loading restores parameters and does not create undo history',async()=>{
  const a=harness(); a.fail();
  await assert.rejects(a.h.run(parse('show equatorial Br')),/Missing volume/);
  assert.equal(a.state.params.equatorField,'T');
  await assert.rejects(a.h.run({action:'undo'}),/Nothing to undo/);
});
test('overlapping asynchronous commands are rejected',async()=>{
  let release;const gate=new Promise(r=>release=r);
  const h=createCommandHistory({capture:()=>({params:{}}),identity:()=>1,ready:()=>{},apply:()=>gate});
  const pending=h.run(parse('show equatorial Br'));
  await assert.rejects(h.run(parse('show meridional ur')),/already running/);
  release();await pending;
});
