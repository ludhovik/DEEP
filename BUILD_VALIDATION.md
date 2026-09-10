# Integrated package validation

## MagIC archived V9 shells (2026-09-10)

- Seven new regression tests pass, covering 16 endian/precision/symmetry/block
  combinations, all seven native fields, coordinate and hemisphere ordering,
  missing-IC provenance, native archive names, normal-reader routing, damaged
  records, an exported bundle and incremental read reuse. The source bytes stay
  unchanged. The 37 converter-package tests, 11 incremental tests and 12 IC
  tests also complete successfully (one IC test requires unavailable real data
  and is skipped).
- Eight big-endian fixtures (both precisions, minc=1/2, one/two latitude blocks)
  agree exactly with an unmodified upstream MagicGraph reader for all seven
  fields and both coordinates. The comparison uses identical shell records
  with a no-IC header for upstream, and a declared-but-absent IC for DEEPscope.
  Little-endian fixtures are checked against independently encoded values;
  upstream's legacy Python string-record reader fails those fixtures, so no
  upstream parity claim is made for them.
- The reported 999,173,240-byte Jupiter file matches the expected full V9 shell
  size for 121 x 384 x 768, float32, seven fields and one latitude block. The
  user's actual binary has not been supplied here; real-data conversion remains
  to be checked. Missing IC records do not establish an insulating boundary:
  sigma is retained, and metadata explicitly states that IC data are unavailable.

## Calypso full-sphere binary restart (2026-09-09)

- All 108 converter tests pass with both supplied Calypso archives enabled.
  Seven new cases cover binary layout, byte order, compressed blocks,
  half-Chebyshev/explicit centre grids, diagnostics, cache reuse, selection
  and the real full-sphere restart. The older shell checks remain enabled.
- Real input: `sph_shell_842/rst_48/rst.99.fsb.gz`, L=31, 48 MPI ranks (6×8),
  192 positive spectral radii plus a separate centre node, 108×216 angular
  samples. Header simulation step 990000 is kept separately from file index
  99; time is 2.474999999948594 and dt is 2.5e-6.
- The native grid is `r_k=sin(pi*k/(2*192))`, k=1..192. Positive radial node
  counts and the sole extra centre record agree with all 48 MPI blocks.
  An independent raw-byte address verifies the stored centre temperature.
  Cubic-spline derivatives of stored poloidal coefficients agree with the
  independently stored P-prime column to relative L2 errors 4.16e-4 (velocity)
  and 2.76e-4 (magnetic), excluding three samples at each radial boundary.
  This is a radial-consistency check, not a full physical-field error bound.
- The user's complete command (EMF, induction, CMB l<=13, both line domains,
  360 seeds, exterior-rmax=40, exterior-nr=192, 4000 steps per branch) exports
  a validated 193×108×216 bundle with 46 volume fields, 364 internal seed
  lines, 358 exterior arcs and 358 internal return branches (1080 segments).
  All retained exterior arcs return to the CMB and all return connections
  succeed. Two internal lines lack a traced CMB intersection; four exterior
  traces reach the r=40 limit and are excluded by the closed-arc selection.
- A real-data rerun reuses all 65 calculations. Its 48 f32 files and three
  line JSON files are byte-identical to the fresh conversion.
- Binary fixtures use independently encoded Fortran rank blocks with multiple
  components, including empty MPI ranks, little/big endian and plain/native
  gzip formats. Bad offsets, CRCs, truncated blocks, trailing bytes, duplicate
  format selection and nonfinite data are rejected. Analytic full-sphere
  exports recover T=1-r²+0.1x, constant Cartesian B and solid rotation at the
  centre and throughout the grid. Incremental addition of EMF/induction
  preserves existing field bytes and view files, and then skips unchanged work.
- The real full-sphere archive contains no independent physical snapshot;
  pointwise physical reconstruction is tested analytically, unlike the shell
  archive's independent physical-node comparison. Extended or adjusted native
  half-Chebyshev grids require explicit matching radii. Rank-local binary and
  non-native single-member gzip wrappers are unsupported. No viewer or Worker
  changes are needed.

