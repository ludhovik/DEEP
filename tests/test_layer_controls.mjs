import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { Window } from 'happy-dom';
import GUI from 'lil-gui';
import { addLayerOverview, enhanceChoice, matchingOptions, moveControl, organiseLayer, restoreLayerValues } from '../src/layer-controls.js';
import { enhanceNumericControls } from '../src/numeric-controls.js';

function environment(t) {
  const window = new Window();
  Object.assign(globalThis, { window, document: window.document,
    requestAnimationFrame: window.requestAnimationFrame.bind(window), cancelAnimationFrame: window.cancelAnimationFrame.bind(window) });
  const gui = new GUI({ title: 'Controls' });
  gui.domElement.classList.add('main-controls-gui');
  t.after(async () => { gui.destroy(); await window.happyDOM.close(); });
  return { window, gui };
}

const keyboard = (window, element, key) => element.dispatchEvent(new window.KeyboardEvent('keydown', {key, bubbles:true, cancelable:true}));

test('field search covers labels, calculator aliases and dataset prefixes without losing values', () => {
  assert.deepEqual(matchingOptions(['T','Mantle: T anomaly','φ1: mean ur'], ['T','SECONDARY:Tanomaly','PHI:1'], 'mantle anomaly'),
    [{label:'Mantle: T anomaly',value:'SECONDARY:Tanomaly'}]);
  assert.equal(matchingOptions(['φ1: mean ur'], ['PHI:1'], 'phi:1')[0].value, 'PHI:1');
  assert.equal(matchingOptions(['Br'], ['Br'], 'missing').length, 0);
});

test('layer restore keeps camera, sequence, other layers and unavailable calculator definitions', () => {
  const params = {equatorField:'T',equatorScale:'manual',meridianField:'ur',cameraDistance:3,sequenceFrame:7,phiAvgCount:0};
  restoreLayerValues(params, {equatorField:'PHI:1',equatorScale:'minmax',cameraDistance:9,sequenceFrame:0},
    {equatorField:'C'}, ['equatorField','equatorScale'], (_, field) => ['T','C'].includes(field));
  assert.deepEqual(params, {equatorField:'C',equatorScale:'minmax',meridianField:'ur',cameraDistance:3,sequenceFrame:7,phiAvgCount:0});
});

test('reordering and Advanced preserve callbacks, controller references and destruction', t => {
  const {gui} = environment(t), params={field:'T',opacity:.5,z:0,show:true}; let calls=0;
  const layer=gui.addFolder('Slice'), field=layer.add(params,'field',['T','C']).onChange(()=>calls++);
  layer.add(params,'opacity'); const position=layer.add(params,'z'); layer.add(params,'show');
  const nested=layer.addFolder('Detail');nested.add({a:1},'a');
  const advanced=organiseLayer(layer,['show','field','z']);
  assert.deepEqual(layer.children.map(c=>c.property || c._title),['show','field','z','Advanced']);
  assert.equal(position.parent,layer);assert.equal(nested.parent,advanced);assert.equal(advanced._closed,true);
  field.setValue('C');assert.equal(calls,1);
  assert.equal(layer.controllersRecursive().length,5);
  layer.destroy();assert.equal(gui.controllersRecursive().length,0);
});

test('search selection, no results, keyboard, live options and disabled selectors use real lil-gui', t => {
  const {window,gui}=environment(t), params={field:'T'};let changes=0,finishes=0;
  const controller=gui.add(params,'field',{'Temperature':'T','Velocity radial':'ur','Mean azimuthal':'PHI:1'})
    .onChange(()=>changes++).onFinishChange(()=>finishes++);
  enhanceChoice(controller);
  const picker=controller.domElement.querySelector('details'), search=picker.querySelector('input');
  picker.open=true;picker.dispatchEvent(new window.Event('toggle'));
  search.value='mean';search.dispatchEvent(new window.Event('input'));
  assert.equal(params.field,'T');assert.equal(picker.querySelectorAll('button').length,1);
  picker.querySelector('button').click();
  assert.equal(params.field,'PHI:1');assert.equal(changes,1);assert.equal(finishes,1);assert.equal(picker.open,false);
  assert.equal(document.activeElement,picker.querySelector('summary'));
  picker.open=true;picker.dispatchEvent(new window.Event('toggle'));
  search.value='nothing';search.dispatchEvent(new window.Event('input'));
  assert.equal(picker.querySelectorAll('button').length,0);assert.ok(picker.querySelector('[role=status]'));
  controller.options({Composition:'C',Temperature:'T'});
  search.value='';search.dispatchEvent(new window.Event('input'));
  keyboard(window,search,'ArrowDown');assert.equal(document.activeElement.textContent,'Composition');
  keyboard(window,document.activeElement,'ArrowDown');assert.equal(document.activeElement.textContent,'Temperature');
  keyboard(window,document.activeElement,'Escape');assert.equal(picker.open,false);
  controller.disable();assert.equal(picker.querySelector('summary').tabIndex,-1);
  controller.enable();assert.equal(picker.querySelector('summary').tabIndex,0);
});

