// Code-level regressions against the actual viewer functions. Rendering and
// network objects are small test doubles; this is not a browser/GPU test suite.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";
import { SURFACE_TEXTURES } from "../src/surface-textures.js";
import * as RealTHREE from "three";
import { fieldRadialDomain } from "../src/volume-domain.js";
import { isosurfaceLegendEntries, updateIsosurfaceLegend } from "../src/isosurface-legend.js";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { peakLineStrength, estimateTubeBytes, makeMagneticTubeGeometry, simplifyMagneticLine } from "../src/field-line-tubes.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { prepareTubeLines, executeGeometryJob, unpackGeometry } from "../src/geometry-jobs.js";
import { readResponseWithProgress } from "../src/work-progress.js";

const source = fs.readFileSync(new URL("../src/main.js", import.meta.url), "utf8");
function definition(name) {
  const match = source.match(new RegExp(`(?:async )?function ${name}\\(`));
  assert.ok(match, `Viewer function ${name} exists`);
  return source.slice(match.index, source.indexOf("\n}", match.index) + 2);
}
function constant(name, end = ";") {
  const start = source.indexOf(`const ${name} = `);
  assert.ok(start >= 0, `Viewer constant ${name} exists`);
  return source.slice(start, source.indexOf(end, start) + end.length);
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
class Geometry {
  constructor(field, value) {
    this.field = field;
    this.value = value;
    this.attributes = { position: { array: new Float32Array(9) } };
    this.disposed = false;
  }
  dispose() { this.disposed = true; }
}
class Color {
  constructor(value) { this.value = value; }
  set(value) { this.value = value; return this; }
}
class Material {
  constructor(options = {}) {
    Object.assign(this, options);
    this.color = options.color instanceof Color ? options.color : new Color(options.color);
    this.disposed = false;
  }
  dispose() { this.disposed = true; }
}
class Mesh {
  constructor(geometry, material) { this.geometry = geometry; this.material = material; this.userData = {}; }
}

function viewer() {
  const ctx = vm.createContext({
    fieldRadialDomain, isosurfaceLegendEntries, updateIsosurfaceLegend, isoLegendEl: null,
    console, DOMException, Response, Blob, AbortController, performance, TextEncoder, Float32Array, btoa, atob,
    SURFACE_TEXTURES, peakLineStrength, estimateTubeBytes, makeMagneticTubeGeometry, simplifyMagneticLine,
    viewerStatus: { clear: () => {}, version: 0 },
    geometryClient: { cancelAll() {} },
    workProgress: { begin: () => ({ update() {}, finish() {} }) },
    buildIsosurfaceInBackground: async (context, field, value) =>
      ctx.makeSphericalGridIsosurfaceMesh(field, value).geometry,
    buildTubeGeometriesInBackground: async () => null,
    prepareTubeLinesInBackground: async (selected, context) => prepareTubeLines({
      selected, settings: context.params, radius: Number(context.metadata.r_outer),
      limitBytes: ctx.tubeGeometryLimitMiB() * 1024 ** 2,
    }),
    window: { setInterval, clearInterval, setTimeout, clearTimeout },
    DEFAULT_DATASET_ROOT: "demo", DEFAULT_SECONDARY_DATASET_ROOT: "secondary",
    THREE: { Mesh, Color, MeshPhongMaterial: Material, DoubleSide: 2, NormalBlending: 1, NoBlending: 0 },
    metadata: { nr: 3, ntheta: 3, nphi: 4, r_inner: 0.35, r_outer: 1,
      fields: { ur: "ur.f32", Br: "Br.f32", T: "T.f32", C: "C.f32" } },
    coords: { r: [0.35, 0.7, 1], theta: [0.1, 1.5, 3.0], phi: [0, Math.PI / 2, Math.PI, 3 * Math.PI / 2] },
    dataBasePath: "demo", datasetRootPath: "demo", secondaryDataset: null,
    activeDatasetFolderSource: null, datasetFolderSources: new Map(),
    datasetFolderSourceCounter: 0, datasetFolderSelectionInProgress: false,
    datasetLoadInProgress: false, sequenceFrameLoading: false, datasetViewSaveInProgress: false,
    datasetRequestSignal: null, sequenceIndex: null,
    renderEpoch: 0, heavyCacheGeneration: 0, cacheAccessCounter: 0,
    heavyObjectCacheBytes: 0, dataCacheBytes: 0, fieldLineDataCacheBytes: 0,
    renderRequestVersions: new Map(), heavyCachePins: new Map(),
    isosurfaceObjectCache: new Map(), isosurfaceBuildPromises: new Map(),
    fieldLineObjectCache: new Map(), fieldLineBuildPromises: new Map(),
    dataCache: new Map(), dataCacheMeta: new Map(), jsonCache: new Map(),
    fieldLineDataCache: new Map(), fieldLineDataCacheMeta: new Map(),
    fieldLineGroups: { shell: null, exterior: null },
    scene: { objects: new Set(), add(obj) { this.objects.add(obj); }, remove(obj) { this.objects.delete(obj); } },
    getActiveIsoClipOptions: () => null,
    setStatusSummary: () => {}, setStatus: () => {},
    syncCameraParamsFromCamera: () => {},
    hideColourbarForSlot: () => {}, setColourbarForSlot: () => {},
    hideFieldLineColourbar: () => {}, setFieldLineColourbar: () => {},
    setLineLegendMode: () => {}, updateLineMaterialResolution: () => {},
    getFieldLineRange: () => [0, 1],
    horizontalSliceRange: () => [-1, 1], rebuildGapFillers: async () => {},
    makeHorizontalSliceMesh: field => new Mesh(new Geometry(field), new Material()),
    normaliseDatasetRoot: root => root,
    updateLighting: () => {}, updateBackgroundColor: () => {},
    applyCameraViewFromParams: () => {}, applyTitleLayout: () => {}, applyLegendLayout: () => {},
    applyExportPanelLayout: () => {}, buildGui: () => {}, updateVisibility: () => {},
    getAvailableColormapNames: () => ["blue-white-red", "viridis"],
    getCmbFieldNames: () => ["Br", "T", "C", "ur"],
    getEarthFieldNames: () => ["Br_Earth_lmax13"],
    PANEL_POSITIONS: new Set(["custom", "top-left", "left-center", "bottom-right"]),
    OPAQUE_OPACITY: 0.999,
    CUSTOM_COLOURMAP: "custom",
    fetchDatasetResource: async () => { throw new Error("Unexpected network request in unit test"); },
    readDatasetResponse: (response, method) => response[method](),
    releaseDatasetResponse: () => {},
    dataUrlForBase: (base, file) => `${base}/${file}`,
    loadField: async name => ({ name }),
    makeSphericalGridIsosurfaceMesh: (field, value, color, opacity) => {
      const mesh = new Mesh(new Geometry(field, value), new Material({ color, opacity }));
      mesh.userData.triangleCount = 1;
      return mesh;
    },
    makeFieldLineGroup: (lines, mode, selectedLines = lines) => {
      const group = new Mesh(new Geometry(mode), new Material({ linewidth: 2 }));
      group.userData.lines = selectedLines;
      group.traverse = callback => callback(group);
      return group;
    },
  });
  for (const name of ["cmbMesh", "icbMesh", "radialSurfaceMesh", "equatorMesh", "equator2Mesh", "meridianMesh", "meridian2Mesh", "earthMesh", "isoPositiveMesh", "isoNegativeMesh", "equatorFillerMesh", "equator2FillerMesh", "meridianFillerMesh", "meridian2FillerMesh"]) ctx[name] = null;
  vm.runInContext(constant("TUBE_MEMORY_LIMITS"), ctx);
  vm.runInContext(constant("params", "\n};") + "\nglobalThis.params = params;", ctx);
  for (const name of ["VIEW_STATE_PREFIX", "LEGACY_VIEW_STATE_PREFIX", "VIEW_STATE_EXCLUDED_PARAMS", "VIEW_STATE_PARAM_TYPES", "DEFAULT_VIEW_PARAMS", "VIEW_STATE_SCALE_KEYS", "VIEW_STATE_NUMBER_LIMITS", "DATASET_FIELD_PARAM_KEYS", "DATASET_VIEW_FILENAME", "DATASET_VIEW_TIMEOUT_MS", "MAX_DATASET_VIEW_CODE_LENGTH", "DATASET_FETCH_TIMEOUT_MS"]) {
    vm.runInContext(constant(name), ctx);
  }
  Object.assign(ctx.params, { showIsosurfaces: true, showIsoNegative: false });
  for (const name of [
    "fieldDisplayDomain", "refreshIsosurfaceLegend", "clamp", "formatBytes", "roundedCacheNumber", "captureRenderContext", "renderContextIsCurrent",
    "withCapturedRenderContext", "renderSignature", "beginRenderRequest", "renderRequestIsCurrent",
    "invalidateRenderRequests", "loadForRender", "pinHeavyCacheEntry", "isEffectivelyOpaque", "applyOpacityAndDepth",
    "normaliseDatasetLabel", "secondaryPrefix", "isSecondaryFieldName", "rawSecondaryFieldName", "prefixedSecondaryFieldName",
    "resolveFieldSource", "getPrimaryVolumeFieldNames", "getSecondaryVolumeFieldNames", "getVolumeFieldNames",
    "normaliseScalarFieldMetadata", "canonicalScalarFieldName", "migrateLegacyScalarFieldName",
    "normalizePhi", "isAngleInCCWSector", "getFourSectorBoundaries", "getSectorIndexForPhi", "shouldKeepSurfaceCellForClip",
    "meridianSidesAreIndependent", "syncLinkedMeridianSide", "meridianFieldSummary",
    "getIsosurfaceObjectCacheKey", "getFieldLineObjectCacheKey", "buildIsosurfaceObjectCacheEntry",
    "ensureIsosurfaceObjectCacheEntry", "detachActiveIsosurfaces", "rebuildIsosurfaces", "makeIsoMaterial",
    "geometryMemoryBytes", "object3DMemoryBytes", "isActiveIsosurfaceEntry", "isActiveFieldLineEntry",
    "removeIsosurfaceCacheEntry", "removeFieldLineObjectCacheEntry", "enforceCacheMemoryLimit", "cacheLimitBytes", "totalCacheBytes",
    "disposeMeshResources", "disposeFieldLineGroupResources", "detachActiveFieldLineGroups", "disposeHeavyPlaybackCaches",
    "primaryGridSignature", "sameGridSignature", "sameCoordinateArrays", "samePlaybackGrid",
    "uniformDatasetCoordinates", "validateDatasetCoordinates", "validateDatasetMetadata", "loadCoordinatesForBase",
    "validFieldForState", "applySnapshotParam", "collectViewState", "encodeViewState", "decodeViewState",
    "getAvailableFieldLineModes", "updateOpacities", "preloadHeavyObjectsForFrame",
    "loadFrameByIndex", "rebuildEquator", "disposeObject", "fetchFieldLineFile",
    "getFieldLineFilename", "loadLinesForMode", "inferLineType", "fieldLinePairKey", "selectFieldLinesByStride",
    "buildFieldLineObjectCacheEntry", "ensureFieldLineObjectCacheEntry", "loadFieldLines", "updateFieldLineVisuals",
    "tubeGeometryLimitMiB", "checkTubeGeometryBudget", "checkFieldLineEntryBudget", "addTubeMemoryControls",
    "applyViewStateParams", "applyDefaultDatasetView", "refreshViewPresentation", "applyViewState", "loadDatasetViewState",
    "updateEarthSurface", "ensureEarthTexture", "updateSurfaceAttribution",
    "viewStateBlob", "writeDatasetViewFile", "saveViewStateCode", "downloadViewStateCode",
    "parseFolderSourcePath", "fileFromDirectoryHandle", "parseLocalFilesystemPath", "encodeLocalFilesystemPath",
    "captureDatasetState", "restoreDatasetState", "loadDatasetFromParams",
  ]) vm.runInContext(definition(name), ctx);
  return ctx;
}

function presetCode(ctx, values = {}) {
  return ctx.encodeViewState({ version: 2, scope: "view-only", params: values });
}

test("duplicate scalar choices disappear for old primary and secondary bundles without mutating their metadata", () => {
  const ctx = viewer();
  const old = { fields: { Cnom0: "Cnom0.f32", C_nom0: "duplicate.f32", Comp_nom0: "legacy-comp.f32", C: "C.f32" },
    ranges: { Cnom0: { min: -1 }, C_nom0: { min: -2 }, Comp_nom0: { min: -3 } } };
  ctx.metadata = ctx.normaliseScalarFieldMetadata(old);
  ctx.secondaryDataset = { metadata: ctx.normaliseScalarFieldMetadata(old) };
  ctx.params.secondaryDatasetLabel = "D2";
  assert.deepEqual(Array.from(ctx.getVolumeFieldNames()), ["Cnom0", "C", "Compnom0", "D2:Cnom0", "D2:C", "D2:Compnom0"]);
  assert.equal(ctx.metadata.fields.Cnom0, "Cnom0.f32");
  assert.equal(ctx.metadata.fields.Compnom0, "legacy-comp.f32");
  assert.equal(ctx.metadata.ranges.Cnom0.min, -1);
  assert.equal(ctx.metadata.ranges.Compnom0.min, -3);
  assert.equal(old.fields.C_nom0, "duplicate.f32");
  assert.deepEqual(ctx.normaliseScalarFieldMetadata(ctx.metadata), ctx.metadata);
});

test("version-2 composition C_nom0 remains a canonical viewer field", () => {
  const ctx = viewer();
  const current = { scalar_naming_version: 2,
    fields: { T: "T_volume.f32", C: "C_volume.f32", C_nom0: "C_nom0_volume.f32" } };
  assert.equal(ctx.normaliseScalarFieldMetadata(current), current);
  ctx.metadata = current;
  assert.equal(ctx.canonicalScalarFieldName("C_nom0"), "C_nom0");
});

test("legacy scalar selections in view codes map to canonical primary and secondary fields", () => {
  const ctx = viewer();
  ctx.metadata.fields = { Cnom0: "Cnom0.f32", Compnom0: "Compnom0.f32" };
  ctx.secondaryDataset = { metadata: ctx.metadata };
  ctx.params.secondaryDatasetLabel = "D2";
  const code = presetCode(ctx, { equatorField: "C_nom0", meridianField: "D2:Comp_nom0", isoField: "Comp_nom0" });
  assert.equal(ctx.applyViewStateParams(ctx.decodeViewState(code)).length, 0);
  assert.equal(ctx.params.equatorField, "Cnom0");
  assert.equal(ctx.params.meridianField, "D2:Compnom0");
  assert.equal(ctx.params.isoField, "Compnom0");
  assert.equal(ctx.canonicalScalarFieldName("grad_rC_full"), "grad_rC_full");
});

test("legacy scalar view names migrate by meaning for naming-version-2 bundles", () => {
  const ctx = viewer();
  ctx.metadata = {
    scalar_naming_version: 2,
    fields: {
      T: "T_volume.f32", C: "C_volume.f32",
      T_nom0: "T_nom0_volume.f32", C_nom0: "C_nom0_volume.f32",
      grad_sT: "grad_sT_volume.f32", grad_sT_nom0: "grad_sT_nom0_volume.f32",
      grad_sC: "grad_sC_volume.f32", grad_sC_nom0: "grad_sC_nom0_volume.f32",
      N2: "N2_volume.f32", N2_nom0: "N2_nom0_volume.f32",
    },
  };
  const legacy = ctx.decodeViewState(presetCode(ctx, {
    equatorField: "C", equator2Field: "Comp",
    meridianField: "grad_sC_full", meridianLeftField: "grad_sC",
    meridian2Field: "grad_sComp_full", meridian2LeftField: "grad_sComp",
    isoField: "N2_full",
  }));
  assert.deepEqual(Array.from(ctx.applyViewStateParams(legacy)), []);
  assert.equal(ctx.params.equatorField, "T");
  assert.equal(ctx.params.equator2Field, "C");
  assert.equal(ctx.params.meridianField, "grad_sT");
  assert.equal(ctx.params.meridianLeftField, "grad_sT_nom0");
  assert.equal(ctx.params.meridian2Field, "grad_sC");
  assert.equal(ctx.params.meridian2LeftField, "grad_sC_nom0");
  assert.equal(ctx.params.isoField, "N2");
  assert.equal(ctx.collectViewState().scalarNamingVersion, 2);
});

test("older view codes mirror each meridian setting to its new left half", () => {
  const ctx = viewer();
  ctx.metadata.fields = { C: "C.f32", Br: "Br.f32" };
  const old = ctx.decodeViewState(presetCode(ctx, {
    meridianField: "Br", meridianScale: "manual", meridianMin: -4,
    meridianMax: 7, meridianColormap: "viridis", meridianOpacity: .35,
    meridian2Field: "C", meridian2Colormap: "viridis",
  }));
  assert.deepEqual(Array.from(ctx.applyViewStateParams(old)), []);
  assert.equal(ctx.params.meridianLeftField, "Br");
  assert.equal(ctx.params.meridianLeftScale, "manual");
  assert.equal(ctx.params.meridianLeftMin, -4);
  assert.equal(ctx.params.meridianLeftMax, 7);
  assert.equal(ctx.params.meridianLeftColormap, "viridis");
  assert.equal(ctx.params.meridianLeftOpacity, .35);
  assert.equal(ctx.params.meridian2LeftField, "C");
  assert.equal(ctx.params.meridian2LeftColormap, "viridis");
  assert.equal(ctx.params.meridianIndependentSides, false);
  assert.equal(ctx.params.meridian2IndependentSides, false);
  const roundTrip = ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  assert.equal(roundTrip.params.meridianLeftField, "Br");
});

test("meridian halves are linked by default and preserve explicit independent legacy views", () => {
  const ctx = viewer();
  ctx.metadata.fields = { C: "C.f32", Br: "Br.f32" };
  ctx.params.meridianField = "Br";
  ctx.params.meridianLeftField = "C";
  ctx.params.meridianLeftColormap = "viridis";
  ctx.syncLinkedMeridianSide("meridian");
  assert.equal(ctx.params.meridianLeftField, "Br");
  assert.equal(ctx.params.meridianLeftColormap, ctx.params.meridianColormap);
  assert.equal(ctx.meridianFieldSummary("meridian"), "Br");

  const split = ctx.decodeViewState(presetCode(ctx, {
    meridianField: "C", meridianLeftField: "Br",
    meridianColormap: "blue-white-red", meridianLeftColormap: "viridis",
  }));
  assert.deepEqual(Array.from(ctx.applyViewStateParams(split)), []);
  assert.equal(ctx.params.meridianIndependentSides, true);
  assert.equal(ctx.params.meridianLeftField, "Br");
  assert.equal(ctx.meridianFieldSummary("meridian"), "C/Br");
  assert.deepEqual(Array.from(ctx.applyViewStateParams({ backgroundColor: "#112233" })), []);
  assert.equal(ctx.params.meridianIndependentSides, true,
    "an unrelated partial view must not relink an existing split meridian");
});

test("front and rear choose opposite CMB sectors between two meridians", () => {
  const ctx = viewer();
  const options = {
    enabled: true, mode: "between-meridians-behind", hasTwoPlanes: true,
    phiA: 0, phiB: Math.PI / 2, side: "positive",
  };
  assert.equal(ctx.shouldKeepSurfaceCellForClip(Math.PI / 2, Math.PI / 4, options), false);
  assert.equal(ctx.shouldKeepSurfaceCellForClip(Math.PI / 2, Math.PI, options), true);
  options.side = "negative";
  assert.equal(ctx.shouldKeepSurfaceCellForClip(Math.PI / 2, Math.PI / 4, options), true);
  assert.equal(ctx.shouldKeepSurfaceCellForClip(Math.PI / 2, Math.PI, options), false);
});

function surfaceViewer() {
  const ctx = viewer(), loads = [], elements = new Map();
  const element = () => ({ style: {}, children: [], textContent: "",
    replaceChildren(...children) { this.children = children; } });
  Object.assign(ctx, {
    surfaceTextures: new Map(), surfaceTexturePromises: new Map(), SURFACE_TEXTURE_CACHE_SIZE: 3,
    renderer: { capabilities: { getMaxAnisotropy: () => 16 } },
    appPublicUrl: path => `https://example.test/DEEP/${path}`,
    document: {
      getElementById: id => elements.get(id), createElement: element,
      createTextNode: text => ({ textContent: text }),
      body: { appendChild: node => elements.set(node.id, node) },
    },
    getActiveCmbClipOptions: () => null,
    makeEarthSurfaceMesh: (radius, opacity, texture, longitude) => {
      const obj = new Mesh(new Geometry(radius, longitude), new Material({ opacity, map: texture.clone() }));
      return obj;
    },
    THREE: { ...RealTHREE, TextureLoader: class {
      setCrossOrigin() {}
      load(url, resolve, _progress, reject) { loads.push({ url, resolve, reject }); }
    } },
  });
  ctx.params.showEarthSurface = true;
  return { ctx, loads, elements };
}

test("all planet selections survive view-code round trips without loading a different dataset", () => {
  const ctx = viewer();
  for (const body of Object.keys(SURFACE_TEXTURES)) {
    ctx.params.earthTextureBody = body;
    ctx.params.earthLongitudeDeg = 42;
    ctx.params.earthRadiusScale = 1.2;
    const snapshot = ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
    ctx.params.earthTextureBody = "earth";
    ctx.applyViewStateParams(snapshot);
    assert.equal(ctx.params.earthTextureBody, body);
    assert.equal(ctx.params.earthRadiusScale, 1.2);
    assert.equal(ctx.params.earthLongitudeDeg, 42);
    assert.equal(ctx.dataBasePath, "demo");
    assert.equal(ctx.params.earthField, "Br_Earth_lmax13");
  }
  assert.equal(ctx.applySnapshotParam("earthTextureBody", "unknown"), false);
  assert.equal(ctx.applySnapshotParam("earthTextureBody", "__proto__"), false);
  assert.equal(ctx.applySnapshotParam("earthTextureBody", "constructor"), false);
});

test("older full view codes select Earth while partial changes preserve the selected body", () => {
  const ctx = viewer();
  ctx.params.earthTextureBody = "mars";
  ctx.applyViewStateParams({ earthOpacity: 0.5 });
  assert.equal(ctx.params.earthTextureBody, "mars");
  ctx.applyViewStateParams({ version: 2, scope: "view-only", params: { earthOpacity: 0.7 } });
  assert.equal(ctx.params.earthTextureBody, "earth");
});

test("rapid body changes display only the latest requested image and its matching credit", async () => {
  const { ctx, loads, elements } = surfaceViewer();
  ctx.params.earthTextureBody = "mars";
  const first = ctx.updateEarthSurface();
  ctx.params.earthTextureBody = "moon";
  const second = ctx.updateEarthSurface();
  assert.match(loads[0].url, /\/DEEP\/assets\/surfaces\/mars.jpg$/);
  const moon = new RealTHREE.Texture();
  loads[1].resolve(moon);
  await second;
  const displayed = ctx.earthMesh;
  assert.equal(displayed.userData.viewerTopology.body, "moon");
  assert.equal(displayed.material.map.source, moon.source);
  loads[0].resolve(new RealTHREE.Texture());
  await first;
  assert.equal(ctx.earthMesh, displayed);
  assert.match(elements.get("earth-attribution").children[0].textContent, /^Moon:/);
  assert.equal(elements.get("earth-attribution").style.display, "block");
  assert.equal(ctx.scene.objects.size, 1);
});

test("a failed image keeps the displayed body and can be retried", async () => {
  const { ctx, loads, elements } = surfaceViewer();
  let pending = ctx.updateEarthSurface();
  loads[0].resolve(new RealTHREE.Texture());
  await pending;
  const earth = ctx.earthMesh;
  let disposed = false;
  earth.material.map.addEventListener("dispose", () => { disposed = true; });
  ctx.console = { warn() {} };
  let status;
  ctx.setStatus = message => { status = message; };
  ctx.params.earthTextureBody = "venus";
  pending = ctx.updateEarthSurface();
  loads[1].reject(new Error("Network error"));
  await pending;
  assert.equal(ctx.earthMesh, earth);
  assert.equal(disposed, false);
  assert.match(elements.get("earth-attribution").children[0].textContent, /^Earth:/);
  assert.match(status, /Venus.*retry/);
  pending = ctx.updateEarthSurface();
  loads[2].resolve(new RealTHREE.Texture());
  await pending;
  assert.equal(ctx.earthMesh.userData.viewerTopology.body, "venus");
  assert.equal(disposed, true, "Release the replaced mesh's texture");
  assert.equal(earth.geometry.disposed, true);
});

test("hiding the surface while an image loads prevents a late mesh or credit", async () => {
  const { ctx, loads, elements } = surfaceViewer();
  const pending = ctx.updateEarthSurface();
  ctx.params.showEarthSurface = false;
  await ctx.updateEarthSurface();
  loads[0].resolve(new RealTHREE.Texture());
  await pending;
  assert.equal(ctx.earthMesh, null);
  assert.equal(elements.has("earth-attribution"), false);
});

test("reusing a surface cannot retain the wrong body or longitude", async () => {
  const { ctx, loads } = surfaceViewer();
  let pending = ctx.updateEarthSurface();
  loads[0].resolve(new RealTHREE.Texture());
  await pending;
  const earth = ctx.earthMesh;
  ctx.params.earthTextureBody = "ganymede";
  ctx.params.earthRadiusScale = 1.3;
  pending = ctx.updateEarthSurface({ reuseGeometry: true });
  loads[1].resolve(new RealTHREE.Texture());
  await pending;
  const ganymede = ctx.earthMesh;
  assert.notEqual(ganymede, earth);
  assert.equal(ganymede.userData.viewerTopology.body, "ganymede");
  assert.equal(ganymede.userData.viewerTopology.radius, 1.3);
  ctx.params.earthLongitudeDeg = 57;
  await ctx.updateEarthSurface({ reuseGeometry: true });
  assert.notEqual(ctx.earthMesh, ganymede);
  assert.equal(ctx.earthMesh.userData.viewerTopology.longitudeDeg, 57);
  const rotated = ctx.earthMesh;
  ctx.params.earthOpacity = 0.2;
  await ctx.updateEarthSurface({ reuseGeometry: true });
  assert.equal(ctx.earthMesh, rotated);
  assert.equal(ctx.earthMesh.material.opacity, 0.2);
  assert.equal(loads.length, 2, "Changing longitude or opacity reuses the downloaded image");
});

test("texture loads are shared and decoded-image cache eviction leaves displayed clones alive", async () => {
  const { ctx, loads } = surfaceViewer();
  const pending = ctx.ensureEarthTexture("mars");
  const shared = ctx.ensureEarthTexture("mars");
  assert.equal(loads.length, 1);
  const original = new RealTHREE.Texture(), clone = original.clone();
  let originalDisposed = false, cloneDisposed = false;
  original.addEventListener("dispose", () => { originalDisposed = true; });
  clone.addEventListener("dispose", () => { cloneDisposed = true; });
  loads[0].resolve(original);
  assert.equal(await pending, original);
  assert.equal(await shared, original);
  assert.equal(original.wrapS, RealTHREE.RepeatWrapping);
  assert.equal(original.wrapT, RealTHREE.ClampToEdgeWrapping);
  assert.equal(original.colorSpace, RealTHREE.SRGBColorSpace);
  assert.equal(original.anisotropy, 8);
  for (const body of ["moon", "ganymede", "mercury"]) {
    const loading = ctx.ensureEarthTexture(body);
    loads.at(-1).resolve(new RealTHREE.Texture());
    await loading;
  }
  assert.equal(ctx.surfaceTextures.size, 3);
  assert.equal(originalDisposed, true);
  assert.equal(cloneDisposed, false);
  assert.equal(clone.source, original.source);
  const reload = ctx.ensureEarthTexture("mars");
  loads.at(-1).resolve(new RealTHREE.Texture());
  assert.notEqual(await reload, original);
  assert.equal(ctx.surfaceTexturePromises.size, 0);
});

function datasetLoader(ctx, code) {
  const meta = structuredClone(ctx.metadata), grid = structuredClone(ctx.coords);
  Object.assign(ctx, {
    setDatasetLoadingState: loading => { ctx.datasetLoadInProgress = loading; },
    cancelPendingViewerTasks: () => ctx.invalidateRenderRequests(),
    pauseSequence: () => { ctx.params.sequencePlaying = false; },
    fetchSequenceIndexForRoot: async () => null,
    loadMetadataForBase: async () => meta,
    loadCoordinatesForBase: async () => grid,
    loadFloat32ForBase: async () => new Float32Array(36),
    fetchDatasetResource: async () => new Response(code, { status: code === null ? 404 : 200 }),
    applyDefaultFields: () => {}, rebuildAllMeshes: async () => {}, loadFieldLines: async () => {},
    rememberDatasetRoot: () => {}, hideDatasetLauncher: () => {},
    sequenceFrameBasePathForRoot: (root, frame) => `${root}/${frame.path}`,
  });
  ctx.params.datasetPath = "new-dataset";
  return { meta, grid };
}

function localDatasetViewer() {
  const ctx = viewer(), selections = [], messages = [];
  datasetLoader(ctx, null);
  Object.assign(ctx, {
    chooseDatasetDirectory: async () => selections.shift(),
    fetchRemoteRepositoryResource: async () => null,
    setStatus: message => messages.push(message),
    console: { ...console, error: () => {} },
  });
  for (const name of [
    "selectDatasetFolder", "fetchDatasetResource", "fetchJsonStrict", "stripLegacyCpsMetadata",
    "loadMetadataForBase", "loadCoordinatesForBase", "loadFloat32ForBase",
    "fetchSequenceIndexForRoot", "normaliseSequenceFramePathForRoot",
    "resolveDatasetBasePath", "loadSecondaryDatasetFromParams", "chooseField", "applyDefaultFields",
    "getPrimaryCmbFieldNames", "getSecondaryCmbFieldNames", "getCmbFieldNames",
    "getPrimaryEarthFieldNames", "getSecondaryEarthFieldNames", "getEarthFieldNames",
  ]) vm.runInContext(definition(name), ctx);
  ctx.rebuildAllMeshes = async () => {
    const field = ctx.resolveFieldSource(ctx.params.equatorField);
    ctx.displayed = await ctx.loadFloat32ForBase(field.basePath, field.meta.fields[field.rawName],
      field.meta.nr * field.meta.ntheta * field.meta.nphi);
  };
  return { ctx, selections, messages };
}

function selectedFolder(ctx, value, { type = "files", sequence = false, middleRadius = 0.7, nphi = ctx.metadata.nphi } = {}) {
  const meta = { ...structuredClone(ctx.metadata), nphi, title: `Dataset ${value}`, coordinates: "coordinates.json" };
  const grid = structuredClone(ctx.coords);
  grid.r[1] = middleRadius;
  grid.phi = Array.from({ length: nphi }, (_, i) => 2 * Math.PI * i / nphi);
  const prefix = sequence ? "frames/first/" : "";
  const files = new Map([
    [`${prefix}metadata.json`, new Blob([JSON.stringify(meta)])],
    [`${prefix}coordinates.json`, new Blob([JSON.stringify(grid)])],
  ]);
  for (const filename of Object.values(meta.fields)) {
    files.set(prefix + filename, new Blob([new Float32Array(meta.nr * meta.ntheta * meta.nphi).fill(value)]));
  }
  if (sequence) files.set("sequence.json", new Blob([JSON.stringify({ frames: [{ path: "frames/first", label: `Frame ${value}` }] })]));
  function directory(prefix = "") {
    return {
      getDirectoryHandle: async name => directory(`${prefix}${name}/`),
      getFileHandle: async name => {
        if (!files.has(prefix + name)) throw new DOMException("File not found", "NotFoundError");
        return { getFile: async () => files.get(prefix + name) };
      },
    };
  }
  return type === "handle" ? { type, handle: directory() } : { type, files };
}

test("switching local folders reads the new metadata, coordinates and field values without a refresh", async () => {
  for (const type of ["files", "handle"]) {
    const { ctx, selections } = localDatasetViewer();
    const first = selectedFolder(ctx, 1, { type }), second = selectedFolder(ctx, 2, { type, middleRadius: 0.8, nphi: 6 });
    selections.push(first, second, first);
    await ctx.selectDatasetFolder("primary");
    assert.equal(ctx.displayed[0], 1);
    const firstPath = ctx.datasetRootPath;
    await ctx.selectDatasetFolder("primary");
    assert.equal(ctx.displayed[0], 2);
    assert.equal(ctx.metadata.title, "Dataset 2");
    assert.equal(ctx.metadata.nphi, 6);
    assert.equal(ctx.displayed.length, 54);
    assert.equal(ctx.coords.r[1], 0.8);
    assert.notEqual(ctx.datasetRootPath, firstPath);
    await ctx.selectDatasetFolder("primary");
    assert.equal(ctx.displayed[0], 1);
    assert.equal(ctx.coords.r[1], 0.7);
    assert.equal(ctx.activeDatasetFolderSource, first);
    assert.equal(ctx.datasetFolderSources.size, 1);
  }
});

test("two selected sequences with identical frame paths keep their own index and volumes", async () => {
  const { ctx, selections } = localDatasetViewer();
  selections.push(selectedFolder(ctx, 3, { sequence: true }), selectedFolder(ctx, 4, { sequence: true }));
  await ctx.selectDatasetFolder("primary");
  assert.equal(ctx.displayed[0], 3);
  await ctx.selectDatasetFolder("primary");
  assert.equal(ctx.displayed[0], 4);
  assert.equal(ctx.sequenceIndex.frames[0].label, "Frame 4");
  assert.match(ctx.dataBasePath, /\/frames\/first$/);
});

test("a failed local folder switch restores the previous source for uncached reads and saving", async () => {
  const { ctx, selections, messages } = localDatasetViewer();
  const first = selectedFolder(ctx, 1), second = selectedFolder(ctx, 2);
  selections.push(first, second);
  await ctx.selectDatasetFolder("primary");
  const firstPath = ctx.datasetRootPath, render = ctx.rebuildAllMeshes;
  ctx.rebuildAllMeshes = async () => {
    if (ctx.metadata.title === "Dataset 2") throw new Error("failed new surface");
    await render();
  };
  await ctx.selectDatasetFolder("primary");
  assert.match(messages.at(-1), /failed new surface/);
  assert.equal(ctx.datasetRootPath, firstPath);
  assert.equal(ctx.params.datasetPath, firstPath);
  assert.equal(ctx.displayed[0], 1);
  assert.equal(ctx.activeDatasetFolderSource, first);
  const fresh = await ctx.fetchDatasetResource(`${firstPath}/metadata.json`);
  assert.equal((await fresh.json()).title, "Dataset 1");
  assert.equal(ctx.datasetFolderSources.size, 1);
});

test("replacing a secondary folder refreshes its data while preserving the primary folder", async () => {
  const { ctx, selections } = localDatasetViewer();
  selections.push(selectedFolder(ctx, 1), selectedFolder(ctx, 2), selectedFolder(ctx, 3));
  await ctx.selectDatasetFolder("primary");
  const primaryPath = ctx.datasetRootPath;
  Object.assign(ctx.params, { backgroundColor: "#345678", cameraDistance: 7, legendCollapsed: true });
  await ctx.selectDatasetFolder("secondary");
  const oldSecondary = ctx.secondaryDataset.basePath;
  assert.equal((await ctx.loadFloat32ForBase(oldSecondary, "ur.f32", 36))[0], 2);
  ctx.params.equatorField = "D2:ur";
  await ctx.rebuildAllMeshes();
  assert.equal(ctx.displayed[0], 2);
  await ctx.selectDatasetFolder("secondary");
  assert.equal((await ctx.loadFloat32ForBase(ctx.secondaryDataset.basePath, "ur.f32", 36))[0], 3);
  assert.notEqual(ctx.secondaryDataset.basePath, oldSecondary);
  assert.equal(ctx.datasetRootPath, primaryPath);
  assert.equal(ctx.displayed[0], 3);
  assert.equal(ctx.params.equatorField, "D2:ur");
  assert.equal(ctx.params.backgroundColor, "#345678");
  assert.equal(ctx.params.cameraDistance, 7);
  assert.equal(ctx.params.legendCollapsed, true);
  assert.equal((await ctx.loadFloat32ForBase(primaryPath, "ur.f32", 36))[0], 1);
  assert.equal(ctx.datasetFolderSources.size, 2);
});

test("an incomplete replacement folder leaves the displayed data and source intact", async () => {
  const { ctx, selections, messages } = localDatasetViewer();
  const first = selectedFolder(ctx, 1), broken = selectedFolder(ctx, 2);
  broken.files.set("ur.f32", new Blob([new Float32Array(1)]));
  selections.push(first, broken);
  assert.equal(await ctx.selectDatasetFolder("primary"), true);
  const original = ctx.metadata;
  assert.equal(await ctx.selectDatasetFolder("primary"), false);
  assert.match(messages.at(-1), /Unexpected array length/);
  assert.equal(ctx.metadata, original);
  assert.equal(ctx.displayed[0], 1);
  assert.equal(ctx.activeDatasetFolderSource, first);
  assert.equal(ctx.datasetFolderSources.size, 1);
  assert.equal(ctx.datasetLoadInProgress, false);
});

test("a rejected secondary grid keeps the previous comparison path and files usable", async () => {
  const { ctx, selections, messages } = localDatasetViewer();
  selections.push(selectedFolder(ctx, 1), selectedFolder(ctx, 2), selectedFolder(ctx, 3, { middleRadius: 0.8 }));
  await ctx.selectDatasetFolder("primary");
  await ctx.selectDatasetFolder("secondary");
  const previous = ctx.secondaryDataset;
  assert.equal(await ctx.selectDatasetFolder("secondary"), false);
  assert.match(messages.at(-1), /coordinates do not match/);
  assert.equal(ctx.secondaryDataset, previous);
  assert.equal(ctx.params.secondaryDatasetPath, previous.rootPath);
  const fresh = await ctx.fetchDatasetResource(`${previous.rootPath}/metadata.json`);
  assert.equal((await fresh.json()).title, "Dataset 2");
  assert.equal(ctx.datasetFolderSources.size, 2);
});

test("a comparison render failure restores its previous selected field and folder", async () => {
  const { ctx, selections, messages } = localDatasetViewer();
  selections.push(selectedFolder(ctx, 1), selectedFolder(ctx, 2), selectedFolder(ctx, 3));
  await ctx.selectDatasetFolder("primary");
  await ctx.selectDatasetFolder("secondary");
  ctx.params.equatorField = "D2:ur";
  await ctx.rebuildAllMeshes();
  const previous = ctx.secondaryDataset, render = ctx.rebuildAllMeshes;
  ctx.rebuildAllMeshes = async () => {
    if (ctx.secondaryDataset?.metadata.title === "Dataset 3") throw new Error("comparison surface unavailable");
    await render();
  };
  assert.equal(await ctx.selectDatasetFolder("secondary"), false);
  assert.match(messages.at(-1), /comparison surface unavailable/);
  assert.equal(ctx.secondaryDataset, previous);
  assert.equal(ctx.params.equatorField, "D2:ur");
  assert.equal(ctx.displayed[0], 2);
  assert.equal(ctx.datasetLoadInProgress, false);
  const fresh = await ctx.fetchDatasetResource(`${previous.rootPath}/metadata.json`);
  assert.equal((await fresh.json()).title, "Dataset 2");
});

test("overlapping folder selection and a load started while the picker is open cannot replace its source", async () => {
  const { ctx, selections } = localDatasetViewer();
  const folder = selectedFolder(ctx, 1), picker = deferred();
  selections.push(folder);
  await ctx.selectDatasetFolder("primary");
  const originalPath = ctx.datasetRootPath;
  ctx.chooseDatasetDirectory = () => picker.promise;
  const pending = ctx.selectDatasetFolder("primary");
  assert.equal(await ctx.selectDatasetFolder("secondary"), false);
  ctx.datasetLoadInProgress = true;
  picker.resolve(selectedFolder(ctx, 2));
  assert.equal(await pending, false);
  assert.equal(ctx.datasetRootPath, originalPath);
  assert.equal(ctx.activeDatasetFolderSource, folder);
  assert.equal(ctx.datasetFolderSources.size, 1);
  assert.equal(ctx.datasetFolderSelectionInProgress, false);
});

test("cancelling the fallback directory picker releases the selection lock", async () => {
  const { ctx, selections } = localDatasetViewer();
  const folder = selectedFolder(ctx, 1), input = new EventTarget();
  let removed = false;
  Object.assign(input, { style: {}, setAttribute: () => {}, click: () => {}, remove: () => { removed = true; } });
  ctx.document = { createElement: () => input, body: { appendChild: () => {} } };
  for (const name of ["chooseDatasetDirectory", "selectDirectoryUsingFileInput"]) vm.runInContext(definition(name), ctx);
  const pending = ctx.selectDatasetFolder("primary");
  input.dispatchEvent(new Event("cancel"));
  assert.equal(await pending, false);
  assert.equal(removed, true);
  assert.equal(ctx.datasetFolderSelectionInProgress, false);
  assert.equal(ctx.datasetFolderSources.size, 0);
  ctx.chooseDatasetDirectory = async () => selections.shift();
  selections.push(folder);
  assert.equal(await ctx.selectDatasetFolder("primary"), true);
});

test("a shell-to-full-sphere switch removes the preceding inner boundary", async () => {
  const ctx = viewer();
  const original = new Mesh(new Geometry("old shell"), new Material());
  ctx.icbMesh = original;
  ctx.scene.add(original);
  ctx.metadata.has_inner_core = false;
  for (const key of ["showCMB", "showRadialSurface", "showEquator", "showEquator2", "showMeridian", "showMeridian2", "showEarthSurface", "showIsosurfaces"]) ctx.params[key] = false;
  ctx.params.showICB = true;
  for (const name of ["rebuildICB", "rebuildAllMeshes"]) vm.runInContext(definition(name), ctx);
  await ctx.rebuildAllMeshes();
  assert.equal(ctx.icbMesh, null);
  assert.equal(original.geometry.disposed, true);
  assert.equal(original.material.disposed, true);
  assert.equal(ctx.scene.objects.has(original), false);
});

test("changing frames replaces an unavailable isosurface field before rendering", async () => {
  const ctx = viewer(), nextMetadata = structuredClone(ctx.metadata), nextCoords = structuredClone(ctx.coords);
  ctx.metadata.fields.Comp = "Comp.f32";
  ctx.params.isoField = "Comp";
  Object.assign(ctx, {
    sequenceIndex: { frames: [{ path: "frames/second" }] },
    sequenceFrameBasePath: frame => frame.path,
    loadMetadataForBase: async () => nextMetadata, loadCoordinatesForBase: async () => nextCoords,
    refreshSequenceControllers: () => {}, setDeferredSequenceObjectVisibility: () => {}, formatBytes: String,
    loadField: async name => {
      if (!ctx.metadata.fields[name]) throw new Error(`Unavailable field ${name}`);
      return { name };
    },
    rebuildAllMeshes: async () => ctx.rebuildIsosurfaces(),
  });
  for (const name of ["chooseField", "applyDefaultFields"]) vm.runInContext(definition(name), ctx);
  ctx.params.showFieldLines = false;
  assert.equal(await ctx.loadFrameByIndex(0), true);
  assert.equal(ctx.params.isoField, "ur");
  assert.equal(ctx.isoPositiveMesh.geometry.field.name, "ur");
});

function writableFolder(permission = "granted") {
  const state = { files: new Map(), requests: [], aborted: false };
  function directory(prefix = "") {
    return {
      name: "test-dataset",
      requestPermission: async options => { state.requests.push(options.mode); return permission; },
      getDirectoryHandle: async name => directory(`${prefix}${name}/`),
      getFileHandle: async name => ({
        getFile: async () => new Blob([state.files.get(prefix + name)]),
        createWritable: async () => {
          let pending;
          return {
            write: async blob => { pending = await blob.text(); if (state.failWrite) throw new Error("disk full"); },
            close: async () => { state.files.set(prefix + name, pending); },
            abort: async () => { state.aborted = true; },
          };
        },
      }),
    };
  }
  return { source: { type: "handle", handle: directory() }, state };
}

test("newer isosurface selection wins even when older fetch finishes last", async () => {
  const ctx = viewer(), old = deferred(), newer = deferred();
  ctx.loadField = name => name === "ur" ? old.promise : newer.promise;
  const a = ctx.rebuildIsosurfaces();
  ctx.params.isoField = "Br";
  ctx.params.isoPositiveValue = 0.2;
  const b = ctx.rebuildIsosurfaces();
  newer.resolve({ name: "Br" }); await b;
  old.resolve({ name: "ur" }); await a;
  assert.equal(ctx.isoPositiveMesh.geometry.field.name, "Br");
  assert.equal(ctx.scene.objects.size, 1);
  for (const [key, entry] of ctx.isosurfaceObjectCache) {
    assert.equal(entry.positive.field.name, JSON.parse(key).field);
    assert.equal(entry.positive.value, JSON.parse(key).positiveValue);
  }
});

test("failed replacement preserves the last displayed isosurface", async () => {
  const ctx = viewer();
  await ctx.rebuildIsosurfaces();
  const original = ctx.isoPositiveMesh;
  ctx.params.isoField = "Br";
  ctx.loadField = async () => { throw new Error("file unavailable"); };
  await assert.rejects(ctx.rebuildIsosurfaces(), /file unavailable/);
  assert.equal(ctx.isoPositiveMesh, original);
  assert.ok(ctx.scene.objects.has(original));
  assert.equal(original.material.disposed, false);
});

test("appearance changes reuse geometry, not stale materials", async () => {
  const ctx = viewer();
  await ctx.rebuildIsosurfaces();
  const geometry = ctx.isoPositiveMesh.geometry;
  ctx.params.isoOpacity = 1;
  ctx.updateOpacities();
  ctx.params.isoPositiveValue = 0.2;
  await ctx.rebuildIsosurfaces();
  ctx.params.isoOpacity = 0.45;
  ctx.params.isoPositiveColor = "#123456";
  ctx.params.isoTransparencyMode = "smooth";
  ctx.params.isoPositiveValue = 0.1;
  await ctx.rebuildIsosurfaces();
  assert.equal(ctx.isoPositiveMesh.geometry, geometry);
  assert.equal(ctx.isoPositiveMesh.material.opacity, 0.45);
  assert.equal(ctx.isoPositiveMesh.material.color.value, "#123456");
  assert.equal(ctx.isoPositiveMesh.material.transparent, true);
  assert.equal(geometry.disposed, false);
});

test("concurrent requests for one geometry share one pending build", async () => {
  const ctx = viewer(), data = deferred();
  let loads = 0;
  ctx.loadField = () => { loads++; return data.promise; };
  const a = ctx.rebuildIsosurfaces(), b = ctx.rebuildIsosurfaces();
  data.resolve({ name: "ur" });
  await Promise.all([a, b]);
  assert.equal(loads, 1);
  assert.equal(ctx.isosurfaceObjectCache.size, 1);
  assert.equal(ctx.scene.objects.size, 1);
  assert.equal(ctx.heavyObjectCacheBytes, 36);
  assert.equal(ctx.heavyCachePins.size, 0);
});

test("clearing geometry cache discards pending results", async () => {
  const ctx = viewer(), data = deferred();
  ctx.loadField = () => data.promise;
  const pending = assert.rejects(ctx.rebuildIsosurfaces(), { name: "AbortError" });
  ctx.disposeHeavyPlaybackCaches();
  data.resolve({ name: "ur" });
  await pending;
  assert.equal(ctx.isosurfaceObjectCache.size, 0);
  assert.equal(ctx.heavyObjectCacheBytes, 0);
  assert.equal(ctx.scene.objects.size, 0);
  assert.equal(ctx.heavyCachePins.size, 0);
});

test("a dataset switch prevents an old request from restoring an old mesh", async () => {
  const ctx = viewer(), data = deferred();
  ctx.loadField = () => data.promise;
  const pending = ctx.rebuildIsosurfaces();
  ctx.invalidateRenderRequests();
  ctx.dataBasePath = "other-dataset";
  data.resolve({ name: "ur" });
  await pending;
  assert.equal(ctx.isoPositiveMesh, null);
  assert.equal(ctx.scene.objects.size, 0);
});

test("preloading a frame never changes the active dataset context while awaiting data", async () => {
  const ctx = viewer(), data = deferred();
  const originalMetadata = ctx.metadata, originalCoords = ctx.coords;
  ctx.params.sequenceDeferIsosurfaces = false;
  ctx.params.showFieldLines = false;
  ctx.loadCoordinatesForBase = async () => structuredClone(originalCoords);
  ctx.loadField = () => data.promise;
  const pending = ctx.preloadHeavyObjectsForFrame("frames/second", { ...originalMetadata });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(ctx.dataBasePath, "demo");
  assert.equal(ctx.metadata, originalMetadata);
  assert.equal(ctx.coords, originalCoords);
  data.resolve({ name: "ur" });
  await pending;
  assert.equal(ctx.dataBasePath, "demo");
  assert.equal(ctx.scene.objects.size, 0);
});

test("grid compatibility includes every coordinate, not only dimensions/endpoints", () => {
  const ctx = viewer(), other = structuredClone(ctx.coords);
  other.r[1] = 0.8;
  assert.equal(ctx.samePlaybackGrid(ctx.metadata, { ...ctx.metadata }, ctx.coords, other), false);
  assert.equal(ctx.samePlaybackGrid(ctx.metadata, { ...ctx.metadata }, ctx.coords, structuredClone(ctx.coords)), true);
  other.r[1] = ctx.coords.r[1]; other.phi[1] += 0.1;
  assert.equal(ctx.sameCoordinateArrays(ctx.coords, other), false);
});

test("coordinate validation rejects missing, nonfinite, unordered and inconsistent axes", () => {
  const ctx = viewer();
  for (const mutate of [
    c => { c.r = null; }, c => { c.r[1] = NaN; }, c => { c.r[1] = c.r[0]; },
    c => { c.theta[1] = 4; }, c => { c.phi[3] = 2 * Math.PI; }, c => { c.r[2] = 1.1; },
  ]) {
    const coords = structuredClone(ctx.coords); mutate(coords);
    assert.throws(() => ctx.validateDatasetCoordinates(coords, ctx.metadata, "test"));
  }
  ctx.validateDatasetCoordinates(ctx.coords, ctx.metadata, "test");
});

test("a declared coordinates file is required; legacy uniform demo remains supported", async () => {
  const ctx = viewer();
  ctx.fetchDatasetResource = async () => new Response("missing", { status: 404 });
  await assert.rejects(ctx.loadCoordinatesForBase("demo", { ...ctx.metadata, coordinates: "coordinates.json" }), /Required coordinates/);
  const uniform = await ctx.loadCoordinatesForBase("demo", ctx.metadata);
  assert.equal(uniform.r.length, 3);
  assert.equal(uniform.r[0], 0.35);
  assert.equal(uniform.r[2], 1);
  assert.equal(uniform.phi[3], 3 * Math.PI / 2);
});

test("the actual bundled demo passes coordinate and binary-size checks", async () => {
  const ctx = viewer(), root = new URL("../public/data/", import.meta.url);
  const meta = JSON.parse(fs.readFileSync(new URL("metadata.json", root), "utf8"));
  ctx.validateDatasetMetadata(meta, "bundled demo");
  ctx.fetchDatasetResource = async url => new Response(fs.readFileSync(new URL(url.split("/").at(-1), root)));
  const coordinates = await ctx.loadCoordinatesForBase("demo", meta);
  ctx.validateDatasetCoordinates(coordinates, meta, "bundled demo");
  for (const filename of Object.values(meta.fields)) {
    assert.equal(fs.statSync(new URL(filename, root)).size, meta.nr * meta.ntheta * meta.nphi * 4);
  }
});

test("all available saved options round-trip, including numeric Earth radius", () => {
  const ctx = viewer();
  ctx.metadata.field_lines = { mode: "both", shell: "shell.json", exterior: "exterior.json" };
  const state = ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  assert.equal(state.params.datasetPath, undefined);
  assert.equal(state.params.secondaryDatasetPath, undefined);
  assert.equal(state.params.sequenceFrame, undefined);
  for (const [key, value] of Object.entries(state.params)) {
    if (typeof value === "number") ctx.params[key] = value + 0.1;
    if (typeof value === "boolean") ctx.params[key] = !value;
    assert.equal(ctx.applySnapshotParam(key, value), true, key);
    assert.equal(ctx.params[key], value, key);
  }
  assert.equal(ctx.applySnapshotParam("earthRadiusScale", 2.2), true);
  assert.equal(ctx.params.earthRadiusScale, 2.2);
});

test("view state rejects malformed types and skips unavailable isosurface fields", () => {
  const ctx = viewer();
  for (const [key, value] of [["cameraDistance", NaN], ["showCMB", "false"], ["earthRadiusScale", "2.2"], ["isoOpacity", 2], ["isoField", "missing"], ["__proto__", {}]]) {
    assert.equal(ctx.applySnapshotParam(key, value), false, key);
  }
  assert.equal(ctx.params.isoField, "ur");
});

test("active cache entries remain alive under memory pressure; inactive entries can be freed", async () => {
  const ctx = viewer();
  await ctx.rebuildIsosurfaces();
  const oldGeometry = ctx.isoPositiveMesh.geometry;
  ctx.cacheLimitBytes = () => 0;
  ctx.enforceCacheMemoryLimit();
  assert.equal(oldGeometry.disposed, false);
  ctx.params.isoPositiveValue = 0.2;
  await ctx.rebuildIsosurfaces();
  assert.equal(oldGeometry.disposed, true);
  assert.equal(ctx.isoPositiveMesh.geometry.disposed, false);
});

test("ordinary slices commit only the latest selection and keep the mesh on failure", async () => {
  const ctx = viewer(), old = deferred(), newer = deferred();
  ctx.params.equatorField = "C";
  ctx.loadField = name => name === "C" ? old.promise : newer.promise;
  const a = ctx.rebuildEquator();
  ctx.params.equatorField = "Br";
  const b = ctx.rebuildEquator();
  newer.resolve({ name: "Br" }); await b;
  old.resolve({ name: "C" }); await a;
  const original = ctx.equatorMesh;
  assert.equal(original.geometry.field.name, "Br");
  assert.equal(ctx.scene.objects.size, 1);
  ctx.loadField = async () => { throw new Error("slice unavailable"); };
  await assert.rejects(ctx.rebuildEquator(), /slice unavailable/);
  assert.equal(ctx.equatorMesh, original);
  assert.equal(original.geometry.disposed, false);
});

test("field-line loads use captured filenames and only the latest mode is displayed", async () => {
  const ctx = viewer(), shell = deferred(), exterior = deferred();
  ctx.metadata.field_lines = { shell: "shell.json", exterior: "exterior.json" };
  ctx.params.showFieldLines = true;
  ctx.params.fieldLineDisplay = "shell";
  const fetched = [];
  ctx.fetchDatasetResource = url => {
    fetched.push(url);
    return url.endsWith("shell.json") ? shell.promise : exterior.promise;
  };
  const a = ctx.loadFieldLines();
  ctx.params.fieldLineDisplay = "exterior";
  const b = ctx.loadFieldLines();
  exterior.resolve(new Response("[]")); await b;
  shell.resolve(new Response("[]")); await a;
  assert.equal(ctx.fieldLineGroups.shell, null);
  assert.ok(ctx.fieldLineGroups.exterior);
  assert.equal(ctx.scene.objects.size, 1);
  assert.deepEqual(fetched, ["demo/shell.json", "demo/exterior.json"]);
  const cached = ctx.fieldLineGroups.exterior;
  ctx.params.lineOpacity = 0.4;
  ctx.params.lineWidthPx = 5;
  await ctx.loadFieldLines();
  assert.equal(ctx.fieldLineGroups.exterior, cached);
  assert.equal(cached.material.opacity, 0.4);
  assert.equal(cached.material.linewidth, 5);
});

function pairedLineFixture() {
  const shell = Array.from({ length: 12 }, (_, i) => {
    const foot = [Math.cos(i), Math.sin(i), 0];
    return { line_id: `seed-${i}`, points: [foot.map(x => 0.8 * x), foot],
      strength: [2, 1], region: "fluid_shell" };
  });
  // Missing arcs and reordered records reproduce the independent-stride bug.
  const exterior = [11, 8, 6, 5, 3, 2, 0].map(i => ({
    line_id: `seed-${i}`, paired_shell_line_id: `seed-${i}`,
    points: [shell[i].points[1], shell[i].points[1].map(x => 1.2 * x)],
    strength: [1, 0.5], region: "outside_cmb_potential_poloidal",
  }));
  return { shell, exterior };
}

test("every viewer stride preserves all available shell/exterior pairs despite missing and reordered arcs", () => {
  const ctx = viewer(), lines = pairedLineFixture();
  for (let stride = 1; stride <= 10; stride++) {
    const shown = ctx.selectFieldLinesByStride(lines, stride);
    const selectedIds = new Set(shown.shell.map(line => line.line_id));
    assert.equal(shown.shell.length, Math.ceil(lines.shell.length / stride));
    for (const arc of lines.exterior) {
      assert.equal(shown.exterior.includes(arc), selectedIds.has(arc.paired_shell_line_id));
    }
    for (const arc of shown.exterior) {
      const internal = shown.shell.find(line => line.line_id === arc.paired_shell_line_id);
      assert.deepEqual(arc.points[0], internal.points.at(-1));
    }
  }
  assert.equal(lines.shell.length, 12);
  assert.equal(lines.exterior.length, 7);
});

test("explicit pairing takes precedence and all segments with one identifier stay together", () => {
  const ctx = viewer();
  const shell = [{ line_id: 0 }, { line_id: "skip" }, { line_id: "last" }];
  const exterior = [
    { line_id: "last", paired_shell_line_id: "skip" },
    { line_id: "different-exterior-id", paired_shell_line_id: 0 },
    { line_id: "second-segment", paired_shell_line_id: "0" },
    { line_id: "last" },
    { line_id: "unpaired-extra" },
  ];
  const shown = ctx.selectFieldLinesByStride({ shell, exterior }, 2);
  assert.deepEqual(Array.from(shown.shell), [shell[0], shell[2]]);
  assert.deepEqual(Array.from(shown.exterior), exterior.slice(1, 4));
  assert.equal(ctx.selectFieldLinesByStride({ shell, exterior }, 1).exterior.length, 5);
});

test("stride retains the original internal line, exterior arc and return branch as one group", () => {
  const ctx = viewer(), fixture = pairedLineFixture();
  const returns = fixture.exterior.map(arc => ({
    line_id: `${arc.line_id}:return`, line_group_id: arc.line_id,
    points: [arc.points.at(-1), arc.points.at(-1).map(x => .7*x)],
  }));
  const shell = fixture.shell.concat(returns);
  for (let stride=1; stride<=10; stride++) {
    const selected = ctx.selectFieldLinesByStride({ shell, exterior: fixture.exterior }, stride);
    const ids = new Set(selected.shell.map(line => line.line_id));
    for (const arc of fixture.exterior) {
      assert.equal(ids.has(arc.line_id), ids.has(`${arc.line_id}:return`));
      assert.equal(ids.has(arc.line_id), selected.exterior.includes(arc));
    }
  }
});

test("legacy lines without identifiers and single-domain selections retain ordinary stride", () => {
  const ctx = viewer();
  const shell = Array.from({ length: 5 }, (_, i) => ({ points: [[i, 0, 0], [i, 1, 0]] }));
  const exterior = shell.slice().reverse();
  const shown = ctx.selectFieldLinesByStride({ shell, exterior }, 2);
  assert.deepEqual(Array.from(shown.shell), [shell[0], shell[2], shell[4]]);
  assert.deepEqual(Array.from(shown.exterior), [exterior[0], exterior[2], exterior[4]]);
  const fixture = pairedLineFixture();
  const single = ctx.selectFieldLinesByStride({ exterior: fixture.exterior }, 3);
  assert.deepEqual(Array.from(single.exterior), [fixture.exterior[0], fixture.exterior[3], fixture.exterior[6]]);
  assert.equal(single.shell, undefined);
});

test("paired selection is applied during loading and cached separately for each stride", async () => {
  const ctx = viewer(), fixture = pairedLineFixture();
  ctx.metadata.field_lines = { shell: "shell.json", exterior: "exterior.json" };
  Object.assign(ctx.params, { showFieldLines: true, fieldLineDisplay: "both", lineStride: 3 });
  let fetches = 0;
  ctx.fetchDatasetResource = async url => {
    fetches++;
    return new Response(JSON.stringify(url.endsWith("shell.json") ? fixture.shell : fixture.exterior));
  };
  await ctx.loadFieldLines();
  const cached = { ...ctx.fieldLineGroups };
  assert.deepEqual(Array.from(cached.shell.userData.lines, line => line.line_id), ["seed-0", "seed-3", "seed-6", "seed-9"]);
  assert.deepEqual(Array.from(cached.exterior.userData.lines, line => line.paired_shell_line_id), ["seed-6", "seed-3", "seed-0"]);
  ctx.params.lineStride = 1;
  await ctx.loadFieldLines();
  assert.equal(ctx.fieldLineGroups.shell.userData.lines.length, 12);
  assert.equal(ctx.fieldLineGroups.exterior.userData.lines.length, 7);
  ctx.params.lineStride = 3;
  await ctx.loadFieldLines();
  assert.equal(ctx.fieldLineGroups.shell, cached.shell);
  assert.equal(ctx.fieldLineGroups.exterior, cached.exterior);
  assert.equal(fetches, 2);
  assert.equal(ctx.scene.objects.size, 2);
});

test("real Three.js line geometry keeps every selected pair with coincident CMB endpoints", async () => {
  const ctx = viewer(), fixture = pairedLineFixture();
  Object.assign(ctx, {
    THREE: RealTHREE, Line2, LineGeometry,
    makeLineMaterial: () => new LineMaterial({ vertexColors: true }),
    getFieldLineVertexColor: () => new RealTHREE.Color("red"),
    loadLinesForMode: async mode => fixture[mode],
  });
  vm.runInContext(definition("makeFieldLineGroup"), ctx);
  ctx.metadata.field_lines = { mode: "both" };
  Object.assign(ctx.params, { fieldLineDisplay: "both", lineStride: 3 });
  const { groups } = await ctx.buildFieldLineObjectCacheEntry();
  assert.equal(groups.shell.children.length, 4);
  assert.equal(groups.exterior.children.length, 3);
  for (let i = 0; i < groups.exterior.children.length; i++) {
    const id = groups.exterior.userData.lines[i].paired_shell_line_id;
    const j = groups.shell.userData.lines.findIndex(line => line.line_id === id);
    const end = groups.shell.children[j].geometry.getAttribute("instanceEnd");
    const start = groups.exterior.children[i].geometry.getAttribute("instanceStart");
    assert.deepEqual([end.getX(0), end.getY(0), end.getZ(0)], [start.getX(0), start.getY(0), start.getZ(0)]);
  }
  for (const group of Object.values(groups)) ctx.disposeFieldLineGroupResources(group);
});

test("a field-line HTTP failure does not erase the working lines", async () => {
  const ctx = viewer();
  ctx.metadata.field_lines = { shell: "shell.json", exterior: "exterior.json" };
  ctx.params.showFieldLines = true;
  ctx.params.fieldLineDisplay = "shell";
  ctx.fetchDatasetResource = async () => new Response("[]");
  await ctx.loadFieldLines();
  const original = ctx.fieldLineGroups.shell;
  ctx.params.fieldLineDisplay = "exterior";
  ctx.fetchDatasetResource = async () => new Response("missing", { status: 404 });
  await assert.rejects(ctx.loadFieldLines(), /HTTP 404/);
  assert.equal(ctx.fieldLineGroups.shell, original);
  assert.ok(ctx.scene.objects.has(original));
  assert.equal(original.geometry.disposed, false);
});

test("B² tube controls round-trip through DTV2 and reject invalid settings", () => {
  const ctx = viewer();
  const values = { lineRenderMode: "b2-tubes", lineTubeReference: 2.5, lineTubeDiameter: 0.03,
    lineTubeMinDiameter: 0.001, lineTubeMaxDiameter: 0.1, lineTubeSides: 12,
    lineTubeSimplify: false, lineTubeShapeError: 0.001, lineTubeEnergyErrorPercent: 2.5 };
  Object.assign(ctx.params, values);
  const saved = ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  ctx.params.lineRenderMode = "lines";
  ctx.applyViewStateParams(saved);
  for (const [key, value] of Object.entries(values)) assert.equal(ctx.params[key], value);
  assert.equal(ctx.applySnapshotParam("lineRenderMode", "dmfi"), false);
  assert.equal(ctx.applySnapshotParam("lineTubeReference", -1), false);
  assert.equal(ctx.applySnapshotParam("lineTubeSides", 4.5), false);
  assert.equal(ctx.applySnapshotParam("lineTubeDiameter", 1e100), false);
  assert.equal(ctx.applySnapshotParam("lineTubeSimplify", "false"), false);
  assert.equal(ctx.applySnapshotParam("lineTubeShapeError", -1), false);
  assert.equal(ctx.applySnapshotParam("lineTubeEnergyErrorPercent", 100), false);
});

test("tube simplification runs before the budget check and keeps paired footpoints and the original data", async () => {
  const ctx = viewer(), count = 110_000;
  const shell = { line_id: 17, points: Array.from({ length: count }, (_, i) => [0, 0, 0.35 + 0.65 * i / (count - 1)]),
    strength: Array(count).fill(2) };
  const exterior = { paired_shell_line_id: 17, points: Array.from({ length: count }, (_, i) => [0, 0, 1 + i / (count - 1)]),
    strength: Array(count).fill(2) };
  ctx.metadata.field_lines = { mode: "both" };
  ctx.loadLinesForMode = async mode => [mode === "shell" ? shell : exterior];
  Object.assign(ctx.params, { showFieldLines: true, fieldLineDisplay: "both", lineStride: 1,
    lineRenderMode: "b2-tubes", lineTubeSimplify: true });
  await ctx.loadFieldLines();
  const good = ctx.fieldLineGroups;
  const goodShell = good.shell;
  const reducedShell = good.shell.userData.lines[0], reducedExterior = good.exterior.userData.lines[0];
  assert.equal(reducedShell.points.length, 2);
  assert.equal(reducedExterior.points.length, 2);
  assert.deepEqual(reducedShell.points.at(-1), reducedExterior.points[0]);
  assert.equal(reducedShell.line_id, reducedExterior.paired_shell_line_id);
  assert.equal(shell.points.length, count); assert.equal(exterior.points.length, count);
  assert.equal(good.shell.userData.tubeOriginalPoints, count);
  assert.equal(good.shell.userData.tubePoints, 2);
  ctx.params.lineTubeSimplify = false;
  await assert.rejects(ctx.loadFieldLines(), /geometry budget.*Enable Simplify tubes/);
  assert.equal(ctx.fieldLineGroups, good, "an oversized unsimplified request keeps the working display");
  ctx.params.lineTubeSimplify = true;
  await ctx.loadFieldLines();
  assert.equal(ctx.fieldLineGroups.shell, goodShell, "switching back reuses the matching geometry");
});

test("tube memory controls switch between the default and a bounded custom limit", () => {
  const ctx = viewer(), controls = new Map();
  let refreshes = 0;
  const folder = {
    addFolder(name) { assert.equal(name, "Tube memory"); return this; },
    add(object, key, min, max) {
      const controller = {
        domElement: {}, min, max,
        name() { return this; },
        enable(value) { this.enabled = value; return this; },
        onChange(callback) { this.change = callback; return this; },
        onFinishChange(callback) { this.finish = callback; return this; },
        updateDisplay() {},
      };
      controls.set(key, controller);
      return controller;
    },
  };
  ctx.addTubeMemoryControls(folder, () => refreshes++);
  const custom = controls.get("lineTubeCustomMemoryLimit"), limit = controls.get("lineTubeMemoryLimitMiB");
  assert.equal(ctx.tubeGeometryLimitMiB(), 192);
  assert.equal(limit.enabled, false);
  assert.equal(limit.min, 32); assert.equal(limit.max, 2048);
  ctx.params.lineTubeCustomMemoryLimit = true;
  custom.change();
  assert.equal(limit.enabled, true);
  for (const [input, expected] of [[512, 512], [0, 192], [NaN, 192], [Infinity, 192], [-5, 192], [1, 32], [1e6, 2048], [300.7, 301]]) {
    ctx.params.lineTubeMemoryLimitMiB = input;
    limit.finish();
    assert.equal(ctx.params.lineTubeMemoryLimitMiB, expected);
    assert.equal(ctx.tubeGeometryLimitMiB(), expected);
  }
  ctx.params.lineTubeCustomMemoryLimit = false;
  custom.change();
  assert.equal(limit.enabled, false);
  assert.equal(ctx.tubeGeometryLimitMiB(), 192);
  ctx.params.lineTubeCustomMemoryLimit = true;
  custom.change();
  assert.equal(ctx.tubeGeometryLimitMiB(), 301, "turning off retains the user's custom value");
  assert.equal(refreshes, 11);
});

function budgetViewer() {
  const ctx = viewer();
  ctx.metadata.field_lines = { mode: "both" };
  Object.assign(ctx.params, { showFieldLines: true, fieldLineDisplay: "both", lineStride: 1 });
  // The real estimator sees ~142 MiB per domain, ~284 MiB combined. The renderer
  // double avoids allocating hundreds of megabytes in this policy regression.
  ctx.loadLinesForMode = async mode => [{ line_id: 1, paired_shell_line_id: 1,
    type: mode, points: { length: 150_000 }, strength: [2] }];
  return ctx;
}

test("custom tube memory counts both domains and checks cached geometry without rebuilding it", async () => {
  const ctx = budgetViewer();
  await ctx.loadFieldLines();
  const original = ctx.fieldLineGroups.shell;
  ctx.params.lineRenderMode = "b2-tubes";
  await assert.rejects(ctx.loadFieldLines(), /estimated 283\.8 MiB, limit 192 MiB.*Tube memory/);
  assert.equal(ctx.fieldLineGroups.shell, original);
  Object.assign(ctx.params, { lineTubeCustomMemoryLimit: true, lineTubeMemoryLimitMiB: 384 });
  await ctx.loadFieldLines();
  const tubes = ctx.fieldLineGroups.shell, key = ctx.getFieldLineObjectCacheKey();
  assert.notEqual(tubes, original);
  ctx.params.lineTubeCustomMemoryLimit = false;
  await assert.rejects(ctx.loadFieldLines(), /limit 192 MiB/);
  assert.equal(ctx.fieldLineGroups.shell, tubes, "lowering the limit preserves the last working display");
  ctx.params.lineRenderMode = "lines";
  await ctx.loadFieldLines();
  assert.equal(ctx.fieldLineGroups.shell, original, "the cap does not block ordinary lines");
  ctx.params.lineRenderMode = "b2-tubes";
  ctx.loadLinesForMode = async () => { throw new Error("Cached geometry should be reused"); };
  await assert.rejects(ctx.loadFieldLines(), /limit 192 MiB/);
  assert.equal(ctx.fieldLineGroups.shell, original, "an over-budget cached entry cannot replace the display");
  Object.assign(ctx.params, { lineTubeCustomMemoryLimit: true, lineTubeMemoryLimitMiB: 512 });
  assert.equal(ctx.getFieldLineObjectCacheKey(), key, "memory preferences do not duplicate geometry");
  await ctx.loadFieldLines();
  assert.equal(ctx.fieldLineGroups.shell, tubes);
  assert.equal(ctx.fieldLineObjectCache.size, 2);
});

test("pending shared tube builds use the latest memory limit before allocation", async () => {
  for (const raising of [true, false]) {
    const ctx = budgetViewer(), gate = deferred();
    await ctx.loadFieldLines();
    const original = ctx.fieldLineGroups.shell, load = ctx.loadLinesForMode;
    let reads = 0, allocations = 0;
    const makeGroup = ctx.makeFieldLineGroup;
    ctx.makeFieldLineGroup = (...args) => { allocations++; return makeGroup(...args); };
    ctx.loadLinesForMode = async mode => { reads++; await gate.promise; return load(mode); };
    Object.assign(ctx.params, { lineRenderMode: "b2-tubes", lineTubeCustomMemoryLimit: !raising,
      lineTubeMemoryLimitMiB: 384 });
    const first = ctx.loadFieldLines();
    ctx.params.lineTubeCustomMemoryLimit = raising;
    const latest = ctx.loadFieldLines();
    const checked = raising ? latest : assert.rejects(latest, /limit 192 MiB/);
    gate.resolve();
    await Promise.all([first, checked]);
    assert.equal(reads, 2, "requests share one build for shell and exterior");
    assert.equal(allocations, raising ? 2 : 0);
    if (raising) assert.notEqual(ctx.fieldLineGroups.shell, original);
    else assert.equal(ctx.fieldLineGroups.shell, original);
  }
});

test("a memory change while accepting a cached entry is checked before replacing visible lines", async () => {
  const ctx = budgetViewer();
  Object.assign(ctx.params, { lineRenderMode: "b2-tubes", lineTubeCustomMemoryLimit: true,
    lineTubeMemoryLimitMiB: 384 });
  await ctx.loadFieldLines();
  ctx.params.lineRenderMode = "lines";
  await ctx.loadFieldLines();
  const original = ctx.fieldLineGroups.shell;
  ctx.params.lineRenderMode = "b2-tubes";
  const ensure = ctx.ensureFieldLineObjectCacheEntry;
  ctx.ensureFieldLineObjectCacheEntry = async context => {
    const entry = await ensure(context);
    ctx.params.lineTubeCustomMemoryLimit = false;
    return entry;
  };
  await assert.rejects(ctx.loadFieldLines(), /limit 192 MiB/);
  assert.equal(ctx.fieldLineGroups.shell, original);
});

test("view codes and dataset defaults preserve the session's tube memory preference", () => {
  const ctx = viewer();
  Object.assign(ctx.params, { lineTubeCustomMemoryLimit: true, lineTubeMemoryLimitMiB: 512 });
  const state = ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  assert.equal(Object.hasOwn(state.params, "lineTubeCustomMemoryLimit"), false);
  assert.equal(Object.hasOwn(state.params, "lineTubeMemoryLimitMiB"), false);
  ctx.applyViewStateParams({ version: 2, scope: "view-only",
    params: { lineTubeCustomMemoryLimit: false, lineTubeMemoryLimitMiB: 2048, lineTubeSides: 12 } });
  assert.equal(ctx.params.lineTubeSides, 12, "the appearance still applies");
  ctx.applyDefaultFields = () => {};
  ctx.applyDefaultDatasetView();
  assert.equal(ctx.params.lineTubeCustomMemoryLimit, true);
  assert.equal(ctx.params.lineTubeMemoryLimitMiB, 512);
});

test("automatic tube limits round-trip and geometry caching includes the fitting budget", () => {
  const ctx = viewer();
  Object.assign(ctx.params, { lineTubeAutoDetail: true, lineTubeAutoMaxShapeError: 0.003,
    lineTubeAutoMaxEnergyErrorPercent: 3, lineTubeCustomMemoryLimit: true, lineTubeMemoryLimitMiB: 256 });
  const key = ctx.getFieldLineObjectCacheKey();
  const saved = ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  ctx.params.lineTubeAutoDetail = false;
  ctx.applyViewStateParams(saved);
  assert.equal(ctx.params.lineTubeAutoDetail, true);
  assert.equal(ctx.params.lineTubeAutoMaxShapeError, 0.003);
  assert.equal(ctx.params.lineTubeAutoMaxEnergyErrorPercent, 3);
  ctx.params.lineTubeMemoryLimitMiB = 512;
  assert.notEqual(ctx.getFieldLineObjectCacheKey(), key);
  assert.equal(ctx.applySnapshotParam("lineTubeAutoMaxShapeError", 1), false);
  assert.equal(ctx.applySnapshotParam("lineTubeAutoMaxEnergyErrorPercent", 100), false);
});

test("the viewer uses background-prepared tube geometry with captured colours and connected lines", async () => {
  const ctx = viewer(), fixture = pairedLineFixture(), jobs = [];
  for (const lines of Object.values(fixture)) for (const line of lines) line.strength = line.points.map(() => 2);
  Object.assign(ctx, {
    THREE: RealTHREE, Line2, LineGeometry, unpackGeometry,
    makeLineMaterial: () => new LineMaterial({ vertexColors: true }),
    getFieldLineVertexColor: () => new RealTHREE.Color("red"),
    loadLinesForMode: async mode => fixture[mode],
    runGeometryJob: async (type, payload) => { jobs.push(type); return executeGeometryJob(type, structuredClone(payload)); },
  });
  for (const name of ["makeFieldLineGroup", "prepareTubeLinesInBackground", "buildTubeGeometriesInBackground"]) {
    vm.runInContext(definition(name), ctx);
  }
  ctx.metadata.field_lines = { mode: "both" };
  Object.assign(ctx.params, { showFieldLines: true, lineStride: 3, fieldLineDisplay: "both", lineRenderMode: "b2-tubes" });
  await ctx.loadFieldLines();
  assert.deepEqual(jobs, ["prepare-tubes", "tubes", "tubes"]);
  const { shell, exterior } = ctx.fieldLineGroups;
  assert.equal(shell.children.length, 4); assert.equal(exterior.children.length, 3);
  for (const group of [shell, exterior]) for (const mesh of group.children) {
    assert.ok(mesh.geometry.boundingSphere.radius > 0);
    assert.ok(mesh.geometry.attributes.normal.array.every(Number.isFinite));
    assert.equal(mesh.geometry.attributes.color.getX(0), 1);
    assert.equal(mesh.geometry.attributes.color.getY(0), 0);
    assert.equal(mesh.userData.isMagneticTube, true);
  }
  for (const line of exterior.userData.lines) assert.ok(shell.userData.lines.some(s => s.line_id === line.paired_shell_line_id));
  ctx.disposeHeavyPlaybackCaches();
});

test("dataset response progress displays the logical filename and releases the operation", async () => {
  const ctx = viewer(), updates = [];
  Object.assign(ctx, { readResponseWithProgress });
  for (const name of ["RESPONSE_CLEANUP", "RESPONSE_ABORT_CONTROLLER", "RESPONSE_PROGRESS"]) vm.runInContext(constant(name), ctx);
  vm.runInContext(definition("readDatasetResponse"), ctx);
  let finished = 0;
  ctx.workProgress.begin = text => ({ update: p => updates.push(p), finish: () => finished++ });
  const response = new Response(new Uint8Array([0, 1, 2, 3]), { headers: { "Content-Length": "4" } });
  response.deepDatasetLabel = "Loading Br_volume.f32";
  const result = await ctx.readDatasetResponse(response, "arrayBuffer");
  assert.equal(result.byteLength, 4);
  assert.match(updates.at(-1).label, /Br_volume\.f32/);
  assert.equal(updates.at(-1).fraction, 1);
  assert.equal(finished, 1);
});

test("cancelling before dataset commit keeps the previous dataset and allows retry", async () => {
  const ctx = viewer();
  datasetLoader(ctx, null);
  const previousMetadata = ctx.metadata, previousCoords = ctx.coords;
  const gate = deferred(), started = deferred();
  let cancel, message;
  ctx.workProgress.begin = (_, onCancel) => { cancel = onCancel; return { update() {}, finish() {} }; };
  ctx.setStatus = text => { message = text; };
  ctx.loadMetadataForBase = async () => { started.resolve(); await gate.promise; return previousMetadata; };
  const pending = ctx.loadDatasetFromParams();
  await started.promise;
  cancel(); gate.resolve();
  assert.equal(await pending, false);
  assert.equal(ctx.metadata, previousMetadata); assert.equal(ctx.coords, previousCoords);
  assert.equal(ctx.datasetRootPath, "demo"); assert.equal(ctx.datasetLoadInProgress, false);
  assert.match(message, /cancelled/);
  assert.equal(ctx.datasetRequestSignal, null);
  datasetLoader(ctx, null);
  assert.equal(await ctx.loadDatasetFromParams(), true);
});

test("cancelling after dataset commit restores the old appearance with an un-aborted read context", async () => {
  const ctx = viewer();
  datasetLoader(ctx, null);
  ctx.params.backgroundColor = "#abcdef";
  const previousMetadata = ctx.metadata;
  let cancel, renders = 0, message;
  ctx.workProgress.begin = (_, onCancel) => { cancel = onCancel; return { update() {}, finish() {} }; };
  ctx.setStatus = text => { message = text; };
  ctx.rebuildAllMeshes = async () => {
    renders++;
    if (renders === 1) {
      assert.equal(ctx.datasetRootPath, "new-dataset");
      cancel();
      throw new DOMException("Cancelled", "AbortError");
    }
    assert.equal(ctx.datasetRequestSignal, null, "old uncached files can be read during rollback");
    assert.equal(ctx.params.backgroundColor, "#abcdef");
    assert.equal(ctx.metadata, previousMetadata);
  };
  assert.equal(await ctx.loadDatasetFromParams(), false);
  assert.equal(renders, 2); assert.equal(ctx.datasetRootPath, "demo");
  assert.equal(ctx.datasetLoadInProgress, false);
  assert.match(message, /cancelled.*previous dataset/);
});

test("the title reports tube geometry against the user's current limit", () => {
  const ctx = viewer();
  vm.runInContext(definition("setStatusSummary"), ctx);
  let status;
  ctx.setStatus = value => { status = value; };
  ctx.formatNumber = String;
  Object.assign(ctx.params, { showFieldLines: true, lineRenderMode: "b2-tubes",
    lineTubeCustomMemoryLimit: true, lineTubeMemoryLimitMiB: 512 });
  ctx.fieldLineGroups.shell = { userData: { tubeEstimatedBytes: 20 * 1024 ** 2 } };
  ctx.setStatusSummary();
  assert.match(status, /mesh estimate 20\.0\/512 MiB/);
  ctx.params.lineTubeCustomMemoryLimit = false;
  ctx.setStatusSummary();
  assert.match(status, /mesh estimate 20\.0\/192 MiB/);
});

test("tube stride preserves connected groups and uses one reference before thinning", async () => {
  const ctx = viewer(), fixture = pairedLineFixture();
  for (const [mode, lines] of Object.entries(fixture)) {
    for (const [index, line] of lines.entries()) line.strength = line.points.map(() => mode === "shell" && index === 1 ? 20 : 2);
  }
  Object.assign(ctx, {
    THREE: RealTHREE, Line2, LineGeometry,
    makeLineMaterial: () => new LineMaterial({ vertexColors: true }),
    getFieldLineVertexColor: () => new RealTHREE.Color("red"),
    loadLinesForMode: async mode => fixture[mode],
  });
  vm.runInContext(definition("makeFieldLineGroup"), ctx);
  ctx.metadata.field_lines = { mode: "both" };
  Object.assign(ctx.params, { showFieldLines: true, fieldLineDisplay: "both", lineStride: 3, lineRenderMode: "b2-tubes" });
  await ctx.loadFieldLines();
  const { shell, exterior } = ctx.fieldLineGroups;
  assert.equal(shell.children.length, 4);
  assert.equal(exterior.children.length, 3);
  assert.equal(shell.userData.tubeReference, 20);
  assert.equal(exterior.userData.tubeReference, 20);
  for (const line of exterior.userData.lines) {
    assert.ok(shell.userData.lines.some(s => s.line_id === line.paired_shell_line_id));
  }
  assert.ok(shell.children.every(object => object.isMesh && object.userData.isMagneticTube));
  const key = ctx.getFieldLineObjectCacheKey();
  ctx.params.lineTubeReference = 10;
  assert.notEqual(ctx.getFieldLineObjectCacheKey(), key);
  ctx.params.lineTubeReference = 0;
  ctx.params.lineOpacity = 0.5;
  ctx.updateFieldLineVisuals();
  for (const group of [shell, exterior]) for (const object of group.children) {
    assert.equal(object.material.alphaHash, true);
    assert.equal(object.material.depthWrite, true);
    assert.equal(object.material.transparent, false);
  }
  ctx.params.lineValueTransform = "log10";
  await ctx.loadFieldLines();
  assert.equal(ctx.fieldLineGroups.shell.userData.tubeReference, 20, "colour transform cannot change tube scaling");
  for (const entry of ctx.fieldLineObjectCache.values()) {
    for (const group of Object.values(entry.groups)) ctx.disposeFieldLineGroupResources(group);
  }
});

test("legacy internal tube strengths use the captured Babs grid without mutating line data", async () => {
  const ctx = viewer();
  const original = [{ points: [[0.5, 0, 0], [1, 0, 0]] }];
  ctx.metadata.fields.Babs = "Babs.f32";
  ctx.metadata.field_lines = { mode: "shell" };
  Object.assign(ctx.params, { fieldLineDisplay: "shell", lineRenderMode: "b2-tubes" });
  ctx.loadLinesForMode = async () => original;
  ctx.loadField = async name => { assert.equal(name, "Babs"); return new Float32Array([2, 4]); };
  ctx.sampleVolumeNearest = (field, x) => field[x === 0.5 ? 0 : 1];
  const entry = await ctx.buildFieldLineObjectCacheEntry();
  assert.deepEqual(Array.from(entry.groups.shell.userData.lines[0].strength), [2, 4]);
  assert.equal(entry.groups.shell.userData.lines[0].strength_source, "viewer_grid_Babs");
  assert.equal(original[0].strength, undefined);
});

test("excessive tube geometry leaves the last displayed field lines intact", async () => {
  const ctx = viewer();
  ctx.metadata.field_lines = { mode: "shell" };
  Object.assign(ctx.params, { showFieldLines: true, fieldLineDisplay: "shell", lineStride: 1 });
  ctx.loadLinesForMode = async () => [{ points: [[0, 0, 0], [0, 0, 1]], strength: [1, 1] }];
  await ctx.loadFieldLines();
  const original = ctx.fieldLineGroups.shell;
  ctx.params.lineRenderMode = "b2-tubes";
  ctx.loadLinesForMode = async () => [{ points: { length: 10_000_000 }, strength: [1] }];
  await assert.rejects(ctx.loadFieldLines(), /geometry budget.*limit 192 MiB/);
  assert.equal(ctx.fieldLineGroups.shell, original);
  assert.ok(ctx.scene.objects.has(original));
  assert.equal(original.geometry.disposed, false);
});

test("sequence frames read their own coordinate file even when dimensions match", async () => {
  const ctx = viewer(), newCoords = structuredClone(ctx.coords);
  newCoords.r[1] = 0.8;
  Object.assign(ctx, {
    sequenceFrameLoading: false, sequenceIndex: { frames: [{ path: "frames/second" }] },
    sequenceFrameBasePath: frame => frame.path,
    loadMetadataForBase: async () => ({ ...ctx.metadata }),
    refreshSequenceControllers: () => {}, applyDefaultFields: () => {}, updateVisibility: () => {},
    setDeferredSequenceObjectVisibility: () => {}, formatBytes: String,
  });
  let coordinateReads = 0, reuseGeometry;
  ctx.loadCoordinatesForBase = async base => {
    assert.equal(base, "frames/second"); coordinateReads++; return newCoords;
  };
  ctx.rebuildAllMeshes = async options => { reuseGeometry = options.reuseGeometry; };
  ctx.params.showFieldLines = false;
  Object.assign(ctx.params, { backgroundColor: "#345678", cameraDistance: 7, legendCollapsed: true });
  assert.equal(await ctx.loadFrameByIndex(0), true);
  assert.equal(coordinateReads, 1);
  assert.equal(ctx.coords, newCoords);
  assert.equal(reuseGeometry, false);
  assert.equal(ctx.sequenceFrameLoading, false);
  assert.equal(ctx.params.backgroundColor, "#345678");
  assert.equal(ctx.params.cameraDistance, 7);
  assert.equal(ctx.params.legendCollapsed, true);
});

test("dataset view is applied before the first render, without changing its data source", async () => {
  const ctx = viewer();
  const code = presetCode(ctx, { cameraDistance: 5, backgroundColor: "#123456", earthRadiusScale: 2.1,
    legendCollapsed: true, isoField: "missing", datasetPath: "wrong", sequenceFrame: 99 });
  datasetLoader(ctx, code);
  let renders = 0;
  ctx.rebuildAllMeshes = async () => {
    renders++;
    assert.equal(ctx.params.cameraDistance, 5);
    assert.equal(ctx.params.backgroundColor, "#123456");
    assert.equal(ctx.params.earthRadiusScale, 2.1);
    assert.equal(ctx.params.legendCollapsed, true);
  };
  let status;
  ctx.setStatusSummary = message => { status = message; };
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.equal(renders, 1);
  assert.equal(ctx.datasetRootPath, "new-dataset");
  assert.equal(ctx.params.datasetPath, "new-dataset");
  assert.equal(ctx.params.sequenceFrame, 0);
  assert.equal(ctx.params.isoField, "ur");
  assert.match(status, /view.DTV2 applied.*unavailable fields skipped: missing/);
  assert.equal(ctx.datasetLoadInProgress, false);
});

test("reloading after deleting a Figshare or Zenodo view resets the rendered appearance and camera", async () => {
  for (const provider of ["figshare", "zenodo"]) {
    const { ctx, state, root } = repositoryViewLoader(provider, "33455530");
    const readResource = ctx.fetchDatasetResource, fetch = ctx.fetchWithTimeout;
    datasetLoader(ctx, null);
    ctx.fetchDatasetResource = readResource;
    ctx.params.datasetPath = root;
    ctx.params.sequenceCacheLimitMB = 768;
    ctx.params.secondaryDatasetPath = "keep-this-comparison-path";
    ctx.fetchWithTimeout = (url, options, timeout) => url.includes("/view-")
      ? Promise.resolve(new Response(presetCode(ctx, {
        cameraDistance: 7, cameraAzimuthDeg: 25, cameraElevationDeg: 60,
        cameraTargetX: 0.2, cameraTargetY: -0.1, cameraTargetZ: 0.5, cameraFovDeg: 30,
        backgroundColor: "#abcdef", cmbScale: "manual", cmbMin: -8, cmbMax: 9,
        showCMB: false, showIsosurfaces: true, isoPositiveValue: 0.8,
        legendCollapsed: true, titleVisible: false, titleWidth: 700,
        exportPanelCollapsed: true, earthTextureBody: "mars", lineRenderMode: "b2-tubes",
      }))) : fetch(url, options, timeout);
    Object.assign(ctx.THREE, { Vector3: RealTHREE.Vector3, MathUtils: RealTHREE.MathUtils });
    ctx.camera = new RealTHREE.PerspectiveCamera(45, 1, 0.001, 100);
    ctx.camera.position.set(0, -3, 1.35);
    ctx.controls = { target: new RealTHREE.Vector3(), update: () => {} };
    for (const name of ["syncCameraParamsFromCamera", "applyCameraViewFromParams"]) {
      vm.runInContext(definition(name), ctx);
    }
    const renders = [];
    ctx.rebuildAllMeshes = async () => renders.push({ ...ctx.params });
    let message;
    ctx.setStatusSummary = text => { message = text; };
    assert.equal(await ctx.loadDatasetFromParams(), true);
    assert.equal(ctx.params.cameraDistance, 7);
    assert.equal(ctx.camera.fov, 30);
    assert.equal(renders[0].backgroundColor, "#abcdef");
    assert.match(message, /view\.DTV2 applied/);

    state.hasView = false;
    assert.equal(await ctx.loadDatasetFromParams(), true);
    const displayed = renders.at(-1);
    assert.equal(renders.length, 2);
    assert.equal(displayed.cameraDistance, 3.29);
    assert.equal(displayed.cameraAzimuthDeg, -90);
    assert.equal(displayed.cameraElevationDeg, 24);
    assert.ok(Math.abs(ctx.camera.position.length() - 3.29) < 1e-12);
    assert.deepEqual(ctx.controls.target.toArray(), [0, 0, 0]);
    assert.deepEqual(ctx.camera.up.toArray(), [0, 0, 1]);
    assert.equal(ctx.camera.fov, 45);
    assert.equal(displayed.backgroundColor, "#050505");
    assert.equal(displayed.cmbScale, "symmetric");
    assert.equal(displayed.cmbMin, -1);
    assert.equal(displayed.cmbMax, 1);
    assert.equal(displayed.showCMB, true);
    assert.equal(displayed.showIsosurfaces, false);
    assert.equal(displayed.isoPositiveValue, 0.1);
    assert.equal(displayed.legendCollapsed, false);
    assert.equal(displayed.titleVisible, true);
    assert.equal(displayed.titleWidth, 390);
    assert.equal(displayed.exportPanelCollapsed, false);
    assert.equal(displayed.earthTextureBody, "earth");
    assert.equal(displayed.lineRenderMode, "lines");
    assert.equal(ctx.params.datasetPath, root);
    assert.equal(ctx.params.secondaryDatasetPath, "keep-this-comparison-path");
    assert.equal(ctx.params.sequenceCacheLimitMB, 768);
    assert.match(message, /default view applied/);
    assert.doesNotMatch(message, /view\.DTV2 applied/);
  }
});

test("a new local dataset without a view starts with defaults and fields from its own metadata", async () => {
  const { ctx, selections } = localDatasetViewer();
  const first = selectedFolder(ctx, 1), second = selectedFolder(ctx, 2);
  first.files.set("view.DTV2", new Blob([presetCode(ctx, {
    cameraDistance: 7, backgroundColor: "#abcdef", showCMB: false,
    legendCollapsed: true, isoField: "Br",
  })]));
  const meta = JSON.parse(await second.files.get("metadata.json").text());
  meta.fields = { Comp: "Comp.f32" };
  second.files.set("metadata.json", new Blob([JSON.stringify(meta)]));
  second.files.set("Comp.f32", new Blob([new Float32Array(36).fill(2)]));
  selections.push(first, second);
  assert.equal(await ctx.selectDatasetFolder("primary"), true);
  assert.equal(ctx.params.cameraDistance, 7);
  const firstPath = ctx.datasetRootPath;
  assert.equal(await ctx.selectDatasetFolder("primary"), true);
  assert.notEqual(ctx.datasetRootPath, firstPath);
  assert.equal(ctx.params.cameraDistance, 3.29);
  assert.equal(ctx.params.backgroundColor, "#050505");
  assert.equal(ctx.params.showCMB, true);
  assert.equal(ctx.params.legendCollapsed, false);
  for (const key of ["cmbField", "icbField", "equatorField", "isoField"]) {
    assert.equal(ctx.params[key], "Comp");
  }
  assert.equal(ctx.displayed[0], 2);
  assert.equal(ctx.activeDatasetFolderSource, second);
});

test("sequence view removal tries the first-frame fallback then defaults when both are absent", async () => {
  const ctx = viewer();
  datasetLoader(ctx, null);
  let rootView = true, frameView = true;
  ctx.params.datasetPath = "sequence";
  ctx.fetchSequenceIndexForRoot = async () => ({ frames: [{ path: "frames/first" }, { path: "frames/second" }] });
  ctx.fetchDatasetResource = async url => {
    const isRoot = url === "sequence/view.DTV2";
    return (isRoot ? rootView : frameView)
      ? new Response(presetCode(ctx, { cameraDistance: isRoot ? 6 : 8 }))
      : new Response("", { status: 404 });
  };
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.equal(ctx.params.cameraDistance, 6);
  rootView = false;
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.equal(ctx.params.cameraDistance, 8);
  frameView = false;
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.equal(ctx.params.cameraDistance, 3.29);
  assert.equal(ctx.dataBasePath, "sequence/frames/first");
  assert.equal(ctx.params.sequencePlaybackFirst, 0);
  assert.equal(ctx.params.sequencePlaybackLast, 1);
});

test("a partial new dataset view starts from defaults while failed no-view loads preserve the old view", async () => {
  const ctx = viewer();
  datasetLoader(ctx, presetCode(ctx, { backgroundColor: "#fedcba" }));
  Object.assign(ctx.params, { cameraDistance: 9, backgroundColor: "#123456", legendCollapsed: true });
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.equal(ctx.params.backgroundColor, "#fedcba");
  assert.equal(ctx.params.cameraDistance, 3.29);
  assert.equal(ctx.params.legendCollapsed, false);
  for (const stage of ["metadata", "volume", "render"]) {
    const ctx = viewer();
    datasetLoader(ctx, null);
    ctx.console = { ...console, error: () => {} };
    Object.assign(ctx.params, { cameraDistance: 9, backgroundColor: "#123456", legendCollapsed: true });
    const oldMetadata = ctx.metadata;
    const fail = async () => { throw new Error(`New dataset ${stage} failure`); };
    if (stage === "metadata") ctx.loadMetadataForBase = fail;
    else if (stage === "volume") ctx.loadFloat32ForBase = fail;
    else ctx.rebuildAllMeshes = async () => { if (ctx.datasetRootPath === "new-dataset") await fail(); };
    assert.equal(await ctx.loadDatasetFromParams(), false);
    assert.equal(ctx.params.cameraDistance, 9);
    assert.equal(ctx.params.backgroundColor, "#123456");
    assert.equal(ctx.params.legendCollapsed, true);
    assert.equal(ctx.datasetRootPath, "demo");
    assert.equal(ctx.metadata, oldMetadata);
  }
});

test("missing, malformed and unsupported optional view files do not block dataset loading", async () => {
  for (const contents of [null, "not a code", "DTV2:bad", "<!doctype html><html></html>",
    "DTV2:" + btoa(JSON.stringify({ version: 2, scope: "view-only", params: [] })),
    "DTV2:" + btoa(JSON.stringify({ version: 1, params: { cameraDistance: 9 } }))]) {
    const ctx = viewer();
    datasetLoader(ctx, contents);
    Object.assign(ctx.params, { cameraDistance: 9, backgroundColor: "#abcdef", showCMB: false, legendCollapsed: true });
    assert.equal(await ctx.loadDatasetFromParams(), true);
    assert.equal(ctx.params.cameraDistance, 3.29);
    assert.equal(ctx.params.backgroundColor, "#050505");
    assert.equal(ctx.params.showCMB, true);
    assert.equal(ctx.params.legendCollapsed, false);
  }
});

test("an unrenderable optional view falls back to the normal view of the new dataset", async () => {
  const ctx = viewer();
  datasetLoader(ctx, presetCode(ctx, { cameraDistance: 6, isoPositiveValue: 0.8 }));
  Object.assign(ctx.params, { cameraDistance: 9, backgroundColor: "#abcdef", legendCollapsed: true });
  const seen = [];
  ctx.rebuildAllMeshes = async () => {
    seen.push(ctx.params.cameraDistance);
    if (ctx.params.cameraDistance === 6) throw new Error("saved surface cannot be built");
  };
  let message;
  ctx.setStatus = (text, options) => { if (options?.level === "warning") message = text; };
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.deepEqual(seen, [6, 3.29]);
  assert.equal(ctx.datasetRootPath, "new-dataset");
  assert.equal(ctx.params.isoPositiveValue, 0.1);
  assert.equal(ctx.params.backgroundColor, "#050505");
  assert.equal(ctx.params.legendCollapsed, false);
  assert.match(message, /default view used/);
});

test("a failed dataset switch restores the previous appearance and folder save target", async () => {
  const ctx = viewer(), old = writableFolder();
  ctx.activeDatasetFolderSource = old.source;
  ctx.console = { ...console, error: () => {} };
  datasetLoader(ctx, presetCode(ctx, { cameraDistance: 6, backgroundColor: "#abcdef" }));
  Object.assign(ctx.params, { cameraDistance: 9, backgroundColor: "#123456", legendCollapsed: true });
  ctx.params.sequencePlaying = true;
  const oldMetadata = ctx.metadata, oldColour = ctx.params.backgroundColor;
  ctx.rebuildAllMeshes = async () => {
    if (ctx.datasetRootPath === "new-dataset") throw new Error("new bundle unavailable");
  };
  assert.equal(await ctx.loadDatasetFromParams(), false);
  assert.equal(ctx.datasetRootPath, "demo");
  assert.equal(ctx.metadata, oldMetadata);
  assert.equal(ctx.params.backgroundColor, oldColour);
  assert.equal(ctx.params.cameraDistance, 9);
  assert.equal(ctx.params.legendCollapsed, true);
  assert.equal(ctx.activeDatasetFolderSource, old.source);
  assert.equal(ctx.params.sequencePlaying, false);
});

test("sequence root view takes precedence; initial frame view is a fallback only", async () => {
  const ctx = viewer(), requests = [];
  let rootMissing = false;
  ctx.fetchDatasetResource = async (url, options) => {
    requests.push(url);
    assert.equal(options.timeoutMs, 5000);
    assert.equal(options.cache, "no-store");
    if (url === "sequence/view.DTV2" && rootMissing) return new Response("", { status: 404 });
    return new Response(presetCode(ctx, { cameraDistance: url === "sequence/view.DTV2" ? 4 : 7 }));
  };
  let loaded = await ctx.loadDatasetViewState("sequence", "sequence/frames/first");
  assert.equal(loaded.snapshot.params.cameraDistance, 4);
  assert.deepEqual(requests, ["sequence/view.DTV2"]);
  rootMissing = true; requests.length = 0;
  loaded = await ctx.loadDatasetViewState("sequence", "sequence/frames/first");
  assert.equal(loaded.snapshot.params.cameraDistance, 7);
  assert.deepEqual(requests, ["sequence/view.DTV2", "sequence/frames/first/view.DTV2"]);
});

test("optional view timeout is nonfatal, while dataset cancellation is respected", async () => {
  const ctx = viewer();
  ctx.fetchDatasetResource = async () => { throw new DOMException("view lookup timed out", "TimeoutError"); };
  let loaded = await ctx.loadDatasetViewState("remote");
  assert.equal(loaded.snapshot, null);
  assert.match(loaded.warnings[0], /timed out/);
  const controller = new AbortController();
  controller.abort();
  ctx.fetchDatasetResource = async () => new Response(presetCode(ctx));
  await assert.rejects(ctx.loadDatasetViewState("remote", "remote", controller.signal), { name: "AbortError" });
});

test("view files use existing HTTP, local filesystem, Figshare and Zenodo routing", async () => {
  const ctx = viewer(), calls = [];
  ctx.remoteRepositoryIndexCache = new Map();
  ctx.normaliseRepositoryPath = value => String(value || "");
  ctx.buildFigshareIndex = async () => new Map([["view.DTV2", "https://files.example/figshare-view"]]);
  ctx.buildZenodoIndex = async () => new Map([["view.DTV2", "https://files.example/zenodo-view"]]);
  ctx.fetchWithTimeout = async (url, options, timeout) => {
    calls.push({ url, cache: options.cache, timeout });
    return new Response(presetCode(ctx, { cameraDistance: 8 }));
  };
  for (const name of ["fetchRemoteRepositoryResource", "fetchDatasetResource"]) vm.runInContext(definition(name), ctx);
  for (const root of ["https://example.org/data", "localfs:/tmp/data", "figshare:123", "zenodo:456"]) {
    const loaded = await ctx.loadDatasetViewState(root);
    assert.equal(loaded.snapshot.params.cameraDistance, 8);
  }
  assert.equal(calls[0].url, "https://example.org/data/view.DTV2");
  assert.ok(calls[1].url.startsWith("/__localfs__/"));
  assert.equal(calls[2].url, "https://files.example/figshare-view");
  assert.equal(calls[3].url, "https://files.example/zenodo-view");
  assert.ok(calls.every(call => call.cache === "no-store" && call.timeout === 5000));
});

function repositoryViewLoader(provider, recordId = "33455986") {
  const ctx = viewer(), calls = [];
  const state = { revision: 1, hasView: true };
  const root = `${provider}:${recordId}`;
  const apiUrl = provider === "figshare"
    ? `https://deep-figshare-proxy.ludhovik-research.workers.dev/figshare/articles/${recordId}`
    : `https://zenodo.org/api/records/${recordId}`;
  ctx.remoteRepositoryIndexCache = new Map();
  ctx.fetchWithTimeout = async (url, options, timeout) => {
    calls.push({ url, ...options, timeout });
    if (url === apiUrl) {
      const files = [["metadata.json", "https://files.example/metadata"]];
      if (state.hasView) files.push(["view.DTV2", `https://files.example/view-${state.revision}`]);
      return Response.json(provider === "figshare"
        ? { files: files.map(([name, download_url], id) => ({ id, name, download_url })) }
        : { files: files.map(([key, content]) => ({ key, links: { content } })) });
    }
    if (url === "https://files.example/metadata") return Response.json({ fields: {} });
    const revision = Number(url.match(/view-(\d+)$/)?.[1]);
    assert.ok(revision > 0, `Unexpected download: ${url}`);
    return new Response(presetCode(ctx, { cameraDistance: revision + 3 }));
  };
  for (const name of ["normaliseRepositoryPath", "stripRepositoryDatasetPrefix", "buildFigshareIndex",
    "buildZenodoIndex", "fetchRemoteRepositoryResource", "fetchDatasetResource"]) {
    vm.runInContext(definition(name), ctx);
  }
  return { ctx, calls, state, root, apiUrl };
}

test("reopening a Figshare or Zenodo view discovers replaced file IDs and keeps ordinary reads cached", async () => {
  for (const provider of ["figshare", "zenodo"]) {
    const { ctx, calls, state, root, apiUrl } = repositoryViewLoader(provider);
    const controller = new AbortController();
    const first = await ctx.loadDatasetViewState(root, root, controller.signal);
    assert.equal(first.snapshot.params.cameraDistance, 4);
    state.revision = 2;
    const second = await ctx.loadDatasetViewState(root, root, controller.signal);
    assert.equal(second.snapshot.params.cameraDistance, 5);
    assert.equal(calls.filter(call => call.url === apiUrl).length, 2);
    assert.ok(calls.every(call => call.cache === "no-store" && call.timeout === 5000
      && call.signal === controller.signal));
    // A view refresh updates the shared index without forcing another API
    // request for each subsequent data file or clearing the volume caches.
    const cachedVolume = new Float32Array([1, 2, 3]);
    ctx.dataCache.set(`${root}/Br.f32`, cachedVolume);
    await ctx.fetchDatasetResource(`${root}/metadata.json`);
    await ctx.fetchDatasetResource(`${root}/metadata.json`);
    assert.equal(calls.filter(call => call.url === apiUrl).length, 2);
    assert.equal(ctx.dataCache.get(`${root}/Br.f32`), cachedVolume);
  }
});

test("a saved view added after opening a record is discovered without refreshing the page", async () => {
  for (const provider of ["figshare", "zenodo"]) {
    const { ctx, state, root } = repositoryViewLoader(provider);
    state.hasView = false;
    assert.equal((await ctx.loadDatasetViewState(root)).snapshot, null);
    state.hasView = true;
    assert.equal((await ctx.loadDatasetViewState(root)).snapshot.params.cameraDistance, 4);
  }
});

test("failed old record or file requests cannot discard a newly refreshed repository index", async () => {
  for (const failureStage of ["record", "file"]) {
    const { ctx, calls, state, root, apiUrl } = repositoryViewLoader("figshare");
    const pending = deferred(), started = deferred(), fetch = ctx.fetchWithTimeout;
    let waiting = true;
    ctx.fetchWithTimeout = (url, options, timeout) => {
      if (waiting && url === (failureStage === "record" ? apiUrl : "https://files.example/view-1")) {
        waiting = false;
        started.resolve();
        return pending.promise;
      }
      return fetch(url, options, timeout);
    };
    const oldRead = ctx.fetchRemoteRepositoryResource(`${root}/view.DTV2`);
    await started.promise;
    state.revision = 2;
    assert.equal((await ctx.loadDatasetViewState(root)).snapshot.params.cameraDistance, 5);
    const currentIndex = ctx.remoteRepositoryIndexCache.get(root);
    pending.reject(new Error("Old request failed"));
    assert.equal((await oldRead).status, 502);
    assert.equal(ctx.remoteRepositoryIndexCache.get(root), currentIndex);
    const lookupsBefore = calls.filter(call => call.url === apiUrl).length;
    await ctx.fetchDatasetResource(`${root}/metadata.json`);
    assert.equal(calls.filter(call => call.url === apiUrl).length, lookupsBefore);
  }
});

test("optional view record refreshes propagate timeout and cancellation and can be retried", async () => {
  for (const provider of ["figshare", "zenodo"]) {
    const { ctx, root } = repositoryViewLoader(provider);
    await ctx.fetchDatasetResource(`${root}/metadata.json`);
    const workingIndex = ctx.remoteRepositoryIndexCache.get(root);
    const fetch = ctx.fetchWithTimeout;
    ctx.fetchWithTimeout = async (_url, options, timeout) => {
      assert.equal(timeout, 5000);
      assert.equal(options.cache, "no-store");
      if (options.signal?.aborted) throw options.signal.reason;
      throw new DOMException("Record refresh timed out", "TimeoutError");
    };
    const missed = await ctx.loadDatasetViewState(root);
    assert.equal(missed.snapshot, null);
    assert.match(missed.warnings[0], /Record refresh timed out/);
    assert.equal(ctx.remoteRepositoryIndexCache.get(root), workingIndex);
    const controller = new AbortController();
    controller.abort();
    await assert.rejects(ctx.fetchRemoteRepositoryResource(`${root}/view.DTV2`, {
      cache: "no-store", timeoutMs: 5000, signal: controller.signal,
    }), { name: "AbortError" });
    assert.equal(ctx.remoteRepositoryIndexCache.get(root), workingIndex);
    ctx.fetchWithTimeout = fetch;
    assert.equal((await ctx.loadDatasetViewState(root)).snapshot.params.cameraDistance, 4);
  }
});

test("folder-selected files can supply view.DTV2 without requesting write permission", async () => {
  const ctx = viewer(), folder = writableFolder();
  const code = presetCode(ctx, { cameraDistance: 8 });
  folder.state.files.set("view.DTV2", code);
  ctx.fetchRemoteRepositoryResource = async () => null;
  vm.runInContext(definition("fetchDatasetResource"), ctx);
  for (const source of [folder.source, { type: "files", files: new Map([["view.DTV2", new Blob([code])]]) }]) {
    ctx.datasetFolderSources.set("primary", source);
    const loaded = await ctx.loadDatasetViewState("fsdir:primary");
    assert.equal(loaded.snapshot.params.cameraDistance, 8);
  }
  assert.deepEqual(folder.state.requests, []);
});

test("Save writes the current code at the selected dataset root, even during a sequence", async () => {
  const ctx = viewer(), folder = writableFolder();
  ctx.datasetRootPath = "fsdir:primary/run";
  ctx.dataBasePath = "fsdir:primary/run/frames/second";
  ctx.activeDatasetFolderSource = folder.source;
  ctx.params.sequenceFrame = 10;
  ctx.params.cameraDistance = 7;
  ctx.saveBlob = async () => { throw new Error("Download should not be used"); };
  await ctx.saveViewStateCode();
  assert.deepEqual(folder.state.requests, ["readwrite"]);
  assert.deepEqual([...folder.state.files.keys()], ["run/view.DTV2"]);
  const code = ctx.decodeViewState(folder.state.files.get("run/view.DTV2"));
  assert.equal(code.params.cameraDistance, 7);
  assert.equal(code.params.sequenceFrame, undefined);
  assert.equal(code.params.datasetPath, undefined);
  assert.equal(ctx.datasetViewSaveInProgress, false);
});

test("a saved folder view is read afresh when the dataset is reopened", async () => {
  const ctx = viewer(), folder = writableFolder();
  ctx.datasetRootPath = "fsdir:primary";
  ctx.activeDatasetFolderSource = folder.source;
  ctx.params.cameraDistance = 7;
  ctx.params.backgroundColor = "#abc123";
  await ctx.saveViewStateCode();
  ctx.params.cameraDistance = 2;
  datasetLoader(ctx, null);
  ctx.params.datasetPath = "fsdir:primary";
  ctx.datasetFolderSources.set("primary", folder.source);
  ctx.fetchRemoteRepositoryResource = async () => null;
  vm.runInContext(definition("fetchDatasetResource"), ctx);
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.equal(ctx.params.cameraDistance, 7);
  assert.equal(ctx.params.backgroundColor, "#abc123");
  assert.equal(ctx.activeDatasetFolderSource, folder.source);
  assert.deepEqual(folder.state.requests, ["readwrite"]);
});

test("remote, read-only, and denied-write sources fall back to the same view.DTV2 filename", async () => {
  for (const [root, folder] of [["figshare:123", null], ["fsdir:primary", { type: "files" }],
    ["fsdir:primary", writableFolder("denied").source]]) {
    const ctx = viewer();
    ctx.datasetRootPath = root;
    ctx.activeDatasetFolderSource = folder;
    const downloads = [];
    ctx.saveBlob = async (blob, filename) => { downloads.push({ code: await blob.text(), filename }); return "downloaded"; };
    await ctx.saveViewStateCode();
    assert.equal(downloads.length, 1);
    assert.equal(downloads[0].filename, "view.DTV2");
    assert.equal(ctx.decodeViewState(downloads[0].code).scope, "view-only");
  }
});

test("cancelling save does not open another dialog or write a view file", async () => {
  const ctx = viewer(), folder = writableFolder();
  folder.source.handle.requestPermission = async () => { throw new DOMException("cancelled", "AbortError"); };
  ctx.datasetRootPath = "fsdir:primary";
  ctx.activeDatasetFolderSource = folder.source;
  ctx.saveBlob = async () => { throw new Error("No fallback after cancellation"); };
  await ctx.saveViewStateCode();
  assert.equal(folder.state.files.size, 0);
  assert.equal(ctx.datasetViewSaveInProgress, false);
});

test("failed view writes abort the stream and preserve its old contents", async () => {
  const ctx = viewer(), folder = writableFolder();
  folder.state.files.set("view.DTV2", "old view");
  folder.state.failWrite = true;
  await assert.rejects(ctx.writeDatasetViewFile(folder.source, "", new Blob(["new view"])), /disk full/);
  assert.equal(folder.state.files.get("view.DTV2"), "old view");
  assert.equal(folder.state.aborted, true);
});

test("save captures the view and folder before awaiting permission and ignores duplicate clicks", async () => {
  const ctx = viewer(), folder = writableFolder(), permission = deferred();
  folder.source.handle.requestPermission = () => permission.promise;
  ctx.datasetRootPath = "fsdir:primary/first";
  ctx.activeDatasetFolderSource = folder.source;
  ctx.params.cameraDistance = 4;
  const pending = ctx.saveViewStateCode();
  ctx.datasetRootPath = "fsdir:primary/second";
  ctx.activeDatasetFolderSource = writableFolder().source;
  ctx.params.cameraDistance = 9;
  await ctx.saveViewStateCode();
  permission.resolve("granted"); await pending;
  assert.deepEqual([...folder.state.files.keys()], ["first/view.DTV2"]);
  assert.equal(ctx.decodeViewState(folder.state.files.get("first/view.DTV2")).params.cameraDistance, 4);
});

test("Save refuses a half-loaded dataset", async () => {
  const ctx = viewer();
  ctx.datasetLoadInProgress = true;
  ctx.saveBlob = async () => { throw new Error("No save during loading"); };
  await ctx.saveViewStateCode();
  assert.equal(ctx.datasetViewSaveInProgress, false);
});


test("inner-core magnetic region survives view codes and rejects invalid values", () => {
  const ctx = viewer();
  ctx.params.magneticVolumeDomain = "inner-core";
  const snapshot = ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  ctx.params.magneticVolumeDomain = "all";
  ctx.applyViewStateParams(snapshot);
  assert.equal(ctx.params.magneticVolumeDomain, "inner-core");
  ctx.applySnapshotParam("magneticVolumeDomain", "unrecognised");
  assert.equal(ctx.params.magneticVolumeDomain, "inner-core");
});

test("isosurface legend follows committed meshes through pending, failed, hidden and recoloured views", async () => {
  const ctx = viewer();
  ctx.THREE = RealTHREE;
  ctx.buildIsosurfaceInBackground = async () => new RealTHREE.SphereGeometry(.5,8,8);
  ctx.params.showIsoNegative = true;
  await ctx.rebuildIsosurfaces();
  let entries = isosurfaceLegendEntries([ctx.isoPositiveMesh,ctx.isoNegativeMesh]);
  assert.equal(entries.length,2);
  assert.equal(entries[0].value,.1);
  assert.equal(entries[1].value,-.1);
  const waiting = deferred();
  ctx.params.isoPositiveValue = .2;
  ctx.buildIsosurfaceInBackground = () => waiting.promise;
  const pending = ctx.rebuildIsosurfaces();
  assert.equal(isosurfaceLegendEntries([ctx.isoPositiveMesh])[0].value,.1);
  waiting.reject(new Error("failed replacement"));
  await assert.rejects(pending,/failed replacement/);
  assert.equal(isosurfaceLegendEntries([ctx.isoPositiveMesh])[0].value,.1);
  ctx.isoPositiveMesh.material.color.set("#123456");
  assert.equal(isosurfaceLegendEntries([ctx.isoPositiveMesh])[0].color,"#123456");
  ctx.isoNegativeMesh.visible = false;
  assert.equal(isosurfaceLegendEntries([ctx.isoPositiveMesh,ctx.isoNegativeMesh]).length,1);
  ctx.detachActiveIsosurfaces();
  assert.equal(isosurfaceLegendEntries([ctx.isoPositiveMesh,ctx.isoNegativeMesh]).length,0);
});

test("actual radial and meridional meshes expose IC magnetism and exclude fluid zero padding", async () => {
  const ctx = viewer();
  ctx.THREE = RealTHREE;
  ctx.metadata = {nr:5,ntheta:3,nphi:4,r_inner:0,r_outer:1,r_icb:.5,has_inner_core:true,
    fields:{Br:"B.f32", C:"C.f32"},field_domains:{Br:{r_min:0,r_max:1},C:{r_min:.5,r_max:1}}};
  ctx.coords.r = [0,.25,.5,.75,1];
  ctx.loadFloat32ForBase = async () => new Float32Array(60).fill(1);
  ctx.colourMap = () => new RealTHREE.Color("red");
  for (const name of ["loadField","idx","radiusAtIndex","thetaAtIndex","phiAtIndex","normalizePhi","angularDistance",
    "nearestRadiusIndex","nearestThetaIndex","nearestPhiIndex","radialSurfaceSampling","radialSurfaceValue",
    "makeMeridionalSliceMesh","makeHorizontalSliceMesh","updateSampledMeshColours","updateMeshColourBuffer"])
    vm.runInContext(definition(name),ctx);
  const magnetic = await ctx.loadField("Br"), fluid = await ctx.loadField("C");
  const firstRadius = mesh => {
    const a=mesh.geometry.attributes.position.array;
    return Math.hypot(a[0],a[1],a[2]);
  };
  assert.equal(firstRadius(ctx.makeMeridionalSliceMesh(magnetic,0,1,0,1,"viridis")),0);
  assert.ok(Math.abs(firstRadius(ctx.makeMeridionalSliceMesh(fluid,0,1,0,1,"viridis"))-.5)<1e-6);
  const fluidSlice=ctx.makeHorizontalSliceMesh(fluid,0,1,0,1,"viridis");
  assert.ok(Math.abs(firstRadius(fluidSlice)-.5)<1e-6);
  assert.equal(ctx.updateSampledMeshColours(fluidSlice,magnetic,"horizontal",0,1,"viridis"),false,
    "a shell-only mesh cannot be reused for a field extending into the core");
  ctx.params.magneticVolumeDomain="inner-core";
  const core=ctx.makeMeridionalSliceMesh(magnetic,0,1,0,1,"viridis");
  const p=core.geometry.attributes.position.array;
  for(let i=0;i<p.length;i+=3) assert.ok(Math.hypot(p[i],p[i+1],p[i+2])<=.500001);
  ctx.params.radialSurfaceRadiusRo=.2;
  assert.ok(Math.abs(ctx.radialSurfaceSampling(magnetic).radius-.2)<1e-10);
  assert.equal(ctx.radialSurfaceSampling(fluid).radius,.5);
  ctx.params.magneticVolumeDomain="fluid";
  assert.equal(ctx.radialSurfaceSampling(magnetic).radius,.5);
});

test("split meridian uses independent fields and radial domains on its two sides", async () => {
  const ctx=viewer();ctx.THREE=RealTHREE;
  ctx.metadata={nr:5,ntheta:3,nphi:4,r_inner:0,r_outer:1,r_icb:.5,has_inner_core:true,
    fields:{Br:"B.f32",C:"C.f32"},field_domains:{Br:{r_min:0,r_max:1},C:{r_min:.5,r_max:1}}};
  ctx.coords.r=[0,.25,.5,.75,1];ctx.colourMap=()=>new RealTHREE.Color("red");
  for(const name of ["idx","radiusAtIndex","thetaAtIndex","phiAtIndex","normalizePhi","angularDistance","nearestPhiIndex",
    "makeMeridionalSliceMesh","makeSplitMeridionalSliceGroup"])
    vm.runInContext(definition(name),ctx);
  const magnetic=new Float32Array(60).fill(1),fluid=new Float32Array(60).fill(2);
  Object.defineProperty(magnetic,"viewerDomain",{value:{r_min:0,r_max:1,magnetic:true}});
  Object.defineProperty(fluid,"viewerDomain",{value:{r_min:.5,r_max:1,magnetic:false}});
  const group=ctx.makeSplitMeridionalSliceGroup(magnetic,fluid,30,{
    right:{opacity:.8,vmin:-1,vmax:1,colormap:"viridis"},
    left:{opacity:.3,vmin:0,vmax:2,colormap:"blue-white-red"},
  });
  assert.equal(group.children.length,2);
  const right=group.children.find(child=>child.userData.meridianSide==="right");
  const left=group.children.find(child=>child.userData.meridianSide==="left");
  const firstRadius=mesh=>Math.hypot(...mesh.geometry.attributes.position.array.slice(0,3));
  assert.equal(firstRadius(right),0);
  assert.ok(Math.abs(firstRadius(left)-.5)<1e-6);
  assert.equal(right.material.opacity,.8);assert.equal(left.material.opacity,.3);
  assert.ok(right.geometry.attributes.position.array[0]>=0);
  assert.ok(left.geometry.attributes.position.array[0]<=0);
});

test("isovalue swatches are included in export even when no colourbars are visible", () => {
  const ctx=viewer(); ctx.THREE=RealTHREE;
  ctx.params.legendVisible=true;ctx.params.legendCollapsed=false;
  ctx.getVisibleColourbarSlots=()=>[];
  ctx.isoPositiveMesh=new RealTHREE.Mesh(new RealTHREE.SphereGeometry(.5,8,8),new RealTHREE.MeshBasicMaterial({color:"#abc123"}));
  ctx.isoPositiveMesh.userData.isoLegend={field:"Br",value:.125};
  ctx.drawRoundedRectPath=()=>{};
  ctx.window.innerWidth=1000;
  vm.runInContext(definition("drawExportColourbars"),ctx);
  const labels=[],swatches=[];
  const canvas={save(){},restore(){},fill(){},stroke(){},fillText(label){labels.push(label)},fillRect(){swatches.push(this.fillStyle)}};
  ctx.drawExportColourbars(canvas,1000,700);
  assert.ok(labels.includes("Br = 0.125"));assert.ok(swatches.includes("#abc123"));
  labels.length=0;ctx.params.legendCollapsed=true;
  ctx.drawExportColourbars(canvas,1000,700);
  assert.equal(labels.length,0);
});

test("local Br polarity colours both ends independently and survives view codes", () => {
  const ctx = viewer();ctx.THREE = RealTHREE;
  vm.runInContext(definition("getFieldLineVertexColor"),ctx);
  ctx.params.lineColourMode = "radial-polarity";
  assert.equal(ctx.getFieldLineVertexColor(1,-1,0,2,3).getHex(),0xffd700);
  assert.equal(ctx.getFieldLineVertexColor(1,1,0,2,-3).getHex(),0x246bff);
  for (const missing of [undefined,null,NaN,Infinity,0,"3"])
    assert.equal(ctx.getFieldLineVertexColor(1,1,0,2,missing).getHex(),0xaab0bb);
  const key=ctx.getFieldLineObjectCacheKey();
  const saved=ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  ctx.params.lineColourMode="polarity";
  assert.notEqual(ctx.getFieldLineObjectCacheKey(),key);
  ctx.applyViewStateParams(saved);assert.equal(ctx.params.lineColourMode,"radial-polarity");
});

test("real line and tube geometries receive local Br colours at matching points", () => {
  const ctx=viewer();Object.assign(ctx,{THREE:RealTHREE,Line2,LineGeometry,
    makeLineMaterial:()=>new LineMaterial({vertexColors:true})});
  vm.runInContext(definition("getFieldLineVertexColor")+"\n"+definition("makeFieldLineGroup"),ctx);
  Object.assign(ctx.params,{lineColourMode:"radial-polarity",lineRenderMode:"lines"});
  const line={polarity:1,points:[[1,0,0],[1,0,1],[1,0,2]],strength:[1,1,1],radial_field:[2,-2,0]};
  let group=ctx.makeFieldLineGroup([line],"shell",[line],1);
  let start=group.children[0].geometry.getAttribute("instanceColorStart");
  const yellow=new RealTHREE.Color(0xffd700),blue=new RealTHREE.Color(0x246bff);
  for(const [i,c] of [[0,yellow],[1,blue]])
    assert.ok(Math.abs(start.getX(i)-c.r)<1e-7 && Math.abs(start.getZ(i)-c.b)<1e-7);
  ctx.disposeFieldLineGroupResources(group);
  ctx.params.lineRenderMode="b2-tubes";ctx.params.lineTubeSides=8;
  group=ctx.makeFieldLineGroup([line],"shell",[line],1);
  const colours=group.children[0].geometry.getAttribute("color");
  assert.ok(Math.abs(colours.getX(0)-yellow.r)<1e-7);
  assert.ok(Math.abs(colours.getZ(8)-blue.b)<1e-7);
  ctx.disposeFieldLineGroupResources(group);
});

test("tube worker colour preparation preserves local Br after simplification", async () => {
  const ctx=viewer();ctx.THREE=RealTHREE;
  Object.assign(ctx,{datasetRequestSignal:null,
    runGeometryJob:async(type,payload)=>executeGeometryJob(type,payload),unpackGeometry});
  vm.runInContext(definition("getFieldLineVertexColor")+"\n"+definition("buildTubeGeometriesInBackground"),ctx);
  Object.assign(ctx.params,{lineColourMode:"radial-polarity",lineTubeSides:8,linePositiveColor:"#33aa77",lineNegativeColor:"#cc2288"});
  const line={points:Array.from({length:20},(_,i)=>[1,0,i/20]),strength:Array(20).fill(1),
    radial_field:Array.from({length:20},(_,i)=>i===10?-1:1)};
  const reduced=simplifyMagneticLine(line,{enabled:true,positionTolerance:.01,energyTolerance:.01});
  assert.ok(reduced.points.length<20);
  for(const i of [9,10,11])assert.ok(reduced.points.some(p=>p[2]===i/20));
  assert.deepEqual(reduced.radial_field,reduced.points.map(p=>p[2]===.5?-1:1));
  const geometries=await ctx.buildTubeGeometriesInBackground([line],[reduced],ctx.captureRenderContext(),1);
  const negativeIndex=reduced.radial_field.indexOf(-1),colours=geometries[0].getAttribute("color");
  assert.ok(Math.abs(colours.getZ(negativeIndex*8)-new RealTHREE.Color("#cc2288").b)<1e-7);
  geometries.forEach(g=>g.dispose());
});

test("polarity legend distinguishes local values from CMB starting values", () => {
  const ctx=viewer(), elements=Object.fromEntries(["line-positive-label","line-negative-label","line-polarity-note"].map(k=>[k,{}]));
  const swatches={".yellow":{style:{}},".blue":{style:{}}};
  ctx.lineLegendEl={style:{},querySelector:key=>swatches[key]};ctx.document={getElementById:key=>elements[key]};
  vm.runInContext(definition("setLineLegendMode"),ctx);
  ctx.params.showFieldLines=true;ctx.setLineLegendMode("radial-polarity");
  assert.match(elements["line-positive-label"].textContent,/here/);
  assert.match(elements["line-polarity-note"].textContent,/unavailable/);
  ctx.setLineLegendMode("polarity");assert.match(elements["line-positive-label"].textContent,/start/);
  ctx.setLineLegendMode("strength");assert.equal(ctx.lineLegendEl.style.display,"none");
});

test("local polarity swatches are exported without a strength colourbar", () => {
  const ctx=viewer();Object.assign(ctx.params,{legendVisible:true,legendCollapsed:false,showFieldLines:true,lineColourMode:"radial-polarity"});
  ctx.getVisibleColourbarSlots=()=>[];ctx.drawRoundedRectPath=()=>{};ctx.window.innerWidth=1000;
  vm.runInContext(definition("drawExportColourbars"),ctx);
  const labels=[],swatches=[];
  const canvas={save(){},restore(){},fill(){},stroke(){},fillText(label){labels.push(label)},fillRect(){swatches.push(this.fillStyle)}};
  ctx.drawExportColourbars(canvas,1000,700);
  assert.ok(labels.includes("Br > 0: outward here"));assert.ok(labels.includes("Br < 0: inward here"));
  assert.deepEqual(swatches,["#ffd700","#246bff"]);
  labels.length=0;ctx.params.legendCollapsed=true;ctx.drawExportColourbars(canvas,1000,700);assert.equal(labels.length,0);
});

test("a dipole arc colours its negative CMB endpoint by local Br, independent of point order", () => {
  const ctx=viewer();Object.assign(ctx,{THREE:RealTHREE,Line2,LineGeometry,
    makeLineMaterial:()=>new LineMaterial({vertexColors:true})});
  vm.runInContext(definition("getFieldLineVertexColor")+"\n"+definition("makeFieldLineGroup"),ctx);
  // Dipole field: r = 2 sin²(theta), Br = 2 cos(theta) / r³, CMB radius = 1.
  const theta=Array.from({length:33},(_,i)=>Math.PI/4+i*Math.PI/64);
  const points=theta.map(t=>{const r=2*Math.sin(t)**2;return [r*Math.sin(t),0,r*Math.cos(t)];});
  const radial=theta.map(t=>2*Math.cos(t)/(2*Math.sin(t)**2)**3);
  for(const reverse of [false,true]) for(const render of ["lines","b2-tubes"]) {
    const line={points:reverse?[...points].reverse():points,radial_field:reverse?[...radial].reverse():radial,
      strength:Array(33).fill(1),polarity:1};
    Object.assign(ctx.params,{lineRenderMode:render,lineTubeSides:8,lineColourMode:"radial-polarity",
      linePositiveColor:"#ee8811",lineNegativeColor:"#1133cc"});
    const group=ctx.makeFieldLineGroup([line],"exterior",[line],1),g=group.children[0].geometry;
    for(const endpoint of [0,32]) {
      const expected=new RealTHREE.Color(line.radial_field[endpoint]>0?"#ee8811":"#1133cc");
      const a=render==="lines"?g.getAttribute(endpoint===0?"instanceColorStart":"instanceColorEnd"):g.getAttribute("color");
      const i=render==="lines"?(endpoint===0?0:31):endpoint*8;
      for(const [value,want] of [[a.getX(i),expected.r],[a.getY(i),expected.g],[a.getZ(i),expected.b]])
        assert.ok(Math.abs(value-want)<1e-7);
    }
    ctx.disposeFieldLineGroupResources(group);
  }
  // Starting-footpoint mode deliberately stays positive at the negative return.
  ctx.params.lineColourMode="polarity";
  assert.equal(ctx.getFieldLineVertexColor(1,1,0,2,radial.at(-1)).getHexString(),"ee8811");
});

test("both polarity colours invalidate cached geometry and round-trip with validation", () => {
  const ctx=viewer();ctx.params.lineColourMode="radial-polarity";
  const original=ctx.getFieldLineObjectCacheKey();
  assert.equal(ctx.applySnapshotParam("linePositiveColor","#123456"),true);
  const positive=ctx.getFieldLineObjectCacheKey();assert.notEqual(original,positive);
  assert.equal(ctx.applySnapshotParam("lineNegativeColor","#ABCDEF"),true);
  assert.notEqual(positive,ctx.getFieldLineObjectCacheKey());
  const saved=ctx.decodeViewState(ctx.encodeViewState(ctx.collectViewState()));
  ctx.params.linePositiveColor="#ffffff";ctx.params.lineNegativeColor="#000000";
  ctx.applyViewStateParams(saved);
  assert.equal(ctx.params.linePositiveColor,"#123456");assert.equal(ctx.params.lineNegativeColor,"#ABCDEF");
  for(const invalid of [null,23,"red","#12","#abcdef00","url(x)","#GG0000"])
    for(const key of ["linePositiveColor","lineNegativeColor"])assert.equal(ctx.applySnapshotParam(key,invalid),false);
  assert.equal(ctx.applySnapshotParam("lineColourMode","invalid"),false);
  assert.equal(ctx.params.linePositiveColor,"#123456");
});

test("custom polarity colours match DOM and export legends in both modes", () => {
  const ctx=viewer();Object.assign(ctx.params,{legendVisible:true,legendCollapsed:false,showFieldLines:true,
    linePositiveColor:"#33aa77",lineNegativeColor:"#cc2288"});
  const elements=Object.fromEntries(["line-positive-label","line-negative-label","line-polarity-note"].map(k=>[k,{}]));
  const swatches={".yellow":{style:{}},".blue":{style:{}}};
  ctx.lineLegendEl={style:{},querySelector:key=>swatches[key]};ctx.document={getElementById:key=>elements[key]};
  ctx.getVisibleColourbarSlots=()=>[];ctx.drawRoundedRectPath=()=>{};ctx.window.innerWidth=1000;
  vm.runInContext(definition("setLineLegendMode")+"\n"+definition("drawExportColourbars"),ctx);
  for(const mode of ["polarity","radial-polarity"]) {
    ctx.params.lineColourMode=mode;ctx.setLineLegendMode(mode);
    assert.equal(swatches[".yellow"].style.background,"#33aa77");assert.equal(swatches[".blue"].style.background,"#cc2288");
    const exported=[];
    const canvas={save(){},restore(){},fill(){},stroke(){},fillText(){},fillRect(){exported.push(this.fillStyle)}};
    ctx.drawExportColourbars(canvas,1000,700);assert.deepEqual(exported,["#33aa77","#cc2288"]);
  }
});