## Field-line performance and progress (2026-09-09)

- All 101 converter tests pass with the supplied Calypso sample enabled.
  Ten new regressions cover interpolation equivalence, grid lifetime, tracing,
  progress, line serialization, interruption and cached return connections.
- The prepared sampler matches the unchanged scalar interpolator exactly at
  seams, poles and radial boundaries, with float32/float64 samples and shifted
  longitude grids. Internal/exterior coordinates, sampled strengths, terminal
  statuses and short-arc refinements match the reference path bit for bit.
- An unprofiled 400-step internal branch from the supplied restart-1 magnetic
  field takes median 0.533 s with reference interpolation and 0.075 s with the
  prepared sampler (7.1 times faster, two runs each with order reversed).
  This is a tracing benchmark, not a whole-conversion speedup guarantee.
- The user's full configuration (360 requested seeds, external-rmax=40,
  external-nr=192, line-max-steps=4000, EMF and induction) completes and passes
  bundle validation. With cached volumes/diagnostics and fresh tracing, it
  takes 170 s here: 364 seed lines, 336 closed exterior arcs, 336 connected
  internal return branches and 46 volume fields. Twenty-eight internal lines
  have no traced CMB intersection and do not seed exterior arcs.
- A subsequent run reuses all 65 calculations. All 48 f32 files and all three
  line JSON files match the fresh-tracing output byte for byte. The combined
  file now retains return-connection labels when cached exterior records are
  restored, matching the separate exterior file.
- Injected Ctrl+C during tracing preserves the existing published bundle and
  view. A retry reuses completed native transforms; unfinished seed tracing is
  restarted. No per-seed checkpointing is claimed.
- An earlier streamed-JSON trial failed final JSON validation and was withheld
  from publication; its isolated write failure was not diagnosed. The full
  run with one-pass encoding and its cached rerun both pass strict validation.
- The shared changes apply to Leeds, XSHELLS, MagIC and Calypso. The real
  performance run uses Calypso; other native backends retain their existing
  regression coverage. No viewer JavaScript or Worker deployment changes.

## Calypso converter (2026-09-09)

- 91 converter tests pass with the supplied Calypso data enabled (75 existing
  tests plus 16 Calypso tests). Without CALYPSO_SAMPLE_DIR, the two external
  sample tests are skipped. All 125 viewer/proxy tests and production build
  pass; the existing Vite chunk-size advisory remains.
- Real input: the supplied shell/dynamobench_case_1 archive, restarts 0 and 1,
  L=63, six MPI ranks, 73 radial nodes, 96 Gauss latitudes, 192 longitudes.
  Native ASCII byte/node stacks and the active signed-harmonic ordering are
  checked. Restart 0 reproduces the analytic dynamo benchmark magnetic field
  to within 4e-14 in all components. Restart 1 is independently compared with
  out.1.fld on every owned MPI node, including Cartesian vector conversion:
  maximum absolute discrepancies <5e-16 (temperature), <9e-9 (velocity),
  <8e-8 (magnetic components).
- A complete, untruncated restart-1 conversion writes 46 volume fields,
  gradients, N2, EMF, induction and surface maps. At external-rmax=40,
  external-nr=192 and line-max-steps=1000, all 12 test exterior seeds return
  to the CMB and all 12 receive internal return branches (36 total segments).
  The bundle passes binary-size/coordinate/metadata validation.
- Analytic native-format fixtures check non-axisymmetric cosine/sine phase,
  P/T/P-prime normalization, solid rotation, constant Cartesian magnetic
  fields, full-sphere centre continuity, conducting-core field domains,
  convection-only inputs, spectral cutoff, downsampling, optional fields,
  native buoyancy coefficients and explicit parameter overrides.
- Incremental tests verify whole-bundle skipping, reuse of native transforms
  when adding EMF/induction, core-only updates preserving field bytes, sequence
  extension preserving root/frame views, and rollback after corrupt input.
  Gzip input, truncated records, incompatible controls and cyclic references
  are checked.
