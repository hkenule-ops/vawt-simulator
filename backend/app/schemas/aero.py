from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class CpLambdaRequest(BaseModel):
    geometry: HybridRotorIn
    wind_speed_ms: float = Field(8.0, gt=0, le=60)
    tsr_min: float = Field(0.5, gt=0, le=10)
    tsr_max: float = Field(5.0, gt=0, le=15)
    n_points: int = Field(25, ge=3, le=200)


class HybridOperatingPointOut(BaseModel):
    wind_speed_ms: float
    tip_speed_ratio: float
    darrieus_power_w: float
    savonius_power_w: float
    total_power_w: float
    total_torque_nm: float
    system_cp: float
    darrieus_cp: float
    savonius_cp: float
    darrieus_max_aoa_deg: float
    induction_factor: float
    converged: bool


class CpLambdaResponse(BaseModel):
    points: list[HybridOperatingPointOut]
    warnings: list[str] = []


class PowerCurveRequest(BaseModel):
    geometry: HybridRotorIn
    wind_speeds_ms: list[float] = Field(
        default_factory=lambda: [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    )


class PowerCurvePoint(BaseModel):
    wind_speed_ms: float
    operating_point: HybridOperatingPointOut | None


class PowerCurveResponse(BaseModel):
    curve: list[PowerCurvePoint]
    warnings: list[str] = []
    rated_power_w: float | None = None
    rated_wind_speed_ms: float | None = None
