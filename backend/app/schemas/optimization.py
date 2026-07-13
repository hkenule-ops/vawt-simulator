from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class OptimizationRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD")
    ply_material: str = Field("CFRP_UD_PLY")
    target_safety_factor: float = Field(1.5, gt=0.5, le=10)
    operating_tsr: float = Field(2.25, gt=0, le=10)
    population_size: int = Field(24, ge=8, le=60)
    n_generations: int = Field(10, ge=2, le=30)
    seed: int = Field(1, ge=0)
    capture_history: bool = Field(False, description="Return per-generation Pareto front snapshots for animation")


class ParetoDesignOut(BaseModel):
    rotor_radius_m: float
    blade_height_m: float
    chord_m: float
    spar_width_fraction: float
    spar_wall_thickness_m: float
    aep_kwh: float
    lcoe_usd_per_kwh: float
    blade_mass_kg: float


class GenerationSnapshotOut(BaseModel):
    generation: int
    n_eval: int
    pareto_front: list[ParetoDesignOut]


class OptimizationResponse(BaseModel):
    pareto_front: list[ParetoDesignOut]
    n_generations: int
    population_size: int
    n_evaluated: int
    generation_history: list[GenerationSnapshotOut] = []
