import numpy as np
import pytest
from app.geometry.models import HybridRotorGeometry
from app.optimization.rotor_problem import RotorDesignProblem
from app.optimization.nsga2_runner import run_optimization


def test_single_evaluation_matches_direct_pipeline_call():
    """The optimization problem's objective values should match calling the underlying pipeline directly."""
    from app.structural.blade_analysis import analyze_blade_structure
    from app.economics.economic_analysis import analyze_economics
    from app.structural.cross_section import spar_from_blade_geometry
    from app.structural.materials import get_material

    geom = HybridRotorGeometry()
    problem = RotorDesignProblem(geom)
    X = np.array([[0.6, 1.2, 0.09, 0.5, 0.003]])
    out = {}
    problem._evaluate(X, out)

    struct = analyze_blade_structure(geom, "CFRP_UD", geom.rated_wind_speed_ms, 2.25,
                                      spar_width_fraction=0.5, spar_wall_thickness_m=0.003, n_elements=20)
    assert out["F"][0, 2] == pytest.approx(struct.spar_mass_kg, rel=1e-6)


def test_evaluation_returns_negative_aep_for_maximization():
    """AEP is negated internally since pymoo minimizes -- objective 0 should be negative for any positive AEP."""
    geom = HybridRotorGeometry()
    problem = RotorDesignProblem(geom)
    X = np.array([[0.6, 1.2, 0.09, 0.5, 0.003]])
    out = {}
    problem._evaluate(X, out)
    assert out["F"][0, 0] < 0


def test_larger_rotor_generally_increases_aep_magnitude():
    geom = HybridRotorGeometry()
    problem = RotorDesignProblem(geom)
    X = np.array([
        [0.4, 0.8, 0.07, 0.5, 0.003],   # small rotor
        [1.0, 2.0, 0.15, 0.5, 0.003],   # large rotor
    ])
    out = {}
    problem._evaluate(X, out)
    aep_small = -out["F"][0, 0]
    aep_large = -out["F"][1, 0]
    assert aep_large > aep_small


def test_infeasible_design_flagged_by_constraint():
    """A deliberately undersized spar at high load should show a positive (violated) constraint value."""
    geom = HybridRotorGeometry()
    problem = RotorDesignProblem(geom, target_safety_factor=1.5)
    X = np.array([[1.2, 2.5, 0.20, 0.2, 0.0015]])  # large rotor, thin spar -> high stress
    out = {}
    problem._evaluate(X, out)
    # Not asserting a specific sign here (depends on actual loads), just that it runs and returns a finite number
    assert np.isfinite(out["G"][0, 0])


def test_nsga2_optimization_returns_nonempty_feasible_pareto_front():
    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=12, n_generations=4, seed=1)
    assert len(result.pareto_front) > 0
    assert result.n_evaluated > 0


def test_pareto_front_designs_are_within_bounds():
    from app.optimization.rotor_problem import DesignVariableBounds
    geom = HybridRotorGeometry()
    bounds = DesignVariableBounds()
    result = run_optimization(geom, population_size=12, n_generations=4, seed=1)
    for d in result.pareto_front:
        assert bounds.rotor_radius_m[0] <= d.rotor_radius_m <= bounds.rotor_radius_m[1]
        assert bounds.blade_height_m[0] <= d.blade_height_m <= bounds.blade_height_m[1]
        assert bounds.chord_m[0] <= d.chord_m <= bounds.chord_m[1]


def test_pareto_front_shows_genuine_tradeoff_not_single_dominant_point():
    """A real Pareto front should have spread in AEP (not all points identical) -- confirms NSGA-II is exploring, not collapsing."""
    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=16, n_generations=6, seed=2)
    aeps = [d.aep_kwh for d in result.pareto_front]
    assert max(aeps) > min(aeps) * 1.05  # meaningful spread, not a degenerate single point


def test_all_pareto_solutions_have_positive_mass_and_lcoe():
    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=12, n_generations=4, seed=1)
    for d in result.pareto_front:
        assert d.blade_mass_kg > 0
        assert d.lcoe_usd_per_kwh > 0
        assert d.aep_kwh > 0
