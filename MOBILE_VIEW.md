# Phone and desktop layouts

DEEPscope uses the same viewer and dataset format on phones and computers.
The layout selector offers **Auto**, **Phone**, and **Desktop**. Auto chooses
Phone for a viewport at most 700 CSS pixels wide, or a touch-oriented viewport
with a shortest side at most 600 CSS pixels. This keeps landscape phones in
Phone mode without treating every touchscreen laptop as a phone. Detection is
based on the available screen and pointer, not an assertion about device model.
The override is remembered in this browser and is independent of DTV2 codes.

On a phone, the bottom menu opens one scrollable panel at a time:

- **Dataset:** sources, comparisons and sequence playback.
- **Fields:** surfaces, slices, magnetic lines and isosurfaces.
- **View:** saved view codes, lighting, appearance and camera controls.
- **Legend:** colour bars and active isosurface legends.
- **Export:** export settings and quick PNG, PDF and video actions.

Tap **Done**, the active menu button, or Escape to close the panel. One finger
rotates the scene; pinch to zoom and use two fingers to pan. **View > Reset / fit
view** resets the camera with extra distance for a portrait viewport. Loading a
saved view retains its camera settings; pinch to adjust framing if needed.
The title initially appears compact; its plus button opens the status, and the
warning button remains accessible. Phone panels use fixed, touch-friendly
placement; saved desktop panel positions and collapse settings are preserved.

Controls account for screen safe areas, portrait/landscape rotation and the
on-screen keyboard. The opening dataset screen can scroll on short screens.
Large tables of fields remain available through collapsible sections.

This change adapts the interface, not the simulation arrays or geometry budget.
Large datasets and dense tubes can still exceed a phone's memory. Existing
stride, tube simplification, memory limits and sequence cache settings remain
available. Local folder selection and export formats retain browser-dependent
support; remote record URLs provide an alternative to local folder selection.

## Validation

- `npm run test-viewer`: 127 tests pass, including phone/landscape detection and
  both manual overrides.
- `npm run build`: succeeds; the existing large-bundle advisory remains.
- Chromium with a touch viewport and the bundled dataset: inspected the phone
  view and Fields panel, exercised all five tabs, landscape orientation and
  return to desktop. Reloading the dataset and reopening panels left one controls
  instance and no JavaScript exceptions. This is browser emulation, not physical iPhone/Android
  hardware validation.
