# Integrated package validation

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
