# GitHub Pages deployment

This release is designed to be used as a static website. End users do **not** need Node.js or a clone of this repository.

## One-time repository setup

1. Push this project to GitHub with the viewer project at the repository root.
2. In **Settings → Pages → Build and deployment**, choose **GitHub Actions** as the source.
3. Push to `main` (or run the `Deploy DEEPscope to GitHub Pages` workflow manually).
4. Open the URL reported by the deployment job.

The workflow in `.github/workflows/deploy-pages.yml` runs `npm ci`, builds the Vite application, uploads `dist/`, and deploys it to GitHub Pages.

`vite.config.js` uses `base: "./"`, so the same build works for both:

- `https://USER.github.io/REPOSITORY/`
- a custom-domain Pages site.

## What a user does

A visitor opens the website and chooses one of three sources:

### Open local dataset folder

Choose the directory produced by one of the converters. The browser reads the selected files directly. The dataset is not uploaded to GitHub Pages or another server.

A single-frame root contains for example:

```text
viewer_data/
├── metadata.json
├── coordinates.json
├── profiles.json
├── Br_volume.f32
├── Bt_volume.f32
├── Bp_volume.f32
└── ...
```

A time sequence can be selected at its root:

```text
viewer_data/
├── sequence.json
└── frames/
    ├── state03484/
    │   ├── metadata.json
    │   └── ...
    ├── state03826/
    │   └── ...
    └── state04086/
        └── ...
```

The local-folder route uses the browser directory API when available and falls back to directory file selection (`webkitdirectory`).

### Open bundled demonstration

The `public/data/` dataset is built into the deployed website and can be used immediately.

### Load dataset from URL

Enter the URL of a converted dataset root. The remote host must allow browser cross-origin (CORS) reads for `metadata.json`, `.f32`, and other dataset files.

The viewer can also be opened directly with:

```text
https://USER.github.io/REPOSITORY/?dataset=https://DATA-HOST/path/to/viewer_data
```

The same CORS requirement applies.

## Privacy model

For **Open local dataset folder**, the website receives no simulation files. The browser grants the page read access only to the directory explicitly selected by the user. Data are decoded locally into browser memory for visualization.

## Development remains unchanged

Developers can still use:

```bash
npm ci
npm run dev
```

and the converter commands in `tools/`. The old absolute-filesystem-path helper in `vite.config.js` remains available during local Vite development, but it is not required by the public website.
