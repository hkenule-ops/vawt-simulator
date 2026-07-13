"""
Stage 1 solver for the Savonius (drag-type) portion of the hybrid rotor.

Savonius rotors are drag-driven and dominated by 3D end effects, bucket
overlap, and dynamic stall on the returning bucket -- none of which a simple
blade-element model captures well without empirical corrections. The
established fast-engineering approach (used for exactly this reason in most
hybrid-VAWT sizing studies, e.g. Bhuyan & Biswas 2013, Kacprzak et al. 2013)
is a validated empirical Cp(lambda) correlation, corrected for overlap ratio,
rather than a first-principles solve. That empirical model is what Stage 1
uses here.

Stage 2 (CFD) directly resolves the real 3D separated flow and supersedes
this correlation for the Pareto-optimal candidates.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

from app.geometry.models import SavoniusBucketGeometry

RHO_AIR = 1.225


@dataclass
class SavoniusOperatingPoint:
    wind_speed_ms: float
    tip_speed_ratio: float
    power_w: float
    torque_nm: float
    cp: float


def _cp_max_and_lambda_opt(overlap_ratio: float) -> tuple[float, float]:
    """
    Peak Cp and the TSR at which it occurs, as a function of overlap ratio.
    Fitted to the commonly-cited experimental trend (peak Cp ~0.15-0.30 for
    e/d in 0.0-0.3, optimum lambda ~0.7-1.0) e.g. Fujisawa (1992), Akwa et al.
    (2012) review of Savonius performance. This is a coarse engineering fit,
    intentionally simple for Stage 1 speed; documented as a calibration point
    for future replacement with a validated lookup table or CFD-fit surrogate.
    """
    cp_max = 0.155 + 0.55 * overlap_ratio - 1.1 * overlap_ratio ** 2
    cp_max = max(0.10, min(cp_max, 0.24))
    lambda_opt = 0.75 + 0.25 * overlap_ratio
    return cp_max, lambda_opt


def solve_savonius_operating_point(
    geom: SavoniusBucketGeometry,
    wind_speed_ms: float,
    tip_speed_ratio: float,
) -> SavoniusOperatingPoint:
    A = geom.swept_area_m2
    cp_max, lambda_opt = _cp_max_and_lambda_opt(geom.overlap_ratio)
    width = 0.9  # half-width of the Cp(lambda) parabola, calibrated to typical curves

    x = (tip_speed_ratio - lambda_opt) / width
    cp = cp_max * max(0.0, 1 - x ** 2)

    power_w = cp * 0.5 * RHO_AIR * A * wind_speed_ms ** 3
    omega = tip_speed_ratio * wind_speed_ms / (geom.rotor_diameter_m / 2)
    torque_nm = power_w / omega if omega > 1e-6 else 0.0

    return SavoniusOperatingPoint(
        wind_speed_ms=wind_speed_ms,
        tip_speed_ratio=tip_speed_ratio,
        power_w=power_w,
        torque_nm=torque_nm,
        cp=cp,
    )
