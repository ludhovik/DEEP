import test from 'node:test';
import assert from 'node:assert/strict';
import { bindRecenterGesture } from '../src/recenter-gesture.js';
function fixture() {
  const element=new EventTarget(), doc=new EventTarget();element.ownerDocument=doc;
  let time=0,count=0;
  const unbind=bindRecenterGesture(element,()=>count++,()=>time);
  function send(type,{id=1,x=50,y=50,dt=50,pointerType='touch',button=0}={}) {
    time+=dt;const e=new Event(type,{cancelable:true});
    Object.assign(e,{pointerType,pointerId:id,clientX:x,clientY:y,button});
    (type==='pointerdown'||type==='dblclick'?element:doc).dispatchEvent(e);
  }
  return {send,unbind,get count(){return count;}};
}
test('double click and double tap recenter once; synthetic mouse double click is ignored',()=>{
  const f=fixture();f.send('dblclick',{pointerType:'mouse'});assert.equal(f.count,1);
  for(let i=0;i<2;i++){f.send('pointerdown');f.send('pointerup');}
  assert.equal(f.count,2);f.send('dblclick');assert.equal(f.count,2);
  f.unbind();f.send('dblclick',{dt:1000});assert.equal(f.count,2);
});
test('pinches, cancelled gestures, long presses, drags and distant taps never recenter',()=>{
  for(const kind of ['pinch','cancel','long','drag','distant']) {
    const f=fixture();
    for(let i=0;i<2;i++) {
      const x=kind==='distant'?50+100*i:50;f.send('pointerdown',{x});
      if(kind==='pinch'){f.send('pointerdown',{id:2});f.send('pointerup',{id:2});}
      if(kind==='drag')f.send('pointermove',{x:100});
      f.send(kind==='cancel'?'pointercancel':'pointerup',{x,dt:kind==='long'?400:50});
    }
    assert.equal(f.count,0,kind);
  }
});
