"""
Runs pymoo's NSGA-II on the RotorDesignProblem and extracts the Pareto
front (non-dominated, feasible solutions) as plain Python data structures
for the API layer.
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.optimize import minimize
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

from app.geometry.models import HybridRotorGeometry
from app.optimization.rotor_problem import RotorDesignProblem, DesignVariableBounds


@dataclass
class ParetoDesign:
    rotor_radius_m: float
    blade_height_m: float
    chord_m: float
    spar_width_fraction: float
    spar_wall_thickness_m: float
    aep_kwh: float
    lcoe_usd_per_kwh: float
    blade_mass_kg: float


@dataclass
class GenerationSnapshot:
    generation: int
    n_eval: int
    pareto_front: list[ParetoDesign]


@dataclass
class OptimizationResult:
    pareto_front: list[ParetoDesign]
    n_generations: int
    population_size: int
    n_evaluated: int
    generation_history: list[GenerationSnapshot]


def _rows_to_designs(X: np.ndarray, F: np.ndarray) -> list[ParetoDesign]:
    designs = []
    for x_row, f_row in zip(X, F):
        designs.append(ParetoDesign(
            rotor_radius_m=float(x_row[0]), blade_height_m=float(x_row[1]),
            chord_m=float(x_row[2]), spar_width_fraction=float(x_row[3]),
            spar_wall_thickness_m=float(x_row[4]),
            aep_kwh=float(-f_row[0]), lcoe_usd_per_kwh=float(f_row[1]),
            blade_mass_kg=float(f_row[2]),
        ))
    return designs


def run_optimization(
    base_geometry: HybridRotorGeometry,
    material_key: str = "CFRP_UD",
    ply_material_key: str = "CFRP_UD_PLY",
    target_safety_factor: float = 1.5,
    operating_tsr: float = 2.25,
    population_size: int = 24,
    n_generations: int = 10,
    seed: int = 1,
    capture_history: bool = False,
) -> OptimizationResult:
    problem = RotorDesignProblem(
        base_geometry, material_key=material_key, ply_material_key=ply_material_key,
        target_safety_factor=target_safety_factor, operating_tsr=operating_tsr,
    )

    algorithm = NSGA2(
        pop_size=population_size,
        sampling=FloatRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True,
    )

    res = minimize(
        problem, algorithm, ("n_gen", n_generations),
        seed=seed, verbose=False, save_history=capture_history,
    )

    pareto_designs: list[ParetoDesign] = []
    if res.X is not None and len(res.X.shape) > 0:
        X = res.X if res.X.ndim == 2 else res.X.reshape(1, -1)
        F = res.F if res.F.ndim == 2 else res.F.reshape(1, -1)
        pareto_designs = _rows_to_designs(X, F)

    generation_history: list[GenerationSnapshot] = []
    if capture_history and res.history:
        nds = NonDominatedSorting()
        for gen_idx, algo_state in enumerate(res.history):
            pop_X = algo_state.pop.get("X")
            pop_F = algo_state.pop.get("F")
            # Only feasible individuals contribute to the visible Pareto front at each
            # generation -- infeasible ones (constraint violated) are excluded, matching
            # the feasibility filtering pymoo applies to the final result.
            pop_G = algo_state.pop.get("G")
            feasible_mask = (pop_G <= 0).all(axis=1) if pop_G is not None else np.ones(len(pop_F), dtype=bool)
            feas_X, feas_F = pop_X[feasible_mask], pop_F[feasible_mask]
            if len(feas_F) == 0:
                generation_history.append(GenerationSnapshot(
                    generation=gen_idx + 1, n_eval=int(algo_state.evaluator.n_eval), pareto_front=[],
                ))
                continue
            front_idx = nds.do(feas_F, only_non_dominated_front=True)
            snapshot_designs = _rows_to_designs(feas_X[front_idx], feas_F[front_idx])
            generation_history.append(GenerationSnapshot(
                generation=gen_idx + 1, n_eval=int(algo_state.evaluator.n_eval), pareto_front=snapshot_designs,
            ))

    return OptimizationResult(
        pareto_front=pareto_designs,
        n_generations=n_generations,
        population_size=population_size,
        n_evaluated=int(res.algorithm.evaluator.n_eval) if res.algorithm else population_size * n_generations,
        generation_history=generation_history,
    )
