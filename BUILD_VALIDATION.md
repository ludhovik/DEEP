# Integrated package validation

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
