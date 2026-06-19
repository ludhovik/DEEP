import "./style.css";

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import GUI from "lil-gui";

const statusEl = document.getElementById("status");
const exportMessageEl = document.getElementById("export-message");

const displaySlots = ["cmb", "icb", "equator", "equator2", "meridian", "meridian2"];
const displayNames = {
  cmb: "CMB",
  icb: "ICB",
  equator: "Equator 1",
  equator2: "Equator 2",
  meridian: "Meridian 1",
  meridian2: "Meridian 2",
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
  preserveDrawingBuffer: true,
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
scene.add(directionalLight);

function updateLighting() {
  ambientLight.intensity = Number(params.ambientIntensity);
  directionalLight.intensity = Number(params.directionalIntensity);
  const az = THREE.MathUtils.degToRad(Number(params.lightAzimuthDeg));
  const el = THREE.MathUtils.degToRad(Number(params.lightElevationDeg));
  const rho = 5.0;
  directionalLight.position.set(
    rho * Math.cos(el) * Math.cos(az),
    rho * Math.cos(el) * Math.sin(az),
    rho * Math.sin(el)
  );
}

const axes = new THREE.AxesHelper(1.25);
axes.visible = false;
scene.add(axes);

const params = {
  cmbField: "Br",
  icbField: "Br",
  equatorField: "C",
  equator2Field: "C",
  meridianField: "C",
  meridian2Field: "C",

  showCMB: true,
  showICB: true,
  showEquator: true,
  showEquator2: false,
  showMeridian: false,
  showMeridian2: false,
  showFieldLines: true,
  fieldLineDisplay: "shell",
  showAxes: false,

  meridianPhiDeg: 0,
  meridian2PhiDeg: 90,
  equator2Z: 0.25,
  cmbClipWithMeridian: true,
  cmbClipMode: "rear-half",
  cmbRearSide: "positive",

  ambientIntensity: 0.55,
  directionalIntensity: 2.0,
  lightAzimuthDeg: 304,
  lightElevationDeg: 48,

  cmbOpacity: 0.82,
  icbOpacity: 0.72,
  equatorOpacity: 1.0,
  equator2Opacity: 1.0,
  meridianOpacity: 1.0,
  meridian2Opacity: 1.0,

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
  meridian2Scale: "symmetric",
  meridian2Min: -1.0,
  meridian2Max: 1.0,

  cmbColormap: "blue-white-red",
  icbColormap: "blue-white-red",
  equatorColormap: "blue-white-red",
  equator2Colormap: "blue-white-red",
  meridianColormap: "blue-white-red",
  meridian2Colormap: "blue-white-red",

  lineStride: 3,

  cameraDistance: 3.29,
  cameraAzimuthDeg: -90,
  cameraElevationDeg: 24,
  cameraTargetX: 0.0,
  cameraTargetY: 0.0,
  cameraTargetZ: 0.0,
  cameraFovDeg: 45,
  applyCameraView: () => applyCameraViewFromParams(),
  captureCameraView: () => syncCameraParamsFromCamera(true),

  exportWidthPx: 2400,
  videoWidthPx: 1920,
  videoDurationSec: 8,
  videoFps: 30,
  videoRotationMode: "phi360",
  exportPngWhite: () => exportCurrentViewPNG(),
  exportPdfWhite: () => exportCurrentViewPDF(),
  recordFullRotation: () => startFullRotationRecording(),

  resetCamera: () => { resetCameraView(); syncCameraParamsFromCamera(true); },
};

let metadata = null;
let coords = { r: null, theta: null, phi: null };

let cmbMesh = null;
let icbMesh = null;
let equatorMesh = null;
let equator2Mesh = null;
let meridianMesh = null;
let meridian2Mesh = null;
let fieldLineGroups = { shell: null, exterior: null };
const fieldLineDataCache = new Map();

const dataCache = new Map();

const videoState = {
  active: false,
  recorder: null,
  chunks: [],
  startTime: 0,
  durationMs: 0,
  startAngle: 0,
  radiusXY: 0,
  zOffset: 0,
  radius: 0,
  polarAngle: 0,
  mode: "phi360",
  target: new THREE.Vector3(),
  startPosition: new THREE.Vector3(),
  previousRendererSize: new THREE.Vector2(),
  previousPixelRatio: 1,
  previousAspect: 1,
  resizedRenderer: false,
};

const cameraParamControllers = [];

function setStatus(text) {
  statusEl.textContent = text;
  setExportMessage(text);
}

function setExportMessage(text) {
  if (exportMessageEl) exportMessageEl.textContent = text;
}

function refreshCameraParamControllers() {
  for (const controller of cameraParamControllers) controller.updateDisplay();
}

function syncCameraParamsFromCamera(updateControllers = false) {
  const offset = camera.position.clone().sub(controls.target);
  const distance = Math.max(offset.length(), 1.0e-6);
  params.cameraDistance = distance;
  params.cameraAzimuthDeg = THREE.MathUtils.radToDeg(Math.atan2(offset.y, offset.x));
  params.cameraElevationDeg = THREE.MathUtils.radToDeg(Math.asin(clamp(offset.z / distance, -1.0, 1.0)));
  params.cameraTargetX = controls.target.x;
  params.cameraTargetY = controls.target.y;
  params.cameraTargetZ = controls.target.z;
  params.cameraFovDeg = camera.fov;
  if (updateControllers) refreshCameraParamControllers();
}

function applyCameraViewFromParams() {
  const distance = Math.max(0.05, Number(params.cameraDistance));
  const az = THREE.MathUtils.degToRad(Number(params.cameraAzimuthDeg));
  const el = THREE.MathUtils.degToRad(clamp(Number(params.cameraElevationDeg), -89.0, 89.0));
  const target = new THREE.Vector3(
    Number(params.cameraTargetX),
    Number(params.cameraTargetY),
    Number(params.cameraTargetZ)
  );

  controls.target.copy(target);
  camera.position.set(
    target.x + distance * Math.cos(el) * Math.cos(az),
    target.y + distance * Math.cos(el) * Math.sin(az),
    target.z + distance * Math.sin(el)
  );
  camera.up.set(0.0, 0.0, 1.0);
  camera.fov = clamp(Number(params.cameraFovDeg), 5.0, 120.0);
  camera.updateProjectionMatrix();
  controls.update();
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

const OPAQUE_OPACITY = 0.999;

function isEffectivelyOpaque(opacity) {
  return Number(opacity) >= OPAQUE_OPACITY;
}

function applyOpacityAndDepth(material, opacity) {
  const alpha = clamp(Number(opacity), 0.0, 1.0);
  const opaque = isEffectivelyOpaque(alpha);

  material.opacity = alpha;
  material.transparent = !opaque;
  material.depthTest = true;
  material.depthWrite = opaque;
  material.blending = opaque ? THREE.NoBlending : THREE.NormalBlending;
  material.needsUpdate = true;
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

function normalizePhi(phi) {
  const twoPi = 2.0 * Math.PI;
  return ((phi % twoPi) + twoPi) % twoPi;
}

function isAngleInCCWSector(phi, start, end) {
  const p = normalizePhi(phi);
  const s = normalizePhi(start);
  const e = normalizePhi(end);
  const span = (e - s + 2.0 * Math.PI) % (2.0 * Math.PI);
  const rel = (p - s + 2.0 * Math.PI) % (2.0 * Math.PI);
  return rel <= span;
}

function nearestPhiIndex(phi) {
  const twoPi = 2.0 * Math.PI;
  const target = normalizePhi(phi);

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
    shininess: 8,
  });
  applyOpacityAndDepth(material, opacity);

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
        const phiMid = normalizePhi(phiAtIndex(ip));
        let keep = true;

        if (clipOptions.mode === "between-meridians-behind" && clipOptions.hasTwoPlanes) {
          const a = normalizePhi(clipOptions.phiA);
          const b = normalizePhi(clipOptions.phiB);
          const spanAB = (b - a + 2.0 * Math.PI) % (2.0 * Math.PI);
          const useAB = spanAB <= Math.PI;
          const inFrontOpening = useAB
            ? isAngleInCCWSector(phiMid, a, b)
            : isAngleInCCWSector(phiMid, b, a);
          keep = !inFrontOpening;
        } else {
          const sideValue = Math.sin(phiMid - clipOptions.phi0);
          keep = clipOptions.side === "negative" ? sideValue < 0.0 : sideValue > 0.0;
        }

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
    shininess: 8,
  });
  applyOpacityAndDepth(material, opacity);

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
  });
  applyOpacityAndDepth(material, opacity);

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
  });
  applyOpacityAndDepth(material, opacity);

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
  const fieldText = `CMB=${params.cmbField}, ICB=${params.icbField}, Eq1=${params.equatorField}, Eq2=${params.equator2Field}, Mer1=${params.meridianField}, Mer2=${params.meridian2Field}`;
  const changed = lastFieldName ? ` | updated=${lastFieldName}` : "";
  setStatus(`${title}${sim}${lineMode}${fieldText}${changed} | grid ${metadata.nr} x ${metadata.ntheta} x ${metadata.nphi}`);
}

