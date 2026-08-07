"""
Stage 1 aerodynamic solver for the Darrieus (lift-type) portion of the hybrid
rotor: a single-streamtube momentum model (Templin, 1974 style), which is the
standard "fast" first-pass model used before committing to the much more
expensive Double-Multiple Streamtube (DMST) or CFD stages.

Why single-streamtube for Stage 1:
    - O(azimuth_stations) cost per candidate design -> can evaluate thousands
      of geometries per second for the multi-objective optimiser (Phase 12).
    - Captures the core physics: blade-element loads (via airfoil polars),
      momentum-balanced induction factor, torque/power integrated over one
      revolution.
    - Known to over-predict Cp somewhat vs DMST/CFD at high solidity; Stage 2
      (CFD) and a future DMST module correct this. The `AeroModel` interface
      below is the seam where DMST/Actuator Cylinder models plug in later
      without touching the optimiser or API layer.

Reference formulation: Islam, M., Ting, D.S.-K., Fartaj, A. (2008),
"Aerodynamic models for Darrieus-type straight-bladed vertical axis wind
turbines", Renewable and Sustainable Energy Reviews 12(4), and Templin, R.J.
(1974) NRC single streamtube model.

Spanwise twist/helical support (Phase 14): a straight blade is aerodynamically
uniform along its span, so the original model correctly treated the whole
blade height as one lumped 2D element. A twisted or helical blade is not
uniform along the span, so this module now optionally discretises the blade
into `n_span_stations` elements (see `app.geometry.models.spanwise_stations`)
and integrates each one separately:
    - Local twist changes each station's effective angle of attack directly,
      so it changes the revolution-averaged torque/power -- a real
      aerodynamic effect, not just cosmetic geometry.
    - Local helical azimuth offset is a per-station phase shift. Because the
      induction factor and mean torque are already averaged over a full
      revolution, a constant phase shift leaves the *mean* essentially
      unchanged (as expected physically -- helical/eggbeater rotors are used
      to smooth torque ripple, not to raise mean Cp). It does change the
      *instantaneous* combined-station torque trace, which is what actually
      matters for self-starting and fatigue, so `compute_normal_force_azimuthal_trace`
      and `compute_blade_spanwise_loads` apply it when summing station traces.

When `twist_angle_deg == 0` and `helical_twist_deg == 0` (the pre-existing
default), `n_span_stations` auto-resolves to 1 and every function below
reproduces the original straight-blade results exactly, so existing callers
(structural sizing, AEP sweeps, the fast optimiser loop) are unaffected.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import brentq

from app.geometry.models import DarrieusBladeGeometry, spanwise_stations
from app.aero.airfoil import get_airfoil, AirfoilPolar

RHO_AIR = 1.225  # kg/m^3, sea level standard


@dataclass
class DarrieusOperatingPoint:
    wind_speed_ms: float
    tip_speed_ratio: float          # lambda = Omega*R / V_inf
    power_w: float
    torque_nm: float
    cp: float
    ct_thrust_coeff: float          # rotor thrust coefficient
    induction_factor: float
    converged: bool
    max_angle_of_attack_deg: float  # diagnostic: flags heavy stall


def _resolve_n_span_stations(geom: DarrieusBladeGeometry, requested: int | None) -> int:
    """
    Straight blades (twist=helical=0, the historical default) always use a
    single lumped station -- exact match to the original model, full speed
    for the optimiser's inner loop. Twisted/helical blades default to 6
    stations, enough to resolve a linear spanwise distribution without
    materially slowing down interactive use.
    """
    if requested is not None:
        return max(1, requested)
    if geom.twist_angle_deg == 0.0 and geom.helical_twist_deg == 0.0:
        return 1
    return 6


def _blade_element_integrand(theta: np.ndarray, Ue: float, omega_r: float,
                              chord: float, height: float, polar: AirfoilPolar,
                              twist_rad: float = 0.0):
    """
    Vectorised blade-element force calc at an array of azimuth angles theta.
    theta is measured such that the blade is directly upwind at theta=0.

    Velocity triangle (Paraschivoiu convention):
        W_chordwise = omega*R + Ue*sin(theta)   [flow component the blade "cuts into"]
        W_normal    = Ue*cos(theta)             [cross-chord component -> sets AoA]
    giving W/Ue = sqrt(lambda^2 + 2*lambda*sin(theta) + 1), tan(alpha) = cos(theta)/(lambda+sin(theta)),
    which matches the standard single-streamtube Darrieus formulation.

    `twist_rad` is this station's local geometric pitch relative to the root
    chord (see `app.geometry.models.spanwise_stations`). Twist reorients the
    blade's chordline relative to the relative-wind vector without changing
    the relative-wind kinematics itself, so it's applied as a pure additive
    offset to the aerodynamic angle of attack -- W (and therefore dynamic
    pressure) stays a function of the rotor kinematics only.
    """
    Wc = omega_r + Ue * np.sin(theta)
    Wn = Ue * np.cos(theta)
    W2 = Wc ** 2 + Wn ** 2
    alpha = np.arctan2(Wn, Wc) + twist_rad

    cl = np.empty_like(theta)
    cd = np.empty_like(theta)
    for i, a in enumerate(alpha):
        cl[i], cd[i] = polar.cl_cd(a)

    q = 0.5 * RHO_AIR * W2 * chord  # dynamic-pressure * chord, per unit span
    Ct = cl * np.sin(alpha) - cd * np.cos(alpha)   # tangential (torque-driving)
    Cn = cl * np.cos(alpha) + cd * np.sin(alpha)   # radial (normal)

    Ft = q * Ct * height   # tangential force, full element height
    Fn = q * Cn * height   # radial force, full element height
    Fx = Fn * np.cos(theta) - Ft * np.sin(theta)   # streamwise (thrust) component

    return Ft, Fn, Fx, alpha


def solve_darrieus_operating_point(
    geom: DarrieusBladeGeometry,
    wind_speed_ms: float,
    tip_speed_ratio: float,
    n_azimuth: int = 72,
    n_span_stations: int | None = None,
) -> DarrieusOperatingPoint:
    """
    Solve for the induction factor `a` such that blade-element thrust equals
    momentum-theory thrust, then integrate torque/power over one revolution.

    For a twisted blade, each spanwise station is solved at the same shared
    induction factor `a` (single-streamtube assumption: one streamtube per
    azimuth, not per span station -- consistent with the Stage-1 fidelity
    level; a spanwise-varying induction factor is a DMST/Stage-2+ refinement).
    """
    polar = get_airfoil(geom.airfoil)
    R = geom.rotor_radius_m
    c = geom.chord_m
    N = geom.num_blades
    V_inf = wind_speed_ms
    omega = tip_speed_ratio * V_inf / R
    omega_r = omega * R
    A = geom.swept_area_m2
    theta = np.linspace(0, 2 * np.pi, n_azimuth, endpoint=False)

    n_stations = _resolve_n_span_stations(geom, n_span_stations)
    stations = spanwise_stations(geom, n_stations)

    def _station_mean_ft_fx(Ue: float):
        """Sum of per-station mean tangential/thrust force across the span, one blade."""
        ft_sum, fx_sum = 0.0, 0.0
        max_alpha = 0.0
        for st in stations:
            twist_rad = math.radians(st.local_twist_deg)
            Ft, _, Fx, alpha = _blade_element_integrand(
                theta, Ue, omega_r, c, st.height_m, polar, twist_rad=twist_rad
            )
            ft_sum += float(np.mean(Ft))
            fx_sum += float(np.mean(Fx))
            max_alpha = max(max_alpha, float(np.max(np.abs(alpha))))
        return ft_sum, fx_sum, max_alpha

    def thrust_residual(a: float) -> float:
        a = min(max(a, 0.0), 0.95)
        Ue = V_inf * (1 - a)
        _, fx_sum, _ = _station_mean_ft_fx(Ue)
        T_blade_element = N * fx_sum
        T_momentum = 2 * RHO_AIR * A * V_inf ** 2 * a * (1 - a)
        return T_blade_element - T_momentum

    # Bracket and solve for induction factor. Momentum theory is only valid
    # for a < ~0.4-0.5 (beyond that, empirical corrections like Glauert's
    # would be needed -- flagged via `converged=False` if we hit the bound).
    converged = True
    try:
        a_lo, a_hi = 1e-4, 0.5
        if thrust_residual(a_lo) * thrust_residual(a_hi) > 0:
            # No sign change: rotor is very lightly loaded (low solidity) or
            # heavily stalled. Fall back to a coarse scan for the closest root.
            a_scan = np.linspace(1e-4, 0.6, 60)
            residuals = [thrust_residual(a) for a in a_scan]
            idx = int(np.argmin(np.abs(residuals)))
            a_sol = a_scan[idx]
            converged = abs(residuals[idx]) < 0.05 * max(abs(r) for r in residuals) + 1.0
        else:
            a_sol = brentq(thrust_residual, a_lo, a_hi, xtol=1e-5)
    except Exception:
        a_sol = 0.15
        converged = False

    Ue = V_inf * (1 - a_sol)
    ft_sum, fx_sum, max_alpha = _station_mean_ft_fx(Ue)
    torque_per_blade_avg = ft_sum * R
    total_torque = N * torque_per_blade_avg
    power_w = total_torque * omega
    cp = power_w / (0.5 * RHO_AIR * A * V_inf ** 3)
    thrust_total = N * fx_sum
    ct_thrust = thrust_total / (0.5 * RHO_AIR * A * V_inf ** 2)
    max_aoa_deg = math.degrees(max_alpha)

    return DarrieusOperatingPoint(
        wind_speed_ms=wind_speed_ms,
        tip_speed_ratio=tip_speed_ratio,
        power_w=power_w,
        torque_nm=total_torque,
        cp=cp,
        ct_thrust_coeff=ct_thrust,
        induction_factor=float(a_sol),
        converged=bool(converged),
        max_angle_of_attack_deg=max_aoa_deg,
    )


def sweep_tsr(geom: DarrieusBladeGeometry, wind_speed_ms: float,
              tsr_min: float = 0.5, tsr_max: float = 5.0, n_points: int = 25):
    """Cp-lambda curve at a fixed wind speed -- the standard first plot for any VAWT design."""
    tsrs = np.linspace(tsr_min, tsr_max, n_points)
    return [solve_darrieus_operating_point(geom, wind_speed_ms, float(l)) for l in tsrs]


def compute_normal_force_azimuthal_trace(
    geom: DarrieusBladeGeometry, wind_speed_ms: float, tip_speed_ratio: float,
    n_azimuth: int = 144, n_span_stations: int | None = None,
) -> np.ndarray:
    """
    Returns the per-unit-span radial/normal force Fn(theta)/H over one full
    revolution (n_azimuth points), at the converged induction factor. This
    is the fundamental fatigue-driving signal for a Darrieus blade: unlike a
    HAWT blade (which sees comparatively steady loading with slower,
    turbulence-driven fluctuations), a VAWT blade's angle of attack -- and
    therefore its bending load -- swings through a large range every single
    revolution, giving one full stress cycle per rotation as the dominant
    fatigue driver (Phase 9).

    For a helical blade, each spanwise station is physically offset in
    azimuth (see `spanwise_stations`), so its instantaneous contribution is
    evaluated at `theta + local_azimuth_offset` before the stations are
    combined -- this is what actually captures the torque/load-ripple
    smoothing a helical blade is built for, even though the revolution-mean
    barely changes.
    """
    op = solve_darrieus_operating_point(
        geom, wind_speed_ms, tip_speed_ratio, n_azimuth=n_azimuth, n_span_stations=n_span_stations,
    )
    polar = get_airfoil(geom.airfoil)
    omega_r = tip_speed_ratio * wind_speed_ms
    Ue = wind_speed_ms * (1 - op.induction_factor)
    theta = np.linspace(0, 2 * np.pi, n_azimuth, endpoint=False)

    n_stations = _resolve_n_span_stations(geom, n_span_stations)
    stations = spanwise_stations(geom, n_stations)

    H = geom.blade_height_m
    Fn_total = np.zeros_like(theta)
    for st in stations:
        twist_rad = math.radians(st.local_twist_deg)
        offset_rad = math.radians(st.local_azimuth_offset_deg)
        _, Fn_station, _, _ = _blade_element_integrand(
            theta + offset_rad, Ue, omega_r, geom.chord_m, st.height_m, polar, twist_rad=twist_rad
        )
        Fn_total += Fn_station

    return Fn_total / H


@dataclass
class BladeSpanwiseLoads:
    """Per-unit-span force envelope over one revolution, for structural sizing (Phase 7)."""
    peak_normal_force_per_span_n_m: float   # max |Fn|/H over azimuth -- flapwise design load
    peak_tangential_force_per_span_n_m: float  # max |Ft|/H over azimuth -- edgewise design load
    mean_normal_force_per_span_n_m: float
    mean_tangential_force_per_span_n_m: float


def compute_blade_spanwise_loads(
    geom: DarrieusBladeGeometry, wind_speed_ms: float, tip_speed_ratio: float,
    n_azimuth: int = 144, n_span_stations: int | None = None,
) -> BladeSpanwiseLoads:
    """
    Re-runs the blade-element azimuthal sweep at the converged induction
    factor and returns per-unit-span force envelopes, used as the design
    loads for the Phase 7 structural beam FEA. Peak (not mean) values are
    used for static structural sizing -- the standard conservative practice,
    since a blade must survive its worst instantaneous load each revolution,
    not just the revolution-averaged one that the power/torque calculation cares about.

    Twisted/helical stations are combined the same way as
    `compute_normal_force_azimuthal_trace` (span-summed, helical stations
    phase-shifted before summing) so the structural design loads reflect the
    actual combined-blade envelope, not just the root station's.
    """
    op = solve_darrieus_operating_point(
        geom, wind_speed_ms, tip_speed_ratio, n_azimuth=n_azimuth, n_span_stations=n_span_stations,
    )
    polar = get_airfoil(geom.airfoil)
    omega_r = tip_speed_ratio * wind_speed_ms
    Ue = wind_speed_ms * (1 - op.induction_factor)
    theta = np.linspace(0, 2 * np.pi, n_azimuth, endpoint=False)

    n_stations = _resolve_n_span_stations(geom, n_span_stations)
    stations = spanwise_stations(geom, n_stations)

    H = geom.blade_height_m
    Ft_total = np.zeros_like(theta)
    Fn_total = np.zeros_like(theta)
    for st in stations:
        twist_rad = math.radians(st.local_twist_deg)
        offset_rad = math.radians(st.local_azimuth_offset_deg)
        Ft_station, Fn_station, _, _ = _blade_element_integrand(
            theta + offset_rad, Ue, omega_r, geom.chord_m, st.height_m, polar, twist_rad=twist_rad
        )
        Ft_total += Ft_station
        Fn_total += Fn_station

    return BladeSpanwiseLoads(
        peak_normal_force_per_span_n_m=float(np.max(np.abs(Fn_total))) / H,
        peak_tangential_force_per_span_n_m=float(np.max(np.abs(Ft_total))) / H,
        mean_normal_force_per_span_n_m=float(np.mean(np.abs(Fn_total))) / H,
        mean_tangential_force_per_span_n_m=float(np.mean(np.abs(Ft_total))) / H,
    )