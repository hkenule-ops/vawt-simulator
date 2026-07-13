from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class LaminateRequest(BaseModel):
    ply_material: str = Field("CFRP_UD_PLY", description="Key from the ply material library")
    angles_deg: list[float] = Field(..., description="Ply angles in stacking order")


class LaminateResponse(BaseModel):
    total_thickness_m: float
    ex_pa: float
    ey_pa: float
    gxy_pa: float
    ex_flexural_pa: float
    density_kg_m3: float
    mass_per_area_kg_m2: float
    max_b_matrix_term: float


class CompositeOptimizeRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD_PLY")
    wind_speed_ms: float = Field(12.0, gt=0, le=60)
    tip_speed_ratio: float = Field(2.25, gt=0, le=10)
    target_safety_factor: float = Field(1.5, gt=0.5, le=10)
    boundary: str = Field("pinned-pinned", pattern="^(pinned-pinned|cantilever)$")


class OptimizedSparOut(BaseModel):
    material_key: str
    n_cap_plies: int
    n_web_pairs: int
    spar_width_fraction: float
    feasible: bool
    spar_mass_kg: float
    cap_thickness_m: float
    web_thickness_m: float
    combined_max_stress_pa: float
    safety_factor: float
    buckling_safety_factor: float
    warnings: list[str]


class CompositeCompareResponse(BaseModel):
    cfrp: OptimizedSparOut
    gfrp: OptimizedSparOut
