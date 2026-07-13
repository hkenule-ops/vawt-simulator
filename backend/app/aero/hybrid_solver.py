"""
Combines the Darrieus (lift-type) and Savonius (drag-type) Stage-1 solvers
into a single hybrid-rotor performance model.

Both sub-rotors are mounted on the same shaft, so they share angular velocity
Omega, but each has its own radius and therefore its own local tip-speed
ratio. Power superposes directly; Cp does not (different reference areas), so
we report an overall system Cp normalised to the Darrieus swept area, which
is the convention used in the hybrid-VAWT literature this platform targets
(see geometry.models.HybridRotorGeometry.total_swept_area_m2 docstring).
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from app.geometry.models import HybridRotorGeometry
from app.aero.darrieus_bem import solve_darrieus_operating_point, RHO_AIR
from app.aero.savonius_model import solve_savonius_operating_point


@dataclass
class HybridOperatingPoint:
    wind_speed_ms: float
    tip_speed_ratio: float          # defined w.r.t. Darrieus radius (system reference)
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


def solve_hybrid_operating_point(
    geom: HybridRotorGeometry, wind_speed_ms: float, tip_speed_ratio: float,
    n_azimuth: int = 72,
) -> HybridOperatingPoint:
    d_point = solve_darrieus_operating_point(
        geom.darrieus, wind_speed_ms, tip_speed_ratio, n_azimuth=n_azimuth
    )
    omega = tip_speed_ratio * wind_speed_ms / geom.darrieus.rotor_radius_m
    savonius_radius = geom.savonius.rotor_diameter_m / 2
    lambda_savonius = omega * savonius_radius / wind_speed_ms
    s_point = solve_savonius_operating_point(geom.savonius, wind_speed_ms, lambda_savonius)

    total_power = d_point.power_w + s_point.power_w
    total_torque = total_power / omega if omega > 1e-6 else 0.0
    A_ref = geom.total_swept_area_m2
    system_cp = total_power / (0.5 * RHO_AIR * A_ref * wind_speed_ms ** 3)

    return HybridOperatingPoint(
        wind_speed_ms=wind_speed_ms,
        tip_speed_ratio=tip_speed_ratio,
        darrieus_power_w=d_point.power_w,
        savonius_power_w=s_point.power_w,
        total_power_w=total_power,
        total_torque_nm=total_torque,
        system_cp=system_cp,
        darrieus_cp=d_point.cp,
        savonius_cp=s_point.cp,
        darrieus_max_aoa_deg=d_point.max_angle_of_attack_deg,
        induction_factor=d_point.induction_factor,
        converged=d_point.converged,
    )


def cp_lambda_curve(geom: HybridRotorGeometry, wind_speed_ms: float,
                     tsr_min: float = 0.5, tsr_max: float = 5.0, n_points: int = 25,
                     n_azimuth: int = 60):
    tsrs = np.linspace(tsr_min, tsr_max, n_points)
    return [solve_hybrid_operating_point(geom, wind_speed_ms, float(l), n_azimuth=n_azimuth)
            for l in tsrs]


def power_curve(geom: HybridRotorGeometry, wind_speeds_ms: list[float],
                 n_azimuth: int = 60, tsr_search_points: int = 15):
    """
    For each wind speed, find the best operating TSR (max power) within a
    plausible search band, then return that best operating point. This
    mimics an ideal MPPT (maximum power point tracking) controller, which is
    the standard assumption for a first-pass power curve before the control
    system design phase.
    """
    results = []
    for v in wind_speeds_ms:
        if v < geom.cut_in_wind_speed_ms or v > geom.cut_out_wind_speed_ms:
            results.append(None)
            continue
        tsrs = np.linspace(1.0, 4.5, tsr_search_points)
        points = [solve_hybrid_operating_point(geom, v, float(l), n_azimuth=n_azimuth) for l in tsrs]
        best = max(points, key=lambda p: p.total_power_w)
        results.append(best)
    return results
