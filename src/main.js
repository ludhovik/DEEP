import "./style.css";

import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import GUI from "lil-gui";

const statusEl = document.getElementById("status");
const exportMessageEl = document.getElementById("export-message");

const displaySlots = ["cmb", "icb", "equator", "equator2", "meridian", "meridian2", "fieldlines"];
const displayNames = {
  cmb: "CMB",
  icb: "ICB",
  equator: "Equator 1",
  equator2: "Equator 2",
  meridian: "Meridian 1",
  meridian2: "Meridian 2",
  fieldlines: "Field lines",
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

const lineLegendEl = document.getElementById("line-legend");

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

  showIsosurfaces: false,
  isoField: "ur",
  showIsoPositive: true,
  showIsoNegative: true,
  isoPositiveValue: 0.10,
  isoNegativeValue: -0.10,
  isoResolution: 36,
  isoOpacity: 0.45,
  isoClipWithMeridian: false,
  isoClipOffsetMeridian1: 0.0,
  isoClipOffsetMeridian2: 0.0,
  isoPositiveColor: "#d73027",
  isoNegativeColor: "#4575b4",

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
  lineColourMode: "strength",
  lineColormap: "viridis",
  lineScale: "minmax",
  lineValueTransform: "linear",
  lineMin: 0.0,
  lineMax: 1.0,
  lineWidthPx: 2.0,
  lineOpacity: 0.95,

  showEarthSurface: false,
  earthLongitudeDeg: 0.0,
  earthRadiusScale: 1.83,
  earthOpacity: 0.95,
  showSliceGapFiller: true,
  sliceGapFillerOpacity: 0.35,

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

  datasetPath: "/data",
  reloadDataset: () => loadDatasetFromParams(),

  secondaryDatasetPath: "/data2",
  secondaryDatasetLabel: "D2",
  loadSecondaryDataset: () => loadSecondaryDatasetFromParams(),
  clearSecondaryDataset: () => clearSecondaryDataset(),

  sequenceFrame: 0,
  sequenceFps: 4,
  sequencePlaying: false,
  sequenceMaxCachedFrames: 10,
  sequenceCacheLimitMB: 1500,
  playSequence: () => playSequence(),
  pauseSequence: () => pauseSequence(),
  reloadSequence: () => reloadSequenceIndex(),
  preloadSequenceFrames: () => preloadSequenceFrames(),
  clearSequenceCache: () => clearLoadedDataCaches(true),

  copyViewStateCode: () => copyViewStateCode(),
  showViewStateCode: () => showViewStateCode(),
  loadViewStateCode: () => loadViewStateCode(),
  saveViewStateCode: () => saveViewStateCode(),

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
let isoPositiveMesh = null;
let isoNegativeMesh = null;
let equatorFillerMesh = null;
let equator2FillerMesh = null;
let meridianFillerMesh = null;
let meridian2FillerMesh = null;
let fieldLineGroups = { shell: null, exterior: null };
let earthMesh = null;
let earthTexture = null;
const fieldLineDataCache = new Map();

const EARTH_TEXTURE_URL = "/assets/earth_blue_marble.jpg";
const EARTH_TEXTURE_ATTRIBUTION = "Earth texture: local file public/assets/earth_blue_marble.jpg."; 

const dataCache = new Map();
const dataCacheMeta = new Map();
const jsonCache = new Map();
let dataCacheBytes = 0;
let dataCacheCounter = 0;
let guiRoot = null;
let datasetRootPath = "/data";
let dataBasePath = "/data";
let secondaryDataset = null;
let sequenceIndex = null;
let sequenceTimer = null;
let sequenceFrameLoading = false;
const sequenceControllers = [];

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


function setLineLegendMode(mode) {
  if (!lineLegendEl) return;
  lineLegendEl.style.display = mode === "polarity" && params.showFieldLines ? "block" : "none";
}

function getLineColourbarState() {
  const bar = colourbars.fieldlines;
  if (!bar) return null;
  return bar;
}

function transformFieldLineStrength(value) {
  const v = Number(value);
  if (!Number.isFinite(v)) return NaN;
  if (params.lineValueTransform === "log10") {
    return v > 0 ? Math.log10(v) : NaN;
  }
  return v;
}

function inverseTransformFieldLineStrength(value) {
  const v = Number(value);
  if (!Number.isFinite(v)) return NaN;
  if (params.lineValueTransform === "log10") {
    return 10 ** v;
  }
  return v;
}

function fieldLineQuantityLabel() {
  return params.lineValueTransform === "log10" ? "Field lines: log10(|B|)" : "Field lines: |B|";
}

function setFieldLineColourbar(vmin, vmax) {
  const bar = getLineColourbarState();
  if (!bar) return;
  const mid = 0.5 * (vmin + vmax);
  bar.title.textContent = fieldLineQuantityLabel();
  bar.min.textContent = formatNumber(vmin);
  if (bar.mid) bar.mid.textContent = formatNumber(mid);
  bar.max.textContent = formatNumber(vmax);
  if (bar.gradient) bar.gradient.style.background = colourbarCssGradient(params.lineColormap || "viridis");
  bar.row.style.display = params.showFieldLines && params.lineColourMode === "strength" ? "block" : "none";
}

function hideFieldLineColourbar() {
  const bar = getLineColourbarState();
  if (bar?.row) bar.row.style.display = "none";
}

function strengthRangeFromLines(lines) {
  let vmin = Infinity;
  let vmax = -Infinity;
  for (const line of lines) {
    if (!Array.isArray(line.strength)) continue;
    for (const val of line.strength) {
      const tval = transformFieldLineStrength(val);
      if (!Number.isFinite(tval)) continue;
      if (tval < vmin) vmin = tval;
      if (tval > vmax) vmax = tval;
    }
  }
  if (!Number.isFinite(vmin) || !Number.isFinite(vmax) || vmax <= vmin) {
    vmin = params.lineValueTransform === "log10" ? -6.0 : 0.0;
    vmax = 1.0;
  }
  return [vmin, vmax];
}

function getFieldLineRange(lines) {
  const [autoMin, autoMax] = strengthRangeFromLines(lines);
  if (params.lineScale === "manual") {
    const a = Number(params.lineMin);
    const b = Number(params.lineMax);
    if (Number.isFinite(a) && Number.isFinite(b) && b > a) return [a, b];
  }
  return [autoMin, autoMax];
}

function getFieldLineVertexColor(strength, polarity, vmin, vmax) {
  if (params.lineColourMode === "polarity") {
    const c = polarity >= 0 ? new THREE.Color(0xffd080) : new THREE.Color(0x80c0ff);
    return c;
  }
  const value = transformFieldLineStrength(strength);
  const safeValue = Number.isFinite(value) ? value : 0.5 * (vmin + vmax);
  return colourMap(safeValue, vmin, vmax, params.lineColormap || "viridis");
}

function updateLineMaterialResolution(material) {
  if (material && material.resolution) {
    material.resolution.set(renderer.domElement.width, renderer.domElement.height);
  }
}

function makeLineMaterial() {
  const material = new LineMaterial({
    color: 0xffffff,
    linewidth: Math.max(1.0, Number(params.lineWidthPx)),
    transparent: Number(params.lineOpacity) < 0.999,
    opacity: Number(params.lineOpacity),
    vertexColors: true,
    dashed: false,
    depthTest: true,
    depthWrite: Number(params.lineOpacity) >= 0.999,
  });
  updateLineMaterialResolution(material);
  return material;
}

function updateFieldLineVisuals() {
  const groups = Object.values(fieldLineGroups).filter(Boolean);
  for (const group of groups) {
    group.traverse((obj) => {
      const mat = obj.material;
      if (mat && typeof mat === "object") {
        if ("linewidth" in mat) mat.linewidth = Math.max(1.0, Number(params.lineWidthPx));
        mat.opacity = Number(params.lineOpacity);
        mat.transparent = Number(params.lineOpacity) < 0.999;
        mat.depthWrite = Number(params.lineOpacity) >= 0.999;
        updateLineMaterialResolution(mat);
        mat.needsUpdate = true;
      }
    });
  }
}

async function ensureEarthTexture() {
  if (earthTexture) return earthTexture;
  const loader = new THREE.TextureLoader();
  loader.setCrossOrigin("anonymous");
  const texture = await new Promise((resolve, reject) => {
    loader.load(EARTH_TEXTURE_URL, resolve, undefined, reject);
  });
  earthTexture = texture;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.ClampToEdgeWrapping;
  texture.colorSpace = THREE.SRGBColorSpace;

  let attrib = document.getElementById("earth-attribution");
  if (!attrib) {
    attrib = document.createElement("div");
    attrib.id = "earth-attribution";
    attrib.innerHTML = '<div>' + EARTH_TEXTURE_ATTRIBUTION + '</div><div><a href="' + EARTH_TEXTURE_URL + '" target="_blank" rel="noopener">Open texture source</a></div>';
    document.body.appendChild(attrib);
  }
  return earthTexture;
}

function getActiveCmbClipOptions() {
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
  return cmbClip;
}

function getActiveIsoClipOptions() {
  if (!params.isoClipWithMeridian) return { enabled: false };

  const mer1Shown = params.showMeridian;
  const mer2Shown = params.showMeridian2;
  const anyMeridianShown = mer1Shown || mer2Shown;
  const activeMeridianPhiDeg = mer1Shown
    ? params.meridianPhiDeg
    : mer2Shown
      ? params.meridian2PhiDeg
      : params.meridianPhiDeg;
  const activeOffset = mer1Shown
    ? Number(params.isoClipOffsetMeridian1 || 0.0)
    : mer2Shown
      ? Number(params.isoClipOffsetMeridian2 || 0.0)
      : Number(params.isoClipOffsetMeridian1 || 0.0);

  let isoClip = { enabled: false };
  if (params.cmbClipWithMeridian && anyMeridianShown && params.cmbClipMode !== "none") {
    if (params.cmbClipMode === "between-meridians-behind" && mer1Shown && mer2Shown) {
      isoClip = {
        enabled: true,
        mode: "between-meridians-behind",
        hasTwoPlanes: true,
        phiA: THREE.MathUtils.degToRad(params.meridianPhiDeg),
        phiB: THREE.MathUtils.degToRad(params.meridian2PhiDeg),
        offsetA: Number(params.isoClipOffsetMeridian1 || 0.0),
        offsetB: Number(params.isoClipOffsetMeridian2 || 0.0),
      };
    } else {
      isoClip = {
        enabled: true,
        mode: "rear-half",
        phi0: THREE.MathUtils.degToRad(activeMeridianPhiDeg),
        side: params.cmbRearSide,
        offset: activeOffset,
      };
    }
  }
  return isoClip;
}

function planeValueAtPoint(point, phi0) {
  const x = point[0];
  const y = point[1];
  return -Math.sin(phi0) * x + Math.cos(phi0) * y;
}

function shouldKeepPointForIsoClip(point, clipOptions = null) {
  if (!clipOptions?.enabled) return true;

  if (clipOptions.mode === "between-meridians-behind" && clipOptions.hasTwoPlanes) {
    const a = normalizePhi(clipOptions.phiA);
    const b = normalizePhi(clipOptions.phiB);
    const spanAB = (b - a + 2.0 * Math.PI) % (2.0 * Math.PI);
    const useAB = spanAB <= Math.PI;
    const valA = planeValueAtPoint(point, a);
    const valB = planeValueAtPoint(point, b);
    const offA = Number(clipOptions.offsetA || 0.0);
    const offB = Number(clipOptions.offsetB || 0.0);
    const inFrontOpening = useAB
      ? (valA >= offA && valB <= offB)
      : (valB >= offB && valA <= offA);
    return !inFrontOpening;
  }

  const val = planeValueAtPoint(point, clipOptions.phi0);
  const off = Number(clipOptions.offset || 0.0);
  return clipOptions.side === "negative" ? val < off : val > off;
}

function shouldKeepPhiForClip(phiValue, clipOptions = null) {
  if (!clipOptions?.enabled) return true;

  const phiMid = normalizePhi(phiValue);
  if (clipOptions.mode === "between-meridians-behind" && clipOptions.hasTwoPlanes) {
    const a = normalizePhi(clipOptions.phiA);
    const b = normalizePhi(clipOptions.phiB);
    const spanAB = (b - a + 2.0 * Math.PI) % (2.0 * Math.PI);
    const useAB = spanAB <= Math.PI;
    const inFrontOpening = useAB
      ? isAngleInCCWSector(phiMid, a, b)
      : isAngleInCCWSector(phiMid, b, a);
    return !inFrontOpening;
  }

  const sideValue = Math.sin(phiMid - clipOptions.phi0);
  return clipOptions.side === "negative" ? sideValue < 0.0 : sideValue > 0.0;
}

function triangleCentroidPhi(p0, p1, p2) {
  const x = (p0[0] + p1[0] + p2[0]) / 3.0;
  const y = (p0[1] + p1[1] + p2[1]) / 3.0;
  return normalizePhi(Math.atan2(y, x));
}

function makeEarthSurfaceMesh(radius, opacity, texture, longitudeDeg, clipOptions = null) {
  const nTheta = 96;
  const nPhi = 192;
  const positions = [];
  const normals = [];
  const uvs = [];
  const indices = [];

  // Geometry is fixed in the dynamo frame: north pole is always +z.
  // The longitude control must only shift the texture in u, never rotate/tilt the mesh.

  for (let it = 0; it <= nTheta; it++) {
    const theta = Math.PI * it / nTheta;
    for (let ip = 0; ip <= nPhi; ip++) {
      const phi = 2.0 * Math.PI * ip / nPhi;
      positions.push(
        radius * Math.sin(theta) * Math.cos(phi),
        radius * Math.sin(theta) * Math.sin(phi),
        radius * Math.cos(theta)
      );
      normals.push(
        Math.sin(theta) * Math.cos(phi),
        Math.sin(theta) * Math.sin(phi),
        Math.cos(theta)
      );
      const u = normalizePhi(phi) / (2.0 * Math.PI);
      const v = 1.0 - theta / Math.PI;
      uvs.push(u, v);
    }
  }

  for (let it = 0; it < nTheta; it++) {
    for (let ip = 0; ip < nPhi; ip++) {
      if (!shouldKeepPhiForClip(2.0 * Math.PI * (ip + 0.5) / nPhi, clipOptions)) continue;
      const row = nPhi + 1;
      const a = it * row + ip;
      const b = it * row + (ip + 1);
      const c = (it + 1) * row + ip;
      const d = (it + 1) * row + (ip + 1);
      indices.push(a, c, b, b, c, d);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("normal", new THREE.Float32BufferAttribute(normals, 3));
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);

  const textureMap = texture.clone();
  textureMap.wrapS = THREE.RepeatWrapping;
  textureMap.wrapT = THREE.ClampToEdgeWrapping;
  textureMap.colorSpace = THREE.SRGBColorSpace;
  textureMap.offset.x = -Number(longitudeDeg) / 360.0;
  textureMap.offset.y = 0.0;
  textureMap.repeat.set(1.0, 1.0);
  textureMap.needsUpdate = true;

  const material = new THREE.MeshPhongMaterial({ map: textureMap, side: THREE.FrontSide, shininess: 6 });
  applyOpacityAndDepth(material, Number(opacity));
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = "earth-surface-sphere";
  mesh.rotation.set(0.0, 0.0, 0.0);
  mesh.up.set(0.0, 0.0, 1.0);
  return mesh;
}

async function updateEarthSurface() {
  if (!params.showEarthSurface) {
    if (earthMesh) earthMesh.visible = false;
    const a = document.getElementById("earth-attribution");
    if (a) a.style.display = "none";
    await rebuildGapFillers();
    return;
  }
  try {
    const texture = await ensureEarthTexture();
    const radius = Number(metadata?.radii?.outer || metadata?.r_outer || 1.0) * Number(params.earthRadiusScale);
    const clipOptions = getActiveCmbClipOptions();
    if (earthMesh) {
      scene.remove(earthMesh);
      disposeObject(earthMesh);
      earthMesh = null;
    }
    earthMesh = makeEarthSurfaceMesh(radius, params.earthOpacity, texture, params.earthLongitudeDeg, clipOptions);
    earthMesh.visible = true;
    scene.add(earthMesh);
    const a = document.getElementById("earth-attribution");
    if (a) a.style.display = "block";
    await rebuildGapFillers();
  } catch (err) {
    console.warn("Could not load Earth texture", err);
    setStatus(`Earth texture could not be loaded: ${err.message}`);
  }
}


function normaliseDatasetRoot(path) {
  let p = String(path || "/data").trim().replace(/\\/g, "/");
  p = p.replace(/^public\//, "");
  p = p.replace(/\/+$/, "");
  if (!p) p = "/data";
  if (!p.startsWith("/")) p = `/${p}`;
  return p;
}

function getDatasetPathFromQuery() {
  try {
    return new URLSearchParams(window.location.search).get("dataset");
  } catch {
    return null;
  }
}

function askForDatasetRoot(message = null) {
  const queryPath = getDatasetPathFromQuery();
  if (queryPath) return normaliseDatasetRoot(queryPath);

  const saved = localStorage.getItem("dynamoThreeViewer.datasetPath") || params.datasetPath || "/data";
  const promptMessage = message || [
    "Enter the dataset folder to load from public/.",
    "",
    "Examples:",
    "  /data",
    "  /data_run2",
    "  /datasets/run_A",
    "",
    "If the data are in public/datasets/run_A, enter /datasets/run_A."
  ].join("\n");

  const chosen = window.prompt(promptMessage, saved);
  return normaliseDatasetRoot(chosen || saved || "/data");
}

function rememberDatasetRoot(path) {
  const p = normaliseDatasetRoot(path);
  try {
    localStorage.setItem("dynamoThreeViewer.datasetPath", p);
  } catch {
    // localStorage can be disabled; this is not fatal.
  }
  return p;
}

function dataUrlForBase(basePath, path) {
  const cleanBase = normaliseDatasetRoot(basePath);
  const cleanPath = String(path || "").replace(/^\/+/, "");
  return cleanPath ? `${cleanBase}/${cleanPath}` : cleanBase;
}

function dataUrl(path) {
  return dataUrlForBase(dataBasePath, path);
}

function sequenceFrameBasePath(frame) {
  return dataUrlForBase(datasetRootPath, normaliseSequenceFramePath(frame?.path || ""));
}

function formatBytes(bytes) {
  const b = Number(bytes) || 0;
  if (b < 1024) return `${b} B`;
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} kB`;
  if (b < 1024 ** 3) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${(b / 1024 ** 3).toFixed(2)} GB`;
}

function enforceDataCacheLimit() {
  const limitBytes = Math.max(32, Number(params.sequenceCacheLimitMB) || 1500) * 1024 * 1024;
  if (dataCacheBytes <= limitBytes) return;

  const entries = [...dataCacheMeta.entries()].sort((a, b) => a[1].last - b[1].last);
  for (const [key, info] of entries) {
    if (dataCacheBytes <= limitBytes) break;
    dataCache.delete(key);
    dataCacheMeta.delete(key);
    dataCacheBytes -= info.bytes || 0;
  }
}

function clearLoadedDataCaches(showMessage = false) {
  dataCache.clear();
  dataCacheMeta.clear();
  jsonCache.clear();
  fieldLineDataCache.clear();
  dataCacheBytes = 0;
  if (showMessage) setStatus("Dataset/sequence cache cleared.");
}


async function fetchJsonStrict(url, label) {
  if (jsonCache.has(url)) return jsonCache.get(url);

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${label} not found at ${url} (HTTP ${response.status}).`);
  }
  const raw = await response.text();
  const trimmed = raw.trim();
  if (trimmed.startsWith("<!doctype") || trimmed.startsWith("<html") || trimmed.startsWith("<")) {
    throw new Error(
      `${label} at ${url} returned HTML instead of JSON. ` +
      `Check that the file exists under public${datasetRootPath} and that paths in sequence.json are relative to that dataset folder.`
    );
  }
  try {
    const parsed = JSON.parse(raw);
    jsonCache.set(url, parsed);
    return parsed;
  } catch (err) {
    throw new Error(`${label} at ${url} is not valid JSON: ${err.message}`);
  }
}

function normaliseSequenceFramePath(path) {
  let p = String(path || "").trim().replace(/\\/g, "/");
  p = p.replace(/^\/+/, "");
  p = p.replace(/^public\//, "");

  // Accept sequence.json entries written either as relative paths
  // (frames/state03100) or mistakenly as dataset-prefixed paths
  // (data_run2/frames/state03100, public/data_run2/frames/state03100).
  const rootNoSlash = normaliseDatasetRoot(datasetRootPath).replace(/^\/+/, "");
  if (rootNoSlash && p.startsWith(`${rootNoSlash}/`)) {
    p = p.slice(rootNoSlash.length + 1);
  }

  // Backward compatibility for the original default public/data root.
  p = p.replace(/^data\//, "");
  return p;
}

async function loadSequenceIndex(silent = false) {
  try {
    sequenceIndex = await fetchJsonStrict(dataUrlForBase(datasetRootPath, "sequence.json"), "sequence.json");

    if (Array.isArray(sequenceIndex.frames)) {
      sequenceIndex.frames = sequenceIndex.frames.map((frame) => ({
        ...frame,
        path: normaliseSequenceFramePath(frame.path),
        metadata: normaliseSequenceFramePath(frame.metadata || `${frame.path}/metadata.json`),
      }));
    }

    const n = Array.isArray(sequenceIndex.frames) ? sequenceIndex.frames.length : 0;
    if (n > 0) {
      params.sequenceFrame = clamp(Math.round(params.sequenceFrame), 0, n - 1);
      refreshSequenceControllers();
      if (!silent) setStatus(`Loaded sequence with ${n} frames from ${datasetRootPath}.`);
    }
    return sequenceIndex;
  } catch (err) {
    console.warn("Could not load sequence.json", err);
    sequenceIndex = null;
    if (!silent) setStatus(`Could not load sequence: ${err.message}`);
    return null;
  }
}


async function reloadSequenceIndex() {
  jsonCache.delete(dataUrlForBase(datasetRootPath, "sequence.json"));
  await loadSequenceIndex(false);
  buildGui();
}

function refreshSequenceControllers() {
  for (const controller of sequenceControllers) controller.updateDisplay();
}


function getPreloadFieldRequests(meta) {
  const requests = new Map();
  const nr = Number(meta.nr);
  const nt = Number(meta.ntheta);
  const np = Number(meta.nphi);
  const volumeLength = nr * nt * np;
  const surfaceLength = nt * np;

  function addVolume(fieldName) {
    if (!fieldName || !meta.fields?.[fieldName]) return;
    requests.set(meta.fields[fieldName], volumeLength);
  }

  function addCmb(fieldName) {
    if (!fieldName) return;
    const surfaceInfo = meta.surface_fields?.[fieldName];
    if (surfaceInfo?.surface === "cmb" && surfaceInfo.file) {
      requests.set(surfaceInfo.file, surfaceLength);
      return;
    }
    addVolume(fieldName);
  }

  if (params.showCMB) addCmb(params.cmbField);
  if (params.showICB) addVolume(params.icbField);
  if (params.showEquator) addVolume(params.equatorField);
  if (params.showEquator2) addVolume(params.equator2Field);
  if (params.showMeridian) addVolume(params.meridianField);
  if (params.showMeridian2) addVolume(params.meridian2Field);
  if (params.showIsosurfaces) addVolume(params.isoField);

  return [...requests.entries()].map(([filename, expectedLength]) => ({ filename, expectedLength }));
}

async function preloadSequenceFrames() {
  if (!sequenceIndex || !Array.isArray(sequenceIndex.frames) || sequenceIndex.frames.length === 0) {
    await loadSequenceIndex(false);
  }
  if (!sequenceIndex || !Array.isArray(sequenceIndex.frames) || sequenceIndex.frames.length === 0) return;

  const n = sequenceIndex.frames.length;
  const start = clamp(Math.round(params.sequenceFrame), 0, n - 1);
  const maxFrames = Math.max(1, Math.min(n, Math.round(Number(params.sequenceMaxCachedFrames) || 10)));

  setStatus(`Preloading ${maxFrames} sequence frames...`);

  let loadedFiles = 0;
  for (let k = 0; k < maxFrames; k++) {
    const i = (start + k) % n;
    const frame = sequenceIndex.frames[i];
    const basePath = sequenceFrameBasePath(frame);
    const meta = await loadMetadataForBase(basePath);
    await loadCoordinatesForBase(basePath, meta);

    const requests = getPreloadFieldRequests(meta);
    for (const req of requests) {
      await loadFloat32ForBase(basePath, req.filename, req.expectedLength);
      loadedFiles++;
    }

    refreshSequenceControllers();
    setStatus(
      `Preloaded ${k + 1}/${maxFrames} frames, ${loadedFiles} arrays; cache=${formatBytes(dataCacheBytes)}.`
    );

    // Give the browser one frame to keep the UI responsive during preloading.
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }

  setStatus(`Preload complete: cache=${formatBytes(dataCacheBytes)}.`);
}

async function loadFrameByIndex(index) {
  if (sequenceFrameLoading) return;
  sequenceFrameLoading = true;

  try {
    if (!sequenceIndex || !Array.isArray(sequenceIndex.frames) || sequenceIndex.frames.length === 0) {
      await loadSequenceIndex(false);
    }
    if (!sequenceIndex || !Array.isArray(sequenceIndex.frames) || sequenceIndex.frames.length === 0) return;

    const n = sequenceIndex.frames.length;
    const i = clamp(Math.round(index), 0, n - 1);
    params.sequenceFrame = i;
    refreshSequenceControllers();

    const frame = sequenceIndex.frames[i];
    dataBasePath = sequenceFrameBasePath(frame);

    metadata = await loadMetadata();
    await loadCoordinates();

    // Keep the current selected fields when available; otherwise fall back safely.
    for (const key of ["cmbField", "icbField", "equatorField", "equator2Field", "meridianField", "meridian2Field"]) {
      if (!validFieldForState(key, params[key])) {
        applyDefaultFields();
        break;
      }
    }

    await rebuildAllMeshes();
    await loadFieldLines();
    await updateEarthSurface();
    updateVisibility();
    setStatus(`Frame ${i + 1}/${n}: ${frame.label || frame.state_number || i}; cache=${formatBytes(dataCacheBytes)}`);
  } finally {
    sequenceFrameLoading = false;
  }
}

async function playSequence() {
  if (!sequenceIndex) await loadSequenceIndex(false);
  if (!sequenceIndex || !Array.isArray(sequenceIndex.frames) || sequenceIndex.frames.length === 0) return;

  pauseSequence();
  params.sequencePlaying = true;
  const delayMs = 1000 / Math.max(0.1, Number(params.sequenceFps));
  sequenceTimer = window.setInterval(async () => {
    if (sequenceFrameLoading) return;
    const n = sequenceIndex.frames.length;
    const next = (Math.round(params.sequenceFrame) + 1) % n;
    await loadFrameByIndex(next);
  }, delayMs);
  setStatus(`Playing sequence at ${params.sequenceFps} fps.`);
}

function pauseSequence() {
  if (sequenceTimer) {
    window.clearInterval(sequenceTimer);
    sequenceTimer = null;
  }
  params.sequencePlaying = false;
}

async function loadMetadataForBase(basePath) {
  return await fetchJsonStrict(dataUrlForBase(basePath, "metadata.json"), "metadata.json");
}

async function loadMetadata() {
  return await loadMetadataForBase(dataBasePath);
}

async function loadCoordinatesForBase(basePath, meta) {
  const empty = { r: null, theta: null, phi: null };
  if (!meta?.coordinates) return empty;

  const url = dataUrlForBase(basePath, meta.coordinates);
  if (jsonCache.has(url)) return jsonCache.get(url);

  const response = await fetch(url);
  if (!response.ok) {
    console.warn(`Could not load ${url}; falling back to uniform coordinates.`);
    return empty;
  }

  const raw = await response.json();
  const parsed = {
    r: Array.isArray(raw.r) ? raw.r : null,
    theta: Array.isArray(raw.theta) ? raw.theta : null,
    phi: Array.isArray(raw.phi) ? raw.phi : null,
  };
  jsonCache.set(url, parsed);
  return parsed;
}

async function loadCoordinates() {
  coords = await loadCoordinatesForBase(dataBasePath, metadata);
}

function normaliseDatasetLabel(label) {
  const raw = String(label || "D2").trim();
  const clean = raw.replace(/[:\s]+/g, "_").replace(/[^A-Za-z0-9_.-]/g, "_");
  return clean || "D2";
}

function secondaryPrefix() {
  return `${normaliseDatasetLabel(params.secondaryDatasetLabel)}:`;
}

function isSecondaryFieldName(fieldName) {
  return secondaryDataset && String(fieldName || "").startsWith(secondaryPrefix());
}

function rawSecondaryFieldName(fieldName) {
  return String(fieldName || "").slice(secondaryPrefix().length);
}

function prefixedSecondaryFieldName(rawName) {
  return `${secondaryPrefix()}${rawName}`;
}

function primaryGridSignature(meta) {
  return {
    nr: Number(meta?.nr),
    ntheta: Number(meta?.ntheta),
    nphi: Number(meta?.nphi),
  };
}

function sameGridSignature(a, b) {
  const aa = primaryGridSignature(a);
  const bb = primaryGridSignature(b);
  return aa.nr === bb.nr && aa.ntheta === bb.ntheta && aa.nphi === bb.nphi;
}

async function resolveDatasetBasePath(rootPath) {
  const root = normaliseDatasetRoot(rootPath);

  try {
    await fetchJsonStrict(dataUrlForBase(root, "metadata.json"), "metadata.json");
    return root;
  } catch (metadataError) {
    const seq = await fetchJsonStrict(dataUrlForBase(root, "sequence.json"), "sequence.json");
    if (!Array.isArray(seq.frames) || seq.frames.length === 0) {
      throw new Error(`${root}/sequence.json exists but contains no frames.`);
    }
    const frame = seq.frames[0];
    return dataUrlForBase(root, normaliseSequenceFramePath(frame.path));
  }
}

async function loadSecondaryDatasetFromParams() {
  try {
    const root = normaliseDatasetRoot(params.secondaryDatasetPath);
    const basePath = await resolveDatasetBasePath(root);
    const meta2 = await loadMetadataForBase(basePath);
    const coords2 = await loadCoordinatesForBase(basePath, meta2);

    if (!sameGridSignature(metadata, meta2)) {
      const a = primaryGridSignature(metadata);
      const b = primaryGridSignature(meta2);
      throw new Error(
        `Secondary grid does not match primary grid. ` +
        `Primary nr/ntheta/nphi=${a.nr}/${a.ntheta}/${a.nphi}; ` +
        `secondary=${b.nr}/${b.ntheta}/${b.nphi}.`
      );
    }

    secondaryDataset = {
      rootPath: root,
      basePath,
      metadata: meta2,
      coords: coords2,
      label: normaliseDatasetLabel(params.secondaryDatasetLabel),
    };
    params.secondaryDatasetPath = root;
    params.secondaryDatasetLabel = secondaryDataset.label;

    buildGui();
    setStatus(`Loaded secondary dataset ${secondaryDataset.label} from ${basePath}.`);
  } catch (err) {
    console.error(err);
    secondaryDataset = null;
    buildGui();
    setStatus(`Could not load secondary dataset: ${err.message}`);
  }
}

async function clearSecondaryDataset() {
  secondaryDataset = null;
  applyDefaultFields();
  buildGui();
  await rebuildAllMeshes();
  updateVisibility();
  setStatus("Secondary dataset cleared.");
}

async function loadFloat32ForBase(basePath, filename, expectedLength) {
  const cleanBase = String(basePath || "/data").replace(/\/+$/, "");
  const cacheKey = `${cleanBase}/${filename}`;
  if (dataCache.has(cacheKey)) {
    const info = dataCacheMeta.get(cacheKey);
    if (info) info.last = ++dataCacheCounter;
    return dataCache.get(cacheKey);
  }

  const url = dataUrlForBase(cleanBase, filename);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url}`);

  const buffer = await response.arrayBuffer();
  const arr = new Float32Array(buffer);

  if (arr.length !== expectedLength) {
    console.warn(
      `Unexpected array length for ${filename}: got ${arr.length}, expected ${expectedLength}`
    );
  }

  dataCache.set(cacheKey, arr);
  dataCacheMeta.set(cacheKey, { bytes: arr.byteLength, last: ++dataCacheCounter });
  dataCacheBytes += arr.byteLength;
  enforceDataCacheLimit();
  return arr;
}

async function loadFloat32(filename, expectedLength) {
  return await loadFloat32ForBase(dataBasePath, filename, expectedLength);
}

function resolveFieldSource(fieldName) {
  if (isSecondaryFieldName(fieldName)) {
    const rawName = rawSecondaryFieldName(fieldName);
    return {
      source: "secondary",
      displayName: String(fieldName),
      rawName,
      meta: secondaryDataset.metadata,
      basePath: secondaryDataset.basePath,
    };
  }

  return {
    source: "primary",
    displayName: String(fieldName),
    rawName: String(fieldName),
    meta: metadata,
    basePath: dataBasePath,
  };
}

async function loadField(fieldName) {
  const ref = resolveFieldSource(fieldName);
  const filename = ref.meta.fields?.[ref.rawName];
  if (!filename) throw new Error(`Field not found: ${fieldName}`);
  if (!sameGridSignature(metadata, ref.meta)) {
    throw new Error(`Field ${fieldName} is on a grid that does not match the primary dataset.`);
  }
  const expectedLength = ref.meta.nr * ref.meta.ntheta * ref.meta.nphi;
  return await loadFloat32ForBase(ref.basePath, filename, expectedLength);
}

async function loadCmbDisplayField(fieldName) {
  const ref = resolveFieldSource(fieldName);
  const surfaceInfo = ref.meta.surface_fields?.[ref.rawName];

  if (surfaceInfo) {
    if (surfaceInfo.surface !== "cmb") {
      throw new Error(`Surface field ${fieldName} is not a CMB field.`);
    }
    if (ref.meta.ntheta !== metadata.ntheta || ref.meta.nphi !== metadata.nphi) {
      throw new Error(`CMB surface field ${fieldName} does not match the primary theta/phi grid.`);
    }

    const expectedLength = ref.meta.ntheta * ref.meta.nphi;
    const data = await loadFloat32ForBase(ref.basePath, surfaceInfo.file, expectedLength);
    return { kind: "cmb_surface", name: fieldName, data, nphi: ref.meta.nphi };
  }

  const data = await loadField(fieldName);
  return { kind: "volume", name: fieldName, data };
}

function cmbValue(fieldObject, radiusIndex, it, ip) {
  if (fieldObject.kind === "cmb_surface") {
    const nphi = fieldObject.nphi || metadata.nphi;
    return fieldObject.data[it * nphi + ip];
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

function sphericalFromCartesian(x, y, z) {
  const r = Math.sqrt(x * x + y * y + z * z);
  const theta = r > 0 ? Math.acos(clamp(z / r, -1.0, 1.0)) : 0.0;
  const phi = normalizePhi(Math.atan2(y, x));
  return { r, theta, phi };
}

function sampleVolumeNearest(field, x, y, z) {
  const sph = sphericalFromCartesian(x, y, z);
  if (sph.r < metadata.r_inner || sph.r > metadata.r_outer) return NaN;
  const ir = nearestRadiusIndex(sph.r);
  const it = nearestThetaIndex(sph.theta);
  const ip = nearestPhiIndex(sph.phi);
  return field[idx(ir, it, ip)];
}

function makeIsoMaterial(color, opacity) {
  const material = new THREE.MeshPhongMaterial({
    color: new THREE.Color(color),
    side: THREE.DoubleSide,
    shininess: 25,
    transparent: true,
  });
  applyOpacityAndDepth(material, opacity);
  return material;
}

function sphericalPositionArray(r, theta, phi) {
  const st = Math.sin(theta);
  return [
    r * st * Math.cos(phi),
    r * st * Math.sin(phi),
    r * Math.cos(theta),
  ];
}

function makeSampleIndices(n, maxCount, includeLast = true) {
  const count = Math.max(2, Math.min(n, Math.round(maxCount)));
  const out = [];
  if (includeLast) {
    for (let k = 0; k < count; k++) {
      out.push(Math.round((k * (n - 1)) / Math.max(1, count - 1)));
    }
  } else {
    for (let k = 0; k < count; k++) {
      out.push(Math.floor((k * n) / count) % n);
    }
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

function interpolateIsoPoint(a, b, isoValue) {
  const denom = b.v - a.v;
  const q = Math.abs(denom) > 1.0e-30 ? clamp((isoValue - a.v) / denom, 0.0, 1.0) : 0.5;
  return [
    a.p[0] + q * (b.p[0] - a.p[0]),
    a.p[1] + q * (b.p[1] - a.p[1]),
    a.p[2] + q * (b.p[2] - a.p[2]),
  ];
}

function pushTri(positions, p0, p1, p2, clipOptions = null) {
  const centroid = [
    (p0[0] + p1[0] + p2[0]) / 3.0,
    (p0[1] + p1[1] + p2[1]) / 3.0,
    (p0[2] + p1[2] + p2[2]) / 3.0,
  ];
  if (!shouldKeepPointForIsoClip(centroid, clipOptions)) return;
  positions.push(
    p0[0], p0[1], p0[2],
    p1[0], p1[1], p1[2],
    p2[0], p2[1], p2[2]
  );
}

function polygoniseTetra(positions, tet, isoValue, clipOptions = null) {
  const inside = tet.map((v) => Number.isFinite(v.v) && v.v >= isoValue);
  const insideIdx = [];
  const outsideIdx = [];
  for (let i = 0; i < 4; i++) {
    if (inside[i]) insideIdx.push(i);
    else outsideIdx.push(i);
  }

  if (insideIdx.length === 0 || insideIdx.length === 4) return;

  if (insideIdx.length === 1 || insideIdx.length === 3) {
    const singleInside = insideIdx.length === 1;
    const a = singleInside ? insideIdx[0] : outsideIdx[0];
    const others = singleInside ? outsideIdx : insideIdx;

    const p0 = interpolateIsoPoint(tet[a], tet[others[0]], isoValue);
    const p1 = interpolateIsoPoint(tet[a], tet[others[1]], isoValue);
    const p2 = interpolateIsoPoint(tet[a], tet[others[2]], isoValue);

    if (singleInside) pushTri(positions, p0, p1, p2, clipOptions);
    else pushTri(positions, p0, p2, p1, clipOptions);
    return;
  }

  // Two inside, two outside: quadrilateral split into two triangles.
  const a = insideIdx[0];
  const b = insideIdx[1];
  const c = outsideIdx[0];
  const d = outsideIdx[1];

  const pAC = interpolateIsoPoint(tet[a], tet[c], isoValue);
  const pAD = interpolateIsoPoint(tet[a], tet[d], isoValue);
  const pBC = interpolateIsoPoint(tet[b], tet[c], isoValue);
  const pBD = interpolateIsoPoint(tet[b], tet[d], isoValue);

  pushTri(positions, pAC, pBC, pAD, clipOptions);
  pushTri(positions, pAD, pBC, pBD, clipOptions);
}

function makeSphericalGridIsosurfaceMesh(field, isoValue, color, opacity, requestedResolution, clipOptions = null) {
  const nr = metadata.nr;
  const nt = metadata.ntheta;
  const np = metadata.nphi;

  const res = Math.max(8, Math.min(96, Math.round(Number(requestedResolution))));
  const rIdx = makeSampleIndices(nr, res, true);
  const tIdx = makeSampleIndices(nt, res, true);
  const pIdx = makeSampleIndices(np, 2 * res, false);

  const positions = [];
  const tetrahedra = [
    [0, 5, 1, 6],
    [0, 1, 2, 6],
    [0, 2, 3, 6],
    [0, 3, 7, 6],
    [0, 7, 4, 6],
    [0, 4, 5, 6],
  ];

  function vertex(ir, it, ip, phiShift = 0.0) {
    const r = radiusAtIndex(ir);
    const theta = thetaAtIndex(it);
    const phi = phiAtIndex(ip) + phiShift;
    const v = field[idx(ir, it, ip)];
    return { p: sphericalPositionArray(r, theta, phi), v };
  }

  for (let ar = 0; ar < rIdx.length - 1; ar++) {
    const ir0 = rIdx[ar];
    const ir1 = rIdx[ar + 1];

    for (let at = 0; at < tIdx.length - 1; at++) {
      const it0 = tIdx[at];
      const it1 = tIdx[at + 1];

      for (let ap = 0; ap < pIdx.length; ap++) {
        const ip0 = pIdx[ap];
        const ip1 = pIdx[(ap + 1) % pIdx.length];
        const wraps = ip1 <= ip0;
        const phiShift1 = wraps ? 2.0 * Math.PI : 0.0;

        const cube = [
          vertex(ir0, it0, ip0, 0.0),
          vertex(ir1, it0, ip0, 0.0),
          vertex(ir1, it1, ip0, 0.0),
          vertex(ir0, it1, ip0, 0.0),
          vertex(ir0, it0, ip1, phiShift1),
          vertex(ir1, it0, ip1, phiShift1),
          vertex(ir1, it1, ip1, phiShift1),
          vertex(ir0, it1, ip1, phiShift1),
        ];

        for (const tet of tetrahedra) {
          polygoniseTetra(
            positions,
            [cube[tet[0]], cube[tet[1]], cube[tet[2]], cube[tet[3]]],
            Number(isoValue),
            clipOptions
          );
        }
      }
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();

  const mesh = new THREE.Mesh(geometry, makeIsoMaterial(color, opacity));
  mesh.name = "velocity-isosurface";
  mesh.userData.triangleCount = positions.length / 9;
  return mesh;
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
    [
      0.0,
      [
        40,
        60,
        180
      ]
    ],
    [
      0.5,
      [
        255,
        255,
        255
      ]
    ],
    [
      1.0,
      [
        180,
        40,
        40
      ]
    ]
  ],
  "red-white-blue": [
    [
      0.0,
      [
        180,
        40,
        40
      ]
    ],
    [
      0.5,
      [
        255,
        255,
        255
      ]
    ],
    [
      1.0,
      [
        40,
        60,
        180
      ]
    ]
  ],
  "viridis": [
    [
      0.0,
      [
        68,
        1,
        84
      ]
    ],
    [
      0.25,
      [
        59,
        82,
        139
      ]
    ],
    [
      0.5,
      [
        33,
        145,
        140
      ]
    ],
    [
      0.75,
      [
        94,
        201,
        98
      ]
    ],
    [
      1.0,
      [
        253,
        231,
        37
      ]
    ]
  ],
  "plasma": [
    [
      0.0,
      [
        13,
        8,
        135
      ]
    ],
    [
      0.25,
      [
        126,
        3,
        168
      ]
    ],
    [
      0.5,
      [
        204,
        71,
        120
      ]
    ],
    [
      0.75,
      [
        248,
        149,
        64
      ]
    ],
    [
      1.0,
      [
        240,
        249,
        33
      ]
    ]
  ],
  "inferno": [
    [
      0.0,
      [
        0,
        0,
        4
      ]
    ],
    [
      0.25,
      [
        87,
        15,
        109
      ]
    ],
    [
      0.5,
      [
        187,
        55,
        84
      ]
    ],
    [
      0.75,
      [
        249,
        142,
        8
      ]
    ],
    [
      1.0,
      [
        252,
        255,
        164
      ]
    ]
  ],
  "gray": [
    [
      0.0,
      [
        20,
        20,
        20
      ]
    ],
    [
      1.0,
      [
        245,
        245,
        245
      ]
    ]
  ],
  "batlow": [
    [
      0.0,
      [
        1,
        25,
        89
      ]
    ],
    [
      0.125,
      [
        17,
        67,
        96
      ]
    ],
    [
      0.25,
      [
        34,
        96,
        97
      ]
    ],
    [
      0.375,
      [
        77,
        115,
        77
      ]
    ],
    [
      0.5,
      [
        130,
        130,
        49
      ]
    ],
    [
      0.625,
      [
        192,
        144,
        54
      ]
    ],
    [
      0.75,
      [
        242,
        157,
        109
      ]
    ],
    [
      0.875,
      [
        253,
        180,
        182
      ]
    ],
    [
      1.0,
      [
        250,
        204,
        250
      ]
    ]
  ],
  "bamako": [
    [
      0.0,
      [
        0,
        59,
        71
      ]
    ],
    [
      0.125,
      [
        16,
        69,
        62
      ]
    ],
    [
      0.25,
      [
        37,
        82,
        49
      ]
    ],
    [
      0.375,
      [
        65,
        100,
        31
      ]
    ],
    [
      0.5,
      [
        99,
        122,
        10
      ]
    ],
    [
      0.625,
      [
        139,
        137,
        0
      ]
    ],
    [
      0.75,
      [
        181,
        161,
        36
      ]
    ],
    [
      0.875,
      [
        222,
        197,
        103
      ]
    ],
    [
      1.0,
      [
        255,
        229,
        173
      ]
    ]
  ],
  "broc": [
    [
      0.0,
      [
        44,
        26,
        76
      ]
    ],
    [
      0.125,
      [
        41,
        75,
        125
      ]
    ],
    [
      0.25,
      [
        91,
        130,
        169
      ]
    ],
    [
      0.375,
      [
        165,
        187,
        208
      ]
    ],
    [
      0.5,
      [
        235,
        238,
        236
      ]
    ],
    [
      0.625,
      [
        211,
        211,
        167
      ]
    ],
    [
      0.75,
      [
        153,
        153,
        96
      ]
    ],
    [
      0.875,
      [
        91,
        91,
        44
      ]
    ],
    [
      1.0,
      [
        38,
        38,
        0
      ]
    ]
  ],
  "cork": [
    [
      0.0,
      [
        44,
        25,
        76
      ]
    ],
    [
      0.125,
      [
        40,
        75,
        126
      ]
    ],
    [
      0.25,
      [
        86,
        127,
        166
      ]
    ],
    [
      0.375,
      [
        158,
        181,
        204
      ]
    ],
    [
      0.5,
      [
        230,
        237,
        236
      ]
    ],
    [
      0.625,
      [
        166,
        196,
        166
      ]
    ],
    [
      0.75,
      [
        91,
        146,
        91
      ]
    ],
    [
      0.875,
      [
        31,
        97,
        29
      ]
    ],
    [
      1.0,
      [
        15,
        41,
        3
      ]
    ]
  ],
  "davos": [
    [
      0.0,
      [
        0,
        5,
        74
      ]
    ],
    [
      0.125,
      [
        20,
        50,
        119
      ]
    ],
    [
      0.25,
      [
        47,
        90,
        150
      ]
    ],
    [
      0.375,
      [
        78,
        121,
        157
      ]
    ],
    [
      0.5,
      [
        108,
        142,
        147
      ]
    ],
    [
      0.625,
      [
        140,
        163,
        136
      ]
    ],
    [
      0.75,
      [
        189,
        201,
        149
      ]
    ],
    [
      0.875,
      [
        240,
        241,
        205
      ]
    ],
    [
      1.0,
      [
        254,
        254,
        254
      ]
    ]
  ],
  "devon": [
    [
      0.0,
      [
        44,
        26,
        76
      ]
    ],
    [
      0.125,
      [
        41,
        56,
        106
      ]
    ],
    [
      0.25,
      [
        41,
        88,
        143
      ]
    ],
    [
      0.375,
      [
        66,
        114,
        188
      ]
    ],
    [
      0.5,
      [
        126,
        143,
        221
      ]
    ],
    [
      0.625,
      [
        176,
        171,
        238
      ]
    ],
    [
      0.75,
      [
        203,
        198,
        244
      ]
    ],
    [
      0.875,
      [
        229,
        227,
        250
      ]
    ],
    [
      1.0,
      [
        255,
        255,
        255
      ]
    ]
  ],
  "hawaii": [
    [
      0.0,
      [
        140,
        2,
        115
      ]
    ],
    [
      0.125,
      [
        146,
        46,
        85
      ]
    ],
    [
      0.25,
      [
        151,
        78,
        62
      ]
    ],
    [
      0.375,
      [
        155,
        111,
        40
      ]
    ],
    [
      0.5,
      [
        156,
        150,
        28
      ]
    ],
    [
      0.625,
      [
        137,
        189,
        74
      ]
    ],
    [
      0.75,
      [
        107,
        212,
        142
      ]
    ],
    [
      0.875,
      [
        103,
        233,
        213
      ]
    ],
    [
      1.0,
      [
        179,
        242,
        253
      ]
    ]
  ],
  "imola": [
    [
      0.0,
      [
        26,
        51,
        179
      ]
    ],
    [
      0.125,
      [
        37,
        73,
        168
      ]
    ],
    [
      0.25,
      [
        48,
        94,
        157
      ]
    ],
    [
      0.375,
      [
        63,
        113,
        142
      ]
    ],
    [
      0.5,
      [
        84,
        134,
        127
      ]
    ],
    [
      0.625,
      [
        113,
        164,
        119
      ]
    ],
    [
      0.75,
      [
        146,
        196,
        110
      ]
    ],
    [
      0.875,
      [
        191,
        231,
        103
      ]
    ],
    [
      1.0,
      [
        255,
        255,
        102
      ]
    ]
  ],
  "lajolla": [
    [
      0.0,
      [
        25,
        25,
        0
      ]
    ],
    [
      0.125,
      [
        55,
        36,
        17
      ]
    ],
    [
      0.25,
      [
        103,
        52,
        42
      ]
    ],
    [
      0.375,
      [
        166,
        70,
        68
      ]
    ],
    [
      0.5,
      [
        217,
        96,
        78
      ]
    ],
    [
      0.625,
      [
        229,
        136,
        81
      ]
    ],
    [
      0.75,
      [
        237,
        174,
        84
      ]
    ],
    [
      0.875,
      [
        247,
        218,
        116
      ]
    ],
    [
      1.0,
      [
        255,
        254,
        203
      ]
    ]
  ],
  "lapaz": [
    [
      0.0,
      [
        26,
        12,
        100
      ]
    ],
    [
      0.125,
      [
        36,
        50,
        126
      ]
    ],
    [
      0.25,
      [
        45,
        83,
        147
      ]
    ],
    [
      0.375,
      [
        61,
        113,
        160
      ]
    ],
    [
      0.5,
      [
        92,
        140,
        163
      ]
    ],
    [
      0.625,
      [
        134,
        158,
        155
      ]
    ],
    [
      0.75,
      [
        181,
        173,
        150
      ]
    ],
    [
      0.875,
      [
        235,
        207,
        187
      ]
    ],
    [
      1.0,
      [
        254,
        242,
        243
      ]
    ]
  ],
  "lipari": [
    [
      0.0,
      [
        3,
        19,
        38
      ]
    ],
    [
      0.125,
      [
        24,
        62,
        97
      ]
    ],
    [
      0.25,
      [
        82,
        91,
        122
      ]
    ],
    [
      0.375,
      [
        120,
        95,
        114
      ]
    ],
    [
      0.5,
      [
        165,
        98,
        103
      ]
    ],
    [
      0.625,
      [
        218,
        111,
        94
      ]
    ],
    [
      0.75,
      [
        233,
        155,
        116
      ]
    ],
    [
      0.875,
      [
        231,
        196,
        154
      ]
    ],
    [
      1.0,
      [
        253,
        245,
        218
      ]
    ]
  ],
  "navia": [
    [
      0.0,
      [
        3,
        19,
        39
      ]
    ],
    [
      0.125,
      [
        7,
        57,
        102
      ]
    ],
    [
      0.25,
      [
        27,
        96,
        143
      ]
    ],
    [
      0.375,
      [
        47,
        121,
        139
      ]
    ],
    [
      0.5,
      [
        65,
        138,
        128
      ]
    ],
    [
      0.625,
      [
        90,
        161,
        113
      ]
    ],
    [
      0.75,
      [
        137,
        195,
        106
      ]
    ],
    [
      0.875,
      [
        211,
        227,
        161
      ]
    ],
    [
      1.0,
      [
        252,
        244,
        217
      ]
    ]
  ],
  "nuuk": [
    [
      0.0,
      [
        5,
        89,
        140
      ]
    ],
    [
      0.125,
      [
        45,
        100,
        131
      ]
    ],
    [
      0.25,
      [
        83,
        119,
        133
      ]
    ],
    [
      0.375,
      [
        125,
        143,
        145
      ]
    ],
    [
      0.5,
      [
        161,
        166,
        152
      ]
    ],
    [
      0.625,
      [
        181,
        181,
        145
      ]
    ],
    [
      0.75,
      [
        195,
        195,
        133
      ]
    ],
    [
      0.875,
      [
        221,
        221,
        139
      ]
    ],
    [
      1.0,
      [
        254,
        254,
        178
      ]
    ]
  ],
  "oslo": [
    [
      0.0,
      [
        1,
        1,
        1
      ]
    ],
    [
      0.125,
      [
        14,
        30,
        46
      ]
    ],
    [
      0.25,
      [
        21,
        57,
        91
      ]
    ],
    [
      0.375,
      [
        38,
        87,
        140
      ]
    ],
    [
      0.5,
      [
        80,
        123,
        188
      ]
    ],
    [
      0.625,
      [
        125,
        153,
        202
      ]
    ],
    [
      0.75,
      [
        163,
        177,
        202
      ]
    ],
    [
      0.875,
      [
        207,
        210,
        216
      ]
    ],
    [
      1.0,
      [
        255,
        255,
        255
      ]
    ]
  ],
  "roma": [
    [
      0.0,
      [
        126,
        23,
        0
      ]
    ],
    [
      0.125,
      [
        157,
        88,
        24
      ]
    ],
    [
      0.25,
      [
        182,
        140,
        50
      ]
    ],
    [
      0.375,
      [
        208,
        202,
        114
      ]
    ],
    [
      0.5,
      [
        192,
        234,
        195
      ]
    ],
    [
      0.625,
      [
        118,
        209,
        215
      ]
    ],
    [
      0.75,
      [
        56,
        156,
        198
      ]
    ],
    [
      0.875,
      [
        34,
        105,
        176
      ]
    ],
    [
      1.0,
      [
        3,
        49,
        152
      ]
    ]
  ],
  "tokyo": [
    [
      0.0,
      [
        28,
        14,
        52
      ]
    ],
    [
      0.125,
      [
        81,
        36,
        70
      ]
    ],
    [
      0.25,
      [
        108,
        71,
        80
      ]
    ],
    [
      0.375,
      [
        113,
        93,
        82
      ]
    ],
    [
      0.5,
      [
        116,
        112,
        83
      ]
    ],
    [
      0.625,
      [
        121,
        141,
        87
      ]
    ],
    [
      0.75,
      [
        135,
        184,
        103
      ]
    ],
    [
      0.875,
      [
        186,
        234,
        164
      ]
    ],
    [
      1.0,
      [
        239,
        252,
        221
      ]
    ]
  ],
  "vik": [
    [
      0.0,
      [
        0,
        18,
        97
      ]
    ],
    [
      0.125,
      [
        3,
        68,
        129
      ]
    ],
    [
      0.25,
      [
        48,
        125,
        166
      ]
    ],
    [
      0.375,
      [
        148,
        190,
        210
      ]
    ],
    [
      0.5,
      [
        236,
        229,
        224
      ]
    ],
    [
      0.625,
      [
        219,
        170,
        141
      ]
    ],
    [
      0.75,
      [
        194,
        112,
        65
      ]
    ],
    [
      0.875,
      [
        145,
        45,
        6
      ]
    ],
    [
      1.0,
      [
        89,
        0,
        8
      ]
    ]
  ]
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

      if (!shouldKeepPhiForClip(phiAtIndex(ip), clipOptions)) continue;

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

function makeGapFillerMaterial(opacity) {
  const material = new THREE.MeshPhongMaterial({
    color: new THREE.Color(0.62, 0.62, 0.62),
    side: THREE.DoubleSide,
    shininess: 4,
  });
  applyOpacityAndDepth(material, opacity);
  return material;
}

function earthRadius() {
  return Number(metadata?.r_outer || metadata?.radii?.outer || 1.0) * Number(params.earthRadiusScale);
}

function makeHorizontalGapFillerMesh(z, opacity) {
  const np = metadata.nphi;
  const rOuter = metadata.r_outer;
  const rEarth = earthRadius();
  const zAbs = Math.abs(z);
  if (zAbs >= rEarth || rEarth <= rOuter) {
    return new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  }

  const sInner = zAbs < rOuter ? Math.sqrt(Math.max(0.0, rOuter * rOuter - z * z)) : 0.0;
  const sOuter = Math.sqrt(Math.max(0.0, rEarth * rEarth - z * z));
  if (!(sOuter > sInner + 1.0e-10)) {
    return new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  }

  const positions = [];
  const indices = [];
  for (let ir = 0; ir < 2; ir++) {
    const s = ir === 0 ? sInner : sOuter;
    for (let ip = 0; ip < np; ip++) {
      const phi = phiAtIndex(ip);
      positions.push(s * Math.cos(phi), s * Math.sin(phi), z);
    }
  }
  for (let ip = 0; ip < np; ip++) {
    const ip1 = (ip + 1) % np;
    const a = ip;
    const b = ip1;
    const c = np + ip;
    const d = np + ip1;
    indices.push(a, c, b, b, c, d);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, makeGapFillerMaterial(opacity));
  mesh.name = "horizontal-gap-filler";
  return mesh;
}

function makeMeridionalGapFillerMesh(phiDeg, opacity) {
  const requestedPhi = THREE.MathUtils.degToRad(phiDeg);
  const cosPhi = Math.cos(requestedPhi);
  const sinPhi = Math.sin(requestedPhi);
  const rOuter = metadata.r_outer;
  const rEarth = earthRadius();
  if (rEarth <= rOuter) {
    return new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshBasicMaterial());
  }

  const nt = metadata.ntheta;
  const thetaExt = [0.0];
  for (let j = 0; j < nt; j++) thetaExt.push(thetaAtIndex(j));
  thetaExt.push(Math.PI);

  const columns = [];
  for (let j = 0; j < thetaExt.length; j++) columns.push({ theta: thetaExt[j], sign: 1.0 });
  for (let j = thetaExt.length - 1; j >= 0; j--) columns.push({ theta: thetaExt[j], sign: -1.0 });
  const ncol = columns.length;

  const positions = [];
  const indices = [];
  for (let ir = 0; ir < 2; ir++) {
    const r = ir === 0 ? rOuter : rEarth;
    for (const colInfo of columns) {
      const signedS = colInfo.sign * r * Math.sin(colInfo.theta);
      positions.push(
        signedS * cosPhi,
        signedS * sinPhi,
        r * Math.cos(colInfo.theta)
      );
    }
  }
  for (let jc = 0; jc < ncol; jc++) {
    const jn = (jc + 1) % ncol;
    const a = jc;
    const b = jn;
    const c = ncol + jc;
    const d = ncol + jn;
    indices.push(a, c, b, b, c, d);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, makeGapFillerMaterial(opacity));
  mesh.name = "meridional-gap-filler";
  return mesh;
}

async function rebuildGapFillers() {
  disposeObject(equatorFillerMesh); equatorFillerMesh = null;
  disposeObject(equator2FillerMesh); equator2FillerMesh = null;
  disposeObject(meridianFillerMesh); meridianFillerMesh = null;
  disposeObject(meridian2FillerMesh); meridian2FillerMesh = null;

  if (!params.showEarthSurface || !params.showSliceGapFiller) return;

  equatorFillerMesh = makeHorizontalGapFillerMesh(0.0, params.sliceGapFillerOpacity);
  equatorFillerMesh.visible = params.showEquator;
  scene.add(equatorFillerMesh);

  const z2 = clamp(Number(params.equator2Z), -1.0, 1.0) * metadata.r_outer;
  equator2FillerMesh = makeHorizontalGapFillerMesh(z2, params.sliceGapFillerOpacity);
  equator2FillerMesh.visible = params.showEquator2;
  scene.add(equator2FillerMesh);

  meridianFillerMesh = makeMeridionalGapFillerMesh(params.meridianPhiDeg, params.sliceGapFillerOpacity);
  meridianFillerMesh.visible = params.showMeridian;
  scene.add(meridianFillerMesh);

  meridian2FillerMesh = makeMeridionalGapFillerMesh(params.meridian2PhiDeg, params.sliceGapFillerOpacity);
  meridian2FillerMesh.visible = params.showMeridian2;
  scene.add(meridian2FillerMesh);
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
  const ipFront = nearestPhiIndex(requestedPhi);
  const ipBack = nearestPhiIndex(requestedPhi + Math.PI);

  const positions = [];
  const colors = [];
  const indices = [];

  // The SHTns/Gauss theta grid usually does not include the exact poles.
  // Extend it to theta=0 and theta=pi, duplicating the nearest boundary values,
  // equivalent to the RegularGridInterpolator extension used in the Python plots.
  const thetaExt = [];
  const thetaSampleIndex = [];

  for (let j = 0; j < nt + 2; j++) {
    if (j === 0) {
      thetaExt.push(0.0);
      thetaSampleIndex.push(0);
    } else if (j === nt + 1) {
      thetaExt.push(Math.PI);
      thetaSampleIndex.push(nt - 1);
    } else {
      thetaExt.push(thetaAtIndex(j - 1));
      thetaSampleIndex.push(j - 1);
    }
  }

  function poleValue(ir, it) {
    // Force the two sides to have the same colour at the pole vertices.
    // This removes the visual seam where phi and phi+pi meet at theta=0/pi.
    return 0.5 * (field[idx(ir, it, ipFront)] + field[idx(ir, it, ipBack)]);
  }

  const columns = [];

  // Positive signed half-plane: phi.
  for (let j = 0; j < thetaExt.length; j++) {
    columns.push({
      theta: thetaExt[j],
      it: thetaSampleIndex[j],
      ip: ipFront,
      sign: 1.0,
      pole: j === 0 || j === thetaExt.length - 1,
    });
  }

  // Negative signed half-plane: phi + pi, reversed so the meridional
  // coordinate is continuous around the full signed plane.
  for (let j = thetaExt.length - 1; j >= 0; j--) {
    columns.push({
      theta: thetaExt[j],
      it: thetaSampleIndex[j],
      ip: ipBack,
      sign: -1.0,
      pole: j === 0 || j === thetaExt.length - 1,
    });
  }

  const ncol = columns.length;
  const cosPhi = Math.cos(requestedPhi);
  const sinPhi = Math.sin(requestedPhi);

  for (let ir = 0; ir < nr; ir++) {
    const r = radiusAtIndex(ir);

    for (const colInfo of columns) {
      const theta = colInfo.theta;
      const signedS = colInfo.sign * r * Math.sin(theta);

      positions.push(
        signedS * cosPhi,
        signedS * sinPhi,
        r * Math.cos(theta)
      );

      const val = colInfo.pole
        ? poleValue(ir, colInfo.it)
        : field[idx(ir, colInfo.it, colInfo.ip)];
      const col = colourMap(val, vmin, vmax, colormap);
      colors.push(col.r, col.g, col.b);
    }
  }

  // Connect the signed meridional plane as one continuous annular mesh.
  // The cyclic closure connects theta=0 on both sides and removes the pole seam.
  for (let ir = 0; ir < nr - 1; ir++) {
    for (let jc = 0; jc < ncol; jc++) {
      const jn = (jc + 1) % ncol;
      const a = ir * ncol + jc;
      const b = ir * ncol + jn;
      const c = (ir + 1) * ncol + jc;
      const d = (ir + 1) * ncol + jn;
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
  const dataset = datasetRootPath ? `dataset=${datasetRootPath} | ` : "";
  const title = metadata.title ? `${metadata.title} | ` : "";
  const sim = metadata.magnetic?.classification ? `${metadata.magnetic.classification} | ` : "";
  const shownMap = {shell: "shell/internal", exterior: "exterior potential/poloidal", both: "both"};
  const lineMode = metadata.field_lines?.mode ? `B lines=${metadata.field_lines.mode}, shown=${shownMap[params.fieldLineDisplay] || params.fieldLineDisplay} | ` : "";
  const fieldText = `CMB=${params.cmbField}, ICB=${params.icbField}, Eq1=${params.equatorField}, Eq2=${params.equator2Field}, Mer1=${params.meridianField}, Mer2=${params.meridian2Field}`;
  const changed = lastFieldName ? ` | updated=${lastFieldName}` : "";
  setStatus(`${dataset}${title}${sim}${lineMode}${fieldText}${changed} | grid ${metadata.nr} x ${metadata.ntheta} x ${metadata.nphi}`);
}

async function rebuildCMB() {
  disposeObject(cmbMesh);
  cmbMesh = null;

  const fieldObject = await loadCmbDisplayField(params.cmbField);
  const [vmin, vmax] = cmbDisplayRange(fieldObject, metadata.nr - 1, "cmb");
  setColourbarForSlot("cmb", params.cmbField, vmin, vmax);

  const cmbClip = getActiveCmbClipOptions();
  cmbMesh = makeCmbSurfaceMesh(fieldObject, metadata.nr - 1, params.cmbOpacity, vmin, vmax, params.cmbColormap, cmbClip);
  cmbMesh.visible = params.showCMB;
  scene.add(cmbMesh);
  await updateEarthSurface();
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
  await rebuildGapFillers();
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
  await rebuildGapFillers();
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
  await rebuildGapFillers();
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
  await rebuildGapFillers();
  setStatusSummary(`Meridian2:${params.meridian2Field}`);
}

async function rebuildIsosurfaces() {
  disposeObject(isoPositiveMesh); isoPositiveMesh = null;
  disposeObject(isoNegativeMesh); isoNegativeMesh = null;

  if (!params.showIsosurfaces) return;

  const volumeFields = getVolumeFieldNames();
  if (!volumeFields.includes(params.isoField)) return;

  const field = await loadField(params.isoField);
  const isoClipOptions = getActiveIsoClipOptions();
  let triCount = 0;

  if (params.showIsoPositive) {
    isoPositiveMesh = makeSphericalGridIsosurfaceMesh(
      field,
      Number(params.isoPositiveValue),
      params.isoPositiveColor,
      params.isoOpacity,
      params.isoResolution,
      isoClipOptions
    );
    isoPositiveMesh.visible = params.showIsosurfaces;
    triCount += isoPositiveMesh.userData.triangleCount || 0;
    scene.add(isoPositiveMesh);
  }

  if (params.showIsoNegative) {
    isoNegativeMesh = makeSphericalGridIsosurfaceMesh(
      field,
      Number(params.isoNegativeValue),
      params.isoNegativeColor,
      params.isoOpacity,
      params.isoResolution,
      isoClipOptions
    );
    isoNegativeMesh.visible = params.showIsosurfaces;
    triCount += isoNegativeMesh.userData.triangleCount || 0;
    scene.add(isoNegativeMesh);
  }

  setStatusSummary(`Isosurfaces:${params.isoField}, triangles=${Math.round(triCount)}${params.isoClipWithMeridian ? ", clipped" : ""}`);
}

async function rebuildAllMeshes() {
  setStatus("Loading selected fields...");
  await rebuildCMB();
  await rebuildICB();
  await rebuildEquator();
  await rebuildEquator2();
  await rebuildMeridian();
  await rebuildMeridian2();
  await rebuildIsosurfaces();
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
  if (isoPositiveMesh) isoPositiveMesh.visible = params.showIsosurfaces && params.showIsoPositive;
  if (isoNegativeMesh) isoNegativeMesh.visible = params.showIsosurfaces && params.showIsoNegative;
  const fillerActive = params.showEarthSurface && params.showSliceGapFiller;
  if (equatorFillerMesh) equatorFillerMesh.visible = fillerActive && params.showEquator;
  if (equator2FillerMesh) equator2FillerMesh.visible = fillerActive && params.showEquator2;
  if (meridianFillerMesh) meridianFillerMesh.visible = fillerActive && params.showMeridian;
  if (meridian2FillerMesh) meridian2FillerMesh.visible = fillerActive && params.showMeridian2;

  if (colourbars.cmb?.row) colourbars.cmb.row.style.display = params.showCMB && cmbMesh ? "block" : "none";
  if (colourbars.icb?.row) colourbars.icb.row.style.display = params.showICB && icbMesh ? "block" : "none";
  if (colourbars.equator?.row) colourbars.equator.row.style.display = params.showEquator && equatorMesh ? "block" : "none";
  if (colourbars.equator2?.row) colourbars.equator2.row.style.display = params.showEquator2 && equator2Mesh ? "block" : "none";
  if (colourbars.meridian?.row) colourbars.meridian.row.style.display = params.showMeridian && meridianMesh ? "block" : "none";
  if (colourbars.meridian2?.row) colourbars.meridian2.row.style.display = params.showMeridian2 && meridian2Mesh ? "block" : "none";
  if (!params.showFieldLines) {
    disposeFieldLineGroups();
    hideFieldLineColourbar();
  } else {
    const requested = params.fieldLineDisplay;
    for (const [mode, group] of Object.entries(fieldLineGroups)) {
      if (!group) continue;
      group.visible = requested === "both" || requested === mode;
    }
    if (params.lineColourMode === "polarity") hideFieldLineColourbar();
  }
  setLineLegendMode(params.lineColourMode);
  axes.visible = params.showAxes;
  updateEarthSurface();
}

function updateOpacities() {
  if (cmbMesh) applyOpacityAndDepth(cmbMesh.material, params.cmbOpacity);
  if (icbMesh) applyOpacityAndDepth(icbMesh.material, params.icbOpacity);
  if (equatorMesh) applyOpacityAndDepth(equatorMesh.material, params.equatorOpacity);
  if (equator2Mesh) applyOpacityAndDepth(equator2Mesh.material, params.equator2Opacity);
  if (meridianMesh) applyOpacityAndDepth(meridianMesh.material, params.meridianOpacity);
  if (meridian2Mesh) applyOpacityAndDepth(meridian2Mesh.material, params.meridian2Opacity);
  if (isoPositiveMesh) applyOpacityAndDepth(isoPositiveMesh.material, params.isoOpacity);
  if (isoNegativeMesh) applyOpacityAndDepth(isoNegativeMesh.material, params.isoOpacity);
  if (equatorFillerMesh) applyOpacityAndDepth(equatorFillerMesh.material, params.sliceGapFillerOpacity);
  if (equator2FillerMesh) applyOpacityAndDepth(equator2FillerMesh.material, params.sliceGapFillerOpacity);
  if (meridianFillerMesh) applyOpacityAndDepth(meridianFillerMesh.material, params.sliceGapFillerOpacity);
  if (meridian2FillerMesh) applyOpacityAndDepth(meridian2FillerMesh.material, params.sliceGapFillerOpacity);
}

async function fetchFieldLineFile(filename) {
  if (!filename) return [];

  const cacheKey = `${dataBasePath}/${filename}`;
  if (fieldLineDataCache.has(cacheKey)) {
    return fieldLineDataCache.get(cacheKey);
  }

  const response = await fetch(dataUrl(filename));
  if (!response.ok) {
    console.warn(`Could not load field lines: ${filename}`);
    return [];
  }

  const lines = await response.json();
  fieldLineDataCache.set(cacheKey, lines);
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

  const stride = Math.max(1, params.lineStride);
  const material = makeLineMaterial();
  const loadedLines = [];

  const [vmin, vmax] = getFieldLineRange(lines);
  group.userData.strengthRange = [vmin, vmax];

  for (let i = 0; i < lines.length; i += stride) {
    const line = lines[i];
    if (!Array.isArray(line.points) || line.points.length < 2) continue;

    const positions = [];
    const colors = [];
    const strengths = Array.isArray(line.strength) ? line.strength : null;
    for (let j = 0; j < line.points.length; j++) {
      const p = line.points[j];
      positions.push(p[0], p[1], p[2]);
      const rawStrength = strengths ? Number(strengths[j]) : NaN;
      const c = getFieldLineVertexColor(rawStrength, line.polarity ?? 1, vmin, vmax);
      colors.push(c.r, c.g, c.b);
    }

    const geometry = new LineGeometry();
    geometry.setPositions(positions);
    geometry.setColors(colors);
    const object = new Line2(geometry, material);
    object.computeLineDistances();
    object.userData.lineMode = mode;
    group.add(object);
    loadedLines.push(line);
  }

  group.userData.lines = loadedLines;
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

  let allLoadedLines = [];
  for (const mode of modesToLoad) {
    if (!availableModes.includes(mode)) continue;

    const lines = await loadLinesForMode(mode);
    const group = makeFieldLineGroup(lines, mode);
    group.visible = params.showFieldLines;
    fieldLineGroups[mode] = group;
    scene.add(group);
    allLoadedLines = allLoadedLines.concat(group.userData.lines || []);
  }

  if (params.lineColourMode === "strength" && allLoadedLines.length > 0) {
    const [vmin, vmax] = getFieldLineRange(allLoadedLines);
    setFieldLineColourbar(vmin, vmax);
  } else {
    hideFieldLineColourbar();
  }
  setLineLegendMode(params.lineColourMode);
  updateFieldLineVisuals();
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

function getPrimaryVolumeFieldNames() {
  return Object.keys(metadata.fields || {});
}

function getSecondaryVolumeFieldNames() {
  if (!secondaryDataset?.metadata?.fields) return [];
  return Object.keys(secondaryDataset.metadata.fields).map(prefixedSecondaryFieldName);
}

function getVolumeFieldNames() {
  return [...getPrimaryVolumeFieldNames(), ...getSecondaryVolumeFieldNames()];
}

function getPrimaryCmbFieldNames() {
  const volumeFields = getPrimaryVolumeFieldNames();
  const surfaceFields = Object.entries(metadata.surface_fields || {})
    .filter(([, info]) => info.surface === "cmb")
    .map(([name]) => name);
  return [...volumeFields, ...surfaceFields];
}

function getSecondaryCmbFieldNames() {
  if (!secondaryDataset?.metadata) return [];
  const meta2 = secondaryDataset.metadata;
  const volumeFields = Object.keys(meta2.fields || {}).map(prefixedSecondaryFieldName);
  const surfaceFields = Object.entries(meta2.surface_fields || {})
    .filter(([, info]) => info.surface === "cmb")
    .map(([name]) => prefixedSecondaryFieldName(name));
  return [...volumeFields, ...surfaceFields];
}

function getCmbFieldNames() {
  return [...getPrimaryCmbFieldNames(), ...getSecondaryCmbFieldNames()];
}

function applyDefaultFields() {
  const fields = getVolumeFieldNames();
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

  folder.add(params, showParam).name("Show").onChange(() => { updateVisibility(); if (slot === "meridian" || slot === "meridian2") { rebuildCMB(); rebuildIsosurfaces(); } });
  folder.add(params, fieldParam, availableFields).name("Field").onChange(rebuildFn);
  folder.add(params, `${slot}Scale`, ["symmetric", "minmax", "manual"]).name("Scale").onChange(rebuildFn);
  folder.add(params, `${slot}Colormap`, colourMapNames).name("Colour map").onChange(rebuildFn);
  folder.add(params, `${slot}Min`).name("Manual min").onChange(rebuildFn);
  folder.add(params, `${slot}Max`).name("Manual max").onChange(rebuildFn);
  folder.add(params, opacityParam, 0.0, 1.0, 0.01).name("Opacity").onChange(updateOpacities);

  return folder;
}


const VIEW_STATE_PREFIX = "DTV1:";

function getAvailableColormapNames() {
  return Object.keys(colourStops || {});
}

function collectViewState() {
  const snapshot = { version: 1, params: {} };
  for (const [key, value] of Object.entries(params)) {
    if (typeof value !== "function") snapshot.params[key] = value;
  }
  return snapshot;
}

function encodeViewState(snapshot) {
  const json = JSON.stringify(snapshot);
  const base64 = btoa(unescape(encodeURIComponent(json)));
  return `${VIEW_STATE_PREFIX}${base64}`;
}

function decodeViewState(code) {
  const raw = String(code || "").trim();
  const payload = raw.startsWith(VIEW_STATE_PREFIX) ? raw.slice(VIEW_STATE_PREFIX.length) : raw;
  const json = decodeURIComponent(escape(atob(payload)));
  return JSON.parse(json);
}

function validFieldForState(key, value) {
  if (!["cmbField", "icbField", "equatorField", "equator2Field", "meridianField", "meridian2Field"].includes(key)) return true;
  if (key === "cmbField") return getCmbFieldNames().includes(value);
  return getVolumeFieldNames().includes(value);
}

function applySnapshotParam(key, value) {
  if (!(key in params)) return;
  if (typeof params[key] === "function") return;
  if (key.endsWith("Colormap") && !getAvailableColormapNames().includes(value)) return;
  if (key.endsWith("Scale") && !["symmetric", "minmax", "manual"].includes(value)) return;
  if (!validFieldForState(key, value)) return;
  if (key === "fieldLineDisplay" && !getAvailableFieldLineModes().includes(value)) return;
  params[key] = value;
}

async function applyViewState(snapshot) {
  const snap = snapshot?.params ? snapshot : { params: snapshot || {} };
  const requestedDataset = snap.params?.datasetPath ? normaliseDatasetRoot(snap.params.datasetPath) : null;
  if (requestedDataset && requestedDataset !== datasetRootPath) {
    params.datasetPath = requestedDataset;
    await loadDatasetFromParams();
  }

  for (const [key, value] of Object.entries(snap.params || {})) {
    if (key === "datasetPath") continue;
    applySnapshotParam(key, value);
  }
  updateLighting();
  applyCameraViewFromParams();
  buildGui();
  await rebuildAllMeshes();
  await loadFieldLines();
  await updateEarthSurface();
  updateFieldLineVisuals();
  updateOpacities();
  updateVisibility();
  setStatus("View state loaded.");
}

async function copyViewStateCode() {
  const code = encodeViewState(collectViewState());
  try {
    await navigator.clipboard.writeText(code);
    setStatus("View state code copied to clipboard.");
  } catch (err) {
    window.prompt("Copy this view state code:", code);
  }
}

function showViewStateCode() {
  const code = encodeViewState(collectViewState());
  window.prompt("Copy this view state code:", code);
}

async function loadViewStateCode() {
  const code = window.prompt("Paste a saved view state code:");
  if (!code) return;
  try {
    const snapshot = decodeViewState(code);
    await applyViewState(snapshot);
  } catch (err) {
    console.error(err);
    setStatus(`Could not load view state: ${err.message}`);
    window.alert(`Could not load view state code.\n${err.message}`);
  }
}

async function saveViewStateCode() {
  const code = encodeViewState(collectViewState());
  const blob = new Blob([code + "\n"], { type: "text/plain;charset=utf-8" });
  await saveBlob(blob, `dynamo-view-state-${Date.now()}.txt`, "view-state");
}


async function loadDatasetFromParams() {
  try {
    pauseSequence();
    datasetRootPath = rememberDatasetRoot(params.datasetPath);
    params.datasetPath = datasetRootPath;
    dataBasePath = datasetRootPath;
    sequenceIndex = null;
    secondaryDataset = null;
    params.sequenceFrame = 0;
    clearLoadedDataCaches(false);

    setStatus(`Loading dataset ${datasetRootPath}...`);
    await loadSequenceIndex(true);

    if (sequenceIndex?.frames?.length > 0) {
      const frame = sequenceIndex.frames[0];
      dataBasePath = sequenceFrameBasePath(frame);
    }

    metadata = await loadMetadata();
    await loadCoordinates();

    applyDefaultFields();
    buildGui();
    updateLighting();

    await rebuildAllMeshes();
    await loadFieldLines();
    await updateEarthSurface();
    updateVisibility();
    setStatusSummary(`dataset:${datasetRootPath}`);
  } catch (err) {
    console.error(err);
    setStatus(`Could not load dataset ${params.datasetPath}: ${err.message}`);
  }
}

function buildGui() {
  if (guiRoot) guiRoot.destroy();
  sequenceControllers.length = 0;
  const gui = new GUI({ title: "Controls" });
  guiRoot = gui;

  gui.add(params, "resetCamera").name("Reset camera view");

  const datasetFolder = gui.addFolder("Dataset");
  datasetFolder.add(params, "datasetPath").name("Primary public folder");
  datasetFolder.add(params, "reloadDataset").name("Load primary dataset");
  datasetFolder.add(params, "secondaryDatasetPath").name("Secondary public folder");
  datasetFolder.add(params, "secondaryDatasetLabel").name("Secondary label");
  datasetFolder.add(params, "loadSecondaryDataset").name("Load secondary dataset");
  datasetFolder.add(params, "clearSecondaryDataset").name("Clear secondary");
  if (secondaryDataset) {
    datasetFolder.add({ loaded: `${secondaryDataset.label}: ${secondaryDataset.basePath}` }, "loaded").name("Loaded secondary");
  }

  const sequenceFolder = gui.addFolder("Sequence playback");
  sequenceFolder.add(params, "reloadSequence").name("Reload sequence.json");
  sequenceControllers.push(sequenceFolder.add(params, "sequenceFrame", 0, Math.max(0, (sequenceIndex?.frames?.length || 1) - 1), 1).name("Frame").onChange(loadFrameByIndex));
  sequenceFolder.add(params, "sequenceFps", 0.5, 30, 0.5).name("FPS").onChange(() => { if (sequenceTimer) playSequence(); });
  sequenceFolder.add(params, "sequenceMaxCachedFrames", 1, 20, 1).name("Preload frames");
  sequenceFolder.add(params, "sequenceCacheLimitMB", 128, 8192, 64).name("Cache limit MB").onChange(enforceDataCacheLimit);
  sequenceFolder.add(params, "preloadSequenceFrames").name("Preload current view");
  sequenceFolder.add(params, "clearSequenceCache").name("Clear cache");
  sequenceFolder.add(params, "playSequence").name("Play");
  sequenceFolder.add(params, "pauseSequence").name("Pause");

  const stateFolder = gui.addFolder("View state");
  stateFolder.add(params, "copyViewStateCode").name("Copy code");
  stateFolder.add(params, "showViewStateCode").name("Show code");
  stateFolder.add(params, "loadViewStateCode").name("Load code");
  stateFolder.add(params, "saveViewStateCode").name("Save code to file");

  const volumeFields = getVolumeFieldNames();
  const cmbFields = getCmbFieldNames();

  const cmbFolder = addDisplayControls(gui, "cmb", "CMB surface", "cmbField", "showCMB", "cmbOpacity", rebuildCMB, cmbFields);
  const icbFolder = addDisplayControls(gui, "icb", "ICB surface", "icbField", "showICB", "icbOpacity", rebuildICB, volumeFields);
  const eqFolder = addDisplayControls(gui, "equator", "Equatorial slice 1", "equatorField", "showEquator", "equatorOpacity", rebuildEquator, volumeFields);
  const eq2Folder = addDisplayControls(gui, "equator2", "Equatorial slice 2", "equator2Field", "showEquator2", "equator2Opacity", rebuildEquator2, volumeFields);
  eq2Folder.add(params, "equator2Z", -0.95, 0.95, 0.01).name("z / r_o").onChange(rebuildEquator2);
  const merFolder = addDisplayControls(gui, "meridian", "Meridional slice 1", "meridianField", "showMeridian", "meridianOpacity", rebuildMeridian, volumeFields);
  merFolder.add(params, "meridianPhiDeg", 0, 360, 1).name("Longitude phi").onChange(() => { rebuildMeridian(); rebuildCMB(); rebuildIsosurfaces(); });

  const mer2Folder = addDisplayControls(gui, "meridian2", "Meridional slice 2", "meridian2Field", "showMeridian2", "meridian2Opacity", rebuildMeridian2, volumeFields);
  mer2Folder.add(params, "meridian2PhiDeg", 0, 360, 1).name("Longitude phi").onChange(() => { rebuildMeridian2(); rebuildCMB(); rebuildIsosurfaces(); });

  merFolder.add(params, "cmbClipWithMeridian").name("Clip CMB with meridians").onChange(() => { rebuildCMB(); rebuildIsosurfaces(); });
  merFolder.add(params, "cmbClipMode", { None: "none", "Rear half": "rear-half", "Between meridional planes (behind)": "between-meridians-behind" }).name("CMB clip mode").onChange(() => { rebuildCMB(); rebuildIsosurfaces(); });
  merFolder.add(params, "cmbRearSide", { Rear: "positive", Front: "negative" }).name("CMB side").onChange(() => { rebuildCMB(); rebuildIsosurfaces(); });

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

  const lineFolder = gui.addFolder("Magnetic field lines");
  const lineModes = getAvailableFieldLineModes();
  if (lineModes.length > 0) {
    if (!lineModes.includes(params.fieldLineDisplay)) params.fieldLineDisplay = lineModes[0];
    lineFolder.add(params, "showFieldLines").name("Show").onChange(onFieldLineVisibilityChanged);
    const lineModeOptions = {};
    if (lineModes.includes("shell")) lineModeOptions["Shell/internal"] = "shell";
    if (lineModes.includes("exterior")) lineModeOptions["Exterior potential/poloidal"] = "exterior";
    if (lineModes.includes("both")) lineModeOptions["Both"] = "both";
    lineFolder.add(params, "fieldLineDisplay", lineModeOptions).name("Line type").onChange(loadFieldLines);
    lineFolder.add(params, "lineStride", 1, 10, 1).name("Line stride").onChange(loadFieldLines);
    lineFolder.add(params, "lineColourMode", { Strength: "strength", Polarity: "polarity" }).name("Colour by").onChange(loadFieldLines);
    lineFolder.add(params, "lineColormap", colourMapNames).name("Colour map").onChange(loadFieldLines);
    lineFolder.add(params, "lineValueTransform", { Linear: "linear", "log10(|B|)": "log10" }).name("Value scale").onChange(loadFieldLines);
    lineFolder.add(params, "lineScale", ["minmax", "manual"]).name("Range").onChange(loadFieldLines);
    lineFolder.add(params, "lineMin").name("Manual min").onChange(loadFieldLines);
    lineFolder.add(params, "lineMax").name("Manual max").onChange(loadFieldLines);
    lineFolder.add(params, "lineWidthPx", 1, 12, 0.25).name("Thickness px").onChange(updateFieldLineVisuals);
    lineFolder.add(params, "lineOpacity", 0.05, 1.0, 0.01).name("Opacity").onChange(updateFieldLineVisuals);
  } else {
    params.showFieldLines = false;
  }

  const isoFolder = gui.addFolder("Isosurfaces");
  if (!volumeFields.includes(params.isoField) && volumeFields.length > 0) params.isoField = volumeFields[0];
  isoFolder.add(params, "showIsosurfaces").name("Show").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "isoField", volumeFields).name("Field").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "isoResolution", 16, 80, 2).name("Resolution").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "isoClipWithMeridian").name("Clip with meridians").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "isoClipOffsetMeridian1", -1.0, 1.0, 0.01).name("Clip offset M1").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "isoClipOffsetMeridian2", -1.0, 1.0, 0.01).name("Clip offset M2").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "showIsoPositive").name("Show positive").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "isoPositiveValue").name("Positive value").onChange(rebuildIsosurfaces);
  isoFolder.addColor(params, "isoPositiveColor").name("Positive color").onChange(() => { if (isoPositiveMesh) isoPositiveMesh.material.color.set(params.isoPositiveColor); });
  isoFolder.add(params, "showIsoNegative").name("Show negative").onChange(rebuildIsosurfaces);
  isoFolder.add(params, "isoNegativeValue").name("Negative value").onChange(rebuildIsosurfaces);
  isoFolder.addColor(params, "isoNegativeColor").name("Negative color").onChange(() => { if (isoNegativeMesh) isoNegativeMesh.material.color.set(params.isoNegativeColor); });
  isoFolder.add(params, "isoOpacity", 0.05, 1.0, 0.01).name("Opacity").onChange(updateOpacities);

  const earthFolder = gui.addFolder("Earth surface");
  earthFolder.add(params, "showEarthSurface").name("Show").onChange(updateEarthSurface);
  earthFolder.add(params, "earthLongitudeDeg", -180, 180, 1).name("Texture longitude").onChange(updateEarthSurface);
  earthFolder.add(params, "earthRadiusScale", 1.0, 2.5, 0.01).name("Radius / core").onChange(updateEarthSurface);
  earthFolder.add(params, "earthOpacity", 0.05, 1.0, 0.01).name("Opacity").onChange(updateEarthSurface);
  earthFolder.add(params, "showSliceGapFiller").name("Slice gap filler").onChange(rebuildGapFillers);
  earthFolder.add(params, "sliceGapFillerOpacity", 0.0, 1.0, 0.01).name("Filler opacity").onChange(updateOpacities);

  const other = gui.addFolder("Other visualisation");
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


function getVisibleColourbarSlots() {
  return displaySlots.filter((slot) => {
    const bar = colourbars[slot];
    return bar?.row && bar.row.style.display !== "none";
  });
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
    const scheme = slot === "fieldlines" ? (params.lineColormap || "viridis") : (params[`${slot}Colormap`] || "blue-white-red");

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
    updateFieldLineVisuals();
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
    updateFieldLineVisuals();
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
  updateFieldLineVisuals();
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  videoState.resizedRenderer = true;
}

function restoreRendererAfterVideo() {
  if (!videoState.resizedRenderer) return;
  renderer.setPixelRatio(videoState.previousPixelRatio);
  renderer.setSize(videoState.previousRendererSize.x, videoState.previousRendererSize.y, false);
  updateFieldLineVisuals();
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
  let started = false;

  for (let attempt = 0; attempt < 3 && !started; attempt++) {
    try {
      const message = attempt === 0 ? null : [
        `Could not load dataset: ${params.datasetPath}`,
        "",
        "Enter another dataset folder under public/.",
        "",
        "Examples:",
        "  /data",
        "  /data_run2",
        "  /datasets/run_A"
      ].join("\n");

      datasetRootPath = rememberDatasetRoot(askForDatasetRoot(message));
      params.datasetPath = datasetRootPath;
      dataBasePath = datasetRootPath;
      sequenceIndex = null;
      params.sequenceFrame = 0;
      clearLoadedDataCaches(false);

      setStatus(`Loading metadata from ${datasetRootPath}...`);
      await loadSequenceIndex(true);

      if (sequenceIndex?.frames?.length > 0) {
        const frame = sequenceIndex.frames[clamp(Math.round(params.sequenceFrame), 0, sequenceIndex.frames.length - 1)];
        dataBasePath = sequenceFrameBasePath(frame);
      }

      metadata = await loadMetadata();
      await loadCoordinates();

      applyDefaultFields();
      syncCameraParamsFromCamera(false);
      buildGui();
      bindExportPanelButtons();
      updateLighting();

      await rebuildAllMeshes();
      await loadFieldLines();
      await updateEarthSurface();

      animate();
      started = true;
    } catch (err) {
      console.error(err);
      setStatus(`Error loading ${params.datasetPath}: ${err.message}`);
      if (attempt === 2) {
        buildGui();
        bindExportPanelButtons();
      }
    }
  }
}

window.addEventListener("resize", () => {
  if (videoState.active) return;
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  updateFieldLineVisuals();
  syncCameraParamsFromCamera(true);
});

init();
