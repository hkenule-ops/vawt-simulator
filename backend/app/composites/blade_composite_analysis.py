"""
Composite version of Phase 7's blade_analysis.py: same load derivation
(peak aero loads from Stage-1 BEM + centrifugal), same beam moment diagram
(statically determinate, material-independent), but deflection and stress
now come from the composite transformed-section spar (app/composite_spar.py)
instead of a single isotropic modulus.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.geometry.models import HybridRotorGeometry
from app.aero.darrieus_bem import compute_blade_spanwise_loads, BladeSpanwiseLoads
from app.structural.beam_fem import solve_beam_udl
from app.structural.buckling import euler_critical_buckling_load
from app.composites.composite_spar import CompositeSparDesign
from app.composites.lamina import PlyMaterial

G = 9.81


@dataclass
class CompositeBladeResult:
    spar_mass_kg: float
    cap_thickness_m: float
    web_thickness_m: float
    flapwise_distributed_load_n_m: float
    edgewise_distributed_load_n_m: float
    centrifugal_distributed_load_n_m: float
    max_flapwise_deflection_m: float
    max_edgewise_deflection_m: float
    max_flapwise_stress_pa: float
    max_edgewise_stress_pa: float
    combined_max_stress_pa: float
    strength_limit_pa: float
    safety_factor: float
    euler_buckling_load_n: float
    nominal_axial_load_n: float
    buckling_safety_factor: float
    warnings: list[str]


def analyze_composite_blade(
    geom: HybridRotorGeometry,
    spar: CompositeSparDesign,
    cap_ply_material: PlyMaterial,
    wind_speed_ms: float,
    tip_speed_ratio: float,
    boundary: str = "pinned-pinned",
    n_elements: int = 40,
    aero_loads: BladeSpanwiseLoads | None = None,
) -> CompositeBladeResult:
    d = geom.darrieus
    mass_per_span = spar.mass_per_span_kg_m
    spar_mass = mass_per_span * d.blade_height_m

    omega = tip_speed_ratio * wind_speed_ms / d.rotor_radius_m
    centrifugal_per_span = mass_per_span * omega ** 2 * d.rotor_radius_m

    if aero_loads is None:
        aero_loads = compute_blade_spanwise_loads(d, wind_speed_ms, tip_speed_ratio)
    flapwise_load = aero_loads.peak_normal_force_per_span_n_m + centrifugal_per_span
    edgewise_load = aero_loads.peak_tangential_force_per_span_n_m

    # Moment diagrams are statically determinate (independent of EI) for this
    # beam/BC/load combination, so we can reuse solve_beam_udl with the
    # composite EI purely to get a consistent deflection number, then
    # recompute stress ourselves via the composite (transformed-section)
    # formula rather than trusting solve_beam_udl's built-in M*c/I (which
    # assumes a single homogeneous modulus).
    flap_fem = solve_beam_udl(d.blade_height_m, spar.ei_flapwise, flapwise_load,
                               n_elements=n_elements, boundary=boundary)
    edge_fem = solve_beam_udl(d.blade_height_m, spar.ei_edgewise, edgewise_load,
                               n_elements=n_elements, boundary=boundary)

    max_flap_stress = spar.max_stress_pa(flap_fem.max_bending_moment_nm, "flapwise")
    max_edge_stress = spar.max_stress_pa(edge_fem.max_bending_moment_nm, "edgewise")
    combined_stress = max_flap_stress + max_edge_stress

    strength_limit = cap_ply_material.tensile_strength_1_pa
    safety_factor = strength_limit / combined_stress if combined_stress > 0 else float("inf")

    nominal_axial_load = spar_mass * G
    euler_load = euler_critical_buckling_load(spar.ei_flapwise, d.blade_height_m, end_condition=boundary)
    buckling_sf = euler_load / nominal_axial_load if nominal_axial_load > 0 else float("inf")

    warnings = []
    if safety_factor < 1.5:
        warnings.append(
            f"Safety factor {safety_factor:.2f} is below the common 1.5 minimum design threshold."
        )
    warnings.append(
        "Strength check uses the 0-degree ply tensile strength as a simplified failure "
        "criterion, not a full first-ply-failure analysis (e.g. Tsai-Wu) across all ply "
        "angles and load combinations -- a documented simplification for this phase."
    )

    return CompositeBladeResult(
        spar_mass_kg=spar_mass,
        cap_thickness_m=spar.cap_thickness_m,
        web_thickness_m=spar.web_thickness_m,
        flapwise_distributed_load_n_m=flapwise_load,
        edgewise_distributed_load_n_m=edgewise_load,
        centrifugal_distributed_load_n_m=centrifugal_per_span,
        max_flapwise_deflection_m=flap_fem.max_deflection_m,
        max_edgewise_deflection_m=edge_fem.max_deflection_m,
        max_flapwise_stress_pa=max_flap_stress,
        max_edgewise_stress_pa=max_edge_stress,
        combined_max_stress_pa=combined_stress,
        strength_limit_pa=strength_limit,
        safety_factor=safety_factor,
        euler_buckling_load_n=euler_load,
        nominal_axial_load_n=nominal_axial_load,
        buckling_safety_factor=buckling_sf,
        warnings=warnings,
    )
