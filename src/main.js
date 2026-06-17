import "./style.css";

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import GUI from "lil-gui";

const statusEl = document.getElementById("status");

const displaySlots = ["cmb", "icb", "equator", "equator2", "meridian"];
const displayNames = {
  cmb: "CMB",
  icb: "ICB",
  equator: "Equator 1",
  equator2: "Equator 2",
  meridian: "Meridian",
};

const colourbars = Object.fromEntries(
  displaySlots.map((id) => [
    id,
    {
      row: document.getElementById(`cb-row-${id}`),
      title: document.getElementById(`cb-${id}-title`),
      min: document.getElementById(`cb-${id}-min`),
      mid: document.getElementById(`cb-${id}-mid`),
      max: document.getElementById(`cb-${id}-max`),
      gradient: document.getElementById(`cb-${id}-gradient`),
    },
  ])
);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x050505);

const camera = new THREE.PerspectiveCamera(
  45,
  window.innerWidth / window.innerHeight,
  0.001,
  100.0
);
camera.position.set(0.0, -3.0, 1.35);

const renderer = new THREE.WebGLRenderer({
  antialias: true,
  powerPreference: "high-performance",
});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.target.set(0.0, 0.0, 0.0);

function resetCameraView() {
  camera.position.set(0.0, -3.0, 1.35);
  camera.up.set(0.0, 0.0, 1.0);
  controls.target.set(0.0, 0.0, 0.0);
  controls.update();
}

const ambientLight = new THREE.AmbientLight(0xffffff, 0.55);
scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 2.0);
directionalLight.position.set(2.0, -3.0, 4.0);
scene.add(directionalLight);

const axes = new THREE.AxesHelper(1.25);
axes.visible = false;
scene.add(axes);

const params = {
  cmbField: "Br",
  icbField: "Br",
  equatorField: "C",
  equator2Field: "C",
  meridianField: "C",

  showCMB: true,
  showICB: true,
  showEquator: true,
  showEquator2: false,
  showMeridian: false,
  showFieldLines: true,
  fieldLineDisplay: "shell",
  showAxes: false,

  meridianPhiDeg: 0,
  equator2Z: 0.25,
  cmbClipWithMeridian: true,
  cmbRearSide: "positive",

  cmbOpacity: 0.82,
  icbOpacity: 0.72,
  equatorOpacity: 1.0,
  equator2Opacity: 1.0,
  meridianOpacity: 1.0,

  cmbScale: "symmetric",
  cmbMin: -1.0,
  cmbMax: 1.0,
  icbScale: "symmetric",
  icbMin: -1.0,
  icbMax: 1.0,
  equatorScale: "symmetric",
  equatorMin: -1.0,
  equatorMax: 1.0,
  equator2Scale: "symmetric",
  equator2Min: -1.0,
  equator2Max: 1.0,
  meridianScale: "symmetric",
  meridianMin: -1.0,
  meridianMax: 1.0,

  cmbColormap: "blue-white-red",
  icbColormap: "blue-white-red",
  equatorColormap: "blue-white-red",
  equator2Colormap: "blue-white-red",
  meridianColormap: "blue-white-red",

  lineStride: 3,

  resetCamera: () => resetCameraView(),
};

let metadata = null;
let coords = { r: null, theta: null, phi: null };

let cmbMesh = null;
let icbMesh = null;
let equatorMesh = null;
let equator2Mesh = null;
let meridianMesh = null;
let fieldLineGroups = { shell: null, exterior: null };
const fieldLineDataCache = new Map();

const dataCache = new Map();

function setStatus(text) {
  statusEl.textContent = text;
}

function formatNumber(x) {
  if (!Number.isFinite(x)) return "NaN";
  const ax = Math.abs(x);
  if (ax >= 1000 || (ax > 0 && ax < 1.0e-3)) return x.toExponential(2);
  return x.toFixed(3);
}

function setColourbarForSlot(slot, fieldName, vmin, vmax) {
  const bar = colourbars[slot];
  if (!bar) return;

  const mid = 0.5 * (vmin + vmax);
  const cmap = params[`${slot}Colormap`] || "blue-white-red";
  bar.title.textContent = `${displayNames[slot]}: ${fieldName}`;
  bar.min.textContent = formatNumber(vmin);
  if (bar.mid) bar.mid.textContent = formatNumber(mid);
  bar.max.textContent = formatNumber(vmax);
  if (bar.gradient) bar.gradient.style.background = colourbarCssGradient(cmap);
  bar.row.style.display = "block";
}

function hideColourbarForSlot(slot) {
  const bar = colourbars[slot];
  if (bar) bar.row.style.display = "none";
}

async function loadMetadata() {
  const response = await fetch("/data/metadata.json");
  if (!response.ok) {
    throw new Error("Could not load /data/metadata.json. Run: npm run make-data or convert a state file.");
  }
  return await response.json();
}

async function loadCoordinates() {
  coords = { r: null, theta: null, phi: null };

  if (!metadata?.coordinates) return;

  const response = await fetch(`/data/${metadata.coordinates}`);
  if (!response.ok) {
    console.warn(`Could not load /data/${metadata.coordinates}; falling back to uniform coordinates.`);
    return;
  }

  const raw = await response.json();
  coords.r = Array.isArray(raw.r) ? raw.r : null;
  coords.theta = Array.isArray(raw.theta) ? raw.theta : null;
  coords.phi = Array.isArray(raw.phi) ? raw.phi : null;
}

