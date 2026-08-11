from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.optimization import (
    OptimizationRequest, OptimizationResponse, ParetoDesignOut, GenerationSnapshotOut,
    OptimizationJobCreateOut, OptimizationJobStatusOut,
)
from app.api.routes_geometry import to_domain
from app.structural.materials import MATERIAL_LIBRARY
from app.composites.lamina import PLY_LIBRARY
from app.optimization.nsga2_runner import run_optimization
from app.optimization import job_runner
from app.models.optimization_job import OptimizationJob

router = APIRouter(prefix="/optimization", tags=["optimization"])


def _validate_materials(material: str, ply_material: str) -> None:
    if material not in MATERIAL_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown material. Available: {list(MATERIAL_LIBRARY)}")
    if ply_material not in PLY_LIBRARY:
        raise HTTPException(status_code=400, detail=f"Unknown ply material. Available: {list(PLY_LIBRARY)}")


def _job_to_status_out(job: OptimizationJob) -> OptimizationJobStatusOut:
    pct = 0.0 if job.n_generations == 0 else min(100.0, 100.0 * job.generations_completed / job.n_generations)
    return OptimizationJobStatusOut(
        job_id=job.id, status=job.status,
        population_size=job.population_size, n_generations=job.n_generations,
        generations_completed=job.generations_completed, n_evaluated=job.n_evaluated,
        progress_pct=pct,
        pareto_front=[ParetoDesignOut(**d) for d in job.pareto_front_json] if job.pareto_front_json else None,
        generation_history=[GenerationSnapshotOut(**s) for s in (job.generation_history_json or [])],
        error=job.error_message,
    )


@router.post("/pareto-front", response_model=OptimizationResponse)
def optimize_pareto_front(req: OptimizationRequest):
    """
    Synchronous, single-request optimization. Kept for local development
    where there's no serverless request-duration ceiling to worry about --
    on Vercel this WILL 504 once population_size * n_generations is large
    enough. Production/browser clients should use the async job endpoints
    below (POST /optimization/jobs + POST /optimization/jobs/{id}/step)
    instead, which never block for longer than a few seconds per request.
    """
    _validate_materials(req.material, req.ply_material)

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


@router.post("/jobs", response_model=OptimizationJobCreateOut)
def create_optimization_job(req: OptimizationRequest, db: Session = Depends(get_db)):
    """
    Sets up the NSGA-II search and checkpoints it, but runs zero
    generations -- this call is always fast. Call POST
    /optimization/jobs/{job_id}/step repeatedly afterwards to advance it.
    """
    _validate_materials(req.material, req.ply_material)

    domain = to_domain(req.geometry)
    job = job_runner.create_job(
        db, domain, request_json=req.model_dump(),
        material_key=req.material, ply_material_key=req.ply_material,
        target_safety_factor=req.target_safety_factor, operating_tsr=req.operating_tsr,
        population_size=req.population_size, n_generations=req.n_generations, seed=req.seed,
    )
    return OptimizationJobCreateOut(
        job_id=job.id, status=job.status,
        population_size=job.population_size, n_generations=job.n_generations,
    )


@router.post("/jobs/{job_id}/step", response_model=OptimizationJobStatusOut)
def step_optimization_job(job_id: str, db: Session = Depends(get_db)):
    """
    Advances the job by as many generations as fit in ~8s of wall time,
    then returns. Safe to call repeatedly/rapidly -- a no-op once the job
    is completed or failed.
    """
    job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    job = job_runner.step_job(db, job)
    return _job_to_status_out(job)


@router.get("/jobs/{job_id}", response_model=OptimizationJobStatusOut)
def get_optimization_job(job_id: str, db: Session = Depends(get_db)):
    """Read-only status check -- does not advance the job."""
    job = db.query(OptimizationJob).filter(OptimizationJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Optimization job not found")
    return _job_to_status_out(job)