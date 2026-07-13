from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class ReportRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD")
    ply_material: str = Field("CFRP_UD_PLY")
    wind_speed_ms: float | None = Field(None, description="Defaults to the design's rated wind speed")
    operating_tsr: float = Field(2.25, gt=0, le=10)
