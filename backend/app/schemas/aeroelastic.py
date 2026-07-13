from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class AeroelasticAnalysisRequest(BaseModel):
    geometry: HybridRotorIn
    material: str = Field("CFRP_UD")
    operating_tsr: float = Field(2.25, gt=0, le=10)
    spar_width_fraction: float = Field(0.5, gt=0.05, le=0.9)
    spar_wall_thickness_m: float = Field(0.003, gt=0.0002, le=0.05)
    boundary: str = Field("pinned-pinned", pattern="^(pinned-pinned|cantilever)$")
    n_modes: int = Field(4, ge=1, le=8)


class ModalResultOut(BaseModel):
    natural_frequencies_hz: list[float]
    mode_shapes: list[list[float]]
    x_m: list[float]


class ResonanceRiskOut(BaseModel):
    mode_number: int
    natural_frequency_hz: float
    harmonic_number: int
    excitation_rpm: float
    margin_percent: float


class CampbellResultOut(BaseModel):
    rpm_range: list[float]
    natural_frequencies_hz: list[float]
    excitation_lines_hz: dict[str, list[float]]
    resonance_risks: list[ResonanceRiskOut]


class HarmonicContentOut(BaseModel):
    harmonic_number: list[int]
    amplitude_n_m: list[float]
    dominant_harmonics: list[int]


class AeroelasticAnalysisResponse(BaseModel):
    modal: ModalResultOut
    campbell: CampbellResultOut
    harmonics: HarmonicContentOut
    operating_rpm_min: float
    operating_rpm_max: float
    warnings: list[str]
