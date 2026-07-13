"""
Simplified blade spar cross-section: a rectangular hollow box spar embedded
in the blade profile (the standard load-carrying member in a real Darrieus
blade -- the outer aerodynamic shell carries comparatively little bending
load and is not modelled structurally here). Spar width is sized as a
fraction of chord, spar height as a fraction of the airfoil's max thickness,
both configurable.

This is a deliberate simplification flagged as such: real spar cap sizing
(carbon vs glass, ply schedule, shear web placement) is Phase 8 territory.
What this module gives Phase 7 is a single, well-defined I and A so the beam
FEM solver has real numbers to work with instead of a placeholder.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SparCrossSection:
    outer_width_m: float     # chordwise extent (B)
    outer_height_m: float    # thickness-wise extent (H)
    wall_thickness_m: float

    @property
    def inner_width_m(self) -> float:
        return max(self.outer_width_m - 2 * self.wall_thickness_m, 1e-6)

    @property
    def inner_height_m(self) -> float:
        return max(self.outer_height_m - 2 * self.wall_thickness_m, 1e-6)

    @property
    def area_m2(self) -> float:
        return self.outer_width_m * self.outer_height_m - self.inner_width_m * self.inner_height_m

    @property
    def i_flapwise_m4(self) -> float:
        """Second moment of area about the chordwise axis (resists flapwise/normal-direction bending)."""
        B, H = self.outer_width_m, self.outer_height_m
        b, h = self.inner_width_m, self.inner_height_m
        return (B * H ** 3 - b * h ** 3) / 12.0

    @property
    def i_edgewise_m4(self) -> float:
        """Second moment of area about the thickness axis (resists edgewise/tangential-direction bending)."""
        B, H = self.outer_width_m, self.outer_height_m
        b, h = self.inner_width_m, self.inner_height_m
        return (H * B ** 3 - h * b ** 3) / 12.0

    @property
    def c_flapwise_m(self) -> float:
        return self.outer_height_m / 2.0

    @property
    def c_edgewise_m(self) -> float:
        return self.outer_width_m / 2.0


def spar_from_blade_geometry(
    chord_m: float, thickness_ratio: float,
    spar_width_fraction: float = 0.5, wall_thickness_m: float = 0.003,
) -> SparCrossSection:
    """Size a spar box as a fraction of chord (width) and max airfoil thickness (height)."""
    outer_width = spar_width_fraction * chord_m
    outer_height = thickness_ratio * chord_m * 0.85  # leave a small margin inside the airfoil skin
    return SparCrossSection(
        outer_width_m=outer_width, outer_height_m=outer_height, wall_thickness_m=wall_thickness_m,
    )
