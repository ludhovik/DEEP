import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { Window } from 'happy-dom';
import { NamedViews, ViewJournal, portableView, mergeNamedView, validCameraPose, createViewWorkspace, captureGuiFolders, restoreGuiFolders } from '../src/view-workspace.js';
import { createComparisonBridge, COMPARISON_CHANNEL } from '../src/comparison-bridge.js';
import { mountComparison } from '../src/comparison-controller.js';

const pose = {position:[0,-3,1], target:[0,0,0], up:[0,0,1], fov:45};
const view = () => ({version:2, cameraLengthUnit:'r_outer', cameraPose:structuredClone(pose), params:{equatorField:'T',equatorScale:'manual',equatorMin:-1,equatorMax:1,showEquator:true}});
const memory = () => { const map = new Map(); return {getItem:key=>map.get(key),setItem:(key,value)=>map.set(key,value)}; };
const tick = () => new Promise(resolve => setImmediate(resolve));

test('named views are portable across radii and datasets without losing scientific display settings', () => {
  const store = new NamedViews(memory()), snapshot = view();
  Object.assign(snapshot.params,{primaryNativeRadius:1.53,primaryPhysicalRadius:3480,secondaryNativeRadius:1.2,
    secondaryPhysicalRadius:3480,placementUnit:'km',datasetPath:'private/folder',sequenceFrame:8,
    meridianField:'PHI:1',phiAvgCount:1,phiAvg1Field:'ur',phiAvg1Mode:'mean'});
  store.save('Mean flow',snapshot);
  const saved = store.list()[0].snapshot;
  assert.equal(saved.params.meridianField,'PHI:1'); assert.equal(saved.params.phiAvg1Field,'ur');
  for(const key of ['primaryNativeRadius','primaryPhysicalRadius','secondaryNativeRadius','secondaryPhysicalRadius','placementUnit','datasetPath','sequenceFrame']) assert.equal(saved.params[key],undefined);
  assert.equal(saved.params.equatorMin,-1); assert.deepEqual(saved.cameraPose,pose);
  assert.equal(snapshot.params.primaryNativeRadius,1.53,'saving must not mutate active settings');
  const appearance = portableView(saved,false);
  assert.equal(appearance.params.meridianField,undefined);assert.equal(appearance.params.phiAvgCount,undefined);
  assert.equal(appearance.params.equatorScale,'manual');
  const current=view();Object.assign(current.params,{primaryNativeRadius:2.7,phiAvgCount:2,meridianField:'PHI:2',phiAvg2Field:'T'});
  const merged=mergeNamedView(current,saved,false);
  assert.equal(merged.params.primaryNativeRadius,2.7);assert.equal(merged.params.phiAvgCount,2);
  assert.equal(merged.params.meridianField,'PHI:2');assert.equal(merged.params.phiAvg2Field,'T');
});

test('named views round-trip, merge without overwriting, and reject malformed/quota-limited storage', () => {
  const store = new NamedViews(memory());
  store.save('Temperature',view());
  assert.throws(()=>store.save('Temperature',view()),/already exists/);
  store.import(store.export()); assert.deepEqual(store.list().map(x=>x.name),['Temperature','Temperature (2)']);
  store.rename('Temperature (2)','Velocity'); store.remove('Temperature');
  const exported=store.export(); const other=new NamedViews(memory()); other.import(exported);
  assert.equal(other.list()[0].name,'Velocity');
  assert.throws(()=>store.rename('Velocity',''),/names/);
  assert.throws(()=>store.import('{bad'),SyntaxError);
  assert.throws(()=>store.import(JSON.stringify({format:'deepscope-named-views',version:1,views:[{name:'bad',snapshot:{version:2,params:{foo:{run:'code'}}}}]})),/Invalid view/);
  const blocked=new NamedViews({getItem:()=>null,setItem:()=>{throw new Error('quota');}});
  assert.throws(()=>blocked.save('Test',view()),/quota/);
  assert.throws(()=>store.import(' '.repeat(2_000_001)),/2 MB/);
});

test('undo and redo cover UI changes, branch correctly and retain history across frames but not datasets',async()=>{
  let state=view(),root='core',frame=0;
  const journal=new ViewJournal({capture:()=>state,apply:async value=>{state=value;},identity:()=>root,ready:()=>true,limit:4});
  journal.record(); state.params.equatorField='ur';journal.record();frame=12;
  await journal.step(-1);assert.equal(state.params.equatorField,'T');assert.equal(frame,12);
  await journal.step(1);assert.equal(state.params.equatorField,'ur');
  await journal.step(-1);state.params.equatorField='C';journal.record();
  await assert.rejects(journal.step(1),/Nothing to redo/);
  root='mantle';await assert.rejects(journal.step(-1),/Nothing to undo/);
  for(let i=0;i<10;i++){state.params.equatorMin=i;journal.record();}assert.equal(journal.states.length,4);
});

