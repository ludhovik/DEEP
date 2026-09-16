import assert from "node:assert/strict";
import test from "node:test";
import { inverseMollweide, sampleAngularSurface, sampleRadialSurface, surfaceRange, paintMollweide } from "../src/mollweide.js";
const near = (a, b, tolerance = 1e-10) => assert.ok(Math.abs(a - b) < tolerance, `${a} != ${b}`);

test("Mollweide equator, poles, ellipse mask and central meridian", () => {
  near(inverseMollweide(0, 0).theta, Math.PI / 2);
  near(inverseMollweide(1, 0).phi, Math.PI / 2);
  near(inverseMollweide(-1, 0).phi, 3 * Math.PI / 2);
  near(inverseMollweide(0, 1).theta, 0);
  near(inverseMollweide(0, -1).theta, Math.PI);
  near(inverseMollweide(0, 0, Math.PI).phi, Math.PI);
  assert.equal(inverseMollweide(1.9, .9), null);
  // A numerical Jacobian checks equal-area behaviour away from poles/seam:
  // cos(latitude) d(latitude,longitude)/d(x,y) = 2 everywhere.
  for (const [x, y] of [[.1,.1],[.3,.6],[-.5,-.4]]) {
    const h = 1e-6, p = inverseMollweide(x, y);
    const a = inverseMollweide(x + h, y), b = inverseMollweide(x, y + h);
    const jac = Math.abs(((a.theta-p.theta)*(b.phi-p.phi)-(a.phi-p.phi)*(b.theta-p.theta))/(h*h));
    near(jac * Math.sin(p.theta), 2, 2e-5);
  }
});

test("angular interpolation uses nonuniform coordinates and wraps the longitude seam", () => {
  const theta = [.2, .8, 2.9], phi = [.1, 1, 3, 5];
  const values = Float32Array.from(theta.flatMap(t => phi.map(p => 2*t + p)));
  near(sampleAngularSurface(values, theta, phi, .5, 2), 3, 1e-6);
  near(sampleAngularSurface(values, theta, phi, .5, 2 + 2*Math.PI), 3, 1e-6);
  near(sampleAngularSurface(values, theta, phi, .5, .1 - 1e-8), 1.1, 1e-6);
});

test("arbitrary depth interpolates radii without entering padded solid regions", () => {
  const coordinates = { r: [0, .2, .5, 1], theta: [0, Math.PI], phi: [0, Math.PI] };
  const values = Float32Array.from(coordinates.r.flatMap(r => Array(4).fill(r*10)));
  const interior = sampleRadialSurface(values, coordinates, .7, .5, 1);
  for (const v of interior.surface) near(v, 7);
  near(interior.radius, .7); assert.equal(interior.clamped, false);
  const padded = sampleRadialSurface(values, coordinates, .1, .5, 1);
  near(padded.radius, .5); assert.equal(padded.clamped, true);
  for (const v of padded.surface) near(v, 5);
  assert.throws(() => sampleRadialSurface(values, coordinates, .5, .6, .7), /no samples/);
});

test("surface colour scales use selected surface data and reject invalid manual ranges", () => {
  assert.deepEqual(surfaceRange([-2,4], "symmetric"), [-4,4]);
  assert.deepEqual(surfaceRange([-2,4], "minmax"), [-2,4]);
  assert.deepEqual(surfaceRange([0], "minmax"), [-1,1]);
  assert.deepEqual(surfaceRange([-2,4], "manual", -1, 1), [-1,1]);
  assert.throws(() => surfaceRange([0], "manual", 1, 1));
});

test("raster draws the actual field inside the ellipse and masks the corners", () => {
  let raster;
  const ctx = { createImageData: (w,h) => ({ data: new Uint8ClampedArray(w*h*4) }),
    putImageData(image) { raster = image; }, fillRect() {}, strokeRect() {}, fillText() {},
    beginPath() {}, ellipse() {}, stroke() {} };
  const canvas = { getContext: () => ctx };
  paintMollweide(canvas, { values: new Float32Array(8).fill(.5), theta: [0,Math.PI],
    phi: [0,Math.PI/2,Math.PI,3*Math.PI/2], centre: 0, title: "constant", range: [0,1],
    colour: v => [v*200,0,0], graticule: false });
  assert.equal(raster.data[3], 0);
  const centre = (160*640+320)*4;
  assert.deepEqual(Array.from(raster.data.slice(centre,centre+4)), [100,0,0,255]);
});