async function loadFloat32(filename, expectedLength) {
  if (dataCache.has(filename)) return dataCache.get(filename);

  const response = await fetch(`/data/${filename}`);
  if (!response.ok) throw new Error(`Could not load /data/${filename}`);

  const buffer = await response.arrayBuffer();
  const arr = new Float32Array(buffer);

  if (arr.length !== expectedLength) {
    console.warn(
      `Unexpected array length for ${filename}: got ${arr.length}, expected ${expectedLength}`
    );
  }

  dataCache.set(filename, arr);
  return arr;
}

async function loadField(fieldName) {
  const filename = metadata.fields[fieldName];
  if (!filename) throw new Error(`Field not found: ${fieldName}`);
  const expectedLength = metadata.nr * metadata.ntheta * metadata.nphi;
  return await loadFloat32(filename, expectedLength);
}

async function loadCmbDisplayField(fieldName) {
  const surfaceInfo = metadata.surface_fields?.[fieldName];

  if (surfaceInfo) {
    if (surfaceInfo.surface !== "cmb") {
      throw new Error(`Surface field ${fieldName} is not a CMB field.`);
    }

    const expectedLength = metadata.ntheta * metadata.nphi;
    const data = await loadFloat32(surfaceInfo.file, expectedLength);
    return { kind: "cmb_surface", name: fieldName, data };
  }

  const data = await loadField(fieldName);
  return { kind: "volume", name: fieldName, data };
}

function cmbValue(fieldObject, radiusIndex, it, ip) {
  if (fieldObject.kind === "cmb_surface") {
    return fieldObject.data[it * metadata.nphi + ip];
  }
  return fieldObject.data[idx(radiusIndex, it, ip)];
}

function idx(ir, it, ip) {
  return (ir * metadata.ntheta + it) * metadata.nphi + ip;
}

function clamp(x, a, b) {
  return Math.max(a, Math.min(b, x));
}

function radiusAtIndex(ir) {
  if (coords.r && coords.r.length === metadata.nr) return coords.r[ir];
  return metadata.r_inner + ((metadata.r_outer - metadata.r_inner) * ir) / (metadata.nr - 1);
}

function thetaAtIndex(it) {
  if (coords.theta && coords.theta.length === metadata.ntheta) return coords.theta[it];
  return (Math.PI * it) / (metadata.ntheta - 1);
}

function phiAtIndex(ip) {
  if (coords.phi && coords.phi.length === metadata.nphi) return coords.phi[ip];
  return (2.0 * Math.PI * ip) / metadata.nphi;
}

function nearestThetaIndex(theta) {
  let best = 0;
  let bestDist = Infinity;

  for (let it = 0; it < metadata.ntheta; it++) {
    const d = Math.abs(thetaAtIndex(it) - theta);
    if (d < bestDist) {
      bestDist = d;
      best = it;
    }
  }

  return best;
}

function nearestRadiusIndex(radius) {
  let best = 0;
  let bestDist = Infinity;

  for (let ir = 0; ir < metadata.nr; ir++) {
    const d = Math.abs(radiusAtIndex(ir) - radius);
    if (d < bestDist) {
      bestDist = d;
      best = ir;
    }
  }

  return best;
}

function angularDistance(a, b) {
  const twoPi = 2.0 * Math.PI;
  return Math.abs(((a - b + Math.PI) % twoPi + twoPi) % twoPi - Math.PI);
}

function nearestPhiIndex(phi) {
  const twoPi = 2.0 * Math.PI;
  const target = ((phi % twoPi) + twoPi) % twoPi;

  let best = 0;
  let bestDist = Infinity;

  for (let ip = 0; ip < metadata.nphi; ip++) {
    const d = angularDistance(phiAtIndex(ip), target);
    if (d < bestDist) {
      bestDist = d;
      best = ip;
    }
  }

  return best;
}

function rawMinMaxFromSamples(field, sampleIndexGenerator) {
  let vmin = Infinity;
  let vmax = -Infinity;

  for (const [ir, it, ip] of sampleIndexGenerator()) {
    const v = field[idx(ir, it, ip)];
    if (!Number.isFinite(v)) continue;
    if (v < vmin) vmin = v;
    if (v > vmax) vmax = v;
  }

  if (!Number.isFinite(vmin) || !Number.isFinite(vmax)) return [-1.0, 1.0];
  if (vmin === vmax) {
    const pad = Math.max(Math.abs(vmin) * 0.01, 1.0e-12);
    return [vmin - pad, vmax + pad];
  }
  return [vmin, vmax];
}

function applyScale(slot, rawMin, rawMax) {
  const scale = params[`${slot}Scale`];

  if (scale === "manual") {
    let vmin = Number(params[`${slot}Min`]);
    let vmax = Number(params[`${slot}Max`]);
    if (!Number.isFinite(vmin) || !Number.isFinite(vmax) || vmin === vmax) {
      [vmin, vmax] = [rawMin, rawMax];
    }
    if (vmin > vmax) [vmin, vmax] = [vmax, vmin];
    return [vmin, vmax];
  }

  if (scale === "symmetric") {
    const a = Math.max(Math.abs(rawMin), Math.abs(rawMax), 1.0e-12);
    return [-a, a];
  }

  return [rawMin, rawMax];
}