test('failed history operations restore the previous view and cannot overlap or cross dataset boundaries',async()=>{
  let state=view(),root='same',unblock;
  const journal=new ViewJournal({capture:()=>state,identity:()=>root,ready:()=>true,apply:async value=>{
    state=value;
    if(value.params.equatorField==='bad')throw new Error('missing field');
    if(value.params.equatorField==='slow')await new Promise(resolve=>{unblock=resolve;});
  }});
  journal.record();
  await assert.rejects(journal.restore({...view(),params:{equatorField:'bad'}}),/missing field/);
  assert.equal(state.params.equatorField,'T');assert.equal(journal.states.length,1);
  const pending=journal.restore({...view(),params:{equatorField:'slow'}});
  await assert.rejects(journal.restore(view()),/Wait for/);
  root='other';state=view();unblock();await assert.rejects(pending,/dataset changed/i);
  assert.equal(state.params.equatorField,'T','must not roll back into another dataset');
});

test('named-view UI saves, updates, loads and keeps text editing shortcuts native',async t=>{
  const window=new Window();Object.assign(globalThis,{window,document:window.document});
  let state=view(),errors=[];const workspace=createViewWorkspace({capture:()=>state,apply:async value=>{state=value;},identity:()=>1,ready:()=>true,
    initial:()=>view(),storage:memory(),openComparison(){},onError:message=>errors.push(message)});
  const parent=document.createElement('div');document.body.append(parent);
  const history=document.createElement('div');document.body.prepend(history);workspace.mountHistory(history);
  workspace.mount(parent);
  assert.equal(parent.querySelector('[data-action=undo]'),null,'history must be outside named views');
  assert.equal(history.querySelectorAll('button').length,2);
  t.after(async()=>{window.dispatchEvent(new window.Event('pagehide'));await window.happyDOM.close();});
  const input=parent.querySelector('[data-name]'); input.value='Sections';
  parent.querySelector('[data-action=save]').click();await tick();
  assert.equal(parent.querySelector('select').value,'Sections');
  workspace.journal.record();state.params.equatorField='ur';workspace.journal.record();
  parent.querySelector('[data-action=load]').click();await tick();assert.equal(state.params.equatorField,'T');
  history.querySelector('[data-action=undo]').click();await tick();assert.equal(state.params.equatorField,'ur');
  const textUndo=new window.KeyboardEvent('keydown',{key:'z',ctrlKey:true,bubbles:true,cancelable:true});
  input.dispatchEvent(textUndo);assert.equal(textUndo.defaultPrevented,false);
  const undo=new window.KeyboardEvent('keydown',{key:'z',ctrlKey:true,bubbles:true,cancelable:true});
  document.body.dispatchEvent(undo);await tick();assert.equal(undo.defaultPrevented,true);assert.equal(state.params.equatorField,'T');
  assert.deepEqual(errors,[]);
  parent.querySelector('[data-fields]').checked=false;
  input.value='New draft';
  const replacement=document.createElement('div');parent.replaceWith(replacement);workspace.mount(replacement);
  assert.equal(replacement.querySelector('select').value,'Sections');
  assert.equal(replacement.querySelector('[data-fields]').checked,false);
  assert.equal(replacement.querySelector('[data-name]').value,'New draft');
});

test('restoring a view preserves which control folders are open without replaying control values',()=>{
  const folder=(title,closed,folders=[])=>({_title:title,_closed:closed,folders,open(value){this._closed=!value;}});
  const old=folder('Controls',false,[folder('Views & comparison',false),folder('Slices',true)]);
  const state=captureGuiFolders(old),next=folder('Controls',true,[folder('Views & comparison',true),folder('Slices',false)]);
  restoreGuiFolders(next,state);
  assert.equal(next._closed,false);assert.equal(next.folders[0]._closed,false);assert.equal(next.folders[1]._closed,true);
});

test('camera validation rejects degenerate/nonfinite poses but keeps rolled cameras',()=>{
  assert.equal(validCameraPose(pose),true);
  assert.equal(validCameraPose({...pose,position:[0,0,0]}),false);
  assert.equal(validCameraPose({...pose,up:[0,0,0]}),false);
  assert.equal(validCameraPose({...pose,fov:Infinity}),false);
  assert.equal(validCameraPose({...pose,up:[1,0,0]}),true);
});

