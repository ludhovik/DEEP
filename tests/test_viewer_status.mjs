import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";
import { createViewerStatus } from "../src/viewer-status.js";

class Element {
  constructor() {
    this.textContent = ""; this.hidden = false; this.dataset = {}; this.attributes = {}; this.events = {};
    const names = new Set();
    this.classList = { toggle: (name, enabled) => enabled ? names.add(name) : names.delete(name), contains: name => names.has(name) };
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) { this.events[name] = callback; }
  click() { this.events.click?.(); }
  focus() { this.focused = true; }
}

function setup() {
  const elements = Object.fromEntries(["status", "panel", "warningButton", "notice", "noticeText", "dismissButton"].map(key => [key, new Element()]));
  elements.panel.classList.toggle("collapsed", true);
  const status = createViewerStatus({ ...elements, onReveal: () => elements.panel.classList.toggle("collapsed", false) });
  const ctx = vm.createContext({ viewerStatus: status, console: { error() {} } });
  const source = fs.readFileSync(new URL("../src/main.js", import.meta.url), "utf8");
  for (const name of ["setStatus", "runViewerTask"]) {
    const at = source.search(new RegExp(`(?:async )?function ${name}\\(`));
    vm.runInContext(source.slice(at, source.indexOf("\n}", at) + 2), ctx);
  }
  return { ...elements, display: status, ctx };
}

test("title errors retain the dataset summary and a collapsed warning until revealed or dismissed", () => {
  const ui = setup();
  ui.ctx.setStatus("dataset=zenodo:22310643 | XSHELLS");
  ui.ctx.setStatus("B² tubes exceed the geometry budget", { level: "error" });
  assert.equal(ui.status.textContent, "dataset=zenodo:22310643 | XSHELLS");
  assert.equal(ui.warningButton.hidden, false);
  assert.equal(ui.panel.classList.contains("collapsed"), true);
  assert.match(ui.warningButton.attributes["aria-label"], /geometry budget/);
  ui.warningButton.click();
  assert.equal(ui.panel.classList.contains("collapsed"), false);
  assert.equal(ui.notice.focused, true);
  assert.match(ui.noticeText.textContent, /geometry budget/);
  ui.dismissButton.click();
  assert.equal(ui.warningButton.hidden, true);
  assert.equal(ui.notice.hidden, true);
  assert.equal(ui.status.textContent, "dataset=zenodo:22310643 | XSHELLS");
});

test("progress and unrelated successful tasks cannot hide an error; a successful retry clears it", async () => {
  const ui = setup();
  await ui.ctx.runViewerTask("Magnetic field-line update", async () => { throw new Error("too many points"); });
  ui.ctx.setStatus("Camera distance: 3");
  await ui.ctx.runViewerTask("Colour update", async () => {});
  assert.equal(ui.warningButton.hidden, false);
  await ui.ctx.runViewerTask("Magnetic field-line visibility", async () => {});
  assert.equal(ui.warningButton.hidden, true);
});

test("older successes and tasks reporting their own errors cannot clear newer warnings", async () => {
  const ui = setup();
  let release;
  const old = ui.ctx.runViewerTask("Lines", () => new Promise(resolve => { release = resolve; }));
  await ui.ctx.runViewerTask("Lines", async () => { throw new Error("new failure"); });
  release(); await old;
  assert.equal(ui.warningButton.hidden, false);
  assert.match(ui.noticeText.textContent, /new failure/);
  await ui.ctx.runViewerTask("Lines", async () => {
    ui.ctx.setStatus("Failure reported internally", { level: "error", scope: "Lines" });
  });
  assert.equal(ui.warningButton.hidden, false);
  assert.equal(ui.noticeText.textContent, "Failure reported internally");
});

test("cancellation is silent while explicit nonfatal warnings show in the title", async () => {
  const ui = setup();
  await ui.ctx.runViewerTask("Load", async () => { throw { name: "AbortError" }; });
  assert.equal(ui.warningButton.hidden, true);
  ui.ctx.setStatus("Optional view.DTV2 was ignored", { level: "warning" });
  assert.equal(ui.warningButton.hidden, false);
  assert.equal(ui.notice.dataset.level, "warning");
  ui.display.clear();
  assert.equal(ui.warningButton.hidden, true);
});
