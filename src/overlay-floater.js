const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export const OVERLAY_POSITION_OPTIONS = {
  "Top left": "top-left", "Top middle": "top-center", "Top right": "top-right",
  "Middle left": "middle-left", "Middle centre": "middle-center", "Middle right": "middle-right",
  "Bottom left": "bottom-left", "Bottom middle": "bottom-center", "Bottom right": "bottom-right",
  "Dragged position": "custom",
};
export const OVERLAY_POSITIONS = Object.values(OVERLAY_POSITION_OPTIONS);

// Custom x/y describe the fraction of free space before the box (top-left
// origin). This preserves placement through viewport and export-size changes.
export function overlayLayout(width, height, boxWidth, boxHeight, position, customX = .5, customY = .5) {
  const fit = Math.min(1, width * .96 / boxWidth, height * .96 / boxHeight);
  const w = boxWidth * fit, h = boxHeight * fit;
  const margin = Math.min(width, height) * .02;
  let left, top;
  if (position === "custom") {
    left = clamp(customX, 0, 1) * (width - w);
    top = clamp(customY, 0, 1) * (height - h);
  } else {
    left = position.endsWith("right") ? width - margin - w
      : position.endsWith("center") ? (width - w) / 2 : margin;
    top = position.startsWith("top") ? margin
      : position.startsWith("middle") ? (height - h) / 2 : height - margin - h;
  }
  return { width: w, height: h, x: left + w / 2, y: height - top - h / 2 };
}

export function floaterGesture(start, dx, dy, resize) {
  const { left, top, width, height, viewportWidth, viewportHeight, size, minimum, maximum } = start;
  let w = width, h = height, nextSize = size;
  if (resize) {
    // Uniform resizing keeps a Mollweide ellipse 2:1 and text undistorted.
    const scale = (width * (width + dx) + height * (height + dy)) / (width * width + height * height);
    const limit = Math.min(maximum, size * (viewportWidth - left) / width, size * (viewportHeight - top) / height);
    nextSize = clamp(size * scale, Math.min(minimum, limit), limit);
    w *= nextSize / size; h *= nextSize / size;
  }
  const x = clamp(left + (resize ? 0 : dx), 0, viewportWidth - w);
  const y = clamp(top + (resize ? 0 : dy), 0, viewportHeight - h);
  return { position: "custom", x: x / Math.max(1e-9, viewportWidth - w),
    y: y / Math.max(1e-9, viewportHeight - h), size: nextSize };
}

export function createOverlayFloater({ label, getSize, minimum, maximum, onChange,
  zIndex = 10, document: doc = document }) {
  const box = doc.createElement("div");
  box.className = "overlay-floater"; box.hidden = true; box.tabIndex = 0;
  box.style.zIndex = String(zIndex);
  box.setAttribute("role", "group"); box.setAttribute("aria-label", `${label}: drag to move; arrow keys move; Shift+arrows resize`);
  box.title = `${label}: drag to move; drag the bottom-right corner to resize`;
  const handle = doc.createElement("div"); handle.className = "overlay-floater-resize";
  handle.setAttribute("aria-hidden", "true"); box.appendChild(handle); doc.body.appendChild(box);
  let bounds = null, gesture = null;
  const stop = event => { event.preventDefault(); event.stopPropagation(); };
  const finish = event => {
    if (gesture && (event.pointerId === undefined || event.pointerId === gesture.id)) {
      const id = gesture.id; gesture = null;
      box.classList.remove("is-dragging");
      if (box.hasPointerCapture?.(id)) box.releasePointerCapture(id);
    }
  };
  box.addEventListener("pointerdown", event => {
    if (box.hidden || !bounds || gesture || event.button !== 0) return;
    stop(event);
    gesture = { ...bounds, size: getSize(), minimum, maximum, id: event.pointerId,
      clientX: event.clientX, clientY: event.clientY, resize: event.target === handle };
    box.setPointerCapture?.(event.pointerId); box.classList.add("is-dragging");
    box.focus({ preventScroll: true });
  });
  box.addEventListener("pointermove", event => {
    if (!gesture || event.pointerId !== gesture.id) return;
    stop(event);
    onChange(floaterGesture(gesture, event.clientX - gesture.clientX, event.clientY - gesture.clientY, gesture.resize));
  });
  for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) box.addEventListener(type, finish);
  for (const type of ["dblclick", "wheel"]) box.addEventListener(type, stop, { passive: false });
  box.addEventListener("keydown", event => {
    const delta = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, -10], ArrowDown: [0, 10] }[event.key];
    if (!delta || !bounds || box.hidden) return;
    stop(event);
    onChange(floaterGesture({ ...bounds, size: getSize(), minimum, maximum }, ...delta, event.shiftKey));
  });
  return {
    sync(layout, canvas, locked = false) {
      box.hidden = !layout || locked;
      if (box.hidden) { finish({}); return; }
      const rect = canvas.getBoundingClientRect();
      const sx = rect.width / canvas.width, sy = rect.height / canvas.height;
      bounds = { left: (layout.x - layout.width / 2) * sx,
        top: (canvas.height - layout.y - layout.height / 2) * sy,
        width: layout.width * sx, height: layout.height * sy,
        viewportWidth: rect.width, viewportHeight: rect.height };
      Object.assign(box.style, { left: `${rect.left + bounds.left}px`, top: `${rect.top + bounds.top}px`,
        width: `${bounds.width}px`, height: `${bounds.height}px` });
    },
    dispose() { finish({}); box.remove(); },
  };
}
