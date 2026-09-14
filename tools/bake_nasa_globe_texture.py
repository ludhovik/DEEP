#!/usr/bin/env python3
"""Reproject the base colour of NASA's 55 Cancri e GLB to latitude/longitude.

Requires NumPy, SciPy and Pillow. This samples the published mesh and UVs;
it does not synthesize terrain. Restricted to one untransformed, origin-centred
mesh with an embedded base-colour image, as in the credited NASA download.
"""

import argparse
import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = args.source.read_bytes()
    magic, version, size = struct.unpack_from("<4sII", data)
    if (magic, version, size) != (b"glTF", 2, len(data)):
        raise ValueError("Expected a complete GLB 2 file")
    length, kind = struct.unpack_from("<II", data, 12)
    if kind != 0x4E4F534A:
        raise ValueError("Expected JSON as the first GLB chunk")
    doc = json.loads(data[20:20 + length])
    offset = 20 + length
    length, kind = struct.unpack_from("<II", data, offset)
    if kind != 0x004E4942:
        raise ValueError("Expected an embedded BIN chunk")
    binary = data[offset + 8:offset + 8 + length]
    if len(doc["nodes"]) != 1 or any(
        key in doc["nodes"][0] for key in ("matrix", "translation", "rotation", "scale")
    ):
        raise ValueError("Only a single untransformed mesh is supported")
    primitives = doc["meshes"][doc["nodes"][0]["mesh"]]["primitives"]
    if len(primitives) != 1 or primitives[0].get("mode", 4) != 4:
        raise ValueError("Expected one triangle primitive")
    primitive = primitives[0]

    def view_bytes(index):
        view = doc["bufferViews"][index]
        if view.get("buffer", 0) != 0:
            raise ValueError("External buffers are unsupported")
        start = view.get("byteOffset", 0)
        return binary[start:start + view["byteLength"]]

    def accessor(index):
        item = doc["accessors"][index]
        view = doc["bufferViews"][item["bufferView"]]
        if "byteStride" in view or "sparse" in item or item.get("normalized"):
            raise ValueError("Expected tightly packed, unnormalized accessors")
        dtype = {5126: "<f4", 5123: "<u2", 5125: "<u4"}[item["componentType"]]
        components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[item["type"]]
        return np.frombuffer(view_bytes(item["bufferView"]), dtype=dtype,
                             count=item["count"] * components,
                             offset=item.get("byteOffset", 0)).reshape(-1, components)

    vertices = accessor(primitive["attributes"]["POSITION"]).astype(float)
    uv = accessor(primitive["attributes"]["TEXCOORD_0"]).astype(float)
    indices = accessor(primitive["indices"]).reshape(-1, 3)
    material = doc["materials"][primitive["material"]]
    texture_info = material["pbrMetallicRoughness"]["baseColorTexture"]
    if texture_info.get("texCoord", 0) != 0 or "extensions" in texture_info:
        raise ValueError("Expected untransformed TEXCOORD_0")
    texture = doc["textures"][texture_info["index"]]
    image = doc["images"][texture["source"]]
    pixels = np.asarray(Image.open(io.BytesIO(view_bytes(image["bufferView"])))
                        .convert("RGB"), dtype=float)
    triangles = vertices[indices]
    centres = triangles.mean(axis=1)
    tree = cKDTree(centres / np.linalg.norm(centres, axis=1)[:, None])
    a = triangles[:, 0]
    e1, e2 = triangles[:, 1] - a, triangles[:, 2] - a
    triangle_uv = uv[indices]
    width, height = 2048, 1024
    lon, lat = np.meshgrid(np.linspace(-np.pi, np.pi, width),
                          np.linspace(np.pi / 2, -np.pi / 2, height))
    # glTF uses +Y up. Map that axis to north in the equirectangular output.
    directions = np.stack([np.cos(lat) * np.cos(lon), np.sin(lat),
                           -np.cos(lat) * np.sin(lon)], axis=-1).reshape(-1, 3)
    result = np.empty((len(directions), 3), dtype=np.uint8)
    tex_h, tex_w = pixels.shape[:2]
    for start in range(0, len(directions), 8192):
        rays = directions[start:start + 8192]
        _, near = tree.query(rays, k=min(32, len(triangles)))
        p = np.cross(rays[:, None, :], e2[near])
        det = np.einsum("nki,nki->nk", e1[near], p)
        safe_det = np.where(abs(det) > 1e-12, det, np.nan)
        u = np.einsum("nki,nki->nk", -a[near], p) / safe_det
        q = np.cross(-a[near], e1[near])
        v = np.einsum("ni,nki->nk", rays, q) / safe_det
        distance = np.einsum("nki,nki->nk", e2[near], q) / safe_det
        hit = (u >= -1e-7) & (v >= -1e-7) & (u + v <= 1 + 1e-7) & (distance > 0)
        if not hit.any(axis=1).all():
            raise ValueError("Mesh does not cover every output direction; no image written")
        chosen = np.where(hit, distance, np.inf).argmin(axis=1)
        row = np.arange(len(rays))
        u, v = u[row, chosen, None], v[row, chosen, None]
        coords = triangle_uv[near[row, chosen]]
        sample = (1 - u - v) * coords[:, 0] + u * coords[:, 1] + v * coords[:, 2]
        # glTF UV v=0 is the top of the embedded image. Bilinear, clamp to edge.
        x = np.clip(sample[:, 0] * tex_w - 0.5, 0, tex_w - 1)
        y = np.clip(sample[:, 1] * tex_h - 0.5, 0, tex_h - 1)
        ix, iy = x.astype(int), y.astype(int)
        jx, jy = np.minimum(ix + 1, tex_w - 1), np.minimum(iy + 1, tex_h - 1)
        fx, fy = (x - ix)[:, None], (y - iy)[:, None]
        rgb = ((1 - fy) * ((1 - fx) * pixels[iy, ix] + fx * pixels[iy, jx])
               + fy * ((1 - fx) * pixels[jy, ix] + fx * pixels[jy, jx]))
        result[start:start + len(rays)] = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    result = result.reshape(height, width, 3)
    result[:, -1] = result[:, 0]
    result[0] = result[0, 0]
    result[-1] = result[-1, 0]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(result).save(args.out)
    print(f"Reprojected {len(triangles)} triangles; all {width * height} directions covered: {args.out}")


if __name__ == "__main__":
    main()