function surfaceRange(field, radiusIndex, slot) {
  const raw = rawMinMaxFromSamples(field, function* () {
    for (let it = 0; it < metadata.ntheta; it++) {
      for (let ip = 0; ip < metadata.nphi; ip++) yield [radiusIndex, it, ip];
    }
  });
  return applyScale(slot, raw[0], raw[1]);
}

function cmbDisplayRange(fieldObject, radiusIndex, slot) {
  let raw;

  if (fieldObject.kind === "cmb_surface") {
    let vmin = Infinity;
    let vmax = -Infinity;

    for (let it = 0; it < metadata.ntheta; it++) {
      for (let ip = 0; ip < metadata.nphi; ip++) {
        const v = cmbValue(fieldObject, radiusIndex, it, ip);
        if (!Number.isFinite(v)) continue;
        if (v < vmin) vmin = v;
        if (v > vmax) vmax = v;
      }
    }

    raw = Number.isFinite(vmin) && Number.isFinite(vmax) ? [vmin, vmax] : [-1.0, 1.0];
    if (raw[0] === raw[1]) {
      const pad = Math.max(Math.abs(raw[0]) * 0.01, 1.0e-12);
      raw = [raw[0] - pad, raw[1] + pad];
    }
  } else {
    raw = rawMinMaxFromSamples(fieldObject.data, function* () {
      for (let it = 0; it < metadata.ntheta; it++) {
        for (let ip = 0; ip < metadata.nphi; ip++) yield [radiusIndex, it, ip];
      }
    });
  }

  return applyScale(slot, raw[0], raw[1]);
}

function equatorRange(field, slot) {
  const it = nearestThetaIndex(0.5 * Math.PI);
  const raw = rawMinMaxFromSamples(field, function* () {
    for (let ir = 0; ir < metadata.nr; ir++) {
      for (let ip = 0; ip < metadata.nphi; ip++) yield [ir, it, ip];
    }
  });
  return applyScale(slot, raw[0], raw[1]);
}

function meridianRange(field, phiDeg, slot) {
  const phi0 = THREE.MathUtils.degToRad(phiDeg);
  const ip0 = nearestPhiIndex(phi0);
  const ip1 = nearestPhiIndex(phi0 + Math.PI);
  const raw = rawMinMaxFromSamples(field, function* () {
    for (const ip of [ip0, ip1]) {
      for (let ir = 0; ir < metadata.nr; ir++) {
        for (let it = 0; it < metadata.ntheta; it++) yield [ir, it, ip];
      }
    }
  });
  return applyScale(slot, raw[0], raw[1]);
}

const colourStops = {
  "blue-white-red": [
    [0.0, [40, 60, 180]],
    [0.5, [255, 255, 255]],
    [1.0, [180, 40, 40]],
  ],
  "red-white-blue": [
    [0.0, [180, 40, 40]],
    [0.5, [255, 255, 255]],
    [1.0, [40, 60, 180]],
  ],
  viridis: [
    [0.0, [68, 1, 84]],
    [0.25, [59, 82, 139]],
    [0.5, [33, 145, 140]],
    [0.75, [94, 201, 98]],
    [1.0, [253, 231, 37]],
  ],
  plasma: [
    [0.0, [13, 8, 135]],
    [0.25, [126, 3, 168]],
    [0.5, [204, 71, 120]],
    [0.75, [248, 149, 64]],
    [1.0, [240, 249, 33]],
  ],
  inferno: [
    [0.0, [0, 0, 4]],
    [0.25, [87, 15, 109]],
    [0.5, [187, 55, 84]],
    [0.75, [249, 142, 8]],
    [1.0, [252, 255, 164]],
  ],
  gray: [
    [0.0, [20, 20, 20]],
    [1.0, [245, 245, 245]],
  ],
};

const colourMapNames = Object.keys(colourStops);

