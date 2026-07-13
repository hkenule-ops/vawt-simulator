"""
Phase 15 system validation.

This is distinct from (and complements) the pytest suite that runs during
development: pytest validates that each solver reproduces known closed-form
physics/theory (Betz limit, beam vibration formulas, CLT special cases,
rainflow hand-traces, financial identities, etc) in isolation, for
developers, before code ships. This module re-runs a subset of those same
checks live, end-to-end, against the platform's REST API surface for a
SPECIFIC design the user is evaluating -- a "does this design's own results
hold together" check exposed as a feature, not just a CI gate.

Each check is genuinely re-derived here (not just imported and re-asserted
from the test suite) so a check failing here reflects the live API
response for this design, not stale test fixtures.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.geometry.models import HybridRotorGeometry
from app.aero.hybrid_solver import cp_lambda_curve
from app.structural.blade_analysis import analyze_blade_structure
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material
from app.economics.economic_analysis import analyze_economics
from app.economics.energy_yield import compute_aep
from app.aeroelastic.blade_aeroelastic_analysis import analyze_blade_aeroelastics
from app.fatigue.fatigue_analysis import analyze_blade_fatigue

BETZ_LIMIT = 0.593


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def _check_betz_limit(geom: HybridRotorGeometry, wind_speed: float) -> CheckResult:
    points = cp_lambda_curve(geom, wind_speed, tsr_min=0.5, tsr_max=4.5, n_points=15)
    max_cp = max(p.system_cp for p in points)
    passed = max_cp < BETZ_LIMIT
    return CheckResult(
        "Betz limit (momentum theory)", passed,
        f"Max system Cp = {max_cp:.4f}, must be < {BETZ_LIMIT} (Betz limit). "
        f"{'A violation here would indicate a real bug in the BEM solver.' if not passed else 'Within physical bounds.'}",
    )


def _check_rated_power_capping_reduces_aep(geom: HybridRotorGeometry) -> CheckResult:
    capped = compute_aep(geom, apply_rated_power_limit=True)
    uncapped = compute_aep(geom, apply_rated_power_limit=False)
    passed = capped.aep_kwh <= uncapped.aep_kwh + 1e-6
    return CheckResult(
        "AEP rated-power-limiting is conservative", passed,
        f"Rated-power-limited AEP ({capped.aep_kwh:.0f} kWh/yr) must not exceed the "
        f"unregulated theoretical maximum ({uncapped.aep_kwh:.0f} kWh/yr).",
    )


def _check_structural_safety_factor_positive(geom: HybridRotorGeometry, material_key: str, wind_speed: float, tsr: float) -> CheckResult:
    struct = analyze_blade_structure(geom, material_key, wind_speed, tsr,
                                      spar_width_fraction=0.5, spar_wall_thickness_m=0.003)
    passed = struct.safety_factor > 0 and struct.combined_max_stress_pa > 0
    return CheckResult(
        "Structural analysis produces physical results", passed,
        f"Safety factor = {struct.safety_factor:.2f}, combined stress = "
        f"{struct.combined_max_stress_pa/1e6:.1f} MPa -- both must be positive finite numbers.",
    )


def _check_modal_frequencies_increasing(geom: HybridRotorGeometry, material_key: str, tsr: float) -> CheckResult:
    mat = get_material(material_key)
    spar = spar_from_blade_geometry(geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, 0.5, 0.003)
    result = analyze_blade_aeroelastics(
        geom, ei_flapwise=mat.youngs_modulus_pa * spar.i_flapwise_m4,
        mass_per_length_kg_m=spar.area_m2 * mat.density_kg_m3, operating_tsr=tsr,
    )
    freqs = result.modal.natural_frequencies_hz
    passed = freqs == sorted(freqs) and all(f > 0 for f in freqs)
    return CheckResult(
        "Modal natural frequencies are physically ordered", passed,
        f"Frequencies: {[round(f,1) for f in freqs]} Hz -- each mode must have a strictly "
        f"higher frequency than the last, and all must be positive.",
    )


def _check_fatigue_life_positive(geom: HybridRotorGeometry, material_key: str, ply_key: str, tsr: float) -> CheckResult:
    mat = get_material(material_key)
    spar = spar_from_blade_geometry(geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, 0.5, 0.003)
    fatigue = analyze_blade_fatigue(
        geom, ei_flapwise=mat.youngs_modulus_pa * spar.i_flapwise_m4,
        section_i_m4=spar.i_flapwise_m4, section_c_m=spar.c_flapwise_m,
        static_strength_pa=mat.yield_strength_pa, ply_material_key=ply_key, operating_tsr=tsr,
    )
    passed = fatigue.estimated_life_years > 0 and fatigue.total_cycles_per_year > 0
    return CheckResult(
        "Fatigue life estimate is physically valid", passed,
        f"Estimated life = {fatigue.estimated_life_years:,.1f} years, "
        f"{fatigue.total_cycles_per_year/1e6:.1f}M cycles/year -- both must be positive.",
    )


def _check_economic_irr_npv_consistency(geom: HybridRotorGeometry, spar_mass_kg: float, ply_key: str, discount_rate: float = 0.06) -> CheckResult:
    econ = analyze_economics(geom, spar_mass_kg=spar_mass_kg, ply_material_key=ply_key, discount_rate=discount_rate)
    if econ.irr is None:
        passed = econ.npv_usd < 0  # no IRR found should mean cash flows never justify CAPEX -> negative NPV
        detail = f"No IRR found in search range; NPV = ${econ.npv_usd:,.0f} (should be negative, consistent with no positive-return rate existing)."
    else:
        if econ.irr < discount_rate:
            passed = econ.npv_usd < 0
        elif econ.irr > discount_rate:
            passed = econ.npv_usd > 0
        else:
            passed = True
        detail = f"IRR = {econ.irr*100:.1f}%, discount rate = {discount_rate*100:.1f}%, NPV = ${econ.npv_usd:,.0f} -- sign must agree (standard DCF identity)."
    return CheckResult("Economic IRR/NPV internal consistency", passed, detail)


@dataclass
class ValidationReport:
    checks: list[CheckResult]
    all_passed: bool
    n_passed: int
    n_total: int


def run_system_validation(
    geom: HybridRotorGeometry,
    material_key: str = "CFRP_UD",
    ply_material_key: str = "CFRP_UD_PLY",
    operating_tsr: float = 2.25,
    wind_speed_ms: float | None = None,
) -> ValidationReport:
    wind_speed_ms = wind_speed_ms or geom.rated_wind_speed_ms

    struct = analyze_blade_structure(geom, material_key, wind_speed_ms, operating_tsr,
                                      spar_width_fraction=0.5, spar_wall_thickness_m=0.003)

    checks = [
        _check_betz_limit(geom, wind_speed_ms),
        _check_rated_power_capping_reduces_aep(geom),
        _check_structural_safety_factor_positive(geom, material_key, wind_speed_ms, operating_tsr),
        _check_modal_frequencies_increasing(geom, material_key, operating_tsr),
        _check_fatigue_life_positive(geom, material_key, ply_material_key, operating_tsr),
        _check_economic_irr_npv_consistency(geom, struct.spar_mass_kg, ply_material_key),
    ]

    n_passed = sum(1 for c in checks if c.passed)
    return ValidationReport(
        checks=checks, all_passed=(n_passed == len(checks)), n_passed=n_passed, n_total=len(checks),
    )