test('palette selectors show each gradient and refresh custom previews', t => {
  const {window,gui}=environment(t), p={colormap:'blue'};let custom='red';
  const controller=gui.add(p,'colormap',['blue','custom']);
  enhanceChoice(controller, value=>`linear-gradient(to right, white, ${value==='custom'?custom:value})`);
  const picker=controller.domElement.querySelector('details');picker.open=true;picker.dispatchEvent(new window.Event('toggle'));
  assert.equal(picker.querySelectorAll('button .palette-swatch').length,2);
  picker.querySelectorAll('button')[1].click();
  assert.match(picker.querySelector('summary .palette-swatch').style.background,/red/);
  custom='green';controller.updateDisplay();
  assert.match(picker.querySelector('summary .palette-swatch').style.background,/green/);
});

test('overview toggles share original callbacks and reflect per-layer changes', t => {
  const {gui}=environment(t), p={show:true,unavailable:false};let calls=0;
  const folder=gui.addFolder('CMB'), original=folder.add(p,'show').onChange(()=>calls++);
  const hidden=gui.addFolder('Unavailable').hide();hidden.add(p,'unavailable');
  const overview=addLayerOverview(gui,p,[{folder,label:'CMB',show:'show'},{folder:hidden,label:'Unavailable',show:'unavailable'}]);
  assert.equal(gui.children[0],overview);assert.equal(overview.controllers.length,1);
  const quick=overview.controllers[0];quick.setValue(false);assert.equal(p.show,false);assert.equal(calls,1);
  original.setValue(true);quick.updateDisplay();assert.equal(quick.getValue(),true);assert.equal(calls,2);
});

test('actual layer reset handler restores only its whitelist and avoids a GUI rebuild', async t => {
  const {gui}=environment(t), params={showEquator:true,equatorField:'T',equatorScale:'manual',equatorOpacity:.4,
    meridianField:'Br',sequenceFrame:8,cameraDistance:3,cmbClipMode:'rear-half'};
  const folder=gui.addFolder('Equator');
  for(const key of ['showEquator','equatorField','equatorScale','equatorOpacity','cmbClipMode']) folder.add(params,key);
  let pending,rebuilt=0;
  const source=fs.readFileSync(new URL('../src/main.js',import.meta.url),'utf8');
  const functionSource=source.slice(source.indexOf('function installLayerControls('),source.indexOf('\nfunction buildGui()',source.indexOf('function installLayerControls(')));
  const install=vm.runInNewContext(`(${functionSource})`,{params,initialDatasetView:{snapshot:{params:{showEquator:false,equatorField:'C',equatorScale:'minmax',cmbClipMode:'none'}}},
    addLayerOverview,enhanceChoice,organiseLayer,restoreLayerValues,validFieldForState:()=>true,
    viewerTaskCallback:(_,fn)=>()=>pending=fn(),updateOpacities(){},updateFieldLineVisuals(){},updateVisibility(){},setStatus(){}});
  install(gui,[{folder,label:'Equator',show:'showEquator',primary:['showEquator','equatorField','equatorScale'],rebuild:async()=>rebuilt++}]);
  folder.controllers.find(c=>c.property==='reset').getValue()();await pending;
  assert.equal(rebuilt,1);assert.equal(params.showEquator,false);assert.equal(params.equatorField,'C');assert.equal(params.equatorScale,'minmax');
  assert.equal(params.cmbClipMode,'rear-half');assert.equal(params.meridianField,'Br');assert.equal(params.sequenceFrame,8);assert.equal(params.cameraDistance,3);
  assert.equal(folder.parent,gui);
});

test('compact desktop and phone layout reserve separate grid cells for numbers and sliders', t => {
  const {window,gui}=environment(t);
  for(const file of ['style.css','mobile-layout.css']) {const style=document.createElement('style');style.textContent=fs.readFileSync(new URL(`../src/${file}`,import.meta.url),'utf8');document.head.append(style);}
  const c=gui.add({z:0},'z',-1,1,.01);enhanceNumericControls(gui);
  assert.equal(window.getComputedStyle(c.$input).gridColumn,'5');assert.equal(window.getComputedStyle(c.$slider).gridColumn,'3');
  assert.equal(window.getComputedStyle(c.$slider).height,'18px');
  document.documentElement.classList.add('mobile-layout');
  // happy-dom caches computed :not() ancestor rules on existing elements.
  // Fresh controls verify the mobile cascade without relying on that cache.
  const phone=gui.add({z:0},'z',-1,1,.01);enhanceNumericControls(gui);
  assert.equal(window.getComputedStyle(phone.$input).gridRow,'1');assert.equal(window.getComputedStyle(phone.$slider).gridRow,'2');
  assert.equal(window.getComputedStyle(phone.$slider).height,'44px');
});
