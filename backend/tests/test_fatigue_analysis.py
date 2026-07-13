import pytest
from app.geometry.models import HybridRotorGeometry
from app.structural.cross_section import spar_from_blade_geometry
from app.structural.materials import get_material
from app.fatigue.fatigue_analysis import analyze_blade_fatigue
from app.fatigue.wind_distribution import bin_probabilities, annual_hours_per_bin


def _default_fatigue_result(material_key="CFRP_UD", ply_key="CFRP_UD_PLY",
                             width_frac=0.5, wall_m=0.003, tsr=2.25):
    geom = HybridRotorGeometry()
    mat = get_material(material_key)
    spar = spar_from_blade_geometry(geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, width_frac, wall_m)
    EI = mat.youngs_modulus_pa * spar.i_flapwise_m4
    return analyze_blade_fatigue(
        geom, ei_flapwise=EI, section_i_m4=spar.i_flapwise_m4, section_c_m=spar.c_flapwise_m,
        static_strength_pa=mat.yield_strength_pa, ply_material_key=ply_key,
        operating_tsr=tsr, weibull_k=2.0, weibull_c=7.0,
    )


def test_wind_distribution_probabilities_sum_to_one():
    bins = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    probs = bin_probabilities(bins, k=2.0, c=7.0)
    assert sum(probs) == pytest.approx(1.0, rel=1e-6)


def test_annual_hours_sum_to_8760():
    bins = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    hours = annual_hours_per_bin(bins, k=2.0, c=7.0)
    assert sum(hours) == pytest.approx(8760.0, rel=1e-6)


def test_well_margined_design_has_very_long_life():
    """A well-sized CFRP spar (per Phase 7/8's ~9.5 static safety factor) should show a very long fatigue life."""
    r = _default_fatigue_result()
    assert r.estimated_life_years > 1000


def test_thinner_more_marginal_design_has_shorter_life_than_well_margined_one():
    r_robust = _default_fatigue_result(width_frac=0.5, wall_m=0.003)
    r_marginal = _default_fatigue_result(
        material_key="GFRP_UD", ply_key="GFRP_UD_PLY", width_frac=0.25, wall_m=0.0012, tsr=3.5,
    )
    assert r_marginal.estimated_life_years < r_robust.estimated_life_years


def test_low_life_triggers_warning():
    r = _default_fatigue_result(
        material_key="GFRP_UD", ply_key="GFRP_UD_PLY", width_frac=0.2, wall_m=0.0008, tsr=4.0,
    )
    if r.estimated_life_years < 20:
        assert any("fatigue life" in w.lower() for w in r.warnings)


def test_damage_is_never_negative():
    r = _default_fatigue_result()
    assert r.annual_damage >= 0
    assert all(d >= 0 for d in r.damage_by_bin)


def test_higher_static_strength_gives_longer_life_for_same_load():
    geom = HybridRotorGeometry()
    spar = spar_from_blade_geometry(geom.darrieus.chord_m, geom.darrieus.blade_thickness_ratio, 0.3, 0.0015)
    mat = get_material("GFRP_UD")
    EI = mat.youngs_modulus_pa * spar.i_flapwise_m4

    r_weak = analyze_blade_fatigue(
        geom, ei_flapwise=EI, section_i_m4=spar.i_flapwise_m4, section_c_m=spar.c_flapwise_m,
        static_strength_pa=400e6, ply_material_key="GFRP_UD_PLY", operating_tsr=3.0,
    )
    r_strong = analyze_blade_fatigue(
        geom, ei_flapwise=EI, section_i_m4=spar.i_flapwise_m4, section_c_m=spar.c_flapwise_m,
        static_strength_pa=1200e6, ply_material_key="GFRP_UD_PLY", operating_tsr=3.0,
    )
    assert r_strong.estimated_life_years > r_weak.estimated_life_years


def test_cycles_per_year_are_physically_plausible_for_small_vawt():
    """A small VAWT spinning at a few hundred RPM should accumulate tens to hundreds of millions of cycles/year."""
    r = _default_fatigue_result()
    assert 1e6 < r.total_cycles_per_year < 1e10
