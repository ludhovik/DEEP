import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import vm from "node:vm";
import { createSimulationTimeOverlay, simulationTimeLabel, timeBoxLayout,
  TIME_BOX_POSITIONS } from "../src/simulation-time.js";

test("time comes from the snapshot, with zero preserved and unknown times explicit", () => {
  assert.equal(simulationTimeLabel({ time: 0 }), "t = 0 (native units)");
  assert.equal(simulationTimeLabel({ time: 1.23456789 }, { time: 99 }, 5), "t = 1.2346 (native units)");
  assert.equal(simulationTimeLabel({ time: .5, time_units: "s" }), "t = 0.5 (s)");
  assert.equal(simulationTimeLabel({}, { time: 2 }), "t = 2 (native units)");
  for (const time of [null, undefined, NaN, Infinity, "", "1"])
    assert.equal(simulationTimeLabel({ time }, { time: 42 }), "t = unknown");
  assert.equal(simulationTimeLabel(null), "");
});

test("box position scales with PNG/PDF/video resolution", () => {
  for (const corner of TIME_BOX_POSITIONS) {
    const a = timeBoxLayout(1200, 700, 480, 76, corner);
    const b = timeBoxLayout(2400, 1400, 480, 76, corner);
    for (const key of Object.keys(a)) assert.equal(b[key], a[key] * 2);
    assert.ok(a.x - a.width / 2 >= 0 && a.x + a.width / 2 <= 1200);
    assert.ok(a.y - a.height / 2 >= 0 && a.y + a.height / 2 <= 700);
  }
});

test("overlay updates its texture per frame and preserves the rendered scene", () => {
  const labels = [];
  const ctx = { measureText: text => ({ width: text.length * 20 }),
    fillRect() {}, strokeRect() {}, fillText(text) { labels.push(text); } };
  const canvas = { width: 1, height: 1, getContext: () => ctx };
  const overlay = createSimulationTimeOverlay({ makeCanvas: () => canvas });
  let draws = 0, firstMap, disposals = 0;
  const renderer = { domElement: { width: 1200, height: 700 }, autoClear: true,
    render(scene, camera) {
      draws++;
      assert.equal(this.autoClear, false);
      assert.equal(camera.right, 1200);
      const sprite = scene.children[0];
      assert.equal(sprite.material.depthTest, false);
      assert.equal(sprite.material.depthWrite, false);
      if (!firstMap) {
        firstMap = sprite.material.map;
        firstMap.addEventListener("dispose", () => { disposals++; });
      }
    } };
  overlay.render(renderer, "t = 1");
  overlay.render(renderer, "t = 1");
  assert.equal(disposals, 0);
  overlay.render(renderer, "t = 2");
  assert.deepEqual(labels, ["t = 1", "t = 2"]);
  assert.equal(disposals, 1);
  overlay.render(renderer, "");
  assert.equal(draws, 3);
  assert.equal(renderer.autoClear, true);
  renderer.render = () => { throw new Error("GPU failure"); };
  assert.throws(() => overlay.render(renderer, "t = 2"), /GPU failure/);
  assert.equal(renderer.autoClear, true);
  overlay.dispose();
});

test("shared renderScene uses the current frame time and honours visibility", () => {
  const source = fs.readFileSync(new URL("../src/main.js", import.meta.url), "utf8");
  const start = source.indexOf("function renderScene() {");
  const events = [];
  const context = vm.createContext({
    updateDisplayScale() {}, updateCameraClipping() {},
    renderer: { render() { events.push("scene"); } }, scene: {}, camera: {},
    params: { showSimulationTime: true, sequenceFrame: 0, simulationTimePrecision: 7,
      simulationTimePosition: "bottom-left", simulationTimeSize: 18 },
    sequenceIndex: { frames: [{ time: 1 }, { time: 2 }] }, metadata: { time: 1 },
    simulationTimeLabel, simulationTimeOverlay: { render(renderer, text) { events.push(text); } },
  });
  vm.runInContext(source.slice(start, source.indexOf("\n}", start) + 2), context);
  context.renderScene();
  context.metadata = { time: 2 }; context.params.sequenceFrame = 1;
  context.renderScene();
  context.params.showSimulationTime = false;
  context.renderScene();
  assert.deepEqual(events, ["scene", "t = 1 (native units)", "scene", "t = 2 (native units)", "scene"]);
});
