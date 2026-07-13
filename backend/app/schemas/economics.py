from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class EconomicAnalysisRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD", description="Isotropic material key (for spar mass estimate)")
    ply_material: str = Field("CFRP_UD_PLY", description="Ply material key (for cost lookup)")
    spar_width_fraction: float = Field(0.5, gt=0.05, le=0.9)
    spar_wall_thickness_m: float = Field(0.003, gt=0.0002, le=0.05)
    electricity_price_usd_per_kwh: float = Field(0.15, gt=0, le=2.0)
    discount_rate: float = Field(0.06, ge=0, le=0.5)
    project_lifetime_years: int = Field(20, ge=1, le=50)
    weibull_k: float = Field(2.0, gt=0.5, le=5.0)
    weibull_c: float = Field(7.0, gt=1.0, le=25.0)
    opex_fraction_of_capex: float = Field(0.02, ge=0, le=0.2)


class AEPResultOut(BaseModel):
    aep_kwh: float
    capacity_factor: float
    wind_bins_ms: list[float]
    energy_by_bin_kwh: list[float]
    rated_power_w: float


class CapexBreakdownOut(BaseModel):
    blade_material_cost_usd: float
    blade_fabrication_cost_usd: float
    generator_electronics_cost_usd: float
    tower_foundation_cost_usd: float
    installation_cost_usd: float
    total_capex_usd: float


class EconomicAnalysisResponse(BaseModel):
    aep: AEPResultOut
    capex: CapexBreakdownOut
    annual_opex_usd: float
    lcoe_usd_per_kwh: float
    npv_usd: float
    irr: float | None
    simple_payback_years: float
    annual_revenue_usd: float
    warnings: list[str]