- Full-sphere and conducting-core tests use generated native-format analytic
  fixtures. No real Calypso full-sphere dataset was supplied. Binary/rank-local
  restarts and custom MPI index layouts are explicitly unsupported. No new
  browser rendering algorithm or Cloudflare deployment is required.

## Inner-core data and isosurface legends (2026-09-08)

- 75 converter tests and 125 viewer/proxy tests pass; production build passes.
- Analytic dipole, quadrupole and toroidal tests check Leeds QST values and the
  solenoidal identity. Marked regular coefficients recover a finite, unique
  Cartesian vector at the centre. Classic NetCDF padding, HDF5 attributes and
  reversed radial ordering are tested with generated state files.
- The actual Leeds entry point is exercised with synthetic native transforms:
  an older outer-only output gains IC rows without reloading the outer state,
  and its binaries match a fresh complete conversion. Existing outer samples
  are byte-identical; field lines, profiles and views remain intact. Repeated
  updates, sequences, changed inputs and a failed ICB check are covered.
- XSHELLS/MagIC core-only metadata updates run without native calculations.
  Tests preserve native MagIC IC vector components, reject incomplete vectors
  and invalid radii, and avoid advertising padding as measured core data.
- Real Three.js slice and isosurface geometries obey native radial domains.
  A constant fluid field produces no artificial isosurface against solid-core
  zero padding; magnetic IC-only geometry stays inside the ICB. DTV2 round
  trips, cached geometry replacement, committed-mesh legend values, colour
  edits, hidden/empty meshes and PNG/PDF canvas legend composition are tested.
- No production Leeds state file or native SHTns runtime was supplied for an
  end-to-end simulation check. Tests use analytic angular-transform adapters;
  browser UI tests use DOM doubles, without GPU profiling. The existing
  large-chunk Vite advisory remains. Cloudflare deployment is unchanged.

## Loading progress, geometry workers and automatic tube detail (2026-09-07)

- All 118 viewer/proxy tests pass, including actual worker-thread execution of
  the browser worker entry point. Tests compare isosurface/tube buffers to the
  synchronous calculations, check an analytical spherical isosurface and clipping,
  preserve input buffers, and confirm the calling event loop continues running.
- Worker cancellation, queued work, stale replies, errors and retries are covered.
  Viewer integration passes messages through structured cloning, assembles real
  Three.js tubes, and preserves shell/exterior pairing and vertex colours.
- Automatic fitting is tested against its budget and original-sample shape/B²
  bounds, with retained lines and endpoints, manual off switches, impossible-fit
  rejection and view-code/cache handling. Stream tests cover byte counts, UTF-8,
  unknown lengths, cancellation and malformed/interrupted responses.
- Primary dataset cancellation is checked before and after commit, including
  rollback with a usable read context and subsequent retry. Progress UI uses DOM
  doubles; no browser/GPU profiling was available in this environment.
- Production build emits the separate worker asset; JavaScript syntax and
  whitespace checks pass. The existing large main-chunk advisory remains.

## Adjustable tube geometry memory (2026-09-07)

- All 99 viewer/proxy tests pass. New cases exercise the custom/default toggle,
  numeric bounds, invalid input, both-domain accounting, cached rejection and
  reuse, and preservation of the previous display. Pending builds use the latest
  limit before allocation; a limit changed while accepting a cached result is
  checked again before replacing visible lines.
- Tests verify that view codes and dataset defaults preserve this session
  preference, ordinary lines remain usable, and the title shows the selected
  limit. Large-budget cases use the real estimator with small rendering doubles
  to avoid allocating hundreds of megabytes in the test suite.
- Production build, JavaScript syntax and whitespace checks pass. Existing
  geometry tests use real Three.js, while UI/network checks use test doubles;
  no browser/GPU memory profiling was performed. The existing large-chunk build
  advisory remains. No converter or Worker deployment changes are required.

