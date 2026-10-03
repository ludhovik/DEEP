import test from 'node:test';
import assert from 'node:assert/strict';
import { commandSuggestions, commandCompletionStart } from '../src/command-suggestions.js';
import { parseViewerCommand, createCommandHistory, COMMAND_EXAMPLES } from '../src/viewer-commands.js';
const volume = ['ur', 'Br', 'T', 'C', 'Tanomaly'].map(name => ({name, value:name, dataset:1}));
volume.push({ name:'T', value:'D2:T', dataset:2 });
const fields = Object.fromEntries(['meridian', 'meridian2', 'equator', 'equator2', 'radial', 'icb', 'cmb', 'iso', 'mollweide', 'earth'].map(s => [s,volume]));
const options = { fields, params: {meridianField:'T', cmbField:'Br'}, cameraAzimuth:-45, colormaps:['viridis','blue-white-red'], settings:[{key:'cameraAzimuthDeg',label:'camera azimuth',type:'number',min:-180,max:180}] };
const parse = text => parseViewerCommand(text,options);

test('user sentence applies all requested settings with linked meridional halves', () => {
  const c = parse('show me meriodional crosssection of ur and equatorial of Br and Br at cmb with a sphere open for 1/8th north hemisphere?');
  assert.equal(c.patch.meridianField,'ur'); assert.equal(c.patch.meridianLeftField,'ur');
  assert.equal(c.patch.meridianIndependentSides,false);
  assert.equal(c.patch.equatorField,'Br'); assert.equal(c.patch.cmbField,'Br');
  assert.equal(c.patch.showCMB,true); assert.equal(c.patch.showEquator,true); assert.equal(c.patch.showMeridian,true);
  assert.equal(c.patch.quarterN4,false); assert.equal(c.patch.quarterS4,true);
});
test('every displayed example parses', () => { for (const s of COMMAND_EXAMPLES) assert.equal(parse(s).action,s==='Reset view'?'reset':'apply',s); });
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


test('isosurface commands select exact signed levels, zero and scientific notation',()=>{
  for (const [input,value] of [['-100',-100],['+100',100],['0',0],['-1e2',-100],['−.5',-.5]]) {
    const p=parse(`show isosurface of ur at ${input}`).patch;
    assert.equal(p.isoField,'ur'); assert.equal(p.showIsosurfaces,true);
    assert.equal(p.showIsoNegative,value<0); assert.equal(p.showIsoPositive,value>=0);
    assert.equal(p[value<0?'isoNegativeValue':'isoPositiveValue'],value);
  }
});
test('isosurfaces use volume fields, aliases and dataset selection',()=>{
  const p=parse('show iso-surface of temperature at .4 from dataset 2').patch;
  assert.equal(p.isoField,'D2:T'); assert.equal(p.isoPositiveValue,.4);
  assert.equal(parse('hide isosurfaces').patch.showIsosurfaces,false);
  assert.throws(()=>parse('show isosurface of missing at -100'),/unavailable/);
  assert.throws(()=>parseViewerCommand('show isosurface of flux at 2',{fields:{cmb:[{name:'flux',value:'flux',dataset:1}]}}),/unavailable/);
});
test('paired levels share one field and ambiguous requests reject without partial actions',()=>{
  const p=parse('show isosurface ur at -100 and show isosurface ur at 100').patch;
  assert.equal(p.showIsoNegative,true);assert.equal(p.showIsoPositive,true);
  assert.equal(p.isoNegativeValue,-100);assert.equal(p.isoPositiveValue,100);
  for (const s of ['show isosurface ur at -1 and show isosurface T at 1',
    'show isosurface ur at 1 and show isosurface ur at 2',
    'show isosurface ur at NaN','show isosurface ur at Infinity',
    'show isosurface ur at 1e999','show isosurface ur at -100 nonsense',
    'hide isosurface ur at -100']) assert.throws(()=>parse(s),undefined,s);
});


