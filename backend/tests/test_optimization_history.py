import pytest
from app.geometry.models import HybridRotorGeometry
from app.optimization.nsga2_runner import run_optimization


def test_generation_history_has_one_snapshot_per_generation():
    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=12, n_generations=4, seed=1, capture_history=True)
    assert len(result.generation_history) == 4


def test_generation_history_empty_when_not_requested():
    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=12, n_generations=4, seed=1, capture_history=False)
    assert result.generation_history == []


def test_generation_n_eval_increases_monotonically():
    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=12, n_generations=4, seed=1, capture_history=True)
    n_evals = [s.n_eval for s in result.generation_history]
    assert n_evals == sorted(n_evals)
    assert n_evals[-1] > n_evals[0]


def test_best_aep_in_history_does_not_decrease_across_generations():
    """NSGA-II with elitism should never lose its best-found solution across generations."""
    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=12, n_generations=5, seed=1, capture_history=True)
    best_per_gen = [
        max((d.aep_kwh for d in s.pareto_front), default=0.0)
        for s in result.generation_history
    ]
    non_empty = [b for b in best_per_gen if b > 0]
    assert non_empty == sorted(non_empty)


def test_all_generation_snapshot_designs_are_feasible():
    """Every design in each generation's captured front should satisfy the safety constraint."""
    from app.structural.blade_analysis import analyze_blade_structure

    geom = HybridRotorGeometry()
    result = run_optimization(geom, population_size=12, n_generations=3, seed=1, capture_history=True)
    for snap in result.generation_history:
        for d in snap.pareto_front:
            struct = analyze_blade_structure(
                geom, "CFRP_UD", geom.rated_wind_speed_ms, 2.25,
                spar_width_fraction=d.spar_width_fraction, spar_wall_thickness_m=d.spar_wall_thickness_m,
                n_elements=20,
            )
            assert struct.safety_factor >= 1.5 - 1e-6
