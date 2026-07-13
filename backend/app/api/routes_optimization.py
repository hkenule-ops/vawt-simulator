from fastapi import APIRouter, HTTPException

from app.schemas.optimization import (
    OptimizationRequest, OptimizationResponse, ParetoDesignOut, GenerationSnapshotOut,
)
from app.api.routes_geometry import to_domain
from app.structural.materials import MATERIAL_LIBRARY
from app.composites.lamina import PLY_LIBRARY
from app.optimization.nsga2_runner import run_optimization

router = APIRouter(prefix="/optimization", tags=["optimization"])


@router.post("/pareto-front", response_model=OptimizationResponse)
def optimize_pareto_front(req: OptimizationRequest):
    if req.material not in MATERIAL_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown material. Available: {list(MATERIAL_LIBRARY)}")
    if req.ply_material not in PLY_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown ply material. Available: {list(PLY_LIBRARY)}")

    domain = to_domain(req.geometry)
    result = run_optimization(
        domain, material_key=req.material, ply_material_key=req.ply_material,
        target_safety_factor=req.target_safety_factor, operating_tsr=req.operating_tsr,
        population_size=req.population_size, n_generations=req.n_generations, seed=req.seed,
        capture_history=req.capture_history,
    )

    return OptimizationResponse(
        pareto_front=[ParetoDesignOut(**d.__dict__) for d in result.pareto_front],
        n_generations=result.n_generations, population_size=result.population_size,
        n_evaluated=result.n_evaluated,
        generation_history=[
            GenerationSnapshotOut(
                generation=s.generation, n_eval=s.n_eval,
                pareto_front=[ParetoDesignOut(**d.__dict__) for d in s.pareto_front],
            )
            for s in result.generation_history
        ],
    )
