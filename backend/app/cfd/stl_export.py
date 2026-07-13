"""
Exports the Darrieus blade cross-section (from app/cfd/airfoil_geometry.py) as
an extruded, closed ASCII STL solid -- the actual geometry file snappyHexMesh
needs to mesh around the blade. Extrusion is a simple linear sweep along the
blade height (straight blades; helical twist support is a documented seam for
a later phase, not faked here).
"""
from __future__ import annotations
import numpy as np
from app.cfd.airfoil_geometry import naca_panels


def _facet(v1, v2, v3) -> str:
    n = np.cross(np.array(v2) - np.array(v1), np.array(v3) - np.array(v1))
    norm = np.linalg.norm(n)
    n = n / norm if norm > 1e-12 else np.array([0.0, 0.0, 1.0])
    return (
        f"  facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}\n"
        f"    outer loop\n"
        f"      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}\n"
        f"      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}\n"
        f"      vertex {v3[0]:.6e} {v3[1]:.6e} {v3[2]:.6e}\n"
        f"    endloop\n"
        f"  endfacet\n"
    )


def generate_blade_stl(
    chord_m: float, thickness_ratio: float, span_m: float, n_panels: int = 60,
    solid_name: str = "blade",
) -> str:
    """
    Returns ASCII STL text for a straight-extruded blade of the given chord,
    thickness ratio, and span, centred at z in [0, span_m].
    """
    panels = naca_panels(thickness_ratio, n_panels=n_panels, chord=chord_m)
    n = len(panels)
    # boundary loop points (n+1, closed) in the x-y plane
    loop = [(p.xa, p.ya) for p in panels] + [(panels[-1].xb, panels[-1].yb)]

    facets = []

    # Side wall facets (two triangles per panel, sweeping from z=0 to z=span_m)
    for i in range(n):
        x1, y1 = loop[i]
        x2, y2 = loop[i + 1]
        v1 = (x1, y1, 0.0)
        v2 = (x2, y2, 0.0)
        v3 = (x2, y2, span_m)
        v4 = (x1, y1, span_m)
        facets.append(_facet(v1, v2, v3))
        facets.append(_facet(v1, v3, v4))

    # Simple fan triangulation for the root (z=0) and tip (z=span_m) caps.
    # A true NACA section is non-convex enough that a fan from the centroid
    # is adequate for a thin symmetric section at reasonable panel counts;
    # documented here as a simplification a real meshing pass should redo
    # with a proper 2D triangulation (e.g. ear-clipping) for thicker sections.
    cx = sum(p[0] for p in loop[:-1]) / n
    cy = sum(p[1] for p in loop[:-1]) / n
    for i in range(n):
        x1, y1 = loop[i]
        x2, y2 = loop[i + 1]
        facets.append(_facet((cx, cy, 0.0), (x1, y1, 0.0), (x2, y2, 0.0)))
        facets.append(_facet((cx, cy, span_m), (x2, y2, span_m), (x1, y1, span_m)))

    header = f"solid {solid_name}\n"
    footer = f"endsolid {solid_name}\n"
    return header + "".join(facets) + footer
