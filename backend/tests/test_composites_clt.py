"""
Classical Laminate Theory validation tests. Each check here is a known,
independently-derivable closed-form result from composite mechanics theory
-- not something tuned to make the test pass. This is the same standard
applied to the BEM (Betz limit), panel method (Kutta condition, thickness
correction), and beam FEM (closed-form deflection) solvers in earlier phases.
"""
import pytest
from app.composites.lamina import get_ply
from app.composites.laminate import Ply, analyze_laminate


def _uniform_layup(ply_name: str, angle: float, n: int) -> list[Ply]:
    mat = get_ply(ply_name)
    return [Ply(mat, angle) for _ in range(n)]


def test_all_zero_degree_layup_gives_pure_fibre_direction_modulus():
    """A stack of all 0deg plies must have Ex exactly equal to E1 and Ey exactly equal to E2."""
    cfrp = get_ply("CFRP_UD_PLY")
    r = analyze_laminate(_uniform_layup("CFRP_UD_PLY", 0.0, 8))
    assert r.ex_pa == pytest.approx(cfrp.e1_pa, rel=1e-9)
    assert r.ey_pa == pytest.approx(cfrp.e2_pa, rel=1e-9)


def test_all_ninety_degree_layup_swaps_ex_ey():
    """Rotating every ply 90deg must exactly swap Ex and Ey relative to the 0deg case."""
    cfrp = get_ply("CFRP_UD_PLY")
    r = analyze_laminate(_uniform_layup("CFRP_UD_PLY", 90.0, 8))
    assert r.ex_pa == pytest.approx(cfrp.e2_pa, rel=1e-9)
    assert r.ey_pa == pytest.approx(cfrp.e1_pa, rel=1e-9)


def test_symmetric_layup_has_zero_coupling_matrix():
    """A symmetric (mirror-plane) layup must have B=0 -- no extension-bending coupling."""
    cfrp = get_ply("CFRP_UD_PLY")
    plies = [Ply(cfrp, 0), Ply(cfrp, 90), Ply(cfrp, 90), Ply(cfrp, 0)]
    r = analyze_laminate(plies)
    assert r.max_b_matrix_term < 1e-8


def test_asymmetric_layup_has_nonzero_coupling_matrix():
    """An asymmetric layup (no mirror plane) must show real extension-bending coupling."""
    cfrp = get_ply("CFRP_UD_PLY")
    plies = [Ply(cfrp, 0), Ply(cfrp, 90)]
    r = analyze_laminate(plies)
    assert r.max_b_matrix_term > 1.0


def test_quasi_isotropic_layup_gives_equal_ex_ey():
    """
    A [0/45/-45/90]s quasi-isotropic layup is a well-known CLT result: the
    in-plane extensional response becomes direction-independent, i.e. Ex=Ey
    exactly, despite being built entirely from a highly anisotropic ply.
    """
    cfrp = get_ply("CFRP_UD_PLY")
    plies = [Ply(cfrp, a) for a in [0, 45, -45, 90, 90, -45, 45, 0]]
    r = analyze_laminate(plies)
    assert r.ex_pa == pytest.approx(r.ey_pa, rel=1e-6)


def test_quasi_isotropic_modulus_between_e1_and_e2():
    """Quasi-isotropic Ex should be a genuine blend, strictly between E2 and E1."""
    cfrp = get_ply("CFRP_UD_PLY")
    plies = [Ply(cfrp, a) for a in [0, 45, -45, 90, 90, -45, 45, 0]]
    r = analyze_laminate(plies)
    assert cfrp.e2_pa < r.ex_pa < cfrp.e1_pa


def test_thicker_laminate_has_more_mass_per_area():
    r_thin = analyze_laminate(_uniform_layup("CFRP_UD_PLY", 0.0, 4))
    r_thick = analyze_laminate(_uniform_layup("CFRP_UD_PLY", 0.0, 8))
    assert r_thick.mass_per_area_kg_m2 > r_thin.mass_per_area_kg_m2
    assert r_thick.mass_per_area_kg_m2 == pytest.approx(2 * r_thin.mass_per_area_kg_m2, rel=1e-9)


def test_empty_layup_raises():
    with pytest.raises(ValueError):
        analyze_laminate([])


def test_carbon_stiffer_than_glass_for_same_layup():
    plies_cfrp = _uniform_layup("CFRP_UD_PLY", 0.0, 8)
    plies_gfrp = _uniform_layup("GFRP_UD_PLY", 0.0, 8)
    r_c = analyze_laminate(plies_cfrp)
    r_g = analyze_laminate(plies_gfrp)
    assert r_c.ex_pa > r_g.ex_pa
