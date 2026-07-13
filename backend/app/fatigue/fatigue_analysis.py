"""
Phase 9 top-level fatigue analysis. Ties together:
  1. The per-revolution azimuthal normal-force trace from the Stage-1 BEM
     solver (the dominant VAWT fatigue driver -- one stress cycle per
     rotation, not slow turbulence-driven fluctuation as in a HAWT).
  2. A "stress per unit distributed load" scale factor, derived once from
     a unit-load beam FEM solve (the beam problem is linear, so this avoids
     re-running the FEM at every azimuth angle/wind-speed bin).
  3. Rainflow counting of the resulting stress trace at each wind-speed bin.
  4. A Weibull wind distribution to weight how many revolutions/year occur
     at each bin.
  5. Miner's rule, summed across all bins and cycles, for annual damage and
     an estimated fatigue life in years.

Scope notes (consistent with this platform's incremental, documented-
simplification approach throughout):
  - Operating TSR is held constant across all wind speed bins (a fixed-TSR
    control assumption) rather than re-running an MPPT search per bin --
    reasonable for small, simply-controlled VAWTs, but a simplification
    worth knowing about.
  - Only the aerodynamic normal-force cycle is treated as time-varying
    within a revolution; centrifugal load is constant at fixed RPM and
    enters only as a mean-stress offset, not a cyclic component.
  - This is not a full IEC 61400-2 Design Load Case (DLC) table (which
    includes extreme gusts, start/stop transients, grid loss, etc.) -- it
    implements the rainflow + Weibull + Miner's-rule core that the IEC
    fatigue methodology is built on, applied to the single dominant DLC 1.1
    "normal operation" load case.
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from app.geometry.models import HybridRotorGeometry
from app.aero.darrieus_bem import compute_normal_force_azimuthal_trace
from app.structural.beam_fem import solve_beam_udl
from app.fatigue.rainflow import count_cycles, RainflowCycle
from app.fatigue.sn_curve import get_sn_curve, SNCurve
from app.fatigue.miners_rule import compute_miners_damage, DamageResult
from app.fatigue.wind_distribution import annual_hours_per_bin

RHO_AIR = 1.225


@dataclass
class FatigueResult:
    annual_damage: float
    estimated_life_years: float
    dominant_stress_range_pa: float
    total_cycles_per_year: float
    wind_bins_ms: list[float]
    damage_by_bin: list[float]
    warnings: list[str]


def _stress_per_unit_udl(
    span_m: float, EI: float, c_m: float, i_m4: float,
    boundary: str, n_elements: int = 40,
) -> float:
    """Peak bending stress produced by a 1 N/m uniform distributed load -- used to linearly
    scale the azimuthal force trace into a stress trace without re-solving the FEM per point."""
    fem = solve_beam_udl(span_m, EI, 1.0, n_elements=n_elements, boundary=boundary)
    return abs(fem.max_bending_moment_nm) * c_m / i_m4 if i_m4 > 0 else 0.0


def analyze_blade_fatigue(
    geom: HybridRotorGeometry,
    ei_flapwise: float,
    section_i_m4: float,
    section_c_m: float,
    static_strength_pa: float,
    ply_material_key: str,
    operating_tsr: float,
    weibull_k: float = 2.0,
    weibull_c: float = 7.0,
    wind_bins_ms: list[float] | None = None,
    boundary: str = "pinned-pinned",
    n_azimuth: int = 144,
) -> FatigueResult:
    d = geom.darrieus
    if wind_bins_ms is None:
        wind_bins_ms = [float(v) for v in range(
            int(geom.cut_in_wind_speed_ms), int(geom.cut_out_wind_speed_ms) + 1
        )]

    stress_per_udl = _stress_per_unit_udl(
        d.blade_height_m, ei_flapwise, section_c_m, section_i_m4, boundary,
    )

    sn_curve = get_sn_curve(ply_material_key, static_strength_pa)
    hours_per_bin = annual_hours_per_bin(wind_bins_ms, weibull_k, weibull_c)

    total_damage = 0.0
    damage_by_bin: list[float] = []
    dominant_range = 0.0
    total_cycles_per_year = 0.0
    warnings: list[str] = []

    for v, hours in zip(wind_bins_ms, hours_per_bin):
        if v < geom.cut_in_wind_speed_ms or v > geom.cut_out_wind_speed_ms or hours <= 0:
            damage_by_bin.append(0.0)
            continue

        omega = operating_tsr * v / d.rotor_radius_m
        revolutions_per_year = omega / (2 * np.pi) * hours * 3600.0

        fn_trace = compute_normal_force_azimuthal_trace(d, v, operating_tsr, n_azimuth=n_azimuth)
        stress_trace = fn_trace * stress_per_udl

        cycles = count_cycles(list(stress_trace))
        # Scale each cycle's count by how many revolutions occur per year at this bin --
        # the rainflow trace covers exactly one revolution, so this converts
        # "cycles per revolution" into "cycles per year" for this bin.
        scaled_cycles = [RainflowCycle(range_=c.range_, mean=c.mean, count=c.count * revolutions_per_year)
                          for c in cycles]

        bin_damage_result = compute_miners_damage(scaled_cycles, sn_curve)
        damage_by_bin.append(bin_damage_result.total_damage)
        total_damage += bin_damage_result.total_damage
        total_cycles_per_year += bin_damage_result.n_cycles_considered

        if cycles:
            dominant_range = max(dominant_range, max(c.range_ for c in cycles))

    estimated_life_years = 1.0 / total_damage if total_damage > 0 else float("inf")

    if estimated_life_years < 20:
        warnings.append(
            f"Estimated fatigue life ({estimated_life_years:.1f} years) is below the common "
            f"20-year design target for wind turbine blades -- increase spar sizing or "
            f"reconsider material/layup."
        )
    warnings.append(
        "Fixed-TSR control assumption used across all wind speed bins (not a full MPPT "
        "TSR schedule); centrifugal load treated as mean-stress offset only, not cyclic. "
        "Not a full IEC 61400-2 DLC table -- see module docstring."
    )

    return FatigueResult(
        annual_damage=total_damage,
        estimated_life_years=min(estimated_life_years, 1e6),
        dominant_stress_range_pa=dominant_range,
        total_cycles_per_year=total_cycles_per_year,
        wind_bins_ms=wind_bins_ms,
        damage_by_bin=damage_by_bin,
        warnings=warnings,
    )