test('manual range in the user sentence remains one instruction',()=>{
  const p=parse('Show Br at radius 0.7 with -1 and +1').patch;
  assert.equal(p.radialField,'Br');assert.equal(p.radialSurfaceRadiusRo,.7);
  assert.equal(p.radialScale,'manual');assert.equal(p.radialMin,-1);assert.equal(p.radialMax,1);
  const q=parse('Show Br at radius 0.7 with -1 and +1 using viridis and hide CMB').patch;
  assert.equal(q.radialColormap,'viridis');assert.equal(q.showCMB,false);
  assert.throws(()=>parse('Show Br at radius 0.7 with 1 and -1'),/minimum/);
  assert.throws(()=>parse('Show Br at radius 0.7 using nonexistent'),/colour map/);
});
test('per-display range, palette, scale and Mollweide fields',()=>{
  assert.equal(parse('set radial colourbar to viridis').patch.radialColormap,'viridis');
  assert.equal(parse('set equatorial range to -1e2 and +1e2').patch.equatorMax,100);
  assert.equal(parse('set meridional colour scale to symmetric').patch.meridianScale,'symmetric');
  assert.equal(parse('show Mollweide Br using viridis').patch.mollweideField,'Br');
  assert.throws(()=>parse('set field lines colour scale to symmetric'));
});
const settings=[
  {key:'cameraAzimuthDeg',label:'Point of view / Azimuth phi',aliases:['camera azimuth'],type:'number',min:-180,max:180},
  {key:'showAxes',label:'Other / Axes',type:'boolean'},
  {key:'isoNegativeColor',label:'Isosurfaces / Negative color',type:'string',color:true},
  {key:'earthTextureBody',label:'Planet image',type:'string',options:[{value:'earth',label:'Earth'},{value:'jupiter',label:'Jupiter'}]},
  {key:'title',label:'Title / Text',type:'string'},
  {key:'phiAvgCount',label:'Phi average count',type:'number',min:0,max:4,integer:true},
  {key:'earthField',label:'Earth field',type:'string',options:[]},
];
const parseSettings=text=>parseViewerCommand(text,{...options,settings});
test('typed settings cover enums, booleans, colors, bounds and quoted text',()=>{
  assert.equal(parseSettings('set camera azimuth to 45').patch.cameraAzimuthDeg,45);
  assert.equal(parseSettings('set showAxes to on').patch.showAxes,true);
  assert.equal(parseSettings('set "Isosurfaces / Negative color" to blue').patch.isoNegativeColor,'#0000ff');
  assert.equal(parseSettings('set planet image to Jupiter').patch.earthTextureBody,'jupiter');
  assert.equal(parseSettings('set "Title / Text" to "Core and Mantle, Snapshot 1"').patch.title,'Core and Mantle, Snapshot 1');
  for(const text of ['set camera azimuth to 360','set phi average count to 1.5','set planet image to Vulcan',
    'set earth field to Br','set showAxes to maybe','set unknownSetting to 1']) assert.throws(()=>parseSettings(text),undefined,text);
});
test('ambiguous control labels require a full path',()=>{
  assert.throws(()=>parseViewerCommand('set opacity to .5',{settings:[
    {key:'cmbOpacity',label:'CMB / Opacity',aliases:['opacity'],type:'number'},
    {key:'isoOpacity',label:'Isosurface / Opacity',aliases:['opacity'],type:'number'},
  ]}),/Ambiguous/);
});


test('reset restores the opening view, preserves frame outside view state, and can be undone',async()=>{
  let state={params:{equatorField:'Br',cameraAzimuthDeg:45}},frame=7;
  const opening={params:{equatorField:'T',cameraAzimuthDeg:0}};
  const h=createCommandHistory({capture:()=>structuredClone(state),identity:()=>1,ready:()=>{},
    initial:()=>opening,apply:async snapshot=>{state=structuredClone(snapshot)}});
  await h.run(parse('reset view')); assert.deepEqual(state,opening);assert.equal(frame,7);
  await h.run(parse('undo'));assert.equal(state.params.equatorField,'Br');assert.equal(state.params.cameraAzimuthDeg,45);
});


