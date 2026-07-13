import pytest
from app.geometry.models import HybridRotorGeometry
from app.composites.lamina import get_ply
from app.composites.composite_spar import (
    CompositeSparDesign, build_uniform_angle_laminate, build_symmetric_angle_ply_laminate,
)
from app.composites.blade_composite_analysis import analyze_composite_blade
from app.composites.optimizer import optimize_spar_layup, compare_materials


def test_composite_spar_reduces_to_isotropic_formula_for_single_material():
    """
    When cap and web use the identical layup (same modulus throughout), the
    composite transformed-section EI must exactly match the classical
    isotropic hollow-rectangle formula -- the composite model is a strict
    generalisation of the isotropic one, not a different formula.
    """
    cfrp = get_ply("CFRP_UD_PLY")
    lam = build_uniform_angle_laminate(cfrp, 0.0, 24)
    B, H = 0.045, 0.0153
    spar = CompositeSparDesign(outer_width_m=B, outer_height_m=H, cap_laminate=lam, web_laminate=lam)

    t = lam.total_thickness_m
    b_inner, h_inner = B - 2 * t, H - 2 * t
    I_flap_iso = (B * H ** 3 - b_inner * h_inner ** 3) / 12
    I_edge_iso = (H * B ** 3 - h_inner * b_inner ** 3) / 12
    EI_flap_iso = lam.ex_flexural_pa * I_flap_iso
    EI_edge_iso = lam.ex_flexural_pa * I_edge_iso

    assert spar.ei_flapwise == pytest.approx(EI_flap_iso, rel=1e-9)
    assert spar.ei_edgewise == pytest.approx(EI_edge_iso, rel=1e-9)


def test_thicker_spar_cap_increases_flapwise_stiffness():
    cfrp = get_ply("CFRP_UD_PLY")
    web = build_symmetric_angle_ply_laminate(cfrp, 45.0, 2)
    thin_cap = build_uniform_angle_laminate(cfrp, 0.0, 4)
    thick_cap = build_uniform_angle_laminate(cfrp, 0.0, 16)

    spar_thin = CompositeSparDesign(outer_width_m=0.045, outer_height_m=0.02, cap_laminate=thin_cap, web_laminate=web)
    spar_thick = CompositeSparDesign(outer_width_m=0.045, outer_height_m=0.02, cap_laminate=thick_cap, web_laminate=web)

    assert spar_thick.ei_flapwise > spar_thin.ei_flapwise


def test_composite_blade_analysis_runs():
    geom = HybridRotorGeometry()
    cfrp = get_ply("CFRP_UD_PLY")
    cap = build_uniform_angle_laminate(cfrp, 0.0, 10)
    web = build_symmetric_angle_ply_laminate(cfrp, 45.0, 2)
    spar = CompositeSparDesign(outer_width_m=0.045, outer_height_m=0.02, cap_laminate=cap, web_laminate=web)

    r = analyze_composite_blade(geom, spar, cfrp, wind_speed_ms=12.0, tip_speed_ratio=2.25)
    assert r.spar_mass_kg > 0
    assert r.combined_max_stress_pa > 0
    assert r.safety_factor > 0


def test_optimizer_finds_feasible_design_under_moderate_load():
    geom = HybridRotorGeometry()
    opt = optimize_spar_layup(geom, "CFRP_UD_PLY", wind_speed_ms=12.0, tip_speed_ratio=2.25, target_safety_factor=1.5)
    assert opt.feasible
    assert opt.result.safety_factor >= 1.5


def test_optimizer_result_is_actually_minimum_mass_among_feasible_candidates():
    """Spot-check: no feasible candidate in a small sub-grid should beat the optimizer's answer."""
    geom = HybridRotorGeometry()
    opt = optimize_spar_layup(
        geom, "CFRP_UD_PLY", wind_speed_ms=12.0, tip_speed_ratio=2.25, target_safety_factor=1.5,
        cap_ply_range=range(4, 13, 2), web_pair_range=range(1, 3), spar_width_fractions=(0.3, 0.45),
    )
    from app.composites.lamina import get_ply as gp
    from app.composites.composite_spar import build_uniform_angle_laminate as bl, build_symmetric_angle_ply_laminate as bs
    from app.composites.blade_composite_analysis import analyze_composite_blade as acb
    cfrp = gp("CFRP_UD_PLY")
    for width in (0.3, 0.45):
        for n_cap in range(4, 13, 2):
            for n_web in range(1, 3):
                d = geom.darrieus
                cap = bl(cfrp, 0.0, n_cap)
                web = bs(cfrp, 45.0, n_web)
                spar = CompositeSparDesign(
                    outer_width_m=width * d.chord_m, outer_height_m=d.blade_thickness_ratio * d.chord_m * 0.85,
                    cap_laminate=cap, web_laminate=web,
                )
                r = acb(geom, spar, cfrp, 12.0, 2.25)
                if r.safety_factor >= 1.5:
                    assert r.spar_mass_kg >= opt.result.spar_mass_kg - 1e-9


def test_carbon_achieves_lower_mass_than_glass_for_high_load_case():
    """Under a demanding load case, CFRP's higher strength-to-weight should win out over GFRP."""
    geom = HybridRotorGeometry()
    results = compare_materials(geom, wind_speed_ms=20.0, tip_speed_ratio=4.5, target_safety_factor=1.5)
    cfrp_result = results["CFRP_UD_PLY"]
    gfrp_result = results["GFRP_UD_PLY"]
    # CFRP should at least be feasible or clearly better than GFRP under demanding loads
    if cfrp_result.feasible and gfrp_result.feasible:
        assert cfrp_result.result.spar_mass_kg <= gfrp_result.result.spar_mass_kg
    elif cfrp_result.feasible and not gfrp_result.feasible:
        pass  # expected: carbon succeeds where glass doesn't
    else:
        pytest.fail("Expected at least CFRP to find a feasible design under this load case")


def test_unknown_material_key_raises():
    geom = HybridRotorGeometry()
    with pytest.raises(ValueError):
        optimize_spar_layup(geom, "UNOBTANIUM", wind_speed_ms=12.0, tip_speed_ratio=2.25)
