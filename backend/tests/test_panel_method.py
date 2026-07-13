"""
Physics sanity tests for the 2D vortex panel method (app/cfd/panel_method.py).

These tests are what caught two real bugs during development: (1) the Kutta
condition being tied to the wrong panel pair because the boundary loop was
seamed at the leading edge instead of the trailing edge, and (2) an inverted
Kutta-Joukowski sign convention. Both were invisible from "does it run
without crashing" -- only checking against known physics caught them.
"""
import pytest
from app.cfd.panel_method import solve_panel_method


def test_symmetric_airfoil_zero_lift_at_zero_alpha():
    """A symmetric (zero-camber) section must produce exactly zero lift at alpha=0."""
    r = solve_panel_method(thickness_ratio=0.18, alpha_deg=0.0, n_panels=60)
    assert abs(r.cl) < 1e-8


def test_lift_sign_matches_angle_of_attack_sign():
    r_pos = solve_panel_method(thickness_ratio=0.18, alpha_deg=5.0, n_panels=60)
    r_neg = solve_panel_method(thickness_ratio=0.18, alpha_deg=-5.0, n_panels=60)
    assert r_pos.cl > 0
    assert r_neg.cl < 0
    assert r_pos.cl == pytest.approx(-r_neg.cl, rel=1e-3)


def test_cl_scales_linearly_with_alpha_in_small_angle_regime():
    """In the linear (pre-stall) regime, Cl/alpha should be roughly constant."""
    r2 = solve_panel_method(thickness_ratio=0.18, alpha_deg=2.0, n_panels=80)
    r4 = solve_panel_method(thickness_ratio=0.18, alpha_deg=4.0, n_panels=80)
    ratio2 = r2.cl / 2.0
    ratio4 = r4.cl / 4.0
    assert ratio2 == pytest.approx(ratio4, rel=0.02)


def test_lift_slope_exceeds_thin_airfoil_theory_by_expected_thickness_correction():
    """
    Real symmetric sections have a higher lift-curve slope than the 2*pi
    thin-airfoil-theory value, due to thickness. The correction factor is
    well known to be roughly (1 + 0.77*t/c) (van Dyke-type thin-body
    correction). For t/c=0.18 that's ~1.14; the panel method should land
    within a reasonable band of that, not equal thin-airfoil theory exactly
    (that would indicate thickness isn't being resolved at all) and not
    wildly off (indicating a solver bug).
    """
    r = solve_panel_method(thickness_ratio=0.18, alpha_deg=4.0, n_panels=100)
    ratio = r.cl / r.cl_thin_airfoil_theory
    assert 1.05 < ratio < 1.30


def test_thinner_section_has_smaller_thickness_correction():
    r_thin = solve_panel_method(thickness_ratio=0.09, alpha_deg=4.0, n_panels=100)
    r_thick = solve_panel_method(thickness_ratio=0.21, alpha_deg=4.0, n_panels=100)
    ratio_thin = r_thin.cl / r_thin.cl_thin_airfoil_theory
    ratio_thick = r_thick.cl / r_thick.cl_thin_airfoil_theory
    assert ratio_thick > ratio_thin


def test_upper_surface_shows_more_suction_than_lower_at_positive_alpha():
    """For positive lift, the upper surface must have lower Cp (more suction) than the lower surface."""
    r = solve_panel_method(thickness_ratio=0.18, alpha_deg=5.0, n_panels=80)
    upper_cp = [cp for cp, up in zip(r.cp, r.is_upper) if up]
    lower_cp = [cp for cp, up in zip(r.cp, r.is_upper) if not up]
    assert sum(upper_cp) / len(upper_cp) < sum(lower_cp) / len(lower_cp)


def test_solver_converges():
    r = solve_panel_method(thickness_ratio=0.18, alpha_deg=6.0, n_panels=80)
    assert r.converged
