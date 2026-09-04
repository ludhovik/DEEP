# Dynamo Three Viewer 0.3.0 — converter parity release

This release integrates the Leeds and XSHELLS converter package v3.0.0 into the complete Three.js viewer.

## Converter changes

- Common Leeds/XSHELLS viewer-field contract.
- Optional `--emf` and `--induction` output in both converters.
- Correct motional EMF component definitions.
- Shared vector `curl_spat(Ar, Atheta, Aphi, r, theta, phi)` implementation.
- Physical spherical scalar-gradient components in both converters.
- Leeds geometry now separates the full radial transform domain from the physical fluid domain.
- Automatic distinction between a true full fluid sphere and a spherical shell with a conducting inner core.
- Magnetic field retained within conducting inner cores while velocity and fluid diagnostics are masked there.
- XSHELLS confirms that the magnetic field is nonzero below the fluid ICB before labeling the inner core conducting.
- Existing CMB, Earth-surface, field-line, sequence, and export functionality is retained.

## Viewer compatibility

The viewer obtains available volume fields dynamically from `metadata.fields`. Therefore EMF and induction quantities appear in the field selectors automatically when the converters were run with the corresponding flags.

## Validation

Run:

```bash
./run_converter_tests.sh
npm run build
```

See `CONVERTER_VALIDATION.md` for the completed numerical checks and environment limitations.
