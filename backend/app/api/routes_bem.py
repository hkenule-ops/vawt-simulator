from fastapi import APIRouter
from app.core.config import get_settings
from app.schemas.aero import (
    CpLambdaRequest, CpLambdaResponse, HybridOperatingPointOut,
    PowerCurveRequest, PowerCurveResponse, PowerCurvePoint,
)
from app.api.routes_geometry import to_domain
from app.aero.hybrid_solver import cp_lambda_curve, power_curve

router = APIRouter(prefix="/bem", tags=["bem"])
settings = get_settings()


def _to_out(p) -> HybridOperatingPointOut:
    return HybridOperatingPointOut(**p.__dict__)


@router.post("/cp-lambda", response_model=CpLambdaResponse)
def get_cp_lambda_curve(req: CpLambdaRequest):
    domain = to_domain(req.geometry)
    warnings = domain.validate()
    points = cp_lambda_curve(
        domain, req.wind_speed_ms, req.tsr_min, req.tsr_max, req.n_points,
        n_azimuth=settings.default_azimuth_stations,
    )
    if any(p.system_cp > 0.593 for p in points):
        warnings.append(
            "One or more points exceed the Betz limit (Cp>0.593) -- check solidity/geometry inputs."
        )
    return CpLambdaResponse(points=[_to_out(p) for p in points], warnings=warnings)


@router.post("/power-curve", response_model=PowerCurveResponse)
def get_power_curve(req: PowerCurveRequest):
    domain = to_domain(req.geometry)
    warnings = domain.validate()
    results = power_curve(domain, req.wind_speeds_ms, n_azimuth=settings.default_azimuth_stations)

    curve = []
    rated_power, rated_speed = None, None
    for v, p in zip(req.wind_speeds_ms, results):
        if p is None:
            curve.append(PowerCurvePoint(wind_speed_ms=v, operating_point=None))
            continue
        curve.append(PowerCurvePoint(wind_speed_ms=v, operating_point=_to_out(p)))
        if rated_power is None or p.total_power_w > rated_power:
            rated_power, rated_speed = p.total_power_w, v

    target = req.geometry.target_power_w
    if rated_power is not None and abs(rated_power - target) / target > 0.5:
        warnings.append(
            f"Peak predicted power ({rated_power:.0f} W) is more than 50% off the "
            f"target ({target:.0f} W) across the swept wind-speed range -- consider "
            f"adjusting rotor radius, blade height, or chord."
        )

    return PowerCurveResponse(
        curve=curve, warnings=warnings, rated_power_w=rated_power, rated_wind_speed_ms=rated_speed
    )
