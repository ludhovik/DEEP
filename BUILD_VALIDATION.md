# Integrated package validation

## Switching datasets through Controls (2026-09-07)

- Reproduced stale metadata, coordinates, sequence indexes and scalar volumes
  when successive local folder selections shared the same resource path.
- All 65 viewer tests pass. Eleven added regressions cover primary folder
  replacement with both browser file APIs, different grids, identical sequence
  paths, secondary comparison redraw, truncated files, render-error rollback,
  mismatched comparison grids, concurrent selection, picker cancellation,
  shell-to-full-sphere geometry, and unavailable isosurface fields in frames.
- The tests exercise the actual loaders and caches with in-memory files;
  rendering and browser dialogs use test doubles. No browser/GPU test was run.
- `node --check src/main.js`, `git diff --check` and `npm run build` pass.
  The existing large JavaScript chunk advisory remains.
- After deploying, refresh the page once to load the new viewer. Then select
  two different folders successively through Controls without refreshing.

## Remove duplicate scalar fields (2026-09-07)

- All 52 converter tests pass; the synthetic MagIC bundle now verifies that
  only `Cnom0`/`Compnom0` are exported, without underscored metadata or files.
- All 54 viewer tests pass, including old primary/secondary metadata,
  aliases-only bundles, canonical range preservation, idempotent metadata
  normalization, and old saved-view field selections.
- Python/JavaScript syntax checks and the production build pass. The existing
  large-chunk advisory remains. No browser/GPU visual test was performed.
- Deploy the updated viewer to remove duplicate choices from existing datasets.
  Reconvert to omit redundant files from future exports; existing stored files
  are not deleted by the viewer.

## Spectral cutoffs and both-end connections (2026-09-06)

- Converter suites: 52 passing tests across package, exterior tracing and new
  scalar/vector spectral projection coverage. Python syntax checks pass.
- `npm run test-viewer`: 52 passing tests. The added regression retains or
  omits original internal lines, exterior arcs and return branches as complete
  groups at strides 1 through 10. Existing paired geometry tests still pass.
- `npm run build` passes; the existing large JavaScript chunk advisory remains.
- No browser/GPU rendering test or native production-snapshot conversion was
  performed. Converter validation and the real pyxshells class check are
  detailed in `CONVERTER_VALIDATION.md`.
- Reconversion is required to create smaller volumes or new return branches.
  After updating the viewer, use **Line type → Both** and change **Line stride**
  to verify all three segments remain selected together.

## Paired field-line stride (2026-09-06)

- `npm run test-viewer`: 51 passing tests. Five new regressions verify paired
  selection at strides 1 through 10 with missing/reordered exterior arcs,
  explicit pairing identifiers, repeated segments, legacy files, single-mode
  selection, and cache reuse after changing stride.
- The geometry regression builds real Three.js `Line2`/`LineGeometry` objects
  and checks that every selected exterior segment has its selected shell
  partner with identical CMB endpoint coordinates in the geometry buffers.
- `npm run build` passes with the installed lockfile dependencies; the existing
  large JavaScript chunk advisory remains. No browser/GPU rendering test was
  performed for this selection change. Check **Line type → Both** and move
  **Line stride** from 1 to 10 after deployment.
- Existing bundles containing `line_id`/`paired_shell_line_id` need no
  reconversion for this viewer change. Converter code is unchanged.

## Exterior tracing (2026-09-06)

- Converter suite: 41 passing tests (33 package tests, eight exterior tests).
  New coverage includes CMB rounding, short-loop refinement, long dipole arcs,
  radial convergence of a mixed dipole/quadrupole field, termination/seed
  accounting, and a synthetic MagIC export with paired exterior lines.
- The correction applies to Leeds, XSHELLS and MagIC. Python syntax checks
  pass. The viewer, workflow, volume reconstruction and polarity convention
  are unchanged; no new viewer build was needed for this Python correction.
- The production Leeds snapshot from the reported run was not available.
  Analytic checks and native-backend limitations are detailed in
  `CONVERTER_VALIDATION.md`; test a single native frame before a long sequence.

## Planet and moon images (2026-09-06)

- `npm run test-viewer`: 46 passing tests. Seven new regressions exercise body
  selection and saved-code compatibility, out-of-order image loads and credits,
  failure/retry, hiding during a pending load, geometry reuse, bounded source
  caching and disposal of replaced texture clones. Image/network/DOM objects
  use test doubles; the texture objects and existing sphere tests use Three.js.
