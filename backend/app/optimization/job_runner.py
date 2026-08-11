"""
Resumable NSGA-II execution for serverless hosts.

The synchronous /optimization/pareto-front endpoint (nsga2_runner.run_optimization)
blocks for the entire search in one request, which reliably 504s on Vercel
once population_size * n_generations gets large enough -- there's no
reliable "run this in the background after I respond" primitive on that
platform for Python functions, so the fix isn't a background task, it's
splitting the search into many short, resumable steps:

  1. create_job(): build the pymoo Problem + NSGA2 Algorithm, call
     .setup(), pickle it, save as a job row. Fast -- no evaluations yet.
  2. step_job(): unpickle the algorithm, call .next() in a loop until
     either the search finishes or a wall-clock budget is used up
     (comfortably inside any serverless timeout), then re-pickle and save.
     The client just keeps calling step() until status == "completed".

Each step is a normal, bounded request/response -- nothing needs to
survive after the response is sent, which is what makes this work
reliably on Vercel (or anywhere else) regardless of plan tier.
"""
from __future__ import annotations

import pickle
import time
import uuid

import numpy as np
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting
from sqlalchemy.orm import Session

from app.geometry.models import HybridRotorGeometry
from app.models.optimization_job import OptimizationJob
from app.optimization.nsga2_runner import _rows_to_designs
from app.optimization.rotor_problem import RotorDesignProblem

DEFAULT_MAX_STEP_SECONDS = 8.0


def _snapshot(nds: NonDominatedSorting, pop, generation: int) -> dict:
    pop_X, pop_F, pop_G = pop.get("X"), pop.get("F"), pop.get("G")
    feasible_mask = (pop_G <= 0).all(axis=1) if pop_G is not None else np.ones(len(pop_F), dtype=bool)
    feas_X, feas_F = pop_X[feasible_mask], pop_F[feasible_mask]
    if len(feas_F) == 0:
        pareto_front = []
    else:
        front_idx = nds.do(feas_F, only_non_dominated_front=True)
        pareto_front = [d.__dict__ for d in _rows_to_designs(feas_X[front_idx], feas_F[front_idx])]
    return {"generation": generation, "n_eval": 0, "pareto_front": pareto_front}


def create_job(
    db: Session,
    base_geometry: HybridRotorGeometry,
    request_json: dict,
    material_key: str = "CFRP_UD",
    ply_material_key: str = "CFRP_UD_PLY",
    target_safety_factor: float = 1.5,
    operating_tsr: float = 2.25,
    population_size: int = 24,
    n_generations: int = 10,
    seed: int = 1,
) -> OptimizationJob:
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
    algorithm.setup(problem, termination=("n_gen", n_generations), seed=seed, verbose=False)

    job = OptimizationJob(
        id=str(uuid.uuid4()),
        status="pending",
        request_json=request_json,
        population_size=population_size,
        n_generations=n_generations,
        generations_completed=0,
        n_evaluated=0,
        state_blob=pickle.dumps(algorithm),
        generation_history_json=[],
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def step_job(db: Session, job: OptimizationJob, max_step_seconds: float = DEFAULT_MAX_STEP_SECONDS) -> OptimizationJob:
    if job.status in ("completed", "failed"):
        return job

    try:
        algorithm = pickle.loads(job.state_blob)
        nds = NonDominatedSorting()
        history = list(job.generation_history_json or [])

        t0 = time.time()
        job.status = "running"
        while algorithm.has_next() and (time.time() - t0) < max_step_seconds:
            algorithm.next()
            job.generations_completed += 1
            snap = _snapshot(nds, algorithm.pop, job.generations_completed)
            snap["n_eval"] = int(algorithm.evaluator.n_eval)
            history.append(snap)

        job.generation_history_json = history
        job.n_evaluated = int(algorithm.evaluator.n_eval)

        if not algorithm.has_next():
            res = algorithm.result()
            pareto_designs = []
            if res.X is not None and len(res.X.shape) > 0:
                X = res.X if res.X.ndim == 2 else res.X.reshape(1, -1)
                F = res.F if res.F.ndim == 2 else res.F.reshape(1, -1)
                pareto_designs = [d.__dict__ for d in _rows_to_designs(X, F)]
            job.pareto_front_json = pareto_designs
            job.status = "completed"
            job.state_blob = None
        else:
            job.state_blob = pickle.dumps(algorithm)

    except Exception as exc:  # noqa: BLE001 - persist failure instead of crashing the request
        job.status = "failed"
        job.error_message = str(exc)
        job.state_blob = None

    db.add(job)
    db.commit()
    db.refresh(job)
    return job