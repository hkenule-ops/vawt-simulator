import pytest
from app.geometry.models import HybridRotorGeometry
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material
from app.economics.economic_analysis import analyze_economics
from app.economics.energy_yield import compute_aep


def _default_spar_mass(material_key="CFRP_UD"):
    geom = HybridRotorGeometry()
    mat = get_material(material_key)
    spar = spar_from_blade_geometry(geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, 0.5, 0.003)
    return geom, spar.area_m2 * geom.darrieus.blade_height_m * mat.density_kg_m3


def test_aep_rated_power_limit_reduces_energy_vs_unregulated():
    """A real (rated-power-limited) power curve must produce less energy than the unregulated one."""
    geom = HybridRotorGeometry()
    r_limited = compute_aep(geom, apply_rated_power_limit=True)
    r_unlimited = compute_aep(geom, apply_rated_power_limit=False)
    assert r_limited.aep_kwh < r_unlimited.aep_kwh


def test_capacity_factor_is_between_zero_and_one():
    geom = HybridRotorGeometry()
    r = compute_aep(geom)
    assert 0 < r.capacity_factor < 1.0


def test_economic_analysis_runs_and_returns_positive_capex():
    geom, spar_mass = _default_spar_mass()
    r = analyze_economics(geom, spar_mass_kg=spar_mass, ply_material_key="CFRP_UD_PLY")
    assert r.capex.total_capex_usd > 0
    assert r.aep.aep_kwh > 0
    assert r.lcoe_usd_per_kwh > 0


def test_higher_electricity_price_improves_npv():
    geom, spar_mass = _default_spar_mass()
    r_low_price = analyze_economics(geom, spar_mass_kg=spar_mass, ply_material_key="CFRP_UD_PLY",
                                      electricity_price_usd_per_kwh=0.10)
    r_high_price = analyze_economics(geom, spar_mass_kg=spar_mass, ply_material_key="CFRP_UD_PLY",
                                      electricity_price_usd_per_kwh=0.30)
    assert r_high_price.npv_usd > r_low_price.npv_usd


def test_cheaper_material_reduces_capex():
    geom, spar_mass_cfrp = _default_spar_mass("CFRP_UD")
    _, spar_mass_gfrp = _default_spar_mass("GFRP_UD")
    r_cfrp = analyze_economics(geom, spar_mass_kg=spar_mass_cfrp, ply_material_key="CFRP_UD_PLY")
    r_gfrp = analyze_economics(geom, spar_mass_kg=spar_mass_gfrp, ply_material_key="GFRP_UD_PLY")
    # GFRP is much cheaper per kg even though it's heavier -- blade material cost should be lower
    assert r_gfrp.capex.blade_material_cost_usd < r_cfrp.capex.blade_material_cost_usd


def test_negative_npv_triggers_warning():
    geom, spar_mass = _default_spar_mass()
    r = analyze_economics(geom, spar_mass_kg=spar_mass, ply_material_key="CFRP_UD_PLY",
                           electricity_price_usd_per_kwh=0.05)  # deliberately low price
    if r.npv_usd < 0:
        assert any("negative npv" in w.lower() for w in r.warnings)


def test_payback_and_irr_are_internally_consistent():
    """If IRR < discount rate, NPV should be negative, and vice versa (standard financial identity)."""
    geom, spar_mass = _default_spar_mass()
    r = analyze_economics(geom, spar_mass_kg=spar_mass, ply_material_key="CFRP_UD_PLY", discount_rate=0.06)
    if r.irr is not None:
        if r.irr < 0.06:
            assert r.npv_usd < 0
        elif r.irr > 0.06:
            assert r.npv_usd > 0
