// Exercise the actual Earth mesh with Three.js, without a browser or WebGL.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";
import * as THREE from "three";

const source = fs.readFileSync(new URL("../src/main.js", import.meta.url), "utf8");
const ctx = vm.createContext({ THREE, OPAQUE_OPACITY: 0.999, params: {} });
for (const name of ["clamp", "normalizePhi", "isAngleInCCWSector", "getFourSectorBoundaries",
  "getSectorIndexForPhi", "shouldKeepSurfaceCellForClip", "isEffectivelyOpaque",
  "applyOpacityAndDepth", "addSurfaceAppearanceControls", "configureSurfaceUnderside", "getSurfaceClipOptions", "getActiveCmbClipOptions", "makeEarthSurfaceMesh", "makeGapFillerMaterial"]) {
  const match = source.match(new RegExp(`function ${name}\\(`));
  assert.ok(match, `Viewer function ${name} exists`);
  vm.runInContext(source.slice(match.index, source.indexOf("\n}", match.index) + 2), ctx);
}

function mesh(longitude = 0, clip = null, opacity = 1) {
  return ctx.makeEarthSurfaceMesh(1, opacity, new THREE.Texture(), longitude, clip);
}

function triangles(geometry, visit) {
  const ids = geometry.index.array;
  const positions = geometry.getAttribute("position");
  for (let i = 0; i < ids.length; i += 3) {
    const indices = Array.from(ids.slice(i, i + 3));
    visit(indices, indices.map(j => new THREE.Vector3().fromBufferAttribute(positions, j)));
  }
}

test("Earth is a closed sphere with outward, non-degenerate faces including both poles", () => {
  const { geometry } = mesh();
  const edges = new Map(), vertices = new Set();
  triangles(geometry, (_ids, points) => {
    const [a, b, c] = points;
    const normal = b.clone().sub(a).cross(c.clone().sub(a));
    assert.ok(normal.length() > 1e-9, "No collapsed polar triangles");
    assert.ok(normal.dot(a) > 0, "All faces point outward");
    const keys = points.map(p => {
      assert.ok(Math.abs(p.length() - 1) < 1e-6);
      const key = p.toArray().join(",");
      vertices.add(key);
      return key;
    });
    for (let k = 0; k < 3; k++) {
      const key = [keys[k], keys[(k + 1) % 3]].sort().join("|");
      edges.set(key, (edges.get(key) || 0) + 1);
    }
  });
  assert.ok(vertices.has("0,0,1") && vertices.has("0,0,-1"));
  for (const count of edges.values()) assert.equal(count, 2, "No boundary gap or overlap");
  assert.equal(vertices.size - edges.size + geometry.index.count / 3, 2, "Sphere topology");
});

test("no Earth triangle interpolates across the map; polar UVs are centred", () => {
  const { geometry } = mesh();
  const uv = geometry.getAttribute("uv");
  let polarTriangles = 0;
  triangles(geometry, (ids, points) => {
    const u = ids.map(i => uv.getX(i));
    assert.ok(Math.max(...u) - Math.min(...u) < 0.01, "No whole-map seam strip");
    const pole = points.findIndex(p => Math.abs(p.z) === 1);
    if (pole >= 0) {
      polarTriangles++;
      const neighbours = u.filter((_value, i) => i !== pole);
      assert.ok(Math.abs(u[pole] - (neighbours[0] + neighbours[1]) / 2) < 1e-7);
      assert.equal(uv.getY(ids[pole]), points[pole].z > 0 ? 1 : 0);
    }
  });
  assert.ok(polarTriangles > 0);
});

test("rays hit the longitude join and both polar caps", () => {
  const earth = mesh();
  earth.updateMatrixWorld(true);
  for (const direction of [
    [1, 0, 0], [1, -1e-7, 0], [1, 1e-7, 0], [-1, 0, 0],
    [1e-6, 2e-6, 1], [-1e-6, -2e-6, -1], [0, 0, 1], [0, 0, -1],
  ]) {
    const radial = new THREE.Vector3(...direction).normalize();
    const ray = new THREE.Raycaster(radial.clone().multiplyScalar(3), radial.clone().negate());
    const hits = ray.intersectObject(earth);
    assert.ok(hits.length > 0, `No missing face at ${direction}`);
    assert.ok(Math.abs(hits[0].distance - 2) < 0.001);
  }
});

