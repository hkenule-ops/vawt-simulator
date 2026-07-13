"""
Material property library for Stage-1 structural sizing.

These are isotropic-equivalent properties -- good enough for first-pass beam
FEA and safety-factor checks on the blade spar. Real anisotropic composite
layup behaviour (fibre orientation, ply stacking, laminate theory) is Phase 8
("Composites") territory; this module deliberately stays isotropic so the FEA
solver here has a single, unambiguous set of engineering constants to work
with, and can be swapped for a full laminate stiffness matrix later without
changing the beam solver itself.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Material:
    name: str
    density_kg_m3: float
    youngs_modulus_pa: float
    shear_modulus_pa: float
    yield_strength_pa: float
    ultimate_strength_pa: float


MATERIAL_LIBRARY: dict[str, Material] = {
    "CFRP_UD": Material(
        name="Carbon Fibre Reinforced Polymer (unidirectional, isotropic-equivalent)",
        density_kg_m3=1600.0,
        youngs_modulus_pa=135e9,
        shear_modulus_pa=5e9,
        yield_strength_pa=1500e6,   # tensile strength used as the practical limit (no distinct yield for CFRP)
        ultimate_strength_pa=1500e6,
    ),
    "GFRP_UD": Material(
        name="Glass Fibre Reinforced Polymer (unidirectional, isotropic-equivalent)",
        density_kg_m3=1900.0,
        youngs_modulus_pa=40e9,
        shear_modulus_pa=4e9,
        yield_strength_pa=800e6,
        ultimate_strength_pa=800e6,
    ),
    "AL_6061_T6": Material(
        name="Aluminium 6061-T6",
        density_kg_m3=2700.0,
        youngs_modulus_pa=68.9e9,
        shear_modulus_pa=26e9,
        yield_strength_pa=276e6,
        ultimate_strength_pa=310e6,
    ),
    "AISI_304_Stainless": Material(
        name="AISI 304 Stainless Steel",
        density_kg_m3=8000.0,
        youngs_modulus_pa=193e9,
        shear_modulus_pa=75e9,
        yield_strength_pa=215e6,
        ultimate_strength_pa=505e6,
    ),
}


def get_material(name: str) -> Material:
    if name not in MATERIAL_LIBRARY:
        raise ValueError(f"Unknown material '{name}'. Available: {list(MATERIAL_LIBRARY)}")
    return MATERIAL_LIBRARY[name]
