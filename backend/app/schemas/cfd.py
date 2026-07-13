from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class PanelMethodRequest(BaseModel):
    airfoil_thickness_ratio: float = Field(0.18, gt=0, le=0.4)
    alpha_deg: float = Field(5.0, ge=-25, le=25)
    n_panels: int = Field(80, ge=20, le=300)


class PanelMethodResponse(BaseModel):
    x_over_c: list[float]
    cp: list[float]
    is_upper: list[bool]
    cl: float
    cl_thin_airfoil_theory: float
    alpha_deg: float
    converged: bool


class CFDCaseRequest(BaseModel):
    geometry: HybridRotorIn
    wind_speed_ms: float = Field(8.0, gt=0, le=60)
    tip_speed_ratio: float = Field(2.25, gt=0, le=10)
    end_time_revolutions: float = Field(6.0, gt=0, le=50)


class ForceCoeffsParseRequest(BaseModel):
    file_content: str
    averaging_window_fraction: float = Field(0.25, gt=0, le=1.0)


class ForceCoeffsParseResponse(BaseModel):
    cd_mean: float
    cl_mean: float
    cm_mean: float
    n_samples_averaged: int
    averaging_window_fraction: float
    n_total_samples: int


class ValidationRequest(BaseModel):
    geometry: HybridRotorIn
    wind_speed_ms: float
    tip_speed_ratio: float
    cfd_cd_mean: float
    cfd_cl_mean: float


class ValidationResponse(BaseModel):
    bem_ct: float
    cfd_ct_equivalent: float
    percent_error: float
    bem_power_w: float
    within_engineering_tolerance: bool
    notes: str
