#!/usr/bin/env python3
"""Render Li et al. (2008) continental blocks at 1000 Ma as a globe texture.

Requires pygplates 1.0, matplotlib and Pillow. Download and unpack the model
linked in public/assets/surfaces/CREDITS.txt, then pass its model directory.
This is a tectonic-block map, not a reconstruction of coastlines or topography.
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as PlotPath
from matplotlib.patches import PathPatch
import numpy as np
import pygplates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    geometries = []
    pygplates.reconstruct(
        str(args.model_dir / "RodiniaBlocks_WithPlateIDColumnAndIDs.shp"),
        str(args.model_dir / "RodiniaModel_CompleteRotationFile.rot"),
        geometries, 1000, anchor_plate_id=0,
    )
    if not geometries:
        raise ValueError("The model produced no continental blocks at 1000 Ma")

    # Centre on 120 E to keep Rodinia together. No tilt or latitude shift.
    wrapper = pygplates.DateLineWrapper(120)
    ocean = "#15394c"
    fig = plt.figure(figsize=(20.48, 10.24), dpi=100, facecolor=ocean)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=ocean)
    ax.set(xlim=(-60, 300), ylim=(-90, 90), aspect="equal")
    ax.set_axis_off()
    for reconstructed in geometries:
        for polygon in wrapper.wrap(reconstructed.get_reconstructed_geometry(), 0.2):
            rings = [polygon.get_exterior_points()]
            rings += [polygon.get_interior_points(i)
                      for i in range(polygon.get_number_of_interior_rings())]
            vertices, codes = [], []
            for i, ring in enumerate(rings):
                xy = np.array([(p.get_longitude(), p.get_latitude()) for p in ring])
                # Opposite winding makes any interior rings transparent.
                area = np.sum(xy[:, 0] * np.roll(xy[:, 1], -1)
                              - np.roll(xy[:, 0], -1) * xy[:, 1])
                if (area > 0) != (i == 0):
                    xy = xy[::-1]
                vertices.extend([*xy, xy[0]])
                codes.extend([PlotPath.MOVETO] + [PlotPath.LINETO] * (len(xy) - 1)
                             + [PlotPath.CLOSEPOLY])
            ax.add_patch(PathPatch(PlotPath(vertices, codes), facecolor="#bd9867",
                                   edgecolor="#eed4a1", linewidth=0.55))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=100, facecolor=ocean, metadata={
        "Title": "Rodinia: continental blocks at 1000 Ma",
        "Author": "DEEPscope, after Li et al. (2008) / EarthByte",
        "Description": "CC BY 4.0; see CREDITS.txt. Equirectangular, centre 120 E.",
    })
    plt.close(fig)
    print(f"Rendered {len(geometries)} reconstructed geometries to {args.out}")


if __name__ == "__main__":
    main()
