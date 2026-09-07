# v0.4.0 — static hosted/local-data viewer

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
