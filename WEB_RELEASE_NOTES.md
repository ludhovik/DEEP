# v0.4.0 — static hosted/local-data viewer

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
