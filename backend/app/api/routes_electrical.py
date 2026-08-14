from fastapi import APIRouter
from app.core.config import get_settings
from app.schemas.electrical import (
    TorqueSpeedCurveRequest, TorqueSpeedCurveResponse, GeneratorOperatingPointOut,
    GeneratorAnalysisRequest, GeneratorAnalysisResponse, BreakawayCheckOut,
)
from app.api.routes_geometry import to_domain
from app.aero.hybrid_solver import solve_hybrid_operating_point
from app.electrical.generator_model import (
    generator_operating_point, torque_speed_curve, cogging_ripple_frequency_hz, check_breakaway,
)

router = APIRouter(prefix="/generator", tags=["generator"])
settings = get_settings()


def _point_to_out(p) -> GeneratorOperatingPointOut:
    return GeneratorOperatingPointOut(**p.__dict__)


@router.post("/torque-speed-curve", response_model=TorqueSpeedCurveResponse)
def get_torque_speed_curve(req: TorqueSpeedCurveRequest):
    domain = to_domain(req.geometry)
    points = torque_speed_curve(domain.generator, req.rpm_max, req.n_points)
    return TorqueSpeedCurveResponse(
        points=[_point_to_out(p) for p in points],
        cogging_ripple_frequency_hz_at_max_rpm=cogging_ripple_frequency_hz(domain.generator, req.rpm_max),
    )


@router.post("/analyze", response_model=GeneratorAnalysisResponse)
def analyze_generator(req: GeneratorAnalysisRequest):
    domain = to_domain(req.geometry)
    warnings = domain.validate()

    v_hub = domain.wind_speed_at_hub(req.wind_speed_ms)
    aero_point = solve_hybrid_operating_point(
        domain, v_hub, req.tip_speed_ratio, n_azimuth=settings.default_azimuth_stations,
    )
    omega = req.tip_speed_ratio * v_hub / domain.darrieus.rotor_radius_m
    gen_point = generator_operating_point(domain.generator, aero_point.total_torque_nm, omega)

    # Starting-torque check at a low, near-standstill TSR at this wind speed,
    # to see whether cogging torque would prevent breakaway from rest.
    starting_point = solve_hybrid_operating_point(
        domain, v_hub, 0.15, n_azimuth=settings.default_azimuth_stations,
    )
    breakaway = check_breakaway(domain.generator, starting_point.total_torque_nm)
    if not breakaway.can_break_away:
        warnings.append(
            f"Generator cogging torque ({breakaway.cogging_torque_peak_nm:.3f} Nm) exceeds the "
            f"rotor's starting torque ({breakaway.rotor_starting_torque_nm:.3f} Nm) at "
            f"{req.wind_speed_ms:.1f} m/s -- the rotor may not break away from rest without an "
            f"assisted start (Savonius stage helps here) or a lower-cogging generator."
        )
    if not aero_point.converged:
        warnings.append("BEM solver did not fully converge at this operating point; results may be approximate.")

    return GeneratorAnalysisResponse(
        aero_operating_point=aero_point.__dict__,
        generator_operating_point=_point_to_out(gen_point),
        breakaway_check=BreakawayCheckOut(**breakaway.__dict__),
        hub_height_m=domain.hub_height_m,
        wind_speed_at_hub_ms=v_hub,
        warnings=warnings,
    )