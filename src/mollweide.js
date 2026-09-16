import * as THREE from "three";

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const TAU = 2 * Math.PI;

// Normalized ellipse: x in [-2,2], y in [-1,1]. North is up;
// longitude increases to the right of the selected central meridian.
export function inverseMollweide(x, y, centre = 0) {
  if (x * x / 4 + y * y > 1 + 1e-12) return null;
  const alpha = Math.asin(clamp(y, -1, 1));
  const latitude = Math.asin(clamp((2 * alpha + Math.sin(2 * alpha)) / Math.PI, -1, 1));
  const longitude = Math.abs(y) >= 1 ? 0 : Math.PI * x / (2 * Math.cos(alpha));
  return { theta: Math.PI / 2 - latitude, phi: ((longitude + centre) % TAU + TAU) % TAU };
}

export function bracket(axis, value) {
  if (axis.length === 1 || value <= axis[0]) return [0, 0, 0];
  const last = axis.length - 1;
  if (value >= axis[last]) return [last, last, 0];
  let lo = 0, hi = last;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (axis[mid] <= value) lo = mid; else hi = mid;
  }
  return [lo, hi, (value - axis[lo]) / (axis[hi] - axis[lo])];
}

export function sampleAngularSurface(values, theta, phi, t, p) {
  const [t0, t1, wt] = bracket(theta, t);
  p = ((p - phi[0]) % TAU + TAU) % TAU + phi[0];
  let [p0, p1, wp] = bracket(phi, p);
  if (p >= phi[phi.length - 1]) {
    p0 = phi.length - 1; p1 = 0;
    wp = (p - phi[p0]) / (phi[0] + TAU - phi[p0]);
  }
  const row = i => values[i * phi.length + p0] * (1 - wp) + values[i * phi.length + p1] * wp;
  return row(t0) * (1 - wt) + row(t1) * wt;
}

export function sampleRadialSurface(values, coordinates, radius, minimum, maximum) {
  const { r, theta, phi } = coordinates;
  const valid = Array.from(r).map((value, i) => ({ value, i }))
    .filter(({ value }) => value >= minimum - 1e-10 * Math.max(1, maximum)
      && value <= maximum + 1e-10 * Math.max(1, maximum));
  if (!valid.length) throw new Error("This field has no samples in its radial domain.");
  const actualRadius = clamp(radius, valid[0].value, valid.at(-1).value);
  const [a, b, weight] = bracket(valid.map(v => v.value), actualRadius);
  const stride = theta.length * phi.length;
  const surface = new Float32Array(stride);
  for (let i = 0; i < stride; i++) {
    surface[i] = values[valid[a].i * stride + i] * (1 - weight) + values[valid[b].i * stride + i] * weight;
  }
  return { surface, radius: actualRadius, clamped: Math.abs(actualRadius - radius) > 1e-10 * Math.max(1, maximum) };
}

export function surfaceRange(values, mode, minimum, maximum) {
  if (mode === "manual") {
    if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || minimum >= maximum)
      throw new Error("Mollweide colour minimum must be smaller than maximum.");
    return [minimum, maximum];
  }
  let lo = Infinity, hi = -Infinity;
  for (const value of values) if (Number.isFinite(value)) { lo = Math.min(lo, value); hi = Math.max(hi, value); }
  if (!Number.isFinite(lo)) throw new Error("No finite values in this surface.");
  if (mode === "symmetric") { const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1; return [-m, m]; }
  if (lo === hi) { const pad = Math.abs(lo) * 0.01 || 1; return [lo - pad, hi + pad]; }
  return [lo, hi];
}

