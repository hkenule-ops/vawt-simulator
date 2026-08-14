from pydantic import BaseModel, Field
from app.schemas.geometry import HybridRotorIn


class GeneratorOperatingPointOut(BaseModel):
    omega_mech_rad_s: float
    rpm: float
    electrical_freq_hz: float
    mechanical_torque_nm: float
    mechanical_power_w: float
    phase_current_a: float
    back_emf_v: float
    terminal_voltage_v: float
    copper_loss_w: float
    core_loss_w: float
    electrical_power_w: float
    efficiency: float


class TorqueSpeedCurveRequest(BaseModel):
    geometry: HybridRotorIn
    rpm_max: float = Field(600.0, gt=0, le=20000)
    n_points: int = Field(30, ge=5, le=200)


class TorqueSpeedCurveResponse(BaseModel):
    points: list[GeneratorOperatingPointOut]
    cogging_ripple_frequency_hz_at_max_rpm: float


class GeneratorAnalysisRequest(BaseModel):
    geometry: HybridRotorIn
    wind_speed_ms: float = Field(..., gt=0, le=80)
    tip_speed_ratio: float = Field(2.25, gt=0, le=8)


class BreakawayCheckOut(BaseModel):
    cogging_torque_peak_nm: float
    rotor_starting_torque_nm: float
    can_break_away: bool
    margin_nm: float


class GeneratorAnalysisResponse(BaseModel):
    aero_operating_point: dict
    generator_operating_point: GeneratorOperatingPointOut
    breakaway_check: BreakawayCheckOut
    hub_height_m: float
    wind_speed_at_hub_ms: float
    warnings: list[str]