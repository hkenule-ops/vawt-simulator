"""
Exports the Darrieus blade as an extruded, closed ASCII STL solid -- the
actual geometry file snappyHexMesh needs to mesh around the blade.

Straight blades: a simple linear sweep along the blade height (the original
behaviour). Twisted/helical blades: the 2D NACA section is lofted station by
station using `app.geometry.models.spanwise_stations` -- at each spanwise
height the section is rotated by that station's local twist (about its own
quarter-chord, the standard pitch axis for a thin symmetric section) and
translated by that station's local helical azimuth offset around the rotor
axis, then the stations are stitched together into one closed solid. With
zero twist and zero helical sweep this reduces to exactly the original
straight extrusion.
"""
from __future__ import annotations
import numpy as np
from app.cfd.airfoil_geometry import naca_panels
from app.geometry.models import DarrieusBladeGeometry, spanwise_stations


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


def _section_loop(thickness_ratio: float, chord_m: float, n_panels: int) -> list[tuple[float, float]]:
    """Boundary loop points (n+1, closed) for a NACA00XX section in the x-y plane, quarter-chord at origin."""
    panels = naca_panels(thickness_ratio, n_panels=n_panels, chord=chord_m)
    loop = [(p.xa, p.ya) for p in panels] + [(panels[-1].xb, panels[-1].yb)]
    # Recentre on the quarter-chord (x = 0.25*chord) so twist rotation below
    # pivots about the standard aerodynamic pitch axis rather than the
    # leading edge.
    x_offset = 0.25 * chord_m
    return [(x - x_offset, y) for x, y in loop]


def _transform_section(loop: list[tuple[float, float]], twist_rad: float,
                        helical_rad: float, radius_m: float) -> list[tuple[float, float, float]]:
    """
    Rotate a section (about its own quarter-chord, in-plane) by `twist_rad`,
    then place it at the rotor's swept radius, offset azimuthally by
    `helical_rad` around the rotor (z) axis. Returns 3D points; z (height)
    is added by the caller since it's constant for a given station's loop.
    """
    ct, st = np.cos(twist_rad), np.sin(twist_rad)
    ch, sh = np.cos(helical_rad), np.sin(helical_rad)
    pts = []
    for x, y in loop:
        # In-plane twist (pitches the section about its quarter-chord).
        xt = x * ct - y * st
        yt = x * st + y * ct
        # Place at radius, then sweep azimuthally by the helical offset.
        # x is chordwise (radial-ish), y is thickness -- the section's local
        # x-axis is tangent-ish to the rotor circle at the root's azimuth 0.
        rx = radius_m + xt
        px = rx * ch
        pz = rx * sh
        pts.append((px, yt, pz))
    return pts


