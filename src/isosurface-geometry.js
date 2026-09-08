import * as THREE from "three";
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

function normalizePhi(phi) {
  const twoPi = 2.0 * Math.PI;
  return ((phi % twoPi) + twoPi) % twoPi;
}

function planeValueAtPoint(point, phi0) {
  const x = point[0];
  const y = point[1];
  return -Math.sin(phi0) * x + Math.cos(phi0) * y;
}

function shouldKeepPointForIsoClip(point, clipOptions = null) {
  if (!clipOptions?.enabled) return true;

  if (clipOptions.mode === "between-meridians-behind" && clipOptions.hasTwoPlanes) {
    const a = normalizePhi(clipOptions.phiA);
    const b = normalizePhi(clipOptions.phiB);
    const spanAB = (b - a + 2.0 * Math.PI) % (2.0 * Math.PI);
    const useAB = spanAB <= Math.PI;
    const valA = planeValueAtPoint(point, a);
    const valB = planeValueAtPoint(point, b);
    const offA = Number(clipOptions.offsetA || 0.0);
    const offB = Number(clipOptions.offsetB || 0.0);
    const inFrontOpening = useAB
      ? (valA >= offA && valB <= offB)
      : (valB >= offB && valA <= offA);
    return !inFrontOpening;
  }

  const val = planeValueAtPoint(point, clipOptions.phi0);
  const off = Number(clipOptions.offset || 0.0);
  return clipOptions.side === "negative" ? val < off : val > off;
}

function sphericalPositionArray(r, theta, phi) {
  const st = Math.sin(theta);
  return [
    r * st * Math.cos(phi),
    r * st * Math.sin(phi),
    r * Math.cos(theta),
  ];
}