test('comparison bridge bootstraps data once and transfers only view codes through copy requests',async()=>{
  const listeners={},sent=[],parent={postMessage:(message,origin)=>sent.push({message,origin})};
  let poll, camera=structuredClone(pose), loads=0,viewLoads=[],frame=0,colours={equatorScale:'manual',equatorMin:-1,equatorMax:1};
  const window={parent,location:{origin:'https://viewer.test',href:'https://viewer.test/DEEP/'},
    addEventListener:(name,fn)=>{listeners[name]=fn;},setInterval:fn=>{poll=fn;},clearInterval(){}};
  globalThis.window=window;
  const bundle={root:'fsdir:primary-1',folders:[['primary-1',{type:'files',files:new Map([['metadata.json',new Blob(['{}'])]])}]],snapshot:view()};
  createComparisonBridge({captureCamera:()=>camera,applyCamera:value=>{camera=value;},captureDataset:()=>bundle,
    applyDataset:async()=>{loads++;},captureView:()=> 'DTV2:view',applyView:async code=>{viewLoads.push(code);},ready:()=>true,onError:message=>assert.fail(message),
    captureFrame:()=>frame,applyFrame:async value=>{frame=value;},captureColours:()=>colours,applyColours:async value=>{colours=value;}});
  const message=(source,origin,type,payload={})=>listeners.message({source,origin,data:{channel:COMPARISON_CHANNEL,type,...payload}});
  await message({},window.location.origin,'load-dataset',{bundle});
  await message(parent,'https://evil.test','load-dataset',{bundle});assert.equal(loads,0);
  await message(parent,window.location.origin,'load-dataset',{bundle});assert.equal(loads,1);
  await message(parent,window.location.origin,'request-view',{request:7});
  const transfer=sent.find(entry=>entry.message.type==='view').message;
  assert.equal(transfer.request,7);assert.equal(transfer.code,'DTV2:view');assert.equal(transfer.bundle,undefined);
  await message(parent,window.location.origin,'load-view',{code:transfer.code});
  assert.deepEqual(viewLoads,['DTV2:view']);assert.equal(loads,1);assert.equal(frame,0);
  const noDatasetExport=sent.length;
  await message(parent,window.location.origin,'request-dataset',{request:8});
  assert.equal(sent.length,noDatasetExport,'old dataset-copy protocol has been removed');
  const moved={...pose,position:[1,-4,2]};await message(parent,window.location.origin,'camera',{pose:moved});
  const count=sent.length;await poll();assert.equal(sent.length,count);
  camera={...pose,position:[2,-4,2]};await poll();assert.equal(sent.at(-1).message.type,'camera');
  await message(parent,window.location.origin,'frame',{frame:7});await poll();assert.equal(frame,7);
  const linkedCount=sent.length;await poll();assert.equal(sent.length,linkedCount,'linked frame must not echo');
  await message(parent,window.location.origin,'colours',{colours:{equatorMin:-3}});await poll();assert.equal(colours.equatorMin,-3);
  await message(parent,window.location.origin,'frame',{frame:9});
  await message(parent,window.location.origin,'unlink',{kind:'frame'});await poll();assert.equal(frame,7);
});

test('comparison host queues initial data, links only cameras and routes copy requests to the intended pane',async t=>{
  const dom=new Window();t.after(()=>dom.happyDOM.close());
  const html=fs.readFileSync(new URL('../compare.html',import.meta.url),'utf8').replace(/src="\.\/\?comparison[^\"]*"/g,'');
  dom.document.body.innerHTML=html;
  const frames=[...dom.document.querySelectorAll('iframe')],sent=[[],[]],listeners={};
  frames.forEach((frame,i)=>{Object.defineProperty(frame,'contentWindow',{value:{postMessage:message=>sent[i].push(message)}});});
  const opener={postMessage(){}},window={location:{origin:'https://viewer.test'},opener,addEventListener:(name,fn)=>listeners[name]=fn};
  mountComparison(dom.document,window);
  assert.equal(sent[0][0].type,'hello');sent[0].length=sent[1].length=0;
  const message=(source,type,payload={})=>listeners.message({source,origin:window.location.origin,data:{channel:COMPARISON_CHANNEL,type,...payload}});
  message(opener,'bootstrap',{bundle:{root:'mantle',snapshot:view()}});assert.equal(sent[0].length,0);
  message(frames[0].contentWindow,'viewer-ready');assert.equal(sent[0][0].type,'load-dataset');
  message(frames[1].contentWindow,'viewer-ready');
  message(frames[0].contentWindow,'camera',{pose});assert.equal(sent[1].at(-1).type,'camera');
  const count=sent[1].length;dom.document.querySelector('#link-cameras').checked=false;
  message(frames[0].contentWindow,'camera',{pose});assert.equal(sent[1].length,count);
  dom.document.querySelector('#copy-a').click();const request=sent[0].at(-1).request;
  message(frames[1].contentWindow,'view',{request,code:'wrong'});assert.equal(sent[1].length,count);
  message(frames[0].contentWindow,'view',{request,code:'DTV2:appearance'});assert.equal(sent[1].at(-1).code,'DTV2:appearance');
  assert.equal(sent[1].some(message=>message.type==='load-dataset'),false,'copy appearance must never load a dataset');
  message({},'camera',{pose});assert.equal(sent[1].at(-1).type,'load-view');
  dom.document.querySelector('#copy-b').click();const reverse=sent[1].at(-1).request;
  assert.equal(sent[1].at(-1).type,'request-view');
  message(frames[1].contentWindow,'view',{request:reverse,code:'DTV2:other'});
  assert.equal(sent[0].at(-1).type,'load-view');assert.equal(sent[0].at(-1).code,'DTV2:other');
  const before=sent[1].length;message(frames[0].contentWindow,'frame',{frame:3});assert.equal(sent[1].length,before);
  dom.document.querySelector('#link-frames').checked=true;
  message(frames[0].contentWindow,'frame',{frame:3});assert.equal(sent[1].at(-1).frame,3);
  dom.document.querySelector('#link-colours').checked=true;
  message(frames[0].contentWindow,'colours',{colours:{equatorMin:-8}});assert.equal(sent[1].at(-1).colours.equatorMin,-8);
});