def generate_blade_stl(
    chord_m: float, thickness_ratio: float, span_m: float, n_panels: int = 60,
    solid_name: str = "blade",
    twist_angle_deg: float = 0.0, helical_twist_deg: float = 0.0,
    rotor_radius_m: float = 0.0, n_span_stations: int | None = None,
) -> str:
    """
    Returns ASCII STL text for a blade of the given chord, thickness ratio,
    and span, centred at z in [0, span_m].

    Straight-blade fast path (twist_angle_deg == helical_twist_deg == 0):
    identical to the original simple linear extrusion, in the section's own
    local frame (rotor_radius_m unused). Twisted/helical path: loft `n_span_stations`
    cross-sections (default 12) from root to tip, each pitched by its local
    twist and swept azimuthally by its local helical offset around
    `rotor_radius_m` (the blade's mean swept radius), then stitch the
    stations together with quad side walls.
    """
    is_straight = (twist_angle_deg == 0.0 and helical_twist_deg == 0.0)
    loop = _section_loop(thickness_ratio, chord_m, n_panels)
    n = len(loop) - 1  # number of panels

    facets: list[str] = []

    if is_straight:
        # Original behaviour: simple linear sweep in the section's local frame.
        for i in range(n):
            x1, y1 = loop[i]
            x2, y2 = loop[i + 1]
            v1 = (x1, y1, 0.0)
            v2 = (x2, y2, 0.0)
            v3 = (x2, y2, span_m)
            v4 = (x1, y1, span_m)
            facets.append(_facet(v1, v2, v3))
            facets.append(_facet(v1, v3, v4))
        root_loop = [(x, y, 0.0) for x, y in loop[:-1]]
        tip_loop = [(x, y, span_m) for x, y in loop[:-1]]
    else:
        # Fabricate a temporary geometry object purely to reuse the single
        # source of truth for span discretisation (twist/helical distribution).
        dummy = DarrieusBladeGeometry(
            blade_height_m=span_m, twist_angle_deg=twist_angle_deg,
            helical_twist_deg=helical_twist_deg,
        )
        n_stations = n_span_stations or 12
        stations = spanwise_stations(dummy, n_stations)
        R = rotor_radius_m if rotor_radius_m > 0 else 0.0

        loops_3d = []
        z_levels = []
        for st in stations:
            twist_rad = np.radians(st.local_twist_deg)
            helical_rad = np.radians(st.local_azimuth_offset_deg)
            pts = _transform_section(loop[:-1], twist_rad, helical_rad, R)
            # z (height) placed at the station midpoint; consecutive stations
            # are joined at their shared boundary below.
            loops_3d.append(pts)
            z_levels.append((st.z_start_m, st.z_end_m))

        # Side walls: stitch each pair of adjacent station loops. To keep the
        # root/tip faces flat and the mesh watertight, each station's loop is
        # duplicated at its z_start and z_end (a small "stack of pitched
        # prisms" loft -- simple, robust, and exactly reduces to the straight
        # extrusion when twist/helical are both zero).
        for si, st in enumerate(stations):
            z0, z1 = z_levels[si]
            loop3d = loops_3d[si]
            for i in range(n):
                x1, y1, zz1 = loop3d[i]
                x2, y2, zz2 = loop3d[(i + 1) % n]
                v1 = (x1, y1, z0)
                v2 = (x2, y2, z0)
                v3 = (x2, y2, z1)
                v4 = (x1, y1, z1)
                facets.append(_facet(v1, v2, v3))
                facets.append(_facet(v1, v3, v4))

        # Connect consecutive stations to each other (small step face at each
        # station boundary, since each station is pitched/offset slightly
        # differently from its neighbour).
        for si in range(len(stations) - 1):
            _, z_end_prev = z_levels[si]
            z_start_next, _ = z_levels[si + 1]
            loop_prev = loops_3d[si]
            loop_next = loops_3d[si + 1]
            for i in range(n):
                x1, y1, _ = loop_prev[i]
                x2, y2, _ = loop_prev[(i + 1) % n]
                x3, y3, _ = loop_next[(i + 1) % n]
                x4, y4, _ = loop_next[i]
                v1 = (x1, y1, z_end_prev)
                v2 = (x2, y2, z_end_prev)
                v3 = (x3, y3, z_start_next)
                v4 = (x4, y4, z_start_next)
                facets.append(_facet(v1, v2, v3))
                facets.append(_facet(v1, v3, v4))

        root_loop = [(x, y, z_levels[0][0]) for x, y, _ in loops_3d[0]]
        tip_loop = [(x, y, z_levels[-1][1]) for x, y, _ in loops_3d[-1]]

    # Simple fan triangulation for the root and tip caps, from the loop
    # centroid. A true NACA section is non-convex enough that this is only
    # adequate for thin symmetric sections at reasonable panel counts -- a
    # documented simplification a real meshing pass should redo with proper
    # 2D triangulation (e.g. ear-clipping) for thicker sections.
    def _cap(loop_pts, flip: bool):
        cx = sum(p[0] for p in loop_pts) / len(loop_pts)
        cy = sum(p[1] for p in loop_pts) / len(loop_pts)
        cz = loop_pts[0][2]
        out = []
        for i in range(len(loop_pts)):
            p1 = loop_pts[i]
            p2 = loop_pts[(i + 1) % len(loop_pts)]
            if flip:
                out.append(_facet((cx, cy, cz), p2, p1))
            else:
                out.append(_facet((cx, cy, cz), p1, p2))
        return out

    facets.extend(_cap(root_loop, flip=True))
    facets.extend(_cap(tip_loop, flip=False))

    header = f"solid {solid_name}\n"
    footer = f"endsolid {solid_name}\n"
    return header + "".join(facets) + footer