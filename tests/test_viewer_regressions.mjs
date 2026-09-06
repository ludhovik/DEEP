// Code-level regressions against the actual viewer functions. Rendering and
// network objects are small test doubles; this is not a browser/GPU test suite.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import test from "node:test";

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
    console, DOMException, Response, Blob, AbortController, performance, TextEncoder, Float32Array, btoa, atob,
    window: { setInterval, clearInterval, setTimeout, clearTimeout },
    DEFAULT_DATASET_ROOT: "demo", DEFAULT_SECONDARY_DATASET_ROOT: "secondary",
    THREE: { Mesh, Color, MeshPhongMaterial: Material, DoubleSide: 2, NormalBlending: 1, NoBlending: 0 },
    metadata: { nr: 3, ntheta: 3, nphi: 4, r_inner: 0.35, r_outer: 1,
      fields: { ur: "ur.f32", Br: "Br.f32", C: "C.f32" } },
    coords: { r: [0.35, 0.7, 1], theta: [0.1, 1.5, 3.0], phi: [0, Math.PI / 2, Math.PI, 3 * Math.PI / 2] },
    dataBasePath: "demo", datasetRootPath: "demo", secondaryDataset: null,
    activeDatasetFolderSource: null, datasetFolderSources: new Map(),
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
    getCmbFieldNames: () => ["Br", "C", "ur"],
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
    makeFieldLineGroup: (lines, mode) => {
      const group = new Mesh(new Geometry(mode), new Material({ linewidth: 2 }));
      group.userData.lines = lines;
      group.traverse = callback => callback(group);
      return group;
    },
  });
  for (const name of ["cmbMesh", "icbMesh", "radialSurfaceMesh", "equatorMesh", "equator2Mesh", "meridianMesh", "meridian2Mesh", "earthMesh", "isoPositiveMesh", "isoNegativeMesh", "equatorFillerMesh", "equator2FillerMesh", "meridianFillerMesh", "meridian2FillerMesh"]) ctx[name] = null;
  vm.runInContext(constant("params", "\n};") + "\nglobalThis.params = params;", ctx);
  Object.assign(ctx.params, { showIsosurfaces: true, showIsoNegative: false });
  for (const name of ["VIEW_STATE_PREFIX", "LEGACY_VIEW_STATE_PREFIX", "VIEW_STATE_EXCLUDED_PARAMS", "VIEW_STATE_PARAM_TYPES", "VIEW_STATE_SCALE_KEYS", "VIEW_STATE_NUMBER_LIMITS", "DATASET_FIELD_PARAM_KEYS", "DATASET_VIEW_FILENAME", "DATASET_VIEW_TIMEOUT_MS", "MAX_DATASET_VIEW_CODE_LENGTH", "DATASET_FETCH_TIMEOUT_MS"]) {
    vm.runInContext(constant(name), ctx);
  }
  for (const name of [
    "clamp", "roundedCacheNumber", "captureRenderContext", "renderContextIsCurrent",
    "withCapturedRenderContext", "renderSignature", "beginRenderRequest", "renderRequestIsCurrent",
    "invalidateRenderRequests", "loadForRender", "pinHeavyCacheEntry", "isEffectivelyOpaque", "applyOpacityAndDepth",
    "normaliseDatasetLabel", "secondaryPrefix", "isSecondaryFieldName", "rawSecondaryFieldName", "prefixedSecondaryFieldName",
    "resolveFieldSource", "getPrimaryVolumeFieldNames", "getSecondaryVolumeFieldNames", "getVolumeFieldNames",
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
    "getFieldLineFilename", "loadLinesForMode", "inferLineType",
    "buildFieldLineObjectCacheEntry", "ensureFieldLineObjectCacheEntry", "loadFieldLines", "updateFieldLineVisuals",
    "applyViewStateParams", "refreshViewPresentation", "applyViewState", "loadDatasetViewState",
    "viewStateBlob", "writeDatasetViewFile", "saveViewStateCode", "downloadViewStateCode",
    "parseFolderSourcePath", "fileFromDirectoryHandle", "parseLocalFilesystemPath", "encodeLocalFilesystemPath",
    "captureDatasetState", "restoreDatasetState", "loadDatasetFromParams",
  ]) vm.runInContext(definition(name), ctx);
  return ctx;
}

function presetCode(ctx, values = {}) {
  return ctx.encodeViewState({ version: 2, scope: "view-only", params: values });
}

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
  assert.equal(await ctx.loadFrameByIndex(0), true);
  assert.equal(coordinateReads, 1);
  assert.equal(ctx.coords, newCoords);
  assert.equal(reuseGeometry, false);
  assert.equal(ctx.sequenceFrameLoading, false);
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

test("missing, malformed and unsupported optional view files do not block dataset loading", async () => {
  for (const contents of [null, "not a code", "DTV2:bad", "<!doctype html><html></html>",
    "DTV2:" + btoa(JSON.stringify({ version: 2, scope: "view-only", params: [] })),
    "DTV2:" + btoa(JSON.stringify({ version: 1, params: { cameraDistance: 9 } }))]) {
    const ctx = viewer();
    datasetLoader(ctx, contents);
    const distance = ctx.params.cameraDistance;
    assert.equal(await ctx.loadDatasetFromParams(), true);
    assert.equal(ctx.params.cameraDistance, distance);
  }
});

test("an unrenderable optional view falls back to the normal view of the new dataset", async () => {
  const ctx = viewer();
  datasetLoader(ctx, presetCode(ctx, { cameraDistance: 6, isoPositiveValue: 0.8 }));
  const originalDistance = ctx.params.cameraDistance;
  const seen = [];
  ctx.rebuildAllMeshes = async () => {
    seen.push(ctx.params.cameraDistance);
    if (ctx.params.cameraDistance === 6) throw new Error("saved surface cannot be built");
  };
  let message;
  ctx.setStatusSummary = text => { message = text; };
  assert.equal(await ctx.loadDatasetFromParams(), true);
  assert.deepEqual(seen, [6, originalDistance]);
  assert.equal(ctx.datasetRootPath, "new-dataset");
  assert.equal(ctx.params.isoPositiveValue, 0.1);
  assert.match(message, /default view used/);
});

test("a failed dataset switch restores the previous appearance and folder save target", async () => {
  const ctx = viewer(), old = writableFolder();
  ctx.activeDatasetFolderSource = old.source;
  ctx.console = { ...console, error: () => {} };
  datasetLoader(ctx, presetCode(ctx, { cameraDistance: 6, backgroundColor: "#abcdef" }));
  ctx.params.sequencePlaying = true;
  const oldMetadata = ctx.metadata, oldColour = ctx.params.backgroundColor;
  ctx.rebuildAllMeshes = async () => {
    if (ctx.datasetRootPath === "new-dataset") throw new Error("new bundle unavailable");
  };
  assert.equal(await ctx.loadDatasetFromParams(), false);
  assert.equal(ctx.datasetRootPath, "demo");
  assert.equal(ctx.metadata, oldMetadata);
  assert.equal(ctx.params.backgroundColor, oldColour);
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
