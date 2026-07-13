"""
Phase 14 report data assembler. Runs the platform's own pipeline (Stages
1-8) for a given design and packages the results into one structured
dataclass, which every report format (DOCX/XLSX/PDF/CSV) renders from --
so the numbers in a PDF report and an Excel export of the same design are
guaranteed to match (they come from the same analysis run, not two
separate code paths that could drift apart).
"""
from __future__ import annotations
from dataclasses import dataclass, field

from app.geometry.models import HybridRotorGeometry
from app.aero.hybrid_solver import cp_lambda_curve
from app.structural.blade_analysis import analyze_blade_structure
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material
from app.composites.optimizer import compare_materials
from app.fatigue.fatigue_analysis import analyze_blade_fatigue
from app.aeroelastic.blade_aeroelastic_analysis import analyze_blade_aeroelastics
from app.economics.economic_analysis import analyze_economics


@dataclass
class ReportData:
    geometry: HybridRotorGeometry
    material_key: str
    ply_material_key: str
    wind_speed_ms: float
    operating_tsr: float

    cp_lambda_points: list = field(default_factory=list)
    peak_cp: float = 0.0
    peak_cp_tsr: float = 0.0

    structural_safety_factor: float = 0.0
    structural_max_stress_pa: float = 0.0
    structural_max_deflection_m: float = 0.0
    spar_mass_kg: float = 0.0

    composite_cfrp_mass_kg: float = 0.0
    composite_gfrp_mass_kg: float = 0.0
    composite_cfrp_feasible: bool = False
    composite_gfrp_feasible: bool = False

    fatigue_life_years: float = 0.0
    fatigue_cycles_per_year: float = 0.0

    natural_frequencies_hz: list = field(default_factory=list)
    resonance_risks_count: int = 0

    aep_kwh: float = 0.0
    capacity_factor: float = 0.0
    total_capex_usd: float = 0.0
    lcoe_usd_per_kwh: float = 0.0
    npv_usd: float = 0.0
    irr: float | None = None
    payback_years: float = 0.0

    warnings: list = field(default_factory=list)


def assemble_report_data(
    geom: HybridRotorGeometry,
    material_key: str = "CFRP_UD",
    ply_material_key: str = "CFRP_UD_PLY",
    wind_speed_ms: float | None = None,
    operating_tsr: float = 2.25,
) -> ReportData:
    wind_speed_ms = wind_speed_ms or geom.rated_wind_speed_ms
    all_warnings: list[str] = []

    cp_points = cp_lambda_curve(geom, wind_speed_ms, tsr_min=0.5, tsr_max=4.5, n_points=20)
    peak = max(cp_points, key=lambda p: p.system_cp)

    struct = analyze_blade_structure(
        geom, material_key, wind_speed_ms, operating_tsr,
        spar_width_fraction=0.5, spar_wall_thickness_m=0.003,
    )
    all_warnings += struct.warnings

    composite_results = compare_materials(geom, wind_speed_ms, operating_tsr, target_safety_factor=1.5)
    cfrp, gfrp = composite_results["CFRP_UD_PLY"], composite_results["GFRP_UD_PLY"]

    mat = get_material(material_key)
    spar = spar_from_blade_geometry(geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, 0.5, 0.003)
    fatigue = analyze_blade_fatigue(
        geom, ei_flapwise=mat.youngs_modulus_pa * spar.i_flapwise_m4,
        section_i_m4=spar.i_flapwise_m4, section_c_m=spar.c_flapwise_m,
        static_strength_pa=mat.yield_strength_pa, ply_material_key=ply_material_key,
        operating_tsr=operating_tsr,
    )
    all_warnings += fatigue.warnings

    aeroelastic = analyze_blade_aeroelastics(
        geom, ei_flapwise=mat.youngs_modulus_pa * spar.i_flapwise_m4,
        mass_per_length_kg_m=spar.area_m2 * mat.density_kg_m3, operating_tsr=operating_tsr,
    )
    all_warnings += aeroelastic.warnings

    econ = analyze_economics(geom, spar_mass_kg=struct.spar_mass_kg, ply_material_key=ply_material_key)
    all_warnings += econ.warnings

    return ReportData(
        geometry=geom, material_key=material_key, ply_material_key=ply_material_key,
        wind_speed_ms=wind_speed_ms, operating_tsr=operating_tsr,
        cp_lambda_points=cp_points, peak_cp=peak.system_cp, peak_cp_tsr=peak.tip_speed_ratio,
        structural_safety_factor=struct.safety_factor,
        structural_max_stress_pa=struct.combined_max_stress_pa,
        structural_max_deflection_m=struct.flapwise.max_deflection_m,
        spar_mass_kg=struct.spar_mass_kg,
        composite_cfrp_mass_kg=cfrp.result.spar_mass_kg, composite_gfrp_mass_kg=gfrp.result.spar_mass_kg,
        composite_cfrp_feasible=cfrp.feasible, composite_gfrp_feasible=gfrp.feasible,
        fatigue_life_years=min(fatigue.estimated_life_years, 1e6),
        fatigue_cycles_per_year=fatigue.total_cycles_per_year,
        natural_frequencies_hz=aeroelastic.modal.natural_frequencies_hz,
        resonance_risks_count=len(aeroelastic.campbell.resonance_risks),
        aep_kwh=econ.aep.aep_kwh, capacity_factor=econ.aep.capacity_factor,
        total_capex_usd=econ.capex.total_capex_usd, lcoe_usd_per_kwh=econ.lcoe_usd_per_kwh,
        npv_usd=econ.npv_usd, irr=econ.irr, payback_years=econ.simple_payback_years,
        warnings=all_warnings,
    )