export function paintMollweide(canvas, { values, theta, phi, centre, title, range, colour, graticule }) {
  const ctx = canvas.getContext("2d");
  const width = 640, height = 320, left = 24, top = 60;
  canvas.width = 688; canvas.height = 456;
  ctx.fillStyle = "rgba(255,255,255,0.96)"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = "#666"; ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
  ctx.fillStyle = "#111"; ctx.font = "20px sans-serif";
  ctx.fillText(title, 18, 29, canvas.width - 36);
  ctx.font = "14px sans-serif";
  ctx.fillText(`Mollweide · centre ${Number((centre * 180 / Math.PI).toFixed(1))}° · longitude increases →`, 18, 49);
  const image = ctx.createImageData(width, height);
  for (let row = 0; row < height; row++) for (let col = 0; col < width; col++) {
    const point = inverseMollweide(4 * (col + .5) / width - 2, 1 - 2 * (row + .5) / height, centre);
    if (!point) continue;
    const value = sampleAngularSurface(values, theta, phi, point.theta, point.phi);
    if (!Number.isFinite(value)) continue;
    const rgb = colour(value); const offset = 4 * (row * width + col);
    image.data.set([rgb[0], rgb[1], rgb[2], 255], offset);
  }
  ctx.putImageData(image, left, top);
  if (graticule) {
    ctx.save(); ctx.strokeStyle = "rgba(0,0,0,0.28)"; ctx.lineWidth = 1;
    // Parameterize grid lines by the projection's auxiliary latitude alpha.
    for (let lon = -150; lon <= 150; lon += 30) {
      ctx.beginPath();
      for (let i = 0; i <= 100; i++) {
        const alpha = -Math.PI / 2 + Math.PI * i / 100;
        const x = left + width / 2 + width / 2 * lon / 180 * Math.cos(alpha);
        const y = top + height / 2 - height / 2 * Math.sin(alpha);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    for (let lat = -60; lat <= 60; lat += 30) {
      let low = -Math.PI / 2, high = Math.PI / 2;
      for (let i = 0; i < 40; i++) {
        const mid = (low + high) / 2;
        if (2 * mid + Math.sin(2 * mid) < Math.PI * Math.sin(lat * Math.PI / 180)) low = mid; else high = mid;
      }
      const alpha = (low + high) / 2, half = width / 2 * Math.cos(alpha);
      const y = top + height / 2 - height / 2 * Math.sin(alpha);
      ctx.beginPath(); ctx.moveTo(left + width / 2 - half, y); ctx.lineTo(left + width / 2 + half, y); ctx.stroke();
    }
    ctx.restore();
  }
  ctx.strokeStyle = "#444"; ctx.beginPath();
  ctx.ellipse(left + width / 2, top + height / 2, width / 2, height / 2, 0, 0, TAU); ctx.stroke();
  for (let x = 0; x < width; x++) {
    const rgb = colour(range[0] + (range[1] - range[0]) * x / (width - 1));
    ctx.fillStyle = `rgb(${rgb.join(",")})`; ctx.fillRect(left + x, 404, 1, 14);
  }
  ctx.fillStyle = "#111"; ctx.font = "16px sans-serif";
  const label = v => Number(v.toPrecision(5)).toString();
  ctx.textAlign = "left"; ctx.fillText(label(range[0]), left, 440);
  ctx.textAlign = "center"; ctx.fillText(label((range[0] + range[1]) / 2), canvas.width / 2, 440);
  ctx.textAlign = "right"; ctx.fillText(label(range[1]), left + width, 440); ctx.textAlign = "left";
}

export function createMollweideOverlay() {
  const canvas = document.createElement("canvas");
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(0, 1, 1, 0, -1, 1);
  const material = new THREE.SpriteMaterial({ depthTest: false, depthWrite: false, toneMapped: false });
  const sprite = new THREE.Sprite(material); scene.add(sprite);
  return {
    update(options) {
      paintMollweide(canvas, options);
      material.map?.dispose();
      material.map = new THREE.CanvasTexture(canvas);
      material.map.colorSpace = THREE.SRGBColorSpace;
      material.map.minFilter = THREE.LinearFilter; material.map.generateMipmaps = false;
      material.needsUpdate = true;
    },
    render(renderer, position, fraction) {
      if (!material.map) return;
      const width = renderer.domElement.width, height = renderer.domElement.height;
      const w = Math.min(width * fraction, height * .8 * canvas.width / canvas.height);
      const h = w * canvas.height / canvas.width, margin = Math.min(width, height) * .02;
      sprite.scale.set(w, h, 1);
      sprite.position.set(position.endsWith("right") ? width - margin - w / 2 : margin + w / 2,
        position.startsWith("top") ? height - margin - h / 2 : margin + height * .07 + h / 2, 0);
      camera.right = width; camera.top = height; camera.updateProjectionMatrix();
      const previous = renderer.autoClear;
      try { renderer.autoClear = false; renderer.render(scene, camera); }
      finally { renderer.autoClear = previous; }
    },
    dispose() { material.map?.dispose(); material.dispose(); },
  };
}
