import * as THREE from "three";

export const TIME_BOX_POSITIONS = ["bottom-left", "bottom-right", "top-left", "top-right"];

export function simulationTimeLabel(metadata, frame = null, precision = 7) {
  if (!metadata) return "";
  // An explicit null means unknown, not zero. Only older metadata lacking
  // the key may fall back to the sequence index's simulation time.
  const time = Object.hasOwn(metadata, "time") ? metadata.time : frame?.time;
  if (typeof time !== "number" || !Number.isFinite(time)) return "t = unknown";
  const digits = Math.max(2, Math.min(12, Math.round(Number(precision) || 7)));
  const units = typeof metadata.time_units === "string" && metadata.time_units.trim()
    ? metadata.time_units.trim() : "native units";
  return `t = ${Number(time.toPrecision(digits)).toString()} (${units})`;
}

export function timeBoxLayout(width, height, textureWidth, textureHeight, position, size = 18) {
  // Relative to the image, so high-resolution exports keep the same layout.
  const scale = Math.min(width / 1200, height / 700) * size / 36;
  const w = textureWidth * scale, h = textureHeight * scale;
  const margin = Math.min(width, height) * 0.02;
  return { width: w, height: h,
    x: position.endsWith("right") ? width - margin - w / 2 : margin + w / 2,
    y: position.startsWith("top") ? height - margin - h / 2 : margin + h / 2 };
}

// Draw directly into the same WebGL canvas as the data, so PNG/PDF, realtime
// MediaRecorder and offline VideoEncoder all capture the identical time box.
export function createSimulationTimeOverlay({ makeCanvas = () => document.createElement("canvas") } = {}) {
  const canvas = makeCanvas();
  const ctx = canvas.getContext("2d");
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearFilter;
  texture.generateMipmaps = false;
  const material = new THREE.SpriteMaterial({ map: texture, depthTest: false, depthWrite: false, toneMapped: false });
  const sprite = new THREE.Sprite(material);
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(0, 1, 1, 0, -1, 1);
  scene.add(sprite);
  let lastText = null;
  return {
    render(renderer, text, position = "bottom-left", size = 18) {
      if (!text) return;
      if (text !== lastText) {
        ctx.font = "36px sans-serif";
        canvas.width = Math.ceil(ctx.measureText(text).width) + 48;
        canvas.height = 76;
        ctx.fillStyle = "rgba(255,255,255,0.92)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = "rgba(0,0,0,0.3)";
        ctx.lineWidth = 2;
        ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
        ctx.font = "36px sans-serif";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#111111";
        ctx.fillText(text, 24, canvas.height / 2);
        // Canvas resizing changes the GPU texture dimensions; replace the
        // texture when the label changes and release the old allocation.
        const next = new THREE.CanvasTexture(canvas);
        next.colorSpace = THREE.SRGBColorSpace;
        next.minFilter = THREE.LinearFilter;
        next.generateMipmaps = false;
        material.map.dispose();
        material.map = next;
        lastText = text;
      }
      const width = renderer.domElement.width, height = renderer.domElement.height;
      const layout = timeBoxLayout(width, height, canvas.width, canvas.height, position, size);
      camera.right = width; camera.top = height; camera.updateProjectionMatrix();
      sprite.position.set(layout.x, layout.y, 0);
      sprite.scale.set(layout.width, layout.height, 1);
      const autoClear = renderer.autoClear;
      try {
        renderer.autoClear = false;
        renderer.render(scene, camera);
      } finally {
        renderer.autoClear = autoClear;
      }
    },
    dispose() { material.map.dispose(); material.dispose(); },
  };
}
