#!/usr/bin/env python3
"""Adapt a downloaded tileable material to a 2:1 spherical image (NumPy/Pillow).

Three perpendicular planar samples are blended by the sphere normal. This
avoids stretching a planar photograph or texture into pinched polar caps.
The result is decorative artwork, not a geographic reconstruction.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    texture = np.asarray(Image.open(args.source).convert("RGB"), dtype=np.float32)
    height, width = texture.shape[:2]

    def sample(u, v):
        tx, ty = (u % 1) * width, (v % 1) * height
        ix, iy = np.floor(tx).astype(int), np.floor(ty).astype(int)
        fx, fy = (tx - ix)[..., None], (ty - iy)[..., None]
        return ((1 - fy) * ((1 - fx) * texture[iy % height, ix % width]
                           + fx * texture[iy % height, (ix + 1) % width])
                + fy * ((1 - fx) * texture[(iy + 1) % height, ix % width]
                        + fx * texture[(iy + 1) % height, (ix + 1) % width]))

    lon, lat = np.meshgrid(np.linspace(-np.pi, np.pi, 2048),
                          np.linspace(np.pi / 2, -np.pi / 2, 1024))
    x, y, z = np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)
    weights = np.stack([abs(x)**8, abs(y)**8, abs(z)**8], axis=-1)
    weights /= weights.sum(axis=-1, keepdims=True)
    rgb = np.zeros((*x.shape, 3))
    for i, (u, v) in enumerate([(y, z), (x, z), (x, y)]):
        rgb += weights[..., i, None] * sample(0.5 + 0.5 * u, 0.5 - 0.5 * v)
    pixels = np.clip(np.rint(rgb), 0, 255).astype(np.uint8)
    # Identical samples at the join and each pole, including rounding effects.
    pixels[:, -1] = pixels[:, 0]
    pixels[0] = pixels[0, 0]
    pixels[-1] = pixels[-1, 0]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels).save(args.out)
    print(f"Wrapped {args.source} to {args.out}")


if __name__ == "__main__":
    main()