test('view transfer uses destination history, blocks overlapping links and does not echo the applied pose',async()=>{
  const listeners={},sent=[],errors=[],parent={postMessage:message=>sent.push(message)};
  let poll,bridge,release,state=view();
  globalThis.window={parent,location:{origin:'https://viewer.test'},addEventListener:(name,fn)=>{listeners[name]=fn;},setInterval:fn=>{poll=fn;},clearInterval(){}};
  const journal=new ViewJournal({capture:()=>state,identity:()=>1,ready:()=>!bridge?.busy,
    apply:async value=>{state=value;if(release===undefined)await new Promise(resolve=>{release=resolve;});}});
  const target={...view(),cameraPose:{...pose,position:[3,-4,2]}};
  bridge=createComparisonBridge({captureCamera:()=>state.cameraPose,applyCamera:value=>{state.cameraPose=value;},
    captureDataset:()=>assert.fail('No dataset transfer'),applyDataset:async()=>assert.fail('No dataset load'),
    captureView:()=> 'DTV2:test',applyView:async()=>journal.restore(target),ready:()=>true,onError:message=>errors.push(message)});
  const message=(type,payload={})=>listeners.message({source:parent,origin:'https://viewer.test',data:{channel:COMPARISON_CHANNEL,type,...payload}});
  const pending=message('load-view',{code:'DTV2:test'});
  assert.equal(journal.busy,true);
  await message('camera',{pose});assert.deepEqual(state.cameraPose,target.cameraPose);
  await message('load-view',{code:'DTV2:another'});assert.equal(errors.length,1);
  const during=sent.length;await poll();assert.equal(sent.length,during);
  release();await pending;assert.equal(journal.index,1);
  assert.equal(sent.at(-1).type,'view-applied');
  const count=sent.length;await poll();assert.equal(sent.length,count);
  await journal.step(-1);assert.deepEqual(state.cameraPose,pose);
});

test('comparison compact styles stay scoped and preserve separate slider/value columns',async t=>{
  for(const comparison of [false,true]) {
    const window=new Window();t.after(()=>window.happyDOM.close());
    const {document}=window;
    // happy-dom caches descendant computed styles on ancestor-class changes;
    // use separate documents, just as standalone and comparison viewers do.
    document.documentElement.classList.toggle('comparison-view',comparison);
    for(const file of ['style.css','mobile-layout.css','view-workspace.css','comparison-viewer.css']) {
      const style=document.createElement('style');style.textContent=fs.readFileSync(new URL(`../src/${file}`,import.meta.url),'utf8');document.head.append(style);
    }
    document.body.innerHTML='<div class="lil-gui main-controls-gui"><div class="lil-controller numeric-enhanced lil-has-slider"><input></div></div>';
    const gui=document.querySelector('.lil-gui'),input=document.querySelector('input');
    assert.equal(window.getComputedStyle(gui).getPropertyValue('--font-size'),comparison?'10.5px':'11px');
    assert.equal(window.getComputedStyle(input).gridColumn,'5');
    if(comparison)assert.match(window.getComputedStyle(gui).maxWidth,/260px/);
  }
});
