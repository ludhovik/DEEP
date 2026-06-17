from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def sph_to_cart(r: float, theta: float, phi: float) -> np.ndarray:
    """
    Spherical to Cartesian coordinates.

    theta: colatitude, 0 at north pole
    phi: longitude
    """
    return np.array(
        [
            r * np.sin(theta) * np.cos(phi),
            r * np.sin(theta) * np.sin(phi),
            r * np.cos(theta),
        ],
        dtype=np.float32,
    )


def demo_fields(nr: int, nt: int, np_: int, r_inner: float, r_outer: float):
    """
    Generate synthetic physical-space fields shaped as:

        field[ir, itheta, iphi]

    This matches the JavaScript index:

        (ir * ntheta + itheta) * nphi + iphi
    """

    r = np.linspace(r_inner, r_outer, nr, dtype=np.float32)
    theta = np.linspace(0.0, np.pi, nt, dtype=np.float32)
    phi = np.linspace(0.0, 2.0 * np.pi, np_, endpoint=False, dtype=np.float32)

    R, TH, PH = np.meshgrid(r, theta, phi, indexing="ij")

    shell = (R - r_inner) / (r_outer - r_inner)

    # A fake dipole + non-axisymmetric perturbation for Br.
    Br = (
        2.0 * np.cos(TH) * (R / r_outer) ** 2
        + 0.45 * np.sin(3.0 * TH) * np.cos(4.0 * PH) * np.sin(np.pi * shell)
    )

    Bt = (
        np.sin(TH) * (R / r_outer)
        + 0.30 * np.cos(2.0 * TH + 0.8 * np.sin(PH)) * np.sin(np.pi * shell)
    )

    Bp = 0.65 * np.sin(TH) * np.sin(2.0 * PH) * np.sin(np.pi * shell)

    ur = 0.25 * np.sin(np.pi * shell) * np.sin(2.0 * TH) * np.cos(3.0 * PH)
    ut = 0.45 * np.sin(np.pi * shell) * np.cos(TH) * np.sin(2.0 * PH)
    up = 0.80 * R * np.sin(TH) + 0.15 * np.sin(np.pi * shell) * np.cos(5.0 * PH)

    C = (
        0.8 * np.cos(4.0 * PH) * np.sin(TH) ** 2 * np.sin(np.pi * shell)
        + 0.3 * np.cos(3.0 * TH)
        + 0.15 * np.sin(8.0 * PH + 2.0 * TH)
    )

    Babs = np.sqrt(Br * Br + Bt * Bt + Bp * Bp)

    return {
        "Br": Br,
        "Bt": Bt,
        "Bp": Bp,
        "ur": ur,
        "ut": ut,
        "up": up,
        "C": C,
        "Babs": Babs,
    }


def make_demo_field_lines(
    r_inner: float,
    r_outer: float,
    n_lat: int = 9,
    n_lon: int = 18,
    n_steps: int = 160,
):
    """
    Create synthetic magnetic-looking field lines.

    These are not integrated from the B field. They are only a placeholder
    until we implement real field-line integration from your physical statefile.
    """

    lines = []

    latitudes = np.linspace(20.0, 160.0, n_lat) * np.pi / 180.0
    longitudes = np.linspace(0.0, 2.0 * np.pi, n_lon, endpoint=False)

    for theta0 in latitudes:
        for phi0 in longitudes:
            polarity = 1 if np.cos(theta0) >= 0 else -1

            points = []
            for i in range(n_steps):
                s = i / (n_steps - 1)

                # Field-line-like loop inside the fluid shell, outside the inner core.
                r = r_inner + 0.08 * (r_outer - r_inner) + 0.78 * (r_outer - r_inner) * (0.5 + 0.5 * np.cos(2.0 * np.pi * s))
                theta = theta0 + 0.55 * np.sin(2.0 * np.pi * s) * np.sign(np.cos(theta0))
                phi = phi0 + polarity * 2.0 * np.pi * s

                xyz = sph_to_cart(r, theta, phi)
                points.append([float(xyz[0]), float(xyz[1]), float(xyz[2])])

            seed = sph_to_cart(r_outer, theta0, phi0)

            lines.append(
                {
                    "seed": [float(seed[0]), float(seed[1]), float(seed[2])],
                    "polarity": polarity,
                    "region": "fluid_shell_outside_inner_core",
                    "mode": "demo_shell_loop",
                    "closed": True,
                    "points": points,
                }
            )

    return lines


def main():
    # Moderate size for browser testing.
    # Later, this can be increased, but start modest.
    nr = 64
    ntheta = 128
    nphi = 256

    r_inner = 0.35
    r_outer = 1.0
    has_inner_core = True

    out = Path("public/data")
    out.mkdir(parents=True, exist_ok=True)

    fields = demo_fields(nr, ntheta, nphi, r_inner, r_outer)

    field_files = {}
    field_ranges = {}

    for name, arr in fields.items():
        arr = np.asarray(arr, dtype="<f4", order="C")
        filename = f"{name}_volume.f32"
        arr.tofile(out / filename)

        field_files[name] = filename
        field_ranges[name] = {
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
        }

    lines = make_demo_field_lines(r_inner, r_outer)
    with open(out / "B_lines.json", "w", encoding="utf-8") as f:
        json.dump(lines, f)

    metadata = {
        "description": "Synthetic demo data. Replace with converted physical statefile later.",
        "nr": nr,
        "ntheta": ntheta,
        "nphi": nphi,
        "r_inner": r_inner,
        "r_outer": r_outer,
        "has_inner_core": has_inner_core,
        "layout": "r_theta_phi",
        "endianness": "little",
        "fields": field_files,
        "ranges": field_ranges,
        "magnetic": {
            "has_magnetic_field": True,
            "classification": "demo_dynamo",
            "criterion": "synthetic demo data"
        },
        "field_lines": {
            "B_lines": "B_lines.json",
            "mode": "demo_shell",
            "description": "Synthetic closed-looking shell loops inside the fluid shell",
            "count": len(lines)
        },
    }

    with open(out / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("Wrote demo data to public/data")
    print(f"Grid: nr={nr}, ntheta={ntheta}, nphi={nphi}")
    print(f"Number of points per scalar field: {nr * ntheta * nphi:,}")
    print(f"Approximate size per scalar field: {nr * ntheta * nphi * 4 / 1024**2:.1f} MiB")


if __name__ == "__main__":
    main()