## Missing/deleted dataset view reset (2026-09-07)

- All 93 viewer/proxy tests pass. New scenarios open a Figshare/Zenodo preset,
  remove it from the record fixture, and reopen through the actual dataset
  loader. They check the rendered parameters and real Three.js camera position,
  target, up vector and FOV, along with colour scales, visibility and panel layout.
- Local-folder switching checks metadata-dependent field defaults. Additional
  scenarios cover sequence-root deletion with/without an initial-frame fallback,
  partial presets, invalid presets, rendering fallback, and preservation of the
  previous view when metadata, volume validation or rendering fails.
- Existing frame and secondary-folder tests now explicitly verify that their
  camera, background and legend settings survive those operations.
- Production build, JavaScript syntax and whitespace checks pass. Network and
  rendering operations use test doubles; no live record or browser/GPU validation
  was possible. The existing large JavaScript chunk advisory remains.

## Refresh published dataset views (2026-09-07)

- All 89 viewer/proxy tests pass. New fixtures publish changed download IDs or
  add a previously missing view in both Figshare and Zenodo; a repeat read
  discovers the new view without clearing ordinary volume caches. Tests also
  cover record timeouts, cancellation, retry and stale-request cache eviction.
- Worker tests verify uncached upstream requests and browser response headers,
  while preserving HTTP status, read-only routes and CORS behaviour. They use
  mocked HTTP responses, not a deployed Cloudflare runtime.
- The production build, JavaScript syntax and whitespace checks pass. The
  existing large JavaScript chunk advisory remains. Live retrieval of the
  reported Figshare record was unavailable; no browser/GPU check was run.
- Both the viewer and Worker need deployment. The new Wrangler configuration
  pins support for the standard no-store request option. Converter code is
  unchanged.

## Tube simplification and title feedback (2026-09-07)

- All 83 viewer tests pass. Simplification tests check every original sample
  against the requested spatial and local B² error bounds on curved paths
  with strongly varying fields. Additional cases preserve peaks, zeros,
  return bends, closed loops, missing-data separators, exact endpoints and
  large finite strengths. Disabling simplification returns the original data.
- A dense paired-line fixture exceeds the 192 MiB limit before simplification
  and fits afterwards; toggling off preserves the previous working mesh when
  the new request is too large. DTV2 preserves the toggle and both tolerances.
- Title-notice tests cover collapsed warnings, reveal/dismiss actions,
  preservation through unrelated progress, retries through different field-line
  controls, cancellation, and older tasks completing after newer failures.
  These UI checks use DOM test doubles; geometry checks use real Three.js.
- The production build, JavaScript syntax and whitespace checks pass. A live
  browser/GPU check could not run because the Chromium download timed out.
  Converter code and data are unchanged by this viewer-only update.

## Incremental conversion and B² tubes (2026-09-07)

- All 63 converter tests pass. Eleven incremental tests cover source/code
  invalidation, force, corruption repair, precision, mutation isolation,
  failed-output preservation, tracing metadata and sequence reuse. For each
  converter, adding diagnostics with cached transforms produces byte-for-byte
  identical `.f32` files to a fresh conversion. Native readers/transforms use
  analytical fixtures; no production HPC snapshot was available for this run.
- All 74 viewer tests pass. New tests check the B² diameter law, clipping,
  ring radii, normals, caps, invalid samples, paired stride, shared references,
  legacy volume sampling, DTV2 validation and retention of existing lines when
  a replacement exceeds the memory budget. Geometry tests use real Three.js
  objects and ray intersections; UI/network objects use test doubles.
- Python/JavaScript syntax checks, `git diff --check` and the production build
  pass. The existing large JavaScript chunk advisory remains. No browser/GPU
  visual test was performed.
- After applying, add `--incremental` to an existing converter command. Its
  first run populates the native cache; a repeat skips an unchanged bundle.
  In the viewer select **Render as → B² tubes** and use a positive reference
  strength when comparing figures on the same diameter scale.

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