- `npm run build` passes on Node 24 with the installed lockfile dependencies.
  The existing large JavaScript chunk advisory remains.
- All seven source maps were visually inspected. Pillow decoded each complete
  image and verified a 2:1 aspect ratio, with no map borders or labels. The six
  new JPEGs total about 5.4 MiB; only the selected image is requested at runtime.
  The deployed assets match the source files byte for byte. Source URLs, credits,
  licences and map limitations are in `public/assets/surfaces/CREDITS.txt`.
- Browser/GPU visual validation remains unperformed in this environment. After
  applying, open the demo and switch all seven choices under Planet / moon
  surface; check longitude, poles, opacity, clipping, and a copied view code.

## Earth image and dataset launcher (2026-09-06)

- `npm ci --no-audit --no-fund` and `npm run build` pass using the lockfile.
- `npm run test-viewer`: 39 passing tests, including six Earth tests using real
  Three.js geometry, materials and ray intersections without a WebGL renderer.
  These verify closed sphere topology, outward faces, non-degenerate polar caps,
  continuous texture coordinates, geographic orientation and intentional clipping.
- The NASA PNG was visually inspected and matches the downloaded source bytes:
  2048 x 1024, with a complete latitude-longitude extent and no graticule/border.
- The launcher now describes a 3D full sphere or spherical shell and links to the
  three converters in a small-font note.
- No browser/GPU rendering test was completed: the browser executable download
  timed out. Check the north/south poles, longitude seam and clipped Earth image
  in the browser after applying the patch. The build retains its existing
  advisory about a JavaScript chunk exceeding 500 kB.

## Dataset default view (2026-09-06)

The `view.DTV2` feature adds optional automatic view loading and saving to a
selected dataset folder. Viewer regressions cover applying the code before
the first render, missing/invalid files, render fallback and rollback, sequence
root precedence, source routing, folder permissions, save/load round trips,
cancelled/failed writes, and preserving the destination across pending prompts.
The converter suite also verifies preservation of `view.DTV2` on reconversion.

Validation: 33 viewer logic tests and 32 converter tests pass, along with
JavaScript/Python syntax checks and patch application to the verified base.
Rendering and browser file handles use test doubles. No new Vite production
build or browser/GPU/permission-dialog test was performed here; run the commands
below and check saving/reopening a local folder in your browser before pushing.

## Converter/viewer review fixes (2026-09-05)

- Converter regression suite: 31/31 passing (synthetic/import-only native backends).
- Viewer regression suite: 18/18 passing using Node's built-in test runner.
- Viewer coverage includes out-of-order isosurface/slice/field-line requests,
  preserving a working mesh after failure, geometry-cache lifetime and appearance,
  captured preload context, real coordinate comparison, required coordinate
  files, frame-coordinate loading, typed view-code round trips, and the actual
  bundled demo's coordinates and binary sizes.
- Python and JavaScript syntax checks pass.
- No new Vite production build or browser/GPU validation was performed for
  these changes. The checkout has no installed Node dependencies; the viewer
  logic tests deliberately run without those dependencies.

Run locally before pushing:

```bash
python3 tests/test_converter_package.py
npm run test-viewer
npm run build
```

Then check the demo and a real converted bundle, rapid field/frame changes,
cached isosurface opacity/colour changes, and PNG/video export in a browser.

The broader hardening pass (Web Workers, CI changes, proxy controls and local
filesystem endpoint restrictions) is deliberately not included.

## Historical 0.3.0 packaging checks

Completed for release `DEEPscope` 0.3.0:

- Python syntax compilation passed for both converters, `modules.py`, and converter tests.
- Converter regression suite passed: 9/9 tests.
- JavaScript syntax checks passed for `src/main.js` and `vite.config.js`.
- `package.json` and `package-lock.json` versions and root metadata are consistent.
- Every field referenced by the bundled sample `metadata.json` exists and has the expected binary size.
- Bundled `B_lines.json` parses as valid JSON.
- Final ZIP integrity is checked after packaging.

A clean `npm ci && npm run build` was attempted twice. The source build could not be completed in the packaging environment because the configured npm mirror returned HTTP 503 while fetching Vite and Three.js packages. This is an external registry availability limitation; dependency-independent JavaScript syntax validation passed. Run the following after unpacking when npm access is available:

```bash
npm ci
npm run build
```
