from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class ValidationRunRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD")
    ply_material: str = Field("CFRP_UD_PLY")
    operating_tsr: float = Field(2.25, gt=0, le=10)
    wind_speed_ms: float | None = None


class CheckResultOut(BaseModel):
    name: str
    passed: bool
    detail: str


class ValidationReportOut(BaseModel):
    checks: list[CheckResultOut]
    all_passed: bool
    n_passed: int
    n_total: int
