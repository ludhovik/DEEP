// A double tap must be two short, stationary, single-finger taps—not a pinch.
export function bindRecenterGesture(element, recenter, now = () => performance.now()) {
  const pointers = new Map();
  let previous = null, multi = false, lastTouch = -Infinity;
  const doc = element.ownerDocument;
  function down(event) {
    if (event.pointerType !== 'touch') return;
    const time = now();lastTouch = time;
    pointers.set(event.pointerId,{x:event.clientX,y:event.clientY,time,moved:false});
    if (pointers.size > 1) { multi = true; previous = null; }
  }
  function move(event) {
    const p = pointers.get(event.pointerId);
    if (p && Math.hypot(event.clientX-p.x,event.clientY-p.y)>10) { p.moved=true;previous=null; }
  }
  function up(event) {
    const p = pointers.get(event.pointerId);
    if (!p) return;
    pointers.delete(event.pointerId);
    const time = now();lastTouch = time;
    if (event.type !== 'pointercancel' && !multi && !p.moved && time-p.time<=250
      && Math.hypot(event.clientX-p.x,event.clientY-p.y)<=10) {
      if (previous && time-previous.time<=350 && Math.hypot(p.x-previous.x,p.y-previous.y)<=24) {
        previous=null;recenter();
      } else previous={x:p.x,y:p.y,time};
    } else previous=null;
    if (!pointers.size) multi=false;
  }
  function doubleClick(event) {
    if (event.button===0 && now()-lastTouch>500) {event.preventDefault();recenter();}
  }
  element.addEventListener('pointerdown',down);
  element.addEventListener('dblclick',doubleClick);
  doc.addEventListener('pointermove',move);
  doc.addEventListener('pointerup',up);
  doc.addEventListener('pointercancel',up);
  return () => {
    element.removeEventListener('pointerdown',down);
    element.removeEventListener('dblclick',doubleClick);
    doc.removeEventListener('pointermove',move);
    doc.removeEventListener('pointerup',up);
    doc.removeEventListener('pointercancel',up);
  };
}
