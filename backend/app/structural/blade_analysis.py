"""
Phase 7 top-level structural analysis: takes a rotor design and an operating
point, derives the flapwise and edgewise design loads (aerodynamic peak
loads from the Stage-1 BEM solver, plus centrifugal loading), runs each
through the beam FEA solver, and reports combined stress, deflection, and
safety factor.

Scope and honesty notes:
- Flapwise and edgewise bending are solved as two independent 1D beam
  problems and combined by direct stress superposition at the same section
  (conservative -- ignores any coupling/torsion between the two planes,
  which a full 3D beam or shell FEA would capture). This is a standard
  first-pass simplification in early-stage VAWT blade sizing.
- Centrifugal load direction: for a straight blade parallel to the rotation
  axis at fixed radius R, centrifugal force is radially outward, i.e. in the
  same plane as the aerodynamic normal force, so it's added into the
  flapwise (not edgewise) load case.
- Buckling is checked as a secondary output using the blade's own weight as
  a conservative nominal axial load; real axial loading depends on strut
  geometry (angle, attachment point), which isn't modelled yet -- flagged
  in the result, not silently assumed away.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.geometry.models import HybridRotorGeometry
from app.aero.darrieus_bem import compute_blade_spanwise_loads
from app.structural.materials import get_material, Material
from app.structural.cross_section import spar_from_blade_geometry, SparCrossSection
from app.structural.beam_fem import solve_beam_udl, BeamFEAResult
from app.structural.buckling import euler_critical_buckling_load

G = 9.81


@dataclass
class BladeStructuralResult:
    material: str
    spar_area_m2: float
    spar_mass_kg: float
    flapwise_distributed_load_n_m: float
    edgewise_distributed_load_n_m: float
    centrifugal_distributed_load_n_m: float
    flapwise: BeamFEAResult
    edgewise: BeamFEAResult
    max_flapwise_stress_pa: float
    max_edgewise_stress_pa: float
    combined_max_stress_pa: float
    yield_strength_pa: float
    safety_factor: float
    euler_buckling_load_n: float
    nominal_axial_load_n: float
    buckling_safety_factor: float
    warnings: list[str]


def analyze_blade_structure(
    geom: HybridRotorGeometry,
    material_name: str,
    wind_speed_ms: float,
    tip_speed_ratio: float,
    spar_width_fraction: float = 0.5,
    spar_wall_thickness_m: float = 0.003,
    boundary: str = "pinned-pinned",
    n_elements: int = 40,
) -> BladeStructuralResult:
    material = get_material(material_name)
    d = geom.darrieus
    spar = spar_from_blade_geometry(d.chord_m, d.blade_thickness_ratio, spar_width_fraction, spar_wall_thickness_m)

    spar_mass = spar.area_m2 * d.blade_height_m * material.density_kg_m3
    mass_per_span = spar.area_m2 * material.density_kg_m3

    omega = tip_speed_ratio * wind_speed_ms / d.rotor_radius_m
    centrifugal_per_span = mass_per_span * omega ** 2 * d.rotor_radius_m

    aero_loads = compute_blade_spanwise_loads(d, wind_speed_ms, tip_speed_ratio)

    flapwise_load = aero_loads.peak_normal_force_per_span_n_m + centrifugal_per_span
    edgewise_load = aero_loads.peak_tangential_force_per_span_n_m

    EI_flap = material.youngs_modulus_pa * spar.i_flapwise_m4
    EI_edge = material.youngs_modulus_pa * spar.i_edgewise_m4

    flap_result = solve_beam_udl(
        d.blade_height_m, EI_flap, flapwise_load, n_elements=n_elements, boundary=boundary,
        section_i_m4=spar.i_flapwise_m4, section_c_m=spar.c_flapwise_m,
    )
    edge_result = solve_beam_udl(
        d.blade_height_m, EI_edge, edgewise_load, n_elements=n_elements, boundary=boundary,
        section_i_m4=spar.i_edgewise_m4, section_c_m=spar.c_edgewise_m,
    )

    combined_stress = flap_result.max_bending_stress_pa + edge_result.max_bending_stress_pa
    safety_factor = material.yield_strength_pa / combined_stress if combined_stress > 0 else float("inf")

    nominal_axial_load = spar_mass * G  # conservative placeholder; see module docstring
    euler_load = euler_critical_buckling_load(EI_flap, d.blade_height_m, end_condition=boundary)
    buckling_sf = euler_load / nominal_axial_load if nominal_axial_load > 0 else float("inf")

    warnings = []
    if safety_factor < 1.5:
        warnings.append(
            f"Safety factor {safety_factor:.2f} is below the common 1.5 minimum design "
            f"threshold for composite wind turbine blades -- increase spar size or change material."
        )
    if spar.outer_height_m <= 2 * spar_wall_thickness_m:
        warnings.append(
            "Spar wall thickness leaves little to no hollow core -- effectively a solid "
            "section; check spar sizing inputs."
        )
    warnings.append(
        "Buckling check uses blade self-weight as a nominal axial load, not strut-derived "
        "axial loading -- treat as a secondary indicator, not a certified buckling check."
    )

    return BladeStructuralResult(
        material=material.name,
        spar_area_m2=spar.area_m2,
        spar_mass_kg=spar_mass,
        flapwise_distributed_load_n_m=flapwise_load,
        edgewise_distributed_load_n_m=edgewise_load,
        centrifugal_distributed_load_n_m=centrifugal_per_span,
        flapwise=flap_result,
        edgewise=edge_result,
        max_flapwise_stress_pa=flap_result.max_bending_stress_pa,
        max_edgewise_stress_pa=edge_result.max_bending_stress_pa,
        combined_max_stress_pa=combined_stress,
        yield_strength_pa=material.yield_strength_pa,
        safety_factor=safety_factor,
        euler_buckling_load_n=euler_load,
        nominal_axial_load_n=nominal_axial_load,
        buckling_safety_factor=buckling_sf,
        warnings=warnings,
    )
