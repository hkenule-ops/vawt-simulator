from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class StructuralAnalysisRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD", description="Key from the material library")
    wind_speed_ms: float = Field(12.0, gt=0, le=60)
    tip_speed_ratio: float = Field(2.25, gt=0, le=10)
    spar_width_fraction: float = Field(0.5, gt=0.05, le=0.9)
    spar_wall_thickness_m: float = Field(0.003, gt=0.0002, le=0.05)
    boundary: str = Field("pinned-pinned", pattern="^(pinned-pinned|cantilever)$")


class BeamResultOut(BaseModel):
    x_m: list[float]
    deflection_m: list[float]
    bending_moment_nm: list[float]
    max_deflection_m: float
    max_deflection_location_m: float
    max_bending_moment_nm: float
    max_bending_stress_pa: float
    max_stress_location_m: float


class StructuralAnalysisResponse(BaseModel):
    material: str
    spar_area_m2: float
    spar_mass_kg: float
    flapwise_distributed_load_n_m: float
    edgewise_distributed_load_n_m: float
    centrifugal_distributed_load_n_m: float
    flapwise: BeamResultOut
    edgewise: BeamResultOut
    max_flapwise_stress_pa: float
    max_edgewise_stress_pa: float
    combined_max_stress_pa: float
    yield_strength_pa: float
    safety_factor: float
    euler_buckling_load_n: float
    nominal_axial_load_n: float
    buckling_safety_factor: float
    warnings: list[str]


class MaterialOut(BaseModel):
    key: str
    name: str
    density_kg_m3: float
    youngs_modulus_pa: float
    shear_modulus_pa: float
    yield_strength_pa: float
    ultimate_strength_pa: float