async function rebuildCMB() {
  disposeObject(cmbMesh);
  cmbMesh = null;

  const fieldObject = await loadCmbDisplayField(params.cmbField);
  const [vmin, vmax] = cmbDisplayRange(fieldObject, metadata.nr - 1, "cmb");
  setColourbarForSlot("cmb", params.cmbField, vmin, vmax);

  const mer1Shown = params.showMeridian;
  const mer2Shown = params.showMeridian2;
  const anyMeridianShown = mer1Shown || mer2Shown;
  const activeMeridianPhiDeg = mer1Shown
    ? params.meridianPhiDeg
    : mer2Shown
      ? params.meridian2PhiDeg
      : params.meridianPhiDeg;

  let cmbClip = { enabled: false };
  if (params.cmbClipWithMeridian && anyMeridianShown && params.cmbClipMode !== "none") {
    if (params.cmbClipMode === "between-meridians-behind" && mer1Shown && mer2Shown) {
      cmbClip = {
        enabled: true,
        mode: "between-meridians-behind",
        hasTwoPlanes: true,
        phiA: THREE.MathUtils.degToRad(params.meridianPhiDeg),
        phiB: THREE.MathUtils.degToRad(params.meridian2PhiDeg),
      };
    } else {
      cmbClip = {
        enabled: true,
        mode: "rear-half",
        phi0: THREE.MathUtils.degToRad(activeMeridianPhiDeg),
        side: params.cmbRearSide,
      };
    }
  }
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

async function rebuildMeridian2() {
  disposeObject(meridian2Mesh);
  meridian2Mesh = null;

  const field = await loadField(params.meridian2Field);
  const [vmin, vmax] = meridianRange(field, params.meridian2PhiDeg, "meridian2");
  setColourbarForSlot("meridian2", params.meridian2Field, vmin, vmax);

  meridian2Mesh = makeMeridionalSliceMesh(
    field,
    params.meridian2PhiDeg,
    params.meridian2Opacity,
    vmin,
    vmax,
    params.meridian2Colormap
  );
  meridian2Mesh.visible = params.showMeridian2;
  scene.add(meridian2Mesh);
  setStatusSummary(`Meridian2:${params.meridian2Field}`);
}

async function rebuildAllMeshes() {
  setStatus("Loading selected fields...");
  await rebuildCMB();
  await rebuildICB();
  await rebuildEquator();
  await rebuildEquator2();
  await rebuildMeridian();
  await rebuildMeridian2();
  updateVisibility();
  setStatusSummary();
}

function updateVisibility() {
  if (cmbMesh) cmbMesh.visible = params.showCMB;
  if (icbMesh) icbMesh.visible = params.showICB;
  if (equatorMesh) equatorMesh.visible = params.showEquator;
  if (equator2Mesh) equator2Mesh.visible = params.showEquator2;
  if (meridianMesh) meridianMesh.visible = params.showMeridian;
  if (meridian2Mesh) meridian2Mesh.visible = params.showMeridian2;

  if (colourbars.cmb?.row) colourbars.cmb.row.style.display = params.showCMB && cmbMesh ? "block" : "none";
  if (colourbars.icb?.row) colourbars.icb.row.style.display = params.showICB && icbMesh ? "block" : "none";
  if (colourbars.equator?.row) colourbars.equator.row.style.display = params.showEquator && equatorMesh ? "block" : "none";
  if (colourbars.equator2?.row) colourbars.equator2.row.style.display = params.showEquator2 && equator2Mesh ? "block" : "none";
  if (colourbars.meridian?.row) colourbars.meridian.row.style.display = params.showMeridian && meridianMesh ? "block" : "none";
  if (colourbars.meridian2?.row) colourbars.meridian2.row.style.display = params.showMeridian2 && meridian2Mesh ? "block" : "none";
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
  if (cmbMesh) applyOpacityAndDepth(cmbMesh.material, params.cmbOpacity);
  if (icbMesh) applyOpacityAndDepth(icbMesh.material, params.icbOpacity);
  if (equatorMesh) applyOpacityAndDepth(equatorMesh.material, params.equatorOpacity);
  if (equator2Mesh) applyOpacityAndDepth(equator2Mesh.material, params.equator2Opacity);
  if (meridianMesh) applyOpacityAndDepth(meridianMesh.material, params.meridianOpacity);
  if (meridian2Mesh) applyOpacityAndDepth(meridian2Mesh.material, params.meridian2Opacity);
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
  params.meridian2Field = chooseField(["C", "Comp", "Br", "Uabs"], fields);
}

function addDisplayControls(gui, slot, label, fieldParam, showParam, opacityParam, rebuildFn, availableFields) {
  const folder = gui.addFolder(label);

  folder.add(params, showParam).name("Show").onChange(() => { updateVisibility(); if (slot === "meridian" || slot === "meridian2") rebuildCMB(); });
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
  const merFolder = addDisplayControls(gui, "meridian", "Meridional slice 1", "meridianField", "showMeridian", "meridianOpacity", rebuildMeridian, volumeFields);
  merFolder.add(params, "meridianPhiDeg", 0, 360, 1).name("Longitude phi").onChange(() => { rebuildMeridian(); rebuildCMB(); });

  const mer2Folder = addDisplayControls(gui, "meridian2", "Meridional slice 2", "meridian2Field", "showMeridian2", "meridian2Opacity", rebuildMeridian2, volumeFields);
  mer2Folder.add(params, "meridian2PhiDeg", 0, 360, 1).name("Longitude phi").onChange(() => { rebuildMeridian2(); rebuildCMB(); });

  merFolder.add(params, "cmbClipWithMeridian").name("Clip CMB with meridians").onChange(rebuildCMB);
  merFolder.add(params, "cmbClipMode", { None: "none", "Rear half": "rear-half", "Between meridional planes (behind)": "between-meridians-behind" }).name("CMB clip mode").onChange(rebuildCMB);
  merFolder.add(params, "cmbRearSide", { Rear: "positive", Front: "negative" }).name("CMB side").onChange(rebuildCMB);

  const lighting = gui.addFolder("Lighting");
  lighting.add(params, "ambientIntensity", 0.0, 2.0, 0.01).name("Ambient").onChange(updateLighting);
  lighting.add(params, "directionalIntensity", 0.0, 4.0, 0.01).name("Directional").onChange(updateLighting);
  lighting.add(params, "lightAzimuthDeg", 0, 360, 1).name("Light azimuth").onChange(updateLighting);
  lighting.add(params, "lightElevationDeg", -89, 89, 1).name("Light elevation").onChange(updateLighting);

  const viewFolder = gui.addFolder("Point of view");
  cameraParamControllers.push(viewFolder.add(params, "cameraDistance", 0.2, 20.0, 0.01).name("Distance").onChange(applyCameraViewFromParams));
  cameraParamControllers.push(viewFolder.add(params, "cameraAzimuthDeg", -180, 180, 1).name("Azimuth phi").onChange(applyCameraViewFromParams));
  cameraParamControllers.push(viewFolder.add(params, "cameraElevationDeg", -89, 89, 1).name("Elevation theta").onChange(applyCameraViewFromParams));
  cameraParamControllers.push(viewFolder.add(params, "cameraTargetX", -2.0, 2.0, 0.01).name("Target x").onChange(applyCameraViewFromParams));
  cameraParamControllers.push(viewFolder.add(params, "cameraTargetY", -2.0, 2.0, 0.01).name("Target y").onChange(applyCameraViewFromParams));
  cameraParamControllers.push(viewFolder.add(params, "cameraTargetZ", -2.0, 2.0, 0.01).name("Target z").onChange(applyCameraViewFromParams));
  cameraParamControllers.push(viewFolder.add(params, "cameraFovDeg", 10, 90, 1).name("FOV").onChange(applyCameraViewFromParams));
  viewFolder.add(params, "captureCameraView").name("Use current mouse view");
  viewFolder.add(params, "applyCameraView").name("Apply view");

  const exportFolder = gui.addFolder("Export");
  exportFolder.add(params, "exportWidthPx", 800, 6000, 100).name("PNG/PDF width px");
  exportFolder.add(params, "exportPngWhite").name("Save PNG + colourbars");
  exportFolder.add(params, "exportPdfWhite").name("Save PDF + colourbars");
  exportFolder.add(params, "videoWidthPx", 800, 6000, 100).name("Video width px");
  exportFolder.add(params, "videoDurationSec", 2, 120, 1).name("Video duration s");
  exportFolder.add(params, "videoFps", 10, 60, 1).name("Video FPS");
  exportFolder.add(params, "videoRotationMode", { "360° in phi": "phi360", "360° phi + 180° theta": "phi360Theta180" }).name("Rotation mode");
  exportFolder.add(params, "recordFullRotation").name("Record video");

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


async function saveBlob(blob, filename, description = "file") {
  if (!(blob instanceof Blob) || blob.size === 0) {
    throw new Error(`No ${description} data were produced.`);
  }

  setExportMessage(`Saving ${filename}...`);

  if (window.isSecureContext && "showSaveFilePicker" in window) {
    try {
      const extension = filename.split(".").pop()?.toLowerCase() || "dat";
      const pickerTypes = {
        png: [{ description: "PNG image", accept: { "image/png": [".png"] } }],
        pdf: [{ description: "PDF document", accept: { "application/pdf": [".pdf"] } }],
        webm: [{ description: "WebM video", accept: { "video/webm": [".webm"] } }],
      };
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: pickerTypes[extension] || undefined,
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      setStatus(`Saved ${filename}.`);
      return;
    } catch (err) {
      if (err?.name === "AbortError") {
        setStatus(`Save cancelled for ${filename}.`);
        return;
      }
      console.warn("Save picker failed; falling back to download link.", err);
    }
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  setStatus(`Download requested for ${filename}. Check your browser Downloads.`);
}


function withTemporaryWhiteBackground(renderCallback) {
  const previousBackground = scene.background;
  scene.background = new THREE.Color(0xffffff);
  renderer.render(scene, camera);
  const result = renderCallback();
  scene.background = previousBackground;
  renderer.render(scene, camera);
  return result;
}

function getVisibleColourbarSlots() {
  return displaySlots.filter((slot) => {
    const bar = colourbars[slot];
    return bar?.row && bar.row.style.display !== "none";
  });
}

function drawRoundedRectPath(ctx, x, y, w, h, r) {
  const rr = Math.min(r, 0.5 * w, 0.5 * h);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.lineTo(x + w - rr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
  ctx.lineTo(x + w, y + h - rr);
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
  ctx.lineTo(x + rr, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
  ctx.lineTo(x, y + rr);
  ctx.quadraticCurveTo(x, y, x + rr, y);
  ctx.closePath();
}

function drawColourbarGradient(ctx, x, y, w, h, scheme) {
  const stops = colourStops[scheme] || colourStops["blue-white-red"];
  const gradient = ctx.createLinearGradient(x, y, x + w, y);
  for (const [t, rgb] of stops) {
    gradient.addColorStop(t, `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`);
  }
  ctx.fillStyle = gradient;
  drawRoundedRectPath(ctx, x, y, w, h, 0.5 * h);
  ctx.fill();
  ctx.strokeStyle = "rgba(0,0,0,0.45)";
  ctx.lineWidth = Math.max(1, h * 0.08);
  ctx.stroke();
}

function drawExportColourbars(ctx, width, height) {
  const slots = getVisibleColourbarSlots();
  if (slots.length === 0) return;

  const scale = clamp(width / Math.max(1, window.innerWidth), 1.0, 4.0);
  const panelWidth = 330 * scale;
  const panelHeight = 58 * scale;
  const gap = 8 * scale;
  const x = 18 * scale;
  const totalHeight = slots.length * panelHeight + (slots.length - 1) * gap;
  let y = 0.5 * (height - totalHeight);
  y = clamp(y, 18 * scale, Math.max(18 * scale, height - totalHeight - 18 * scale));

  ctx.save();
  for (const slot of slots) {
    const bar = colourbars[slot];
    const scheme = params[`${slot}Colormap`] || "blue-white-red";

    ctx.fillStyle = "rgba(255,255,255,0.88)";
    ctx.strokeStyle = "rgba(0,0,0,0.22)";
    ctx.lineWidth = Math.max(1, scale);
    drawRoundedRectPath(ctx, x, y, panelWidth, panelHeight, 8 * scale);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "rgb(0,0,0)";
    ctx.font = `${Math.round(12 * scale)}px system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif`;
    ctx.textBaseline = "top";
    ctx.fillText(bar.title?.textContent || displayNames[slot], x + 9 * scale, y + 7 * scale);

    const gx = x + 9 * scale;
    const gy = y + 27 * scale;
    const gw = panelWidth - 18 * scale;
    const gh = 13 * scale;
    drawColourbarGradient(ctx, gx, gy, gw, gh, scheme);

    ctx.font = `${Math.round(10 * scale)}px system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif`;
    ctx.textBaseline = "top";
    ctx.fillStyle = "rgb(0,0,0)";
    const minText = bar.min?.textContent || "min";
    const midText = bar.mid?.textContent || "";
    const maxText = bar.max?.textContent || "max";
    ctx.fillText(minText, gx, y + 43 * scale);
    ctx.textAlign = "center";
    ctx.fillText(midText, gx + 0.5 * gw, y + 43 * scale);
    ctx.textAlign = "right";
    ctx.fillText(maxText, gx + gw, y + 43 * scale);
    ctx.textAlign = "left";

    y += panelHeight + gap;
  }
  ctx.restore();
}

function makeCompositeExportCanvas(widthPx = null) {
  const prevSize = renderer.getSize(new THREE.Vector2());
  const prevPixelRatio = renderer.getPixelRatio();
  const prevAspect = camera.aspect;
  const previousBackground = scene.background;
  let needResize = false;

  if (widthPx && Number.isFinite(widthPx) && widthPx > 0) {
    const width = Math.round(widthPx);
    const height = Math.round(width / prevAspect);
    renderer.setPixelRatio(1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    needResize = true;
  }

  scene.background = new THREE.Color(0xffffff);
  renderer.render(scene, camera);

  const canvas = document.createElement("canvas");
  canvas.width = renderer.domElement.width;
  canvas.height = renderer.domElement.height;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "white";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(renderer.domElement, 0, 0, canvas.width, canvas.height);
  drawExportColourbars(ctx, canvas.width, canvas.height);

  scene.background = previousBackground;
  if (needResize) {
    renderer.setPixelRatio(prevPixelRatio);
    renderer.setSize(prevSize.x, prevSize.y, false);
    camera.aspect = prevAspect;
    camera.updateProjectionMatrix();
  }
  renderer.render(scene, camera);

  return canvas;
}

function exportCanvasDataUrl(type = "image/png", quality = 0.95, widthPx = null) {
  const canvas = makeCompositeExportCanvas(widthPx);
  return canvas.toDataURL(type, quality);
}

function exportCanvasBlob(type = "image/png", quality = 0.95, widthPx = null) {
  return new Promise((resolve, reject) => {
    try {
      const canvas = makeCompositeExportCanvas(widthPx);
      if (canvas.toBlob) {
        canvas.toBlob((blob) => {
          if (blob) resolve(blob);
          else reject(new Error("Canvas export produced no blob."));
        }, type, quality);
      } else {
        resolve(dataUrlToBlob(canvas.toDataURL(type, quality)));
      }
    } catch (err) {
      reject(err);
    }
  });
}

function dataUrlToBlob(dataUrl) {
  const [header, data] = dataUrl.split(",");
  const mime = header.match(/data:(.*?);base64/)[1];
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

async function exportCurrentViewPNG() {
  try {
    setStatus("Preparing PNG export...");
    const blob = await exportCanvasBlob("image/png", 1.0, params.exportWidthPx);
    await saveBlob(blob, `dynamo-viewer-${Date.now()}.png`, "PNG");
  } catch (err) {
    console.error(err);
    setStatus(`PNG export failed: ${err.message}`);
  }
}


function concatUint8Arrays(chunks) {
  const total = chunks.reduce((s, a) => s + a.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const a of chunks) {
    out.set(a, offset);
    offset += a.length;
  }
  return out;
}

function asciiBytes(str) {
  return new TextEncoder().encode(str);
}

function base64ToUint8Array(base64) {
  const binary = atob(base64);
  const arr = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) arr[i] = binary.charCodeAt(i);
  return arr;
}

function makeSimplePdfFromJpegDataUrl(dataUrl, widthPx, heightPx) {
  const base64 = dataUrl.split(",")[1];
  const jpegBytes = base64ToUint8Array(base64);
  const pageWidth = Math.max(100, Math.round(widthPx * 0.75));
  const pageHeight = Math.max(100, Math.round(heightPx * 0.75));
  const content = `q\n${pageWidth} 0 0 ${pageHeight} 0 0 cm\n/Im0 Do\nQ\n`;

  const objects = [
    asciiBytes("<< /Type /Catalog /Pages 2 0 R >>"),
    asciiBytes("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    asciiBytes(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Resources << /ProcSet [/PDF /ImageC] /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>`),
    concatUint8Arrays([
      asciiBytes(`<< /Type /XObject /Subtype /Image /Width ${widthPx} /Height ${heightPx} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpegBytes.length} >>\nstream\n`),
      jpegBytes,
      asciiBytes("\nendstream")
    ]),
    asciiBytes(`<< /Length ${content.length} >>\nstream\n${content}endstream`)
  ];

  const chunks = [asciiBytes("%PDF-1.4\n%\xFF\xFF\xFF\xFF\n")];
  const offsets = [0];
  let currentOffset = chunks[0].length;

  for (let i = 0; i < objects.length; i++) {
    offsets.push(currentOffset);
    const header = asciiBytes(`${i + 1} 0 obj\n`);
    const footer = asciiBytes("\nendobj\n");
    chunks.push(header, objects[i], footer);
    currentOffset += header.length + objects[i].length + footer.length;
  }

  const xrefOffset = currentOffset;
  let xref = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (let i = 1; i <= objects.length; i++) {
    xref += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }

  const trailer = `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;
  chunks.push(asciiBytes(xref), asciiBytes(trailer));
  return new Blob(chunks, { type: "application/pdf" });
}

async function exportCurrentViewPDF() {
  try {
    setStatus("Preparing PDF export...");
    const widthPx = Math.round(params.exportWidthPx);
    const heightPx = Math.round(widthPx / camera.aspect);
    const dataUrl = exportCanvasDataUrl("image/jpeg", 0.95, widthPx);
    const blob = makeSimplePdfFromJpegDataUrl(dataUrl, widthPx, heightPx);
    await saveBlob(blob, `dynamo-viewer-${Date.now()}.pdf`, "PDF");
  } catch (err) {
    console.error(err);
    setStatus(`PDF export failed: ${err.message}`);
  }
}


function getSupportedVideoMimeType() {
  const candidates = [
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm"
  ];

  for (const type of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) return type;
  }

  return "";
}

function resizeRendererForVideoIfNeeded() {
  const width = Math.round(Number(params.videoWidthPx));
  if (!Number.isFinite(width) || width <= 0) return;

  videoState.previousRendererSize = renderer.getSize(new THREE.Vector2());
  videoState.previousPixelRatio = renderer.getPixelRatio();
  videoState.previousAspect = camera.aspect;

  const height = Math.max(1, Math.round(width / camera.aspect));
  renderer.setPixelRatio(1);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  videoState.resizedRenderer = true;
}

function restoreRendererAfterVideo() {
  if (!videoState.resizedRenderer) return;
  renderer.setPixelRatio(videoState.previousPixelRatio);
  renderer.setSize(videoState.previousRendererSize.x, videoState.previousRendererSize.y, false);
  camera.aspect = videoState.previousAspect;
  camera.updateProjectionMatrix();
  videoState.resizedRenderer = false;
}

function cameraPositionFromRawSpherical(target, radius, polarAngle, azimuthAngle) {
  return new THREE.Vector3(
    target.x + radius * Math.sin(polarAngle) * Math.cos(azimuthAngle),
    target.y + radius * Math.sin(polarAngle) * Math.sin(azimuthAngle),
    target.z + radius * Math.cos(polarAngle)
  );
}

function startFullRotationRecording() {
  if (videoState.active) return;

  if (typeof MediaRecorder === "undefined" || !renderer.domElement.captureStream) {
    setStatus("Video recording is not supported in this browser.");
    return;
  }

  const offset = camera.position.clone().sub(controls.target);
  const radius = offset.length();
  const radiusXY = Math.hypot(offset.x, offset.y);

  if (radius <= 1.0e-8 || radiusXY <= 1.0e-8) {
    setStatus("Cannot record rotation from current camera position.");
    return;
  }

  resizeRendererForVideoIfNeeded();
  renderer.render(scene, camera);

  const mimeType = getSupportedVideoMimeType();
  const stream = renderer.domElement.captureStream(Math.max(1, Math.round(params.videoFps)));
  const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);

  videoState.active = true;
  videoState.recorder = recorder;
  videoState.chunks = [];
  videoState.startTime = performance.now();
  videoState.durationMs = 1000 * Math.max(1, Number(params.videoDurationSec));
  videoState.startAngle = Math.atan2(offset.y, offset.x);
  videoState.radiusXY = radiusXY;
  videoState.zOffset = offset.z;
  videoState.radius = radius;
  videoState.polarAngle = Math.acos(clamp(offset.z / radius, -1.0, 1.0));
  videoState.mode = params.videoRotationMode;
  videoState.target.copy(controls.target);
  videoState.startPosition.copy(camera.position);

  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) videoState.chunks.push(event.data);
  };

  recorder.onstop = async () => {
    const blob = new Blob(videoState.chunks, { type: mimeType || "video/webm" });
    try {
      await saveBlob(blob, `dynamo-viewer-rotation-${Date.now()}.webm`, "video");
    } catch (err) {
      console.error(err);
      setStatus(`Video save failed: ${err.message}`);
    } finally {
      stream.getTracks().forEach((t) => t.stop());
      controls.enabled = true;
      videoState.active = false;
      camera.position.copy(videoState.startPosition);
      restoreRendererAfterVideo();
      controls.update();
      syncCameraParamsFromCamera(true);
    }
  };

  controls.enabled = false;
  recorder.start();
  setStatus(`Recording video at ${renderer.domElement.width} x ${renderer.domElement.height} px...`);
}

function updateVideoRecordingFrame(nowMs) {
  if (!videoState.active) return;

  const frac = Math.min(1, (nowMs - videoState.startTime) / videoState.durationMs);
  let azimuth = videoState.startAngle + 2.0 * Math.PI * frac;
  let polar = videoState.polarAngle;

  if (videoState.mode === "phi360Theta180") {
    const phiPhase = Math.min(1.0, frac / 0.75);
    const thetaPhase = frac <= 0.75 ? 0.0 : (frac - 0.75) / 0.25;
    azimuth = videoState.startAngle + 2.0 * Math.PI * phiPhase;
    polar = videoState.polarAngle + Math.PI * thetaPhase;
  }

  camera.position.copy(cameraPositionFromRawSpherical(videoState.target, videoState.radius, polar, azimuth));
  camera.up.set(0.0, 0.0, 1.0);
  camera.lookAt(videoState.target);

  if (frac >= 1 && videoState.recorder && videoState.recorder.state !== "inactive") {
    videoState.recorder.stop();
  }
}



function bindExportPanelButtons() {
  document.getElementById("export-png-button")?.addEventListener("click", () => exportCurrentViewPNG());
  document.getElementById("export-pdf-button")?.addEventListener("click", () => exportCurrentViewPDF());
  document.getElementById("export-video-button")?.addEventListener("click", () => startFullRotationRecording());
}

function animate(now = performance.now()) {
  requestAnimationFrame(animate);
  if (videoState.active) {
    updateVideoRecordingFrame(now);
  } else {
    controls.update();
  }
  renderer.render(scene, camera);
}

async function init() {
  try {
    setStatus("Loading metadata...");
    metadata = await loadMetadata();
    await loadCoordinates();

    applyDefaultFields();
    syncCameraParamsFromCamera(false);
    buildGui();
    bindExportPanelButtons();
    updateLighting();

    await rebuildAllMeshes();
    await loadFieldLines();

    animate();
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`);
  }
}

window.addEventListener("resize", () => {
  if (videoState.active) return;
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  syncCameraParamsFromCamera(true);
});

init();