test("texture longitude changes geographic alignment without rotating geometry or clips", () => {
  const zero = mesh(), rotated = mesh(90);
  assert.deepEqual(zero.geometry.attributes.position.array, rotated.geometry.attributes.position.array);
  assert.deepEqual(zero.geometry.index.array, rotated.geometry.index.array);
  assert.deepEqual(rotated.rotation.toArray().slice(0, 3), [0, 0, 0]);
  zero.material.map.updateMatrix(); rotated.material.map.updateMatrix();
  const texel = (map, u, v) => map.transformUv(new THREE.Vector2(u, v));
  assert.equal(texel(zero.material.map, 0, 0.5).x, 0.5, "Greenwich at +x");
  assert.equal(texel(zero.material.map, 0.25, 0.5).x, 0.75, "90 E at +y");
  assert.equal(texel(rotated.material.map, 0.25, 0.5).x, 0.5, "Positive offset moves Greenwich east");
  assert.equal(texel(zero.material.map, 0, 1).y, 0, "North samples the top of the image");
});

test("intentional Earth clipping and opacity still work", () => {
  const full = mesh();
  const quarter = mesh(0, { enabled: true, mode: "selected-eight-quarters", hasTwoPlanes: true,
    phiA: 0, phiB: Math.PI / 2, northMask: [true, false, false, false],
    southMask: [false, false, false, false] }, 0.4);
  assert.equal(quarter.geometry.index.count, full.geometry.index.count / 8);
  triangles(quarter.geometry, (_ids, points) => {
    const centre = points.reduce((sum, p) => sum.add(p), new THREE.Vector3());
    assert.ok(centre.x > 0 && centre.y > 0 && centre.z > 0);
  });
  assert.equal(full.material.transparent, false);
  assert.equal(full.material.depthWrite, true);
  assert.equal(quarter.material.transparent, true);
  assert.equal(quarter.material.depthWrite, false);
  assert.equal(quarter.material.opacity, 0.4);
});

test("the bundled texture is a 2:1 PNG suitable for latitude-longitude mapping", () => {
  const png = fs.readFileSync(new URL("../public/assets/earth_blue_marble.png", import.meta.url));
  assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  const width = png.readUInt32BE(16), height = png.readUInt32BE(20);
  assert.ok(width >= 2048);
  assert.equal(width, 2 * height);
});

test("all 256 surface-sector masks select exactly their own octants without slices", () => {
  Object.assign(ctx.params, { earthCutLongitude: 0, showMeridian: false, showMeridian2: false, showEquator: false });
  const keys = ["N", "S"].flatMap(h => [1, 2, 3, 4].map(i => `earthSector${h}${i}`));
  for (let bits = 0; bits < 256; bits++) {
    keys.forEach((key, i) => ctx.params[key] = Boolean(bits & (1 << i)));
    const clip = ctx.getSurfaceClipOptions("earth");
    for (let i = 0; i < 8; i++) {
      const theta = i < 4 ? Math.PI / 4 : 3 * Math.PI / 4;
      const phi = ((i % 4) + .5) * Math.PI / 2;
      assert.equal(ctx.shouldKeepSurfaceCellForClip(theta, phi, clip), Boolean(bits & (1 << i)));
    }
  }
  keys.forEach(key => ctx.params[key] = true);
  const full = mesh();
  ctx.params.earthSectorN1 = false;
  assert.equal(mesh(0, ctx.getSurfaceClipOptions("earth")).geometry.index.count, full.geometry.index.count * 7 / 8);
  keys.forEach(key => ctx.params[key] = false);
  assert.equal(mesh(0, ctx.getSurfaceClipOptions("earth")).geometry.index.count, 0);
});

