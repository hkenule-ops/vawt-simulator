"""
Classical Laminate Theory (CLT) solver.

Given a stacking sequence (list of plies, each with a fibre angle and
thickness), computes the laminate extensional (A), coupling (B), and
bending (D) stiffness matrices, then derives effective engineering
constants (Ex, Ey, Gxy for in-plane loading; Ex_flexural for bending) that
the beam FEM (Phase 7) can use in place of a single isotropic modulus.

Standard reference formulation (e.g. Jones, "Mechanics of Composite
Materials"; Gay, "Composite Materials: Design and Applications"). Validated
in tests/test_composites.py against known closed-form special cases:
  - all-0-degree layup reduces to Ex=E1, Ey=E2 exactly
  - all-90-degree layup reduces to Ex=E2, Ey=E1 exactly
  - a symmetric layup has B=0 (no extension-bending coupling)
  - a quasi-isotropic layup gives Ex=Ey (a well-known CLT result)
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np

from app.composites.lamina import PlyMaterial


@dataclass
class Ply:
    material: PlyMaterial
    angle_deg: float
    thickness_m: float | None = None  # falls back to material.default_ply_thickness_m

    @property
    def t(self) -> float:
        return self.thickness_m if self.thickness_m is not None else self.material.default_ply_thickness_m


def _reduced_stiffness(mat: PlyMaterial) -> np.ndarray:
    """3x3 reduced stiffness matrix Q in material (1-2) axes, plane stress."""
    v12, v21 = mat.v12, mat.v21
    denom = 1 - v12 * v21
    Q11 = mat.e1_pa / denom
    Q22 = mat.e2_pa / denom
    Q12 = v12 * mat.e2_pa / denom
    Q66 = mat.g12_pa
    return np.array([[Q11, Q12, 0], [Q12, Q22, 0], [0, 0, Q66]])


def _transformed_stiffness(Q: np.ndarray, angle_deg: float) -> np.ndarray:
    """Transform Q from material axes to laminate (x-y) axes at the given ply angle."""
    th = math.radians(angle_deg)
    c, s = math.cos(th), math.sin(th)
    Q11, Q12, Q22, Q66 = Q[0, 0], Q[0, 1], Q[1, 1], Q[2, 2]

    Qbar11 = Q11 * c**4 + 2 * (Q12 + 2 * Q66) * s**2 * c**2 + Q22 * s**4
    Qbar22 = Q11 * s**4 + 2 * (Q12 + 2 * Q66) * s**2 * c**2 + Q22 * c**4
    Qbar12 = (Q11 + Q22 - 4 * Q66) * s**2 * c**2 + Q12 * (s**4 + c**4)
    Qbar66 = (Q11 + Q22 - 2 * Q12 - 2 * Q66) * s**2 * c**2 + Q66 * (s**4 + c**4)
    Qbar16 = (Q11 - Q12 - 2 * Q66) * s * c**3 + (Q12 - Q22 + 2 * Q66) * s**3 * c
    Qbar26 = (Q11 - Q12 - 2 * Q66) * s**3 * c + (Q12 - Q22 + 2 * Q66) * s * c**3

    return np.array([
        [Qbar11, Qbar12, Qbar16],
        [Qbar12, Qbar22, Qbar26],
        [Qbar16, Qbar26, Qbar66],
    ])


@dataclass
class LaminateResult:
    total_thickness_m: float
    A: list[list[float]]
    B: list[list[float]]
    D: list[list[float]]
    ex_pa: float             # effective in-plane (extensional) modulus, x-direction
    ey_pa: float
    gxy_pa: float
    ex_flexural_pa: float    # effective bending modulus, x-direction (from D matrix)
    density_kg_m3: float     # thickness-weighted average
    mass_per_area_kg_m2: float
    max_b_matrix_term: float  # diagnostic: how close to zero the coupling terms are


def analyze_laminate(plies: list[Ply]) -> LaminateResult:
    if not plies:
        raise ValueError("Laminate must have at least one ply")

    total_t = sum(p.t for p in plies)
    z0 = -total_t / 2
    z_bounds = [z0]
    for p in plies:
        z_bounds.append(z_bounds[-1] + p.t)

    A = np.zeros((3, 3))
    B = np.zeros((3, 3))
    D = np.zeros((3, 3))
    mass_per_area = 0.0

    for i, p in enumerate(plies):
        Q = _reduced_stiffness(p.material)
        Qbar = _transformed_stiffness(Q, p.angle_deg)
        z_k, z_km1 = z_bounds[i + 1], z_bounds[i]
        A += Qbar * (z_k - z_km1)
        B += Qbar * (z_k ** 2 - z_km1 ** 2) / 2
        D += Qbar * (z_k ** 3 - z_km1 ** 3) / 3
        mass_per_area += p.material.density_kg_m3 * p.t

    a = np.linalg.inv(A)
    ex = 1.0 / (total_t * a[0, 0])
    ey = 1.0 / (total_t * a[1, 1])
    gxy = 1.0 / (total_t * a[2, 2])

    try:
        d = np.linalg.inv(D)
        ex_flexural = 12.0 / (total_t ** 3 * d[0, 0])
    except np.linalg.LinAlgError:
        ex_flexural = ex  # degenerate fallback for pathological single-ply cases

    avg_density = mass_per_area / total_t

    return LaminateResult(
        total_thickness_m=total_t,
        A=A.tolist(), B=B.tolist(), D=D.tolist(),
        ex_pa=ex, ey_pa=ey, gxy_pa=gxy,
        ex_flexural_pa=ex_flexural,
        density_kg_m3=avg_density,
        mass_per_area_kg_m2=mass_per_area,
        max_b_matrix_term=float(np.max(np.abs(B))),
    )
