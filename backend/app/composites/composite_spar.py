"""
Composite box-spar structural model.

Unlike the isotropic spar in app/structural/cross_section.py (Phase 7, one
material throughout), a real composite spar uses different layups for
different parts: spar caps (top/bottom flanges) are fibre-dominated
(mostly 0-degree plies) because they carry the bending load at maximum
distance from the neutral axis; shear webs (left/right sides) are usually
angle-ply dominated (+/-45) because they primarily carry shear. This module
combines the two via transformed-section composite beam theory: since axial
strain is continuous across the section but the modulus differs by part,
stiffness contributions are weighted by each part's own effective modulus
(a weighted parallel-axis-theorem sum), and stress at each part's outer
fibre uses that part's own modulus, not a single section-wide value.

Bending moment along the beam is statically determinate for the
pinned-pinned/cantilever uniform-load case (Phase 7's beam_fem.py), so the
moment diagram doesn't depend on material -- only curvature and stress do.
This module reuses solve_beam_udl purely for the moment diagram and
re-derives deflection/stress itself using the composite EI and per-part
moduli.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.composites.laminate import Ply, analyze_laminate, LaminateResult
from app.composites.lamina import PlyMaterial


@dataclass
class CompositeSparDesign:
    outer_width_m: float     # B: chordwise extent
    outer_height_m: float    # H: thickness-wise extent
    cap_laminate: LaminateResult   # top/bottom flanges
    web_laminate: LaminateResult   # left/right shear webs

    @property
    def cap_thickness_m(self) -> float:
        return self.cap_laminate.total_thickness_m

    @property
    def web_thickness_m(self) -> float:
        return self.web_laminate.total_thickness_m

    @property
    def web_height_m(self) -> float:
        return max(self.outer_height_m - 2 * self.cap_thickness_m, 1e-6)

    @property
    def mass_per_span_kg_m(self) -> float:
        cap_area = 2 * self.outer_width_m * self.cap_thickness_m
        web_area = 2 * self.web_height_m * self.web_thickness_m
        return cap_area * self.cap_laminate.density_kg_m3 + web_area * self.web_laminate.density_kg_m3

    @property
    def ei_flapwise(self) -> float:
        """Composite bending stiffness resisting flapwise (H-direction) deflection."""
        E_cap = self.cap_laminate.ex_flexural_pa
        E_web = self.web_laminate.ex_flexural_pa
        B, t_cap = self.outer_width_m, self.cap_thickness_m
        H_web, t_web = self.web_height_m, self.web_thickness_m
        d_cap = self.outer_height_m / 2 - t_cap / 2

        i_cap_own = B * t_cap ** 3 / 12
        a_cap = B * t_cap
        i_cap_total = 2 * (i_cap_own + a_cap * d_cap ** 2)

        i_web_own = t_web * H_web ** 3 / 12  # web centroid is on the neutral axis for flapwise bending
        i_web_total = 2 * i_web_own

        return E_cap * i_cap_total + E_web * i_web_total

    @property
    def ei_edgewise(self) -> float:
        """Composite bending stiffness resisting edgewise (B-direction) deflection."""
        E_cap = self.cap_laminate.ex_flexural_pa
        E_web = self.web_laminate.ex_flexural_pa
        B, t_cap = self.outer_width_m, self.cap_thickness_m
        H_web, t_web = self.web_height_m, self.web_thickness_m
        d_web = self.outer_width_m / 2 - t_web / 2

        i_cap_own = t_cap * B ** 3 / 12  # cap centroid is on the neutral axis for edgewise bending
        i_cap_total = 2 * i_cap_own

        i_web_own = H_web * t_web ** 3 / 12
        a_web = H_web * t_web
        i_web_total = 2 * (i_web_own + a_web * d_web ** 2)

        return E_cap * i_cap_total + E_web * i_web_total

    def max_stress_pa(self, bending_moment_nm: float, plane: str) -> float:
        """
        Peak bending stress at the outer fibre, using each part's own modulus
        (transformed-section theory: strain is continuous, stress = E*curvature*distance).
        """
        if plane == "flapwise":
            EI = self.ei_flapwise
            curvature = bending_moment_nm / EI if EI > 0 else 0.0
            c = self.outer_height_m / 2
            return abs(self.cap_laminate.ex_flexural_pa * curvature * c)
        elif plane == "edgewise":
            EI = self.ei_edgewise
            curvature = bending_moment_nm / EI if EI > 0 else 0.0
            c = self.outer_width_m / 2
            return abs(self.web_laminate.ex_flexural_pa * curvature * c)
        else:
            raise ValueError("plane must be 'flapwise' or 'edgewise'")


def build_uniform_angle_laminate(ply_material: PlyMaterial, angle_deg: float, n_plies: int) -> LaminateResult:
    """Convenience: a laminate of n plies all at the same angle (e.g. spar cap [0]_n)."""
    return analyze_laminate([Ply(ply_material, angle_deg) for _ in range(n_plies)])


def build_symmetric_angle_ply_laminate(ply_material: PlyMaterial, angle_deg: float, n_pairs: int) -> LaminateResult:
    """Convenience: a symmetric +/-angle laminate (e.g. shear web [+45/-45]_ns), B=0 by construction."""
    plies = []
    for _ in range(n_pairs):
        plies.append(Ply(ply_material, angle_deg))
        plies.append(Ply(ply_material, -angle_deg))
    plies = plies + plies[::-1]  # mirror for symmetry
    return analyze_laminate(plies)
