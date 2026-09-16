import assert from "node:assert/strict";
import test from "node:test";
import { overlayLayout, floaterGesture, createOverlayFloater, OVERLAY_POSITIONS } from "../src/overlay-floater.js";

test("all nine presets anchor the requested horizontal and vertical position", () => {
  assert.equal(OVERLAY_POSITIONS.length, 10);
  for (const vertical of ["top", "middle", "bottom"]) for (const horizontal of ["left", "center", "right"]) {
    const p = overlayLayout(1000, 800, 200, 100, `${vertical}-${horizontal}`);
    assert.equal(p.x, { left: 116, center: 500, right: 884 }[horizontal]);
    assert.equal(p.y, { top: 734, middle: 400, bottom: 66 }[vertical]);
  }
});

test("custom positions scale into exports and remain visible on small screens", () => {
  const a = overlayLayout(1000, 800, 200, 100, "custom", .23, .74);
  const b = overlayLayout(3000, 2400, 600, 300, "custom", .23, .74);
  for (const key of Object.keys(a)) assert.equal(b[key], a[key] * 3);
  const huge = overlayLayout(320, 500, 2000, 1000, "custom", 1, 0);
  assert.ok(huge.width <= 320 && huge.height <= 500);
  assert.equal(huge.width / huge.height, 2);
  assert.ok(huge.x + huge.width / 2 <= 320);
});

const start = { left: 100, top: 80, width: 200, height: 100,
  viewportWidth: 1000, viewportHeight: 800, size: .2, minimum: .1, maximum: .9 };
test("drag clamps to viewport and resize preserves shape and top-left anchor", () => {
  assert.deepEqual(floaterGesture(start, 5000, -5000, false), { position: "custom", x: 1, y: 0, size: .2 });
  const resized = floaterGesture(start, 100, 50, true);
  assert.ok(Math.abs(resized.size - .3) < 1e-12);
  const layout = overlayLayout(1000, 800, 300, 150, "custom", resized.x, resized.y);
  assert.equal(layout.x - layout.width / 2, 100);
  assert.equal(800 - layout.y - layout.height / 2, 80);
  assert.equal(floaterGesture(start, -9999, -9999, true).size, .1);
  assert.ok(floaterGesture(start, 9999, 9999, true).size <= .9);
});

class Element extends EventTarget {
  constructor() { super(); this.style = {}; this.children = []; this.captured = new Set();
    this.classList = { add() {}, remove() {} }; }
  setAttribute() {} appendChild(child) { this.children.push(child); }
  setPointerCapture(id) { this.captured.add(id); } hasPointerCapture(id) { return this.captured.has(id); }
  releasePointerCapture(id) { this.captured.delete(id); } focus() {} remove() { this.removed = true; }
}
function send(node, type, properties = {}) {
  const e = new Event(type, { cancelable: true });
  for (const [key, value] of Object.entries({ button: 0, pointerId: 1, clientX: 100, clientY: 80, ...properties }))
    Object.defineProperty(e, key, { value });
  node.dispatchEvent(e); return e;
}

test("mouse/touch pointer drag, handle resize, cancellation and hidden export controls", () => {
  const body = new Element(), changes = [];
  const floater = createOverlayFloater({ label: "Map", getSize: () => .2, minimum: .1, maximum: .9,
    onChange: value => changes.push(value), document: { body, createElement: () => new Element() } });
  const box = body.children[0], handle = box.children[0];
  const canvas = { width: 2000, height: 1600,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 1000, height: 800 }) };
  const layout = { x: 400, y: 1340, width: 400, height: 200 };
  floater.sync(layout, canvas);
  assert.equal(box.style.left, "100px"); assert.equal(box.style.top, "80px");
  assert.ok(send(box, "pointerdown", { pointerType: "touch" }).defaultPrevented);
  send(box, "pointermove", { pointerId: 2, clientX: 300 }); assert.equal(changes.length, 0);
  send(box, "pointermove", { clientX: 300, clientY: 180 });
  assert.equal(changes[0].x, 300/800); assert.equal(changes[0].y, 180/700);
  send(box, "pointercancel"); assert.equal(box.captured.size, 0);
  send(box, "pointermove"); assert.equal(changes.length, 1);
  send(box, "pointerdown", { target: handle });
  send(box, "pointermove", { clientX: 200, clientY: 130 });
  assert.ok(Math.abs(changes[1].size - .3) < 1e-12);
  floater.sync(layout, canvas, true);
  assert.equal(box.hidden, true); assert.equal(box.captured.size, 0);
  send(box, "pointermove", { clientX: 600 }); assert.equal(changes.length, 2);
  floater.sync(layout, canvas);
  assert.ok(send(box, "keydown", { key: "ArrowRight" }).defaultPrevented);
  assert.equal(changes[2].x, 110/800);
  floater.dispose(); assert.equal(box.removed, true);
});
