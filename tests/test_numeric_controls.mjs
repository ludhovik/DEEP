import test from "node:test";
import assert from "node:assert/strict";
import { steppedValue } from "../src/numeric-controls.js";

test("slice height increments avoid floating-point display tails", () => {
  let value = 0;
  for (let i = 0; i < 30; i++) value = steppedValue(value, 1, { step: .01, min: -.95, max: .95 });
  assert.equal(value, .3);
  assert.equal(steppedValue(value, -1, { step: .01 }), .29);
});

test("longitude, frame and radius edits respect bounds and Shift steps", () => {
  assert.equal(steppedValue(355, 1, { step: 1, min: 0, max: 360, fast: true }), 360);
  assert.equal(steppedValue(0, -1, { step: 1, min: 0, max: 20 }), 0);
  assert.equal(steppedValue(.345, 1, { step: .001, fast: true }), .355);
  assert.equal(steppedValue(-.95, -1, { step: .01, min: -.95 }), -.95);
});

test("invalid input or steps cannot manufacture a new numeric value", () => {
  assert.ok(Number.isNaN(steppedValue(NaN, 1)));
  assert.equal(steppedValue(1, 1, { step: 0 }), 1);
  assert.equal(steppedValue(1, 1, { step: NaN }), 1);
});
