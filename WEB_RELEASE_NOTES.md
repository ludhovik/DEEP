# v0.4.0 — static hosted/local-data viewer

## Canonical scalar field names (2026-09-11)

- Use `T` for temperature/codensity and `C` for composition in all converted
  datasets. Unsuffixed diagnostics are full fields; `_nom0` removes the
  axisymmetric component.
- Translate legacy saved-view selections by scientific meaning when they are
  applied to a new naming-version-2 dataset.
- Incremental reconversion replaces legacy managed `.f32` names with exact
  metadata-matching filenames while retaining the dataset's `view.DTV2`.

## Linked meridian halves and reversible two-plane clipping (2026-09-11)

- Link both halves of each meridional slice by default, sharing the field,
  complete colour scale, colour map, opacity and one colourbar. An **Independent
  sides** toggle reveals the existing separate left-side controls when needed.
- Make **CMB side: Rear / Front** select complementary sectors in **Between
  meridional planes** mode. The same correction applies to optional isosurface
  clipping.
- Preserve older one-field views as linked and infer independent mode for view
  codes that already store different settings on the two halves.

## Split meridional fields and cylindrical scalar gradients (2026-09-11)

- Give the right (`+s`, longitude `phi`) and left (`-s`, longitude `phi+180°`)
  halves of both meridional planes independent fields, scaling, colour maps,
  manual limits, opacity and colourbars. Their longitude and visibility remain
  shared. New DTV2 codes retain every setting; older codes mirror their former
  whole-plane settings to both halves.
- All six converters now export cylindrical-radial and axial gradients of
  thermal/codensity `T` and composition `C`: `grad_s*` and `grad_z*`. The
  unsuffixed names are full fields and `_nom0` removes `m=0`. Explicit
  `--output` selection supports the same names.
- Existing datasets remain loadable. Reconversion is required only to add the
  new gradient volumes. No Cloudflare Worker change is needed.

## Calypso dataset conversion (2026-09-09)

- Add Calypso to the converter list and document its native restart workflow.
  Converted bundles use the existing fields, inner-core regions, B² tubes,
  pairing, local/remote loading and saved views without a new viewer format.
- No Cloudflare Worker update is needed.

## Inner-core volumes and isosurface legends (2026-09-08)

- Select Whole core, Fluid outer core or Inner core only for magnetic slices,
  radial spheres and isosurfaces; save the choice in DTV2. Respect native
  fluid-field support so solid-core padding cannot create false isosurfaces.
- Add isosurface colour swatches and numeric thresholds to the existing
  movable/collapsible legend, including PNG/PDF exports. Labels follow the
  displayed meshes through failed replacements, recolouring and visibility.
- Deploy through the existing Pages workflow. No Cloudflare update is needed.

## Loading progress and background geometry (2026-09-07)

- Show file names, bytes received and calculation progress in a separate box
  with **Cancel**, accessible even with the title collapsed. Restore the preceding
  dataset/view on a cancelled primary switch, clearing the aborted read context
  before rollback. Keep previous geometry on cancelled replacements.
- Run tube simplification, tube construction and isosurface generation in a
  browser Web Worker. Queue heavy jobs, transfer result buffers, interrupt active
  calculations on cancellation and restart cleanly on retry. Colour preparation
  yields periodically so controls remain available.
- Add optional **Auto fit budget**, bounded by **Auto max shape / ro** and
  **Auto max B² error %**. Preserve endpoints and pairing; report actual tolerances
  in the title. Store these controls in DTV2 while retaining manual mode for
  reproducible figures. Reject an impossible fit instead of dropping lines.
- Deploy the viewer through the existing Pages workflow. No reconversion or
  Cloudflare Worker update is needed. Hosting guidance distinguishes browser
  computation from the existing record-only proxy and lists current free limits.

## Adjustable tube geometry memory (2026-09-07)

- Add **Magnetic field lines → Tube memory → Custom limit**, with a configurable
  **Limit (MiB)** from 32 to 2048. Turning the switch off uses the existing
  192 MiB default and retains the custom value for reuse.
- Check the combined shell/exterior estimate after stride and simplification,
  including cached geometry and pending loads. Changing only the limit reuses
  matching geometry. Rejected replacements keep the previous display intact.
- Show the current limit in title summaries and error messages. Keep this
  session preference independent of dataset presets and copied view codes.
  It limits estimated tube geometry, not the browser's total memory use.

