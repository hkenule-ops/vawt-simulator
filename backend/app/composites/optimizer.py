"""
Phase 8 optimizer: grid search over spar cap ply count, shear web ply count,
and spar width fraction, to find the minimum-mass design meeting a target
safety factor -- run separately for carbon and glass fibre so the two can be
directly compared (mass, cost-relevant ply count, safety margin).

This is a grid search, not a genetic/gradient optimiser (that's Phase 12,
"multi-objective optimisation," operating across the whole rotor design
space with competing objectives). Here the objective is single (minimise
spar mass) with one hard constraint (safety factor >= target), and the
design space is small and cheap enough per evaluation (each point is one
beam FEM solve) that an exhaustive grid is both simpler to verify correct
and fast enough in practice.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.geometry.models import HybridRotorGeometry
from app.aero.darrieus_bem import compute_blade_spanwise_loads
from app.composites.lamina import PlyMaterial, get_ply
from app.composites.composite_spar import (
    CompositeSparDesign, build_uniform_angle_laminate, build_symmetric_angle_ply_laminate,
)
from app.composites.blade_composite_analysis import analyze_composite_blade, CompositeBladeResult


@dataclass
class OptimizedSparDesign:
    material_key: str
    n_cap_plies: int
    n_web_pairs: int
    spar_width_fraction: float
    result: CompositeBladeResult
    feasible: bool


def _build_spar(
    geom: HybridRotorGeometry, ply_material: PlyMaterial,
    n_cap_plies: int, n_web_pairs: int, spar_width_fraction: float,
) -> CompositeSparDesign:
    d = geom.darrieus
    outer_width = spar_width_fraction * d.chord_m
    outer_height = d.blade_thickness_ratio * d.chord_m * 0.85

    cap_laminate = build_uniform_angle_laminate(ply_material, 0.0, n_cap_plies)
    web_laminate = build_symmetric_angle_ply_laminate(ply_material, 45.0, n_web_pairs)

    return CompositeSparDesign(
        outer_width_m=outer_width, outer_height_m=outer_height,
        cap_laminate=cap_laminate, web_laminate=web_laminate,
    )


def optimize_spar_layup(
    geom: HybridRotorGeometry,
    material_key: str,
    wind_speed_ms: float,
    tip_speed_ratio: float,
    target_safety_factor: float = 1.5,
    cap_ply_range: range = range(4, 25, 2),
    web_pair_range: range = range(1, 6),
    spar_width_fractions: tuple[float, ...] = (0.3, 0.45, 0.6),
    boundary: str = "pinned-pinned",
) -> OptimizedSparDesign:
    """
    Exhaustively evaluates the grid and returns the lowest-mass design that
    meets the safety factor target. If none meet the target, returns the
    highest-safety-factor design found (flagged infeasible) so the caller
    still gets useful information instead of nothing.
    """
    ply_material = get_ply(material_key)
    # Aero loads depend only on the aerodynamic geometry and operating point,
    # not on spar design -- compute once and reuse across the whole grid
    # instead of re-running the BEM azimuthal sweep at every candidate
    # (this cut a ~13s grid search down to under a second).
    aero_loads = compute_blade_spanwise_loads(geom.darrieus, wind_speed_ms, tip_speed_ratio)

    best_feasible: OptimizedSparDesign | None = None
    best_infeasible: OptimizedSparDesign | None = None

    for width_frac in spar_width_fractions:
        for n_cap in cap_ply_range:
            for n_web in web_pair_range:
                spar = _build_spar(geom, ply_material, n_cap, n_web, width_frac)
                result = analyze_composite_blade(
                    geom, spar, ply_material, wind_speed_ms, tip_speed_ratio,
                    boundary=boundary, aero_loads=aero_loads,
                )
                candidate = OptimizedSparDesign(
                    material_key=material_key, n_cap_plies=n_cap, n_web_pairs=n_web,
                    spar_width_fraction=width_frac, result=result,
                    feasible=bool(result.safety_factor >= target_safety_factor),
                )
                if candidate.feasible:
                    if best_feasible is None or result.spar_mass_kg < best_feasible.result.spar_mass_kg:
                        best_feasible = candidate
                else:
                    if best_infeasible is None or result.safety_factor > best_infeasible.result.safety_factor:
                        best_infeasible = candidate

    return best_feasible if best_feasible is not None else best_infeasible


def compare_materials(
    geom: HybridRotorGeometry,
    wind_speed_ms: float,
    tip_speed_ratio: float,
    target_safety_factor: float = 1.5,
    boundary: str = "pinned-pinned",
) -> dict[str, OptimizedSparDesign]:
    """Runs the optimizer for both CFRP and GFRP so they can be compared directly."""
    return {
        "CFRP_UD_PLY": optimize_spar_layup(geom, "CFRP_UD_PLY", wind_speed_ms, tip_speed_ratio, target_safety_factor, boundary=boundary),
        "GFRP_UD_PLY": optimize_spar_layup(geom, "GFRP_UD_PLY", wind_speed_ms, tip_speed_ratio, target_safety_factor, boundary=boundary),
    }
