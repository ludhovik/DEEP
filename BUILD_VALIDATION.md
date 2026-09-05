# Integrated package validation

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
node --test tests/test_viewer_regressions.mjs
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