## Reset views when opening datasets (2026-09-07)

- Start each primary dataset opening/reload from the default appearance, then
  apply its optional `view.DTV2`. Missing or deleted files no longer leave the
  preceding view in memory. Partial dataset presets start from the same defaults.
- Report **default view applied** when no usable preset is applied. Select fields
  from the newly loaded metadata and retain the old view if replacement fails.
- Preserve the current view during sequence frame changes and secondary loads.
  The root view still takes precedence over the initial frame's optional view.
  This update requires a viewer deployment; the existing Worker remains valid.

## Refresh published dataset views (2026-09-07)

- Refresh the Figshare/Zenodo file index as well as the contents when reading
  `view.DTV2`, so reopening a dataset discovers newly added or replaced views.
  Forward the optional view's timeout and cancellation to the record lookup.
- Prevent a failed older request from evicting a newer repository index.
- Remove the Figshare proxy's one-hour cache and add an explicit Wrangler
  configuration. Deploy the Worker separately from GitHub Pages; see
  [deployment instructions](GITHUB_PAGES.md#figshare-proxy).

## Tube simplification and title warnings (2026-09-07)

- Add **Tube simplification → Simplify tubes**, enabled by default with an
  explicit off switch. Bound centreline and B² interpolation errors while
  retaining exact endpoints, magnetic extrema, pairing identifiers and gaps.
  Save the toggle and error limits in DTV2; leave stored line data unchanged.
- Apply the geometry budget after simplification. Show point counts and the
  estimated mesh size in the title, with actionable oversized-mesh errors.
- Keep dataset summaries and viewer feedback in the title instead of copying
  them into Quick export. Show a persistent **⚠** button in collapsed titles;
  clicking it opens the message. Warnings can be dismissed, and successful
  control retries clear their own preceding errors without hiding newer ones.

## B² magnetic tubes and incremental converters (2026-09-07)

- Choose **Magnetic field lines → Render as → B² tubes** for three-dimensional
  tubes whose local diameter is proportional to magnetic strength squared.
  Set a reference strength, diameter, minimum/maximum diameter and tube sides.
  Diameters use outer-radius units; colour scaling is independent.
- Save all tube settings in DTV2 codes. Preserve connected line groups when
  applying stride, and use a common automatic strength reference before
  thinning. Keep the previous lines if a replacement exceeds the mesh budget.
- Use existing converter strength samples without reconversion. Legacy shell
  lines can sample an available `Babs` volume, with the approximation reported
  in the status. Missing exterior strengths retain constant-width lines.
- Add `--incremental`, `--cache-dir` and `--force` to the three converters;
  see the README for cache reuse and initial population. DMFI time tracking
  remains deferred.

## Dataset switching fixes (2026-09-07)

- Successive primary or secondary folder selections load the newly selected
  files even when their names and sequence frame paths match an earlier folder.
- Secondary replacement redraws visible comparison fields. Failed loads
  preserve the previous dataset and its folder access.
- Cancelling folder selection permits another selection. Overlapping selections
  cannot replace a folder being loaded.
- Switching from a shell to a full sphere removes the old inner-boundary mesh;
  sequence frames fall back when the selected isosurface field is unavailable.

## New

- Static-site startup screen instead of the old path prompt.
- Local converted datasets can be opened directly from the browser.
- Local sequence roots (`sequence.json` + `frames/`) use the same loader.
- Local files remain on the user's computer and are not uploaded.
- Bundled demo data can be loaded from the landing screen.
- Converted datasets can be loaded from a remote URL when CORS is enabled.
- `?dataset=...` can deep-link to a remote/hosted converted dataset.
- GitHub Pages deployment workflow included.
- Vite uses a relative build base so project Pages URLs (`/repository/`) work.
- Earth/public asset paths are deployment-subpath aware.
- Dataset controls include **Choose data source…** so the startup selector can be reopened.

## Preserved

- Leeds and XSHELLS converters v3.0.0.
- Full sphere, shell, and conducting-inner-core support.
- EMF and induction outputs.
- CMB/Earth surfaces and magnetic field lines.
- Sequence playback/preloading/export.
- Secondary dataset comparison.
- Local Vite development and absolute filesystem path helper.

## Browser behavior

The local-folder route uses `showDirectoryPicker()` when available and otherwise falls back to a directory file input. The public deployment requires HTTPS for the strongest File System Access support; GitHub Pages provides HTTPS.
