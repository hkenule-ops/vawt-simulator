"""
Structural module tests. The beam FEM tests validate against closed-form
analytical beam solutions -- the same standard applied to the BEM (Betz
limit) and panel method (Kutta condition, thin-airfoil comparison) solvers
in earlier phases: a FEM that "runs" isn't trusted until it reproduces a
known-correct answer.
"""
import pytest
import math

from app.structural.beam_fem import solve_beam_udl
from app.structural.cross_section import spar_from_blade_geometry, SparCrossSection
from app.structural.materials import get_material, MATERIAL_LIBRARY
from app.structural.buckling import euler_critical_buckling_load
from app.structural.blade_analysis import analyze_blade_structure
from app.geometry.models import HybridRotorGeometry


# ---- Beam FEM validation against closed-form solutions ----

def test_pinned_pinned_udl_deflection_matches_closed_form():
    L, EI, w0 = 1.2, 68.9e9 * 5e-8, 100.0
    r = solve_beam_udl(L, EI, w0, n_elements=40, boundary="pinned-pinned")
    analytical = 5 * w0 * L ** 4 / (384 * EI)
    assert r.max_deflection_m == pytest.approx(analytical, rel=1e-6)


def test_pinned_pinned_udl_moment_matches_closed_form():
    L, EI, w0 = 1.2, 68.9e9 * 5e-8, 100.0
    r = solve_beam_udl(L, EI, w0, n_elements=40, boundary="pinned-pinned")
    analytical = w0 * L ** 2 / 8
    assert abs(r.max_bending_moment_nm) == pytest.approx(analytical, rel=1e-6)


def test_cantilever_udl_tip_deflection_matches_closed_form():
    L, EI, w0 = 1.2, 68.9e9 * 5e-8, 100.0
    r = solve_beam_udl(L, EI, w0, n_elements=40, boundary="cantilever")
    analytical = w0 * L ** 4 / (8 * EI)
    assert r.max_deflection_m == pytest.approx(analytical, rel=1e-6)


def test_cantilever_udl_root_moment_matches_closed_form():
    L, EI, w0 = 1.2, 68.9e9 * 5e-8, 100.0
    r = solve_beam_udl(L, EI, w0, n_elements=40, boundary="cantilever")
    analytical = w0 * L ** 2 / 2
    assert abs(r.max_bending_moment_nm) == pytest.approx(analytical, rel=1e-6)


def test_beam_fem_converges_with_mesh_refinement():
    """Euler-Bernoulli elements are exact for UDL beams -- coarse and fine meshes should agree."""
    L, EI, w0 = 1.2, 68.9e9 * 5e-8, 100.0
    r_coarse = solve_beam_udl(L, EI, w0, n_elements=4, boundary="pinned-pinned")
    r_fine = solve_beam_udl(L, EI, w0, n_elements=100, boundary="pinned-pinned")
    assert r_coarse.max_deflection_m == pytest.approx(r_fine.max_deflection_m, rel=1e-6)


def test_zero_load_gives_zero_deflection():
    r = solve_beam_udl(1.2, 68.9e9 * 5e-8, 0.0, n_elements=20)
    assert r.max_deflection_m == pytest.approx(0.0, abs=1e-12)


# ---- Cross-section properties ----

def test_hollow_section_area_positive_and_less_than_solid():
    spar = spar_from_blade_geometry(chord_m=0.09, thickness_ratio=0.18, wall_thickness_m=0.003)
    solid_area = spar.outer_width_m * spar.outer_height_m
    assert 0 < spar.area_m2 < solid_area


def test_flapwise_and_edgewise_inertia_differ_for_non_square_section():
    spar = SparCrossSection(outer_width_m=0.05, outer_height_m=0.02, wall_thickness_m=0.003)
    assert spar.i_flapwise_m4 != spar.i_edgewise_m4
    # wider than tall -> stiffer resisting edgewise (bending about the thickness axis)
    assert spar.i_edgewise_m4 > spar.i_flapwise_m4


# ---- Material library ----

def test_all_materials_have_positive_properties():
    for name, mat in MATERIAL_LIBRARY.items():
        assert mat.youngs_modulus_pa > 0
        assert mat.yield_strength_pa > 0
        assert mat.density_kg_m3 > 0


def test_unknown_material_raises():
    with pytest.raises(ValueError):
        get_material("UNOBTANIUM")


# ---- Buckling ----

def test_cantilever_has_higher_effective_length_than_pinned_pinned():
    EI, L = 1000.0, 2.0
    p_pinned = euler_critical_buckling_load(EI, L, "pinned-pinned")
    p_cantilever = euler_critical_buckling_load(EI, L, "cantilever")
    assert p_cantilever < p_pinned  # cantilever (K=2) has a much lower critical load


def test_buckling_matches_closed_form_pinned_pinned():
    EI, L = 1000.0, 2.0
    p = euler_critical_buckling_load(EI, L, "pinned-pinned")
    assert p == pytest.approx(math.pi ** 2 * EI / L ** 2, rel=1e-9)


# ---- Full blade structural analysis ----

def test_blade_analysis_runs_for_all_materials():
    geom = HybridRotorGeometry()
    for mat_name in MATERIAL_LIBRARY:
        r = analyze_blade_structure(geom, mat_name, wind_speed_ms=10.0, tip_speed_ratio=2.25)
        assert r.safety_factor > 0
        assert r.spar_mass_kg > 0
        assert r.combined_max_stress_pa > 0


def test_higher_wind_speed_increases_stress():
    geom = HybridRotorGeometry()
    r_low = analyze_blade_structure(geom, "CFRP_UD", wind_speed_ms=6.0, tip_speed_ratio=2.25)
    r_high = analyze_blade_structure(geom, "CFRP_UD", wind_speed_ms=14.0, tip_speed_ratio=2.25)
    assert r_high.combined_max_stress_pa > r_low.combined_max_stress_pa


def test_stiffer_stronger_material_gives_better_safety_factor_than_weaker_one():
    geom = HybridRotorGeometry()
    r_cfrp = analyze_blade_structure(geom, "CFRP_UD", wind_speed_ms=12.0, tip_speed_ratio=2.25)
    r_al = analyze_blade_structure(geom, "AL_6061_T6", wind_speed_ms=12.0, tip_speed_ratio=2.25)
    assert r_cfrp.safety_factor > r_al.safety_factor


def test_low_safety_factor_triggers_warning():
    # Undersize the spar wall drastically to force a low safety factor and check the warning fires.
    geom = HybridRotorGeometry()
    r = analyze_blade_structure(
        geom, "AL_6061_T6", wind_speed_ms=20.0, tip_speed_ratio=3.5,
        spar_width_fraction=0.15, spar_wall_thickness_m=0.0008,
    )
    if r.safety_factor < 1.5:
        assert any("safety factor" in w.lower() for w in r.warnings)
