# Leeds / XSHELLS converter parity notes

This release makes the Leeds and XSHELLS converters agree at the viewer-output level for shared diagnostics.

## Shared base volume fields

Both converters can now write these field names when the corresponding input data are present:

- velocity: `ur`, `ut`, `up`, `us`, `uz`, `Uabs`, `helicity`
- velocity m=0 helpers: `ur_phiavg`, `ut_phiavg`, `up_phiavg`
- magnetic: `Br`, `Bt`, `Bp`, `Babs`
- magnetic m=0 helpers: `Br_phiavg`, `Bt_phiavg`, `Bp_phiavg`
- optional EMF with `--emf`: `EMFr`, `EMFt`, `EMFp`, `EMFabs`, `EMFr_fluct`, `EMFt_fluct`, `EMFp_fluct`, `EMFabs_fluct`
- optional induction with `--induction`: `Ir`, `It`, `Ip`, `Iz`, `Iabs`
- buoyancy: `N2`, `N2_full` when scalar fields and parameters are sufficient
- scalar-gradient fields unless `--no-gradients` is used
- CMB and Earth-surface Br products when magnetic field and truncation options are enabled

The scalar names differ where the simulation codes differ:

- Leeds codensity is written as `C`.
- XSHELLS temperature is written as `T`.
- Composition is written as `Comp` in both converters.

## Optional diagnostics

`--emf` and `--induction` are disabled by default in both converters.

`--induction` computes `u x B` internally because `curl(u x B)` needs it, but EMF files are written only if `--emf` is also requested.

## Leeds r=0 geometry classification

The Leeds converter no longer classifies a state as full sphere from `r[0] = 0` alone.

When the radial grid includes zero, the converter now checks whether velocity coefficients are zero over a leading radial block while magnetic coefficients are finite there. In that case it classifies the state as

```text
spherical_shell_conducting_inner_core
```

rather than

```text
full_sphere_no_inner_core
```

The velocity and scalar fields are transformed only on the fluid shell and embedded as zero in the conducting inner core. The magnetic field can still be transformed on the full r=0 grid and kept inside the conducting inner core.

Relevant options:

```bash
--full-sphere                 # force no-inner-core/full-fluid-sphere mode
--conducting-inner-core       # force shell + conducting inner core mode
--fluid-inner-radius RICB     # manually set the fluid ICB radius if auto-detection is ambiguous
--inner-core-velocity-tol X   # leading-zero-flow detection tolerance
```

