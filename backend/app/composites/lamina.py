"""
Unidirectional lamina (ply) properties for Classical Laminate Theory.

Unlike the isotropic-equivalent materials in app/structural/materials.py
(used for Phase 7's quick sizing pass), these are real orthotropic single-ply
properties -- fibre-direction modulus E1, transverse modulus E2, in-plane
shear modulus G12, and major Poisson's ratio v12 -- the actual inputs CLT
needs to predict how a stack of plies at different angles behaves.

Typical values for standard UD carbon/epoxy and E-glass/epoxy prepreg,
representative of commonly published data (e.g. Hexcel/Toray datasheets,
Gay "Composite Materials" reference tables).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class PlyMaterial:
    name: str
    e1_pa: float          # fibre-direction modulus
    e2_pa: float          # transverse modulus
    g12_pa: float         # in-plane shear modulus
    v12: float            # major Poisson's ratio
    density_kg_m3: float
    tensile_strength_1_pa: float   # fibre-direction tensile strength (0 deg)
    default_ply_thickness_m: float = 0.000125  # 0.125mm, typical cured UD ply

    @property
    def v21(self) -> float:
        """Minor Poisson's ratio, from the reciprocal relation v21/E2 = v12/E1."""
        return self.v12 * self.e2_pa / self.e1_pa


PLY_LIBRARY: dict[str, PlyMaterial] = {
    "CFRP_UD_PLY": PlyMaterial(
        name="Carbon/Epoxy UD Prepreg",
        e1_pa=135e9, e2_pa=10e9, g12_pa=5e9, v12=0.30,
        density_kg_m3=1600.0, tensile_strength_1_pa=1500e6,
    ),
    "GFRP_UD_PLY": PlyMaterial(
        name="E-Glass/Epoxy UD Prepreg",
        e1_pa=40e9, e2_pa=8e9, g12_pa=4e9, v12=0.26,
        density_kg_m3=1900.0, tensile_strength_1_pa=800e6,
    ),
}


def get_ply(name: str) -> PlyMaterial:
    if name not in PLY_LIBRARY:
        raise ValueError(f"Unknown ply material '{name}'. Available: {list(PLY_LIBRARY)}")
    return PLY_LIBRARY[name]
