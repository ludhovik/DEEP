# Leeds full-sphere v2 release

This package combines the latest converter and viewer with the corrected Leeds
`modules.py` implementation.

## Transform conventions

### Spherical shell

The validated shell path is unchanged:

```python
Slm = -dPol_dr
```

The existing Chebyshev helper returns the opposite radial derivative
orientation, so this minus sign restores the physical positive
`(1/r) d(rP)/dr` coefficient. This is the convention that matched classic and
SHTns Leeds builds for both velocity and magnetic field.

### Full sphere

For regular coefficients in `x=r^2`,

```text
P_lm(r) = r^(l+pP) G_lm(x)
T_lm(r) = r^(l+pT) H_lm(x)
```

the direct SHTns coefficients are

```text
Q = l(l+1) r^(l+pP-1) G
S = +r^(l+pP-1) [(l+pP+1)G + 2x dG/dx]
T = +r^(l+pT) H
```

The full-sphere expression therefore uses a positive `S` sign.

## V2 architecture

- `modules.py` is bundled in the project root.
- The converter calls `modules.PolTor_to_spat_fullsphere` for full-sphere
  velocity and magnetic fields.
- The converter calls `modules.SH_to_spat_fullsphere` and
  `modules.SH_to_spat_nom0_fullsphere` for regular scalar fields.
- The converter no longer contains a duplicate full-sphere QST/projection
  implementation.
- Poloidal and toroidal storage representations are handled independently.
- Legacy conventional full-sphere coefficients use the bounded Leeds `K=7`
  projection in `modules.py`.
- Cartopy is optional for conversion; it is required only for map plotting.

## Validation performed

- Python compilation of the bundled module and converter tools.
- Full-sphere coefficient regression tests, including `D_x x = 1`, bounded
  regular projection, positive `S`, complex `m>0` normalization, and mixed
  regular/conventional vector storage.
- Complete smoke conversion of `state0026.cdf.dat` through the v2 module API,
  including field output and metadata generation.
- JavaScript syntax checks for `src/main.js` and `vite.config.js`.

The npm production build was not run in the packaging environment because npm
packages were not installed there. Run `npm install` followed by `npm run build`
on the target machine.