test("surface sector masks and rotation are independent of every slice and of each other", () => {
  for (const slot of ["earth", "cmb"]) for (const h of ["N", "S"]) for (let i = 1; i <= 4; i++)
    ctx.params[`${slot}Sector${h}${i}`] = true;
  Object.assign(ctx.params, { earthCutLongitude: 315, earthSectorN1: false, cmbCutLongitude: 0 });
  const before = ctx.getSurfaceClipOptions("earth");
  assert.equal(ctx.shouldKeepSurfaceCellForClip(Math.PI / 4, 0, before), false);
  assert.equal(ctx.shouldKeepSurfaceCellForClip(3 * Math.PI / 4, 0, before), true);
  assert.equal(ctx.shouldKeepSurfaceCellForClip(Math.PI / 4, 0, ctx.getSurfaceClipOptions("cmb")), true);
  Object.assign(ctx.params, { showMeridian: true, showMeridian2: true, showEquator: true,
    meridianPhiDeg: 210, meridian2PhiDeg: 310, equator2Z: -.5, quarterN1: false,
    cmbSurfaceCut: "follow", earthSurfaceCut: "follow", cmbClipWithMeridian: true });
  assert.deepEqual(ctx.getSurfaceClipOptions("earth"), before);
});

test("custom underside uses an inward-facing colour with optional lighting, preserving the outer texture", () => {
  Object.assign(ctx.params, { earthUnderside: "custom", earthUndersideColor: "#2479ae", earthUndersideLighting: false });
  const m = mesh().material;
  assert.equal(m.side, THREE.DoubleSide);
  assert.ok(m.map, "outer image retained");
  const shader = { uniforms: {}, fragmentShader: THREE.ShaderLib.phong.fragmentShader };
  m.onBeforeCompile(shader);
  assert.equal(shader.uniforms.undersideColour.value.getHexString(), "2479ae");
  assert.equal(shader.uniforms.undersideLighting.value, false);
  assert.ok(shader.fragmentShader.includes("if (!gl_FrontFacing) diffuseColor.rgb = undersideColour"));
  assert.ok(shader.fragmentShader.includes("if (!gl_FrontFacing && !undersideLighting) outgoingLight = undersideColour"));
  ctx.params.earthUndersideLighting = true;
  const litShader = { uniforms: {}, fragmentShader: THREE.ShaderLib.phong.fragmentShader };
  mesh().material.onBeforeCompile(litShader);
  assert.equal(litShader.uniforms.undersideLighting.value, true);
  ctx.params.earthUnderside = "hidden";
  assert.equal(mesh().material.side, THREE.FrontSide);
  ctx.params.earthUnderside = "original";
  assert.equal(mesh().material.side, THREE.FrontSide);
});

test("gap filler can use a custom colour either lit or flat", () => {
  Object.assign(ctx.params, { sliceGapFillerColor: "#b57c53", sliceGapFillerLighting: false });
  const flat = ctx.makeGapFillerMaterial(.4);
  assert.equal(flat.type, "MeshBasicMaterial");
  assert.equal(flat.color.getHexString(), "b57c53");
  assert.equal(flat.opacity, .4);
  ctx.params.sliceGapFillerLighting = true;
  assert.equal(ctx.makeGapFillerMaterial(.4).type, "MeshPhongMaterial");
});


test("all eight sector checkboxes and underside colour/lighting are accessible; colour enables custom mode", () => {
  const controls = [], children = [];
  const folder = () => ({ domElement: { classList: { add() {} } }, addFolder() { const child = folder(); children.push(child); return child; },
    add(object, key) {
      const c = { object, key, name(label) { this.label = label; return this; },
        onChange(fn) { this.change = fn; return this; }, onFinishChange(fn) { this.finish = fn; return this; },
        updateDisplay() {}, domElement: {} };
      controls.push(c); return c;
    }, addColor(object, key) { return this.add(object, key); } });
  ctx.closeGuiFolder = () => {};
  Object.assign(ctx.params, { earthUnderside: "original", earthUndersideColor: "#888888", earthUndersideLighting: true });
  let builds = 0;
  ctx.addSurfaceAppearanceControls(folder(), "earth", () => builds++);
  assert.equal(controls.filter(c => /^earthSector[NS][1-4]$/.test(c.key)).length, 8);
  assert.ok(!controls.some(c => c.key === "earthSurfaceCut" || c.key === "earthCutWidth"));
  const colour = controls.find(c => c.key === "earthUndersideColor");
  const light = controls.find(c => c.key === "earthUndersideLighting");
  assert.ok(colour && light);
  colour.object[colour.key] = "#c86532"; colour.change();
  assert.equal(ctx.params.earthUnderside, "custom");
  ctx.params.earthUnderside = "hidden";
  light.object[light.key] = false; light.change();
  assert.equal(ctx.params.earthUnderside, "custom");
  assert.equal(ctx.params.earthUndersideLighting, false);
  assert.equal(builds, 2);
});