function interpolateStops(t, stops) {
  const x = clamp(t, 0.0, 1.0);
  for (let i = 0; i < stops.length - 1; i++) {
    const [t0, c0] = stops[i];
    const [t1, c1] = stops[i + 1];
    if (x >= t0 && x <= t1) {
      const q = (x - t0) / (t1 - t0 || 1.0);
      return [
        c0[0] + q * (c1[0] - c0[0]),
        c0[1] + q * (c1[1] - c0[1]),
        c0[2] + q * (c1[2] - c0[2]),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

function colourMap(value, vmin, vmax, scheme = "blue-white-red") {
  const t = clamp((value - vmin) / (vmax - vmin || 1.0), 0.0, 1.0);
  const stops = colourStops[scheme] || colourStops["blue-white-red"];
  const rgb = interpolateStops(t, stops);
  return new THREE.Color(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0);
}

function colourbarCssGradient(scheme = "blue-white-red") {
  const stops = colourStops[scheme] || colourStops["blue-white-red"];
  const parts = stops.map(([t, rgb]) => `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]}) ${100 * t}%`);
  return `linear-gradient(to right, ${parts.join(", ")})`;
}

function makeSurfaceMesh(field, radiusIndex, opacity, vmin, vmax, colormap) {
  const nt = metadata.ntheta;
  const np = metadata.nphi;
  const r = radiusAtIndex(radiusIndex);

  const positions = [];
  const colors = [];
  const indices = [];

  for (let it = 0; it < nt; it++) {
    const theta = thetaAtIndex(it);

    for (let ip = 0; ip < np; ip++) {
      const phi = phiAtIndex(ip);

      positions.push(
        r * Math.sin(theta) * Math.cos(phi),
        r * Math.sin(theta) * Math.sin(phi),
        r * Math.cos(theta)
      );

      const val = field[idx(radiusIndex, it, ip)];
      const col = colourMap(val, vmin, vmax, colormap);
      colors.push(col.r, col.g, col.b);
    }
  }

  for (let it = 0; it < nt - 1; it++) {
    for (let ip = 0; ip < np; ip++) {
      const ip1 = (ip + 1) % np;
      const a = it * np + ip;
      const b = it * np + ip1;
      const c = (it + 1) * np + ip;
      const d = (it + 1) * np + ip1;
      indices.push(a, c, b, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  const material = new THREE.MeshPhongMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    transparent: opacity < 1.0,
    opacity,
    shininess: 8,
    depthWrite: opacity >= 0.95,
  });

  return new THREE.Mesh(geometry, material);
}

function makeCmbSurfaceMesh(fieldObject, radiusIndex, opacity, vmin, vmax, colormap, clipOptions = null) {
  const nt = metadata.ntheta;
  const np = metadata.nphi;
  const r = radiusAtIndex(radiusIndex);

  const positions = [];
  const colors = [];
  const indices = [];

  for (let it = 0; it < nt; it++) {
    const theta = thetaAtIndex(it);

    for (let ip = 0; ip < np; ip++) {
      const phi = phiAtIndex(ip);

      positions.push(
        r * Math.sin(theta) * Math.cos(phi),
        r * Math.sin(theta) * Math.sin(phi),
        r * Math.cos(theta)
      );

      const val = cmbValue(fieldObject, radiusIndex, it, ip);
      const col = colourMap(val, vmin, vmax, colormap);
      colors.push(col.r, col.g, col.b);
    }
  }

  for (let it = 0; it < nt - 1; it++) {
    for (let ip = 0; ip < np; ip++) {
      const ip1 = (ip + 1) % np;

      if (clipOptions?.enabled) {
        const phiMid = phiAtIndex(ip);
        const sideValue = Math.sin(phiMid - clipOptions.phi0);
        const keep = clipOptions.side === "negative" ? sideValue < 0.0 : sideValue > 0.0;
        if (!keep) continue;
      }

      const a = it * np + ip;
      const b = it * np + ip1;
      const c = (it + 1) * np + ip;
      const d = (it + 1) * np + ip1;
      indices.push(a, c, b, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  const material = new THREE.MeshPhongMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    transparent: opacity < 1.0,
    opacity,
    shininess: 8,
    depthWrite: opacity >= 0.95,
  });

  return new THREE.Mesh(geometry, material);
}

function sampleFieldNearest(field, radius, theta, phi) {
  const rOuter = metadata.r_outer;
  const rInner = metadata.r_inner;
  if (radius < rInner || radius > rOuter) return NaN;

  const ir = nearestRadiusIndex(radius);
  const it = nearestThetaIndex(theta);
  const ip = nearestPhiIndex(phi);
  return field[idx(ir, it, ip)];
}

function horizontalSliceRawRange(field, z) {
  const nr = metadata.nr;
  const np = metadata.nphi;
  const rInner = metadata.r_inner;
  const rOuter = metadata.r_outer;
  const zAbs = Math.abs(z);

  if (zAbs >= rOuter) return [-1.0, 1.0];

  const sMin = zAbs < rInner ? Math.sqrt(Math.max(0.0, rInner * rInner - z * z)) : 0.0;
  const sMax = Math.sqrt(Math.max(0.0, rOuter * rOuter - z * z));

  let vmin = Infinity;
  let vmax = -Infinity;

  for (let is = 0; is < nr; is++) {
    const s = sMin + ((sMax - sMin) * is) / Math.max(1, nr - 1);
    const radius = Math.sqrt(s * s + z * z);
    const theta = radius > 0 ? Math.acos(clamp(z / radius, -1.0, 1.0)) : 0.5 * Math.PI;

    for (let ip = 0; ip < np; ip++) {
      const phi = phiAtIndex(ip);
      const v = sampleFieldNearest(field, radius, theta, phi);
      if (!Number.isFinite(v)) continue;
      if (v < vmin) vmin = v;
      if (v > vmax) vmax = v;
    }
  }

  if (!Number.isFinite(vmin) || !Number.isFinite(vmax)) return [-1.0, 1.0];
  if (vmin === vmax) {
    const pad = Math.max(Math.abs(vmin) * 0.01, 1.0e-12);
    return [vmin - pad, vmax + pad];
  }
  return [vmin, vmax];
}

function horizontalSliceRange(field, z, slot) {
  const raw = horizontalSliceRawRange(field, z);
  return applyScale(slot, raw[0], raw[1]);
}

function makeHorizontalSliceMesh(field, z, opacity, vmin, vmax, colormap) {
  const nr = metadata.nr;
  const np = metadata.nphi;
  const rInner = metadata.r_inner;
  const rOuter = metadata.r_outer;
  const zAbs = Math.abs(z);

  const positions = [];
  const colors = [];
  const indices = [];

  if (zAbs >= rOuter) {
    return new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  }

  const sMin = zAbs < rInner ? Math.sqrt(Math.max(0.0, rInner * rInner - z * z)) : 0.0;
  const sMax = Math.sqrt(Math.max(0.0, rOuter * rOuter - z * z));

  for (let is = 0; is < nr; is++) {
    const s = sMin + ((sMax - sMin) * is) / Math.max(1, nr - 1);
    const radius = Math.sqrt(s * s + z * z);
    const theta = radius > 0 ? Math.acos(clamp(z / radius, -1.0, 1.0)) : 0.5 * Math.PI;

    for (let ip = 0; ip < np; ip++) {
      const phi = phiAtIndex(ip);
      positions.push(s * Math.cos(phi), s * Math.sin(phi), z);

      const val = sampleFieldNearest(field, radius, theta, phi);
      const col = colourMap(val, vmin, vmax, colormap);
      colors.push(col.r, col.g, col.b);
    }
  }

  for (let is = 0; is < nr - 1; is++) {
    for (let ip = 0; ip < np; ip++) {
      const ip1 = (ip + 1) % np;
      const a = is * np + ip;
      const b = is * np + ip1;
      const c = (is + 1) * np + ip;
      const d = (is + 1) * np + ip1;
      indices.push(a, c, b, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);

  const material = new THREE.MeshBasicMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    transparent: opacity < 1.0,
    opacity,
    depthWrite: opacity >= 0.95,
  });

  return new THREE.Mesh(geometry, material);
}

function makeMeridionalSliceMesh(field, phiDeg, opacity, vmin, vmax, colormap) {
  const nr = metadata.nr;
  const nt = metadata.ntheta;
  const requestedPhi = THREE.MathUtils.degToRad(phiDeg);

  const positions = [];
  const colors = [];
  const indices = [];

  function appendSide(phiWanted) {
    const ip = nearestPhiIndex(phiWanted);
    const phi = phiAtIndex(ip);
    const offset = positions.length / 3;

    for (let ir = 0; ir < nr; ir++) {
      const r = radiusAtIndex(ir);

      for (let it = 0; it < nt; it++) {
        const theta = thetaAtIndex(it);

        positions.push(
          r * Math.sin(theta) * Math.cos(phi),
          r * Math.sin(theta) * Math.sin(phi),
          r * Math.cos(theta)
        );

        const val = field[idx(ir, it, ip)];
        const col = colourMap(val, vmin, vmax, colormap);
        colors.push(col.r, col.g, col.b);
      }
    }

    for (let ir = 0; ir < nr - 1; ir++) {
      for (let it = 0; it < nt - 1; it++) {
        const a = offset + ir * nt + it;
        const b = offset + ir * nt + it + 1;
        const c = offset + (ir + 1) * nt + it;
        const d = offset + (ir + 1) * nt + it + 1;
        indices.push(a, c, b, b, c, d);
      }
    }
  }

  appendSide(requestedPhi);
  appendSide(requestedPhi + Math.PI);

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  geometry.setIndex(indices);

  const material = new THREE.MeshBasicMaterial({
    vertexColors: true,
    side: THREE.DoubleSide,
    transparent: opacity < 1.0,
    opacity,
    depthWrite: opacity >= 0.95,
  });

  return new THREE.Mesh(geometry, material);
}

function disposeObject(obj) {
  if (!obj) return;

  if (obj.geometry) obj.geometry.dispose();

  if (obj.material) {
    if (Array.isArray(obj.material)) {
      for (const mat of obj.material) mat.dispose();
    } else {
      obj.material.dispose();
    }
  }

  scene.remove(obj);
}

function disposeFieldLineGroups() {
  const groupsToDispose = [];

  for (const key of Object.keys(fieldLineGroups)) {
    if (fieldLineGroups[key]) groupsToDispose.push(fieldLineGroups[key]);
    fieldLineGroups[key] = null;
  }

  // Defensive cleanup: remove any old line group that might have been left in
  // the scene by an earlier version or a reload. This fixes the case where
  // lines remain visible after the GUI toggle is switched off.
  scene.traverse((obj) => {
    if (obj.userData?.isMagneticFieldLineGroup && !groupsToDispose.includes(obj)) {
      groupsToDispose.push(obj);
    }
  });

  for (const group of groupsToDispose) {
    const materials = new Set();
    group.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      if (obj.material) {
        if (Array.isArray(obj.material)) {
          for (const mat of obj.material) materials.add(mat);
        } else {
          materials.add(obj.material);
        }
      }
    });
    for (const mat of materials) mat.dispose?.();
    scene.remove(group);
  }
}

function setStatusSummary(lastFieldName = null) {
  const title = metadata.title ? `${metadata.title} | ` : "";
  const sim = metadata.magnetic?.classification ? `${metadata.magnetic.classification} | ` : "";
  const shownMap = {shell: "shell/internal", exterior: "exterior potential/poloidal", both: "both"};
  const lineMode = metadata.field_lines?.mode ? `B lines=${metadata.field_lines.mode}, shown=${shownMap[params.fieldLineDisplay] || params.fieldLineDisplay} | ` : "";
  const fieldText = `CMB=${params.cmbField}, ICB=${params.icbField}, Eq1=${params.equatorField}, Eq2=${params.equator2Field}, Mer=${params.meridianField}`;
  const changed = lastFieldName ? ` | updated=${lastFieldName}` : "";
  setStatus(`${title}${sim}${lineMode}${fieldText}${changed} | grid ${metadata.nr} x ${metadata.ntheta} x ${metadata.nphi}`);
}

async function rebuildCMB() {
  disposeObject(cmbMesh);
  cmbMesh = null;

  const fieldObject = await loadCmbDisplayField(params.cmbField);
  const [vmin, vmax] = cmbDisplayRange(fieldObject, metadata.nr - 1, "cmb");
  setColourbarForSlot("cmb", params.cmbField, vmin, vmax);

  const cmbClip = {
    enabled: params.cmbClipWithMeridian && params.showMeridian,
    phi0: THREE.MathUtils.degToRad(params.meridianPhiDeg),
    side: params.cmbRearSide,
  };
  cmbMesh = makeCmbSurfaceMesh(fieldObject, metadata.nr - 1, params.cmbOpacity, vmin, vmax, params.cmbColormap, cmbClip);
  cmbMesh.visible = params.showCMB;
  scene.add(cmbMesh);
  setStatusSummary(`CMB:${params.cmbField}`);
}

async function rebuildICB() {
  disposeObject(icbMesh);
  icbMesh = null;

  if (!metadata.has_inner_core) {
    hideColourbarForSlot("icb");
    return;
  }

  const field = await loadField(params.icbField);
  const [vmin, vmax] = surfaceRange(field, 0, "icb");
  setColourbarForSlot("icb", params.icbField, vmin, vmax);

  icbMesh = makeSurfaceMesh(field, 0, params.icbOpacity, vmin, vmax, params.icbColormap);
  icbMesh.visible = params.showICB;
  scene.add(icbMesh);
  setStatusSummary(`ICB:${params.icbField}`);
}

async function rebuildEquator() {
  disposeObject(equatorMesh);
  equatorMesh = null;

  const field = await loadField(params.equatorField);
  const [vmin, vmax] = horizontalSliceRange(field, 0.0, "equator");
  setColourbarForSlot("equator", params.equatorField, vmin, vmax);

  equatorMesh = makeHorizontalSliceMesh(field, 0.0, params.equatorOpacity, vmin, vmax, params.equatorColormap);
  equatorMesh.visible = params.showEquator;
  scene.add(equatorMesh);
  setStatusSummary(`Equator:${params.equatorField}`);
}

async function rebuildEquator2() {
  disposeObject(equator2Mesh);
  equator2Mesh = null;

  const field = await loadField(params.equator2Field);
  const z = params.equator2Z * metadata.r_outer;
  const [vmin, vmax] = horizontalSliceRange(field, z, "equator2");
  setColourbarForSlot("equator2", params.equator2Field, vmin, vmax);

  equator2Mesh = makeHorizontalSliceMesh(field, z, params.equator2Opacity, vmin, vmax, params.equator2Colormap);
  equator2Mesh.visible = params.showEquator2;
  scene.add(equator2Mesh);
  setStatusSummary(`Equator2:${params.equator2Field}`);
}

async function rebuildMeridian() {
  disposeObject(meridianMesh);
  meridianMesh = null;

  const field = await loadField(params.meridianField);
  const [vmin, vmax] = meridianRange(field, params.meridianPhiDeg, "meridian");
  setColourbarForSlot("meridian", params.meridianField, vmin, vmax);

  meridianMesh = makeMeridionalSliceMesh(
    field,
    params.meridianPhiDeg,
    params.meridianOpacity,
    vmin,
    vmax,
    params.meridianColormap
  );
  meridianMesh.visible = params.showMeridian;
  scene.add(meridianMesh);
  setStatusSummary(`Meridian:${params.meridianField}`);
}

async function rebuildAllMeshes() {
  setStatus("Loading selected fields...");
  await rebuildCMB();
  await rebuildICB();
  await rebuildEquator();
  await rebuildEquator2();
  await rebuildMeridian();
  updateVisibility();
  setStatusSummary();
}

function updateVisibility() {
  if (cmbMesh) cmbMesh.visible = params.showCMB;
  if (icbMesh) icbMesh.visible = params.showICB;
  if (equatorMesh) equatorMesh.visible = params.showEquator;
  if (equator2Mesh) equator2Mesh.visible = params.showEquator2;
  if (meridianMesh) meridianMesh.visible = params.showMeridian;

  if (colourbars.cmb?.row) colourbars.cmb.row.style.display = params.showCMB && cmbMesh ? "block" : "none";
  if (colourbars.icb?.row) colourbars.icb.row.style.display = params.showICB && icbMesh ? "block" : "none";
  if (colourbars.equator?.row) colourbars.equator.row.style.display = params.showEquator && equatorMesh ? "block" : "none";
  if (colourbars.equator2?.row) colourbars.equator2.row.style.display = params.showEquator2 && equator2Mesh ? "block" : "none";
  if (colourbars.meridian?.row) colourbars.meridian.row.style.display = params.showMeridian && meridianMesh ? "block" : "none";
  if (!params.showFieldLines) {
    disposeFieldLineGroups();
  } else {
    const requested = params.fieldLineDisplay;
    for (const [mode, group] of Object.entries(fieldLineGroups)) {
      if (!group) continue;
      group.visible = requested === "both" || requested === mode;
    }
  }
  axes.visible = params.showAxes;
}

function updateOpacities() {
  if (cmbMesh) {
    cmbMesh.material.opacity = params.cmbOpacity;
    cmbMesh.material.transparent = params.cmbOpacity < 1.0;
  }

  if (icbMesh) {
    icbMesh.material.opacity = params.icbOpacity;
    icbMesh.material.transparent = params.icbOpacity < 1.0;
  }

  if (equatorMesh) {
    equatorMesh.material.opacity = params.equatorOpacity;
    equatorMesh.material.transparent = params.equatorOpacity < 1.0;
  }

  if (equator2Mesh) {
    equator2Mesh.material.opacity = params.equator2Opacity;
    equator2Mesh.material.transparent = params.equator2Opacity < 1.0;
  }

  if (meridianMesh) {
    meridianMesh.material.opacity = params.meridianOpacity;
    meridianMesh.material.transparent = params.meridianOpacity < 1.0;
  }
}

async function fetchFieldLineFile(filename) {
  if (!filename) return [];

  if (fieldLineDataCache.has(filename)) {
    return fieldLineDataCache.get(filename);
  }

  const response = await fetch(`/data/${filename}`);
  if (!response.ok) {
    console.warn(`Could not load field lines: ${filename}`);
    return [];
  }

  const lines = await response.json();
  fieldLineDataCache.set(filename, lines);
  return lines;
}

function inferLineType(line) {
  const region = String(line.region || "").toLowerCase();
  const mode = String(line.mode || "").toLowerCase();

  if (region.includes("outside") || region.includes("exterior") || mode.includes("exterior")) {
    return "exterior";
  }

  if (region.includes("fluid_shell") || region.includes("shell") || mode.includes("shell")) {
    return "shell";
  }

  return "unknown";
}

function getFieldLineFilename(mode) {
  const fl = metadata?.field_lines || {};

  if (mode === "shell") {
    return fl.shell || fl.B_lines_shell || fl.B_lines || fl.B_from_cmb || null;
  }

  if (mode === "exterior") {
    return fl.exterior_poloidal || fl.B_lines_exterior_poloidal || fl.exterior || fl.B_lines_exterior || fl.B_lines || fl.B_from_cmb || null;
  }

  return fl.B_lines || fl.B_from_cmb || null;
}

function getAvailableFieldLineModes() {
  const fl = metadata?.field_lines || {};
  const modes = [];

  if (fl.shell || fl.B_lines_shell || fl.mode === "shell" || fl.mode === "both") modes.push("shell");
  if (fl.exterior_poloidal || fl.B_lines_exterior_poloidal || fl.exterior || fl.B_lines_exterior || fl.mode === "exterior" || fl.mode === "both") modes.push("exterior");

  // Backward compatibility with older combined line files.
  if (modes.length === 0 && (fl.B_lines || fl.B_from_cmb)) {
    if (fl.mode === "exterior") modes.push("exterior");
    else modes.push("shell");
  }

  if (modes.length >= 2) modes.push("both");
  return modes;
}

async function loadLinesForMode(mode) {
  const filename = getFieldLineFilename(mode);
  if (!filename) return [];

  const lines = await fetchFieldLineFile(filename);

  // If shell and exterior are stored in separate files, no filtering is needed.
  const fl = metadata?.field_lines || {};
  const hasSeparateFiles = Boolean(fl.shell || fl.exterior || fl.exterior_poloidal || fl.B_lines_shell || fl.B_lines_exterior || fl.B_lines_exterior_poloidal);
  if (hasSeparateFiles) return lines;

  // Otherwise filter older combined files by per-line metadata if possible.
  const typed = lines.filter((line) => inferLineType(line) === mode);
  return typed.length > 0 ? typed : lines;
}

function makeFieldLineGroup(lines, mode) {
  const group = new THREE.Group();
  group.name = `magnetic-field-lines-${mode}`;
  group.userData.isMagneticFieldLineGroup = true;
  group.userData.lineMode = mode;

  const positiveMaterial = new THREE.LineBasicMaterial({
    color: mode === "exterior" ? 0xfff0a0 : 0xffd080,
    transparent: true,
    opacity: mode === "exterior" ? 0.72 : 0.90,
  });

  const negativeMaterial = new THREE.LineBasicMaterial({
    color: mode === "exterior" ? 0x80e0ff : 0x80c0ff,
    transparent: true,
    opacity: mode === "exterior" ? 0.72 : 0.90,
  });

  const stride = Math.max(1, params.lineStride);
  for (let i = 0; i < lines.length; i += stride) {
    const line = lines[i];
    if (!Array.isArray(line.points) || line.points.length < 2) continue;

    const points = line.points.map((p) => new THREE.Vector3(p[0], p[1], p[2]));
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = line.polarity >= 0 ? positiveMaterial : negativeMaterial;
    const object = new THREE.Line(geometry, material);
    object.userData.lineMode = mode;
    group.add(object);
  }

  return group;
}

async function loadFieldLines() {
  disposeFieldLineGroups();

  if (!params.showFieldLines) {
    setStatusSummary();
    return;
  }

  const availableModes = getAvailableFieldLineModes();
  if (availableModes.length === 0) {
    setStatusSummary();
    return;
  }

  if (!availableModes.includes(params.fieldLineDisplay)) {
    params.fieldLineDisplay = availableModes[0];
  }

  const modesToLoad = params.fieldLineDisplay === "both" ? ["shell", "exterior"] : [params.fieldLineDisplay];

  for (const mode of modesToLoad) {
    if (!availableModes.includes(mode)) continue;

    const lines = await loadLinesForMode(mode);
    const group = makeFieldLineGroup(lines, mode);
    group.visible = params.showFieldLines;
    fieldLineGroups[mode] = group;
    scene.add(group);
  }

  setStatusSummary();
}

function onFieldLineVisibilityChanged() {
  if (params.showFieldLines) {
    loadFieldLines();
  } else {
    disposeFieldLineGroups();
    setStatusSummary();
  }
}

function chooseField(preferredList, fallbackFields) {
  for (const name of preferredList) {
    if (fallbackFields.includes(name)) return name;
  }
  return fallbackFields[0];
}

function getVolumeFieldNames() {
  return Object.keys(metadata.fields || {});
}

function getCmbFieldNames() {
  const volumeFields = getVolumeFieldNames();
  const surfaceFields = Object.entries(metadata.surface_fields || {})
    .filter(([, info]) => info.surface === "cmb")
    .map(([name]) => name);

  return [...volumeFields, ...surfaceFields];
}

function applyDefaultFields() {
  const fields = Object.keys(metadata.fields);
  if (fields.length === 0) throw new Error("metadata.fields is empty.");

  params.cmbField = chooseField(["Br", "Br_CMB_lmax10", "C", "Comp", "ur", "Uabs"], getCmbFieldNames());
  params.icbField = chooseField(["Br", "C", "Comp", "ur", "Uabs"], fields);
  params.equatorField = chooseField(["C", "Comp", "Br", "Uabs"], fields);
  params.equator2Field = chooseField(["C", "Comp", "Br", "Uabs"], fields);
  params.meridianField = chooseField(["C", "Comp", "Br", "Uabs"], fields);
}

function addDisplayControls(gui, slot, label, fieldParam, showParam, opacityParam, rebuildFn, availableFields) {
  const folder = gui.addFolder(label);

  folder.add(params, showParam).name("Show").onChange(() => { updateVisibility(); if (slot === "meridian") rebuildCMB(); });
  folder.add(params, fieldParam, availableFields).name("Field").onChange(rebuildFn);
  folder.add(params, `${slot}Scale`, ["symmetric", "minmax", "manual"]).name("Scale").onChange(rebuildFn);
  folder.add(params, `${slot}Colormap`, colourMapNames).name("Colour map").onChange(rebuildFn);
  folder.add(params, `${slot}Min`).name("Manual min").onChange(rebuildFn);
  folder.add(params, `${slot}Max`).name("Manual max").onChange(rebuildFn);
  folder.add(params, opacityParam, 0.0, 1.0, 0.01).name("Opacity").onChange(updateOpacities);

  return folder;
}

function buildGui() {
  const gui = new GUI({ title: "Controls" });

  gui.add(params, "resetCamera").name("Reset camera view");

  const volumeFields = getVolumeFieldNames();
  const cmbFields = getCmbFieldNames();

  const cmbFolder = addDisplayControls(gui, "cmb", "CMB surface", "cmbField", "showCMB", "cmbOpacity", rebuildCMB, cmbFields);
  const icbFolder = addDisplayControls(gui, "icb", "ICB surface", "icbField", "showICB", "icbOpacity", rebuildICB, volumeFields);
  const eqFolder = addDisplayControls(gui, "equator", "Equatorial slice 1", "equatorField", "showEquator", "equatorOpacity", rebuildEquator, volumeFields);
  const eq2Folder = addDisplayControls(gui, "equator2", "Equatorial slice 2", "equator2Field", "showEquator2", "equator2Opacity", rebuildEquator2, volumeFields);
  eq2Folder.add(params, "equator2Z", -0.95, 0.95, 0.01).name("z / r_o").onChange(rebuildEquator2);
  const merFolder = addDisplayControls(gui, "meridian", "Meridional slice", "meridianField", "showMeridian", "meridianOpacity", rebuildMeridian, volumeFields);
  merFolder.add(params, "meridianPhiDeg", 0, 360, 1).name("Longitude phi").onChange(() => { rebuildMeridian(); rebuildCMB(); });
  merFolder.add(params, "cmbClipWithMeridian").name("Show rear CMB only").onChange(rebuildCMB);
  merFolder.add(params, "cmbRearSide", { Rear: "positive", Front: "negative" }).name("CMB side").onChange(rebuildCMB);

  const other = gui.addFolder("Other visualisation");
  const lineModes = getAvailableFieldLineModes();
  if (lineModes.length > 0) {
    if (!lineModes.includes(params.fieldLineDisplay)) params.fieldLineDisplay = lineModes[0];
    other.add(params, "showFieldLines").name("Magnetic field lines").onChange(onFieldLineVisibilityChanged);
    const lineModeOptions = {}
    if (lineModes.includes("shell")) lineModeOptions["Shell/internal"] = "shell";
    if (lineModes.includes("exterior")) lineModeOptions["Exterior potential/poloidal"] = "exterior";
    if (lineModes.includes("both")) lineModeOptions["Both"] = "both";
    other.add(params, "fieldLineDisplay", lineModeOptions).name("Line type").onChange(loadFieldLines);
    other.add(params, "lineStride", 1, 10, 1).name("Line stride").onChange(loadFieldLines);
  } else {
    params.showFieldLines = false;
  }
  other.add(params, "showAxes").name("Axes").onChange(updateVisibility);

  cmbFolder.open();
  eqFolder.open();
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

async function init() {
  try {
    setStatus("Loading metadata...");
    metadata = await loadMetadata();
    await loadCoordinates();

    applyDefaultFields();
    buildGui();

    await rebuildAllMeshes();
    await loadFieldLines();

    animate();
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`);
  }
}

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
});

init();
