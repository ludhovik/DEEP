import * as THREE from "three";

// Map the interpolated scalar at each pixel, instead of interpolating RGB
// vertex colours. A narrow colour band must not turn into a triangle diagonal.
export function setSliceColours(mesh, values, minimum, maximum, stops) {
  const samples = new Float32Array(values.length * 2);
  const span = maximum - minimum || 1;
  for (let i = 0; i < values.length; i++) {
    samples[2 * i] = Number.isFinite(values[i]) ? (values[i] - minimum) / span : 0;
    samples[2 * i + 1] = Number.isFinite(values[i]) ? 1 : 0;
  }
  const attribute = mesh.geometry.getAttribute("sliceSample");
  if (attribute?.array.length === samples.length) {
    attribute.array.set(samples); attribute.needsUpdate = true;
  } else {
    mesh.geometry.setAttribute("sliceSample", new THREE.BufferAttribute(samples, 2).setUsage(THREE.DynamicDrawUsage));
  }
  const material = mesh.material;
  material.vertexColors = false;
  const uniforms = {
    sliceStops: { value: stops.map(([position]) => position) },
    sliceColours: { value: stops.map(([, rgb]) => new THREE.Vector3(...rgb.map(x => x / 255))) },
  };
  material.onBeforeCompile = shader => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = "attribute vec2 sliceSample;\nvarying vec2 vSliceSample;\n" + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace("#include <begin_vertex>",
      "#include <begin_vertex>\nvSliceSample = sliceSample;");
    shader.fragmentShader = `
      varying vec2 vSliceSample;
      uniform float sliceStops[${stops.length}];
      uniform vec3 sliceColours[${stops.length}];
      vec3 sliceColour(float value) {
        float t = clamp(value, 0.0, 1.0);
        vec3 rgb = sliceColours[${stops.length - 1}];
        for (int i = 0; i < ${stops.length - 1}; i++) {
          if (t <= sliceStops[i + 1]) {
            float q = clamp((t - sliceStops[i]) / max(sliceStops[i+1] - sliceStops[i], 1e-10), 0.0, 1.0);
            rgb = mix(sliceColours[i], sliceColours[i+1], q);
            break;
          }
        }
        return mix(rgb / 12.92, pow((rgb + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), rgb));
      }
    ` + shader.fragmentShader;
    shader.fragmentShader = shader.fragmentShader.replace("#include <color_fragment>",
      "if (vSliceSample.y < 0.9999) discard;\ndiffuseColor.rgb = sliceColour(vSliceSample.x);");
  };
  // Colours and manual bounds can change while geometry is reused.
  material.customProgramCacheKey = () => `slice-scalar-v1:${JSON.stringify(stops)}`;
  material.needsUpdate = true;
}
