"""
Annual Energy Production (AEP): integrates the Stage-1 BEM power curve
against a Weibull wind-speed distribution (reusing Phase 9's wind
distribution module) to get expected annual energy output. Also reports
capacity factor, the standard normalized measure of how much of the
turbine's rated output it actually achieves on average.
"""
from __future__ import annotations
from dataclasses import dataclass

from app.geometry.models import HybridRotorGeometry
from app.aero.hybrid_solver import power_curve
from app.fatigue.wind_distribution import annual_hours_per_bin


@dataclass
class AEPResult:
    aep_kwh: float
    capacity_factor: float
    wind_bins_ms: list[float]
    energy_by_bin_kwh: list[float]
    rated_power_w: float


def compute_aep(
    geom: HybridRotorGeometry,
    weibull_k: float = 2.0,
    weibull_c: float = 7.0,
    wind_bins_ms: list[float] | None = None,
    apply_rated_power_limit: bool = True,
    system_loss_factor: float = 0.88,
    n_azimuth: int = 36,
    tsr_search_points: int = 8,
) -> AEPResult:
    """
    apply_rated_power_limit: the raw Stage-1 BEM power curve tracks maximum
    achievable aerodynamic power at each wind speed with no control system
    -- it grows well past the nameplate rated power at high wind speeds
    (e.g. ~3.5 kW at 20 m/s for a "300 W" design in this platform's default
    geometry). A real turbine limits power near its rated value above rated
    wind speed via pitch control, aerodynamic stall regulation, or
    electrical load limiting. Without a control-system model (a future
    phase), the standard idealized approximation -- power rises with wind
    speed up to rated wind speed, then flat-lines at rated power up to
    cut-out -- is applied here by default. Turning this off reproduces the
    (unrealistic, inflated) unregulated aerodynamic power curve, useful only
    for sanity-checking against the raw Stage-1 output.

    system_loss_factor: derates gross aerodynamic energy for generator/
    electrical conversion efficiency, downtime/availability, and controller
    losses -- typically 0.85-0.95 for small wind systems. Default 0.88 is a
    representative mid-range estimate, not a substitute for a real loss
    breakdown (Phase 13+ territory if a full electrical/drivetrain model is added).

    n_azimuth / tsr_search_points: BEM resolution used for each wind-speed
    bin's power-curve evaluation. Lower values trade accuracy for speed --
    used by Phase 12's optimizer, which evaluates hundreds of candidate
    designs and needs each AEP call to be fast, at the cost of some
    precision (acceptable there since it's a fast preview search, not a
    final design check).
    """
    if wind_bins_ms is None:
        wind_bins_ms = [float(v) for v in range(1, 26)]  # 1-25 m/s, covers cut-in to well past cut-out

    hours_per_bin = annual_hours_per_bin(wind_bins_ms, weibull_k, weibull_c)
    # AEP is inherently a statistical estimate (integrated against an
    # idealised Weibull distribution), so a coarser BEM search here trades a
    # small amount of precision for a large speedup -- appropriate here in a
    # way it would not be for e.g. the Phase 7 structural safety check.
    power_points = power_curve(geom, wind_bins_ms, n_azimuth=n_azimuth, tsr_search_points=tsr_search_points)

    energy_by_bin = []
    total_energy_wh = 0.0
    for v, point, hours in zip(wind_bins_ms, power_points, hours_per_bin):
        power_w = point.total_power_w if point is not None else 0.0
        if apply_rated_power_limit and v >= geom.rated_wind_speed_ms:
            power_w = min(power_w, geom.target_power_w)
        power_w *= system_loss_factor
        energy_wh = power_w * hours
        energy_by_bin.append(energy_wh / 1000.0)  # -> kWh
        total_energy_wh += energy_wh

    aep_kwh = total_energy_wh / 1000.0
    rated_power_w = geom.target_power_w
    capacity_factor = aep_kwh / (rated_power_w / 1000.0 * 8760.0) if rated_power_w > 0 else 0.0

    return AEPResult(
        aep_kwh=aep_kwh, capacity_factor=capacity_factor,
        wind_bins_ms=wind_bins_ms, energy_by_bin_kwh=energy_by_bin,
        rated_power_w=rated_power_w,
    )