test('paired isosurface colours follow requested level order, including remove and subsequent actions',()=>{
  const p=parse('remove field lines; show isosurface of ur at +100 and -100 in blue and red;').patch;
  assert.equal(p.showFieldLines,false);
  assert.equal(p.isoPositiveValue,100);assert.equal(p.isoPositiveColor,'#0000ff');
  assert.equal(p.isoNegativeValue,-100);assert.equal(p.isoNegativeColor,'#ff0000');
  assert.equal(p.showIsoPositive,true);assert.equal(p.showIsoNegative,true);
  const q=parse('show isosurface of ur at -1e2 and +1e2 in blue and red and hide CMB').patch;
  assert.equal(q.isoNegativeColor,'#0000ff');assert.equal(q.isoPositiveColor,'#ff0000');assert.equal(q.showCMB,false);
});
test('isosurface colours accept a shared colour, single level, hex values and dataset 2',()=>{
  const p=parse('show isosurfaces temperature at +.5 and -.5 in "#0af" and "#f00" from dataset 2').patch;
  assert.equal(p.isoField,'D2:T');assert.equal(p.isoPositiveColor,'#00aaff');assert.equal(p.isoNegativeColor,'#ff0000');
  assert.equal(parse('show isosurface ur at -.5 in blue').patch.isoNegativeColor,'#0000ff');
  const next=parse('show isosurface ur at -.5 in blue and show time').patch;
  assert.equal(next.isoNegativeColor,'#0000ff');assert.equal(next.showSimulationTime,true);
  const shared=parse('show isosurface ur at -.5 and +.5 in cyan').patch;
  assert.equal(shared.isoNegativeColor,'#00ffff');assert.equal(shared.isoPositiveColor,'#00ffff');
  const plain=parse('show isosurface ur at +100 and -100').patch;
  assert.equal(plain.isoPositiveValue,100);assert.equal(plain.isoNegativeValue,-100);
});
test('malformed paired levels or colours reject the whole command',()=>{
  for(const text of ['remove field lines; show isosurface ur at 100 and -100 in blue and bogus',
    'show isosurface ur at 100 in blue and red','show isosurface ur at 100 and 200 in blue and red',
    'show isosurface ur at 100 and -100 in blue and red and green',
    'show isosurface ur at 100 and -100 in #xyz and blue']) assert.throws(()=>parse(text),undefined,text);
});


const completionSettings=[...settings,
  {key:'meridianField',label:'Meridian / Field',options:[{value:'ur'},{value:'T'},{value:'D2:T'}]},
  {key:'isoField',label:'Isosurfaces / Field',options:[{value:'ur'},{value:'Br'}]},
  {key:'radialColormap',label:'Radial / Colour map',options:[{value:'viridis'},{value:'blue-white-red'}]},
];
test('autocomplete discovers loaded fields and preserves preceding actions',()=>{
  const s=commandSuggestions('remove field lines; show meridional D',completionSettings);
  assert.equal(s[0].value,'remove field lines; show meridional D2:T');
  assert.equal(commandSuggestions('show isosurface of u',completionSettings)[0].value,'show isosurface of ur at ');
  assert.equal(commandSuggestions('show meridional nonexistent',completionSettings).length,0);
  assert.equal(commandSuggestions('show meridional',[],3).length<=3,true);
});
test('autocomplete completes ordered colours, palettes and typed settings',()=>{
  assert.equal(commandSuggestions('show isosurface ur at +100 and -100 in blue and r',completionSettings)[0].value,
    'show isosurface ur at +100 and -100 in blue and red');
  assert.equal(commandSuggestions('show Br at radius 0.7 using vi',completionSettings)[0].value,'show Br at radius 0.7 using viridis');
  assert.equal(commandSuggestions('set camera azi',completionSettings)[0].value,'set "Point of view / Azimuth phi" to ');
  assert.equal(commandSuggestions('set planet image to j',completionSettings)[0].value,'set planet image to "jupiter"');
  assert.equal(commandSuggestions('set radial colourbar to vi',completionSettings)[0].value,'set radial colourbar to viridis');
  assert.equal(commandSuggestions('set showAxes to o',completionSettings).length,2);
});
test('completion does not split quoted text or the and in paired levels',()=>{
  assert.equal(commandCompletionStart('set "Title / Text" to "A, B and show C"'),0);
  assert.equal(commandCompletionStart('show isosurface ur at 1 and -1 in blue and red'),0);
  const input='hide CMB and show meridional u';
  assert.equal(input.slice(commandCompletionStart(input)),'show meridional u');
  assert.equal(commandSuggestions(input,completionSettings)[0].value,'hide CMB and show meridional ur');
});