function makeSampleIndices(n, maxCount, includeLast = true) {
  const count = Math.max(2, Math.min(n, Math.round(maxCount)));
  const out = [];
  if (includeLast) {
    for (let k = 0; k < count; k++) {
      out.push(Math.round((k * (n - 1)) / Math.max(1, count - 1)));
    }
  } else {
    for (let k = 0; k < count; k++) {
      out.push(Math.floor((k * n) / count) % n);
    }
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

function interpolateIsoPoint(a, b, isoValue) {
  const denom = b.v - a.v;
  const q = Math.abs(denom) > 1.0e-30 ? clamp((isoValue - a.v) / denom, 0.0, 1.0) : 0.5;
  return [
    a.p[0] + q * (b.p[0] - a.p[0]),
    a.p[1] + q * (b.p[1] - a.p[1]),
    a.p[2] + q * (b.p[2] - a.p[2]),
  ];
}

function pushTri(positions, p0, p1, p2, clipOptions = null) {
  const centroid = [
    (p0[0] + p1[0] + p2[0]) / 3.0,
    (p0[1] + p1[1] + p2[1]) / 3.0,
    (p0[2] + p1[2] + p2[2]) / 3.0,
  ];
  if (!shouldKeepPointForIsoClip(centroid, clipOptions)) return;
  positions.push(
    p0[0], p0[1], p0[2],
    p1[0], p1[1], p1[2],
    p2[0], p2[1], p2[2]
  );
}

function polygoniseTetra(positions, tet, isoValue, clipOptions = null) {
  const inside = tet.map((v) => Number.isFinite(v.v) && v.v >= isoValue);
  const insideIdx = [];
  const outsideIdx = [];
  for (let i = 0; i < 4; i++) {
    if (inside[i]) insideIdx.push(i);
    else outsideIdx.push(i);
  }

  if (insideIdx.length === 0 || insideIdx.length === 4) return;

  if (insideIdx.length === 1 || insideIdx.length === 3) {
    const singleInside = insideIdx.length === 1;
    const a = singleInside ? insideIdx[0] : outsideIdx[0];
    const others = singleInside ? outsideIdx : insideIdx;

    const p0 = interpolateIsoPoint(tet[a], tet[others[0]], isoValue);
    const p1 = interpolateIsoPoint(tet[a], tet[others[1]], isoValue);
    const p2 = interpolateIsoPoint(tet[a], tet[others[2]], isoValue);

    if (singleInside) pushTri(positions, p0, p1, p2, clipOptions);
    else pushTri(positions, p0, p2, p1, clipOptions);
    return;
  }

  // Two inside, two outside: quadrilateral split into two triangles.
  const a = insideIdx[0];
  const b = insideIdx[1];
  const c = outsideIdx[0];
  const d = outsideIdx[1];

  const pAC = interpolateIsoPoint(tet[a], tet[c], isoValue);
  const pAD = interpolateIsoPoint(tet[a], tet[d], isoValue);
  const pBC = interpolateIsoPoint(tet[b], tet[c], isoValue);
  const pBD = interpolateIsoPoint(tet[b], tet[d], isoValue);

  pushTri(positions, pAC, pBC, pAD, clipOptions);
  pushTri(positions, pAD, pBC, pBD, clipOptions);
}

export function buildSphericalIsosurface({ field, metadata, coords, isoValue, requestedResolution, clipOptions = null, domain = null }, report = () => {}) {
  const idx = (ir, it, ip) => (ir * metadata.ntheta + it) * metadata.nphi + ip;
  const radiusAtIndex = i => coords.r[i];
  const thetaAtIndex = i => coords.theta[i];
  const phiAtIndex = i => coords.phi[i];
  const nr = metadata.nr;
  const nt = metadata.ntheta;
  const np = metadata.nphi;

  const res = Math.max(8, Math.min(96, Math.round(Number(requestedResolution))));
  const start = domain?.start ?? 0;
  const end = domain?.end ?? (nr - 1);
  if (domain?.empty || end <= start) return new THREE.BufferGeometry();
  const rIdx = makeSampleIndices(end - start + 1, res, true).map(i => i + start);
  const tIdx = makeSampleIndices(nt, res, true);
  const pIdx = makeSampleIndices(np, 2 * res, false);

  const positions = [];
  const tetrahedra = [
    [0, 5, 1, 6],
    [0, 1, 2, 6],
    [0, 2, 3, 6],
    [0, 3, 7, 6],
    [0, 7, 4, 6],
    [0, 4, 5, 6],
  ];

  function vertex(ir, it, ip, phiShift = 0.0) {
    const r = radiusAtIndex(ir);
    const theta = thetaAtIndex(it);
    const phi = phiAtIndex(ip) + phiShift;
    const v = field[idx(ir, it, ip)];
    return { p: sphericalPositionArray(r, theta, phi), v };
  }

  for (let ar = 0; ar < rIdx.length - 1; ar++) {
    report({ label: "Building isosurface", fraction: ar / (rIdx.length - 1) });
    const ir0 = rIdx[ar];
    const ir1 = rIdx[ar + 1];

    for (let at = 0; at < tIdx.length - 1; at++) {
      const it0 = tIdx[at];
      const it1 = tIdx[at + 1];

      for (let ap = 0; ap < pIdx.length; ap++) {
        const ip0 = pIdx[ap];
        const ip1 = pIdx[(ap + 1) % pIdx.length];
        const wraps = ip1 <= ip0;
        const phiShift1 = wraps ? 2.0 * Math.PI : 0.0;

        const cube = [
          vertex(ir0, it0, ip0, 0.0),
          vertex(ir1, it0, ip0, 0.0),
          vertex(ir1, it1, ip0, 0.0),
          vertex(ir0, it1, ip0, 0.0),
          vertex(ir0, it0, ip1, phiShift1),
          vertex(ir1, it0, ip1, phiShift1),
          vertex(ir1, it1, ip1, phiShift1),
          vertex(ir0, it1, ip1, phiShift1),
        ];

        for (const tet of tetrahedra) {
          polygoniseTetra(
            positions,
            [cube[tet[0]], cube[tet[1]], cube[tet[2]], cube[tet[3]]],
            Number(isoValue),
            clipOptions
          );
        }
      }
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();

  geometry.computeBoundingSphere();
  report({ label: "Isosurface ready", fraction: 1 });
  return geometry;
}
