from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class FatigueAnalysisRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD", description="Isotropic material key (app.structural.materials)")
    ply_material: str = Field("CFRP_UD_PLY", description="Ply material key for the S-N curve exponent")
    operating_tsr: float = Field(2.25, gt=0, le=10)
    spar_width_fraction: float = Field(0.5, gt=0.05, le=0.9)
    spar_wall_thickness_m: float = Field(0.003, gt=0.0002, le=0.05)
    weibull_k: float = Field(2.0, gt=0.5, le=5.0)
    weibull_c: float = Field(7.0, gt=1.0, le=25.0)
    boundary: str = Field("pinned-pinned", pattern="^(pinned-pinned|cantilever)$")


class FatigueAnalysisResponse(BaseModel):
    annual_damage: float
    estimated_life_years: float
    dominant_stress_range_pa: float
    total_cycles_per_year: float
    wind_bins_ms: list[float]
    damage_by_bin: list[float]
    warnings: list[str]
